"""C16-R application boundary. Deterministic tests inject a model and an in-memory client.

Live model reads are skipped unless both opt-in flags are true.
"""

from __future__ import annotations

import inspect
import json
import logging
import os
import threading
from dataclasses import asdict
from datetime import datetime, timezone
from pathlib import Path

import httpx
import pytest
from langchain_core.messages import AIMessage, HumanMessage, ToolMessage

from app.langgraph_fhir_client import (
    APPOINTMENT_ID,
    APPOINTMENTS_TOOL,
    BOUNDARY_EVENTS,
    CASE_IDENTIFIER_SYSTEM,
    DENIAL_ANSWER,
    FOLLOWUP_TOOL,
    PATIENT_CASE,
    PATIENT_ID,
    POLICY_VERSION,
    SAFE_AUDIT_FIELDS,
    CASE_ID_MISMATCH_REASON,
    ClientFHIRTransport,
    FailingPreparedReadClient,
    InMemoryAuditSink,
    PolicyAuditEvent,
    PreparedReadClient,
    ReadClientError,
    clear_boundary_events,
    evaluate_tool_policy,
    record_policy_audit,
    synthetic_followup_appointment,
)
from app.followup_models import dump_followup_endpoint_response
from app.followup_service import _project
from app.langgraph_fhir_followup import (
    UNAVAILABLE_ANSWER,
    FollowUpFHIRAdapter,
    appointment_search_path,
    case_search_path,
    make_followup_tool,
)
from app.langgraph_fhir_hapi import HapiReadClient, hapi_base_url
from app.langgraph_followup_workflow import (
    APPLICATION_RESPONSIBILITIES,
    LANGGRAPH_RESPONSIBILITIES,
    MAX_MODEL_TURNS,
    FollowUpWorkflow,
    FollowUpWorkflowResult,
    build_live_followup_workflow,
)
from app.langgraph_gemini_fhir_followup import (
    FINAL_DECISION_REQUEST,
    MODEL_LIMIT_ANSWER,
    followup_message_from_response,
)


APP = Path(__file__).resolve().parents[1] / "app"
C15_MODULES = (
    "followup_models.py",
    "gemini_provider.py",
    "llm_provider.py",
    "main.py",
    "config.py",
)
PATIENT_PATH = f"Patient/{PATIENT_ID}"
OBSERVATION_PATH = f"Observation?subject=Patient/{PATIENT_ID}"
PROTOCOL_CASE_PATH = f"{case_search_path(PATIENT_CASE)}&_count=2"
PROTOCOL_ENCOUNTER_PATH = f"Encounter?patient=Patient/{PATIENT_ID}&status=finished&_count=25"
PROTOCOL_OBSERVATION_PATH = f"{OBSERVATION_PATH}&status=final&_count=25"
PROTOCOL_APPOINTMENT_PATH = f"Appointment?patient=Patient/{PATIENT_ID}&_count=25"
CASE_READS = [
    PROTOCOL_CASE_PATH,
    PATIENT_PATH,
    PROTOCOL_ENCOUNTER_PATH,
    PROTOCOL_OBSERVATION_PATH,
    PROTOCOL_APPOINTMENT_PATH,
]
FINAL_TEXT = "Context received from the model."
THOUGHT_SIGNATURE = b"\x01synthetic-thought-signature"
CLINICAL_TEXT = (
    "Synthetic Patient",
    "Synthetic observation result",
    "obs-synthetic-001",
    PATIENT_ID,
    "valueString",
    "resourceType",
)


def _live_gemini() -> bool:
    return os.getenv("RUN_LIVE_GEMINI_TESTS", "false").strip().lower() == "true"


def _hapi_enabled() -> bool:
    return os.getenv("RUN_HAPI_INTEGRATION_TESTS", "false").strip().lower() == "true"


class ScriptedModel:
    def __init__(self, replies: list[AIMessage]) -> None:
        self.replies = list(replies)
        self.seen: list[list[object]] = []

    def __call__(self, messages):
        self.seen.append(list(messages))
        if not self.replies:
            raise AssertionError("model called after the script ended")
        return self.replies.pop(0)


class MemoryReadClient:
    """In-memory FHIR reads. This client does not open a socket."""

    def __init__(
        self,
        *,
        name: str = "Synthetic Patient",
        observation_id: str = "obs-synthetic-001",
        value: str = "Synthetic observation result",
    ) -> None:
        self.name = name
        self.observation_id = observation_id
        self.value = value
        self.calls: list[str] = []

    def get(self, path: str) -> dict:
        self.calls.append(path)
        if path in {case_search_path(PATIENT_CASE), PROTOCOL_CASE_PATH}:
            return {
                "resourceType": "Bundle",
                "type": "searchset",
                "entry": [
                    {
                        "resource": {
                            "resourceType": "Patient",
                            "id": PATIENT_ID,
                            "identifier": [
                                {"system": CASE_IDENTIFIER_SYSTEM, "value": PATIENT_CASE}
                            ],
                            "name": [{"text": self.name}],
                        }
                    }
                ],
            }
        if path.startswith("Patient?identifier="):
            return {"resourceType": "Bundle", "type": "searchset", "entry": []}
        if path == PATIENT_PATH:
            return {
                "resourceType": "Patient",
                "id": PATIENT_ID,
                "name": [{"text": self.name}],
            }
        if path in {OBSERVATION_PATH, PROTOCOL_OBSERVATION_PATH}:
            return {
                "resourceType": "Bundle",
                "type": "searchset",
                "entry": [
                    {
                        "resource": {
                            "resourceType": "Observation",
                            "id": self.observation_id,
                            "status": "final",
                            "subject": {"reference": f"Patient/{PATIENT_ID}"},
                            "encounter": {"reference": "Encounter/enc-synthetic-001"},
                            "issued": "2026-09-25T12:30:00Z",
                            "valueString": self.value,
                        }
                    }
                ],
            }
        if path == PROTOCOL_ENCOUNTER_PATH:
            return {
                "resourceType": "Bundle",
                "type": "searchset",
                "entry": [
                    {
                        "resource": {
                            "resourceType": "Encounter",
                            "id": "enc-synthetic-001",
                            "status": "finished",
                            "subject": {"reference": f"Patient/{PATIENT_ID}"},
                            "period": {"end": "2026-09-25T12:00:00Z"},
                        }
                    }
                ],
            }
        if path in {appointment_search_path(PATIENT_ID), PROTOCOL_APPOINTMENT_PATH}:
            return {
                "resourceType": "Bundle",
                "type": "searchset",
                "entry": [{"resource": synthetic_followup_appointment()}],
            }
        raise ReadClientError("unknown path")


@pytest.fixture(autouse=True)
def _clear_probe():
    clear_boundary_events()
    yield
    clear_boundary_events()


def _clock() -> str:
    return "2026-09-25T00:00:03Z"


def _tool_call(name: str = FOLLOWUP_TOOL, arguments: dict | None = None, call_id: str = "call-1") -> AIMessage:
    return AIMessage(
        content="",
        tool_calls=[
            {
                "name": name,
                "args": arguments if arguments is not None else {"case_id": PATIENT_CASE},
                "id": call_id,
                "type": "tool_call",
            }
        ],
    )


def _signed_tool_call() -> AIMessage:
    message = _tool_call()
    message.additional_kwargs["thought_signatures"] = {"call-1": THOUGHT_SIGNATURE}
    return message


