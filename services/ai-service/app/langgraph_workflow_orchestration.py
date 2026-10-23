"""Durable LangGraph orchestration for follow-up workflows.

The graph sequences clinical read, context intelligence, and the existing
deterministic protocol. Gemini may prepare a narrative. It does not decide
eligibility. Human Review remains the only record of a human decision.
Checkpoints live in a SQLite file next to the review database, not in Mini HIS.
"""

from __future__ import annotations

import hashlib
import json
import operator
import pickle
import sqlite3
import threading
from contextlib import contextmanager
from datetime import datetime, timezone
from pathlib import Path
from typing import Annotated, Any, TypedDict

from langgraph.checkpoint.memory import InMemorySaver
from langgraph.errors import GraphInterrupt
from langgraph.graph import END, START, StateGraph
from langgraph.types import Command, interrupt

from app.followup_review import ReviewCaseStatus, ReviewOutcome
from app.missed_follow_up_review import MISSED_FOLLOW_UP_REVIEW_V1
from app.post_consultation_review import POST_CONSULTATION_RESULT_REVIEW_V1


WORKFLOW_DB_NAME = "agent-workflow.sqlite3"
POST_CONSULTATION = "post_consultation"
MISSED_FOLLOW_UP = "missed_follow_up"
PROTOCOL_IDS = {
    POST_CONSULTATION: POST_CONSULTATION_RESULT_REVIEW_V1,
    MISSED_FOLLOW_UP: MISSED_FOLLOW_UP_REVIEW_V1,
}
ALLOWED_DECISIONS = frozenset(item.value for item in ReviewOutcome)
TERMINAL_STATUSES = frozenset({"waiting_human", "completed"})
GRAPH_NODES = (
    "clinical_read",
    "context_intelligence",
    "protocol_evaluation",
    "eligibility_router",
    "narrative",
    "human_review",
    "await_human",
    "completion",
    "failure",
)

_SAVERS: dict[str, SqliteCheckpointSaver] = {}


class WorkflowNotFound(Exception):
    """No persisted workflow matches the identifier."""


class WorkflowNotSuspended(Exception):
    """Resume was requested for a workflow that is not waiting."""


class WorkflowDecisionRejected(Exception):
    """The decision does not match the closed Human Review case."""


class WorkflowReadError(Exception):
    """Clinical Read could not supply the authorized patient."""

    def __init__(self, code: str) -> None:
        super().__init__(code)
        self.code = code


class WorkflowState(TypedDict, total=False):
    """Shared graph state. Narrative text is intentionally absent."""

    workflow_id: str
    case_id: str
    workflow_type: str
    patient_reference: str | None
    clinical_context: dict
    clinical_context_intelligence: dict
    protocol_result: dict
    evidence: list
    narrative_status: str
    review_case_id: str | None
    review_status: str | None
    human_decision: str | None
    current_step: str
    error_code: str | None
    created_at: str
    updated_at: str
    route: str
    steps: Annotated[list[str], operator.add]


def workflow_id_for(case_id: str, workflow_type: str) -> str:
    """Stable id so a repeated start reuses one logical workflow."""
    digest = hashlib.sha256(f"workflow-v1:{workflow_type}:{case_id}".encode("utf-8")).hexdigest()
    return f"wf-{digest[:32]}"


def workflow_db_path(settings: Any) -> Path:
    return Path(settings.ai_review_db_path).resolve().parent / WORKFLOW_DB_NAME


def saver_for(path: Path) -> SqliteCheckpointSaver:
    key = str(Path(path).resolve())
    saver = _SAVERS.get(key)
    if saver is None:
        saver = SqliteCheckpointSaver(path)
        _SAVERS[key] = saver
    return saver


