from __future__ import annotations

from app.experimental_fixture import CANONICAL_FIXTURE
from app.experimental_models import ExperimentalSummaryRequest
from app.fake_llm_provider import FakeLLMProvider
from app.followup_models import FollowUpStatus
from app.followup_policy import ALLOWED_TOOLS, MAX_TOOL_CALLS
from app.followup_runtime import FollowUpRuntime, run_followup_agent
from app.llm_provider import ProviderGeneration


CASE = "SYN-FOLLOWUP-001"


def _tool_call(tool: str, case_id: str = CASE) -> dict:
    return {"type": "tool_call", "tool": tool, "arguments": {"caseId": case_id}}


def _final(*, evidence=None, requires_human_review=True, **overrides) -> dict:
    output = {
        "followUpRequired": "true",
        "summary": "Synthetic follow-up summary.",
        "reason": "Synthetic reason.",
        "suggestedActions": [{"type": "consider-follow-up", "detail": "Review booked visit"}],
        "evidence": evidence or [],
        "requiresHumanReview": requires_human_review,
    }
    output.update(overrides)
    return {"type": "final", "output": output}


def _runtime(script, monotonic=None) -> FollowUpRuntime:
    provider = FakeLLMProvider(script=script)
    if monotonic is None:
        return FollowUpRuntime(provider)
    return FollowUpRuntime(provider, monotonic=monotonic)


class SequenceClock:
    def __init__(self, values: list[float]) -> None:
        self.values = list(values)
        self.i = 0

    def __call__(self) -> float:
        value = self.values[min(self.i, len(self.values) - 1)]
        self.i += 1
        return value


def test_immediate_final_does_not_execute_tools():
    runtime = _runtime([_final()])
    response = runtime.run(CASE)
    assert response.status == FollowUpStatus.COMPLETED
    assert response.requires_human_review is True
    assert response.model_called is True
    assert runtime.tool_executions == []
    assert runtime.observed_results == []


def test_one_tool_then_final():
    runtime = _runtime(
        [
            _tool_call("get_patient"),
            _final(evidence=[{"tool": "get_patient", "id": "SYN-PAT-001"}]),
        ]
    )
    response = runtime.run(CASE)
    assert response.status == FollowUpStatus.COMPLETED
    assert runtime.tool_executions == ["get_patient"]
    assert runtime.observed_results[0]["data"]["id"] == "SYN-PAT-001"
    assert response.evidence[0].id == "SYN-PAT-001"


def test_two_tools_then_final():
    runtime = _runtime(
        [
            _tool_call("get_patient"),
            _tool_call("get_conditions"),
            _final(
                evidence=[
                    {"tool": "get_patient", "id": "SYN-PAT-001"},
                    {"tool": "get_conditions", "id": "SYN-CON-001"},
                ]
            ),
        ]
    )
    response = runtime.run(CASE)
    assert response.status == FollowUpStatus.COMPLETED
    assert runtime.tool_executions == ["get_patient", "get_conditions"]


def test_tools_up_to_limit_then_final():
    script = [_tool_call(name) for name in ALLOWED_TOOLS]
    script.append(_final(evidence=[{"tool": "get_patient", "id": "SYN-PAT-001"}]))
    runtime = _runtime(script)
    response = runtime.run(CASE)
    assert response.status == FollowUpStatus.COMPLETED
    assert runtime.tool_executions == list(ALLOWED_TOOLS)
    assert len(runtime.tool_executions) == MAX_TOOL_CALLS


def test_seventh_tool_call_is_not_executed():
    script = [_tool_call(name) for name in ALLOWED_TOOLS]
    script.append(_tool_call("get_patient"))
    runtime = _runtime(script)
    response = runtime.run(CASE)
    assert response.status == FollowUpStatus.POLICY_DENIED
    assert response.reason == "max tool calls exceeded"
    assert runtime.tool_executions == list(ALLOWED_TOOLS)
    assert runtime.provider.calls == 7
    assert runtime.events.count("execute:get_patient") == 1


def test_unknown_tool_is_denied_without_execution():
    runtime = _runtime([_tool_call("unknown_tool")])
    response = runtime.run(CASE)
    assert response.status == FollowUpStatus.POLICY_DENIED
    assert runtime.tool_executions == []
    assert "execute:unknown_tool" not in runtime.events


def test_send_message_is_denied_without_execution():
    runtime = _runtime([_tool_call("send_message")])
    response = runtime.run(CASE)
    assert response.status == FollowUpStatus.POLICY_DENIED
    assert "send_message" in (response.reason or "")
    assert runtime.tool_executions == []
    assert runtime.events == ["policy:send_message"]


def test_create_appointment_is_denied_without_execution():
    runtime = _runtime([_tool_call("create_appointment")])
    response = runtime.run(CASE)
    assert response.status == FollowUpStatus.POLICY_DENIED
    assert runtime.tool_executions == []


def test_invalid_arguments_are_denied_without_execution():
    runtime = _runtime(
        [
            {
                "type": "tool_call",
                "tool": "get_patient",
                "arguments": {"caseId": CASE, "resourceType": "Patient"},
            }
        ]
    )
    response = runtime.run(CASE)
    assert response.status == FollowUpStatus.POLICY_DENIED
    assert runtime.tool_executions == []


