from __future__ import annotations

from datetime import datetime, timezone
import json
import threading

import httpx
import pytest
from langchain_core.messages import AIMessage

from app.langgraph_fhir_client import (
    APPOINTMENTS_TOOL,
    CASE_IDENTIFIER_SYSTEM,
    FOLLOWUP_TOOL,
    InMemoryAuditSink,
    PreparedReadClient,
    BoundedSearchResult,
    BoundedSearchStatus,
    synthetic_appointment,
)
from app.langgraph_fhir_hapi import HapiReadClient
from app.langgraph_followup_workflow import FollowUpWorkflow
from app.followup_models import dump_followup_endpoint_response
from app.followup_service import _project
from app.post_consultation_review import ProtocolEvaluationStatus


CASE = "SYN-FOLLOWUP-008"
PATIENT = "patient-008"


class CountingModel:
    def __init__(self, replies: list[AIMessage]) -> None:
        self.replies = list(replies)
        self.calls = 0

    def __call__(self, _messages):
        self.calls += 1
        return self.replies.pop(0)


def _final(token: str = "unknown") -> AIMessage:
    return AIMessage(content="legacy answer", additional_kwargs={"follow_up_required": token})


def _workflow(client, model: CountingModel, sink: InMemoryAuditSink | None = None) -> FollowUpWorkflow:
    return FollowUpWorkflow(
        model=model,
        sink=sink or InMemoryAuditSink(),
        fhir_client=client,
        clock=lambda: "2026-09-29T00:00:00Z",
        run_id="run-post-consultation",
        now=lambda: datetime(2026, 9, 29, tzinfo=timezone.utc),
    )


def _prepared(**kwargs) -> PreparedReadClient:
    return PreparedReadClient(case_id=CASE, patient_id=PATIENT, appointments=[], **kwargs)


def test_mandatory_acquisition_runs_before_an_immediate_final_model_answer():
    client = _prepared()
    model = CountingModel([_final()])
    result = _workflow(client, model).run(CASE)
    assert model.calls == 1
    assert result.protocol.evaluation_status is ProtocolEvaluationStatus.MATCHED
    assert result.tools_used == []
    assert client.calls == [
        f"Patient?identifier=https%3A%2F%2Flab.local%2Ffollowup-case%7C{CASE}&_count=2",
        f"Patient/{PATIENT}",
        f"Encounter?patient=Patient/{PATIENT}&status=finished&_count=25",
        f"Observation?subject=Patient/{PATIENT}&status=final&_count=25",
        f"Appointment?patient=Patient/{PATIENT}&_count=25",
    ]


def test_denied_model_tool_cannot_suppress_the_protocol_result():
    denied = AIMessage(
        content="",
        tool_calls=[
            {
                "name": "send_message",
                "args": {"patient_id": "forbidden", "body": "forbidden"},
                "id": "call-denied",
                "type": "tool_call",
            }
        ],
    )
    sink = InMemoryAuditSink()
    result = _workflow(_prepared(), CountingModel([denied]), sink).run(CASE)
    assert result.status == "denied"
    assert result.protocol.evaluation_status is ProtocolEvaluationStatus.MATCHED
    assert [(event.tool_name, event.decision) for event in sink.events] == [("send_message", "denied")]


@pytest.mark.parametrize("token", ["true", "false", "unknown"])
def test_legacy_follow_up_token_does_not_change_protocol(token: str):
    result = _workflow(_prepared(), CountingModel([_final(token)])).run(CASE)
    assert result.follow_up_required == token
    assert result.protocol.evaluation_status is ProtocolEvaluationStatus.MATCHED
    assert result.protocol.matched_resources == (
        "Encounter/encounter-synthetic-001",
        "Observation/obs-synthetic-001",
    )


def test_complete_empty_appointment_search_is_none_and_allows_match():
    result = _workflow(_prepared(), CountingModel([_final()])).run(CASE)
    assert result.appointment_collection == "complete"
    assert result.schedule_check == "checked"
    assert result.schedule_classifications == ("NONE",)
    assert result.protocol.evaluation_status is ProtocolEvaluationStatus.MATCHED


