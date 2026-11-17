"""One external chart pass. NeutralModelGateway is not called. A missing transport fails closed."""
import json
from uuid import uuid4

from langgraph.graph import END, START, StateGraph

from app.clinical_lab_summary.review import (
    assign_review_organization,
    prepare_organization_store,
    queue_summary,
)
from app.enterprise_llm_providers.errors import ProviderError

from .context import validate_summary
from .mcp_tool import read_chart
from .policy import AUTHORIZATION_ID, OPERATION_ID, ORGANIZATION_ID, PATIENT_ID, POLICY_REF


def denied_transport(_chart):
    """Fail closed. This object does not open a provider client."""
    raise ProviderError("model_denied")


class ExternalFhirGraph:
    """Admit the external permit, read one tool, and queue a pending review."""

    def __init__(self, client, audit, review_path, transport=None):
        self._client = client
        self._audit = audit
        self._review_path = review_path
        self._transport = denied_transport if transport is None else transport
        self._used = False
        graph = StateGraph(dict)
        graph.add_node("admit", self._admit)
        graph.add_node("read_chart", self._read)
        graph.add_node("validate", self._validate)
        graph.add_node("execute_model", self._model)
        graph.add_node("finish", self._finish)
        graph.add_edge(START, "admit")
        graph.add_edge("admit", "read_chart")
        graph.add_edge("read_chart", "validate")
        graph.add_edge("validate", "execute_model")
        graph.add_edge("execute_model", "finish")
        graph.add_edge("finish", END)
        self._compiled = graph.compile()

    def invoke(self, review_id=None):
        if self._used:
            raise ProviderError("replay_denied")
        self._used = True
        return self._compiled.invoke({
            "review_id": review_id or str(uuid4()),
            "requests_sent": 0,
            "phase": "ADMITTED",
        })

    def _admit(self, state):
        state["operation_id"] = OPERATION_ID
        state["policy_ref"] = POLICY_REF
        return state

    def _read(self, state):
        response = read_chart(self._bound(), self._client, self._audit)
        if "error" in response:
            raise ProviderError(response["error"]["message"])
        content = response.get("result", {}).get("content")
        if not isinstance(content, list) or not content:
            raise ProviderError("mcp_rejected")
        state["chart"] = json.loads(content[0]["text"])
        return state

    def _validate(self, state):
        if state["chart"].get("operation_id") != OPERATION_ID or state["chart"].get("patient_id") != PATIENT_ID:
            raise ProviderError("context_rejected")
        return state

    def _model(self, state):
        if state.get("requests_sent") != 0:
            raise ProviderError("replay_denied")
        raw = self._transport(state["chart"])
        state["requests_sent"] = 1
        parsed = json.loads(raw) if isinstance(raw, str) else raw
        state["summary"] = validate_summary(state["chart"], parsed)
        return state

    def _finish(self, state):
        queue_summary(
            self._review_path, state["review_id"], AUTHORIZATION_ID, PATIENT_ID, state["summary"])
        prepare_organization_store(self._review_path)
        assign_review_organization(self._review_path, state["review_id"], ORGANIZATION_ID)
        state["phase"] = "PENDING_REVIEW"
        state["reason"] = "pending_human_review"
        state["review_status"] = "pending"
        return state

    def _bound(self):
        return {
            "operation_id": OPERATION_ID,
            "policy_ref": POLICY_REF,
            "patient_id": PATIENT_ID,
            "authorization_id": AUTHORIZATION_ID,
        }
