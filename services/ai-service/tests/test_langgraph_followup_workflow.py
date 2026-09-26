"""C16-R application boundary. Deterministic tests inject a model and an in-memory client.

Live model reads are skipped unless both opt-in flags are true.
"""

from __future__ import annotations

import inspect
import json
import logging
import os
from dataclasses import asdict
from pathlib import Path

import httpx
import pytest
from langchain_core.messages import AIMessage

from app.langgraph_fhir_client import (
    BOUNDARY_EVENTS,
    CASE_IDENTIFIER_SYSTEM,
    DENIAL_ANSWER,
    FOLLOWUP_TOOL,
    PATIENT_CASE,
    PATIENT_ID,
    POLICY_VERSION,
    SAFE_AUDIT_FIELDS,
    FailingPreparedReadClient,
    InMemoryAuditSink,
    ReadClientError,
    clear_boundary_events,
    evaluate_tool_policy,
    record_policy_audit,
)
from app.langgraph_fhir_followup import UNAVAILABLE_ANSWER, case_search_path, make_followup_tool
from app.langgraph_fhir_hapi import HapiReadClient, hapi_base_url
from app.langgraph_followup_workflow import (
    APPLICATION_RESPONSIBILITIES,
    LANGGRAPH_RESPONSIBILITIES,
    MAX_MODEL_TURNS,
    FollowUpWorkflow,
    FollowUpWorkflowResult,
    build_live_followup_workflow,
)
from app.langgraph_gemini_fhir_followup import MODEL_LIMIT_ANSWER, followup_message_from_response


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
CASE_READS = [case_search_path(PATIENT_CASE), PATIENT_PATH, OBSERVATION_PATH]
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
        if path == case_search_path(PATIENT_CASE):
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
        if path == OBSERVATION_PATH:
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
                            "valueString": self.value,
                        }
                    }
                ],
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
    result = _workflow(client, ScriptedModel([_signed_tool_call(), AIMessage(content=FINAL_TEXT)]), sink).run(
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
    }
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
    for text in CLINICAL_TEXT + ("thought_signature", "synthetic-thought-signature", "prompt", "authorization", "AIza"):
        assert text not in audit
    assert FINAL_TEXT not in inspect.getsource(FollowUpWorkflow)


def test_injected_policy_is_called_before_the_tool():
    seen: list[str] = []

    def policy(name: str):
        seen.append(name)
        return evaluate_tool_policy(name)

    client = MemoryReadClient()
    _workflow(client, ScriptedModel([_tool_call(), AIMessage(content=FINAL_TEXT)]), policy=policy).run(PATIENT_CASE)
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
    assert client.calls == []
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
            ScriptedModel([_signed_tool_call(), AIMessage(content=FINAL_TEXT)]),
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
    assert client.calls == []
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
    assert client.calls == []
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
    assert client.calls == []
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
        ScriptedModel([_tool_call(), AIMessage(content=FINAL_TEXT)]),
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
    assert client.calls == [case_search_path(missing)]
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
            self.calls: list[str] = []

        def get(self, path: str) -> dict:
            self.calls.append(path)
            if path == f"Patient/{PATIENT_CASE}":
                raise AssertionError("case id was used as a Patient.id")
            if path == case_search_path(PATIENT_CASE):
                return {
                    "resourceType": "Bundle",
                    "type": "searchset",
                    "entry": [
                        {"resource": {"resourceType": "Patient", "id": PATIENT_CASE}},
                        {
                            "resource": {
                                "resourceType": "Patient",
                                "id": "SYN-PATIENT-OTHER",
                                "identifier": [
                                    {"system": "https://lab.local/other", "value": PATIENT_CASE}
                                ],
                            }
                        },
                        {
                            "resource": {
                                "resourceType": "Patient",
                                "id": PATIENT_ID,
                                "identifier": [
                                    {"system": CASE_IDENTIFIER_SYSTEM, "value": PATIENT_CASE}
                                ],
                                "name": [{"text": "Synthetic Patient"}],
                            }
                        },
                    ],
                }
            if path == PATIENT_PATH:
                return {
                    "resourceType": "Patient",
                    "id": PATIENT_ID,
                    "name": [{"text": "Synthetic Patient"}],
                }
            if path == OBSERVATION_PATH:
                return {
                    "resourceType": "Bundle",
                    "type": "searchset",
                    "entry": [
                        {
                            "resource": {
                                "resourceType": "Observation",
                                "id": "obs-synthetic-001",
                                "valueString": "Synthetic observation result",
                            }
                        }
                    ],
                }
            raise ReadClientError("unexpected path")

    client = _DistinctClient()
    result = _workflow(
        client,
        ScriptedModel([_tool_call(), AIMessage(content=FINAL_TEXT)]),
    ).run(PATIENT_CASE)
    assert result.status == "finish"
    assert result.patient["id"] == PATIENT_ID
    assert result.evidence[0]["resources"] == [f"Patient/{PATIENT_ID}", "Observation/obs-synthetic-001"]
    assert client.calls == CASE_READS


def test_fhir_failure_does_not_invent_clinical_context():
    client = FailingPreparedReadClient()
    sink = InMemoryAuditSink()
    model = ScriptedModel([_tool_call(), AIMessage(content=FINAL_TEXT)])
    result = _workflow(client, model, sink).run(PATIENT_CASE)
    assert result.status == "unavailable"
    assert result.final_answer == UNAVAILABLE_ANSWER
    assert result.follow_up_required == "unknown"
    assert result.patient is None
    assert result.observations == []
    assert result.evidence == []
    assert result.tools_used == []
    assert len(model.seen) == 1
    assert sink.events[0].decision == "allowed"
    assert BOUNDARY_EVENTS.index(f"audit:{FOLLOWUP_TOOL}:allowed") < BOUNDARY_EVENTS.index(
        f"execute:{FOLLOWUP_TOOL}"
    )
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
    assert client.calls == []
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
    assert result.turns == MAX_MODEL_TURNS
    assert MAX_MODEL_TURNS == 4
    assert model.replies[0].content == "this reply must not be requested"
    assert BOUNDARY_EVENTS.count(f"execute:{FOLLOWUP_TOOL}") == MAX_MODEL_TURNS


def test_the_same_workflow_accepts_a_different_fhir_client():
    first = _workflow(
        MemoryReadClient(),
        ScriptedModel([_tool_call(), AIMessage(content=FINAL_TEXT)]),
    ).run(PATIENT_CASE)
    second = _workflow(
        MemoryReadClient(name="Alternate Synthetic", observation_id="obs-synthetic-002", value="Alternate value"),
        ScriptedModel([_tool_call(), AIMessage(content=FINAL_TEXT)]),
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
        model=ScriptedModel([_tool_call(), AIMessage(content=FINAL_TEXT)]),
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
    result = _workflow(
        MemoryReadClient(),
        ScriptedModel(
            [
                _tool_call(),
                AIMessage(content="The text says follow-up is true because an observation exists."),
            ]
        ),
    ).run(PATIENT_CASE)
    assert result.follow_up_required == "unknown"
    assert result.final_answer == "The text says follow-up is true because an observation exists."
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
    result = _workflow(client, ScriptedModel([_tool_call(), AIMessage(content=FINAL_TEXT)]), sink).run(PATIENT_CASE)
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
    assert result.tools_used == [FOLLOWUP_TOOL]
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
    assert workflow.fhir_client.calls == CASE_READS


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
    return patient, observation
