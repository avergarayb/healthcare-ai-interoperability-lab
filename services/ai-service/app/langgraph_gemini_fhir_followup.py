"""The only follow-up graph.

A model proposes a tool. The application authorizes and audits that proposal
before LangGraph can execute it. The clinical tool asks the FHIR adapter.
The adapter, transport, and read client stay outside this graph.
"""

from __future__ import annotations

import json
import logging
import operator
import os
import re
import time
from typing import Annotated, Any, Callable, TypedDict

from langchain_core.messages import AIMessage, AnyMessage, HumanMessage, ToolMessage
from langchain_core.tools import BaseTool
from langgraph.graph import END, START, StateGraph
from langgraph.graph.message import add_messages
from langgraph.prebuilt import ToolNode

from app.config import Settings
from app.langgraph_fhir_client import (
    BOUNDARY_EVENTS,
    DENIAL_ANSWER,
    FOLLOWUP_TOOL,
    PATIENT_CASE,
    SAFE_AUDIT_FIELDS,
    ClientFHIRTransport,
    InMemoryAuditSink,
    ReadClientError,
    evaluate_tool_policy,
    record_policy_audit,
    send_message,
)
from app.langgraph_fhir_followup import (
    UNAVAILABLE_ANSWER,
    FollowUpFHIRAdapter,
    _resource_refs,
    make_followup_tool,
)
from app.langgraph_fhir_hapi import HapiReadClient


MAX_MODEL_TURNS = 4
MODEL_LIMIT_ANSWER = "stopped: model turn limit reached"
GEMINI_RETRY_ATTEMPTS = 3
GEMINI_RETRY_INITIAL_SECONDS = 0.25
GEMINI_RETRY_MAX_SECONDS = 1.0
TRANSIENT_GEMINI_STATUS = frozenset({408, 429, 500, 502, 503, 504})

log = logging.getLogger("ai-service")
_retry_sleep = time.sleep
SYSTEM_INSTRUCTION = (
    "You prepare a synthetic follow-up. "
    "When clinical context is missing, call get_patient_followup_context "
    "with the case id from the user message. "
    "After the tool result arrives, answer from that result only. "
    "Do not invent clinical data. Do not call any other tool. "
    "When you are not calling a tool, respond with a JSON object that has "
    "answer and follow_up_required. follow_up_required is true, false, or unknown."
)
FINAL_DECISION_FIELDS = ("true", "false", "unknown")
FINAL_DECISION_SCHEMA = {
    "type": "object",
    "properties": {
        "answer": {"type": "string"},
        "follow_up_required": {"type": "string", "enum": list(FINAL_DECISION_FIELDS)},
    },
    "required": ["answer", "follow_up_required"],
}

Model = Callable[[list[AnyMessage]], AIMessage]


def _gemini_config() -> tuple[str, str]:
    """Read the application Gemini settings. The follow-up does not keep a second config."""
    settings = Settings.from_env()
    if not settings.gemini_api_key:
        raise ValueError("GEMINI_API_KEY is required")
    return settings.gemini_api_key, settings.gemini_model


def _tool_payload(content: object) -> dict[str, Any]:
    if isinstance(content, dict):
        return content
    text = str(content)
    try:
        parsed = json.loads(text)
    except json.JSONDecodeError:
        return {"result": text}
    if isinstance(parsed, dict):
        return parsed
    return {"result": text}


class GeminiFollowUpState(TypedDict):
    case_id: str
    messages: Annotated[list[AnyMessage], add_messages]
    patient: dict[str, str] | None
    observations: list[dict[str, object]]
    tools_used: Annotated[list[str], operator.add]
    evidence: Annotated[list[dict[str, object]], operator.add]
    turn: int
    decision: str
    final_answer: str | None
    policy_decision: str
    policy_reason: str


def initial_state(case_id: str) -> GeminiFollowUpState:
    return {
        "case_id": case_id,
        "messages": [],
        "patient": None,
        "observations": [],
        "tools_used": [],
        "evidence": [],
        "turn": 0,
        "decision": "",
        "final_answer": None,
        "policy_decision": "",
        "policy_reason": "",
    }


def _mark(event: str) -> None:
    BOUNDARY_EVENTS.append(event)


def _find_read_error(exc: BaseException) -> ReadClientError | None:
    current: BaseException | None = exc
    seen: set[int] = set()
    while current is not None and id(current) not in seen:
        seen.add(id(current))
        if isinstance(current, ReadClientError):
            return current
        current = current.__cause__ or current.__context__
    return None


