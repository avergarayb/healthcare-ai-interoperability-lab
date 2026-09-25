from __future__ import annotations

from app.fake_llm_provider import FakeLLMProvider
from app.followup_fixtures import FOLLOWUP_FIXTURES
from app.followup_models import PROMPT_VERSION
from app.followup_policy import ALLOWED_TOOLS
from app.followup_prompt import build_followup_agent_prompt, build_followup_recovery_prompt
from app.followup_runtime import FollowUpRuntime
from app.followup_tools import FOLLOWUP_TOOLS

CASE = "SYN-FOLLOWUP-001"
TOOLS = tuple((tool.name, tool.description) for tool in FOLLOWUP_TOOLS)
COT_PHRASES = (
    "chain of thought",
    "chain-of-thought",
    "think step by step",
    "show your reasoning",
    "step-by-step",
)


def _prompt(observed_results=()):
    return build_followup_agent_prompt(CASE, TOOLS, observed_results)


def test_prompt_states_agent_identity():
    prompt = _prompt()
    assert "You are a healthcare follow-up decision support agent." in prompt
    assert f"Prompt version: {PROMPT_VERSION}." in prompt
    assert PROMPT_VERSION == "follow-up-agent-v2"


def test_prompt_defines_follow_up_required():
    prompt = _prompt()
    assert "Decision objective: set followUpRequired to true, false, or unknown." in prompt
    assert "true: observed information supports considering a follow-up." in prompt
    assert "false: observed information does not show a follow-up need within the current scope." in prompt
    assert "unknown: available information is insufficient or contradictory" in prompt


def test_prompt_explains_insufficient_and_contradictory_information():
    prompt = _prompt()
    assert "If the available information is not sufficient, use unknown." in prompt
    assert "Do not treat an empty list as false." in prompt
    assert "Do not invent evidence." in prompt
    assert "If observed records contradict each other, do not invent an explanation." in prompt
    assert "Use unknown when the contradiction prevents a reliable true or false conclusion." in prompt


def test_prompt_lists_read_only_tools_and_permitted_actions():
    prompt = _prompt()
    assert "Tools are read-only." in prompt
    for name in ALLOWED_TOOLS:
        assert f"- {name}:" in prompt
    assert "review: request human review of the observed situation." in prompt
    assert "consider-follow-up: observed information supports considering follow-up." in prompt
    assert "none: no additional action is proposed within the current scope." in prompt


def test_prompt_contains_tool_call_and_final_contracts():
    prompt = _prompt()
    assert '"type": "tool_call"' in prompt
    assert f'"caseId": "{CASE}"' in prompt
    assert '"type": "final"' in prompt
    assert '"followUpRequired": "true|false|unknown"' in prompt
    assert "Respond with JSON only." in prompt
    assert "Do not wrap the JSON in markdown fences." in prompt
    assert "Do not include status, runId, modelCalled, or requiresHumanReview" in prompt


def test_prompt_has_no_chain_of_thought_secrets_or_phi():
    prompt = _prompt()
    lowered = prompt.lower()
    for phrase in COT_PHRASES:
        assert phrase not in lowered
    assert "api_key" not in lowered
    assert "bearer " not in lowered
    fixture = FOLLOWUP_FIXTURES[CASE]
    assert fixture["patient"]["display"] not in prompt
    assert fixture["patient"]["id"] not in prompt
    assert "Observed tool results:" not in prompt


def test_prompt_is_deterministic_and_adds_only_observed_results():
    assert _prompt() == _prompt()
    observed = {"tool": "get_patient", "caseId": CASE, "data": {"id": "SYN-PAT-001"}}
    first = _prompt((observed,))
    second = _prompt((observed,))
    assert first == second
    assert "Observed tool results:" in first
    assert "SYN-PAT-001" in first
    assert first != _prompt()


def test_runtime_receives_the_decision_contract_without_calling_gemini():
    provider = FakeLLMProvider(
        script=[
            {"type": "tool_call", "tool": "get_patient", "arguments": {"caseId": CASE}},
            {
                "type": "final",
                "output": {
                    "followUpRequired": "true",
                    "summary": "Synthetic laboratory summary.",
                    "reason": "Synthetic laboratory reason.",
                    "suggestedActions": [{"type": "consider-follow-up", "detail": "Synthetic detail."}],
                    "evidence": [{"tool": "get_patient", "id": "SYN-PAT-001"}],
                    "requiresHumanReview": True,
                },
            },
        ]
    )
    response = FollowUpRuntime(provider).run(CASE)
    assert response.prompt_version == PROMPT_VERSION
    assert "You are a healthcare follow-up decision support agent." in provider.prompts[0]
    assert "Observed tool results:" not in provider.prompts[0]
    assert FOLLOWUP_FIXTURES[CASE]["appointments"][0]["id"] not in provider.prompts[0]
    assert "Observed tool results:" in provider.prompts[1]
    assert "SYN-PAT-001" in provider.prompts[1]
    assert type(provider).__name__ == "FakeLLMProvider"


def test_recovery_prompt_names_the_category_and_omits_the_completion():
    observed = ({"tool": "get_patient", "caseId": CASE, "data": {"id": "SYN-PAT-001"}},)
    prompt = build_followup_recovery_prompt(CASE, TOOLS, observed, "previous_response_invalid_json")
    lowered = prompt.lower()
    assert "error_category=previous_response_invalid_json" in prompt
    assert f"caseId={CASE}" in prompt
    assert "Tools are read-only." in prompt
    assert "Observed tool results:" in prompt
    assert "SYN-PAT-001" in prompt
    assert "Application policy remains the authority." in prompt
    assert "Respond with JSON only." in prompt
    assert "not-json" not in prompt
    for phrase in COT_PHRASES:
        assert phrase not in lowered
    assert prompt == build_followup_recovery_prompt(CASE, TOOLS, observed, "previous_response_invalid_json")
