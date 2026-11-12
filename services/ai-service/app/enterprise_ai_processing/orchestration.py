"""Metadata-only LangGraph for one enterprise answer. No checkpoint and no content."""
from asyncio import CancelledError
from typing import TypedDict

from langgraph.errors import NodeCancelledError
from langgraph.graph import END, START, StateGraph
from langsmith import tracing_context


NODES = (
    "read_recognized_source",
    "admit_gate_c",
    "execute_and_ground",
    "authorize_final",
    "prepare_answer",
    "deliver_local",
    "finish",
)
TERMINAL = frozenset({"COMPLETED", "DENIED", "INSUFFICIENT", "UNCERTAIN", "FAILED"})


class FlowState(TypedDict):
    phase: str
    reason: str
    organization_id: str
    operation_id: str
    entries: int
    reservation: str
    decision: str


def compile_flow(actions):
    graph = StateGraph(FlowState)
    for name in NODES:
        graph.add_node(name, actions[name], retry_policy=None)
    graph.add_edge(START, NODES[0])
    for current, following in zip(NODES, NODES[1:]):
        graph.add_conditional_edges(
            current,
            lambda state, nxt=following: "finish" if state["phase"] in TERMINAL else nxt,
            {following: following, "finish": "finish"})
    graph.add_edge("finish", END)
    return graph.compile(checkpointer=False, store=None, cache=None, debug=False,
                         name="enterprise_answer_delivery")


def invoke_flow(compiled, state):
    with tracing_context(enabled=False, parent=False):
        try:
            return compiled.invoke(state, config={"callbacks": [], "recursion_limit": 16})
        except NodeCancelledError as error:
            raise CancelledError() from error
