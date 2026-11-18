"""One longitudinal MCP tool. Arguments cannot choose an organization, host, or jurisdiction."""
import json
from urllib.parse import urlsplit

from app.clinical_federation_client import ClinicalFederationClient, FederationClientError
from app.enterprise_llm_providers.errors import ProviderError
from app.jurisdiction_lab.profile import CALLER_ORGANIZATION, CALLER_SYSTEM

from .compare import collect_observations
from .series import OPERATION_ID, series_for


TOOL_NAME = "read_longitudinal_lab_chart"
PROTOCOL = "2024-11-05"


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
            "serverInfo": {"name": "longitudinal-lab", "version": "1"},
        })
    if method == "tools/list":
        return _result(message, {"tools": [_schema()]})
    if method == "tools/call":
        return _call(message, bound, client, audit)
    return _error(message, "method_not_found")


def _call(message, bound, client, audit):
    profile = bound.get("profile")
    series = series_for(profile) if profile is not None else None
    params = message.get("params") if isinstance(message.get("params"), dict) else {}
    if params.get("name") != TOOL_NAME or series is None:
        return _error(message, "tool_denied")
    arguments = params.get("arguments") if isinstance(params.get("arguments"), dict) else {}
    if set(arguments) != {"patient_id"} or arguments.get("patient_id") != profile.patient_value:
        _audit(audit, bound, "denied", "scope_mismatch")
        return _error(message, "scope_mismatch")
    if not _client_allowed(client, profile):
        return _error(message, "tool_denied")
    if (bound.get("patient_id") != profile.patient_value or bound.get("operation_id") != OPERATION_ID
            or bound.get("authorization_id") != series.authorization_id):
        _audit(audit, bound, "denied", "remote_not_authorized")
        return _error(message, "remote_not_authorized")
    _audit(audit, bound, "allowed", "tool_started")
    try:
        envelope = client.query(profile.patient_value)
        observations = collect_observations(envelope, profile)
    except FederationClientError as error:
        _audit(audit, bound, "denied", error.code)
        return _error(message, error.code)
    except ProviderError as error:
        _audit(audit, bound, "denied", error.reason)
        return _error(message, error.reason)
    _audit(audit, bound, "allowed", "tool_completed")
    payload = {
        "operation_id": OPERATION_ID,
        "profile_id": profile.profile_id,
        "observations": observations,
    }
    return _result(message, {
        "content": [{"type": "text", "text": json.dumps(payload, ensure_ascii=True, separators=(",", ":"))}],
        "isError": False,
    })


def _client_allowed(client, profile):
    if type(client) is not ClinicalFederationClient or profile is None:
        return False
    if client.organization_id != CALLER_ORGANIZATION or client.patient_system_key != CALLER_SYSTEM:
        return False
    if client.patient_identifier_system != profile.patient_system or client.sources != (profile.source_key,):
        return False
    host = urlsplit(client.base_url).hostname or ""
    return host in {"127.0.0.1", "localhost"}


def _schema():
    return {
        "name": TOOL_NAME,
        "description": "Read the dated synthetic series for the server-selected patient.",
        "inputSchema": {
            "type": "object",
            "additionalProperties": False,
            "required": ["patient_id"],
            "properties": {"patient_id": {"type": "string"}},
        },
    }


def _audit(audit, bound, outcome, reason):
    if audit is None:
        return
    audit({
        "tool": TOOL_NAME,
        "outcome": outcome,
        "reason": reason,
        "authorization_id": bound.get("authorization_id") or "",
        "patient_id": bound.get("patient_id") or "",
    })


def _result(message, result):
    return {"jsonrpc": "2.0", "id": message.get("id"), "result": result}


def _error(message, code):
    return {"jsonrpc": "2.0", "id": message.get("id") if isinstance(message, dict) else None,
            "error": {"code": -32000, "message": code}}
