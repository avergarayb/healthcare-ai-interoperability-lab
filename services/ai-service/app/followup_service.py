"""HTTP adapter for follow-up. Auth, flag, validation, then FollowUpWorkflow.run."""

from __future__ import annotations

import json
import logging
import uuid
from dataclasses import replace
from datetime import datetime, timezone
from typing import Any, Callable

from fastapi import Request
from fastapi.exceptions import RequestValidationError
from fastapi.responses import JSONResponse, Response
from pydantic import ValidationError

from app.config import Settings
from app.followup_models import (
    CASE_IDS,
    ActionState,
    ActionStatus,
    ClinicalAssessment,
    ClinicalAssessmentStatus,
    ContextState,
    Evidence,
    FollowUpEndpointResponse,
    FollowUpEndpointStatus,
    FollowUpRequest,
    FollowUpRequired,
    HumanReview,
    HumanReviewStatus,
    ProtocolState,
    ReviewCaseLink,
    ScheduleAppointment,
    ScheduleState,
    dump_followup_endpoint_response,
)
from app.followup_review import (
    FollowUpReviewCaseService,
    InvalidReviewTrigger,
    ReviewCaseStatus,
    ReviewPersistenceUnavailable,
    validate_review_case_id,
)
from app.langgraph_fhir_client import InMemoryAuditSink, default_clock
from app.langgraph_followup_workflow import (
    FollowUpWorkflow,
    FollowUpWorkflowResult,
    build_live_followup_workflow,
)
from app.security_audit import (
    SecurityAuditRejected,
    SecurityAuditStoreInitializationError,
    SecurityAuditUnavailable,
    audit_correlation_id,
    workflow_security_event,
)
from app.security_audit_sqlite import resolve_security_audit_repository
from app.service_auth import authenticate

log = logging.getLogger("ai-service")

DISABLED_DETAIL = "Follow-up agent is disabled"
WORKFLOW_FAILED_DETAIL = "Follow-up workflow failed"
REVIEW_PERSISTENCE_UNAVAILABLE_DETAIL = "Follow-up review persistence unavailable"
SECURITY_AUDIT_UNAVAILABLE_DETAIL = "Security audit persistence unavailable"


class WorkflowAuditUnavailable(RuntimeError):
    """The access decision could not be durably recorded."""

_HTTP_STATUS = {
    "finish": FollowUpEndpointStatus.COMPLETED,
    "denied": FollowUpEndpointStatus.DENIED,
    "unavailable": FollowUpEndpointStatus.UNAVAILABLE,
    "limit": FollowUpEndpointStatus.LIMIT,
}


def build_followup_workflow(run_id: str) -> FollowUpWorkflow:
    """Compose the live workflow. The caller owns run_id."""
    return build_live_followup_workflow(
        InMemoryAuditSink(),
        clock=default_clock,
        run_id=run_id,
    )


def run_followup_http(
    request: Request,
    settings: Settings,
    raw_body: bytes,
    *,
    build_workflow: Callable[[str], FollowUpWorkflow] | None = None,
) -> Response:
    correlation_id = request.headers.get("X-Correlation-ID") or "missing"
    if not authenticate(request, settings):
        _log(correlation_id, "UNAUTHORIZED")
        return Response(status_code=401)

    if not settings.followup_agent_enabled:
        _log(correlation_id, "DISABLED")
        return JSONResponse(status_code=503, content={"detail": DISABLED_DETAIL})

    try:
        parsed = FollowUpRequest.model_validate(_load_body(raw_body))
    except ValidationError as exc:
        raise RequestValidationError(exc.errors()) from exc

    run_id = str(uuid.uuid4())
    factory = build_workflow or build_followup_workflow
    workflow = factory(run_id)
    review_service: FollowUpReviewCaseService | None = None

    def ensure_review_case(case_id, protocol):
        nonlocal review_service
        if protocol.evaluation_status.value != "matched":
            return None
        if review_service is None:
            repository = getattr(request.app.state, "followup_review_repository", None)
            if repository is None:
                raise ReviewPersistenceUnavailable
            review_service = FollowUpReviewCaseService(repository)
        return review_service.ensure_for_protocol(case_id, protocol)

    if isinstance(workflow, FollowUpWorkflow):
        workflow.ensure_review_case = ensure_review_case
    try:
        result = workflow.run(parsed.case_id)
        if result.protocol.evaluation_status.value == "matched" and result.review_case is None:
            result = _with_review_case(
                result,
                ensure_review_case(result.case_id, result.protocol),
            )
        if (
            review_service is not None
            and result.review_case is not None
            and result.status == "finish"
            and result.final_answer.strip()
        ):
            result = replace(
                result,
                review_case=review_service.record_narrative(
                    result.review_case.id,
                    result.final_answer,
                ),
            )
    except (ReviewPersistenceUnavailable, InvalidReviewTrigger):
        _log(correlation_id, "persistence_unavailable")
        return JSONResponse(
            status_code=503,
            content={"detail": REVIEW_PERSISTENCE_UNAVAILABLE_DETAIL},
        )
    except Exception:
        _log(correlation_id, "error")
        return JSONResponse(status_code=502, content={"detail": WORKFLOW_FAILED_DETAIL})

    payload = _project(result)
    if payload is None:
        _log(correlation_id, "error")
        return JSONResponse(status_code=502, content={"detail": WORKFLOW_FAILED_DETAIL})
    payload = _with_longitudinal_context(payload, getattr(workflow, "fhir_client", None), parsed.case_id)
    _log(correlation_id, payload.status.value)
    return JSONResponse(status_code=200, content=dump_followup_endpoint_response(payload))