class SqliteCheckpointSaver(InMemorySaver):
    """In-memory LangGraph saver flushed to one local SQLite file.

    The pickle stores graph channels. The index stores the public projection
    so a status query does not need to resume the graph. Load only this
    service's own file.
    """

    def __init__(self, path: Path) -> None:
        super().__init__()
        self.path = Path(path)
        self.gate = threading.Lock()
        self.flush_lock = threading.RLock()
        self.path.parent.mkdir(parents=True, exist_ok=True)
        self._init_db()
        self._load()

    def put(self, config, checkpoint, metadata, new_versions):
        with self.flush_lock:
            stored = super().put(config, checkpoint, metadata, new_versions)
            self._flush()
            return stored

    def put_writes(self, config, writes, task_id, task_path=""):
        with self.flush_lock:
            super().put_writes(config, writes, task_id, task_path)
            self._flush()

    def delete_thread(self, thread_id: str) -> None:
        with self.flush_lock:
            super().delete_thread(thread_id)
            self._flush()

    def index_get(self, workflow_id: str) -> dict | None:
        return read_workflow_record(self.path, workflow_id)

    def index_save(self, view: dict) -> None:
        with self.flush_lock:
            _write_index(self.path, view)

    def _init_db(self) -> None:
        with _connect(self.path) as connection:
            connection.execute(
                """
                CREATE TABLE IF NOT EXISTS checkpoint_state (
                    id INTEGER PRIMARY KEY CHECK (id = 1),
                    payload BLOB NOT NULL
                )
                """
            )
            connection.execute(
                """
                CREATE TABLE IF NOT EXISTS workflow_index (
                    workflow_id TEXT PRIMARY KEY,
                    case_id TEXT NOT NULL,
                    workflow_type TEXT NOT NULL,
                    review_case_id TEXT,
                    status TEXT NOT NULL,
                    updated_at TEXT NOT NULL,
                    payload TEXT NOT NULL,
                    UNIQUE (case_id, workflow_type)
                )
                """
            )

    def _flush(self) -> None:
        payload = pickle.dumps(_export_memory(self), protocol=pickle.HIGHEST_PROTOCOL)
        with _connect(self.path) as connection:
            connection.execute(
                """
                INSERT INTO checkpoint_state (id, payload) VALUES (1, ?)
                ON CONFLICT(id) DO UPDATE SET payload = excluded.payload
                """,
                (payload,),
            )

    def _load(self) -> None:
        with _connect(self.path) as connection:
            row = connection.execute("SELECT payload FROM checkpoint_state WHERE id = 1").fetchone()
        if row is None:
            return
        _import_memory(self, pickle.loads(row[0]))


def compile_workflow(ports: Any, saver: SqliteCheckpointSaver):
    """Build the real StateGraph. Nodes close over ports; checkpoints do not."""

    def clinical_read(state: WorkflowState) -> dict:
        try:
            patient = ports.read_patient(state["case_id"], state["workflow_type"])
        except WorkflowReadError as exc:
            return _step(
                "clinical_read",
                patient_reference=None,
                error_code=exc.code,
            )
        return _step("clinical_read", patient_reference=patient, error_code=None)

    def context_intelligence(state: WorkflowState) -> dict:
        if state.get("error_code"):
            failure = {}
            reader = getattr(ports, "federation_failure_context", None)
            if callable(reader):
                failure = reader() or {}
            return _step(
                "context_intelligence",
                clinical_context=failure or _empty_context(),
                clinical_context_intelligence=_empty_intelligence(),
            )
        built = ports.build_context(state["case_id"])
        return _step(
            "context_intelligence",
            clinical_context=built.get("context") or _empty_context(),
            clinical_context_intelligence=built.get("intelligence") or _empty_intelligence(),
        )

    def protocol_evaluation(state: WorkflowState) -> dict:
        if state.get("error_code"):
            result = _unavailable_protocol(state["workflow_type"], state["error_code"])
        else:
            result = ports.evaluate(state["case_id"], state["workflow_type"])
        intelligence = dict(state.get("clinical_context_intelligence") or {})
        intelligence["evaluationStatus"] = result.get("evaluationStatus")
        intelligence["reasonCodes"] = list(result.get("reasonCodes") or [])
        error_code = state.get("error_code")
        if result.get("evaluationStatus") == "unavailable" and not error_code:
            error_code = "evaluation_unavailable"
        return _step(
            "protocol_evaluation",
            protocol_result=result,
            evidence=list(result.get("evidence") or []),
            clinical_context_intelligence=intelligence,
            error_code=error_code,
        )

    def eligibility_router(state: WorkflowState) -> dict:
        status = (state.get("protocol_result") or {}).get("evaluationStatus")
        if state.get("error_code") or status in {None, "", "unavailable", "not_evaluated"}:
            route = "failure"
        elif status == "matched":
            route = "narrative"
        elif status in {"not_matched", "insufficient"}:
            route = "completion"
        else:
            route = "failure"
        return _step("eligibility_router", route=route)

    def narrative(state: WorkflowState) -> dict:
        status = ports.prepare_narrative(state)
        return _step("narrative", narrative_status=status)

    def human_review(state: WorkflowState) -> dict:
        review_id = state.get("review_case_id")
        if not review_id:
            review_id = ports.ensure_review(state)
        if not review_id:
            return _step("human_review", error_code="review_not_created", review_status=None)
        ports.store_prepared_narrative(review_id, state)
        if getattr(ports, "fail_after_ensure", False):
            raise RuntimeError("review persisted before the node finished")
        return _step(
            "human_review",
            review_case_id=review_id,
            review_status="open",
            current_step="await_human",
            error_code=None,
        )

    def await_human(state: WorkflowState) -> dict:
        decision = interrupt(
            {"workflowId": state["workflow_id"], "reviewCaseId": state["review_case_id"]}
        )
        if decision not in ALLOWED_DECISIONS:
            return _step("await_human", error_code="decision_rejected")
        return _step(
            "await_human",
            human_decision=decision,
            review_status="closed",
            error_code=None,
        )

    def completion(state: WorkflowState) -> dict:
        status = (state.get("protocol_result") or {}).get("evaluationStatus")
        review_status = state.get("review_status")
        if status == "matched":
            review_status = "closed"
        elif status in {"not_matched", "insufficient"}:
            review_status = "not_required"
        return _step("completion", current_step="completed", review_status=review_status)

    def failure(state: WorkflowState) -> dict:
        return _step("failure", current_step="failed")

    def route_protocol(state: WorkflowState) -> str:
        return state.get("route") or "failure"

    def route_after_review(state: WorkflowState) -> str:
        if state.get("error_code") or not state.get("review_case_id"):
            return "failure"
        return "await_human"

    def route_after_human(state: WorkflowState) -> str:
        if state.get("error_code"):
            return "failure"
        return "completion"

    graph = StateGraph(WorkflowState)
    graph.add_node("clinical_read", clinical_read)
    graph.add_node("context_intelligence", context_intelligence)
    graph.add_node("protocol_evaluation", protocol_evaluation)
    graph.add_node("eligibility_router", eligibility_router)
    graph.add_node("narrative", narrative)
    graph.add_node("human_review", human_review)
    graph.add_node("await_human", await_human)
    graph.add_node("completion", completion)
    graph.add_node("failure", failure)
    graph.add_edge(START, "clinical_read")
    graph.add_edge("clinical_read", "context_intelligence")
    graph.add_edge("context_intelligence", "protocol_evaluation")
    graph.add_edge("protocol_evaluation", "eligibility_router")
    graph.add_conditional_edges(
        "eligibility_router",
        route_protocol,
        {"narrative": "narrative", "completion": "completion", "failure": "failure"},
    )
    graph.add_edge("narrative", "human_review")
    graph.add_conditional_edges(
        "human_review",
        route_after_review,
        {"await_human": "await_human", "failure": "failure"},
    )
    graph.add_conditional_edges(
        "await_human",
        route_after_human,
        {"completion": "completion", "failure": "failure"},
    )
    graph.add_edge("completion", END)
    graph.add_edge("failure", END)
    return graph.compile(checkpointer=saver)


