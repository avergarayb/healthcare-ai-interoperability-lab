"""Bounded provider backoff. Sleep and jitter are injected. No network calls."""

from __future__ import annotations

import json

from app.fake_llm_provider import FakeLLMProvider
from app.followup_models import FollowUpStatus
from app.followup_runtime import (
    BASE_BACKOFF_SECONDS,
    JITTER_MAX_SECONDS,
    MAX_BACKOFF_SECONDS,
    FollowUpRuntime,
    calculate_provider_backoff,
)
from app.followup_trace import AgentEventType
from app.llm_provider import ProviderGeneration


CASE = "SYN-FOLLOWUP-001"
FORBIDDEN_METADATA = {"prompt", "completion", "text", "api_key", "token", "data", "arguments", "output"}


class RecordingSleeper:
    def __init__(self) -> None:
        self.delays: list[float] = []

    def __call__(self, delay: float) -> None:
        self.delays.append(delay)


def _final() -> dict:
    return {
        "type": "final",
        "output": {
            "followUpRequired": "true",
            "summary": "Synthetic follow-up summary.",
            "reason": "Synthetic reason.",
            "suggestedActions": [{"type": "consider-follow-up", "detail": "Synthetic detail."}],
            "evidence": [],
            "requiresHumanReview": True,
        },
    }


def _failure(error: str, status_code: int | None = None) -> ProviderGeneration:
    return ProviderGeneration(invocation_started=True, error=error, status_code=status_code)


def _runtime(script: list, jitter: float) -> tuple[FollowUpRuntime, RecordingSleeper]:
    sleeper = RecordingSleeper()
    runtime = FollowUpRuntime(
        FakeLLMProvider(script=script),
        sleeper=sleeper,
        jitter=lambda: jitter,
    )
    return runtime, sleeper


def _retry_event(runtime: FollowUpRuntime):
    return next(event for event in runtime.trace if event.type == AgentEventType.LLM_RETRY_REQUESTED)


def test_first_retry_delay_is_at_least_the_base():
    delay = calculate_provider_backoff(1, 0.0)
    assert delay >= BASE_BACKOFF_SECONDS
    assert delay == BASE_BACKOFF_SECONDS


def test_jitter_is_bounded():
    assert calculate_provider_backoff(1, JITTER_MAX_SECONDS) - BASE_BACKOFF_SECONDS == JITTER_MAX_SECONDS
    assert calculate_provider_backoff(1, JITTER_MAX_SECONDS + 5) - BASE_BACKOFF_SECONDS == JITTER_MAX_SECONDS
    assert calculate_provider_backoff(1, -1.0) == BASE_BACKOFF_SECONDS


def test_delay_never_exceeds_cap_plus_jitter():
    delay = calculate_provider_backoff(8, 10.0)
    assert delay == MAX_BACKOFF_SECONDS + JITTER_MAX_SECONDS
    assert delay <= MAX_BACKOFF_SECONDS + JITTER_MAX_SECONDS


def test_controlled_jitter_changes_the_delay():
    low = calculate_provider_backoff(1, 0.0)
    high = calculate_provider_backoff(1, 0.25)
    assert low == 1.0
    assert high == 1.25
    assert low < high
    assert high - low <= JITTER_MAX_SECONDS


def test_attempt_numbering():
    assert calculate_provider_backoff(1, 0.0) == 1.0
    assert calculate_provider_backoff(2, 0.0) == 2.0
    assert calculate_provider_backoff(3, 0.0) == 4.0
    assert calculate_provider_backoff(4, 0.0) == 4.0


def test_503_backoff_then_retry_succeeds():
    runtime, sleeper = _runtime([_failure("http_5xx", 503), _final()], 0.25)
    response = runtime.run(CASE)
    assert response.status == FollowUpStatus.COMPLETED
    assert sleeper.delays == [1.25]
    assert runtime.provider_retries == 1
    assert runtime.provider.calls == 2
    assert runtime.tool_executions == []