def _with_longitudinal_context(payload, client, case_id: str):
    if client is None or client.__class__.__name__ != "ClinicalReadClient":
        return payload
    try:
        from app.clinical_context_intelligence import ProtocolVerdict, analyze_clinical_context
        from app.longitudinal_context import build_longitudinal_context

        context = build_longitudinal_context(client, case_id)
        analysis = analyze_clinical_context(
            context,
            protocol=ProtocolVerdict(
                protocol_id=payload.protocol.id,
                evaluation_status=payload.protocol.evaluation_status.value,
                reason_codes=list(payload.protocol.reason_codes),
                primary_evidence=list(payload.protocol.matched_resources),
            ),
            evaluated_at=datetime.now(timezone.utc),
        )
    except Exception:
        return payload
    return payload.model_copy(
        update={
            "longitudinal_context": context.model_dump(by_alias=True, mode="json", exclude_none=True),
            "clinical_context_intelligence": analysis.model_dump(by_alias=True, mode="json", exclude_none=True),
        }
    )


def _project(result: FollowUpWorkflowResult) -> FollowUpEndpointResponse | None:
    status = _HTTP_STATUS.get(result.status)
    allowed = {item.value for item in FollowUpRequired}
    if status is None or result.run_id == "" or result.follow_up_required not in allowed:
        return None
    try:
        return FollowUpEndpointResponse(
            runId=result.run_id,
            caseId=result.case_id,
            status=status,
            context=ContextState(patient=result.context_patient, observation=result.context_observation),
            schedule=_schedule(result),
            clinicalAssessment=ClinicalAssessment(status=ClinicalAssessmentStatus.NOT_PERFORMED),
            humanReview=HumanReview(
                status=HumanReviewStatus(result.protocol.human_review_status),
                reason=result.protocol.human_review_reason,
            ),
            action=ActionState(
                status=ActionStatus(result.protocol.action_status),
                type=result.protocol.action_type,
            ),
            protocol=ProtocolState(
                id=result.protocol.id,
                evaluationStatus=result.protocol.evaluation_status.value,
                reasonCodes=list(result.protocol.reason_codes),
                matchedResources=list(result.protocol.matched_resources),
            ),
            reviewCase=(
                ReviewCaseLink(
                    reviewCaseId=result.review_case.id,
                    status=result.review_case.status.value,
                    version=result.review_case.version,
                )
                if result.review_case is not None
                else None
            ),
            followUpRequired=FollowUpRequired(result.follow_up_required),
            answer=result.final_answer,
            evidence=_evidence(result.evidence),
        )
    except ValidationError:
        return None


def _with_review_case(result: FollowUpWorkflowResult, review_case) -> FollowUpWorkflowResult:
    return replace(result, review_case=review_case)


def _schedule(result: FollowUpWorkflowResult) -> ScheduleState:
    if result.schedule_check != "checked":
        return ScheduleState(check=result.schedule_check)
    appointments = [
        ScheduleAppointment(id=appointment_id, classification=classification)
        for appointment_id, classification in result.schedule_appointments
    ]
    return ScheduleState(
        check="checked",
        classifications=list(result.schedule_classifications),
        appointments=appointments or None,
    )