def _workflow(client, model, sink: InMemoryAuditSink | None = None, **kwargs) -> FollowUpWorkflow:
    return FollowUpWorkflow(
        model=model,
        sink=sink or InMemoryAuditSink(),
        fhir_client=client,
        clock=_clock,
        run_id="run-workflow-001",
        **kwargs,
    )


def _audit_blob(sink: InMemoryAuditSink) -> str:
    return json.dumps([asdict(event) for event in sink.events])


def _read_answer(result: FollowUpWorkflowResult) -> str:
    return result.final_answer


def test_workflow_can_be_built_without_calling_a_model():
    def refuse(messages):
        raise AssertionError(messages)

    workflow = _workflow(MemoryReadClient(), refuse)
    assert workflow.policy is evaluate_tool_policy
    assert workflow.audit is record_policy_audit
    assert workflow._engine.model_calls == 0
    assert workflow.fhir_client.calls == []


def test_fake_model_returns_an_application_result():
    client = MemoryReadClient()
    sink = InMemoryAuditSink()
    result = _workflow(client, ScriptedModel([_signed_tool_call(), _final("unknown")]), sink).run(
        PATIENT_CASE
    )
    assert isinstance(result, FollowUpWorkflowResult)
    assert result.case_id == PATIENT_CASE
    assert result.status == "finish"
    assert result.final_answer == FINAL_TEXT
    assert result.patient["id"] == PATIENT_ID
    assert result.patient["name"] == "Synthetic Patient"
    assert result.observations[0]["id"] == "obs-synthetic-001"
    assert result.observations[0]["valueString"] == "Synthetic observation result"
    assert result.tools_used == [FOLLOWUP_TOOL]
    assert result.turns == 2
    assert result.evidence[0]["resources"] == [f"Patient/{PATIENT_ID}", "Observation/obs-synthetic-001"]
    assert not hasattr(result, "messages")
    assert set(asdict(result)) == {
        "case_id",
        "status",
        "final_answer",
        "patient",
        "observations",
        "evidence",
        "tools_used",
        "turns",
        "run_id",
        "follow_up_required",
        "context_patient",
        "context_observation",
        "schedule_check",
            "schedule_classifications",
            "schedule_appointments",
            "protocol",
            "encounter_collection",
            "observation_collection",
            "appointment_collection",
            "protocol_encounters",
    }
    assert result.context_patient == "resolved"
    assert result.context_observation == "with_resources"
    assert result.schedule_check == "checked"
    assert result.run_id == "run-workflow-001"
    assert result.follow_up_required == "unknown"
    blob = json.dumps(asdict(result), default=str)
    for token in ("AIMessage", "ToolMessage", "thought_signature", "function_call", "tool_call_id"):
        assert token not in blob
    assert "synthetic-thought-signature" not in blob
    assert client.calls == CASE_READS
    assert BOUNDARY_EVENTS.index(f"policy:{FOLLOWUP_TOOL}:allowed") < BOUNDARY_EVENTS.index(
        f"audit:{FOLLOWUP_TOOL}:allowed"
    )
    assert BOUNDARY_EVENTS.index(f"audit:{FOLLOWUP_TOOL}:allowed") < BOUNDARY_EVENTS.index(
        f"execute:{FOLLOWUP_TOOL}"
    )
    audit = _audit_blob(sink)
    assert set(asdict(sink.events[0]).keys()) == set(SAFE_AUDIT_FIELDS)
    forbidden = CLINICAL_TEXT + (
        "thought_signature",
        "synthetic-thought-signature",
        "prompt",
        "authorization",
        "AIza",
    )
    for text in forbidden:
        assert text not in audit
    assert FINAL_TEXT not in inspect.getsource(FollowUpWorkflow)


def test_injected_policy_is_called_before_the_tool():
    seen: list[str] = []

    def policy(name: str, **kwargs):
        seen.append(name)
        return evaluate_tool_policy(name, **kwargs)

    client = MemoryReadClient()
    _workflow(client, ScriptedModel([_tool_call(), _final("unknown")]), policy=policy).run(PATIENT_CASE)
    assert seen == [FOLLOWUP_TOOL]
    assert client.calls == CASE_READS


def test_denied_tool_does_not_read_fhir():
    client = MemoryReadClient()
    sink = InMemoryAuditSink()
    model = ScriptedModel([_tool_call("send_message", {"patient_id": PATIENT_ID, "body": "synthetic"})])
    result = _workflow(client, model, sink).run(PATIENT_CASE)
    assert result.status == "denied"
    assert result.final_answer == DENIAL_ANSWER
    assert result.follow_up_required == "unknown"
    assert result.patient is None
    assert result.observations == []
    assert result.evidence == []
    assert result.tools_used == []
    assert result.context_patient == "resolved"
    assert result.context_observation == "with_resources"
    assert result.schedule_check == "checked"
    assert client.calls == CASE_READS
    assert f"execute:{FOLLOWUP_TOOL}" not in BOUNDARY_EVENTS
    assert "execute:send_message" not in BOUNDARY_EVENTS
    assert BOUNDARY_EVENTS.index("policy:send_message:denied") < BOUNDARY_EVENTS.index("audit:send_message:denied")
    assert sink.events[0].decision == "denied"
    assert sink.events[0].tool_name == "send_message"
    assert model.seen and len(model.seen) == 1


def _policy_audit_lines(caplog: pytest.LogCaptureFixture) -> list[str]:
    return [
        record.getMessage()
        for record in caplog.records
        if record.name == "ai-service" and record.getMessage().startswith("followup_tool_policy_audit ")
    ]


def _assert_policy_audit_line(
    line: str,
    *,
    run_id: str,
    case_id: str,
    tool_name: str,
    decision: str,
    reason: str,
) -> None:
    assert line == (
        "followup_tool_policy_audit "
        f"run_id={run_id} case_id={case_id} tool_name={tool_name} "
        f"decision={decision} policy_version={POLICY_VERSION} reason={reason}"
    )
    for token in (
        "thought_signature",
        "synthetic-thought-signature",
        "gemini_api_key",
        "x-service-token",
        "authorization",
        "AIza",
        "Patient",
        "Observation",
        "Synthetic Patient",
        "Synthetic observation result",
        "valueString",
        "prompt",
        "completion",
        "args=",
        FINAL_TEXT,
        "clinical-note",
    ):
        assert token not in line


def test_allowed_tool_audit_is_logged_and_the_tool_still_runs(caplog):
    client = MemoryReadClient()
    sink = InMemoryAuditSink()
    with caplog.at_level(logging.INFO, logger="ai-service"):
        result = _workflow(
            client,
            ScriptedModel([_signed_tool_call(), _final("unknown")]),
            sink,
        ).run(PATIENT_CASE)
    assert result.status == "finish"
    assert result.run_id == "run-workflow-001"
    assert sink.events[0].run_id == result.run_id
    assert sink.events[0].decision == "allowed"
    assert client.calls == CASE_READS
    lines = _policy_audit_lines(caplog)
    assert len(lines) == 1
    _assert_policy_audit_line(
        lines[0],
        run_id=result.run_id,
        case_id=PATIENT_CASE,
        tool_name=FOLLOWUP_TOOL,
        decision="allowed",
        reason="read tool is allowed",
    )


