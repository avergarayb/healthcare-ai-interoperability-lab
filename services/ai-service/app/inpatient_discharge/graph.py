"""One discharge preparation. LangGraph orders the steps. The model does not decide."""
import json
import urllib.error
import urllib.request
from typing import TypedDict
from uuid import uuid4

from langgraph.graph import END, START, StateGraph

from app.enterprise_llm_providers.errors import ProviderError

from .draft import build_draft, canonical_hash, validate_draft
from .fhir_projection import project_chart
from .protocols import retrieve
from .store import consume_without_draft, prepare

TOOLS = (
    "read_episode", "read_evolution", "read_results", "read_allergies",
    "read_medications", "read_tasks", "read_protocols",
)
NODES = ("admit", "read_chart", "retrieve", "assess", "execute_model", "finish")


class FlowState(TypedDict, total=False):
    phase: str
    reason: str


class BlockedTransport:
    def send(self, chart, protocols):
        raise ProviderError("egress_blocked")


class InterceptedTransport:
    def send(self, chart, protocols):
        return build_draft(chart, protocols)


class DischargeGraph:
    def __init__(self, review_path, transport, fetcher):
        self._path = review_path
        self._transport = transport
        self._fetcher = fetcher
        self._bound = None
        self._chart = None
        self._protocols = []
        self._tools = []
        self.public = {}
        self._compiled = _compile({
            "admit": self._admit,
            "read_chart": self._read_chart,
            "retrieve": self._retrieve,
            "assess": self._assess,
            "execute_model": self._execute,
            "finish": self._finish,
        })

    def invoke(self, request):
        self._bound = request
        self._chart = None
        self._protocols = []
        self._tools = []
        self.public = {}
        state = _invoke(self._compiled, {"phase": "ADMITTED", "reason": "admitted"})
        self.public.setdefault("phase", state["phase"])
        self.public.setdefault("reason", state["reason"])
        self.public["tools"] = list(self._tools)
        self.public["closesEncounter"] = False
        return self.public

    def _admit(self, state):
        request = self._bound
        if request.get("organizationId") != "org-mini-his" or request.get("role") != "clinician":
            return {**state, "phase": "DENIED", "reason": "wrong_organization"}
        if not str(request.get("authorizationId", "")).startswith("dis"):
            return {**state, "phase": "DENIED", "reason": "remote_not_authorized"}
        return state

    def _read_chart(self, state):
        if state["phase"] in {"DENIED", "FAILED"}:
            return state
        try:
            chart = self._fetcher(self._bound["episodeId"])
        except Exception:
            return {**state, "phase": "FAILED", "reason": "source_unavailable"}
        if not isinstance(chart, dict) or chart.get("episodeId") != self._bound["episodeId"]:
            return {**state, "phase": "FAILED", "reason": "context_rejected"}
        self._chart = chart
        for name in TOOLS:
            if not _tool(name, chart, self._bound):
                return {**state, "phase": "FAILED", "reason": "mcp_rejected"}
            self._tools.append(name)
        return state

    def _retrieve(self, state):
        if state["phase"] in {"DENIED", "FAILED"}:
            return state
        self._protocols = retrieve(self._chart["organizationId"])
        if len(self._protocols) != len(TOOLS) - 2:
            return {**state, "phase": "FAILED", "reason": "protocols_unavailable"}
        return state

    def _assess(self, state):
        if state["phase"] in {"DENIED", "FAILED"}:
            return state
        chart = self._chart
        if chart["organizationId"] != self._bound["organizationId"]:
            return {**state, "phase": "DENIED", "reason": "wrong_organization"}
        if chart["status"] != "open":
            return {**state, "phase": "FAILED", "reason": "episode_not_open"}
        if not chart["notes"]:
            outcome = consume_without_draft(
                self._path, self._bound["authorizationId"], chart["episodeId"], "notes_missing")
            reason = "replay_denied" if outcome["outcome"] == "replay_denied" else "notes_missing"
            return {**state, "phase": "PENDING_INFORMATION", "reason": reason}
        return state

    def _execute(self, state):
        if state["phase"] in {"DENIED", "FAILED", "PENDING_INFORMATION"}:
            return state
        try:
            draft = self._transport.send(self._chart, self._protocols)
        except ProviderError as error:
            consume_without_draft(self._path, self._bound["authorizationId"], self._chart["episodeId"], error.reason)
            return {**state, "phase": "FAILED", "reason": error.reason}
        reason = validate_draft(draft, self._chart, self._protocols)
        if reason:
            consume_without_draft(self._path, self._bound["authorizationId"], self._chart["episodeId"], reason)
            return {**state, "phase": "FAILED", "reason": reason}
        proposal_id = str(uuid4())
        body = {
            "proposalId": proposal_id,
            "episodeVersion": self._chart["version"],
            "draft": draft,
            "tools": list(self._tools),
            "protocols": draft["protocols"],
        }
        outcome = prepare(
            self._path, self._bound["authorizationId"], self._chart["episodeId"],
            self._chart["version"], canonical_hash(draft), body)
        if outcome["outcome"] == "replay_denied":
            return {**state, "phase": "FAILED", "reason": "replay_denied"}
        self.public = {
            "phase": "PENDING_REVIEW",
            "reason": "pending_human_review",
            "proposalId": proposal_id,
            "proposalHash": canonical_hash(draft),
            "episodeVersion": self._chart["version"],
            "checklistComplete": draft["checklistComplete"],
            "statements": draft["statements"],
            "pending": draft["pending"],
            "proposedTasks": draft["proposedTasks"],
            "protocols": draft["protocols"],
            "abstentions": draft["abstentions"],
            "fhirTypes": sorted({item["resource"]["resourceType"] for item in project_chart(self._chart)["entry"]}),
            "closesEncounter": False,
        }
        return {**state, "phase": "PENDING_REVIEW", "reason": "pending_human_review"}

    def _finish(self, state):
        return state