def _evidence(evidence: list[dict[str, Any]]) -> list[Evidence]:
    items: list[Evidence] = []
    for entry in evidence:
        tool = entry.get("tool")
        resources = entry.get("resources")
        if not isinstance(tool, str) or not isinstance(resources, list):
            continue
        for reference in resources:
            if isinstance(reference, str) and reference:
                items.append(Evidence(tool=tool, id=reference))
    return items


def _load_body(raw: bytes) -> Any:
    if raw is None or raw.strip() == b"":
        return None
    try:
        return json.loads(raw.decode("utf-8"))
    except (UnicodeDecodeError, json.JSONDecodeError):
        return None


def _log(correlation_id: str, status: str) -> None:
    line = (
        f"follow_up correlationId={correlation_id} method=POST "
        f"path=/internal/agent/follow-up status={status}"
    )
    lowered = line.lower()
    if "x-service-token=" in lowered or "gemini_api_key=" in lowered:
        raise RuntimeError("follow-up log line must not contain secrets")
    log.info(line)


def run_agent_workflow_http(request: Request, settings: Settings, raw_body: bytes) -> Response:
    """Start one orchestrated workflow. Existing follow-up routes stay unchanged."""
    denied, correlation_id = _workflow_operation_guard(request, settings, "workflow_start")
    if denied is not None:
        return denied
    body = _load_body(raw_body)
    case_id = body.get("caseId") if isinstance(body, dict) else None
    workflow_type = body.get("workflowType") if isinstance(body, dict) else None
    allowed_types = {"post_consultation", "missed_follow_up"}
    if isinstance(workflow_type, str) and workflow_type not in allowed_types:
        return _workflow_denied_response(
            request,
            settings,
            event_type="workflow_start",
            reason_code="workflow_type_not_allowed",
            correlation_id=correlation_id,
            response=JSONResponse(status_code=422, content={"error": "invalid_request"}),
        )
    if case_id not in CASE_IDS or workflow_type not in allowed_types:
        return JSONResponse(status_code=422, content={"error": "invalid_request"})
    repository = getattr(request.app.state, "followup_review_repository", None)
    if repository is None:
        return JSONResponse(status_code=503, content={"detail": REVIEW_PERSISTENCE_UNAVAILABLE_DETAIL})
    from app.langgraph_workflow_orchestration import (
        build_live_ports,
        saver_for,
        start_workflow,
        workflow_db_path,
        workflow_id_for,
    )

    workflow_id = workflow_id_for(case_id, workflow_type)
    if not _append_workflow_audit(
        request,
        settings,
        event_type="workflow_start",
        outcome="allowed",
        reason_code="access_granted",
        correlation_id=correlation_id,
        authenticated=True,
        workflow_id=workflow_id,
        workflow_type=workflow_type,
    ):
        return _audit_unavailable_response()
    ports = getattr(request.app.state, "agent_workflow_ports", None) or build_live_ports(settings, repository)
    saver = getattr(request.app.state, "agent_workflow_saver", None) or saver_for(workflow_db_path(settings))
    view = start_workflow(saver, ports, case_id, workflow_type)
    return JSONResponse(status_code=200, content=view)


def get_agent_workflow_http(request: Request, settings: Settings, workflow_id: str) -> Response:
    return _workflow_read(request, settings, workflow_id, None)


def get_agent_workflow_steps_http(request: Request, settings: Settings, workflow_id: str) -> Response:
    return _workflow_read(
        request,
        settings,
        workflow_id,
        ("workflowId", "status", "currentStep", "steps"),
    )


def get_agent_workflow_evidence_http(request: Request, settings: Settings, workflow_id: str) -> Response:
    return _workflow_read(
        request,
        settings,
        workflow_id,
        ("workflowId", "protocol", "evidence", "clinicalContext", "clinicalContextIntelligence"),
    )


def get_agent_workflow_errors_http(request: Request, settings: Settings, workflow_id: str) -> Response:
    return _workflow_read(
        request,
        settings,
        workflow_id,
        ("workflowId", "status", "currentStep", "errorCode"),
    )