def test_audit_sink_allocates_contiguous_sequences_for_concurrent_writes() -> None:
    writer_count = 8

    class SynchronizedSink(InMemoryAuditSink):
        def __init__(self) -> None:
            super().__init__()
            self.ready = threading.Barrier(writer_count)

        def record(self, *args: object, **kwargs: object) -> PolicyAuditEvent:
            self.ready.wait(timeout=5)
            return super().record(*args, **kwargs)

    sink = SynchronizedSink()
    returned_events: list[PolicyAuditEvent] = []
    errors: list[BaseException] = []
    result_lock = threading.Lock()

    def write_event(index: int) -> None:
        try:
            event = record_policy_audit(
                sink,
                run_id="concurrent-audit-run",
                case_id=PATIENT_CASE,
                tool_name=FOLLOWUP_TOOL,
                decision="allowed",
                reason=f"concurrent audit write {index}",
                timestamp=f"2026-01-01T00:00:{index:02d}+00:00",
            )
            with result_lock:
                returned_events.append(event)
        except BaseException as exc:
            with result_lock:
                errors.append(exc)

    threads = [
        threading.Thread(target=write_event, args=(index,))
        for index in range(writer_count)
    ]
    for thread in threads:
        thread.start()
    for thread in threads:
        thread.join(timeout=10)

    assert not [thread for thread in threads if thread.is_alive()]
    assert errors == []
    assert len(sink.events) == writer_count
    assert [event.sequence for event in sink.events] == list(range(1, writer_count + 1))
    assert sorted(event.sequence for event in returned_events) == list(
        range(1, writer_count + 1)
    )


def test_denied_tool_audit_is_logged_and_fhir_is_not_read(caplog):
    client = MemoryReadClient()
    sink = InMemoryAuditSink()
    model = ScriptedModel(
        [_tool_call("send_message", {"patient_id": PATIENT_ID, "body": "clinical-note"})]
    )
    with caplog.at_level(logging.INFO, logger="ai-service"):
        result = _workflow(client, model, sink).run(PATIENT_CASE)
    assert result.status == "denied"
    assert result.run_id == sink.events[0].run_id == "run-workflow-001"
    assert client.calls == CASE_READS
    assert "execute:send_message" not in BOUNDARY_EVENTS
    lines = _policy_audit_lines(caplog)
    assert len(lines) == 1
    _assert_policy_audit_line(
        lines[0],
        run_id=result.run_id,
        case_id=PATIENT_CASE,
        tool_name="send_message",
        decision="denied",
        reason="external effect is not allowed",
    )


def test_unknown_tool_audit_is_logged_and_the_tool_does_not_run(caplog):
    client = MemoryReadClient()
    sink = InMemoryAuditSink()
    model = ScriptedModel([_tool_call("unknown_tool", {"note": "clinical-note"})])
    with caplog.at_level(logging.INFO, logger="ai-service"):
        result = _workflow(client, model, sink).run(PATIENT_CASE)
    assert result.status == "denied"
    assert result.run_id == sink.events[0].run_id
    assert sink.events[0].reason == "unknown tool is not allowed"
    assert client.calls == CASE_READS
    assert "execute:unknown_tool" not in BOUNDARY_EVENTS
    lines = _policy_audit_lines(caplog)
    assert len(lines) == 1
    _assert_policy_audit_line(
        lines[0],
        run_id=result.run_id,
        case_id=result.case_id,
        tool_name="unknown_tool",
        decision="denied",
        reason="unknown tool is not allowed",
    )


def test_unknown_tool_is_denied_without_reading_fhir():
    client = MemoryReadClient()
    sink = InMemoryAuditSink()
    model = ScriptedModel([_tool_call("unknown_tool", {"case_id": PATIENT_CASE})])
    result = _workflow(client, model, sink).run(PATIENT_CASE)
    assert result.status == "denied"
    assert result.final_answer == DENIAL_ANSWER
    assert result.follow_up_required == "unknown"
    assert result.tools_used == []
    assert result.evidence == []
    assert client.calls == CASE_READS
    assert sink.events[0].decision == "denied"
    assert sink.events[0].tool_name == "unknown_tool"
    assert sink.events[0].reason == "unknown tool is not allowed"
    assert "execute:unknown_tool" not in BOUNDARY_EVENTS
    assert BOUNDARY_EVENTS.index("policy:unknown_tool:denied") < BOUNDARY_EVENTS.index(
        "audit:unknown_tool:denied"
    )


def test_known_case_resolves_the_patient_by_identifier():
    client = MemoryReadClient()
    result = _workflow(
        client,
        ScriptedModel([_tool_call(), _final("unknown")]),
    ).run(PATIENT_CASE)
    assert result.status == "finish"
    assert result.patient["id"] == PATIENT_ID
    assert result.patient["id"] != PATIENT_CASE
    assert result.observations[0]["id"] == "obs-synthetic-001"
    assert result.evidence[0]["resources"] == [f"Patient/{PATIENT_ID}", "Observation/obs-synthetic-001"]
    assert client.calls == CASE_READS
    assert f"Patient/{PATIENT_CASE}" not in client.calls


def test_missing_case_is_unavailable_and_does_not_read_another_patient():
    client = MemoryReadClient()
    missing = "SYN-FOLLOWUP-005"
    result = _workflow(
        client,
        ScriptedModel([_tool_call(arguments={"case_id": missing})]),
    ).run(missing)
    assert result.status == "unavailable"
    assert result.final_answer == UNAVAILABLE_ANSWER
    assert result.follow_up_required == "unknown"
    assert result.patient is None
    assert result.observations == []
    assert result.evidence == []
    assert result.tools_used == []
    assert result.context_patient == "not_resolved"
    assert result.context_observation == "not_read"
    assert result.schedule_check == "not_checked"
    assert client.calls == [f"{case_search_path(missing)}&_count=2"]
    assert PATIENT_PATH not in client.calls
    assert f"Patient/{missing}" not in client.calls


def test_resolution_does_not_treat_the_case_id_as_the_patient_id():
    tool_source = inspect.getsource(make_followup_tool)
    module = (APP / "langgraph_fhir_followup.py").read_text(encoding="utf-8")
    assert "CASE_PATIENT" not in module
    assert "patient_id_for_case" in tool_source
    assert PATIENT_ID not in tool_source
    assert PATIENT_CASE not in tool_source

    class _DistinctClient:
        def __init__(self) -> None:
            self.delegate = PreparedReadClient()
            self.calls = self.delegate.calls

        def get(self, path: str) -> dict:
            if path == f"Patient/{PATIENT_CASE}":
                raise AssertionError("case id was used as a Patient.id")
            return self.delegate.get(path)

    client = _DistinctClient()
    result = _workflow(
        client,
        ScriptedModel([_tool_call(), _final("unknown")]),
    ).run(PATIENT_CASE)
    assert result.status == "finish"
    assert result.patient["id"] == PATIENT_ID
    assert result.evidence[0]["resources"] == [f"Patient/{PATIENT_ID}", "Observation/obs-synthetic-001"]
    assert client.calls == CASE_READS


def test_fhir_failure_does_not_invent_clinical_context():
    client = FailingPreparedReadClient()
    sink = InMemoryAuditSink()
    model = ScriptedModel([_tool_call(), _final("unknown")])
    result = _workflow(client, model, sink).run(PATIENT_CASE)
    assert result.status == "unavailable"
    assert result.final_answer == UNAVAILABLE_ANSWER
    assert result.follow_up_required == "unknown"
    assert result.patient is None
    assert result.observations == []
    assert result.evidence == []
    assert result.tools_used == []
    assert result.context_patient == "unavailable"
    assert result.context_observation == "not_read"
    assert result.context_patient != "not_resolved"
    assert len(model.seen) == 0
    assert sink.events == []
    assert client.calls
    assert "Synthetic Patient" not in result.final_answer