def _object_payload(value: Any) -> dict[str, Any] | None:
    if isinstance(value, dict):
        return value
    dump = getattr(value, "model_dump", None)
    if not callable(dump):
        return None
    dumped = dump()
    if isinstance(dumped, dict):
        return dumped
    return None


def _decision_object(response: Any, text: str) -> dict[str, Any] | None:
    """Read a structured object. Prose that is not that object is left untouched."""
    parsed = _object_payload(getattr(response, "parsed", None))
    if parsed is not None:
        return parsed
    try:
        loaded = json.loads(text)
    except json.JSONDecodeError:
        return None
    if isinstance(loaded, dict):
        return loaded
    return None


def followup_message_from_response(response: Any) -> AIMessage:
    """Map one model response to an AIMessage, keeping each function-call signature."""
    candidates = getattr(response, "candidates", None) or []
    if not candidates or getattr(candidates[0], "content", None) is None:
        raise ValueError("gemini returned no candidate")
    parts = list(getattr(candidates[0].content, "parts", None) or [])
    texts: list[str] = []
    tool_calls: list[dict[str, Any]] = []
    signatures: dict[str, Any] = {}
    for part in parts:
        function_call = getattr(part, "function_call", None)
        if function_call is not None and getattr(function_call, "name", None):
            raw_args = getattr(function_call, "args", None) or {}
            call_id = getattr(function_call, "id", None) or f"call-{len(tool_calls) + 1}"
            tool_calls.append(
                {
                    "name": function_call.name,
                    "args": dict(raw_args),
                    "id": call_id,
                    "type": "tool_call",
                }
            )
            signature = getattr(part, "thought_signature", None)
            if signature is not None:
                signatures[call_id] = signature
            continue
        text = getattr(part, "text", None)
        if isinstance(text, str) and text:
            texts.append(text)
    if not texts and not tool_calls:
        raise ValueError("gemini returned no content")
    content = "".join(texts)
    kwargs: dict[str, Any] = {}
    if signatures:
        kwargs["thought_signatures"] = signatures
    if not tool_calls:
        decision = _decision_object(response, content)
        token = decision.get("follow_up_required") if decision is not None else None
        answer = decision.get("answer") if decision is not None else None
        if token in FINAL_DECISION_FIELDS:
            kwargs["follow_up_required"] = token
            if isinstance(answer, str) and answer.strip():
                content = answer
    extra: dict[str, Any] = {"additional_kwargs": kwargs} if kwargs else {}
    return AIMessage(content=content, tool_calls=tool_calls, **extra)


def _contents(messages: list[AnyMessage]) -> list[Any]:
    """Rebuild Gemini contents. A function-call part keeps the signature Gemini sent."""
    from google.genai import types

    contents = []
    for message in messages:
        if isinstance(message, HumanMessage):
            contents.append(types.Content(role="user", parts=[types.Part(text=str(message.content))]))
        elif isinstance(message, AIMessage):
            parts = []
            signatures = message.additional_kwargs.get("thought_signatures") or {}
            if str(message.content).strip():
                parts.append(types.Part(text=str(message.content)))
            for call in message.tool_calls:
                part_fields: dict[str, Any] = {
                    "function_call": types.FunctionCall(name=call["name"], args=call["args"], id=call["id"])
                }
                signature = signatures.get(call["id"]) if isinstance(signatures, dict) else None
                if signature is not None:
                    part_fields["thought_signature"] = signature
                parts.append(types.Part(**part_fields))
            if not parts:
                raise ValueError("model message has no content")
            contents.append(types.Content(role="model", parts=parts))
        elif isinstance(message, ToolMessage):
            contents.append(
                types.Content(
                    role="user",
                    parts=[
                        types.Part(
                            function_response=types.FunctionResponse(
                                name=message.name,
                                id=message.tool_call_id,
                                response=_tool_payload(message.content),
                            )
                        )
                    ],
                )
            )
        else:
            raise ValueError("unsupported message")
    return contents


def _followup_generate_config(messages: list[AnyMessage]) -> Any:
    """Tools on the read turn. A JSON decision only after a tool result exists."""
    from google.genai import types

    if any(isinstance(message, ToolMessage) for message in messages):
        return types.GenerateContentConfig(
            system_instruction=SYSTEM_INSTRUCTION,
            response_mime_type="application/json",
            response_json_schema=FINAL_DECISION_SCHEMA,
            automatic_function_calling=types.AutomaticFunctionCallingConfig(disable=True),
        )
    return types.GenerateContentConfig(
        system_instruction=SYSTEM_INSTRUCTION,
        tools=[_declared_followup_tool()],
        automatic_function_calling=types.AutomaticFunctionCallingConfig(disable=True),
    )