def start_workflow(saver: SqliteCheckpointSaver, ports: Any, case_id: str, workflow_type: str) -> dict:
    """Start or reuse one workflow. A waiting or completed run is not repeated."""
    if workflow_type not in PROTOCOL_IDS:
        raise ValueError("workflow type is invalid")
    workflow_id = workflow_id_for(case_id, workflow_type)
    with saver.gate:
        existing = saver.index_get(workflow_id)
        if existing and existing.get("status") in TERMINAL_STATUSES:
            return existing
        graph = compile_workflow(ports, saver)
        config = _config(workflow_id)
        snapshot = _safe_state(graph, config)
        if _interrupted(snapshot):
            view = project(snapshot)
            saver.index_save(view)
            return view
        if _completed(snapshot):
            view = project(snapshot)
            saver.index_save(view)
            return view
        if _has_workflow(snapshot):
            saver.delete_thread(workflow_id)
        try:
            graph.invoke(_initial(workflow_id, case_id, workflow_type), config)
        except GraphInterrupt:
            pass
        except Exception:
            view = _failed_view(graph, config, workflow_id, case_id, workflow_type)
            saver.index_save(view)
            return view
        view = project(_safe_state(graph, config))
        saver.index_save(view)
        return view


def resume_workflow(
    saver: SqliteCheckpointSaver,
    ports: Any,
    workflow_id: str,
    decision: str,
    *,
    review_case_id: str,
    stored_outcome: str | None,
    case_is_closed: bool,
) -> dict:
    """Continue only a suspended workflow whose decision is already stored."""
    with saver.gate:
        current = saver.index_get(workflow_id)
        if current is None:
            raise WorkflowNotFound
        if current.get("status") != "waiting_human":
            raise WorkflowNotSuspended
        if (
            not case_is_closed
            or stored_outcome not in ALLOWED_DECISIONS
            or decision != stored_outcome
            or current.get("reviewCaseId") != review_case_id
        ):
            raise WorkflowDecisionRejected
        graph = compile_workflow(ports, saver)
        config = _config(workflow_id)
        graph.invoke(Command(resume=decision), config)
        view = project(_safe_state(graph, config))
        saver.index_save(view)
        return view


