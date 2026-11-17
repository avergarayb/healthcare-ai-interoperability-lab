"""One lab-summary pass. A failed external call is not sent again by this instance."""
from asyncio import CancelledError
from typing import TypedDict
from uuid import uuid4

from langgraph.errors import NodeCancelledError
from langgraph.graph import END, START, StateGraph
from langsmith import tracing_context

from app.enterprise_llm_providers.errors import ProviderError

from .mcp_tool import read_chart
from .policy import DEPLOYMENT_ID, OPERATION_ID, PATIENT_ID
from .review import queue_summary


class FlowState(TypedDict, total=False):
    phase: str
    reason: str
    operation_id: str
    requests_sent: int
    review_status: str
    input_tokens: int
    output_tokens: int
    reserved_microusd: int
    estimated_microusd: int
    cost_kind: str
    provider_request_id: str
    response_status: str


NODES = ("admit", "read_chart", "validate", "execute_model", "finish")
_FORBIDDEN = ("name", "birthDate", "address", "telecom", "source_excerpt", "GEMINI_API_KEY")


class LabSummaryGraph:
    """Admit, read one MCP tool, call the neutral gateway once, and queue Human Review."""

    def __init__(self, gateway, federation, audit, review_path):
        self._gateway = gateway
        self._federation = federation
        self._audit = audit
        self._review_path = review_path
        self._passes = 0
        self._model_calls = 0
        self._bound = None
        self._chart = None
        self._compiled = _compile({
            "admit": self._admit,
            "read_chart": self._read_chart,
            "validate": self._validate,
            "execute_model": self._execute,
            "finish": self._finish,
        })

    @property
    def model_calls(self):
        return self._model_calls

    def invoke(self, access, authorization_id, budget_microusd, resource_id, consent):
        if self._passes:
            return {"phase": "FAILED", "reason": "replay_denied", "operation_id": OPERATION_ID,
                    "requests_sent": consent.requests_sent if consent is not None else 0}
        self._passes += 1
        self._bound = {
            "authorization_id": authorization_id,
            "principal_id": getattr(access, "principal_id", ""),
            "patient_id": resource_id,
            "operation_id": OPERATION_ID,
            "access": access,
            "budget_microusd": budget_microusd,
            "consent": consent,
        }
        state = {"phase": "ADMITTED", "reason": "admitted", "operation_id": OPERATION_ID, "requests_sent": 0}
        try:
            result = _invoke(self._compiled, state)
        finally:
            self._bound = None
            self._chart = None
        for name in _FORBIDDEN:
            result.pop(name, None)
        return result

    def _admit(self, state):
        bound = self._bound
        if bound["operation_id"] != OPERATION_ID or bound["patient_id"] != PATIENT_ID:
            return {**state, "phase": "DENIED", "reason": "operation_denied"}
        if bound["principal_id"] == "" or bound["access"] is None:
            return {**state, "phase": "DENIED", "reason": "remote_not_authorized"}
        return state

    def _read_chart(self, state):
        if state["phase"] in {"DENIED", "FAILED"}:
            return state
        try:
            reply = read_chart(self._bound, self._federation, self._audit)
        except ProviderError as error:
            return {**state, "phase": "FAILED", "reason": error.reason}
        if "error" in reply:
            return {**state, "phase": "FAILED", "reason": reply["error"]["message"]}
        try:
            import json
            self._chart = json.loads(reply["result"]["content"][0]["text"])
        except (KeyError, IndexError, TypeError, ValueError):
            return {**state, "phase": "FAILED", "reason": "context_rejected"}
        return state

    def _validate(self, state):
        if state["phase"] in {"DENIED", "FAILED"}:
            return state
        from .context import require_model_context
        try:
            self._chart = require_model_context(self._chart, PATIENT_ID)
        except ProviderError as error:
            return {**state, "phase": "FAILED", "reason": error.reason}
        return state

    def _execute(self, state):
        if state["phase"] in {"DENIED", "FAILED"}:
            return state
        bound = self._bound
        review_id = str(uuid4())
        self._model_calls += 1

        def before_consume(summary):
            queue_summary(
                self._review_path, review_id, bound["authorization_id"], PATIENT_ID, summary)

        try:
            result = self._gateway.execute_lab_summary(
                bound["access"], bound["authorization_id"], bound["budget_microusd"], PATIENT_ID,
                DEPLOYMENT_ID, self._chart, bound["consent"], before_consume)
        except ProviderError as error:
            sent = bound["consent"].requests_sent if bound["consent"] is not None else 0
            return {**state, "phase": "FAILED", "reason": error.reason, "requests_sent": sent}
        return {
            **state,
            "phase": "PENDING_REVIEW",
            "reason": "pending_human_review",
            "requests_sent": bound["consent"].requests_sent,
            "review_status": "pending",
            "input_tokens": result.input_tokens,
            "output_tokens": result.output_tokens,
            "reserved_microusd": result.reserved_microusd,
            "estimated_microusd": result.estimated_microusd,
            "cost_kind": result.cost_kind,
            "provider_request_id": result.provider_request_id or "",
            "response_status": result.response_status or "",
        }

    def _finish(self, state):
        return state


def _compile(actions):
    graph = StateGraph(FlowState)
    stop = frozenset({"DENIED", "FAILED"})
    for name in NODES:
        graph.add_node(name, actions[name], retry_policy=None)
    graph.add_edge(START, NODES[0])
    for current, following in zip(NODES, NODES[1:]):
        graph.add_conditional_edges(
            current,
            lambda state, nxt=following, halted=stop: "finish" if state["phase"] in halted else nxt,
            {following: following, "finish": "finish"})
    graph.add_edge("finish", END)
    return graph.compile(checkpointer=False, store=None, cache=None, debug=False, name="lab_summary_review")


def _invoke(compiled, state):
    with tracing_context(enabled=False, parent=False):
        try:
            return compiled.invoke(state, config={"callbacks": [], "recursion_limit": 12})
        except NodeCancelledError as error:
            raise CancelledError() from error