def _gemini_http_options() -> Any:
    """One SDK attempt. The application retry below is the only retry."""
    from google.genai import types

    return types.HttpOptions(
        timeout=30_000,
        retry_options=types.HttpRetryOptions(attempts=1),
    )


def _backoff_seconds(failed_attempt: int) -> float:
    delay = GEMINI_RETRY_INITIAL_SECONDS * (2 ** (failed_attempt - 1))
    return min(delay, GEMINI_RETRY_MAX_SECONDS)


def _gemini_retryable(exc: BaseException) -> bool:
    """Retry provider overload and transport loss. Leave permanent request errors alone."""
    import httpx

    if isinstance(exc, (httpx.TimeoutException, httpx.ConnectError)):
        return True
    code = getattr(exc, "code", None)
    return isinstance(code, int) and not isinstance(code, bool) and code in TRANSIENT_GEMINI_STATUS


def _retry_status_label(exc: BaseException) -> str:
    code = getattr(exc, "code", None)
    if isinstance(code, int) and not isinstance(code, bool) and code in TRANSIENT_GEMINI_STATUS:
        return str(code)
    return "transport"


def _generate_with_retry(client: Any, model_name: str, messages: list[AnyMessage]) -> Any:
    """Repeat one generateContent. This does not re-enter the graph or the tool."""
    for attempt in range(1, GEMINI_RETRY_ATTEMPTS + 1):
        try:
            return client.models.generate_content(
                model=model_name,
                contents=_contents(messages),
                config=_followup_generate_config(messages),
            )
        except Exception as exc:
            if attempt >= GEMINI_RETRY_ATTEMPTS or not _gemini_retryable(exc):
                raise RuntimeError(
                    f"gemini follow-up request failed model={model_name} {gemini_error_diagnostics(exc)}"
                ) from None
            log.info("gemini_followup_retry status=%s attempt=%s", _retry_status_label(exc), attempt)
            _retry_sleep(_backoff_seconds(attempt))
    raise RuntimeError(f"gemini follow-up request failed model={model_name} status=unknown")


def gemini_followup_message(messages: list[AnyMessage]) -> AIMessage:
    """Ask the configured model for one message. Automatic tool execution stays off."""
    from google import genai

    api_key, model_name = _gemini_config()
    client = genai.Client(api_key=api_key, http_options=_gemini_http_options())
    return followup_message_from_response(_generate_with_retry(client, model_name, messages))


def gemini_error_diagnostics(exc: BaseException) -> str:
    """Describe a model failure without the key or request headers."""
    code = getattr(exc, "code", None)
    if not isinstance(code, int):
        code = getattr(exc, "status_code", None)
    status = code if isinstance(code, int) else "unknown"
    api_status = getattr(exc, "status", None)
    message = getattr(exc, "message", None)
    details = getattr(exc, "details", None)
    lines = [
        f"type={type(exc).__module__}.{type(exc).__name__}",
        f"status={status}",
        f"api_status={_redact(str(api_status or ''))}",
        f"message={_redact(str(message or ''))}",
        f"text={_redact(str(exc))}",
    ]
    if details is not None:
        lines.append(f"details={_redact(_compact(details))}")
    return " ".join(lines)


def followup_tool_schema() -> dict[str, Any]:
    """Return the function declaration sent with the model request."""
    return _declared_followup_tool().model_dump(exclude_none=True)


def describe_followup_contents(messages: list[AnyMessage]) -> list[dict[str, Any]]:
    """Return roles and part kinds in request order, without part values."""
    described: list[dict[str, Any]] = []
    for content in _contents(messages):
        parts: list[dict[str, Any]] = []
        for part in content.parts or []:
            if part.text:
                parts.append({"kind": "text"})
            function_call = part.function_call
            if function_call is not None and function_call.name:
                parts.append(
                    {
                        "kind": "function_call",
                        "name": function_call.name,
                        "arg_names": sorted((function_call.args or {}).keys()),
                        "has_id": bool(function_call.id),
                    }
                )
            function_response = part.function_response
            if function_response is not None and function_response.name:
                payload = function_response.response or {}
                parts.append(
                    {
                        "kind": "function_response",
                        "name": function_response.name,
                        "response_keys": sorted(payload.keys()) if isinstance(payload, dict) else [],
                        "has_id": bool(function_response.id),
                    }
                )
        described.append({"role": content.role, "parts": parts})
    return described