def test_gemini_failure_is_not_turned_into_a_tool_call():
    client = MemoryReadClient()
    sink = InMemoryAuditSink()

    def unavailable(messages):
        raise RuntimeError("gemini follow-up request failed status=503")

    workflow = _workflow(client, unavailable, sink)
    with pytest.raises(RuntimeError, match="status=503"):
        workflow.run(PATIENT_CASE)
    assert client.calls == CASE_READS
    assert sink.events == []
    assert workflow._engine.model_calls == 1


def test_turn_limit_stops_without_another_model_call():
    replies = [_tool_call(call_id=f"call-{index}") for index in range(1, MAX_MODEL_TURNS + 1)]
    replies.append(AIMessage(content="this reply must not be requested"))
    model = ScriptedModel(replies)
    result = _workflow(MemoryReadClient(), model).run(PATIENT_CASE)
    assert result.status == "limit"
    assert result.final_answer == MODEL_LIMIT_ANSWER
    assert result.follow_up_required == "unknown"
    assert result.context_patient == "resolved"
    assert result.context_observation == "with_resources"
    assert result.schedule_check == "checked"
    assert result.evidence
    assert result.turns == MAX_MODEL_TURNS
    assert MAX_MODEL_TURNS == 4
    assert model.replies[0].content == "this reply must not be requested"
    assert BOUNDARY_EVENTS.count(f"execute:{FOLLOWUP_TOOL}") == MAX_MODEL_TURNS


def test_observation_failure_keeps_the_patient_already_read():
    result = _workflow(
        PreparedReadClient(fail_observation_read=True),
        ScriptedModel([_tool_call(), _final("false", "observations=[] follow-up is false")]),
    ).run(PATIENT_CASE)
    assert result.status == "unavailable"
    assert result.final_answer == UNAVAILABLE_ANSWER
    assert result.follow_up_required == "unknown"
    assert result.context_patient == "resolved"
    assert result.context_observation == "unavailable"
    assert result.schedule_check == "not_checked"
    assert result.observations == []
    assert result.evidence == []
    assert result.context_observation != "empty"


def test_model_text_does_not_change_read_state():
    prose = "patient=unavailable observation=empty schedule=NONE follow-up is false"
    checked = _workflow(
        PreparedReadClient(),
        ScriptedModel([_tool_call(), _final("false", prose)]),
    ).run(PATIENT_CASE)
    unread = _workflow(
        PreparedReadClient(),
        ScriptedModel([_final("true", "patient=resolved observation=with_resources")]),
    ).run(PATIENT_CASE)
    assert checked.status == "finish"
    assert checked.context_patient == "resolved"
    assert checked.context_observation == "with_resources"
    assert checked.schedule_check == "checked"
    assert checked.schedule_classifications == ("UPCOMING_CONFIRMED",)
    assert checked.follow_up_required == "false"
    assert unread.context_patient == "resolved"
    assert unread.context_observation == "with_resources"
    assert unread.schedule_check == "checked"
    assert unread.follow_up_required == "true"
    assert unread.evidence == []


def test_appointment_failure_keeps_context_already_read():
    class _AppointmentFailure:
        def get(self, path: str) -> dict:
            if path in {
                PROTOCOL_CASE_PATH,
                PATIENT_PATH,
                PROTOCOL_ENCOUNTER_PATH,
                PROTOCOL_OBSERVATION_PATH,
            }:
                return PreparedReadClient().get(path)
            raise ReadClientError("HTTP 503")

    result = _workflow(
        _AppointmentFailure(),
        ScriptedModel(
            [
                _tool_call(),
                _tool_call(APPOINTMENTS_TOOL, {"case_id": PATIENT_CASE}, "call-2"),
                _final("unknown"),
            ]
        ),
    ).run(PATIENT_CASE)
    assert result.status == "unavailable"
    assert result.context_patient == "resolved"
    assert result.context_observation == "with_resources"
    assert result.schedule_check == "unavailable"
    assert result.schedule_classifications == ()
    assert result.evidence == []


def test_the_same_workflow_accepts_a_different_fhir_client():
    first = _workflow(
        MemoryReadClient(),
        ScriptedModel([_tool_call(), _final("unknown")]),
    ).run(PATIENT_CASE)
    second = _workflow(
        MemoryReadClient(name="Alternate Synthetic", observation_id="obs-synthetic-002", value="Alternate value"),
        ScriptedModel([_tool_call(), _final("unknown")]),
    ).run(PATIENT_CASE)
    assert type(first) is type(second)
    assert first.observations[0]["id"] == "obs-synthetic-001"
    assert second.patient["name"] == "Alternate Synthetic"
    assert second.observations[0]["id"] == "obs-synthetic-002"
    assert second.observations[0]["valueString"] == "Alternate value"


def test_application_consumer_does_not_need_langgraph():
    consumer = inspect.getsource(_read_answer)
    assert "langgraph" not in consumer
    assert "AIMessage" not in consumer
    assert "ToolMessage" not in consumer
    result_source = inspect.getsource(FollowUpWorkflowResult)
    for token in ("AIMessage", "ToolMessage", "StateGraph", "ToolNode", "thought_signature"):
        assert token not in result_source
    module = inspect.getsource(FollowUpWorkflow)
    assert "StateGraph" not in module
    assert "add_node" not in module
    assert "httpx" not in module
    assert "HapiReadClient" not in module
    for name in ("followup_runtime", "followup_prompt", "gemini_provider", "llm_provider", "main.py"):
        assert name not in module
    assert "policy" in APPLICATION_RESPONSIBILITIES
    assert "audit" in APPLICATION_RESPONSIBILITIES
    assert "http" in APPLICATION_RESPONSIBILITIES
    assert "tool execution" in LANGGRAPH_RESPONSIBILITIES
    assert "policy" not in LANGGRAPH_RESPONSIBILITIES
    drawing = _workflow(MemoryReadClient(), ScriptedModel([]))._engine.graph.get_graph()
    assert {"prepare", "agent", "tools", "update_state", "denied", "finish"} <= set(drawing.nodes)
    for name in ("policy", "audit", "http", "fhir"):
        assert name not in set(drawing.nodes)
    for path in C15_MODULES:
        text = (APP / path).read_text(encoding="utf-8").lower()
        assert "langgraph" not in text
        assert "langchain" not in text


def _final(decision: str, text: str = FINAL_TEXT) -> AIMessage:
    message = AIMessage(content=text)
    message.additional_kwargs["follow_up_required"] = decision
    return message


def test_run_id_is_the_same_value_used_by_the_audit():
    sink = InMemoryAuditSink()
    workflow = FollowUpWorkflow(
        model=ScriptedModel([_tool_call(), _final("unknown")]),
        sink=sink,
        fhir_client=MemoryReadClient(),
        clock=_clock,
        run_id="run-c16-t-001",
    )
    result = workflow.run(PATIENT_CASE)
    assert result.run_id == "run-c16-t-001"
    assert workflow.run_id == "run-c16-t-001"
    assert workflow._engine.run_id == "run-c16-t-001"
    assert sink.events[0].run_id == result.run_id
    assert "uuid" not in inspect.getsource(FollowUpWorkflow.run)


