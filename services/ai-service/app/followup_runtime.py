"""Bounded Follow-up Agent loop. Policy first, then registry, then tool. No HTTP."""

from __future__ import annotations

import json
import random
import time
import uuid
from typing import Any, Callable, Optional

from app.followup_models import (
    CASE_IDS,
    Evidence,
    FollowUpRequired,
    FollowUpResponse,
    FollowUpStatus,
    SuggestedAction,
    followup_response,
)
from app.followup_prompt import build_followup_agent_prompt, build_followup_recovery_prompt
from app.followup_policy import (
    PolicyDenied,
    can_make_tool_call,
    validate_output,
    validate_tool_call,
    within_timeout,
)
from app.followup_tools import ToolRegistry, build_followup_tool_registry
from app.followup_trace import AgentEvent, AgentEventType
from app.llm_provider import LLMProvider, ProviderGeneration

TOOL_CALL = "tool_call"
FINAL = "final"
MAX_RECOVERY_ATTEMPTS = 1
MAX_PROVIDER_RETRIES = 1
BASE_BACKOFF_SECONDS = 1.0
MAX_BACKOFF_SECONDS = 4.0
JITTER_MAX_SECONDS = 0.25
RECOVERY_INVALID_JSON = "previous_response_invalid_json"
RECOVERY_INVALID_MESSAGE = "previous_response_invalid_message"
RECOVERY_INVALID_FINAL = "previous_response_invalid_final"
_NONRECOVERABLE_FINAL_PREFIXES = (
    "evidence id was not observed",
    "evidence tool not allowed",
    "suggested action not allowed",
)


class InvalidAgentMessage(Exception):
    def __init__(self, reason: str) -> None:
        super().__init__(reason)
        self.reason = reason