def resume_agent_workflow_http(
    request: Request,
    settings: Settings,
    workflow_id: str,
    raw_body: bytes,
) -> Response:
    """Resume only after Human Review has stored the same decision for the same case."""
    denied, correlation_id = _workflow_operation_guard(request, settings, "workflow_resume")
    if denied is not None:
        return denied
    canonical_id = _canonical_workflow_id(workflow_id)
    if canonical_id is None:
        return JSONResponse(status_code=422, content={"error": "invalid_request"})
    body = _load_body(raw_body)
    review_case_id = body.get("reviewCaseId") if isinstance(body, dict) else None
    decision = body.get("decision") if isinstance(body, dict) else None
    if not isinstance(review_case_id, str) or not isinstance(decision, str):
        return JSONResponse(status_code=422, content={"error": "invalid_request"})
    try:
        review_case_id = validate_review_case_id(review_case_id)
    except ValueError:
        return JSONResponse(status_code=422, content={"error": "invalid_request"})
    repository = getattr(request.app.state, "followup_review_repository", None)
    if repository is None:
        return JSONResponse(status_code=503, content={"detail": REVIEW_PERSISTENCE_UNAVAILABLE_DETAIL})
    try:
        case = repository.get(review_case_id)
    except ReviewPersistenceUnavailable:
        return JSONResponse(status_code=503, content={"detail": REVIEW_PERSISTENCE_UNAVAILABLE_DETAIL})
    from app.langgraph_workflow_orchestration import (
        WorkflowDecisionRejected,
        WorkflowNotFound,
        WorkflowNotSuspended,
        build_live_ports,
        resume_workflow,
        saver_for,
        workflow_db_path,
    )

    path = workflow_db_path(settings)
    saver = getattr(request.app.state, "agent_workflow_saver", None)
    if saver is None and path.exists():
        saver = saver_for(path)
    indexed = None if saver is None else saver.index_get(canonical_id)
    if indexed is None:
        return JSONResponse(status_code=404, content={"error": "workflow_not_found"})
    ports = getattr(request.app.state, "agent_workflow_ports", None) or build_live_ports(settings, repository)
    closed = case is not None and case.status is ReviewCaseStatus.CLOSED and case.outcome is not None
    stored = None if case is None or case.outcome is None else case.outcome.value
    indexed_type = indexed.get("workflowType")
    known_workflow_types = {"post_consultation", "missed_follow_up", "cross_org_lab_result"}
    workflow_type = indexed_type if indexed_type in known_workflow_types else None

    def audit_allowed_resume() -> None:
        if not _append_workflow_audit(
            request,
            settings,
            event_type="workflow_resume",
            outcome="allowed",
            reason_code="access_granted",
            correlation_id=correlation_id,
            authenticated=True,
            workflow_id=canonical_id,
            workflow_type=workflow_type,
        ):
            raise WorkflowAuditUnavailable

    try:
        view = resume_workflow(
            saver,
            ports,
            canonical_id,
            decision,
            review_case_id=review_case_id,
            stored_outcome=stored,
            case_is_closed=closed,
            before_resume=audit_allowed_resume,
        )
    except WorkflowAuditUnavailable:
        return _audit_unavailable_response()
    except WorkflowNotFound:
        return JSONResponse(status_code=404, content={"error": "workflow_not_found"})
    except WorkflowNotSuspended:
        return JSONResponse(status_code=409, content={"error": "workflow_not_suspended"})
    except WorkflowDecisionRejected:
        return _workflow_denied_response(
            request,
            settings,
            event_type="workflow_resume",
            reason_code="human_review_decision_rejected",
            correlation_id=correlation_id,
            workflow_id=canonical_id,
            workflow_type=workflow_type,
            response=JSONResponse(status_code=403, content={"error": "decision_rejected"}),
        )
    return JSONResponse(status_code=200, content=view)


def workflow_views_for_case(settings: Settings, case_id: str) -> list[dict]:
    """Read workflow projections for a review page. This does not resume anything."""
    from app.langgraph_workflow_orchestration import read_workflows_for_case, workflow_db_path

    return read_workflows_for_case(workflow_db_path(settings), case_id)


def resume_after_human_decision(settings: Settings, repository: Any, review_case_id: str, outcome: str):
    """Hook used after a successful close. A missing workflow is not an error."""
    from app.langgraph_workflow_orchestration import resume_after_human_decision as resume_saved

    return resume_saved(settings, repository, review_case_id, outcome)