def resume_after_human_decision(settings: Any, repository: Any, review_case_id: str, outcome: str) -> dict | None:
    """Resume the workflow that is waiting for this closed review, if one exists."""
    path = workflow_db_path(settings)
    if not path.exists():
        return None
    current = read_workflow_by_review(path, review_case_id)
    if current is None or current.get("status") != "waiting_human":
        return None
    case = repository.get(review_case_id)
    if case is None or case.status is not ReviewCaseStatus.CLOSED or case.outcome is None:
        return None
    if case.outcome.value != outcome:
        return None
    return resume_workflow(
        saver_for(path),
        build_live_ports(settings, repository),
        current["workflowId"],
        outcome,
        review_case_id=review_case_id,
        stored_outcome=case.outcome.value,
        case_is_closed=True,
    )


def project(snapshot: Any) -> dict:
    """Public view. Checkpoint channel blobs stay inside the saver."""
    state = {} if snapshot is None else dict(getattr(snapshot, "values", None) or {})
    next_nodes = () if snapshot is None else tuple(getattr(snapshot, "next", ()) or ())
    interrupted = _interrupted(snapshot) or "await_human" in next_nodes
    current_step = "await_human" if interrupted else state.get("current_step")
    if interrupted:
        status = "waiting_human"
    elif current_step == "failed" or (state.get("error_code") and current_step != "completed"):
        status = "failed"
    elif current_step == "completed":
        status = "completed"
    else:
        status = "running"
    return {
        "workflowId": state.get("workflow_id"),
        "caseId": state.get("case_id"),
        "workflowType": state.get("workflow_type"),
        "status": status,
        "currentStep": current_step,
        "patientReference": state.get("patient_reference"),
        "clinicalContext": state.get("clinical_context") or {},
        "clinicalContextIntelligence": state.get("clinical_context_intelligence") or {},
        "protocol": state.get("protocol_result") or {},
        "evidence": list(state.get("evidence") or []),
        "narrativeStatus": state.get("narrative_status") or "not_started",
        "reviewCaseId": state.get("review_case_id"),
        "reviewStatus": state.get("review_status"),
        "humanDecision": state.get("human_decision"),
        "errorCode": state.get("error_code"),
        "steps": list(state.get("steps") or []),
        "createdAt": state.get("created_at"),
        "updatedAt": state.get("updated_at"),
    }


def read_workflow_record(path: Path, workflow_id: str) -> dict | None:
    rows = _read_payloads(path, "SELECT payload FROM workflow_index WHERE workflow_id = ?", (workflow_id,))
    return rows[0] if rows else None


def read_workflows_for_case(path: Path, case_id: str) -> list[dict]:
    return _read_payloads(
        path,
        "SELECT payload FROM workflow_index WHERE case_id = ? ORDER BY updated_at",
        (case_id,),
    )


def read_workflow_by_review(path: Path, review_case_id: str) -> dict | None:
    rows = _read_payloads(
        path,
        "SELECT payload FROM workflow_index WHERE review_case_id = ?",
        (review_case_id,),
    )
    return rows[0] if rows else None


def execution_snapshot(saver: SqliteCheckpointSaver, workflow_id: str) -> dict:
    """Read checkpoint position. This does not resume the graph."""
    graph = compile_workflow(_IdlePorts(), saver)
    snapshot = _safe_state(graph, _config(workflow_id))
    return {
        "interrupts": len(tuple(getattr(snapshot, "interrupts", ()) or ())) if snapshot else 0,
        "next": list(getattr(snapshot, "next", ()) or ()) if snapshot else [],
        "view": project(snapshot) if _has_workflow(snapshot) else None,
    }