def test_http_projection_uses_only_the_protocol_for_review_and_action():
    matched = _workflow(_prepared(), CountingModel([_final("false")])).run(CASE)
    projected = _project(matched)
    assert projected is not None
    body = dump_followup_endpoint_response(projected)
    assert body["clinicalAssessment"] == {"status": "not_performed"}
    assert body["protocol"] == {
        "id": "POST_CONSULTATION_RESULT_REVIEW_V1",
        "evaluationStatus": "matched",
        "reasonCodes": ["post_consultation_result_requires_review"],
        "matchedResources": [
            "Encounter/encounter-synthetic-001",
            "Observation/obs-synthetic-001",
        ],
    }
    assert body["humanReview"] == {
        "status": "required",
        "reason": "deterministic_post_consultation_protocol_match",
    }
    assert body["action"] == {"status": "proposed", "type": "review_follow_up_case"}
    assert body["followUpRequired"] == "false"


@pytest.mark.parametrize(
    ("appointments", "expected"),
    [
        (
            [
                synthetic_appointment(
                    appointment_id="confirmed",
                    status="booked",
                    start="2026-10-01T10:00:00Z",
                    patient_id=PATIENT,
                )
            ],
            ProtocolEvaluationStatus.NOT_MATCHED,
        ),
        (
            [
                synthetic_appointment(
                    appointment_id="unconfirmed",
                    status="pending",
                    start="2026-10-01T10:00:00Z",
                    patient_id=PATIENT,
                )
            ],
            ProtocolEvaluationStatus.MATCHED,
        ),
        (
            [
                synthetic_appointment(
                    appointment_id="cancelled",
                    status="cancelled",
                    start="2026-10-01T10:00:00Z",
                    patient_id=PATIENT,
                )
            ],
            ProtocolEvaluationStatus.MATCHED,
        ),
    ],
)
def test_schedule_gate_uses_the_complete_collection(appointments, expected):
    client = PreparedReadClient(
        case_id=CASE,
        patient_id=PATIENT,
        appointments=appointments,
    )
    result = _workflow(client, CountingModel([_final()])).run(CASE)
    assert result.protocol.evaluation_status is expected


def test_missing_final_observation_and_wrong_explicit_association_are_insufficient():
    no_observation = _workflow(
        _prepared(observations=[]), CountingModel([_final()])
    ).run(CASE)
    assert no_observation.protocol.evaluation_status is ProtocolEvaluationStatus.INSUFFICIENT
    foreign_reference = _prepared(
        observations=[
            {
                "resourceType": "Observation",
                "id": "obs-other-encounter",
                "status": "final",
                "subject": {"reference": f"Patient/{PATIENT}"},
                "encounter": {"reference": "Encounter/not-fetched"},
                "issued": "2026-09-29T12:00:00Z",
            }
        ]
    )
    wrong = _workflow(foreign_reference, CountingModel([_final()])).run(CASE)
    assert wrong.protocol.evaluation_status is ProtocolEvaluationStatus.INSUFFICIENT


@pytest.mark.parametrize("failure", ["encounter", "observation", "appointment"])
def test_mandatory_acquisition_failure_skips_the_model(failure: str):
    client = _prepared(
        fail_encounter_read=failure == "encounter",
        fail_observation_read=failure == "observation",
        fail_appointment_read=failure == "appointment",
    )
    model = CountingModel([_final()])
    result = _workflow(client, model).run(CASE)
    assert result.status == "unavailable"
    assert result.protocol.evaluation_status is ProtocolEvaluationStatus.UNAVAILABLE
    assert result.follow_up_required == "unknown"
    assert model.calls == 0
    projected = _project(result)
    assert projected is not None
    body = dump_followup_endpoint_response(projected)
    assert body["humanReview"] == {"status": "not_determined"}
    assert body["action"] == {"status": "not_determined"}


def test_complete_cached_tool_reads_do_not_repeat_fhir_or_evidence():
    tool_call = AIMessage(
        content="",
        tool_calls=[
            {
                "name": FOLLOWUP_TOOL,
                "args": {"case_id": CASE},
                "id": "call-context",
                "type": "tool_call",
            },
            {
                "name": APPOINTMENTS_TOOL,
                "args": {"case_id": CASE},
                "id": "call-appointments",
                "type": "tool_call",
            },
        ],
    )
    sink = InMemoryAuditSink()
    client = _prepared()
    result = _workflow(client, CountingModel([tool_call, _final()]), sink).run(CASE)
    assert len(client.calls) == 5
    assert result.tools_used == [FOLLOWUP_TOOL, APPOINTMENTS_TOOL]
    assert len(result.evidence) == 1
    assert len(sink.events) == 2


def _patient() -> dict:
    return {
        "resourceType": "Patient",
        "id": PATIENT,
        "identifier": [{"system": CASE_IDENTIFIER_SYSTEM, "value": CASE}],
    }


