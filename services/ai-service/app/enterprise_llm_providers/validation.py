"""Independent check of a structured observation against the original bytes."""
import json
from dataclasses import dataclass

from .configuration import ALLOWED_MODEL
from .errors import ProviderError
from .schema import QUESTION_ID


_PREFIX = "VACACIONES: "
_MIDDLE = " dias tras "
_SUFFIX = " meses de servicio."
_FIELDS = (
    "question_id", "evidence_found", "proposed_days", "proposed_months",
    "source_excerpt", "evidence_start", "evidence_end", "refusal_or_insufficient",
)


@dataclass(frozen=True, slots=True, repr=False)
class CheckedObservation:
    days: int
    months: int

    def __repr__(self):
        return "CheckedObservation(in-process)"


def parse_output(body):
    if type(body) is not dict:
        raise ProviderError("invalid_output")
    if "model" in body and body.get("model") != ALLOWED_MODEL:
        raise ProviderError("model_denied")
    status = body.get("status")
    if status == "incomplete":
        raise ProviderError("incomplete_output")
    error = body.get("error")
    if type(error) is dict:
        code = error.get("code")
        if code == "rate_limit_exceeded":
            raise ProviderError("rate_limited")
        raise ProviderError("remote_unavailable")
    if status != "completed":
        raise ProviderError("incomplete_output")
    text = _output_text(body.get("output"))
    try:
        parsed = json.loads(text)
    except (TypeError, ValueError):
        raise ProviderError("invalid_output") from None
    if type(parsed) is not dict or set(parsed) != set(_FIELDS):
        raise ProviderError("invalid_output")
    return parsed


def usage_tokens(body):
    usage = body.get("usage") if type(body) is dict else None
    if type(usage) is not dict:
        return None
    incoming, outgoing = usage.get("input_tokens"), usage.get("output_tokens")
    if type(incoming) is not int or type(outgoing) is not int or incoming < 0 or outgoing < 0:
        return None
    return incoming, outgoing


def check_observation(source, parsed):
    if type(source) is not bytes or type(parsed) is not dict:
        raise ProviderError("invalid_output")
    if (parsed["question_id"] != QUESTION_ID or type(parsed["evidence_found"]) is not bool
            or type(parsed["refusal_or_insufficient"]) is not bool or type(parsed["source_excerpt"]) is not str):
        raise ProviderError("invalid_output")
    if parsed["refusal_or_insufficient"] or not parsed["evidence_found"]:
        raise ProviderError("model_refusal")
    start, end = parsed["evidence_start"], parsed["evidence_end"]
    days, months = parsed["proposed_days"], parsed["proposed_months"]
    if not _offset(start) or not _offset(end):
        raise ProviderError("invalid_offset")
    if not _whole(days) or not _whole(months):
        raise ProviderError("invalid_output")
    clauses = _clauses(source)
    pairs = {(item[2], item[3]) for item in clauses}
    if len(pairs) > 1:
        raise ProviderError("contradictory_source")
    if len(clauses) != 1:
        raise ProviderError("candidate_rejected")
    clause_start, clause_end, clause_days, clause_months = clauses[0]
    try:
        excerpt = parsed["source_excerpt"].encode("utf-8")
    except UnicodeError:
        raise ProviderError("invalid_output") from None
    if not _boundary(source, start) or not _boundary(source, end) or start >= end or end > len(source):
        raise ProviderError("invalid_offset")
    if source[start:end] != excerpt or (start, end) != (clause_start, clause_end):
        raise ProviderError("excerpt_mismatch")
    if (days, months) != (clause_days, clause_months):
        raise ProviderError("candidate_rejected")
    return CheckedObservation(days, months)


def _output_text(output):
    if type(output) is not list or output == []:
        raise ProviderError("invalid_output")
    texts = []
    for item in output:
        if type(item) is not dict or item.get("type") != "message":
            raise ProviderError("invalid_output")
        content = item.get("content")
        if type(content) is not list:
            raise ProviderError("invalid_output")
        for part in content:
            if type(part) is not dict:
                raise ProviderError("invalid_output")
            if part.get("type") == "refusal":
                raise ProviderError("model_refusal")
            if part.get("type") == "output_text" and type(part.get("text")) is str:
                texts.append(part["text"])
            else:
                raise ProviderError("invalid_output")
    if len(texts) != 1 or texts[0] == "":
        raise ProviderError("incomplete_output")
    return texts[0]


def _whole(value):
    return type(value) is int and not isinstance(value, bool) and 0 <= value <= 999


def _offset(value):
    return type(value) is int and not isinstance(value, bool) and value >= 0


def _boundary(source, offset):
    if offset > len(source):
        return False
    try:
        source[:offset].decode("utf-8")
    except UnicodeDecodeError:
        return False
    return True


def _clauses(source):
    text = source.decode("utf-8")
    found, index = [], 0
    while index <= len(text):
        start = text.find(_PREFIX, index)
        if start < 0:
            break
        days_at = start + len(_PREFIX)
        middle = text.find(_MIDDLE, days_at)
        months_at = middle + len(_MIDDLE) if middle >= 0 else -1
        suffix = text.find(_SUFFIX, months_at) if months_at >= 0 else -1
        day_text = text[days_at:middle] if middle >= 0 else ""
        month_text = text[months_at:suffix] if suffix >= 0 else ""
        end = suffix + len(_SUFFIX) if suffix >= 0 else -1
        valid = (middle >= 0 and suffix >= 0 and days_at < middle <= days_at + 3
                 and months_at < suffix <= months_at + 3 and day_text.isdigit() and month_text.isdigit())
        if not valid:
            index = start + 1
            continue
        byte_start = len(text[:start].encode("utf-8"))
        byte_end = len(text[:end].encode("utf-8"))
        found.append((byte_start, byte_end, int(day_text), int(month_text)))
        index = end
    return found
