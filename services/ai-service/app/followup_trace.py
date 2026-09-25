"""In-memory Follow-up Agent trace. No prompts, completions, or tool payloads."""

from __future__ import annotations

from dataclasses import dataclass
from enum import Enum
from typing import Any


class AgentEventType(str, Enum):
    RUN_STARTED = "RUN_STARTED"
    LLM_REQUEST = "LLM_REQUEST"
    LLM_RESPONSE = "LLM_RESPONSE"
    TOOL_REQUESTED = "TOOL_REQUESTED"
    POLICY_CHECK = "POLICY_CHECK"
    TOOL_EXECUTED = "TOOL_EXECUTED"
    TOOL_DENIED = "TOOL_DENIED"
    FINAL_RECEIVED = "FINAL_RECEIVED"
    RECOVERY_REQUESTED = "RECOVERY_REQUESTED"
    LLM_PROVIDER_ERROR = "LLM_PROVIDER_ERROR"
    LLM_RETRY_REQUESTED = "LLM_RETRY_REQUESTED"
    RUN_COMPLETED = "RUN_COMPLETED"
    RUN_FAILED = "RUN_FAILED"
    RUN_TIMEOUT = "RUN_TIMEOUT"


@dataclass(frozen=True)
class AgentEvent:
    sequence: int
    type: AgentEventType
    timestamp: float
    run_id: str
    metadata: dict[str, Any]
