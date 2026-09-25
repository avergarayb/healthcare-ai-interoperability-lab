"""Opt-in live Gemini observation for the Follow-up Agent.

Recovery is not provoked against Gemini. Deterministic recovery coverage stays in
test_followup_recovery.py. These tests do not strip fences or relax policy.
"""

from __future__ import annotations

import json
import os
import re
import warnings
from enum import Enum

import pytest

from app.config import Settings
from app.fake_llm_provider import FakeLLMProvider
from app.followup_evaluation import RESPONSE_KEYS
from app.followup_models import FollowUpRequired, FollowUpStatus, dump_followup_response, followup_response
from app.followup_policy import (
    ALLOWED_SUGGESTED_ACTIONS,
    ALLOWED_TOOLS,
    is_prohibited_action,
    validate_evidence,
)
from app.followup_runtime import FollowUpRuntime
from app.followup_trace import AgentEvent, AgentEventType
from app.gemini_provider import GeminiProvider
from app.main import get_llm_provider

LIVE_CASES = ("SYN-FOLLOWUP-001", "SYN-FOLLOWUP-002", "SYN-FOLLOWUP-005")
TERMINAL_EVENTS = {
    AgentEventType.RUN_COMPLETED,
    AgentEventType.RUN_FAILED,
    AgentEventType.RUN_TIMEOUT,
    AgentEventType.TOOL_DENIED,
}
FORBIDDEN_TRACE_KEYS = {"prompt", "completion", "text", "api_key", "token", "data", "arguments", "output"}


class LiveOutcome(str, Enum):
    CONTRACT_SUCCESS = "CONTRACT_SUCCESS"
    CONTRACT_VALIDATION_FAILURE = "CONTRACT_VALIDATION_FAILURE"
    POLICY_DENIAL = "POLICY_DENIAL"
    PROVIDER_ERROR = "PROVIDER_ERROR"
    TIMEOUT = "TIMEOUT"


def _live_enabled() -> bool:
    return os.getenv("RUN_LIVE_GEMINI_TESTS", "false").strip().lower() == "true"


def _leaks_secret(value: str) -> bool:
    secret = os.getenv("GEMINI_API_KEY", "").strip()
    return bool(secret) and secret in value


def _sanitize(value: str, secret: str = "") -> str:
    hidden = secret or os.getenv("GEMINI_API_KEY", "").strip()
    text = " ".join(value.split())
    if hidden:
        text = text.replace(hidden, "[redacted]")
    text = re.sub(r"AIza[\w-]{10,}", "[redacted]", text)
    text = re.sub(r"(?i)(authorization|api[_-]?key|token|key)(['\"\s:=]+)[^\s'\",}]+", r"\1\2[redacted]", text)
    text = re.sub(r"https?://\S+", "[url]", text)
    return text[:180]


def _status_code(exc: BaseException) -> str:
    code = getattr(exc, "code", None)
    if isinstance(code, int):
        return str(code)
    response = getattr(exc, "response", None)
    status = getattr(response, "status_code", None)
    if isinstance(status, int):
        return str(status)
    return "-"


def _exception_detail(exc: BaseException) -> str:
    message = getattr(exc, "message", None)
    status = getattr(exc, "status", None)
    parts = [type(exc).__name__]
    if isinstance(status, str) and status.isidentifier():
        parts.append(status)
    if isinstance(message, str) and message.strip():
        parts.append(_sanitize(message))
    elif str(exc).strip():
        parts.append(_sanitize(str(exc)))
    detail = " ".join(parts)
    secret = os.getenv("GEMINI_API_KEY", "").strip()
    if secret and secret in detail:
        return type(exc).__name__
    return detail


