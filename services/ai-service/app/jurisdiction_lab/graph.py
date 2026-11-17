"""One jurisdiction chart pass. The nodes do not choose a country."""
import json
from asyncio import CancelledError
from typing import TypedDict
from uuid import uuid4

from langgraph.errors import NodeCancelledError
from langgraph.graph import END, START, StateGraph
from langsmith import tracing_context

from app.clinical_lab_summary.review import (
    assign_review_organization,
    prepare_decision_store,
    prepare_organization_store,
    queue_summary,
    record_clinical_evidence,
)
from app.enterprise_llm_providers.errors import ProviderError
from app.enterprise_llm_providers.gemini_configuration import ALLOWED_MODEL

from .consent import OperationalJurisdictionConsent
from .context import require_model_context
from .mcp_tool import read_chart
from .policy import DEPLOYMENT_ID
from .profile import OPERATION_ID


class FlowState(TypedDict, total=False):
    phase: str
    reason: str
    operation_id: str
    review_id: str
    requests_sent: int
    review_status: str
    input_tokens: int
    output_tokens: int
    reserved_microusd: int
    estimated_microusd: int
    provider_request_id: str
    response_status: str
    profile_id: str
    validation_class: str


NODES = (
    "admit", "read_jurisdiction_lab", "validate", "authorize_model",
    "execute_model", "record", "finish",
)
_HALTED = frozenset({"DENIED", "FAILED"})