def _compact(value: object) -> str:
    try:
        return json.dumps(value, default=str, sort_keys=True)
    except TypeError:
        return str(value)


def _redact(text: str) -> str:
    secret = os.getenv("GEMINI_API_KEY", "").strip()
    if secret:
        text = text.replace(secret, "[redacted]")
    text = re.sub(r"AIza[0-9A-Za-z_\-]{10,}", "[redacted]", text)
    for header in ("authorization", "x-goog-api-key"):
        text = re.sub(
            rf"(?i)({header}\s*[:=]\s*)\S+",
            r"\1[redacted]",
            text,
        )
    return text


def _declared_followup_tool():
    from google.genai import types

    return types.Tool(
        function_declarations=[
            types.FunctionDeclaration(
                name=FOLLOWUP_TOOL,
                description="Read the patient and recent observations for one follow-up case.",
                parameters_json_schema={
                    "type": "object",
                    "properties": {"case_id": {"type": "string"}},
                    "required": ["case_id"],
                },
            )
        ]
    )


class GeminiFhirFollowUp:
    """Application boundary. The compiled graph does not own policy, audit, or HTTP."""

    def __init__(
        self,
        sink: InMemoryAuditSink,
        adapter,
        model: Model,
        *,
        clock: Callable[[], str],
        run_id: str,
        policy: Callable[[str], Any] = evaluate_tool_policy,
        audit: Callable[..., Any] = record_policy_audit,
    ) -> None:
        self.sink = sink
        self.adapter = adapter
        self.model = model
        self.clock = clock
        self.run_id = run_id
        self.policy = policy
        self.audit = audit
        self.model_calls = 0
        self.trace: list[str] = []
        self._status = ""
        self._reason = ""
        self.followup_tool = make_followup_tool(adapter)
        self.graph = self._compile()

    def prepare_node(self, state: GeminiFollowUpState) -> dict[str, object]:
        self.trace.append("prepare")
        _mark(f"prepare:{state['case_id']}")
        return {
            "messages": [
                HumanMessage(
                    content=(
                        f"Prepare follow-up for case {state['case_id']}. "
                        "Retrieve the patient context before answering."
                    )
                )
            ]
        }

    def agent_node(self, state: GeminiFollowUpState) -> dict[str, object]:
        self.trace.append("agent")
        turns = sum(isinstance(message, AIMessage) for message in state["messages"])
        if turns >= MAX_MODEL_TURNS:
            return {"decision": "limit", "final_answer": MODEL_LIMIT_ANSWER}
        if not state["messages"]:
            raise ValueError("agent requires the prepared request")
        self.model_calls += 1
        return {"messages": [self.model(state["messages"])], "turn": state["turn"] + 1}

    def route_after_agent(self, state: GeminiFollowUpState) -> str:
        """Authorize a proposed tool, record the verdict, then choose an edge."""
        if state["decision"] == "limit":
            return "finish"
        if not state["messages"]:
            raise ValueError("agent state cannot be routed")
        last = state["messages"][-1]
        if not isinstance(last, AIMessage):
            raise ValueError("agent state cannot be routed")
        if not last.tool_calls:
            return "finish"
        verdict = None
        for call in last.tool_calls:
            verdict = self.policy(call["name"])
            self.audit(
                self.sink,
                run_id=self.run_id,
                case_id=state["case_id"],
                tool_name=call["name"],
                decision=verdict.status,
                reason=verdict.reason,
                timestamp=self.clock(),
            )
            self._status = verdict.status
            self._reason = verdict.reason
            if verdict.status != "allowed":
                return "denied"
        if verdict is None or verdict.status != "allowed":
            raise ValueError("tool proposal was not authorized")
        return "tools"

    def denied_node(self, state: GeminiFollowUpState) -> dict[str, str]:
        del state
        self.trace.append("denied")
        if self._status != "denied":
            raise ValueError("denied path requires a denial")
        return {
            "decision": "denied",
            "policy_decision": self._status,
            "policy_reason": self._reason,
        }

    def update_state(self, state: GeminiFollowUpState) -> dict[str, object]:
        self.trace.append("update_state")
        if self._status != "allowed":
            raise ValueError("update_state requires an allowed tool")
        if not state["messages"] or not isinstance(state["messages"][-1], ToolMessage):
            raise ValueError("update_state requires a tool result")
        message = state["messages"][-1]
        if (message.name or "") != FOLLOWUP_TOOL:
            raise ValueError("unknown tool result")
        payload = _tool_payload(message.content)
        patient = payload.get("patient")
        observations = payload.get("observations")
        if not isinstance(patient, dict) or not isinstance(observations, list) or not observations:
            raise ValueError("tool result must include patient and observations")
        return {
            "decision": "allowed",
            "policy_decision": self._status,
            "policy_reason": self._reason,
            "patient": patient,
            "observations": observations,
            "evidence": [{"tool": FOLLOWUP_TOOL, "resources": _resource_refs(patient, observations)}],
            "tools_used": [FOLLOWUP_TOOL],
        }

    def finish_node(self, state: GeminiFollowUpState) -> dict[str, str]:
        self.trace.append("finish")
        if state["decision"] == "limit":
            return {"final_answer": MODEL_LIMIT_ANSWER, "decision": "limit"}
        if state["policy_decision"] == "denied":
            return {"final_answer": DENIAL_ANSWER, "decision": "denied"}
        last = state["messages"][-1]
        if not isinstance(last, AIMessage) or last.tool_calls or not str(last.content).strip():
            raise ValueError("finish requires a final model message")
        return {"decision": "finish", "final_answer": str(last.content)}

    def _compile(self):
        graph: StateGraph[GeminiFollowUpState] = StateGraph(GeminiFollowUpState)
        tools: list[BaseTool] = [self.followup_tool, send_message]
        graph.add_node("prepare", self.prepare_node)
        graph.add_node("agent", self.agent_node)
        graph.add_node("tools", ToolNode(tools, handle_tool_errors=False))
        graph.add_node("update_state", self.update_state)
        graph.add_node("denied", self.denied_node)
        graph.add_node("finish", self.finish_node)
        graph.add_edge(START, "prepare")
        graph.add_edge("prepare", "agent")
        graph.add_conditional_edges(
            "agent",
            self.route_after_agent,
            {"tools": "tools", "denied": "denied", "finish": "finish"},
        )
        graph.add_edge("tools", "update_state")
        graph.add_edge("update_state", "agent")
        graph.add_edge("denied", "finish")
        graph.add_edge("finish", END)
        return graph.compile()

    def invoke(self, case_id: str = PATIENT_CASE) -> GeminiFollowUpState:
        try:
            return self.graph.invoke(initial_state(case_id))
        except Exception as exc:
            found = _find_read_error(exc)
            if found is None or str(found) == "transport failed":
                raise
            return _unavailable(case_id)