def test_mapped_model_object_sets_follow_up_required():
    class _Part:
        function_call = None
        thought_signature = None

        def __init__(self, text: str) -> None:
            self.text = text

    class _Response:
        parsed = None

        def __init__(self, text: str) -> None:
            self.candidates = [type("Candidate", (), {"content": type("Content", (), {"parts": [_Part(text)]})()})()]

    message = followup_message_from_response(
        _Response('{"answer": "Context received from the model.", "follow_up_required": "true"}')
    )
    result = _workflow(
        MemoryReadClient(),
        ScriptedModel([_tool_call(), message]),
    ).run(PATIENT_CASE)
    assert result.status == "finish"
    assert result.follow_up_required == "true"
    assert result.final_answer == "Context received from the model."
    assert "follow_up_required" not in result.final_answer


def test_follow_up_required_accepts_an_explicit_structured_value():
    required = _workflow(
        MemoryReadClient(),
        ScriptedModel([_tool_call(), _final("true")]),
    ).run(PATIENT_CASE)
    skipped = _workflow(
        MemoryReadClient(),
        ScriptedModel([_tool_call(), _final("false", "No follow-up is needed.")]),
    ).run(PATIENT_CASE)
    assert required.follow_up_required == "true"
    assert required.observations[0]["id"] == "obs-synthetic-001"
    assert skipped.follow_up_required == "false"
    assert skipped.patient["name"] == "Synthetic Patient"


def test_follow_up_required_stays_unknown_without_a_structured_decision():
    prose = "The text says follow-up is true because an observation exists."
    model = ScriptedModel(
        [
            _tool_call(),
            AIMessage(content=prose),
            AIMessage(content="Still no structured decision."),
        ]
    )
    result = _workflow(MemoryReadClient(), model).run(PATIENT_CASE)
    assert result.follow_up_required == "unknown"
    assert result.final_answer == "Still no structured decision."
    assert result.follow_up_required != "true"
    assert isinstance(model.seen[-1][-1], HumanMessage)
    assert model.seen[-1][-1].content == FINAL_DECISION_REQUEST
    assert result.observations
    assert result.patient is not None


def test_explicit_decision_does_not_enter_the_policy_audit():
    sink = InMemoryAuditSink()
    result = _workflow(
        MemoryReadClient(),
        ScriptedModel([_signed_tool_call(), _final("true")]),
        sink,
    ).run(PATIENT_CASE)
    blob = _audit_blob(sink)
    assert result.follow_up_required == "true"
    assert result.run_id == "run-workflow-001"
    assert "follow_up_required" not in blob
    assert "true" not in blob
    assert "synthetic-thought-signature" not in blob
    assert FINAL_TEXT not in blob
    assert "Synthetic Patient" not in blob
    assert "prompt" not in blob


@pytest.mark.skipif(not _hapi_enabled(), reason="set RUN_HAPI_INTEGRATION_TESTS=true to call the local server")
def test_application_workflow_reads_real_hapi_with_a_fake_model():
    base = hapi_base_url()
    stored_patient, stored_observation = _ensure_records(base)
    clear_boundary_events()
    client = HapiReadClient(base)
    sink = InMemoryAuditSink()
    result = _workflow(client, ScriptedModel([_tool_call(), _final("unknown")]), sink).run(PATIENT_CASE)
    assert result.status == "finish"
    assert result.final_answer == FINAL_TEXT
    assert result.patient["id"] == stored_patient["id"] == PATIENT_ID
    assert result.patient["name"] == stored_patient["name"][0]["text"]
    found = next(item for item in result.observations if item.get("id") == stored_observation["id"])
    assert found["id"] == "obs-synthetic-001"
    assert found["valueString"] == stored_observation["valueString"]
    assert f"Observation/{stored_observation['id']}" in result.evidence[0]["resources"]
    assert result.tools_used == [FOLLOWUP_TOOL]
    assert client.calls == CASE_READS
    assert stored_patient["name"][0]["text"] not in _audit_blob(sink)


@pytest.mark.skipif(
    not (_live_gemini() and _hapi_enabled()),
    reason="set RUN_LIVE_GEMINI_TESTS=true and RUN_HAPI_INTEGRATION_TESTS=true",
)
def test_live_application_workflow_reads_hapi_before_the_final_answer():
    if not os.getenv("GEMINI_API_KEY", "").strip():
        pytest.skip("GEMINI_API_KEY is required for live Gemini tests")
    base = hapi_base_url()
    stored_patient, stored_observation = _ensure_records(base)
    clear_boundary_events()
    sink = InMemoryAuditSink()
    workflow = build_live_followup_workflow(sink, clock=_clock, run_id="run-live-workflow-001", base_url=base)
    result = workflow.run(PATIENT_CASE)
    assert result.status == "finish"
    assert result.final_answer
    assert result.turns >= 2
    assert result.turns <= MAX_MODEL_TURNS
    assert result.tools_used[0] == FOLLOWUP_TOOL
    assert set(result.tools_used) <= {FOLLOWUP_TOOL, APPOINTMENTS_TOOL}
    assert result.patient["id"] == stored_patient["id"]
    assert result.patient["name"] == stored_patient["name"][0]["text"]
    found = next(item for item in result.observations if item.get("id") == stored_observation["id"])
    assert found["valueString"] == stored_observation["valueString"]
    assert f"Observation/{stored_observation['id']}" in result.evidence[0]["resources"]
    secret = os.getenv("GEMINI_API_KEY", "").strip()
    blob = _audit_blob(sink)
    rendered = json.dumps(asdict(result), default=str)
    assert secret not in blob
    assert secret not in result.final_answer
    assert secret not in rendered
    assert "thought_signature" not in blob
    assert "thought_signature" not in rendered
    assert stored_observation.get("valueString", "missing-value") not in blob
    assert set(asdict(sink.events[0]).keys()) == set(SAFE_AUDIT_FIELDS)
    assert BOUNDARY_EVENTS.index(f"policy:{FOLLOWUP_TOOL}:allowed") < BOUNDARY_EVENTS.index(
        f"audit:{FOLLOWUP_TOOL}:allowed"
    )
    assert BOUNDARY_EVENTS.index(f"audit:{FOLLOWUP_TOOL}:allowed") < BOUNDARY_EVENTS.index(
        f"execute:{FOLLOWUP_TOOL}"
    )
    assert workflow.fhir_client.calls[: len(CASE_READS)] == CASE_READS
    assert all(
        path.startswith(("Patient", "Observation", "Appointment")) for path in workflow.fhir_client.calls
    )


def _store(base: str, path: str, body: dict) -> None:
    response = httpx.put(
        f"{base}/{path}",
        json=body,
        headers={"Accept": "application/fhir+json", "Content-Type": "application/fhir+json"},
        timeout=5.0,
    )
    if response.status_code not in {200, 201}:
        raise AssertionError(f"seed failed with HTTP {response.status_code}")


def _seed_patient() -> dict:
    return {
        "resourceType": "Patient",
        "id": PATIENT_ID,
        "active": True,
        "identifier": [{"system": CASE_IDENTIFIER_SYSTEM, "value": PATIENT_CASE}],
        "name": [{"text": "Synthetic Patient"}],
    }


def _has_case_identifier(patient: dict) -> bool:
    identifiers = patient.get("identifier")
    if not isinstance(identifiers, list):
        return False
    return any(
        isinstance(item, dict)
        and item.get("system") == CASE_IDENTIFIER_SYSTEM
        and item.get("value") == PATIENT_CASE
        for item in identifiers
    )