def _encounter(encounter_id: str) -> dict:
    return {
        "resourceType": "Encounter",
        "id": encounter_id,
        "status": "finished",
        "subject": {"reference": f"Patient/{PATIENT}"},
        "period": {"end": "2026-09-29T10:00:00Z"},
    }


def _observation(observation_id: str, encounter_id: str, patient_id: str = PATIENT) -> dict:
    return {
        "resourceType": "Observation",
        "id": observation_id,
        "status": "final",
        "subject": {"reference": f"Patient/{patient_id}"},
        "encounter": {"reference": f"Encounter/{encounter_id}"},
        "issued": "2026-09-29T10:00:01Z",
    }


def _bundle(resources=(), next_page: int | None = None) -> dict:
    value = {
        "resourceType": "Bundle",
        "type": "searchset",
        "entry": [{"resource": resource} for resource in resources],
    }
    if next_page is not None:
        value["link"] = [{"relation": "next", "url": f"?page={next_page}"}]
    return value


def _paged_workflow(
    *,
    encounter_pages: dict[int, tuple[list[dict], int | None]] | None = None,
    observation_pages: dict[int, tuple[list[dict], int | None]] | None = None,
    appointment_pages: dict[int, tuple[list[dict], int | None]] | None = None,
    fail: tuple[str, int] | None = None,
    transient_once: tuple[str, int] | None = None,
    model_replies: list[AIMessage] | None = None,
    sink: InMemoryAuditSink | None = None,
):
    encounter_pages = encounter_pages or {1: ([_encounter("enc-1")], None)}
    observation_pages = observation_pages or {1: ([_observation("obs-1", "enc-1")], None)}
    appointment_pages = appointment_pages or {1: ([], None)}
    seen: list[str] = []
    transient_attempts = 0

    def handler(request: httpx.Request) -> httpx.Response:
        nonlocal transient_attempts
        seen.append(str(request.url))
        endpoint = request.url.path.rsplit("/", 1)[-1]
        page = int(request.url.params.get("page", "1"))
        if fail == (endpoint, page):
            return httpx.Response(503, json={"resourceType": "OperationOutcome"})
        if transient_once == (endpoint, page) and transient_attempts == 0:
            transient_attempts += 1
            return httpx.Response(503, json={"resourceType": "OperationOutcome"})
        if endpoint == PATIENT:
            return httpx.Response(200, json=_patient())
        if endpoint == "Patient":
            return httpx.Response(200, json=_bundle([_patient()]))
        pages = {
            "Encounter": encounter_pages,
            "Observation": observation_pages,
            "Appointment": appointment_pages,
        }[endpoint]
        resources, next_page = pages[page]
        return httpx.Response(200, json=_bundle(resources, next_page))

    http = httpx.Client(transport=httpx.MockTransport(handler), timeout=5.0)
    client = HapiReadClient("http://hapi.example/fhir", http_client=http)
    model = CountingModel(model_replies or [_final()])
    return _workflow(client, model, sink), model, http, seen


def _identity_workflow(patient_id: str):
    seen: list[str] = []
    patient = {
        "resourceType": "Patient",
        "id": patient_id,
        "identifier": [{"system": CASE_IDENTIFIER_SYSTEM, "value": CASE}],
    }

    def handler(request: httpx.Request) -> httpx.Response:
        seen.append(str(request.url))
        endpoint = request.url.path.rsplit("/", 1)[-1]
        if endpoint == "Patient":
            return httpx.Response(200, json=_bundle([patient]))
        if endpoint == patient_id:
            return httpx.Response(200, json=patient)
        if endpoint == "Encounter":
            encounter = _encounter("enc-dot")
            encounter["subject"] = {"reference": f"Patient/{patient_id}"}
            return httpx.Response(200, json=_bundle([encounter]))
        if endpoint == "Observation":
            return httpx.Response(
                200,
                json=_bundle([_observation("obs-dot", "enc-dot", patient_id)]),
            )
        if endpoint == "Appointment":
            return httpx.Response(200, json=_bundle([]))
        raise AssertionError(f"unexpected request: {request.url}")

    http = httpx.Client(transport=httpx.MockTransport(handler), timeout=5.0)
    client = HapiReadClient("http://hapi.example/fhir", http_client=http)
    model = CountingModel([_final()])
    return _workflow(client, model), model, http, seen