class LivePorts:
    """Production adapters. Tests inject their own ports and do not use this object."""

    def __init__(self, settings: Any, service: Any, client: Any, federation: Any = None) -> None:
        self.settings = settings
        self.service = service
        self.client = client
        self.federation = federation
        self.fail_after_ensure = False
        self._protocols: dict[tuple[str, str], Any] = {}
        self._pending: dict[str, str] = {}
        self._federation_envelope: dict | None = None
        self._federation_projection: dict | None = None
        self._federation_failure: dict | None = None

    def federation_failure_context(self) -> dict:
        return dict(self._federation_failure or {})

    def read_patient(self, case_id: str, workflow_type: str) -> str:
        if self.federation is None:
            return self._read_patient_single(case_id, workflow_type)
        return self._read_patient_federated(case_id)

    def _read_patient_single(self, case_id: str, workflow_type: str) -> str:
        del workflow_type
        from app.langgraph_fhir_client import BoundedSearchStatus
        from app.langgraph_fhir_followup import case_resolution_search_path

        try:
            result = self.client.search(case_resolution_search_path(case_id), "Patient")
        except Exception as exc:
            raise WorkflowReadError("acquisition_unavailable") from exc
        resources = getattr(result, "resources", ())
        if result.status is not BoundedSearchStatus.COMPLETE or len(resources) != 1:
            raise WorkflowReadError("acquisition_unavailable")
        resource = resources[0]
        patient_id = resource.get("id") if isinstance(resource, dict) else None
        if not isinstance(patient_id, str) or not patient_id:
            raise WorkflowReadError("acquisition_unavailable")
        return f"Patient/{patient_id}"

    def _read_patient_federated(self, case_id: str) -> str:
        from app.clinical_federation_client import FederationClientError
        from app.federated_clinical_context import adapt_federation_envelope, failure_projection

        self._federation_envelope = None
        self._federation_projection = None
        self._federation_failure = None
        try:
            envelope = self.federation.query(case_id)
        except FederationClientError as exc:
            self._federation_failure = failure_projection(exc.code)
            raise WorkflowReadError(exc.code) from exc
        except Exception as exc:
            self._federation_failure = failure_projection("federation_unavailable")
            raise WorkflowReadError("federation_unavailable") from exc
        if envelope.get("status") == "failed":
            context, projection = adapt_federation_envelope(envelope, case_id)
            self._federation_failure = _federation_state(context, projection)
            raise WorkflowReadError("federation_failed")
        context, projection = adapt_federation_envelope(envelope, case_id)
        self._federation_envelope = envelope
        self._federation_projection = projection
        if not context.patient_id:
            self._federation_failure = _federation_state(context, projection)
            raise WorkflowReadError("federation_patient_missing")
        return f"Patient/{context.patient_id}"

    def build_context(self, case_id: str) -> dict:
        if self.federation is not None:
            return self._build_federated_context(case_id)
        from datetime import datetime as clock
        from datetime import timezone as tz

        from app.clinical_context_intelligence import analyze_clinical_context
        from app.longitudinal_context import build_longitudinal_context

        try:
            context = build_longitudinal_context(self.client, case_id)
            analysis = analyze_clinical_context(context, evaluated_at=clock.now(tz.utc))
        except Exception:
            return {"context": _empty_context(), "intelligence": _empty_intelligence()}
        return {"context": _reduce_context(context), "intelligence": _reduce_intelligence(analysis)}

    def _build_federated_context(self, case_id: str) -> dict:
        from datetime import datetime as clock
        from datetime import timezone as tz

        from app.clinical_context_intelligence import analyze_clinical_context
        from app.federated_clinical_context import adapt_federation_envelope, project_context

        if self._federation_envelope is None:
            return {"context": self._federation_failure or _empty_context(), "intelligence": _empty_intelligence()}
        context, projection = adapt_federation_envelope(self._federation_envelope, case_id)
        try:
            analysis = analyze_clinical_context(context, evaluated_at=clock.now(tz.utc))
            intelligence = _reduce_intelligence(analysis)
        except Exception:
            intelligence = _empty_intelligence()
        return {"context": project_context(context, projection), "intelligence": intelligence}

    def evaluate(self, case_id: str, workflow_type: str) -> dict:
        if self.federation is not None:
            return self._evaluate_federated(case_id, workflow_type)
        try:
            return self._evaluate(case_id, workflow_type)
        except Exception:
            return _unavailable_protocol(workflow_type, "evaluation_unavailable")

    def _evaluate_federated(self, case_id: str, workflow_type: str) -> dict:
        """Apply the existing rule to the envelope. Do not query Clinical Read."""
        from datetime import datetime as clock
        from datetime import timezone as tz

        from app.federated_protocol_evaluation import evaluate_federated_protocol

        envelope = self._federation_envelope or {}
        result, review = evaluate_federated_protocol(envelope, workflow_type, clock.now(tz.utc))
        if review is not None:
            self._protocols[(case_id, workflow_type)] = review
        return result

    def prepare_narrative(self, state: dict) -> str:
        if self._narrative_exists(state):
            return "stored"
        text = self._generate(state)
        if not text:
            return "unavailable"
        self._pending[state["workflow_id"]] = text
        return "prepared"

    def ensure_review(self, state: dict) -> str | None:
        protocol = self._protocols.get((state["case_id"], state["workflow_type"]))
        if protocol is None:
            return None
        case = self.service.ensure_for_protocol(state["case_id"], protocol)
        return None if case is None else case.id

    def store_prepared_narrative(self, review_case_id: str, state: dict) -> None:
        text = self._pending.pop(state["workflow_id"], None)
        if not text or not review_case_id:
            return
        case = self.service.get(review_case_id)
        if case.narrative_text:
            return
        self.service.record_narrative(review_case_id, text)

    def _evaluate(self, case_id: str, workflow_type: str) -> dict:
        from datetime import datetime as clock
        from datetime import timezone as tz

        from app.langgraph_fhir_client import ClientFHIRTransport
        from app.langgraph_fhir_followup import FollowUpFHIRAdapter, PostConsultationContextReader
        from app.missed_follow_up_service import evaluate_missed_follow_up_case
        from app.post_consultation_review import (
            ProtocolEvaluationStatus,
            ProtocolReviewResult,
            evaluate_post_consultation_review,
        )
        from app.missed_follow_up_review import REASON_MISSED

        instant = clock.now(tz.utc)
        adapter = FollowUpFHIRAdapter(ClientFHIRTransport(self.client), now=lambda: instant)
        if workflow_type == MISSED_FOLLOW_UP:
            evaluation = evaluate_missed_follow_up_case(adapter, case_id, instant)
            evidence = list(evaluation.triggers or evaluation.provenance_resources)[:8]
            if evaluation.status is ProtocolEvaluationStatus.MATCHED and evaluation.triggers:
                self._protocols[(case_id, workflow_type)] = ProtocolReviewResult(
                    id=MISSED_FOLLOW_UP_REVIEW_V1,
                    evaluation_status=ProtocolEvaluationStatus.MATCHED,
                    reason_codes=(REASON_MISSED,),
                    matched_resources=(evaluation.triggers[0],),
                    human_review_status="required",
                    human_review_reason="deterministic_missed_follow_up_protocol_match",
                    action_status="proposed",
                    action_type="review_follow_up_case",
                )
            return {
                "protocolId": MISSED_FOLLOW_UP_REVIEW_V1,
                "evaluationStatus": evaluation.status.value,
                "reasonCodes": list(evaluation.reason_codes)[:8],
                "evidence": evidence,
            }
        with adapter.bind_read(case_id):
            snapshot = PostConsultationContextReader(adapter).read(case_id)
        result = evaluate_post_consultation_review(snapshot)
        self._protocols[(case_id, workflow_type)] = result
        return {
            "protocolId": result.id,
            "evaluationStatus": result.evaluation_status.value,
            "reasonCodes": list(result.reason_codes)[:8],
            "evidence": list(result.matched_resources)[:8],
        }

    def _narrative_exists(self, state: dict) -> bool:
        from app.followup_review import ReviewCaseStatus

        protocol_id = PROTOCOL_IDS[state["workflow_type"]]
        for status in (ReviewCaseStatus.OPEN, ReviewCaseStatus.CLOSED):
            page = self.service.list_cases(status=status, case_id=state["case_id"], limit=20, after=None)
            for case in page.items:
                if case.protocol_id == protocol_id and case.narrative_text:
                    return True
        return False

    def _generate(self, state: dict) -> str | None:
        if self.federation is not None:
            from app.federated_protocol_evaluation import federated_narrative

            return federated_narrative(state)
        from app.missed_follow_up_narrative import configured_provider, generate_operational_narrative

        provider = configured_provider(self.settings)
        if provider is None:
            return None
        evidence = [item for item in state.get("evidence") or [] if isinstance(item, str)]
        if not evidence:
            return None
        brief = {
            "relationCodes": list((state.get("clinical_context_intelligence") or {}).get("relationCodes") or [])[:8],
            "missing": list((state.get("clinical_context_intelligence") or {}).get("missing") or [])[:8],
            "evaluationStatus": (state.get("protocol_result") or {}).get("evaluationStatus"),
        }
        if state["workflow_type"] == MISSED_FOLLOW_UP:
            appointments = [
                {"reference": item, "status": None, "start": None}
                for item in evidence
                if item.startswith("Appointment/")
            ]
            generation = generate_operational_narrative(
                provider,
                matched_resource=evidence[0],
                appointments=appointments,
                longitudinal_brief=brief,
            )
            return generation.text
        return _post_consultation_narrative(provider, evidence[0], brief)


