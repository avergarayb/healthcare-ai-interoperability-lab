"""Model chart for one comparison. The text cannot replace the calculated difference."""
import json

from app.enterprise_llm_providers.errors import ProviderError

from .compare import _CHART_KEYS
from .series import OPERATION_ID


_DENIED = ("diagnos", "tratamient", "alerta", "patolog", "peligro", "mejor", "peor")


def require_model_context(chart, profile):
    if not isinstance(chart, dict) or set(chart) != _CHART_KEYS:
        raise ProviderError("context_rejected")
    if (chart["operation_id"] != OPERATION_ID or chart["profile_id"] != profile.profile_id
            or chart["profile_version"] != profile.version or chart["validation_class"] != "internal-demo-rules"
            or chart["official_conformance"] is not False or chart["jurisdiction"] != profile.jurisdiction
            or chart["source"] != profile.source_key or chart["comparability"] != "verified"):
        raise ProviderError("context_rejected")
    rendered = json.dumps(chart, ensure_ascii=True)
    if "name" in rendered or "official-conformance" in rendered:
        raise ProviderError("context_rejected")
    return chart


def validate_summary(chart, parsed, profile):
    if not isinstance(parsed, dict) or set(parsed) != {"kind", "statements", "review"}:
        raise ProviderError("invalid_output")
    if parsed["kind"] != OPERATION_ID or parsed["review"] != "pending_human_review":
        raise ProviderError("invalid_output")
    statements = parsed["statements"]
    if not isinstance(statements, list) or len(statements) != 1:
        raise ProviderError("invalid_output")
    item = statements[0]
    if not isinstance(item, dict) or set(item) != {"text", "sources"}:
        raise ProviderError("invalid_output")
    text = item["text"]
    if type(text) is not str or text.strip() == "" or len(text) > 400:
        raise ProviderError("invalid_output")
    required = (
        chart["prior_value"], chart["recent_value"], chart["unit"],
        chart["prior_date"][:10], chart["recent_date"][:10],
        chart["prior_reference"], chart["recent_reference"],
    )
    if any(token not in text for token in required):
        raise ProviderError("invalid_output")
    if chart["absolute_difference"] == "0":
        if "diferencia 0" not in text:
            raise ProviderError("invalid_output")
    elif chart["absolute_difference"] not in text:
        raise ProviderError("invalid_output")
    if chart["percent_difference"] == "0":
        if "porcentaje 0" not in text:
            raise ProviderError("invalid_output")
    elif chart["percent_difference"] not in text:
        raise ProviderError("invalid_output")
    if any(word in text.lower() for word in _DENIED):
        raise ProviderError("invalid_output")
    sources = item["sources"]
    if not isinstance(sources, list) or len(sources) != 2:
        raise ProviderError("invalid_output")
    cited = set()
    kept = []
    for source in sources:
        if not isinstance(source, dict) or set(source) != {"source", "resourceType", "id"}:
            raise ProviderError("invalid_output")
        if source["source"] != profile.source_key or source["resourceType"] != "Observation":
            raise ProviderError("invalid_output")
        if source["id"] not in {chart["prior_reference"], chart["recent_reference"]} or source["id"] in cited:
            raise ProviderError("invalid_output")
        cited.add(source["id"])
        kept.append({"source": profile.source_key, "resourceType": "Observation", "id": source["id"]})
    if cited != {chart["prior_reference"], chart["recent_reference"]}:
        raise ProviderError("invalid_output")
    return {"kind": OPERATION_ID, "review": "pending_human_review", "statements": [{"text": text, "sources": kept}]}