def _observe_provider(provider: GeminiProvider) -> list[dict[str, str]]:
    """Record sanitized provider outcomes. The production method still performs the call."""
    notes: list[dict[str, str]] = []
    pending: list[dict[str, str]] = []
    original_invoke = provider._invoke
    original_generate = provider.generate_text

    def invoke(client, prompt: str):
        try:
            response = original_invoke(client, prompt)
        except Exception as exc:
            pending.append(
                {
                    "sdk_completed": "false",
                    "exception_type": type(exc).__name__,
                    "status_code": _status_code(exc),
                    "text_state": "-",
                    "detail": _exception_detail(exc),
                }
            )
            raise
        text = getattr(response, "text", None)
        if not isinstance(text, str):
            text_state = "none"
        elif text.strip() == "":
            text_state = "empty"
        else:
            text_state = "non-empty"
        pending.append(
            {
                "sdk_completed": "true",
                "exception_type": "-",
                "status_code": "-",
                "text_state": text_state,
                "detail": "-",
            }
        )
        return response

    def generate(prompt: str):
        before = len(pending)
        generation = original_generate(prompt)
        note = pending[before] if len(pending) > before else None
        if generation.text is None:
            text_state = "none"
        elif generation.text.strip() == "":
            text_state = "empty"
        else:
            text_state = "non-empty"
        if note is not None:
            text_state = note["text_state"]
        notes.append(
            {
                "turn": str(len(notes) + 1),
                "provider_error": generation.error or "-",
                "sdk_completed": note["sdk_completed"] if note else "false",
                "exception_type": note["exception_type"] if note else ("FuturesTimeout" if generation.error == "timeout" else "-"),
                "status_code": note["status_code"] if note else "-",
                "text_state": text_state,
                "detail": note["detail"] if note else ("executor timeout" if generation.error == "timeout" else "-"),
            }
        )
        return generation

    provider._invoke = invoke
    provider.generate_text = generate
    return notes


def classify_live_outcome(response, trace) -> LiveOutcome:
    timed_out = response.reason == "timeout" or any(event.type == AgentEventType.RUN_TIMEOUT for event in trace)
    if timed_out:
        return LiveOutcome.TIMEOUT
    if response.status == FollowUpStatus.PROVIDER_ERROR:
        return LiveOutcome.PROVIDER_ERROR
    if response.status == FollowUpStatus.POLICY_DENIED:
        return LiveOutcome.POLICY_DENIAL
    if response.status == FollowUpStatus.VALIDATION_ERROR:
        return LiveOutcome.CONTRACT_VALIDATION_FAILURE
    if response.status == FollowUpStatus.COMPLETED:
        return LiveOutcome.CONTRACT_SUCCESS
    raise AssertionError("unclassified follow-up status")


def _assert_trace(runtime: FollowUpRuntime, response) -> None:
    events = runtime.trace
    assert events
    assert events[0].type == AgentEventType.RUN_STARTED
    assert [event.sequence for event in events] == list(range(1, len(events) + 1))
    assert all(event.run_id == response.run_id for event in events)
    kinds = {event.type for event in events}
    assert AgentEventType.LLM_REQUEST in kinds
    assert AgentEventType.LLM_RESPONSE in kinds
    assert events[-1].type in TERMINAL_EVENTS
    for index, event in enumerate(events):
        assert FORBIDDEN_TRACE_KEYS.isdisjoint(event.metadata)
        if event.type == AgentEventType.TOOL_EXECUTED:
            assert index >= 2
            assert events[index - 1].type == AgentEventType.POLICY_CHECK
            assert events[index - 2].type == AgentEventType.TOOL_REQUESTED
            assert is_prohibited_action(event.metadata.get("tool", "")) is False
        if event.type == AgentEventType.TOOL_DENIED:
            assert all(later.type != AgentEventType.TOOL_EXECUTED for later in events[index + 1 :])
    leaked = _leaks_secret(json.dumps(dump_followup_response(response)))
    for event in events:
        leaked = leaked or _leaks_secret(json.dumps(event.metadata, default=str))
    assert leaked is False


def _assert_contract(runtime: FollowUpRuntime, response, case_id: str) -> None:
    body = dump_followup_response(response)
    assert set(body) == RESPONSE_KEYS
    assert response.case_id == case_id
    assert response.model_called is True
    assert response.requires_human_review is True
    for tool_name in runtime.tool_executions:
        assert tool_name in ALLOWED_TOOLS
        assert is_prohibited_action(tool_name) is False
    for action in response.suggested_actions:
        assert action.type.value in ALLOWED_SUGGESTED_ACTIONS
    validate_evidence(
        [{"tool": item.tool, "id": item.id} for item in response.evidence],
        runtime.observed_results,
    )
    _assert_trace(runtime, response)


def _response(status: FollowUpStatus, reason: str | None = None):
    return followup_response(
        status=status,
        run_id="run-1",
        case_id="SYN-FOLLOWUP-001",
        follow_up_required=FollowUpRequired.UNKNOWN,
        model_called=True,
        reason=reason,
    )


def _events(*types: AgentEventType) -> list[AgentEvent]:
    return [
        AgentEvent(sequence=index, type=event_type, timestamp=0.0, run_id="run-1", metadata={})
        for index, event_type in enumerate(types, start=1)
    ]


def test_diagnostic_detail_redacts_secrets():
    secret = "synthetic-secret-value"
    detail = _sanitize(f"request failed key={secret} url=https://example.test/path?key={secret}", secret=secret)
    assert secret not in detail
    assert "[redacted]" in detail
    assert "[url]" in detail