def test_valid_fhir_patient_id_with_dot_completes_mandatory_acquisition():
    workflow, model, http, seen = _identity_workflow("patient.008")
    try:
        result = workflow.run(CASE)
    finally:
        http.close()
    assert result.protocol.evaluation_status is ProtocolEvaluationStatus.MATCHED
    assert model.calls == 1
    assert any("/Patient/patient.008" in url for url in seen)


@pytest.mark.parametrize(
    "patient_id",
    [
        ".",
        "..",
        "../../admin",
        "../Patient/x",
        "",
        "a" * 65,
        "patient/008",
        "patient%2F008",
    ],
)
def test_invalid_patient_id_fails_before_any_patient_instance_get(patient_id: str):
    workflow, model, http, seen = _identity_workflow(patient_id)
    try:
        result = workflow.run(CASE)
    finally:
        http.close()
    assert result.status == "unavailable"
    assert result.protocol.evaluation_status is ProtocolEvaluationStatus.UNAVAILABLE
    assert model.calls == 0
    assert len(seen) == 1
    assert "/Patient?" in seen[0]


@pytest.mark.parametrize(
    ("target", "reference"),
    [
        ("observation_subject", f"Patient/patient-foreign?alias=/Patient/{PATIENT}"),
        ("observation_subject", f"Patient/{PATIENT}?x=1"),
        ("observation_subject", f"Patient/{PATIENT}#fragment"),
        ("observation_subject", f"https://evil.example/fhir/Patient/{PATIENT}"),
        ("observation_subject", f"https://hapi.example/fhir/Patient/{PATIENT}/extra"),
        ("observation_subject", f"Encounter/{PATIENT}"),
        ("observation_subject", f"Patient%2F{PATIENT}"),
        ("observation_subject", f"Patient/../Patient/{PATIENT}"),
        ("observation_encounter", "Encounter/foreign?alias=/Encounter/enc-1"),
        ("observation_encounter", "Encounter/enc-1?alias=x"),
        ("observation_encounter", "Encounter/."),
        ("observation_encounter", "Encounter/.."),
        ("observation_encounter", "Patient/enc-1"),
        ("observation_encounter", "Encounter%2Fenc-1"),
        ("encounter_subject", f"Patient/{PATIENT}?x=1"),
        ("encounter_subject", "Patient/."),
        ("encounter_subject", "Patient/.."),
        ("appointment_participant", f"Patient/{PATIENT}#fragment"),
    ],
)
def test_noncanonical_fhir_references_fail_closed_in_productive_workflow(
    target: str,
    reference: str,
):
    encounter = _encounter("enc-1")
    observation = _observation("obs-bad-reference", "enc-1")
    appointment = synthetic_appointment(
        appointment_id="appointment-bad-reference",
        status="cancelled",
        start="2026-09-28T10:00:00Z",
        patient_id=PATIENT,
    )
    if target == "observation_subject":
        observation["subject"] = {"reference": reference}
    elif target == "observation_encounter":
        observation["encounter"] = {"reference": reference}
    elif target == "encounter_subject":
        encounter["subject"] = {"reference": reference}
    else:
        appointment["participant"][0]["actor"] = {"reference": reference}
    client = PreparedReadClient(
        case_id=CASE,
        patient_id=PATIENT,
        encounters=[encounter],
        observations=[observation],
        appointments=[appointment],
    )
    model = CountingModel([_final()])
    result = _workflow(client, model).run(CASE)
    assert result.status == "unavailable"
    assert result.protocol.evaluation_status is ProtocolEvaluationStatus.UNAVAILABLE
    assert model.calls == 0
    assert "obs-bad-reference" not in str(result) or target not in {
        "observation_subject",
        "observation_encounter",
    }


@pytest.mark.parametrize("field", ["entry", "link"])
@pytest.mark.parametrize("invalid", [{}, "", 0, False, None])
def test_malformed_falsy_bundle_arrays_make_workflow_unavailable(field: str, invalid):
    seen: list[str] = []

    def handler(request: httpx.Request) -> httpx.Response:
        seen.append(str(request.url))
        endpoint = request.url.path.rsplit("/", 1)[-1]
        if endpoint == PATIENT:
            return httpx.Response(200, json=_patient())
        if endpoint == "Patient":
            return httpx.Response(200, json=_bundle([_patient()]))
        if endpoint == "Encounter":
            return httpx.Response(200, json=_bundle([_encounter("enc-1")]))
        if endpoint == "Observation":
            return httpx.Response(200, json=_bundle([_observation("obs-1", "enc-1")]))
        payload = _bundle([])
        payload[field] = invalid
        return httpx.Response(200, json=payload)

    http = httpx.Client(transport=httpx.MockTransport(handler), timeout=5.0)
    model = CountingModel([_final()])
    workflow = _workflow(
        HapiReadClient("http://hapi.example/fhir", http_client=http),
        model,
    )
    try:
        result = workflow.run(CASE)
    finally:
        http.close()
    assert result.status == "unavailable"
    assert result.protocol.evaluation_status is ProtocolEvaluationStatus.UNAVAILABLE
    assert model.calls == 0


