from __future__ import annotations

import json

from app.fake_llm_provider import FakeLLMProvider
from app.followup_models import FollowUpStatus
from app.followup_runtime import MAX_RECOVERY_ATTEMPTS, FollowUpRuntime
from app.followup_trace import AgentEventType
from app.llm_provider import ProviderGeneration

CASE = "SYN-FOLLOWUP-001"


def _tool_call(tool: str = "get_patient") -> dict:
    return {"type": "tool_call", "tool": tool, "arguments": {"caseId": CASE}}


def _final(**overrides) -> dict:
    output = {
        "followUpRequired": "unknown",
        "summary": "Synthetic laboratory summary.",
        "reason": "Synthetic laboratory reason.",
        "suggestedActions": [{"type": "none", "detail": "Synthetic detail."}],
        "evidence": [],
    }
    output.update(overrides)
    return {"type": "final", "output": output}


def _run(script, monotonic=None) -> tuple[FollowUpRuntime, object]:
    provider = FakeLLMProvider(script=script)
    runtime = FollowUpRuntime(provider) if monotonic is None else FollowUpRuntime(provider, monotonic=monotonic)
    response = runtime.run(CASE)
    return runtime, response


def _types(runtime: FollowUpRuntime) -> list[str]:
    return [event.type.value for event in runtime.trace]


class SequenceClock:
    def __init__(self, values: list[float]) -> None:
        self.values = list(values)
        self.i = 0

    def __call__(self) -> float:
        value = self.values[min(self.i, len(self.values) - 1)]
        self.i += 1
        return value


def test_invalid_json_then_final_completes():
    runtime, response = _run(["not-json", _final()])
    assert response.status == FollowUpStatus.COMPLETED
    assert response.requires_human_review is True
    assert runtime.recovery_attempts == 1
    assert runtime.provider.calls == 2
    assert "previous_response_invalid_json" in runtime.provider.prompts[1]
    assert "not-json" not in runtime.provider.prompts[1]
    assert _types(runtime) == [
        "RUN_STARTED",
        "LLM_REQUEST",
        "LLM_RESPONSE",
        "RECOVERY_REQUESTED",
        "LLM_REQUEST",
        "LLM_RESPONSE",
        "FINAL_RECEIVED",
        "RUN_COMPLETED",
    ]


def test_two_invalid_json_responses_stop():
    runtime, response = _run(["not-json", "still-not-json", "unused"])
    assert response.status == FollowUpStatus.VALIDATION_ERROR
    assert response.reason == "invalid json"
    assert runtime.recovery_attempts == MAX_RECOVERY_ATTEMPTS == 1
    assert runtime.provider.calls == 2
    assert _types(runtime).count("RECOVERY_REQUESTED") == 1
    assert _types(runtime)[-1] == "RUN_FAILED"


def test_markdown_fence_then_raw_json_completes():
    fenced = "```json\n" + json.dumps(_final()) + "\n```"
    runtime, response = _run([fenced, _final()])
    assert response.status == FollowUpStatus.COMPLETED
    assert runtime.provider.calls == 2
    assert "```" not in json.dumps([event.metadata for event in runtime.trace])


def test_invalid_final_then_valid_final_completes():
    runtime, response = _run([_final(followUpRequired="maybe"), _final()])
    assert response.status == FollowUpStatus.COMPLETED
    assert runtime.recovery_attempts == 1
    assert _types(runtime).count("FINAL_RECEIVED") == 2
    assert _types(runtime)[-1] == "RUN_COMPLETED"


def test_send_message_is_not_recovered():
    runtime, response = _run([_tool_call("send_message"), _final()])
    assert response.status == FollowUpStatus.POLICY_DENIED
    assert runtime.provider.calls == 1
    assert runtime.recovery_attempts == 0
    assert "RECOVERY_REQUESTED" not in _types(runtime)


def test_provider_error_is_not_recovered():
    runtime = FollowUpRuntime(FakeLLMProvider(mode="http_5xx"), sleeper=lambda _delay: None, jitter=lambda: 0.0)
    response = runtime.run(CASE)
    assert response.status == FollowUpStatus.PROVIDER_ERROR
    assert runtime.provider.calls == 2
    assert runtime.recovery_attempts == 0
    assert "RECOVERY_REQUESTED" not in _types(runtime)
    assert "LLM_RETRY_REQUESTED" in _types(runtime)


def test_unknown_tool_is_not_recovered():
    runtime, response = _run([_tool_call("unknown_tool"), _final()])
    assert response.status == FollowUpStatus.POLICY_DENIED
    assert runtime.provider.calls == 1
    assert "TOOL_EXECUTED" not in _types(runtime)
    assert "RECOVERY_REQUESTED" not in _types(runtime)


def test_recovery_after_a_tool_keeps_the_observed_result():
    runtime, response = _run(
        [
            _tool_call("get_patient"),
            "not-json",
            _final(
                followUpRequired="true",
                suggestedActions=[{"type": "consider-follow-up", "detail": "Synthetic detail."}],
                evidence=[{"tool": "get_patient", "id": "SYN-PAT-001"}],
            ),
        ]
    )
    assert response.status == FollowUpStatus.COMPLETED
    assert runtime.tool_executions == ["get_patient"]
    assert runtime.observed_results[0]["data"]["id"] == "SYN-PAT-001"
    assert response.evidence[0].id == "SYN-PAT-001"
    assert runtime.recovery_attempts == 1
    assert "SYN-PAT-001" in runtime.provider.prompts[2]
    assert "not-json" not in runtime.provider.prompts[2]
    blob = json.dumps([event.metadata for event in runtime.trace])
    assert "not-json" not in blob
    assert "SYN-PAT-001" not in blob
    assert _types(runtime).count("RECOVERY_REQUESTED") == 1
    assert _types(runtime).count("TOOL_EXECUTED") == 1


def test_timeout_does_not_start_a_recovery_call():
    runtime, response = _run(["not-json", _final()], monotonic=SequenceClock([0.0] * 6 + [31.0]))
    assert response.status == FollowUpStatus.POLICY_DENIED
    assert response.reason == "timeout"
    assert runtime.provider.calls == 1
    assert AgentEventType.RECOVERY_REQUESTED.value in _types(runtime)
    assert AgentEventType.RUN_TIMEOUT.value in _types(runtime)
    assert _types(runtime).count("LLM_REQUEST") == 1


def test_invented_evidence_is_not_recovered():
    runtime, response = _run(
        [
            _tool_call("get_patient"),
            _final(evidence=[{"tool": "get_patient", "id": "SYN-PAT-999"}]),
            _final(evidence=[{"tool": "get_patient", "id": "SYN-PAT-001"}]),
        ]
    )
    assert response.status == FollowUpStatus.VALIDATION_ERROR
    assert runtime.provider.calls == 2
    assert runtime.recovery_attempts == 0
    assert "RECOVERY_REQUESTED" not in _types(runtime)


def test_recovery_trace_stores_only_the_category():
    runtime, _response = _run([ProviderGeneration(invocation_started=True, text="not-json"), _final()])
    event = next(item for item in runtime.trace if item.type == AgentEventType.RECOVERY_REQUESTED)
    assert event.metadata == {"category": "previous_response_invalid_json", "attempt": 1}
    assert event.run_id == runtime.run_id
