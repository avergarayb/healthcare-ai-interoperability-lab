"""Gemini text boundary. The provider returns text; the runtime and policy decide what executes."""

from __future__ import annotations

import inspect
import json

from app.followup_models import FollowUpStatus
from app.followup_policy import ALLOWED_TOOLS, MAX_TOOL_CALLS
from app.followup_runtime import FollowUpRuntime
from app.followup_trace import AgentEventType
from app.gemini_provider import GeminiProvider

CASE = "SYN-FOLLOWUP-001"


class _TextResponse:
    def __init__(self, text: str) -> None:
        self.text = text


def _tool_text(tool: str) -> str:
    return json.dumps({"type": "tool_call", "tool": tool, "arguments": {"caseId": CASE}})


def _final_text(**overrides) -> str:
    output = {
        "followUpRequired": "true",
        "summary": "Synthetic laboratory summary.",
        "reason": "Observed synthetic context.",
        "suggestedActions": [{"type": "consider-follow-up", "detail": "Synthetic detail."}],
        "evidence": [{"tool": "get_patient", "id": "SYN-PAT-001"}],
    }
    output.update(overrides)
    return json.dumps({"type": "final", "output": output})


def _provider(monkeypatch, script: list[object]) -> tuple[GeminiProvider, list[int]]:
    provider = GeminiProvider(api_key="test-key", model="gemini-flash-latest")
    pending = list(script)
    calls: list[int] = []

    def fake_invoke(client, prompt: str):
        calls.append(1)
        item = pending.pop(0)
        if isinstance(item, Exception):
            raise item
        return _TextResponse(item)

    def reject_summary(request):
        raise AssertionError("follow-up must use generate_text")

    monkeypatch.setattr(provider, "_invoke", fake_invoke)
    monkeypatch.setattr(provider, "generate_summary", reject_summary)
    return provider, calls


def _run(monkeypatch, script: list[object]) -> tuple[FollowUpRuntime, object, list[int]]:
    provider, calls = _provider(monkeypatch, script)
    runtime = FollowUpRuntime(provider, sleeper=lambda _delay: None, jitter=lambda: 0.0)
    response = runtime.run(CASE)
    return runtime, response, calls


def _types(runtime: FollowUpRuntime) -> list[AgentEventType]:
    return [event.type for event in runtime.trace]


def _trace_blob(runtime: FollowUpRuntime) -> str:
    return json.dumps([event.metadata for event in runtime.trace])


def test_provider_receives_only_a_prompt(monkeypatch):
    signature = inspect.signature(GeminiProvider.generate_text)
    assert list(signature.parameters) == ["self", "prompt"]
    source = inspect.getsource(GeminiProvider)
    assert "ToolRegistry" not in source
    assert "get_patient" not in source
    provider, calls = _provider(monkeypatch, ['{"type":"final","output":{}}'])
    generation = provider.generate_text("synthetic prompt")
    assert calls == [1]
    assert generation.text == '{"type":"final","output":{}}'
    assert generation.error is None


def test_valid_tool_call_is_executed_only_after_policy(monkeypatch):
    runtime, response, calls = _run(monkeypatch, [_tool_text("get_patient"), _final_text()])
    assert response.status == FollowUpStatus.COMPLETED
    assert response.requires_human_review is True
    assert response.model_called is True
    assert runtime.tool_executions == ["get_patient"]
    assert runtime.events == ["policy:get_patient", "registry:get_patient", "execute:get_patient"]
    assert _types(runtime) == [
        AgentEventType.RUN_STARTED,
        AgentEventType.LLM_REQUEST,
        AgentEventType.LLM_RESPONSE,
        AgentEventType.TOOL_REQUESTED,
        AgentEventType.POLICY_CHECK,
        AgentEventType.TOOL_EXECUTED,
        AgentEventType.LLM_REQUEST,
        AgentEventType.LLM_RESPONSE,
        AgentEventType.FINAL_RECEIVED,
        AgentEventType.RUN_COMPLETED,
    ]
    assert calls == [1, 1]
    assert "synthetic prompt" not in _trace_blob(runtime)
    assert "SYN-PAT-001" not in _trace_blob(runtime)


def test_two_tool_calls_then_final(monkeypatch):
    runtime, response, calls = _run(
        monkeypatch,
        [
            _tool_text("get_patient"),
            _tool_text("get_upcoming_appointments"),
            _final_text(
                evidence=[
                    {"tool": "get_patient", "id": "SYN-PAT-001"},
                    {"tool": "get_upcoming_appointments", "id": "SYN-APT-001"},
                ]
            ),
        ],
    )
    assert response.status == FollowUpStatus.COMPLETED
    assert runtime.tool_executions == ["get_patient", "get_upcoming_appointments"]
    assert _types(runtime).count(AgentEventType.TOOL_EXECUTED) == 2
    assert _types(runtime)[-2:] == [AgentEventType.FINAL_RECEIVED, AgentEventType.RUN_COMPLETED]
    assert calls == [1, 1, 1]


def test_unknown_tool_is_denied_before_registry_execution(monkeypatch):
    runtime, response, calls = _run(monkeypatch, [_tool_text("unknown_tool")])
    assert response.status == FollowUpStatus.POLICY_DENIED
    assert runtime.tool_executions == []
    assert "execute:unknown_tool" not in runtime.events
    assert _types(runtime)[-3:] == [
        AgentEventType.TOOL_REQUESTED,
        AgentEventType.POLICY_CHECK,
        AgentEventType.TOOL_DENIED,
    ]
    assert calls == [1]