def _ensure_records(base: str) -> tuple[dict, dict]:
    reader = HapiReadClient(base)
    try:
        patient = reader.get(PATIENT_PATH)
    except Exception:
        patient = None
    try:
        observation = reader.get("Observation/obs-synthetic-001")
    except Exception:
        observation = None
    if patient is None or not _has_case_identifier(patient):
        _store(base, PATIENT_PATH, _seed_patient())
        patient = reader.get(PATIENT_PATH)
    if observation is None:
        _store(
            base,
            "Observation/obs-synthetic-001",
            {
                "resourceType": "Observation",
                "id": "obs-synthetic-001",
                "status": "final",
                "code": {"text": "Synthetic observation"},
                "subject": {"reference": f"Patient/{PATIENT_ID}"},
                "valueString": "Synthetic observation result",
            },
        )
        observation = reader.get("Observation/obs-synthetic-001")
    try:
        appointment = reader.get(f"Appointment/{APPOINTMENT_ID}")
    except Exception:
        appointment = None
    participants = appointment.get("participant") if isinstance(appointment, dict) else None
    expected = f"Patient/{PATIENT_ID}"
    linked = isinstance(participants, list) and any(
        isinstance(item, dict)
        and isinstance(item.get("actor"), dict)
        and item["actor"].get("reference") == expected
        for item in participants
    )
    if not linked:
        _store(base, f"Appointment/{APPOINTMENT_ID}", synthetic_followup_appointment())
    return patient, observation


OTHER_CASE = "SYN-FOLLOWUP-002"


def _message_with_tools(*calls: tuple[str, str]) -> AIMessage:
    return AIMessage(
        content="",
        tool_calls=[
            {
                "name": name,
                "args": {"case_id": case_id},
                "id": f"call-{index}",
                "type": "tool_call",
            }
            for index, (name, case_id) in enumerate(calls, start=1)
        ],
    )


def _assert_cross_case_denied(result: FollowUpWorkflowResult, client: PreparedReadClient, foreign_case: str) -> None:
    projected = _project(result)
    assert projected is not None
    body = dump_followup_endpoint_response(projected)
    assert body["caseId"] == result.case_id
    assert body["status"] == "denied"
    assert body["context"] == {"patient": "resolved", "observation": "with_resources"}
    assert body["schedule"]["check"] == "checked"
    assert body["clinicalAssessment"] == {"status": "not_performed"}
    assert body["humanReview"] == {"status": "not_proposed"}
    assert body["action"] == {"status": "not_proposed"}
    assert body["protocol"]["evaluationStatus"] == "not_matched"
    assert body["followUpRequired"] == "unknown"
    assert body["evidence"] == []
    assert result.final_answer == DENIAL_ANSWER
    assert client.calls
    assert f"execute:{FOLLOWUP_TOOL}" not in BOUNDARY_EVENTS
    assert f"execute:{APPOINTMENTS_TOOL}" not in BOUNDARY_EVENTS
    rendered = json.dumps(body)
    assert foreign_case not in rendered


def _prepared_other_case() -> PreparedReadClient:
    return PreparedReadClient(
        case_id=OTHER_CASE,
        patient_id="SYN-PATIENT-002",
        observation_id="obs-synthetic-002",
    )


def test_policy_denies_a_clinical_read_proposed_for_another_case():
    decision = evaluate_tool_policy(
        FOLLOWUP_TOOL,
        authorized_case_id=OTHER_CASE,
        proposed_case_id=PATIENT_CASE,
    )
    assert decision.status == "denied"
    assert decision.reason == CASE_ID_MISMATCH_REASON
    assert PATIENT_CASE not in decision.reason
    assert evaluate_tool_policy(FOLLOWUP_TOOL).status == "allowed"


def test_cross_case_context_tool_is_denied_before_fhir(caplog):
    client = _prepared_other_case()
    sink = InMemoryAuditSink()
    with caplog.at_level(logging.INFO, logger="ai-service"):
        result = _workflow(
            client,
            ScriptedModel([_tool_call(FOLLOWUP_TOOL, {"case_id": PATIENT_CASE})]),
            sink,
        ).run(OTHER_CASE)
    _assert_cross_case_denied(result, client, PATIENT_CASE)
    assert len(sink.events) == 1
    assert sink.events[0].case_id == OTHER_CASE
    assert sink.events[0].tool_name == FOLLOWUP_TOOL
    assert sink.events[0].decision == "denied"
    assert sink.events[0].reason == CASE_ID_MISMATCH_REASON
    lines = _policy_audit_lines(caplog)
    assert len(lines) == 1
    _assert_policy_audit_line(
        lines[0],
        run_id=result.run_id,
        case_id=OTHER_CASE,
        tool_name=FOLLOWUP_TOOL,
        decision="denied",
        reason=CASE_ID_MISMATCH_REASON,
    )
    assert PATIENT_CASE not in lines[0]
    assert PATIENT_CASE not in _audit_blob(sink)


def test_cross_case_appointment_tool_is_denied_before_fhir():
    client = _prepared_other_case()
    sink = InMemoryAuditSink()
    result = _workflow(
        client,
        ScriptedModel([_tool_call(APPOINTMENTS_TOOL, {"case_id": PATIENT_CASE})]),
        sink,
    ).run(OTHER_CASE)
    _assert_cross_case_denied(result, client, PATIENT_CASE)
    assert sink.events[0].tool_name == APPOINTMENTS_TOOL
    assert sink.events[0].case_id == OTHER_CASE
    assert sink.events[0].reason == CASE_ID_MISMATCH_REASON
    assert APPOINTMENT_ID not in _audit_blob(sink)


def test_mixed_message_denies_same_case_context_and_foreign_appointments_before_fhir():
    client = PreparedReadClient()
    sink = InMemoryAuditSink()
    result = _workflow(
        client,
        ScriptedModel(
            [_message_with_tools((FOLLOWUP_TOOL, PATIENT_CASE), (APPOINTMENTS_TOOL, OTHER_CASE))]
        ),
        sink,
    ).run(PATIENT_CASE)
    _assert_cross_case_denied(result, client, OTHER_CASE)
    assert [event.tool_name for event in sink.events] == [FOLLOWUP_TOOL, APPOINTMENTS_TOOL]
    assert [event.decision for event in sink.events] == ["allowed", "denied"]
    assert sink.events[1].reason == CASE_ID_MISMATCH_REASON
    assert all(event.case_id == PATIENT_CASE for event in sink.events)
    assert OTHER_CASE not in _audit_blob(sink)


def test_mixed_message_denies_foreign_context_and_same_case_appointments_before_fhir():
    client = PreparedReadClient()
    sink = InMemoryAuditSink()
    result = _workflow(
        client,
        ScriptedModel(
            [_message_with_tools((FOLLOWUP_TOOL, OTHER_CASE), (APPOINTMENTS_TOOL, PATIENT_CASE))]
        ),
        sink,
    ).run(PATIENT_CASE)
    _assert_cross_case_denied(result, client, OTHER_CASE)
    assert len(sink.events) == 1
    assert sink.events[0].tool_name == FOLLOWUP_TOOL
    assert sink.events[0].decision == "denied"
    assert sink.events[0].reason == CASE_ID_MISMATCH_REASON
    assert sink.events[0].case_id == PATIENT_CASE
    assert OTHER_CASE not in _audit_blob(sink)


def test_same_case_context_read_still_completes():
    client = PreparedReadClient()
    result = _workflow(client, ScriptedModel([_tool_call(), _final("unknown")])).run(PATIENT_CASE)
    assert result.status == "finish"
    assert result.case_id == PATIENT_CASE
    assert result.context_patient == "resolved"
    assert result.context_observation == "with_resources"
    assert result.patient["id"] == PATIENT_ID
    assert result.evidence == [
        {"tool": FOLLOWUP_TOOL, "resources": [f"Patient/{PATIENT_ID}", "Observation/obs-synthetic-001"]}
    ]
    assert client.calls == CASE_READS