def test_partial_observation_rejected_tool_has_no_success_evidence_or_tool_entry():
    observation = _observation("obs-partial", "encounter-synthetic-001")

    class PartialObservationClient(PreparedReadClient):
        def search(self, path: str, expected_resource_type: str):
            if expected_resource_type == "Observation":
                self.calls.append(path)
                return BoundedSearchResult(
                    BoundedSearchStatus.INCOMPLETE_LIMIT,
                    (dict(observation),),
                    "page limit reached with continuation",
                )
            return super().search(path, expected_resource_type)

    context_call = AIMessage(
        content="",
        tool_calls=[
            {
                "name": FOLLOWUP_TOOL,
                "args": {"case_id": CASE},
                "id": "partial-context",
                "type": "tool_call",
            }
        ],
    )
    sink = InMemoryAuditSink()
    model = CountingModel([context_call])
    client = PartialObservationClient(case_id=CASE, patient_id=PATIENT, appointments=[])
    result = _workflow(client, model, sink).run(CASE)
    assert result.status == "unavailable"
    assert result.protocol.evaluation_status is ProtocolEvaluationStatus.INSUFFICIENT
    assert result.observation_collection == "partial"
    assert result.tools_used == []
    assert result.evidence == []
    assert [(event.tool_name, event.decision) for event in sink.events] == [
        (FOLLOWUP_TOOL, "allowed")
    ]


def test_submicrosecond_protocol_timestamps_are_insufficient_in_productive_workflow():
    encounter = _encounter("enc-precision")
    encounter["period"]["end"] = "2026-09-29T10:00:00.0000002Z"
    observation = _observation("obs-precision", "enc-precision")
    observation["issued"] = "2026-09-29T10:00:00.0000001Z"
    model = CountingModel([_final()])
    result = _workflow(
        PreparedReadClient(
            case_id=CASE,
            patient_id=PATIENT,
            encounters=[encounter],
            observations=[observation],
            appointments=[],
        ),
        model,
    ).run(CASE)
    assert result.protocol.evaluation_status is ProtocolEvaluationStatus.INSUFFICIENT
    assert result.protocol.matched_resources == ()
    assert model.calls == 1


def test_qualifying_encounter_and_observation_on_page_two_are_found():
    workflow, model, http, _seen = _paged_workflow(
        encounter_pages={1: ([_encounter("unused")], 2), 2: ([_encounter("enc-2")], None)},
        observation_pages={
            1: ([_observation("obs-unused", "missing")], 2),
            2: ([_observation("obs-2", "enc-2")], None),
        },
    )
    try:
        result = workflow.run(CASE)
    finally:
        http.close()
    assert model.calls == 1
    assert result.protocol.evaluation_status is ProtocolEvaluationStatus.MATCHED
    assert result.protocol.matched_resources == ("Encounter/enc-2", "Observation/obs-2")


def test_confirmed_appointment_only_on_page_two_blocks_match():
    cancelled = synthetic_appointment(
        appointment_id="cancelled",
        status="cancelled",
        start="2026-10-01T10:00:00Z",
        patient_id=PATIENT,
    )
    confirmed = synthetic_appointment(
        appointment_id="confirmed",
        status="booked",
        start="2026-10-01T10:00:00Z",
        patient_id=PATIENT,
    )
    workflow, _model, http, _seen = _paged_workflow(
        appointment_pages={1: ([cancelled], 2), 2: ([confirmed], None)}
    )
    try:
        result = workflow.run(CASE)
    finally:
        http.close()
    assert result.protocol.evaluation_status is ProtocolEvaluationStatus.NOT_MATCHED
    assert "Appointment/confirmed" in result.protocol.matched_resources