def build_live_ports(settings: Any, repository: Any) -> LivePorts:
    """Single mode reads Clinical Read. Federated mode reads the Java federation envelope."""
    from app.clinical_federation_client import ClinicalFederationClient
    from app.clinical_read_client import ClinicalReadClient
    from app.followup_review import FollowUpReviewCaseService

    client = ClinicalReadClient.from_settings(settings)
    federation = None
    if getattr(settings, "clinical_context_mode", "single") == "federated":
        federation = ClinicalFederationClient.from_settings(settings)
    return LivePorts(settings, FollowUpReviewCaseService(repository), client, federation)


class _IdlePorts:
    """Ports for a read-only checkpoint inspection. Nodes are not executed."""

    fail_after_ensure = False

    def read_patient(self, case_id: str, workflow_type: str) -> str:
        raise RuntimeError("checkpoint inspection does not read clinical data")

    def build_context(self, case_id: str) -> dict:
        raise RuntimeError("checkpoint inspection does not build context")

    def evaluate(self, case_id: str, workflow_type: str) -> dict:
        raise RuntimeError("checkpoint inspection does not evaluate a protocol")

    def prepare_narrative(self, state: dict) -> str:
        raise RuntimeError("checkpoint inspection does not prepare a narrative")

    def ensure_review(self, state: dict) -> str | None:
        raise RuntimeError("checkpoint inspection does not create a review")

    def store_prepared_narrative(self, review_case_id: str, state: dict) -> None:
        raise RuntimeError("checkpoint inspection does not store a narrative")