def _unavailable(case_id: str) -> GeminiFollowUpState:
    stopped = initial_state(case_id)
    stopped["decision"] = "unavailable"
    stopped["final_answer"] = UNAVAILABLE_ANSWER
    return stopped


def build_gemini_fhir_followup(
    client,
    sink: InMemoryAuditSink,
    model: Model,
    *,
    clock: Callable[[], str],
    run_id: str,
    policy: Callable[[str], Any] = evaluate_tool_policy,
    audit: Callable[..., Any] = record_policy_audit,
) -> GeminiFhirFollowUp:
    """Wire the workflow to a read client and a model. The graph selects neither."""
    return GeminiFhirFollowUp(
        sink,
        FollowUpFHIRAdapter(ClientFHIRTransport(client)),
        model,
        clock=clock,
        run_id=run_id,
        policy=policy,
        audit=audit,
    )


def build_live_gemini_fhir_followup(
    sink: InMemoryAuditSink,
    *,
    clock: Callable[[], str],
    run_id: str,
    base_url: str | None = None,
) -> GeminiFhirFollowUp:
    """Compose the live model and the live read client outside the graph class."""
    return build_gemini_fhir_followup(
        HapiReadClient(base_url),
        sink,
        gemini_followup_message,
        clock=clock,
        run_id=run_id,
    )


__all__ = [
    "MAX_MODEL_TURNS",
    "MODEL_LIMIT_ANSWER",
    "SAFE_AUDIT_FIELDS",
    "GeminiFhirFollowUp",
    "build_gemini_fhir_followup",
    "build_live_gemini_fhir_followup",
    "describe_followup_contents",
    "followup_tool_schema",
    "gemini_error_diagnostics",
    "followup_message_from_response",
    "gemini_followup_message",
    "initial_state",
]
