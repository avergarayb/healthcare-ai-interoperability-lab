"""critical-lab-coordination-v1. A model sentence is not an authorization."""
from langgraph.graph import END, START, StateGraph

from .protocols import retrieve
from .store import find_by_order, save_proposal

TOOLS = (
    "get_critical_event",
    "get_lab_order",
    "get_validated_lab_result",
    "get_patient_encounter",
    "search_clinical_protocol",
    "propose_critical_result_task",
)
_INJECTION = ("ignore previous", "ignore instructions", "system prompt", "<script", "</")


class InterceptedTransport:
    def __init__(self):
        self.calls = 0

    def complete(self, _draft):
        self.calls += 1
        return "Propuesta de reconocimiento interno. No es un diagnóstico ni una orden de tratamiento."


class BlockedTransport:
    def __init__(self):
        self.calls = 0

    def complete(self, _draft):
        self.calls += 1
        raise RuntimeError("egress_blocked")


class CriticalLabGraph:
    def __init__(self, path, transport, fetcher):
        self.path = path
        self.transport = transport
        self.fetcher = fetcher
        self._compiled = _compile({
            "admit": self._admit,
            "validate_event": self._validate_event,
            "read_clinical_context": self._read_context,
            "retrieve_protocol": self._retrieve,
            "assess_evidence": self._assess,
            "prepare_proposal": self._prepare,
            "finish": self._finish,
        })

    def invoke(self, body, on=None):
        order_id = str(body.get("orderId") or "")
        if not order_id or body.get("organizationId") != "org-mini-his":
            return {"phase": "DENIED", "reason": "unauthorized", "closesEncounter": False}
        existing = find_by_order(self.path, order_id)
        if existing is not None:
            return _public(existing)
        state = {
            "order_id": order_id,
            "organization_id": body.get("organizationId"),
            "episode_id": body.get("episodeId") or "",
            "on": on,
            "phase": "ADMITTED",
        }
        result = self._compiled.invoke(state)
        return _public(result)


    def _admit(self, state):
        state["tools"] = []
        return state

    def _validate_event(self, state):
        event = self.fetcher(state["order_id"])
        state["tools"].append("get_critical_event")
        if not isinstance(event, dict):
            state["phase"] = "DENIED"
            state["reason"] = "event_missing"
            return state
        if event.get("organizationId") != state["organization_id"] or event.get("ruleId") != "sim-hemoglobin-low":
            state["phase"] = "DENIED"
            state["reason"] = "foreign_organization" if event.get("organizationId") != state["organization_id"] else "rule_rejected"
            return state
        state["event"] = event
        state["phase"] = "EVENT_VALID"
        return state

    def _read_context(self, state):
        if state.get("phase") == "DENIED":
            return state
        state["tools"].extend(["get_lab_order", "get_validated_lab_result", "get_patient_encounter"])
        note = str(state["event"].get("note") or "")
        state["withheld"] = any(marker in note.lower() for marker in _INJECTION)
        return state

    def _retrieve(self, state):
        if state.get("phase") == "DENIED":
            return state
        state["tools"].append("search_clinical_protocol")
        found = retrieve(state["organization_id"], state.get("on"))
        if len(found) < 5:
            state["phase"] = "DENIED"
            state["reason"] = "protocols_unavailable"
            return state
        state["protocols"] = found
        return state

    def _assess(self, state):
        if state.get("phase") == "DENIED":
            return state
        state["phase"] = "EVIDENCE_READY"
        return state

    def _prepare(self, state):
        if state.get("phase") == "DENIED":
            return state
        try:
            sentence = self.transport.complete(state)
        except RuntimeError:
            state["phase"] = "DENIED"
            state["reason"] = "model_blocked"
            return state
        state["tools"].append("propose_critical_result_task")
        draft = {
            "orderId": state["order_id"],
            "eventId": state["event"].get("eventId"),
            "ruleId": state["event"].get("ruleId"),
            "ruleVersion": state["event"].get("ruleVersion"),
            "taskTitle": "Reconocer hemoglobina crítica",
            "proposal": sentence,
            "protocols": [{"id": item["id"], "version": item["version"]} for item in state["protocols"]],
            "tools": list(TOOLS),
            "withheld": bool(state.get("withheld")),
            "episodeId": state.get("episode_id") or "",
        }
        stored = save_proposal(self.path, state["order_id"], draft)
        state["stored"] = stored
        state["phase"] = "PENDING_REVIEW"
        return state

    def _finish(self, state):
        if state.get("stored"):
            return state["stored"]
        return {"phase": state.get("phase", "DENIED"), "reason": state.get("reason", "denied"), "closesEncounter": False}


def _public(body):
    if body.get("phase") != "PENDING_REVIEW":
        body["closesEncounter"] = False
        return body
    protocols = body.get("protocols") or []
    body["protocolIds"] = ", ".join(item["id"] for item in protocols)
    body["closesEncounter"] = False
    return body


def _compile(nodes):
    graph = StateGraph(dict)
    for name, action in nodes.items():
        graph.add_node(name, action)
    names = list(nodes)
    graph.add_edge(START, names[0])
    for left, right in zip(names, names[1:]):
        graph.add_edge(left, right)
    graph.add_edge(names[-1], END)
    return graph.compile()
