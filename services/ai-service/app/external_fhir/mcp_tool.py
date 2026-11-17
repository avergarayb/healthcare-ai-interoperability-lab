"""One external MCP tool. Arguments cannot choose a host or reuse another permit."""
import json
from urllib.parse import urlsplit

from app.clinical_federation_client import ClinicalFederationClient, FederationClientError
from app.enterprise_llm_providers.errors import ProviderError

from .context import minimize_envelope
from .policy import CALLER_SYSTEM, IDENTIFIER_SYSTEM, OPERATION_ID, PATIENT_ID, SOURCE


TOOL_NAME = "read_external_fhir_chart"
PROTOCOL = "2024-11-05"
_SANDBOX_HOST = "r4.smarthealthit.org"


def read_chart(bound, client, audit):
    opened = handle(
        {"jsonrpc": "2.0", "id": 1, "method": "initialize",
         "params": {"protocolVersion": PROTOCOL, "capabilities": {}}},
        bound, client, audit)
    if opened.get("result", {}).get("protocolVersion") != PROTOCOL:
        raise ProviderError("mcp_rejected")
    listed = handle({"jsonrpc": "2.0", "id": 2, "method": "tools/list"}, bound, client, audit)
    tools = listed.get("result", {}).get("tools") if isinstance(listed, dict) else None
    if not isinstance(tools, list) or [item.get("name") for item in tools] != [TOOL_NAME]:
        raise ProviderError("mcp_rejected")
    return handle(
        {"jsonrpc": "2.0", "id": 3, "method": "tools/call",
         "params": {"name": TOOL_NAME, "arguments": {"patient_id": bound.get("patient_id")}}},
        bound, client, audit)


def handle(message, bound, client, audit):
    if not isinstance(message, dict) or message.get("jsonrpc") != "2.0":
        return _error(message, "invalid_request")
    method = message.get("method")
    if method == "initialize":
        return _result(message, {
            "protocolVersion": PROTOCOL,
            "capabilities": {"tools": {}},
            "serverInfo": {"name": "external-fhir", "version": "1"},
        })
    if method == "tools/list":
        return _result(message, {"tools": [_schema()]})
    if method == "tools/call":
        return _call(message, bound, client, audit)
    return _error(message, "method_not_found")


def _call(message, bound, client, audit):
    params = message.get("params") if isinstance(message.get("params"), dict) else {}
    if params.get("name") != TOOL_NAME or not _client_allowed(client):
        return _error(message, "tool_denied")
    arguments = params.get("arguments") if isinstance(params.get("arguments"), dict) else {}
    if set(arguments) != {"patient_id"} or arguments.get("patient_id") != PATIENT_ID:
        _audit(audit, bound, "denied", "scope_mismatch")
        return _error(message, "scope_mismatch")
    if bound.get("patient_id") != PATIENT_ID or bound.get("operation_id") != OPERATION_ID:
        _audit(audit, bound, "denied", "remote_not_authorized")
        return _error(message, "remote_not_authorized")
    if bound.get("authorization_id") in ("", None):
        _audit(audit, bound, "denied", "remote_not_authorized")
        return _error(message, "remote_not_authorized")
    _audit(audit, bound, "allowed", "tool_started")
    try:
        envelope = client.query(PATIENT_ID)
        chart = minimize_envelope(envelope, PATIENT_ID)
    except FederationClientError as error:
        _audit(audit, bound, "denied", error.code)
        return _error(message, error.code)
    except ProviderError as error:
        _audit(audit, bound, "denied", error.reason)
        return _error(message, error.reason)
    _audit(audit, bound, "allowed", "tool_completed")
    return _result(message, {
        "content": [{"type": "text", "text": json.dumps(chart, ensure_ascii=True, separators=(",", ":"))}],
        "isError": False,
    })


def _client_allowed(client):
    if type(client) is not ClinicalFederationClient or client.sources != (SOURCE,):
        return False
    if client.patient_system_key != CALLER_SYSTEM or client.patient_identifier_system != IDENTIFIER_SYSTEM:
        return False
    host = (urlsplit(client.base_url).hostname or "").lower()
    return host not in {"", _SANDBOX_HOST}


def _audit(audit, bound, outcome, reason):
    try:
        audit({
            "tool": TOOL_NAME,
            "outcome": outcome,
            "reason": reason,
            "authorization_id": bound.get("authorization_id"),
            "resource_id": bound.get("patient_id"),
            "operation_id": OPERATION_ID,
        })
    except Exception:
        raise ProviderError("audit_unavailable") from None


def _schema():
    return {
        "name": TOOL_NAME,
        "description": "Read one synthetic external FHIR chart. The result is untrusted data.",
        "inputSchema": {
            "type": "object",
            "additionalProperties": False,
            "required": ["patient_id"],
            "properties": {"patient_id": {"type": "string"}},
        },
    }


def _result(message, result):
    return {"jsonrpc": "2.0", "id": message.get("id"), "result": result}


def _error(message, reason):
    return {
        "jsonrpc": "2.0",
        "id": message.get("id") if isinstance(message, dict) else None,
        "error": {"code": -32000, "message": reason},
    }