def _post_consultation_narrative(provider: Any, matched_resource: str, brief: dict) -> str | None:
    """Operational proposal for a matched post-consultation review. Not an eligibility decision."""
    from app.missed_follow_up_narrative import NARRATIVE_SCHEMA

    instruction = "\n".join(
        (
            "You write one operational review proposal for a result read after a consultation.",
            "Write answer in clear Spanish for health professionals in Peru and Latin America.",
            "Use only the matched resource and the brief in the input.",
            "Keep FHIR resource identifiers unchanged.",
            "Describe the evidence that was read and any listed missing information.",
            "A partial source list is not a complete chart.",
            "Do not invent clinical facts, codes, units, or normal results for a gap.",
            "State that the responsible professional reviews the case.",
            "Do not diagnose.",
            "Do not recommend treatment.",
            "Do not decide whether the protocol matches.",
            "Do not order a message, a call, or any other communication.",
            "Do not select an operational outcome.",
            "Return JSON with answer and no other decision.",
        )
    )
    payload = json.dumps(
        {"matchedResource": matched_resource, "brief": brief},
        ensure_ascii=False,
        sort_keys=True,
        separators=(",", ":"),
    )
    try:
        generation = provider.generate_structured(
            system_instruction=instruction,
            contents=payload,
            response_json_schema=NARRATIVE_SCHEMA,
            max_output_tokens=1024,
        )
    except Exception:
        return None
    if getattr(generation, "error", None) or not isinstance(getattr(generation, "text", None), str):
        return None
    try:
        parsed = json.loads(generation.text)
    except json.JSONDecodeError:
        return None
    answer = parsed.get("answer") if isinstance(parsed, dict) else None
    if not isinstance(answer, str) or not answer.strip():
        return None
    return answer


def _initial(workflow_id: str, case_id: str, workflow_type: str) -> dict:
    now = _now()
    return {
        "workflow_id": workflow_id,
        "case_id": case_id,
        "workflow_type": workflow_type,
        "patient_reference": None,
        "clinical_context": {},
        "clinical_context_intelligence": {},
        "protocol_result": {},
        "evidence": [],
        "narrative_status": "not_started",
        "review_case_id": None,
        "review_status": None,
        "human_decision": None,
        "current_step": "start",
        "error_code": None,
        "created_at": now,
        "updated_at": now,
        "route": "",
        "steps": [],
    }


def _step(name: str, **fields: Any) -> dict:
    fields.setdefault("current_step", name)
    fields["steps"] = [name]
    fields["updated_at"] = _now()
    return fields


def _config(workflow_id: str) -> dict:
    return {"configurable": {"thread_id": workflow_id}}


def _now() -> str:
    return datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ")


def _empty_context() -> dict:
    return {
        "schema": "LONGITUDINAL_CONTEXT_V1",
        "contextStatus": "unavailable",
        "truncated": False,
        "counts": {"encounters": 0, "observations": 0, "appointments": 0},
    }


def _empty_intelligence() -> dict:
    return {
        "schema": "CLINICAL_CONTEXT_INTELLIGENCE_V1",
        "contextStatus": "unavailable",
        "truncated": False,
        "relationCodes": [],
        "missing": ["longitudinal_context_unavailable"],
        "conflictCodes": [],
    }


def _unavailable_protocol(workflow_type: str, reason: str) -> dict:
    return {
        "protocolId": PROTOCOL_IDS[workflow_type],
        "evaluationStatus": "unavailable",
        "reasonCodes": [reason],
        "evidence": [],
    }


def _federation_state(context: Any, projection: dict) -> dict:
    from app.federated_clinical_context import project_context

    return project_context(context, projection)


def _reduce_context(context: Any) -> dict:
    patient = f"Patient/{context.patient_id}" if context.patient_id else None
    return {
        "schema": "LONGITUDINAL_CONTEXT_V1",
        "contextStatus": context.status,
        "truncated": bool(context.truncated),
        "patientReference": patient,
        "counts": {
            "encounters": len(context.encounters),
            "observations": len(context.observations),
            "appointments": len(context.appointments),
        },
    }


