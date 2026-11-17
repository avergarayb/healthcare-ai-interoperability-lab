"""One LangGraph pass over the neutral gateway.

The graph orders admission, one model call and a public record. It does not
import a provider SDK, does not retry, and does not keep the document or the
credential in its state. A second entry does not call the gateway again.
"""
from asyncio import CancelledError
from typing import TypedDict

from langgraph.errors import NodeCancelledError
from langgraph.graph import END, START, StateGraph
from langsmith import tracing_context

from app.enterprise_llm_providers.errors import ProviderError
from app.model_gateway.agent import VacationClauseAgent


OPERATION_ID = "vacation-days-v1"
NODES = ("admit", "execute_model", "record", "finish")
TERMINAL = frozenset({"COMPLETED", "DENIED", "FAILED"})
_FORBIDDEN = frozenset({
    "source_excerpt", "document", "patient", "fhir", "GEMINI_API_KEY", "OPENAI_API_KEY",
})


class FlowState(TypedDict, total=False):
    phase: str
    reason: str
    organization_id: str
    principal_id: str
    operation_id: str
    deployment_id: str
    authorization_id: str
    requests_sent: int
    input_tokens: int | None
    output_tokens: int | None
    reserved_microusd: int | None
    estimated_microusd: int | None
    cost_kind: str | None
    provider_request_id: str | None
    response_status: str | None


class VacationGraph:
    """Administrative vacation-days flow. It is not a clinical protocol."""

    def __init__(self, gateway):
        self._agent = VacationClauseAgent(gateway)
        self._calls = 0
        self._compiled = _compile({
            "admit": self._admit,
            "execute_model": self._execute,
            "record": self._record,
            "finish": self._finish,
        })

    @property
    def model_calls(self):
        return self._calls

    def invoke(self, access, authorization_id, budget_microusd, resource_id, deployment_id,
               egress_consent=None):
        self._bound = (access, authorization_id, budget_microusd, resource_id, deployment_id, egress_consent)
        state = {
            "phase": "ADMITTED",
            "reason": "pending",
            "organization_id": getattr(access, "organization_id", ""),
            "principal_id": getattr(access, "principal_id", ""),
            "operation_id": OPERATION_ID,
            "deployment_id": deployment_id,
            "authorization_id": authorization_id,
            "requests_sent": 0,
        }
        try:
            result = _invoke(self._compiled, state)
        finally:
            self._bound = None
        return {key: value for key, value in result.items() if key not in _FORBIDDEN}

    def _admit(self, state):
        if any(name in state for name in _FORBIDDEN) or state.get("operation_id") != OPERATION_ID:
            return {**state, "phase": "DENIED", "reason": "operation_denied"}
        if state.get("organization_id") == "" or state.get("principal_id") == "":
            return {**state, "phase": "DENIED", "reason": "remote_not_authorized"}
        return state

    def _execute(self, state):
        if state["phase"] in TERMINAL or self._calls:
            return {**state, "phase": "FAILED", "reason": "replay_denied"}
        self._calls += 1
        access, authorization_id, budget, resource_id, deployment_id, consent = self._bound
        try:
            result = self._agent.run(
                access, authorization_id, budget, resource_id, deployment_id,
                egress_consent=consent)
        except ProviderError as error:
            sent = consent.requests_sent if consent is not None else 0
            return {**state, "phase": "FAILED", "reason": error.reason, "requests_sent": sent}
        except Exception:
            return {**state, "phase": "FAILED", "reason": "internal_failure"}
        sent = consent.requests_sent if consent is not None else 0
        return {
            **state,
            "phase": "COMPLETED",
            "reason": result.reason,
            "requests_sent": sent,
            "input_tokens": result.input_tokens,
            "output_tokens": result.output_tokens,
            "reserved_microusd": result.reserved_microusd,
            "estimated_microusd": result.estimated_microusd,
            "cost_kind": result.cost_kind,
            "provider_request_id": result.provider_request_id,
            "response_status": result.response_status,
        }

    def _record(self, state):
        if state["phase"] != "COMPLETED":
            return state
        if state.get("input_tokens") is None or state.get("output_tokens") is None:
            return {**state, "phase": "FAILED", "reason": "consumption_ambiguous"}
        if state.get("cost_kind") not in (None, "estimated", "uncertain"):
            return {**state, "phase": "FAILED", "reason": "invalid_output"}
        return state

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
    return graph.compile(checkpointer=False, store=None, cache=None, debug=False,
                         name="vacation_days_gateway")


def _invoke(compiled, state):
    with tracing_context(enabled=False, parent=False):
        try:
            return compiled.invoke(state, config={"callbacks": [], "recursion_limit": 12})
        except NodeCancelledError as error:
            raise CancelledError() from error