def fetch_chart(base_url, token, episode_id):
    if not base_url.startswith("http://127.0.0.1:") or not token:
        raise ProviderError("source_unavailable")
    request = urllib.request.Request(
        base_url.rstrip("/") + "/api/inpatient/episodes/" + episode_id + "/chart",
        headers={"X-Service-Token": token, "Accept": "application/json"})
    try:
        with urllib.request.urlopen(request, timeout=3) as response:
            return json.loads(response.read().decode("utf-8"))
    except (urllib.error.URLError, json.JSONDecodeError, TimeoutError) as error:
        raise ProviderError("source_unavailable") from error


def _tool(name, chart, request):
    if request.get("episodeId") != chart.get("episodeId"):
        return False
    slices = {
        "read_episode": chart.get("episodeId"),
        "read_evolution": chart.get("notes"),
        "read_results": chart.get("results"),
        "read_allergies": chart.get("allergies"),
        "read_medications": chart.get("medications"),
        "read_tasks": chart.get("tasks"),
        "read_protocols": True,
    }
    return name in slices and slices[name] is not None


def _compile(actions):
    graph = StateGraph(FlowState)
    stop = frozenset({"DENIED", "FAILED", "PENDING_INFORMATION", "PENDING_REVIEW"})
    for name in NODES:
        graph.add_node(name, actions[name], retry_policy=None)
    graph.add_edge(START, NODES[0])
    for current, following in zip(NODES, NODES[1:]):
        graph.add_conditional_edges(
            current,
            lambda state, nxt=following, halted=stop: "finish" if state["phase"] in halted else nxt,
            {following: following, "finish": "finish"})
    graph.add_edge("finish", END)
    return graph.compile(checkpointer=False, store=None, cache=None, debug=False, name="inpatient_discharge")


def _invoke(compiled, state):
    return compiled.invoke(state, config={"callbacks": [], "recursion_limit": 12})