def _reduce_intelligence(analysis: Any) -> dict:
    confirmed = [item.code for item in analysis.relations if item.kind == "confirmed"][:8]
    return {
        "schema": "CLINICAL_CONTEXT_INTELLIGENCE_V1",
        "contextStatus": analysis.context_status,
        "truncated": bool(analysis.truncated),
        "relationCodes": confirmed,
        "missing": list(analysis.missing)[:8],
        "conflictCodes": [item.code for item in analysis.conflicts][:8],
    }


def _safe_state(graph: Any, config: dict) -> Any:
    try:
        return graph.get_state(config)
    except Exception:
        return None


def _interrupted(snapshot: Any) -> bool:
    if snapshot is None:
        return False
    return bool(tuple(getattr(snapshot, "interrupts", ()) or ()))


def _has_workflow(snapshot: Any) -> bool:
    if snapshot is None:
        return False
    values = getattr(snapshot, "values", None) or {}
    return bool(values.get("workflow_id"))


def _completed(snapshot: Any) -> bool:
    if not _has_workflow(snapshot) or _interrupted(snapshot):
        return False
    values = getattr(snapshot, "values", None) or {}
    return values.get("current_step") == "completed"


def _failed_view(graph: Any, config: dict, workflow_id: str, case_id: str, workflow_type: str) -> dict:
    snapshot = _safe_state(graph, config)
    if _has_workflow(snapshot):
        view = project(snapshot)
    else:
        now = _now()
        view = {
            "workflowId": workflow_id,
            "caseId": case_id,
            "workflowType": workflow_type,
            "status": "failed",
            "currentStep": "failed",
            "patientReference": None,
            "clinicalContext": {},
            "clinicalContextIntelligence": {},
            "protocol": {},
            "evidence": [],
            "narrativeStatus": "not_started",
            "reviewCaseId": None,
            "reviewStatus": None,
            "humanDecision": None,
            "errorCode": "node_failed",
            "steps": [],
            "createdAt": now,
            "updatedAt": now,
        }
    view["status"] = "failed"
    view["currentStep"] = "failed"
    if not view.get("errorCode"):
        view["errorCode"] = "node_failed"
    return view


@contextmanager
def _connect(path: Path):
    connection = sqlite3.connect(path, timeout=5)
    try:
        connection.execute("PRAGMA journal_mode=WAL")
        yield connection
        connection.commit()
    finally:
        connection.close()


def _write_index(path: Path, view: dict) -> None:
    payload = json.dumps(view, ensure_ascii=False, sort_keys=True)
    with _connect(path) as connection:
        connection.execute(
            """
            INSERT INTO workflow_index (
                workflow_id, case_id, workflow_type, review_case_id, status, updated_at, payload
            ) VALUES (?, ?, ?, ?, ?, ?, ?)
            ON CONFLICT(workflow_id) DO UPDATE SET
                review_case_id = excluded.review_case_id,
                status = excluded.status,
                updated_at = excluded.updated_at,
                payload = excluded.payload
            """,
            (
                view.get("workflowId"),
                view.get("caseId"),
                view.get("workflowType"),
                view.get("reviewCaseId"),
                view.get("status"),
                view.get("updatedAt") or _now(),
                payload,
            ),
        )


def _read_payloads(path: Path, query: str, params: tuple) -> list[dict]:
    file_path = Path(path)
    if not file_path.exists():
        return []
    try:
        connection = sqlite3.connect(file_path, timeout=5)
        connection.execute("PRAGMA query_only = ON")
        try:
            rows = connection.execute(query, params).fetchall()
        finally:
            connection.close()
    except sqlite3.DatabaseError:
        return []
    views: list[dict] = []
    for row in rows:
        try:
            parsed = json.loads(row[0])
        except (TypeError, json.JSONDecodeError):
            continue
        if isinstance(parsed, dict):
            views.append(parsed)
    return views


def _export_memory(saver: SqliteCheckpointSaver) -> dict:
    return {
        "storage": {
            thread: {namespace: dict(checkpoints) for namespace, checkpoints in namespaces.items()}
            for thread, namespaces in saver.storage.items()
        },
        "writes": {key: dict(value) for key, value in saver.writes.items()},
        "blobs": dict(saver.blobs),
    }


def _import_memory(saver: SqliteCheckpointSaver, payload: dict) -> None:
    for thread, namespaces in payload.get("storage", {}).items():
        for namespace, checkpoints in namespaces.items():
            saver.storage[thread][namespace].update(checkpoints)
    for key, value in payload.get("writes", {}).items():
        saver.writes[key].update(value)
    saver.blobs.update(payload.get("blobs", {}))