def test_provider_error_does_not_execute_tools():
    runtime = FollowUpRuntime(FakeLLMProvider("http_5xx"), sleeper=lambda _delay: None, jitter=lambda: 0.0)
    response = runtime.run(CASE)
    assert response.status == FollowUpStatus.PROVIDER_ERROR
    assert response.model_called is True
    assert runtime.tool_executions == []


def test_invalid_model_json_is_controlled_failure():
    runtime = _runtime(["not-json", "still-not-json"])
    response = runtime.run(CASE)
    assert response.status == FollowUpStatus.VALIDATION_ERROR
    assert response.reason == "invalid json"
    assert runtime.tool_executions == []


def test_valid_evidence_is_accepted():
    runtime = _runtime(
        [
            _tool_call("get_upcoming_appointments"),
            _final(evidence=[{"tool": "get_upcoming_appointments", "id": "SYN-APT-001"}]),
        ]
    )
    response = runtime.run(CASE)
    assert response.status == FollowUpStatus.COMPLETED
    assert response.evidence[0].id == "SYN-APT-001"


def test_invented_evidence_is_rejected():
    runtime = _runtime(
        [
            _tool_call("get_patient"),
            _final(evidence=[{"tool": "get_upcoming_appointments", "id": "SYN-APT-001"}]),
        ]
    )
    response = runtime.run(CASE)
    assert response.status == FollowUpStatus.VALIDATION_ERROR
    assert runtime.tool_executions == ["get_patient"]


def test_model_cannot_turn_off_human_review():
    runtime = _runtime([_final(requires_human_review=False)])
    response = runtime.run(CASE)
    assert response.status == FollowUpStatus.COMPLETED
    assert response.requires_human_review is True


def test_unknown_case_id_fails_before_llm():
    provider = FakeLLMProvider(script=[_final()])
    runtime = FollowUpRuntime(provider)
    response = runtime.run("SYN-FOLLOWUP-999")
    assert response.status == FollowUpStatus.VALIDATION_ERROR
    assert response.model_called is False
    assert provider.calls == 0
    assert runtime.tool_executions == []


def test_timeout_stops_without_waiting_or_tools():
    runtime = _runtime([_final()], monotonic=SequenceClock([0.0, 31.0]))
    response = runtime.run(CASE)
    assert response.status == FollowUpStatus.POLICY_DENIED
    assert response.reason == "timeout"
    assert runtime.provider.calls == 0
    assert runtime.tool_executions == []


def test_no_tool_runs_before_policy():
    runtime = _runtime([_tool_call("get_patient"), _final(evidence=[{"tool": "get_patient", "id": "SYN-PAT-001"}])])
    runtime.run(CASE)
    policy_at = runtime.events.index("policy:get_patient")
    registry_at = runtime.events.index("registry:get_patient")
    execute_at = runtime.events.index("execute:get_patient")
    assert policy_at < registry_at < execute_at


def test_tool_result_is_returned_to_the_next_llm_turn():
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
    prompts = runtime.provider.prompts
    assert len(prompts) == 3
    assert "Observed tool results:" not in prompts[0]
    assert "SYN-APT-001" in prompts[1]
    assert "get_upcoming_appointments" in prompts[1]
    assert "SYN-ENC-001" in prompts[2]
    assert response.status == FollowUpStatus.COMPLETED
    assert runtime.tool_executions == ["get_upcoming_appointments", "get_recent_encounters"]


def test_agent_loop_appointments_then_encounters_then_final():
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
    assert runtime.events[:6] == [
        "policy:get_upcoming_appointments",
        "registry:get_upcoming_appointments",
        "execute:get_upcoming_appointments",
        "policy:get_recent_encounters",
        "registry:get_recent_encounters",
        "execute:get_recent_encounters",
    ]
    assert runtime.observed_results[0]["data"][0]["id"] == "SYN-APT-001"
    assert runtime.observed_results[1]["data"][0]["id"] == "SYN-ENC-001"
    assert "SYN-APT-001" in runtime.provider.prompts[1]
    assert "SYN-ENC-001" in runtime.provider.prompts[2]
    assert response.agent == "follow-up-agent"
    assert response.requires_human_review is True
    assert {item.id for item in response.evidence} == {"SYN-APT-001", "SYN-ENC-001"}


def test_prompt_asks_for_raw_json_without_markdown_fences():
    # Gemini often wraps JSON in markdown fences. parse_agent_message rejects that text.
    runtime = _runtime([_final()])
    runtime.run(CASE)
    prompt = runtime.provider.prompts[0]
    assert "Respond with JSON only." in prompt
    assert "Do not wrap the JSON in markdown fences." in prompt


def test_run_helper_returns_follow_up_response():
    response = run_followup_agent(CASE, FakeLLMProvider(script=[_final()]))
    assert response.status == FollowUpStatus.COMPLETED


def test_scripted_turns_do_not_change_generate_summary():
    provider = FakeLLMProvider(script=[_final()])
    request = ExperimentalSummaryRequest.model_validate(CANONICAL_FIXTURE)
    summary = provider.generate_summary(request)
    assert summary == ProviderGeneration(
        invocation_started=True,
        text="Synthetic laboratory summary for SYN-076-001.",
    )
    generated = provider.generate_text("prompt")
    assert generated.text is not None
    assert '"type": "final"' in generated.text or '"type":"final"' in generated.text.replace(" ", "")