def test_page_retry_does_not_duplicate_protocol_evidence_or_audit(monkeypatch):
    monkeypatch.setattr("app.langgraph_fhir_hapi._retry_sleep", lambda _delay: None)
    context_call = AIMessage(
        content="",
        tool_calls=[
            {
                "name": FOLLOWUP_TOOL,
                "args": {"case_id": CASE},
                "id": "context-after-retry",
                "type": "tool_call",
            }
        ],
    )
    sink = InMemoryAuditSink()
    workflow, model, http, seen = _paged_workflow(
        observation_pages={
            1: ([_observation("obs-1", "enc-1")], 2),
            2: ([_observation("obs-2", "enc-1")], None),
        },
        transient_once=("Observation", 2),
        model_replies=[context_call, _final()],
        sink=sink,
    )
    try:
        result = workflow.run(CASE)
    finally:
        http.close()
    assert model.calls == 2
    assert sum("/Observation?" in url and "page=2" in url for url in seen) == 2
    assert result.protocol.matched_resources == ("Encounter/enc-1", "Observation/obs-1")
    assert result.evidence == [
        {
            "tool": FOLLOWUP_TOOL,
            "resources": [f"Patient/{PATIENT}", "Observation/obs-1", "Observation/obs-2"],
        }
    ]
    assert [(event.tool_name, event.decision) for event in sink.events] == [(FOLLOWUP_TOOL, "allowed")]


@pytest.mark.parametrize("endpoint", ["Encounter", "Observation", "Appointment"])
def test_later_page_failure_preserves_prior_authorized_resources_and_skips_model(
    endpoint: str,
    monkeypatch,
):
    monkeypatch.setattr("app.langgraph_fhir_hapi._retry_sleep", lambda _delay: None)
    pages = {
        "encounter_pages": {1: ([_encounter("enc-1")], 2), 2: ([_encounter("enc-2")], None)},
        "observation_pages": {
            1: ([_observation("obs-1", "enc-1")], 2),
            2: ([_observation("obs-2", "enc-1")], None),
        },
        "appointment_pages": {
            1: (
                [
                    synthetic_appointment(
                        appointment_id="cancelled",
                        status="cancelled",
                        start="2026-10-01T10:00:00Z",
                        patient_id=PATIENT,
                    )
                ],
                2,
            ),
            2: ([], None),
        },
    }
    workflow, model, http, _seen = _paged_workflow(**pages, fail=(endpoint, 2))
    try:
        result = workflow.run(CASE)
    finally:
        http.close()
    assert result.status == "unavailable"
    assert result.protocol.evaluation_status is ProtocolEvaluationStatus.UNAVAILABLE
    assert model.calls == 0
    if endpoint == "Encounter":
        assert [item["id"] for item in result.protocol_encounters] == ["enc-1"]
    if endpoint == "Observation":
        assert [item["id"] for item in result.observations] == ["obs-1"]
    if endpoint == "Appointment":
        assert result.schedule_appointments == (("Appointment/cancelled", "CANCELLED"),)


def test_foreign_patient_on_later_page_fails_closed_and_is_not_exposed():
    workflow, model, http, _seen = _paged_workflow(
        observation_pages={
            1: ([_observation("obs-authorized", "enc-1")], 2),
            2: ([_observation("obs-foreign", "enc-1", "patient-foreign")], None),
        }
    )
    try:
        result = workflow.run(CASE)
    finally:
        http.close()
    assert result.status == "unavailable"
    assert model.calls == 0
    assert [item["id"] for item in result.observations] == ["obs-authorized"]
    assert "obs-foreign" not in str(result)


@pytest.mark.parametrize("collection", ["Encounter", "Appointment"])
def test_other_foreign_paginated_resources_are_excluded(collection: str):
    kwargs = {}
    foreign_id = "foreign-encounter"
    if collection == "Encounter":
        foreign = {
            **_encounter(foreign_id),
            "subject": {"reference": "Patient/patient-foreign"},
        }
        kwargs["encounter_pages"] = {
            1: ([_encounter("enc-1")], 2),
            2: ([foreign], None),
        }
    else:
        foreign_id = "foreign-appointment"
        foreign = synthetic_appointment(
            appointment_id=foreign_id,
            status="booked",
            start="2026-10-01T10:00:00Z",
            patient_id="patient-foreign",
        )
        kwargs["appointment_pages"] = {1: ([], 2), 2: ([foreign], None)}
    workflow, model, http, _seen = _paged_workflow(**kwargs)
    try:
        result = workflow.run(CASE)
    finally:
        http.close()
    assert result.status == "unavailable"
    assert model.calls == 0
    assert foreign_id not in str(result)