class FollowUpRuntime:
    def __init__(
        self,
        provider: LLMProvider,
        registry: Optional[ToolRegistry] = None,
        *,
        monotonic: Callable[[], float] = time.monotonic,
        sleeper: Optional[Callable[[float], None]] = None,
        jitter: Optional[Callable[[], float]] = None,
    ) -> None:
        self.provider = provider
        self.registry = registry or build_followup_tool_registry()
        self._monotonic = monotonic
        self._sleep = time.sleep if sleeper is None else sleeper
        self._jitter = _default_jitter if jitter is None else jitter
        self.observed_results: list[dict[str, Any]] = []
        self.tool_executions: list[str] = []
        self.events: list[str] = []
        self.trace: list[AgentEvent] = []
        self.run_id = ""
        self.llm_turns = 0
        self.recovery_attempts = 0
        self.provider_retries = 0
        self._recovery_category = ""
        self._sequence = 0

    def run(self, case_id: str) -> FollowUpResponse:
        self.observed_results = []
        self.tool_executions = []
        self.events = []
        self.trace = []
        self.llm_turns = 0
        self.recovery_attempts = 0
        self.provider_retries = 0
        self._recovery_category = ""
        self._sequence = 0
        self.run_id = str(uuid.uuid4())
        started = self._monotonic()
        self._record(AgentEventType.RUN_STARTED, caseId=case_id)
        if case_id not in CASE_IDS:
            self._record(AgentEventType.RUN_FAILED, reason="unknown caseId")
            return self._result(
                status=FollowUpStatus.VALIDATION_ERROR,
                case_id=case_id,
                run_id=self.run_id,
                model_called=False,
                reason="unknown caseId",
            )

        while True:
            if not within_timeout(self._monotonic() - started):
                self._record(AgentEventType.RUN_TIMEOUT)
                return self._result(
                    status=FollowUpStatus.POLICY_DENIED,
                    case_id=case_id,
                    run_id=self.run_id,
                    model_called=self.llm_turns > 0,
                    reason="timeout",
                )

            generation = self._generate(case_id)
            if _is_provider_failure(generation):
                failed = self._fail_or_retry_provider(case_id, generation)
                if failed is None:
                    continue
                return failed

            try:
                message = parse_agent_message(generation.text)
            except InvalidAgentMessage as exc:
                category = RECOVERY_INVALID_JSON if str(exc) == "invalid json" else RECOVERY_INVALID_MESSAGE
                recovered = self._recover_or_fail(
                    case_id,
                    self.run_id,
                    category,
                    str(exc),
                    trace_reason=str(exc),
                )
                if recovered is None:
                    continue
                return recovered

            if message["type"] == FINAL:
                finalized = self._finalize(case_id, self.run_id, message["output"])
                if finalized is None:
                    continue
                return finalized

            denied = self._handle_tool_call(case_id, self.run_id, message)
            if denied is not None:
                return denied

    def _handle_tool_call(
        self, case_id: str, run_id: str, message: dict[str, Any]
    ) -> Optional[FollowUpResponse]:
        tool_name = message["tool"]
        arguments = message["arguments"]
        requested_case = arguments.get("caseId") if isinstance(arguments, dict) else None
        self._record(
            AgentEventType.TOOL_REQUESTED,
            tool=tool_name,
            caseId=requested_case if isinstance(requested_case, str) else case_id,
        )
        if not can_make_tool_call(len(self.tool_executions)) or not isinstance(arguments, dict) or arguments.get("caseId") != case_id:
            self._record(AgentEventType.POLICY_CHECK, tool=tool_name, allowed=False, registryLookup=False)
            self._record(AgentEventType.TOOL_DENIED, tool=tool_name, registryLookup=False)
            reason = "max tool calls exceeded" if not can_make_tool_call(len(self.tool_executions)) else "invalid tool arguments"
            return self._result(
                status=FollowUpStatus.POLICY_DENIED,
                case_id=case_id,
                run_id=run_id,
                model_called=True,
                reason=reason,
            )
        self.events.append(f"policy:{tool_name}")
        try:
            validate_tool_call(tool_name, arguments)
        except PolicyDenied as exc:
            self._record(AgentEventType.POLICY_CHECK, tool=tool_name, allowed=False, registryLookup=False)
            self._record(AgentEventType.TOOL_DENIED, tool=tool_name, registryLookup=False)
            return self._result(
                status=FollowUpStatus.POLICY_DENIED,
                case_id=case_id,
                run_id=run_id,
                model_called=True,
                reason=str(exc),
            )
        self._record(AgentEventType.POLICY_CHECK, tool=tool_name, allowed=True, registryLookup=True)
        self.events.append(f"registry:{tool_name}")
        spec = self.registry.get(tool_name)
        self.events.append(f"execute:{tool_name}")
        result = spec.fn(arguments)
        self.tool_executions.append(tool_name)
        self.observed_results.append(result)
        self._record(AgentEventType.TOOL_EXECUTED, tool=tool_name, caseId=case_id, registryLookup=True)
        return None

    def _fail_or_retry_provider(self, case_id: str, generation: ProviderGeneration) -> Optional[FollowUpResponse]:
        retryable = provider_failure_is_retryable(generation)
        metadata: dict[str, Any] = {
            "category": generation.error or "empty",
            "retryable": retryable,
            "attempt": self.provider_retries + 1,
            "provider": type(self.provider).__name__,
        }
        if generation.status_code is not None:
            metadata["statusCode"] = generation.status_code
        self._record(AgentEventType.LLM_PROVIDER_ERROR, **metadata)
        if retryable and self.provider_retries < MAX_PROVIDER_RETRIES:
            self.provider_retries += 1
            delay = calculate_provider_backoff(self.provider_retries, self._jitter())
            retry_metadata: dict[str, Any] = {
                "category": generation.error or "empty",
                "retryable": True,
                "attempt": self.provider_retries,
                "provider": type(self.provider).__name__,
                "backoffMs": round(delay * 1000),
            }
            if generation.status_code is not None:
                retry_metadata["statusCode"] = generation.status_code
            self._record(AgentEventType.LLM_RETRY_REQUESTED, **retry_metadata)
            self._sleep(delay)
            return None
        self._record(AgentEventType.RUN_FAILED, reason="provider error")
        return self._result(
            status=FollowUpStatus.PROVIDER_ERROR,
            case_id=case_id,
            run_id=self.run_id,
            model_called=True,
            reason="provider error",
        )

    def _generate(self, case_id: str):
        self.llm_turns += 1
        provider_name = type(self.provider).__name__
        self._record(AgentEventType.LLM_REQUEST, provider=provider_name, turn=self.llm_turns)
        generation = self.provider.generate_text(self._prompt(case_id))
        success = generation.error is None and isinstance(generation.text, str) and generation.text.strip() != ""
        self._record(
            AgentEventType.LLM_RESPONSE,
            provider=provider_name,
            turn=self.llm_turns,
            success=success,
        )
        return generation

    def _record(self, event_type: AgentEventType, **metadata: Any) -> None:
        self._sequence += 1
        self.trace.append(
            AgentEvent(
                sequence=self._sequence,
                type=event_type,
                timestamp=self._monotonic(),
                run_id=self.run_id,
                metadata=dict(metadata),
            )
        )

    def _finalize(self, case_id: str, run_id: str, output: Any) -> Optional[FollowUpResponse]:
        self._record(AgentEventType.FINAL_RECEIVED)
        if not isinstance(output, dict):
            return self._recover_or_fail(
                case_id,
                run_id,
                RECOVERY_INVALID_FINAL,
                "final output must be an object",
                trace_reason="validation failed",
            )
        proposed = dict(output)
        proposed["status"] = FollowUpStatus.COMPLETED.value
        proposed["requiresHumanReview"] = True
        proposed.setdefault("suggestedActions", [])
        proposed.setdefault("evidence", [])
        try:
            validate_output(proposed, observed_results=self.observed_results)
        except (PolicyDenied, ValueError) as exc:
            if _final_failure_is_recoverable(exc):
                return self._recover_or_fail(
                    case_id,
                    run_id,
                    RECOVERY_INVALID_FINAL,
                    str(exc),
                    trace_reason="validation failed",
                )
            self._record(AgentEventType.RUN_FAILED, reason="validation failed")
            return self._result(
                status=FollowUpStatus.VALIDATION_ERROR,
                case_id=case_id,
                run_id=run_id,
                model_called=True,
                reason=str(exc),
            )
        self._record(AgentEventType.RUN_COMPLETED)
        return followup_response(
            status=FollowUpStatus.COMPLETED,
            run_id=run_id,
            case_id=case_id,
            follow_up_required=FollowUpRequired(proposed["followUpRequired"]),
            model_called=True,
            summary=proposed.get("summary"),
            reason=proposed.get("reason"),
            suggested_actions=[SuggestedAction.model_validate(item) for item in proposed["suggestedActions"]],
            evidence=[Evidence.model_validate(item) for item in proposed["evidence"]],
        )

    def _recover_or_fail(
        self,
        case_id: str,
        run_id: str,
        category: str,
        response_reason: str,
        *,
        trace_reason: str,
    ) -> Optional[FollowUpResponse]:
        if self.recovery_attempts >= MAX_RECOVERY_ATTEMPTS:
            self._record(AgentEventType.RUN_FAILED, reason=trace_reason)
            return self._result(
                status=FollowUpStatus.VALIDATION_ERROR,
                case_id=case_id,
                run_id=run_id,
                model_called=True,
                reason=response_reason,
            )
        self.recovery_attempts += 1
        self._recovery_category = category
        self._record(
            AgentEventType.RECOVERY_REQUESTED,
            category=category,
            attempt=self.recovery_attempts,
        )
        return None

    def _prompt(self, case_id: str) -> str:
        tools = tuple(
            (self.registry.get(name).name, self.registry.get(name).description) for name in self.registry.names()
        )
        category = self._recovery_category
        self._recovery_category = ""
        if category:
            return build_followup_recovery_prompt(case_id, tools, self.observed_results, category)
        return build_followup_agent_prompt(case_id, tools, self.observed_results)

    def _result(
        self,
        *,
        status: FollowUpStatus,
        case_id: str,
        run_id: str,
        model_called: bool,
        reason: str,
    ) -> FollowUpResponse:
        return followup_response(
            status=status,
            run_id=run_id,
            case_id=case_id,
            follow_up_required=FollowUpRequired.UNKNOWN,
            model_called=model_called,
            reason=reason,
        )