def test_503_backoff_then_second_503_is_provider_error():
    runtime, sleeper = _runtime([_failure("http_5xx", 503), _failure("http_5xx", 503), _final()], 0.0)
    response = runtime.run(CASE)
    assert response.status == FollowUpStatus.PROVIDER_ERROR
    assert sleeper.delays == [BASE_BACKOFF_SECONDS]
    assert runtime.provider.calls == 2
    assert _retry_count(runtime) == 1


def _retry_count(runtime: FollowUpRuntime) -> int:
    return sum(event.type == AgentEventType.LLM_RETRY_REQUESTED for event in runtime.trace)


def test_429_waits_before_retry():
    runtime, sleeper = _runtime([_failure("http_4xx", 429), _final()], 0.0)
    response = runtime.run(CASE)
    assert response.status == FollowUpStatus.COMPLETED
    assert sleeper.delays == [BASE_BACKOFF_SECONDS]
    assert _retry_event(runtime).metadata["statusCode"] == 429


def test_timeout_waits_before_retry():
    runtime, sleeper = _runtime([_failure("timeout"), _final()], 0.0)
    response = runtime.run(CASE)
    assert response.status == FollowUpStatus.COMPLETED
    assert sleeper.delays == [BASE_BACKOFF_SECONDS]
    assert _retry_event(runtime).metadata["category"] == "timeout"
    assert "statusCode" not in _retry_event(runtime).metadata


def test_400_does_not_wait():
    runtime, sleeper = _runtime([_failure("http_4xx", 400), _final()], 0.0)
    response = runtime.run(CASE)
    assert response.status == FollowUpStatus.PROVIDER_ERROR
    assert sleeper.delays == []
    assert runtime.provider.calls == 1
    assert _retry_count(runtime) == 0


def test_malformed_does_not_wait():
    runtime, sleeper = _runtime([_failure("malformed"), _final()], 0.0)
    response = runtime.run(CASE)
    assert response.status == FollowUpStatus.PROVIDER_ERROR
    assert sleeper.delays == []
    assert runtime.provider.calls == 1


def test_empty_does_not_wait():
    runtime, sleeper = _runtime([_failure("empty"), _final()], 0.0)
    response = runtime.run(CASE)
    assert response.status == FollowUpStatus.PROVIDER_ERROR
    assert sleeper.delays == []
    assert runtime.provider.calls == 1


def test_retry_trace_records_bounded_backoff_on_the_same_run():
    runtime, sleeper = _runtime(
        [
            {"type": "tool_call", "tool": "get_patient", "arguments": {"caseId": CASE}},
            _failure("http_5xx", 503),
            {
                "type": "final",
                "output": {
                    "followUpRequired": "true",
                    "summary": "Synthetic follow-up summary.",
                    "reason": "Synthetic reason.",
                    "suggestedActions": [{"type": "consider-follow-up", "detail": "Synthetic detail."}],
                    "evidence": [{"tool": "get_patient", "id": "SYN-PAT-001"}],
                    "requiresHumanReview": True,
                },
            },
        ],
        0.25,
    )
    response = runtime.run(CASE)
    assert response.status == FollowUpStatus.COMPLETED
    assert sleeper.delays == [1.25]
    kinds = [event.type.value for event in runtime.trace]
    assert "LLM_PROVIDER_ERROR" in kinds
    assert kinds.count("LLM_RETRY_REQUESTED") == 1
    retry = _retry_event(runtime)
    assert retry.metadata["category"] == "http_5xx"
    assert retry.metadata["retryable"] is True
    assert retry.metadata["attempt"] == 1
    assert retry.metadata["provider"] == "FakeLLMProvider"
    assert retry.metadata["statusCode"] == 503
    assert retry.metadata["backoffMs"] == 1250
    assert BASE_BACKOFF_SECONDS * 1000 <= retry.metadata["backoffMs"] <= (BASE_BACKOFF_SECONDS + JITTER_MAX_SECONDS) * 1000
    assert len({event.run_id for event in runtime.trace}) == 1
    assert response.run_id == runtime.trace[0].run_id
    assert runtime.tool_executions == ["get_patient"]
    assert kinds.count("TOOL_EXECUTED") == 1
    blob = json.dumps([event.metadata for event in runtime.trace])
    assert not any(key in blob for key in FORBIDDEN_METADATA)