def test_pagination_limit_is_insufficient_and_does_not_invent_none():
    pages = {
        page: (
            [
                synthetic_appointment(
                    appointment_id=f"cancelled-{page}",
                    status="cancelled",
                    start="2026-10-01T10:00:00Z",
                    patient_id=PATIENT,
                )
            ],
            page + 1,
        )
        for page in range(1, 5)
    }
    workflow, model, http, _seen = _paged_workflow(appointment_pages=pages)
    try:
        result = workflow.run(CASE)
    finally:
        http.close()
    assert model.calls == 1
    assert result.status == "finish"
    assert result.appointment_collection == "partial"
    assert result.schedule_check == "not_checked"
    assert "NONE" not in result.schedule_classifications
    assert result.protocol.evaluation_status is ProtocolEvaluationStatus.INSUFFICIENT
    projected = _project(result)
    assert projected is not None
    body = dump_followup_endpoint_response(projected)
    assert body["humanReview"] == {"status": "not_determined"}
    assert body["action"] == {"status": "not_determined"}


@pytest.mark.parametrize(
    ("case_id", "mode", "expected"),
    [
        ("SYN-FOLLOWUP-008", "none", ProtocolEvaluationStatus.MATCHED),
        ("SYN-FOLLOWUP-009", "confirmed", ProtocolEvaluationStatus.NOT_MATCHED),
        ("SYN-FOLLOWUP-010", "no_observation", ProtocolEvaluationStatus.INSUFFICIENT),
        ("SYN-FOLLOWUP-011", "wrong_encounter", ProtocolEvaluationStatus.INSUFFICIENT),
        ("SYN-FOLLOWUP-012", "unconfirmed", ProtocolEvaluationStatus.MATCHED),
        ("SYN-FOLLOWUP-013", "cancelled", ProtocolEvaluationStatus.MATCHED),
        ("SYN-FOLLOWUP-014", "encounter_failure", ProtocolEvaluationStatus.UNAVAILABLE),
    ],
)
def test_named_synthetic_cases_008_through_015(case_id: str, mode: str, expected):
    patient_id = f"patient-{case_id.rsplit('-', 1)[-1]}"
    observations = None
    appointments: list[dict] = []
    fail_encounter = mode == "encounter_failure"
    fail_observation = mode == "observation_failure"
    if mode == "no_observation":
        observations = []
    elif mode == "wrong_encounter":
        observations = [
            {
                "resourceType": "Observation",
                "id": "obs-wrong-encounter",
                "status": "final",
                "subject": {"reference": f"Patient/{patient_id}"},
                "encounter": {"reference": "Encounter/not-authorized"},
                "issued": "2026-09-29T12:00:00Z",
            }
        ]
    if mode in {"confirmed", "unconfirmed", "cancelled"}:
        status = {"confirmed": "booked", "unconfirmed": "pending", "cancelled": "cancelled"}[mode]
        appointments = [
            synthetic_appointment(
                appointment_id=f"appointment-{mode}",
                status=status,
                start="2026-10-01T10:00:00Z",
                patient_id=patient_id,
            )
        ]
    client = PreparedReadClient(
        case_id=case_id,
        patient_id=patient_id,
        observations=observations,
        appointments=appointments,
        fail_encounter_read=fail_encounter,
        fail_observation_read=fail_observation,
    )
    model = CountingModel([_final()])
    result = _workflow(client, model).run(case_id)
    assert result.protocol.evaluation_status is expected
    assert model.calls == (0 if expected is ProtocolEvaluationStatus.UNAVAILABLE else 1)


def test_synthetic_case_015_preserves_page_one_observation_after_page_two_failure():
    case_id = "SYN-FOLLOWUP-015"
    patient_id = "patient-015"
    page_one = {
        "resourceType": "Observation",
        "id": "observation-015-page-1",
        "status": "final",
        "subject": {"reference": f"Patient/{patient_id}"},
        "encounter": {"reference": "Encounter/encounter-synthetic-001"},
        "issued": "2026-09-29T12:00:00Z",
    }

    class Case015Client(PreparedReadClient):
        def search(self, path: str, expected_resource_type: str) -> BoundedSearchResult:
            if expected_resource_type == "Observation":
                self.calls.append(path)
                return BoundedSearchResult(
                    BoundedSearchStatus.FAILED,
                    (dict(page_one),),
                    "HTTP 503",
                )
            return super().search(path, expected_resource_type)

    client = Case015Client(case_id=case_id, patient_id=patient_id, appointments=[])
    model = CountingModel([_final()])
    result = _workflow(client, model).run(case_id)
    assert result.status == "unavailable"
    assert result.protocol.evaluation_status is ProtocolEvaluationStatus.UNAVAILABLE
    assert result.observation_collection == "unavailable"
    assert [item["id"] for item in result.observations] == ["observation-015-page-1"]
    assert model.calls == 0