class JurisdictionLabGraph:
    """One graph for every server-selected demonstration profile."""

    def __init__(self, gateway, client, audit, review_path, profile):
        self._gateway = gateway
        self._client = client
        self._audit = audit
        self._review_path = review_path
        self._profile = profile
        self._passes = 0
        self._model_calls = 0
        self._bound = None
        self._chart = None
        self._review_id = None
        self._compiled = _compile({
            "admit": self._admit,
            "read_jurisdiction_lab": self._read,
            "validate": self._validate,
            "authorize_model": self._authorize,
            "execute_model": self._execute,
            "record": self._record,
            "finish": self._finish,
        })

    @property
    def model_calls(self):
        return self._model_calls

    def invoke(self, access, authorization_id, budget_microusd, resource_id, consent):
        profile = self._profile
        if self._passes:
            sent = consent.requests_sent if consent is not None and hasattr(consent, "requests_sent") else 0
            return {"phase": "FAILED", "reason": "replay_denied", "operation_id": OPERATION_ID,
                    "requests_sent": sent, "profile_id": profile.profile_id}
        self._passes += 1
        self._review_id = str(uuid4())
        self._bound = {
            "authorization_id": authorization_id,
            "principal_id": getattr(access, "principal_id", ""),
            "patient_id": resource_id,
            "operation_id": OPERATION_ID,
            "access": access,
            "budget_microusd": budget_microusd,
            "consent": consent,
            "profile": profile,
        }
        state = {
            "phase": "ADMITTED", "reason": "admitted", "operation_id": OPERATION_ID,
            "requests_sent": 0, "review_id": self._review_id, "profile_id": profile.profile_id,
            "validation_class": "internal-demo-rules",
        }
        try:
            result = _invoke(self._compiled, state)
        finally:
            self._bound = None
            self._chart = None
        result.pop("chart", None)
        return result

    def _admit(self, state):
        profile = self._profile
        bound = self._bound
        if bound["operation_id"] != OPERATION_ID or bound["patient_id"] != profile.patient_value:
            return {**state, "phase": "DENIED", "reason": "scope_mismatch"}
        access = bound["access"]
        if access is None or getattr(access, "organization_id", "") != profile.organization_id:
            return {**state, "phase": "DENIED", "reason": "organization_mismatch"}
        if bound["principal_id"] == "" or bound["authorization_id"] != profile.authorization_id:
            return {**state, "phase": "DENIED", "reason": "remote_not_authorized"}
        return state

    def _read(self, state):
        if state["phase"] in _HALTED:
            return state
        try:
            reply = read_chart(self._bound, self._client, self._audit)
        except ProviderError as error:
            return {**state, "phase": "FAILED", "reason": error.reason}
        if "error" in reply:
            return {**state, "phase": "FAILED", "reason": reply["error"]["message"]}
        try:
            self._chart = json.loads(reply["result"]["content"][0]["text"])
        except (KeyError, IndexError, TypeError, ValueError):
            return {**state, "phase": "FAILED", "reason": "context_rejected"}
        return state

    def _validate(self, state):
        if state["phase"] in _HALTED:
            return state
        try:
            self._chart = require_model_context(self._chart, self._profile)
        except ProviderError as error:
            return {**state, "phase": "FAILED", "reason": error.reason}
        return state

    def _authorize(self, state):
        if state["phase"] in _HALTED:
            return state
        consent = self._bound["consent"]
        if self._gateway is None or type(consent) is not OperationalJurisdictionConsent:
            return {**state, "phase": "DENIED", "reason": "model_denied"}
        return state

    def _execute(self, state):
        if state["phase"] in _HALTED:
            return state
        bound = self._bound
        profile = self._profile
        self._model_calls += 1

        def before_consume(summary):
            queue_summary(
                self._review_path, self._review_id, profile.authorization_id, profile.patient_value, summary)
            prepare_organization_store(self._review_path)
            prepare_decision_store(self._review_path)
            assign_review_organization(self._review_path, self._review_id, profile.organization_id)
            record_clinical_evidence(self._review_path, self._review_id, self._chart, summary, profile)

        try:
            result = self._gateway.execute_jurisdiction_summary(
                bound["access"], bound["authorization_id"], bound["budget_microusd"], profile.patient_value,
                DEPLOYMENT_ID, self._chart, bound["consent"], profile, before_consume)
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
            "provider_request_id": result.provider_request_id or "",
            "response_status": "intercepted",
        }

    def _record(self, state):
        if state["phase"] != "PENDING_REVIEW":
            return state
        profile = self._profile
        receipt = {
            "operation_id": OPERATION_ID,
            "authorization_id": profile.authorization_id,
            "profile_id": profile.profile_id,
            "profile_version": profile.version,
            "validation_class": "internal-demo-rules",
            "official_conformance": False,
            "provider": "gemini",
            "model": ALLOWED_MODEL,
            "phase": "intercepted",
            "requests_sent": state.get("requests_sent", 0),
            "input_tokens": state.get("input_tokens", 0),
            "output_tokens": state.get("output_tokens", 0),
            "estimated_microusd": state.get("estimated_microusd", 0),
            "provider_request_id": state.get("provider_request_id") or "",
        }
        rendered = json.dumps(receipt, ensure_ascii=True)
        if "AIza" in rendered or "GEMINI_API_KEY" in rendered:
            return {**state, "phase": "FAILED", "reason": "invalid_output"}
        self._review_path.with_name("receipt.json").write_text(rendered, encoding="utf-8")
        return state

    def _finish(self, state):
        return state


def _compile(actions):
    graph = StateGraph(FlowState)
    for name in NODES:
        graph.add_node(name, actions[name], retry_policy=None)
    graph.add_edge(START, NODES[0])
    for current, following in zip(NODES, NODES[1:]):
        graph.add_conditional_edges(
            current,
            lambda state, nxt=following: "finish" if state["phase"] in _HALTED else nxt,
            {following: following, "finish": "finish"})
    graph.add_edge("finish", END)
    return graph.compile(checkpointer=False, store=None, cache=None, debug=False, name="jurisdiction_lab_review")


def _invoke(compiled, state):
    with tracing_context(enabled=False, parent=False):
        try:
            return compiled.invoke(state, config={"callbacks": [], "recursion_limit": 16})
        except NodeCancelledError as error:
            raise CancelledError() from error