def parse_agent_message(text: str) -> dict[str, Any]:
    try:
        parsed = json.loads(text)
    except json.JSONDecodeError as exc:
        raise InvalidAgentMessage("invalid json") from exc
    if not isinstance(parsed, dict):
        raise InvalidAgentMessage("message must be an object")
    extra = set(parsed) - {"type", "tool", "arguments", "output"}
    if extra:
        raise InvalidAgentMessage("unsupported fields")
    message_type = parsed.get("type")
    if message_type == TOOL_CALL:
        if set(parsed) != {"type", "tool", "arguments"}:
            raise InvalidAgentMessage("invalid tool_call")
        if not isinstance(parsed.get("tool"), str) or not isinstance(parsed.get("arguments"), dict):
            raise InvalidAgentMessage("invalid tool_call")
        return parsed
    if message_type == FINAL:
        if set(parsed) != {"type", "output"}:
            raise InvalidAgentMessage("invalid final")
        return parsed
    raise InvalidAgentMessage("unknown message type")


def calculate_provider_backoff(attempt: int, random_value: float) -> float:
    exponent = max(attempt, 1) - 1
    base = min(BASE_BACKOFF_SECONDS * (2**exponent), MAX_BACKOFF_SECONDS)
    jitter = min(max(float(random_value), 0.0), JITTER_MAX_SECONDS)
    return base + jitter


def _default_jitter() -> float:
    return random.random() * JITTER_MAX_SECONDS


def provider_failure_is_retryable(generation: ProviderGeneration) -> bool:
    code = generation.status_code
    if code in (400, 401, 403):
        return False
    if code == 429:
        return True
    if code is not None and 500 <= code <= 599:
        return True
    if generation.error == "timeout":
        return True
    if generation.error == "http_5xx" and code is None:
        return True
    return False


def _is_provider_failure(generation: ProviderGeneration) -> bool:
    return bool(generation.error) or generation.text is None or generation.text.strip() == ""


def _final_failure_is_recoverable(exc: Exception) -> bool:
    reason = getattr(exc, "reason", str(exc))
    return not any(reason.startswith(prefix) for prefix in _NONRECOVERABLE_FINAL_PREFIXES)


def run_followup_agent(
    case_id: str,
    provider: LLMProvider,
    registry: Optional[ToolRegistry] = None,
) -> FollowUpResponse:
    return FollowUpRuntime(provider, registry).run(case_id)