@pytest.mark.parametrize(
    ("status", "reason", "terminal", "expected"),
    [
        (FollowUpStatus.COMPLETED, None, AgentEventType.RUN_COMPLETED, LiveOutcome.CONTRACT_SUCCESS),
        (
            FollowUpStatus.VALIDATION_ERROR,
            "invalid json",
            AgentEventType.RUN_FAILED,
            LiveOutcome.CONTRACT_VALIDATION_FAILURE,
        ),
        (
            FollowUpStatus.POLICY_DENIED,
            "tool not allowed: send_message",
            AgentEventType.TOOL_DENIED,
            LiveOutcome.POLICY_DENIAL,
        ),
        (FollowUpStatus.PROVIDER_ERROR, "provider error", AgentEventType.RUN_FAILED, LiveOutcome.PROVIDER_ERROR),
        (FollowUpStatus.POLICY_DENIED, "timeout", AgentEventType.RUN_TIMEOUT, LiveOutcome.TIMEOUT),
    ],
)
def test_live_outcome_classification(status, reason, terminal, expected):
    response = _response(status, reason)
    trace = _events(AgentEventType.RUN_STARTED, terminal)
    assert classify_live_outcome(response, trace) == expected


def test_scripted_run_satisfies_the_live_trace_contract():
    runtime = FollowUpRuntime(FakeLLMProvider(script=[{"type": "final", "output": {
        "followUpRequired": "unknown",
        "summary": "Synthetic laboratory summary.",
        "reason": "Synthetic laboratory reason.",
        "suggestedActions": [{"type": "none", "detail": "Synthetic detail."}],
        "evidence": [],
    }}]))
    response = runtime.run("SYN-FOLLOWUP-001")
    _assert_contract(runtime, response, "SYN-FOLLOWUP-001")
    assert classify_live_outcome(response, runtime.trace) == LiveOutcome.CONTRACT_SUCCESS


def test_trace_contract_rejects_a_foreign_run_id():
    runtime = FollowUpRuntime(FakeLLMProvider(script=[{"type": "final", "output": {
        "followUpRequired": "unknown",
        "summary": "Synthetic laboratory summary.",
        "reason": "Synthetic laboratory reason.",
        "suggestedActions": [],
        "evidence": [],
    }}]))
    response = runtime.run("SYN-FOLLOWUP-001")
    runtime.trace.append(
        AgentEvent(
            sequence=len(runtime.trace) + 1,
            type=AgentEventType.RUN_FAILED,
            timestamp=0.0,
            run_id="other-run",
            metadata={},
        )
    )
    with pytest.raises(AssertionError):
        _assert_trace(runtime, response)


@pytest.mark.skipif(not _live_enabled(), reason="live Gemini tests are opt-in")
@pytest.mark.parametrize("case_id", LIVE_CASES)
def test_live_followup_case(case_id: str):
    api_key = os.getenv("GEMINI_API_KEY", "").strip()
    if not api_key:
        pytest.skip("GEMINI_API_KEY is required for live Gemini tests")
    settings = Settings(
        model_boundary_base_url="http://model-boundary.test",
        model_boundary_path="/api/model-boundary/v1",
        model_boundary_timeout_seconds=5,
        model_boundary_service_token="test-model-boundary-token",
        host="127.0.0.1",
        port=8090,
        llm_experimental_enabled=False,
        gemini_api_key=api_key,
        gemini_model=os.getenv("GEMINI_MODEL", "gemini-flash-latest").strip() or "gemini-flash-latest",
        followup_agent_enabled=True,
    )
    provider = get_llm_provider(settings)
    assert isinstance(provider, GeminiProvider)
    notes = _observe_provider(provider)
    runtime = FollowUpRuntime(provider)
    response = runtime.run(case_id)
    _assert_contract(runtime, response, case_id)
    outcome = classify_live_outcome(response, runtime.trace)
    observed = " ".join(
        "turn={turn} provider_error={provider_error} sdk_completed={sdk_completed} "
        "exception={exception_type} status_code={status_code} text={text_state} detail={detail}".format(**note)
        for note in notes
    )
    if _leaks_secret(observed):
        observed = "diagnostic redacted"
    warnings.warn(
        f"live follow-up case={case_id} category={outcome.value} status={response.status.value} "
        f"llm_turns={runtime.llm_turns} tools={','.join(runtime.tool_executions) or '-'} "
        f"recovery={runtime.recovery_attempts} {observed}",
        UserWarning,
        stacklevel=1,
    )
