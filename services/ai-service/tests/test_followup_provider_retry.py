"""Provider retry is separate from output recovery. No network calls."""

from __future__ import annotations

import json

from app.fake_llm_provider import FakeLLMProvider
from app.followup_models import FollowUpStatus
from app.followup_runtime import FollowUpRuntime, provider_failure_is_retryable
from app.followup_trace import AgentEventType
from app.llm_provider import ProviderGeneration


CASE = "SYN-FOLLOWUP-001"
FORBIDDEN_METADATA = {"prompt", "completion", "text", "api_key", "token", "data", "arguments", "output"}


def _tool_call(tool: str) -> dict:
    return {"type": "tool_call", "tool": tool, "arguments": {"caseId": CASE}}


def _final(*, evidence=None) -> dict:
    return {
        "type": "final",
        "output": {
            "followUpRequired": "true",
            "summary": "Synthetic follow-up summary.",
            "reason": "Synthetic reason.",
            "suggestedActions": [{"type": "consider-follow-up", "detail": "Synthetic detail."}],
            "evidence": evidence or [],
            "requiresHumanReview": True,
        },
    }


def _failure(error: str, status_code: int | None = None) -> ProviderGeneration:
    return ProviderGeneration(invocation_started=True, error=error, status_code=status_code)


def _runtime(provider: FakeLLMProvider) -> FollowUpRuntime:
    return FollowUpRuntime(provider, sleeper=lambda _delay: None, jitter=lambda: 0.0)


def _types(runtime: FollowUpRuntime) -> list[str]:
    return [event.type.value for event in runtime.trace]


def test_503_then_valid_response_continues():
    provider = FakeLLMProvider(script=[_failure("http_5xx", 503), _final()])
    runtime = _runtime(provider)
    response = runtime.run(CASE)
    assert response.status == FollowUpStatus.COMPLETED
    assert response.status != FollowUpStatus.PROVIDER_ERROR
    assert provider.calls == 2
    assert runtime.provider_retries == 1
    assert runtime.recovery_attempts == 0
    assert runtime.tool_executions == []
    assert "LLM_RETRY_REQUESTED" in _types(runtime)
    assert "RECOVERY_REQUESTED" not in _types(runtime)


def test_503_exhausts_the_single_retry():
    unused = _final()
    provider = FakeLLMProvider(script=[_failure("http_5xx", 503), _failure("http_5xx", 503), unused])
    runtime = _runtime(provider)
    response = runtime.run(CASE)
    assert response.status == FollowUpStatus.PROVIDER_ERROR
    assert response.reason == "provider error"
    assert provider.calls == 2
    assert runtime.provider_retries == 1
    assert provider._turns == [unused]
    assert _types(runtime).count("LLM_RETRY_REQUESTED") == 1
    assert "RECOVERY_REQUESTED" not in _types(runtime)


def test_429_is_retryable():
    provider = FakeLLMProvider(script=[_failure("http_4xx", 429), _final()])
    runtime = _runtime(provider)
    response = runtime.run(CASE)
    assert response.status == FollowUpStatus.COMPLETED
    assert provider.calls == 2
    error = next(event for event in runtime.trace if event.type == AgentEventType.LLM_PROVIDER_ERROR)
    assert error.metadata["retryable"] is True
    assert error.metadata["statusCode"] == 429


def test_401_is_not_retried():
    provider = FakeLLMProvider(script=[_failure("http_4xx", 401), _final()])
    runtime = _runtime(provider)
    response = runtime.run(CASE)
    assert response.status == FollowUpStatus.PROVIDER_ERROR
    assert provider.calls == 1
    assert runtime.provider_retries == 0
    assert "LLM_RETRY_REQUESTED" not in _types(runtime)
    assert provider._turns == [_final()]


def test_400_is_not_retried():
    provider = FakeLLMProvider(script=[_failure("http_4xx", 400), _final()])
    runtime = _runtime(provider)
    response = runtime.run(CASE)
    assert response.status == FollowUpStatus.PROVIDER_ERROR
    assert provider.calls == 1
    assert "LLM_RETRY_REQUESTED" not in _types(runtime)


def test_timeout_is_retryable():
    provider = FakeLLMProvider(script=[_failure("timeout"), _final()])
    runtime = _runtime(provider)
    response = runtime.run(CASE)
    assert response.status == FollowUpStatus.COMPLETED
    assert provider.calls == 2
    error = next(event for event in runtime.trace if event.type == AgentEventType.LLM_PROVIDER_ERROR)
    assert error.metadata["category"] == "timeout"
    assert error.metadata["retryable"] is True


def test_provider_retry_after_tools_does_not_rerun_tools():
    provider = FakeLLMProvider(
        script=[
            _tool_call("get_patient"),
            _failure("http_5xx", 503),
            _final(evidence=[{"tool": "get_patient", "id": "SYN-PAT-001"}]),
        ]
    )
    runtime = _runtime(provider)
    response = runtime.run(CASE)
    assert response.status == FollowUpStatus.COMPLETED
    assert runtime.tool_executions == ["get_patient"]
    assert _types(runtime).count("TOOL_EXECUTED") == 1
    assert provider.calls == 3
    assert runtime.provider_retries == 1
    assert runtime.observed_results[0]["data"]["id"] == "SYN-PAT-001"


def test_retry_trace_records_provider_error_then_retry():
    provider = FakeLLMProvider(script=[_failure("http_5xx", 503), _final()])
    runtime = _runtime(provider)
    runtime.run(CASE)
    kinds = _types(runtime)
    assert kinds == [
        "RUN_STARTED",
        "LLM_REQUEST",
        "LLM_RESPONSE",
        "LLM_PROVIDER_ERROR",
        "LLM_RETRY_REQUESTED",
        "LLM_REQUEST",
        "LLM_RESPONSE",
        "FINAL_RECEIVED",
        "RUN_COMPLETED",
    ]
    sequences = [event.sequence for event in runtime.trace]
    assert sequences == list(range(1, len(runtime.trace) + 1))
    assert len({event.run_id for event in runtime.trace}) == 1
    assert all(event.timestamp is not None for event in runtime.trace)
    error = next(event for event in runtime.trace if event.type == AgentEventType.LLM_PROVIDER_ERROR)
    assert error.metadata["category"] == "http_5xx"
    assert error.metadata["retryable"] is True
    assert error.metadata["attempt"] == 1
    assert error.metadata["provider"] == "FakeLLMProvider"
    assert error.metadata["statusCode"] == 503
    blob = json.dumps([event.metadata for event in runtime.trace])
    assert not any(key in blob for key in FORBIDDEN_METADATA)


def test_classifier_keeps_non_transient_errors_from_retry():
    assert provider_failure_is_retryable(_failure("http_4xx", 400)) is False
    assert provider_failure_is_retryable(_failure("http_4xx", 401)) is False
    assert provider_failure_is_retryable(_failure("http_4xx", 403)) is False
    assert provider_failure_is_retryable(_failure("http_4xx", 418)) is False
    assert provider_failure_is_retryable(_failure("http_4xx")) is False
    assert provider_failure_is_retryable(_failure("http_4xx", 429)) is True
    assert provider_failure_is_retryable(_failure("http_5xx", 503)) is True
    assert provider_failure_is_retryable(_failure("http_5xx", 500)) is True
    assert provider_failure_is_retryable(_failure("http_5xx")) is True
    assert provider_failure_is_retryable(_failure("timeout")) is True
    assert provider_failure_is_retryable(_failure("malformed")) is False
    assert provider_failure_is_retryable(_failure("empty")) is False
