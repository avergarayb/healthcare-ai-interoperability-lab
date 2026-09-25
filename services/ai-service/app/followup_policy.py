"""Deterministic Follow-up Agent policy. Application-owned; does not execute tools or call a model."""

from __future__ import annotations

from typing import Any, Iterable, Mapping, Optional

from app.followup_models import (
    CASE_IDS,
    MAX_SUMMARY_CHARS,
    FollowUpRequired,
    FollowUpStatus,
    SuggestedActionType,
)
from app.followup_tools import ToolInputError, parse_tool_case_id

MAX_TOOL_CALLS = 6
TIMEOUT_SECONDS = 30

ALLOWED_TOOLS = (
    "get_patient",
    "get_recent_encounters",
    "get_conditions",
    "get_recent_observations",
    "get_medications",
    "get_upcoming_appointments",
)

PROHIBITED_TOOLS = (
    "diagnose",
    "prescribe",
    "modify_medication",
    "modify_resource",
    "create_appointment",
    "send_message",
)

PROHIBITED_PREFIXES = (
    "create_",
    "send_",
    "write_",
    "delete_",
    "update_",
    "modify_",
)

ALLOWED_SUGGESTED_ACTIONS = tuple(item.value for item in SuggestedActionType)
ALLOWED_FOLLOW_UP_REQUIRED = tuple(item.value for item in FollowUpRequired)
ALLOWED_STATUS = tuple(item.value for item in FollowUpStatus)


class PolicyDenied(Exception):
    def __init__(self, reason: str) -> None:
        super().__init__(reason)
        self.reason = reason


def is_tool_allowed(name: str) -> bool:
    return name in ALLOWED_TOOLS


def is_prohibited_action(name: str) -> bool:
    if name in PROHIBITED_TOOLS:
        return True
    return any(name.startswith(prefix) for prefix in PROHIBITED_PREFIXES)


def can_make_tool_call(completed_calls: int) -> bool:
    return 0 <= completed_calls < MAX_TOOL_CALLS


def within_timeout(elapsed_seconds: float) -> bool:
    return elapsed_seconds <= TIMEOUT_SECONDS


def validate_tool_call(tool_name: str, payload: Any) -> None:
    if not is_tool_allowed(tool_name):
        raise PolicyDenied(f"tool not allowed: {tool_name}")
    try:
        case_id = parse_tool_case_id(payload)
    except ToolInputError as exc:
        raise PolicyDenied(str(exc)) from exc
    if case_id not in CASE_IDS:
        raise PolicyDenied(f"unknown caseId: {case_id}")


def validate_suggested_actions(actions: Any) -> None:
    if not isinstance(actions, list):
        raise PolicyDenied("suggestedActions must be a list")
    for action in actions:
        action_type = _suggested_action_type(action)
        if action_type not in ALLOWED_SUGGESTED_ACTIONS:
            raise PolicyDenied(f"suggested action not allowed: {action_type}")


def enforce_human_review(value: Any) -> bool:
    if value is not True:
        raise PolicyDenied("requiresHumanReview must remain true")
    return True


def validate_follow_up_required(value: Any) -> None:
    token = value.value if isinstance(value, FollowUpRequired) else value
    if token not in ALLOWED_FOLLOW_UP_REQUIRED:
        raise PolicyDenied("followUpRequired must be true, false, or unknown")


def validate_status(value: Any) -> None:
    token = value.value if isinstance(value, FollowUpStatus) else value
    if token not in ALLOWED_STATUS:
        raise PolicyDenied("status is not allowed")


def validate_summary(value: Any) -> None:
    if value is None:
        return
    if not isinstance(value, str) or len(value) > MAX_SUMMARY_CHARS:
        raise PolicyDenied("summary exceeds limit")


def validate_evidence(evidence: Any, observed_results: Iterable[Mapping[str, Any]]) -> None:
    if not isinstance(evidence, list):
        raise PolicyDenied("evidence must be a list")
    observed = _observed_pairs(observed_results)
    for item in evidence:
        tool_name, identifier = _evidence_pair(item)
        if not is_tool_allowed(tool_name):
            raise PolicyDenied(f"evidence tool not allowed: {tool_name}")
        if (tool_name, identifier) not in observed:
            raise PolicyDenied("evidence id was not observed")


def validate_output(
    proposed: Mapping[str, Any],
    *,
    observed_results: Optional[Iterable[Mapping[str, Any]]] = None,
) -> None:
    enforce_human_review(proposed.get("requiresHumanReview"))
    validate_status(proposed.get("status"))
    validate_follow_up_required(proposed.get("followUpRequired"))
    validate_summary(proposed.get("summary"))
    validate_suggested_actions(proposed.get("suggestedActions", []))
    if observed_results is not None:
        validate_evidence(proposed.get("evidence", []), observed_results)


def _suggested_action_type(action: Any) -> Any:
    if isinstance(action, Mapping):
        extra = set(action) - {"type", "detail"}
        if extra:
            raise PolicyDenied("suggestedActions contains unsupported fields")
        return action.get("type")
    action_type = getattr(action, "type", action)
    return action_type.value if isinstance(action_type, SuggestedActionType) else action_type


def _evidence_pair(item: Any) -> tuple[str, str]:
    if isinstance(item, Mapping):
        extra = set(item) - {"tool", "id"}
        if extra:
            raise PolicyDenied("evidence contains unsupported fields")
        tool_name = item.get("tool")
        identifier = item.get("id")
    else:
        tool_name = getattr(item, "tool", None)
        identifier = getattr(item, "id", None)
    if not isinstance(tool_name, str) or not isinstance(identifier, str):
        raise PolicyDenied("evidence must include tool and id")
    return tool_name, identifier


def _observed_pairs(observed_results: Iterable[Mapping[str, Any]]) -> set[tuple[str, str]]:
    pairs: set[tuple[str, str]] = set()
    for result in observed_results:
        tool_name = result.get("tool")
        if not is_tool_allowed(tool_name if isinstance(tool_name, str) else ""):
            continue
        for identifier in _ids_from_data(result.get("data")):
            pairs.add((tool_name, identifier))
    return pairs


def _ids_from_data(data: Any) -> list[str]:
    if isinstance(data, Mapping):
        identifier = data.get("id")
        return [identifier] if isinstance(identifier, str) else []
    if isinstance(data, list):
        collected: list[str] = []
        for item in data:
            collected.extend(_ids_from_data(item))
        return collected
    return []