def test_one_workflow_keeps_concurrent_cases_and_page_tokens_isolated():
    cases = {
        "SYN-FOLLOWUP-008": "patient-008",
        "SYN-FOLLOWUP-012": "patient-012",
    }
    first_pages = threading.Barrier(2)

    def patient_resource(case_id: str, patient_id: str) -> dict:
        return {
            "resourceType": "Patient",
            "id": patient_id,
            "identifier": [{"system": CASE_IDENTIFIER_SYSTEM, "value": case_id}],
        }

    def handler(request: httpx.Request) -> httpx.Response:
        endpoint = request.url.path.rsplit("/", 1)[-1]
        token = request.url.params.get("token")
        if endpoint in cases.values():
            case_id = next(key for key, value in cases.items() if value == endpoint)
            return httpx.Response(200, json=patient_resource(case_id, endpoint))
        if endpoint == "Patient":
            if token is None:
                identifier = request.url.params["identifier"]
                case_id = identifier.rsplit("|", 1)[-1]
                first_pages.wait(timeout=5)
                return httpx.Response(
                    200,
                    json={
                        **_bundle([]),
                        "link": [
                            {"relation": "next", "url": f"?token={case_id}-patient"}
                        ],
                    },
                )
            case_id = token.removesuffix("-patient")
            return httpx.Response(200, json=_bundle([patient_resource(case_id, cases[case_id])]))
        suffix = endpoint.lower()
        if token is None:
            patient_id = request.url.params.get(
                "patient", request.url.params.get("subject", "")
            ).removeprefix("Patient/")
            case_id = next(key for key, value in cases.items() if value == patient_id)
        else:
            case_id = token.removesuffix(f"-{suffix}")
            patient_id = cases[case_id]
        if token is None:
            return httpx.Response(
                200,
                json={
                    "resourceType": "Bundle",
                    "type": "searchset",
                    "entry": [],
                    "link": [{"relation": "next", "url": f"?token={case_id}-{suffix}"}],
                },
            )
        assert token == f"{case_id}-{suffix}"
        if endpoint == "Encounter":
            resources = [
                {
                    "resourceType": "Encounter",
                    "id": f"encounter-{case_id}",
                    "status": "finished",
                    "subject": {"reference": f"Patient/{patient_id}"},
                    "period": {"end": "2026-09-29T10:00:00Z"},
                }
            ]
        elif endpoint == "Observation":
            resources = [
                {
                    "resourceType": "Observation",
                    "id": f"observation-{case_id}",
                    "status": "final",
                    "subject": {"reference": f"Patient/{patient_id}"},
                    "encounter": {"reference": f"Encounter/encounter-{case_id}"},
                    "issued": "2026-09-29T10:00:01Z",
                }
            ]
        else:
            resources = []
        return httpx.Response(200, json=_bundle(resources))

    http = httpx.Client(transport=httpx.MockTransport(handler), timeout=5.0)
    client = HapiReadClient("http://hapi.example/fhir", http_client=http)

    def model(_messages):
        return _final()

    workflow = FollowUpWorkflow(
        model=model,
        sink=InMemoryAuditSink(),
        fhir_client=client,
        clock=lambda: "2026-09-29T00:00:00Z",
        run_id="run-concurrent-pagination",
        now=lambda: datetime(2026, 9, 29, tzinfo=timezone.utc),
    )
    results = {}
    errors = []

    def run(case_id: str) -> None:
        try:
            results[case_id] = workflow.run(case_id)
        except Exception as exc:  # pragma: no cover - asserted below
            errors.append(exc)

    threads = [threading.Thread(target=run, args=(case_id,)) for case_id in cases]
    try:
        for thread in threads:
            thread.start()
        for thread in threads:
            thread.join(timeout=5)
    finally:
        http.close()
    assert errors == []
    assert all(not thread.is_alive() for thread in threads)
    for case_id, patient_id in cases.items():
        result = results[case_id]
        rendered = json.dumps(result.protocol.matched_resources)
        assert result.protocol.evaluation_status is ProtocolEvaluationStatus.MATCHED
        assert patient_id not in rendered
        assert case_id in rendered
        for other_case in cases:
            if other_case != case_id:
                assert other_case not in rendered
    assert all("token=" not in str(result) for result in results.values())