def test_same_case_context_and_appointment_read_still_completes():
    client = PreparedReadClient()
    result = _workflow(
        client,
        ScriptedModel(
            [
                _message_with_tools((FOLLOWUP_TOOL, PATIENT_CASE), (APPOINTMENTS_TOOL, PATIENT_CASE)),
                _final("false"),
            ]
        ),
        now=lambda: datetime(2026, 9, 28, tzinfo=timezone.utc),
    ).run(PATIENT_CASE)
    assert result.status == "finish"
    assert result.case_id == PATIENT_CASE
    assert result.context_patient == "resolved"
    assert result.context_observation == "with_resources"
    assert result.schedule_check == "checked"
    assert result.schedule_classifications == ("UPCOMING_CONFIRMED",)
    by_tool = {item["tool"]: item["resources"] for item in result.evidence}
    assert by_tool[FOLLOWUP_TOOL] == [f"Patient/{PATIENT_ID}", "Observation/obs-synthetic-001"]
    assert by_tool[APPOINTMENTS_TOOL] == [f"Appointment/{APPOINTMENT_ID}"]
    assert PROTOCOL_CASE_PATH in client.calls
    assert PROTOCOL_APPOINTMENT_PATH in client.calls


def test_same_case_observation_failure_preserves_patient():
    client = PreparedReadClient(fail_observation_read=True)
    result = _workflow(client, ScriptedModel([_tool_call(), _final("false")])).run(PATIENT_CASE)
    assert result.status == "unavailable"
    assert result.case_id == PATIENT_CASE
    assert result.context_patient == "resolved"
    assert result.context_observation == "unavailable"
    assert result.observations == []
    assert result.evidence == []
    assert result.schedule_check == "not_checked"


def test_second_run_on_the_same_workflow_does_not_keep_the_first_case():
    client = PreparedReadClient()
    workflow = _workflow(
        client,
        ScriptedModel(
            [
                _tool_call(),
                _tool_call(APPOINTMENTS_TOOL, {"case_id": PATIENT_CASE}, "call-2"),
                _final("false"),
            ]
        ),
    )
    first = workflow.run(PATIENT_CASE)
    assert first.context_patient == "resolved"
    assert first.schedule_check == "checked"
    assert first.evidence
    workflow._engine.model = ScriptedModel(
        [_tool_call(FOLLOWUP_TOOL, {"case_id": OTHER_CASE}), _final("unknown")]
    )
    second = workflow.run(OTHER_CASE)
    assert second.case_id == OTHER_CASE
    assert second.status == "unavailable"
    assert second.context_patient == "not_resolved"
    assert second.context_observation == "not_read"
    assert second.schedule_check == "not_checked"
    assert second.schedule_classifications == ()
    assert second.schedule_appointments == ()
    assert second.evidence == []
    assert second.patient is None
    assert second.observations == []
    blob = json.dumps(asdict(second), default=str)
    assert PATIENT_ID not in blob
    assert "obs-synthetic-001" not in blob
    assert APPOINTMENT_ID not in blob
    assert "UPCOMING_CONFIRMED" not in blob
    assert f"{case_search_path(OTHER_CASE)}&_count=2" in client.calls


def test_concurrent_allowed_and_denied_runs_keep_policy_decisions_isolated():
    read_started = threading.Event()
    release_read = threading.Event()

    class BlockingReadClient:
        def __init__(self) -> None:
            self.delegates = {
                PATIENT_CASE: PreparedReadClient(),
                OTHER_CASE: _prepared_other_case(),
            }
            self.calls: list[str] = []

        def get(self, path: str) -> dict:
            self.calls.append(path)
            if path == PROTOCOL_CASE_PATH:
                read_started.set()
                if not release_read.wait(timeout=5):
                    raise RuntimeError("timed out waiting to release the allowed read")
            if OTHER_CASE in path or "SYN-PATIENT-002" in path:
                return self.delegates[OTHER_CASE].get(path)
            return self.delegates[PATIENT_CASE].get(path)

    def model(messages):
        if any(isinstance(message, ToolMessage) for message in messages):
            return _final("unknown")
        request_text = str(messages[0].content)
        requested_case = OTHER_CASE if OTHER_CASE in request_text else PATIENT_CASE
        return _tool_call(
            FOLLOWUP_TOOL,
            {"case_id": PATIENT_CASE},
            f"call-{requested_case}",
        )

    client = BlockingReadClient()
    sink = InMemoryAuditSink()
    workflow = _workflow(client, model, sink)
    results: dict[str, FollowUpWorkflowResult] = {}
    errors: dict[str, Exception] = {}

    def run(label: str, case_id: str) -> None:
        try:
            results[label] = workflow.run(case_id)
        except Exception as exc:  # pragma: no cover - asserted below
            errors[label] = exc

    allowed = threading.Thread(target=run, args=("allowed", PATIENT_CASE))
    denied = threading.Thread(target=run, args=("denied", OTHER_CASE))
    allowed.start()
    try:
        assert read_started.wait(timeout=5)
        denied.start()
        denied.join(timeout=5)
        assert not denied.is_alive()
    finally:
        release_read.set()
        allowed.join(timeout=5)
        if denied.ident is not None:
            denied.join(timeout=5)

    assert not allowed.is_alive()
    assert errors == {}
    assert results["allowed"].status == "finish"
    assert results["allowed"].case_id == PATIENT_CASE
    assert results["allowed"].patient["id"] == PATIENT_ID
    assert results["allowed"].context_patient == "resolved"
    assert results["allowed"].context_observation == "with_resources"
    assert results["allowed"].schedule_check == "checked"
    assert results["allowed"].evidence == [
        {"tool": FOLLOWUP_TOOL, "resources": [f"Patient/{PATIENT_ID}", "Observation/obs-synthetic-001"]}
    ]
    assert results["denied"].status == "denied"
    assert results["denied"].case_id == OTHER_CASE
    assert results["denied"].patient is None
    assert results["denied"].observations == []
    assert results["denied"].context_patient == "resolved"
    assert results["denied"].context_observation == "with_resources"
    assert results["denied"].schedule_check == "checked"
    assert results["denied"].evidence == []
    assert len(client.calls) == 10
    assert sorted((event.case_id, event.decision) for event in sink.events) == [
        (PATIENT_CASE, "allowed"),
        (OTHER_CASE, "denied"),
    ]
    denied_event = next(event for event in sink.events if event.decision == "denied")
    assert denied_event.reason == CASE_ID_MISMATCH_REASON


