from __future__ import annotations

import json

from fastapi.testclient import TestClient

from app.config import Settings
from app.fake_llm_provider import FakeLLMProvider
from app.followup_runtime import FollowUpRuntime
from app.followup_trace import AgentEventType
from app.main import app, get_settings


CASE = "SYN-FOLLOWUP-001"


def _tool_call(tool: str) -> dict:
    return {"type": "tool_call", "tool": tool, "arguments": {"caseId": CASE}}


def _final(*, evidence=None) -> dict:
    return {
        "type": "final",
        "output": {
            "followUpRequired": "true",
            "summary": "Synthetic follow-up summary.",
            "reason": "Synthetic reason.",
            "suggestedActions": [{"type": "review", "detail": "Synthetic review"}],
            "evidence": evidence or [],
            "requiresHumanReview": True,
        },
    }


def _runtime(script, monotonic=None) -> FollowUpRuntime:
    provider = FakeLLMProvider(script=script)
    if monotonic is None:
        return FollowUpRuntime(provider)
    return FollowUpRuntime(provider, monotonic=monotonic)


def _types(runtime: FollowUpRuntime) -> list[str]:
    return [event.type.value for event in runtime.trace]


class SequenceClock:
    def __init__(self, values: list[float]) -> None:
        self.values = list(values)
        self.index = 0

    def __call__(self) -> float:
        value = self.values[min(self.index, len(self.values) - 1)]
        self.index += 1
        return value


def test_immediate_final_trace():
    runtime = _runtime([_final()])
    response = runtime.run(CASE)
    assert _types(runtime) == [
        "RUN_STARTED",
        "LLM_REQUEST",
        "LLM_RESPONSE",
        "FINAL_RECEIVED",
        "RUN_COMPLETED",
    ]
    assert response.run_id == runtime.run_id
    assert {event.run_id for event in runtime.trace} == {runtime.run_id}
    assert runtime.llm_turns == 1


def test_one_tool_then_final_trace_order():
    runtime = _runtime(
        [
            _tool_call("get_patient"),
            _final(evidence=[{"tool": "get_patient", "id": "SYN-PAT-001"}]),
        ]
    )
    runtime.run(CASE)
    assert _types(runtime) == [
        "RUN_STARTED",
        "LLM_REQUEST",
        "LLM_RESPONSE",
        "TOOL_REQUESTED",
        "POLICY_CHECK",
        "TOOL_EXECUTED",
        "LLM_REQUEST",
        "LLM_RESPONSE",
        "FINAL_RECEIVED",
        "RUN_COMPLETED",
    ]
    assert runtime.llm_turns == 2
    executed = next(event for event in runtime.trace if event.type == AgentEventType.TOOL_EXECUTED)
    assert executed.metadata["registryLookup"] is True
    assert "data" not in executed.metadata


def test_denied_tool_does_not_record_execution():
    runtime = _runtime([_tool_call("send_message")])
    response = runtime.run(CASE)
    assert response.status.value == "POLICY_DENIED"
    kinds = _types(runtime)
    assert kinds.index("TOOL_REQUESTED") < kinds.index("POLICY_CHECK") < kinds.index("TOOL_DENIED")
    assert "TOOL_EXECUTED" not in kinds
    denied = next(event for event in runtime.trace if event.type == AgentEventType.TOOL_DENIED)
    assert denied.metadata["registryLookup"] is False
    assert runtime.tool_executions == []


def test_invalid_json_trace_fails_without_storing_completion():
    runtime = _runtime(["not-json"])
    runtime.run(CASE)
    kinds = _types(runtime)
    assert kinds.index("LLM_REQUEST") < kinds.index("LLM_RESPONSE") < kinds.index("RUN_FAILED")
    assert "not-json" not in json.dumps([event.metadata for event in runtime.trace])


def test_provider_error_trace():
    runtime = FollowUpRuntime(FakeLLMProvider("http_5xx"), sleeper=lambda _delay: None, jitter=lambda: 0.0)
    response = runtime.run(CASE)
    assert response.status.value == "PROVIDER_ERROR"
    kinds = _types(runtime)
    assert kinds.index("LLM_REQUEST") < kinds.index("LLM_RESPONSE") < kinds.index("RUN_FAILED")
    response_event = next(event for event in runtime.trace if event.type == AgentEventType.LLM_RESPONSE)
    assert response_event.metadata["success"] is False
    assert runtime.llm_turns == 2
    assert kinds.count("LLM_RETRY_REQUESTED") == 1


def test_timeout_trace_keeps_policy_denied():
    runtime = _runtime([_final()], monotonic=SequenceClock([0.0, 31.0]))
    response = runtime.run(CASE)
    assert response.status.value == "POLICY_DENIED"
    assert response.reason == "timeout"
    assert "RUN_TIMEOUT" in _types(runtime)
    assert runtime.llm_turns == 0


def test_multiple_tools_have_one_run_and_contiguous_sequences():
    runtime = _runtime(
        [
            _tool_call("get_upcoming_appointments"),
            _tool_call("get_recent_encounters"),
            _final(
                evidence=[
                    {"tool": "get_upcoming_appointments", "id": "SYN-APT-001"},
                    {"tool": "get_recent_encounters", "id": "SYN-ENC-001"},
                ]
            ),
        ]
    )
    response = runtime.run(CASE)
    assert [event.sequence for event in runtime.trace] == list(range(1, len(runtime.trace) + 1))
    assert {event.run_id for event in runtime.trace} == {response.run_id}
    assert _types(runtime).count("TOOL_EXECUTED") == 2
    assert runtime.llm_turns == 3


def test_trace_omits_prompts_completions_tokens_and_tool_payloads():
    runtime = _runtime(
        [
            _tool_call("get_patient"),
            _final(evidence=[{"tool": "get_patient", "id": "SYN-PAT-001"}]),
        ]
    )
    runtime.run(CASE)
    blob = json.dumps(
        [
            {"type": event.type.value, "metadata": event.metadata}
            for event in runtime.trace
        ]
    )
    assert "Do not diagnose" not in blob
    assert "Synthetic follow-up summary." not in blob
    assert "Synthetic patient A" not in blob
    assert "test-model-boundary-token" not in blob
    assert "prompt" not in blob
    assert "completion" not in blob


def test_http_response_does_not_include_the_trace():
    import app.main as main

    original = main.get_llm_provider
    settings = Settings(
        model_boundary_base_url="http://model-boundary.test",
        model_boundary_path="/api/model-boundary/v1",
        model_boundary_timeout_seconds=5,
        model_boundary_service_token="test-model-boundary-token",
        host="127.0.0.1",
        port=8090,
        followup_agent_enabled=True,
    )
    app.dependency_overrides[get_settings] = lambda: settings
    main.get_llm_provider = lambda settings=None: FakeLLMProvider(script=[_final()])
    try:
        response = TestClient(app).post(
            "/internal/agent/follow-up",
            json={"caseId": CASE},
            headers={"X-Service-Token": "test-model-boundary-token"},
        )
        assert response.status_code == 200
        assert "trace" not in response.json()
        assert "events" not in response.json()
    finally:
        app.dependency_overrides.clear()
        main.get_llm_provider = original