def test_prohibited_tool_is_denied_before_registry_execution(monkeypatch):
    runtime, response, calls = _run(monkeypatch, [_tool_text("send_message")])
    assert response.status == FollowUpStatus.POLICY_DENIED
    assert runtime.tool_executions == []
    assert AgentEventType.TOOL_EXECUTED not in _types(runtime)
    assert _types(runtime)[-3:] == [
        AgentEventType.TOOL_REQUESTED,
        AgentEventType.POLICY_CHECK,
        AgentEventType.TOOL_DENIED,
    ]
    assert calls == [1]


def test_invalid_json_recovers_once_then_fails(monkeypatch):
    runtime, response, calls = _run(monkeypatch, ["this is not json", "still not json"])
    assert response.status == FollowUpStatus.VALIDATION_ERROR
    assert response.reason == "invalid json"
    assert runtime.tool_executions == []
    assert _types(runtime).count(AgentEventType.RECOVERY_REQUESTED) == 1
    assert _types(runtime)[-1] == AgentEventType.RUN_FAILED
    assert "this is not json" not in _trace_blob(runtime)
    assert calls == [1, 1]


def test_markdown_fences_stay_invalid_json(monkeypatch):
    fenced = "```json\n" + _final_text(evidence=[], followUpRequired="unknown", suggestedActions=[{"type": "none", "detail": "Synthetic detail."}]) + "\n```"
    runtime, response, calls = _run(monkeypatch, [fenced, fenced])
    assert response.status == FollowUpStatus.VALIDATION_ERROR
    assert response.reason == "invalid json"
    assert runtime.tool_executions == []
    assert _types(runtime).count(AgentEventType.RECOVERY_REQUESTED) == 1
    assert "```" not in _trace_blob(runtime)
    assert calls == [1, 1]


def test_invalid_final_output_fails_after_final_is_received(monkeypatch):
    invalid = _final_text(followUpRequired="maybe")
    runtime, response, calls = _run(monkeypatch, [invalid, invalid])
    assert response.status == FollowUpStatus.VALIDATION_ERROR
    assert response.requires_human_review is True
    assert _types(runtime).count(AgentEventType.RECOVERY_REQUESTED) == 1
    assert _types(runtime)[-2:] == [AgentEventType.FINAL_RECEIVED, AgentEventType.RUN_FAILED]
    assert calls == [1, 1]


def test_invented_evidence_is_rejected(monkeypatch):
    runtime, response, calls = _run(
        monkeypatch,
        [_tool_text("get_patient"), _final_text(evidence=[{"tool": "get_patient", "id": "SYN-PAT-999"}])],
    )
    assert response.status == FollowUpStatus.VALIDATION_ERROR
    assert runtime.tool_executions == ["get_patient"]
    assert response.evidence == []
    assert _types(runtime)[-2:] == [AgentEventType.FINAL_RECEIVED, AgentEventType.RUN_FAILED]
    assert calls == [1, 1]


def test_model_cannot_disable_human_review(monkeypatch):
    runtime, response, calls = _run(monkeypatch, [_final_text(requiresHumanReview=False, evidence=[])])
    assert response.status == FollowUpStatus.COMPLETED
    assert response.requires_human_review is True
    assert calls == [1]
    del runtime


def test_seventh_tool_call_stops_at_the_existing_limit(monkeypatch):
    script = [_tool_text(name) for name in ALLOWED_TOOLS]
    script.append(_tool_text("get_patient"))
    runtime, response, calls = _run(monkeypatch, script)
    assert response.status == FollowUpStatus.POLICY_DENIED
    assert response.reason == "max tool calls exceeded"
    assert runtime.tool_executions == list(ALLOWED_TOOLS)
    assert len(runtime.tool_executions) == MAX_TOOL_CALLS
    assert _types(runtime).count(AgentEventType.TOOL_EXECUTED) == MAX_TOOL_CALLS
    assert _types(runtime)[-1] == AgentEventType.TOOL_DENIED
    assert calls == [1] * (MAX_TOOL_CALLS + 1)


def test_empty_model_text_is_a_provider_error(monkeypatch):
    runtime, response, calls = _run(monkeypatch, ["   \n"])
    assert response.status == FollowUpStatus.PROVIDER_ERROR
    assert response.model_called is True
    assert runtime.tool_executions == []
    assert runtime.llm_turns == 1
    assert _types(runtime)[-2:] == [AgentEventType.LLM_PROVIDER_ERROR, AgentEventType.RUN_FAILED]
    assert calls == [1]


def test_provider_exception_stays_a_provider_error(monkeypatch):
    runtime, response, calls = _run(monkeypatch, [RuntimeError("model transport failed")])
    assert response.status == FollowUpStatus.PROVIDER_ERROR
    assert response.reason == "provider error"
    assert runtime.tool_executions == []
    assert "model transport failed" not in _trace_blob(runtime)
    assert _types(runtime).count(AgentEventType.LLM_RETRY_REQUESTED) == 1
    assert _types(runtime)[-2:] == [AgentEventType.LLM_PROVIDER_ERROR, AgentEventType.RUN_FAILED]
    assert calls == [1, 1]