def test_two_allowed_concurrent_runs_keep_clinical_state_isolated():
    fixtures = {
        PATIENT_CASE: {
            "patient": PATIENT_ID,
            "observation": "obs-synthetic-001",
            "appointment": APPOINTMENT_ID,
            "appointment_status": "booked",
            "classification": "UPCOMING_CONFIRMED",
        },
        OTHER_CASE: {
            "patient": "SYN-PATIENT-002",
            "observation": "obs-synthetic-002",
            "appointment": "appointment-synthetic-002",
            "appointment_status": "cancelled",
            "classification": "CANCELLED",
        },
    }
    first_searches = threading.Barrier(2)

    class ConcurrentReadClient:
        def __init__(self) -> None:
            self.calls: list[str] = []
            self._lock = threading.Lock()
            self._cases_started: set[str] = set()

        def get(self, path: str) -> dict:
            with self._lock:
                self.calls.append(path)
            for case_id, fixture in fixtures.items():
                patient_id = str(fixture["patient"])
                if path == f"{case_search_path(case_id)}&_count=2":
                    with self._lock:
                        first = case_id not in self._cases_started
                        self._cases_started.add(case_id)
                    if first:
                        first_searches.wait(timeout=5)
                    return {
                        "resourceType": "Bundle",
                        "type": "searchset",
                        "entry": [
                            {
                                "resource": {
                                    "resourceType": "Patient",
                                    "id": patient_id,
                                    "identifier": [
                                        {"system": CASE_IDENTIFIER_SYSTEM, "value": case_id}
                                    ],
                                }
                            }
                        ],
                    }
                if path == f"Patient/{patient_id}":
                    return {"resourceType": "Patient", "id": patient_id}
                if path == f"Encounter?patient=Patient/{patient_id}&status=finished&_count=25":
                    return {
                        "resourceType": "Bundle",
                        "type": "searchset",
                        "entry": [
                            {
                                "resource": {
                                    "resourceType": "Encounter",
                                    "id": f"encounter-{patient_id}",
                                    "status": "finished",
                                    "subject": {"reference": f"Patient/{patient_id}"},
                                    "period": {"end": "2026-09-28T12:00:00Z"},
                                }
                            }
                        ],
                    }
                if path == f"Observation?subject=Patient/{patient_id}&status=final&_count=25":
                    return {
                        "resourceType": "Bundle",
                        "type": "searchset",
                        "entry": [
                            {
                                "resource": {
                                    "resourceType": "Observation",
                                    "id": fixture["observation"],
                                    "status": "final",
                                    "subject": {"reference": f"Patient/{patient_id}"},
                                    "encounter": {"reference": f"Encounter/encounter-{patient_id}"},
                                    "issued": "2026-09-28T12:00:01Z",
                                }
                            }
                        ],
                    }
                if path == f"Appointment?patient=Patient/{patient_id}&_count=25":
                    return {
                        "resourceType": "Bundle",
                        "type": "searchset",
                        "entry": [
                            {
                                "resource": {
                                    "resourceType": "Appointment",
                                    "id": fixture["appointment"],
                                    "status": fixture["appointment_status"],
                                    "start": "2027-03-15T15:00:00Z",
                                    "participant": [
                                        {
                                            "actor": {"reference": f"Patient/{patient_id}"},
                                            "status": "accepted",
                                        }
                                    ],
                                }
                            }
                        ],
                    }
            raise ReadClientError("unknown concurrent path")

    def model(messages):
        request_text = str(messages[0].content)
        case_id = OTHER_CASE if OTHER_CASE in request_text else PATIENT_CASE
        tool_results = sum(isinstance(message, ToolMessage) for message in messages)
        if tool_results == 0:
            return _tool_call(FOLLOWUP_TOOL, {"case_id": case_id}, f"context-{case_id}")
        if tool_results == 1:
            return _tool_call(APPOINTMENTS_TOOL, {"case_id": case_id}, f"schedule-{case_id}")
        return _final("unknown", f"Completed {case_id}")

    client = ConcurrentReadClient()
    workflow = _workflow(
        client,
        model,
        now=lambda: datetime(2026, 9, 28, tzinfo=timezone.utc),
    )
    results: dict[str, FollowUpWorkflowResult] = {}
    errors: dict[str, Exception] = {}

    def run(case_id: str) -> None:
        try:
            results[case_id] = workflow.run(case_id)
        except Exception as exc:  # pragma: no cover - asserted below
            errors[case_id] = exc

    threads = [threading.Thread(target=run, args=(case_id,)) for case_id in fixtures]
    for thread in threads:
        thread.start()
    for thread in threads:
        thread.join(timeout=5)

    assert all(not thread.is_alive() for thread in threads)
    assert errors == {}
    for case_id, fixture in fixtures.items():
        result = results[case_id]
        patient_id = str(fixture["patient"])
        observation_id = str(fixture["observation"])
        appointment_id = str(fixture["appointment"])
        assert result.status == "finish"
        assert result.case_id == case_id
        assert result.patient["id"] == patient_id
        assert [item["id"] for item in result.observations] == [observation_id]
        assert result.context_patient == "resolved"
        assert result.context_observation == "with_resources"
        assert result.schedule_check == "checked"
        assert result.schedule_classifications == (fixture["classification"],)
        assert result.schedule_appointments == (
            (f"Appointment/{appointment_id}", fixture["classification"]),
        )
        evidence = json.dumps(result.evidence)
        assert patient_id in evidence
        assert observation_id in evidence
        assert appointment_id in evidence
        for other_case, other in fixtures.items():
            if other_case == case_id:
                continue
            assert str(other["patient"]) not in evidence
            assert str(other["observation"]) not in evidence
            assert str(other["appointment"]) not in evidence


def test_follow_up_required_and_answer_do_not_change_case_identity():
    prose = f"case_id={OTHER_CASE} patient=SYN-PATIENT-999 follow-up is true"
    result = _workflow(
        PreparedReadClient(),
        ScriptedModel([_tool_call(), _final("true", prose)]),
    ).run(PATIENT_CASE)
    assert result.case_id == PATIENT_CASE
    assert result.follow_up_required == "true"
    assert result.final_answer == prose
    assert result.patient["id"] == PATIENT_ID
    assert result.context_patient == "resolved"
    rendered = json.dumps(result.evidence)
    assert OTHER_CASE not in rendered
    assert "SYN-PATIENT-999" not in rendered


def test_execution_binding_does_not_query_a_foreign_case():
    client = PreparedReadClient()
    adapter = FollowUpFHIRAdapter(ClientFHIRTransport(client))
    with adapter.bind_read(OTHER_CASE):
        with pytest.raises(ReadClientError, match="not authorized"):
            adapter.patient_id_for_case(PATIENT_CASE)
    assert client.calls == []
    with adapter.bind_read(PATIENT_CASE):
        assert adapter.patient_id_for_case(PATIENT_CASE) == PATIENT_ID
    assert client.calls == [case_search_path(PATIENT_CASE)]


def test_case_isolation_regression_does_not_attach_another_case_read(caplog):
    """Case isolation regression.

    A workflow started for case X must not return Patient, Observation, or
    Appointment data from a clinical read proposed for case Y. Y is not read.
    Before this hotfix the model case id was the FHIR query, so this failed.
    """
    client = _prepared_other_case()
    sink = InMemoryAuditSink()
    with caplog.at_level(logging.INFO, logger="ai-service"):
        result = _workflow(
            client,
            ScriptedModel(
                [
                    _tool_call(FOLLOWUP_TOOL, {"case_id": PATIENT_CASE}),
                    _final("true", "Patient context received."),
                ]
            ),
            sink,
        ).run(OTHER_CASE)
    _assert_cross_case_denied(result, client, PATIENT_CASE)
    assert result.case_id == OTHER_CASE
    assert len(sink.events) == 1
    assert sink.events[0].reason == CASE_ID_MISMATCH_REASON
    assert PATIENT_CASE not in _policy_audit_lines(caplog)[0]
    assert "Patient" not in _policy_audit_lines(caplog)[0]
    assert "Observation" not in _policy_audit_lines(caplog)[0]
    assert "Appointment" not in _policy_audit_lines(caplog)[0]
