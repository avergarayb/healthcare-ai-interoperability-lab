"""C16-Q model follow-up. Deterministic tests inject a model and a fake HTTP transport.

Live model reads are skipped unless both opt-in flags are true.
"""

from __future__ import annotations

import inspect
import json
import os
from dataclasses import asdict

import httpx
import pytest
from langchain_core.messages import AIMessage, HumanMessage, ToolMessage
from langgraph.graph import END, START
from langgraph.prebuilt import ToolNode

from app.langgraph_fhir_client import (
    BOUNDARY_EVENTS,
    CASE_IDENTIFIER_SYSTEM,
    DENIAL_ANSWER,
    FOLLOWUP_TOOL,
    PATIENT_CASE,
    PATIENT_ID,
    SAFE_AUDIT_FIELDS,
    InMemoryAuditSink,
    clear_boundary_events,
)
from app.langgraph_fhir_followup import UNAVAILABLE_ANSWER, case_search_path, make_followup_tool
from app.langgraph_fhir_hapi import HapiReadClient, hapi_base_url
from app.langgraph_gemini_fhir_followup import (
    MAX_MODEL_TURNS,
    MODEL_LIMIT_ANSWER,
    GeminiFhirFollowUp,
    build_gemini_fhir_followup,
    build_live_gemini_fhir_followup,
    _contents,
    describe_followup_contents,
    followup_message_from_response,
    followup_tool_schema,
    gemini_error_diagnostics,
    initial_state,
)
PATIENT_PATH = f"Patient/{PATIENT_ID}"
OBSERVATION_PATH = f"Observation?subject=Patient/{PATIENT_ID}"
CASE_READS = [case_search_path(PATIENT_CASE), PATIENT_PATH, OBSERVATION_PATH]
FINAL_TEXT = "Context received."
CLINICAL_TEXT = (
    "Name From Server",
    "Value read from the server",
    "obs-from-transport",
    "Synthetic Patient",
    "Synthetic observation result",
    "obs-synthetic-001",
    "resourceType",
    "valueString",
    f"Patient/{PATIENT_ID}",
)
AUDIT_FORBIDDEN = (
    "prompt",
    "completion",
    "api_key",
    "password",
    "authorization",
    "payload",
    "diagnosis",
    "AIza",
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


@pytest.fixture(autouse=True)
def _clear_probe():
    clear_boundary_events()
    yield
    clear_boundary_events()


def _clock() -> str:
    return "2026-09-25T00:00:03Z"


def _tool_call(
    name: str = FOLLOWUP_TOOL,
    arguments: dict | None = None,
    call_id: str = "call-1",
) -> AIMessage:
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


def _patient(name: str) -> dict:
    return {
        "resourceType": "Patient",
        "id": PATIENT_ID,
        "active": True,
        "identifier": [{"system": CASE_IDENTIFIER_SYSTEM, "value": PATIENT_CASE}],
        "name": [{"text": name}],
    }


def _observation(observation_id: str, value: str) -> dict:
    return {
        "resourceType": "Observation",
        "id": observation_id,
        "status": "final",
        "subject": {"reference": f"Patient/{PATIENT_ID}"},
        "valueString": value,
    }


def _bundle(observation: dict) -> dict:
    return {"resourceType": "Bundle", "type": "searchset", "entry": [{"resource": observation}]}


def _client(handler) -> tuple[HapiReadClient, httpx.Client]:
    http = httpx.Client(transport=httpx.MockTransport(handler), timeout=5.0)
    return HapiReadClient("http://hapi.example/fhir", http_client=http), http


def _ok(name: str, observation_id: str, value: str):
    patient = _patient(name)
    observation = _observation(observation_id, value)

    def handler(request: httpx.Request) -> httpx.Response:
        path = request.url.path.rstrip("/")
        if path.endswith("/Patient") and "identifier=" in str(request.url.query):
            return httpx.Response(
                200,
                json={"resourceType": "Bundle", "type": "searchset", "entry": [{"resource": patient}]},
            )
        if request.url.path.endswith(f"/{PATIENT_PATH}"):
            return httpx.Response(200, json=patient)
        if request.url.path.endswith("/Observation"):
            return httpx.Response(200, json=_bundle(observation))
        return httpx.Response(404, json={"resourceType": "OperationOutcome"})

    return handler


def _workflow(client: HapiReadClient, model, sink: InMemoryAuditSink | None = None) -> GeminiFhirFollowUp:
    return build_gemini_fhir_followup(
        client,
        sink or InMemoryAuditSink(),
        model,
        clock=_clock,
        run_id="run-gemini-followup-001",
    )


def _audit_blob(sink: InMemoryAuditSink) -> str:
    return json.dumps([asdict(event) for event in sink.events])


def test_scripted_model_tool_call_is_authorized_before_the_client():
    model = ScriptedModel([_tool_call(), AIMessage(content=FINAL_TEXT)])
    client, http = _client(_ok("Name From Server", "obs-from-transport", "Value read from the server"))
    sink = InMemoryAuditSink()
    try:
        workflow = _workflow(client, model, sink)
        result = workflow.invoke()
    finally:
        http.close()
    first = next(message for message in result["messages"] if isinstance(message, AIMessage))
    assert first.tool_calls[0]["name"] == FOLLOWUP_TOOL
    assert first.tool_calls[0]["args"] == {"case_id": PATIENT_CASE}
    tool_message = next(message for message in result["messages"] if isinstance(message, ToolMessage))
    assert tool_message.name == FOLLOWUP_TOOL
    assert tool_message.tool_call_id == "call-1"
    assert any(isinstance(message, ToolMessage) for message in model.seen[1])
    assert result["patient"]["id"] == PATIENT_ID
    assert result["patient"]["name"] == "Name From Server"
    assert result["observations"][0]["id"] == "obs-from-transport"
    assert result["observations"][0]["valueString"] == "Value read from the server"
    assert result["evidence"][0]["resources"] == [f"Patient/{PATIENT_ID}", "Observation/obs-from-transport"]
    assert "Patient/SYN-PATIENT-999" not in result["evidence"][0]["resources"]
    assert result["tools_used"] == [FOLLOWUP_TOOL]
    assert result["final_answer"] == FINAL_TEXT
    assert result["decision"] == "finish"
    assert workflow.model_calls == 2
    assert client.calls == CASE_READS
    assert workflow.trace == ["prepare", "agent", "update_state", "agent", "finish"]
    assert sink.events[0].decision == "allowed"
    assert sink.events[0].tool_name == FOLLOWUP_TOOL
    assert sink.events[0].timestamp == "2026-09-25T00:00:03Z"
    assert set(asdict(sink.events[0])) == set(SAFE_AUDIT_FIELDS)
    assert BOUNDARY_EVENTS.index(f"policy:{FOLLOWUP_TOOL}:allowed") < BOUNDARY_EVENTS.index(
        f"audit:{FOLLOWUP_TOOL}:allowed"
    )
    assert BOUNDARY_EVENTS.index(f"audit:{FOLLOWUP_TOOL}:allowed") < BOUNDARY_EVENTS.index(
        f"execute:{FOLLOWUP_TOOL}"
    )
    assert BOUNDARY_EVENTS.count(f"execute:{FOLLOWUP_TOOL}") == 1
    blob = _audit_blob(sink)
    for text in CLINICAL_TEXT + AUDIT_FORBIDDEN:
        assert text not in blob
    assert "Name From Server" not in inspect.getsource(GeminiFhirFollowUp)
    assert "obs-from-transport" not in inspect.getsource(GeminiFhirFollowUp)


def test_request_shape_lists_the_tool_schema_and_message_order(monkeypatch):
    messages = [
        HumanMessage(content="Prepare follow-up for case SYN-FOLLOWUP-001."),
        _tool_call(),
        ToolMessage(
            content='{"patient": {"id": "SYN-PATIENT-001"}, "observations": [{"id": "obs-1"}]}',
            name=FOLLOWUP_TOOL,
            tool_call_id="call-1",
        ),
    ]
    assert describe_followup_contents(messages) == [
        {"role": "user", "parts": [{"kind": "text"}]},
        {
            "role": "model",
            "parts": [
                {
                    "kind": "function_call",
                    "name": FOLLOWUP_TOOL,
                    "arg_names": ["case_id"],
                    "has_id": True,
                }
            ],
        },
        {
            "role": "user",
            "parts": [
                {
                    "kind": "function_response",
                    "name": FOLLOWUP_TOOL,
                    "response_keys": ["observations", "patient"],
                    "has_id": True,
                }
            ],
        },
    ]
    declaration = followup_tool_schema()["function_declarations"][0]
    assert declaration["name"] == FOLLOWUP_TOOL
    assert declaration["parameters_json_schema"] == {
        "type": "object",
        "properties": {"case_id": {"type": "string"}},
        "required": ["case_id"],
    }
    monkeypatch.setenv("GEMINI_API_KEY", "secret-key-value")

    class ProviderError(Exception):
        code = 400
        status = "INVALID_ARGUMENT"
        message = "bad request"
        details = {"error": {"message": "bad request", "echo": "secret-key-value"}}

    diagnostic = gemini_error_diagnostics(ProviderError("400 INVALID_ARGUMENT. secret-key-value"))
    assert "ProviderError" in diagnostic
    assert "status=400" in diagnostic
    assert "INVALID_ARGUMENT" in diagnostic
    assert "bad request" in diagnostic
    assert "secret-key-value" not in diagnostic


def test_response_mapping_preserves_the_followup_tool_call():
    message = followup_message_from_response(_model_response())
    assert isinstance(message, AIMessage)
    assert message.tool_calls[0]["name"] == FOLLOWUP_TOOL
    assert message.tool_calls[0]["args"] == {"case_id": PATIENT_CASE}
    assert message.tool_calls[0]["id"] == "call-1"


THOUGHT_SIGNATURE = b"\x01synthetic-thought-signature"


class _SignedCall:
    name = FOLLOWUP_TOOL
    args = {"case_id": PATIENT_CASE}
    id = "call-1"


class _SignedPart:
    function_call = _SignedCall()
    text = None
    thought_signature = THOUGHT_SIGNATURE


class _SignedContent:
    parts = [_SignedPart()]


class _SignedCandidate:
    content = _SignedContent()


class _SignedResponse:
    candidates = [_SignedCandidate()]


def test_thought_signature_survives_the_second_request():
    message = followup_message_from_response(_SignedResponse())
    assert isinstance(message, AIMessage)
    call = message.tool_calls[0]
    assert call["name"] == FOLLOWUP_TOOL
    assert call["args"] == {"case_id": PATIENT_CASE}
    assert call["id"] == "call-1"
    assert message.additional_kwargs["thought_signatures"]["call-1"] is THOUGHT_SIGNATURE

    tool_result = ToolMessage(
        content='{"patient": {"id": "SYN-PATIENT-001"}, "observations": [{"id": "obs-1"}]}',
        name=FOLLOWUP_TOOL,
        tool_call_id="call-1",
    )
    contents = _contents(
        [
            HumanMessage(content="Prepare follow-up for case SYN-FOLLOWUP-001."),
            message,
            tool_result,
        ]
    )
    assert [content.role for content in contents] == ["user", "model", "user"]
    assert contents[0].parts[0].text

    function_part = contents[1].parts[0]
    assert function_part.function_call.name == FOLLOWUP_TOOL
    assert dict(function_part.function_call.args) == {"case_id": PATIENT_CASE}
    assert function_part.function_call.id == "call-1"
    assert function_part.thought_signature == THOUGHT_SIGNATURE
    assert isinstance(function_part.thought_signature, bytes)

    response_part = contents[2].parts[0]
    assert response_part.function_response.name == FOLLOWUP_TOOL
    assert response_part.function_response.id == "call-1"
    assert response_part.function_response.response["patient"]["id"] == PATIENT_ID
    assert response_part.thought_signature is None

    model = ScriptedModel([message, AIMessage(content=FINAL_TEXT)])
    client, http = _client(_ok("Name From Server", "obs-from-transport", "Value read from the server"))
    sink = InMemoryAuditSink()
    try:
        result = _workflow(client, model, sink).invoke(PATIENT_CASE)
    finally:
        http.close()
    kept = [
        item
        for item in result["messages"]
        if isinstance(item, AIMessage) and item.tool_calls
    ][0]
    assert kept.additional_kwargs["thought_signatures"]["call-1"] == THOUGHT_SIGNATURE
    blob = _audit_blob(sink)
    assert "synthetic-thought-signature" not in blob
    assert "thought_signature" not in blob
    assert set(asdict(sink.events[0]).keys()) == set(SAFE_AUDIT_FIELDS)


class _TextPart:
    def __init__(self, text: str) -> None:
        self.function_call = None
        self.text = text
        self.thought_signature = None


class _TextResponse:
    def __init__(self, text: str, parsed: object | None = None) -> None:
        self.parsed = parsed
        self.candidates = [type("Candidate", (), {"content": type("Content", (), {"parts": [_TextPart(text)]})()})()]


def test_structured_final_response_sets_follow_up_required_without_using_prose():
    raw = '{"answer": "Context received.", "follow_up_required": "true", "note": "follow-up is false"}'
    message = followup_message_from_response(_TextResponse(raw))
    assert message.content == "Context received."
    assert message.additional_kwargs["follow_up_required"] == "true"
    assert message.tool_calls == []
    assert "thought_signatures" not in message.additional_kwargs

    parsed = followup_message_from_response(
        _TextResponse("ignore this prose that says follow-up is true", {"answer": "No follow-up.", "follow_up_required": "false"})
    )
    assert parsed.content == "No follow-up."
    assert parsed.additional_kwargs["follow_up_required"] == "false"


def test_unstructured_text_does_not_set_follow_up_required():
    prose = "The text says follow-up is true because an observation exists."
    message = followup_message_from_response(_TextResponse(prose))
    assert message.content == prose
    assert "follow_up_required" not in message.additional_kwargs
    rejected = followup_message_from_response(
        _TextResponse('{"answer": "Context received.", "follow_up_required": "maybe"}')
    )
    assert "follow_up_required" not in rejected.additional_kwargs
    boolean = followup_message_from_response(
        _TextResponse('{"answer": "Context received.", "follow_up_required": true}')
    )
    assert "follow_up_required" not in boolean.additional_kwargs


def test_final_turn_asks_for_the_decision_object_and_the_read_turn_keeps_tools():
    from app.langgraph_gemini_fhir_followup import _followup_generate_config

    first = _followup_generate_config([HumanMessage(content="Prepare follow-up.")])
    first_dump = first.model_dump(exclude_none=True)
    assert first_dump["tools"]
    assert first.automatic_function_calling.disable is True
    assert "response_json_schema" not in first_dump
    second = _followup_generate_config(
        [
            HumanMessage(content="Prepare follow-up."),
            AIMessage(
                content="",
                tool_calls=[{"name": FOLLOWUP_TOOL, "args": {"case_id": PATIENT_CASE}, "id": "call-1", "type": "tool_call"}],
            ),
            ToolMessage(content="{}", name=FOLLOWUP_TOOL, tool_call_id="call-1"),
        ]
    )
    second_dump = second.model_dump(exclude_none=True)
    assert second_dump["response_mime_type"] == "application/json"
    assert "tools" not in second_dump
    assert second.automatic_function_calling.disable is True
    assert second_dump["automatic_function_calling"]["disable"] is True
    assert set(second_dump["response_json_schema"]["required"]) == {"answer", "follow_up_required"}
    assert second_dump["response_json_schema"]["properties"]["follow_up_required"]["enum"] == [
        "true",
        "false",
        "unknown",
    ]
    config_source = inspect.getsource(_followup_generate_config)
    assert config_source.count("AutomaticFunctionCallingConfig(disable=True)") == 2


def test_denied_send_message_never_reaches_the_tool_node():
    model = ScriptedModel(
        [
            _tool_call(
                "send_message",
                {"patient_id": PATIENT_ID, "body": "synthetic"},
            )
        ]
    )

    def fail_if_called(request: httpx.Request) -> httpx.Response:
        raise AssertionError(request.url)

    client, http = _client(fail_if_called)
    sink = InMemoryAuditSink()
    try:
        workflow = _workflow(client, model, sink)
        result = workflow.invoke()
    finally:
        http.close()
    assert result["final_answer"] == DENIAL_ANSWER
    assert result["decision"] == "denied"
    assert result["policy_decision"] == "denied"
    assert result["tools_used"] == []
    assert result["evidence"] == []
    assert result["observations"] == []
    assert result["patient"] is None
    assert client.calls == []
    assert workflow.model_calls == 1
    assert workflow.trace == ["prepare", "agent", "denied", "finish"]
    assert "update_state" not in workflow.trace
    assert sink.events[0].decision == "denied"
    assert sink.events[0].tool_name == "send_message"
    assert f"execute:send_message" not in BOUNDARY_EVENTS
    assert f"policy:send_message:denied" in BOUNDARY_EVENTS
    assert BOUNDARY_EVENTS.index("policy:send_message:denied") < BOUNDARY_EVENTS.index("audit:send_message:denied")


def test_model_turn_limit_does_not_request_another_tool():
    replies = [_tool_call(call_id=f"call-{index}") for index in range(1, MAX_MODEL_TURNS + 1)]
    replies.append(AIMessage(content="this reply must not be requested"))
    model = ScriptedModel(replies)
    client, http = _client(_ok("Name From Server", "obs-from-transport", "Value read from the server"))
    try:
        workflow = _workflow(client, model)
        result = workflow.invoke()
    finally:
        http.close()
    assert result["decision"] == "limit"
    assert result["final_answer"] == MODEL_LIMIT_ANSWER
    assert workflow.model_calls == MAX_MODEL_TURNS
    assert BOUNDARY_EVENTS.count(f"execute:{FOLLOWUP_TOOL}") == MAX_MODEL_TURNS
    assert model.replies[0].content == "this reply must not be requested"
    started = initial_state(PATIENT_CASE)
    started["messages"] = [AIMessage(content=f"turn {index}") for index in range(MAX_MODEL_TURNS)]
    blocked = _workflow(client, ScriptedModel([_tool_call()]))
    update = blocked.agent_node(started)
    assert update["decision"] == "limit"
    assert blocked.model_calls == 0
    merged = {**started, **update}
    assert blocked.route_after_agent(merged) == "finish"
    assert blocked.sink.events == []


def test_fhir_client_error_does_not_invent_evidence():
    def missing(request: httpx.Request) -> httpx.Response:
        return httpx.Response(404, json={"resourceType": "OperationOutcome"})

    model = ScriptedModel([_tool_call(), AIMessage(content=FINAL_TEXT)])
    client, http = _client(missing)
    sink = InMemoryAuditSink()
    try:
        result = _workflow(client, model, sink).invoke()
    finally:
        http.close()
    assert result["decision"] == "unavailable"
    assert result["final_answer"] == UNAVAILABLE_ANSWER
    assert result["patient"] is None
    assert result["observations"] == []
    assert result["evidence"] == []
    assert result["tools_used"] == []
    assert model.seen and len(model.seen) == 1
    assert sink.events[0].decision == "allowed"
    assert "obs-from-transport" not in _audit_blob(sink)
    assert "Name From Server" not in result["final_answer"]


def test_provider_unavailable_is_not_a_tool_call():
    def unavailable(messages):
        raise RuntimeError("gemini follow-up request failed status=503")

    def fail_if_called(request: httpx.Request) -> httpx.Response:
        raise AssertionError(request.url)

    client, http = _client(fail_if_called)
    sink = InMemoryAuditSink()
    try:
        workflow = _workflow(client, unavailable, sink)
        with pytest.raises(RuntimeError, match="status=503"):
            workflow.invoke()
    finally:
        http.close()
    assert client.calls == []
    assert sink.events == []
    assert workflow.model_calls == 1


def test_boundaries_stay_outside_the_graph_and_c15():
    source = inspect.getsource(GeminiFhirFollowUp)
    assert "httpx" not in source
    assert "HapiReadClient" not in source
    assert 'add_node("policy"' not in source
    assert 'add_node("audit"' not in source
    route = inspect.getsource(GeminiFhirFollowUp.route_after_agent)
    assert route.index("self.policy") < route.index("self.audit")
    assert route.index("self.audit") < route.index('return "tools"')
    tool_source = inspect.getsource(make_followup_tool)
    for token in ("httpx", "HapiReadClient", "evaluate_tool_policy", "record_policy_audit", "gemini"):
        assert token not in tool_source
    module = inspect.getsource(build_gemini_fhir_followup) + source
    for token in ("followup_runtime", "followup_prompt", "followup_trace", "gemini_provider", "llm_provider"):
        assert token not in module
    assert "automatic_function_calling" in gemini_request_source()
    assert "AutomaticFunctionCallingConfig(disable=True)" in gemini_request_source()
    client, http = _client(_ok("Name From Server", "obs-from-transport", "Value read from the server"))
    try:
        workflow = _workflow(client, ScriptedModel([_tool_call(), AIMessage(content=FINAL_TEXT)]))
        drawing = workflow.graph.get_graph()
        assert isinstance(workflow.graph.nodes["tools"].bound, ToolNode)
    finally:
        http.close()
    assert "policy" not in set(drawing.nodes)
    assert "audit" not in set(drawing.nodes)
    edges = {(edge.source, edge.target) for edge in drawing.edges}
    assert (START, "prepare") in edges or ("__start__", "prepare") in edges
    assert ("prepare", "agent") in edges
    assert ("agent", "tools") in edges
    assert ("tools", "update_state") in edges
    assert ("update_state", "agent") in edges
    assert ("agent", "denied") in edges
    assert ("denied", "finish") in edges
    assert ("finish", END) in edges or ("finish", "__end__") in edges


def gemini_request_source() -> str:
    from app import langgraph_gemini_fhir_followup as lesson

    return inspect.getsource(lesson.gemini_followup_message) + inspect.getsource(
        lesson._followup_generate_config
    )


class _Call:
    name = FOLLOWUP_TOOL
    args = {"case_id": PATIENT_CASE}
    id = "call-1"


class _Part:
    function_call = _Call()
    text = None


class _Content:
    parts = [_Part()]


class _Candidate:
    content = _Content()


class _Response:
    candidates = [_Candidate()]


def _model_response() -> _Response:
    return _Response()


def _store(base: str, path: str, body: dict) -> None:
    response = httpx.put(
        f"{base}/{path}",
        json=body,
        headers={"Accept": "application/fhir+json", "Content-Type": "application/fhir+json"},
        timeout=5.0,
    )
    if response.status_code not in {200, 201}:
        raise AssertionError(f"seed failed with HTTP {response.status_code}")


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
        _store(
            base,
            PATIENT_PATH,
            {
                "resourceType": "Patient",
                "id": PATIENT_ID,
                "active": True,
                "identifier": [{"system": CASE_IDENTIFIER_SYSTEM, "value": PATIENT_CASE}],
                "name": [{"text": "Synthetic Patient"}],
            },
        )
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


@pytest.mark.skipif(not _hapi_enabled(), reason="set RUN_HAPI_INTEGRATION_TESTS=true to call the local server")
def test_scripted_model_reads_real_hapi_records():
    base = hapi_base_url()
    stored_patient, stored_observation = _ensure_records(base)
    clear_boundary_events()
    model = ScriptedModel([_tool_call(), AIMessage(content=FINAL_TEXT)])
    client = HapiReadClient(base)
    sink = InMemoryAuditSink()
    result = _workflow(client, model, sink).invoke()
    assert result["final_answer"] == FINAL_TEXT
    assert result["patient"]["id"] == stored_patient["id"] == PATIENT_ID
    assert result["patient"]["name"] == stored_patient["name"][0]["text"]
    found = next(item for item in result["observations"] if item.get("id") == stored_observation["id"])
    assert found["id"] == "obs-synthetic-001"
    assert found["valueString"] == stored_observation["valueString"]
    refs = result["evidence"][0]["resources"]
    assert refs[0] == f"Patient/{stored_patient['id']}"
    assert f"Observation/{stored_observation['id']}" in refs
    assert result["tools_used"] == [FOLLOWUP_TOOL]
    assert client.calls == CASE_READS
    assert stored_patient["name"][0]["text"] not in _audit_blob(sink)
    assert stored_observation.get("valueString", "missing-value") not in _audit_blob(sink)


@pytest.mark.skipif(
    not (_live_gemini() and _hapi_enabled()),
    reason="set RUN_LIVE_GEMINI_TESTS=true and RUN_HAPI_INTEGRATION_TESTS=true",
)
def test_live_gemini_reads_hapi_before_the_final_answer():
    if not os.getenv("GEMINI_API_KEY", "").strip():
        pytest.skip("GEMINI_API_KEY is required for live Gemini tests")
    base = hapi_base_url()
    stored_patient, stored_observation = _ensure_records(base)
    clear_boundary_events()
    sink = InMemoryAuditSink()
    workflow = build_live_gemini_fhir_followup(sink, clock=_clock, run_id="run-live-gemini-001", base_url=base)
    result = workflow.invoke()
    assert workflow.model_calls >= 2
    assert workflow.model_calls <= MAX_MODEL_TURNS
    assert result["tools_used"]
    assert all(name == FOLLOWUP_TOOL for name in result["tools_used"])
    assert result["patient"]["id"] == stored_patient["id"]
    assert result["patient"]["name"] == stored_patient["name"][0]["text"]
    found = next(item for item in result["observations"] if item.get("id") == stored_observation["id"])
    assert found["valueString"] == stored_observation["valueString"]
    assert f"Observation/{stored_observation['id']}" in result["evidence"][0]["resources"]
    assert result["final_answer"]
    assert result["decision"] == "finish"
    last = result["messages"][-1]
    assert isinstance(last, AIMessage)
    assert not last.tool_calls
    assert PATIENT_PATH in workflow.adapter.transport.calls or PATIENT_PATH in _client_calls(workflow)
    secret = os.getenv("GEMINI_API_KEY", "").strip()
    blob = _audit_blob(sink)
    assert secret not in blob
    assert secret not in str(result["final_answer"])
    assert stored_observation.get("valueString", "missing-value") not in blob
    assert BOUNDARY_EVENTS.index(f"policy:{FOLLOWUP_TOOL}:allowed") < BOUNDARY_EVENTS.index(
        f"audit:{FOLLOWUP_TOOL}:allowed"
    )
    assert BOUNDARY_EVENTS.index(f"audit:{FOLLOWUP_TOOL}:allowed") < BOUNDARY_EVENTS.index(
        f"execute:{FOLLOWUP_TOOL}"
    )


def _client_calls(workflow: GeminiFhirFollowUp) -> list[str]:
    transport = workflow.adapter.transport
    return list(getattr(transport, "calls", []))