def _workflow_guard(request: Request, settings: Settings) -> Response | None:
    if not authenticate(request, settings):
        return Response(status_code=401)
    if not settings.followup_agent_enabled:
        return JSONResponse(status_code=503, content={"detail": DISABLED_DETAIL})
    return None


def _workflow_operation_guard(
    request: Request,
    settings: Settings,
    event_type: str,
) -> tuple[Response | None, str]:
    correlation_id = audit_correlation_id(request.headers.get("X-Correlation-ID"))
    if not authenticate(request, settings):
        presented = request.headers.get("X-Service-Token")
        reason = "service_token_missing" if presented is None or presented == "" else "service_token_invalid"
        return (
            _workflow_denied_response(
                request,
                settings,
                event_type=event_type,
                reason_code=reason,
                correlation_id=correlation_id,
                authenticated=False,
                response=Response(status_code=401),
            ),
            correlation_id,
        )
    if not settings.followup_agent_enabled:
        return (
            _workflow_denied_response(
                request,
                settings,
                event_type=event_type,
                reason_code="workflow_disabled",
                correlation_id=correlation_id,
                response=JSONResponse(status_code=503, content={"detail": DISABLED_DETAIL}),
            ),
            correlation_id,
        )
    return None, correlation_id


def _workflow_denied_response(
    request: Request,
    settings: Settings,
    *,
    event_type: str,
    reason_code: str,
    correlation_id: str,
    response: Response,
    authenticated: bool = True,
    workflow_id: str | None = None,
    workflow_type: str | None = None,
) -> Response:
    stored = _append_workflow_audit(
        request,
        settings,
        event_type=event_type,
        outcome="denied",
        reason_code=reason_code,
        correlation_id=correlation_id,
        authenticated=authenticated,
        workflow_id=workflow_id,
        workflow_type=workflow_type,
    )
    return response if stored else _audit_unavailable_response()


def _append_workflow_audit(
    request: Request,
    settings: Settings,
    *,
    event_type: str,
    outcome: str,
    reason_code: str,
    correlation_id: str,
    authenticated: bool,
    workflow_id: str | None = None,
    workflow_type: str | None = None,
) -> bool:
    repository = resolve_security_audit_repository(
        settings,
        injected=getattr(request.app.state, "security_audit_repository", None),
        session_repository=getattr(request.app.state, "human_session_repository", None),
    )
    if repository is None:
        return False
    try:
        repository.append(
            workflow_security_event(
                event_type=event_type,
                outcome=outcome,
                reason_code=reason_code,
                correlation_id=correlation_id,
                authenticated=authenticated,
                workflow_id=workflow_id,
                workflow_type=workflow_type,
                clock=getattr(request.app.state, "security_audit_clock", None),
            )
        )
    except (SecurityAuditUnavailable, SecurityAuditStoreInitializationError, SecurityAuditRejected):
        return False
    return True


def _audit_unavailable_response() -> JSONResponse:
    return JSONResponse(status_code=503, content={"detail": SECURITY_AUDIT_UNAVAILABLE_DETAIL})


def _workflow_read(
    request: Request,
    settings: Settings,
    workflow_id: str,
    fields: tuple[str, ...] | None,
) -> Response:
    denied = _workflow_guard(request, settings)
    if denied is not None:
        return denied
    canonical_id = _canonical_workflow_id(workflow_id)
    if canonical_id is None:
        return JSONResponse(status_code=422, content={"error": "invalid_request"})
    from app.langgraph_workflow_orchestration import read_workflow_record, workflow_db_path

    saver = getattr(request.app.state, "agent_workflow_saver", None)
    if saver is not None:
        view = saver.index_get(canonical_id)
    else:
        view = read_workflow_record(workflow_db_path(settings), canonical_id)
    if view is None:
        return JSONResponse(status_code=404, content={"error": "workflow_not_found"})
    if fields is not None:
        view = {name: view.get(name) for name in fields}
    return JSONResponse(status_code=200, content=view)


def _canonical_workflow_id(value: str) -> str | None:
    if not isinstance(value, str) or len(value) != 35 or not value.startswith("wf-"):
        return None
    digest = value[3:]
    if any(char not in "0123456789abcdef" for char in digest):
        return None
    return value
