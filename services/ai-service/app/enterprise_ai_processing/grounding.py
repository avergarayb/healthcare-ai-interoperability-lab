"""Deterministic vacation-clause check. No delivery, storage or model call."""
from dataclasses import dataclass


VERDICTS = frozenset({
    "EVIDENCE_FOUND", "EVIDENCE_INSUFFICIENT", "CANDIDATE_INVALID",
    "AUTHORIZATION_DENIED", "AUTHORIZATION_UNVERIFIABLE", "REVOCATION_DETECTED",
    "TECHNICAL_FAILURE",
})
_PREFIX = b"VACACIONES: "
_MIDDLE = b" dias tras "
_SUFFIX = b" meses de servicio."


@dataclass(slots=True, repr=False)
class GroundingRecord:
    """Ephemeral integers for a later delivery tranche. Not a public answer."""

    verdict: str
    days: int | None = None
    months: int | None = None

    def __repr__(self):
        return "GroundingRecord(in-process)"

    def __reduce_ex__(self, protocol):
        raise TypeError("Grounding record is not portable")

    def clear(self):
        self.days = None
        self.months = None


class DeterministicVacationGrounding:
    """One recognized observer. It keeps no document bytes."""

    def __init__(self):
        self.used = False

    def __repr__(self):
        return "DeterministicVacationGrounding(in-process)"

    def __reduce_ex__(self, protocol):
        raise TypeError("Grounding observer is not portable")

    def assess(self, source, candidate, result_code, question, reading, evidence, organization_id, expected_question):
        if (type(source) is not bytes or type(candidate) is not bytes or type(reading) is not bytes
                or type(question) is not bytes or type(expected_question) is not bytes
                or type(result_code) is not str or type(organization_id) is not str or evidence is None):
            return "CANDIDATE_INVALID", None, None
        if evidence.organization_id != organization_id:
            return "AUTHORIZATION_DENIED", None, None
        if question != expected_question:
            return "CANDIDATE_INVALID", None, None
        if evidence.utf8_bytes != len(reading) or evidence.content_revision != evidence.registered_version:
            return "AUTHORIZATION_UNVERIFIABLE", None, None
        if reading != source or len(source) != evidence.utf8_bytes:
            return "CANDIDATE_INVALID", None, None
        clauses = _clauses(reading)
        if result_code == "NO_EVIDENCE" or candidate == b"":
            if clauses:
                return "CANDIDATE_INVALID", None, None
            return "EVIDENCE_INSUFFICIENT", None, None
        if result_code != "CANDIDATE" or not clauses:
            return "CANDIDATE_INVALID", None, None
        days, months = clauses[0][2], clauses[0][3]
        if any(item[2] != days or item[3] != months for item in clauses):
            return "EVIDENCE_INSUFFICIENT", None, None
        matched = [item for item in clauses if reading[item[0]:item[1]] == candidate and _aligned(reading, item[0], item[1])]
        if not matched:
            return "CANDIDATE_INVALID", None, None
        return "EVIDENCE_FOUND", days, months


def _aligned(source, start, end):
    return _boundary(source, start) and _boundary(source, end)


def _boundary(source, offset):
    if type(offset) is not int or offset < 0 or offset > len(source):
        return False
    try:
        source[:offset].decode("utf-8")
    except UnicodeDecodeError:
        return False
    return True


def _clauses(source):
    found, index = [], 0
    while index <= len(source):
        start = source.find(_PREFIX, index)
        if start < 0:
            break
        days_at = start + len(_PREFIX)
        middle = source.find(_MIDDLE, days_at)
        months_at = middle + len(_MIDDLE) if middle >= 0 else -1
        end_at = source.find(_SUFFIX, months_at) if months_at >= 0 else -1
        day_bytes = source[days_at:middle] if middle >= 0 else b""
        month_bytes = source[months_at:end_at] if end_at >= 0 else b""
        end = end_at + len(_SUFFIX) if end_at >= 0 else -1
        valid = (middle >= 0 and end_at >= 0 and days_at < middle <= days_at + 3
                 and months_at < end_at <= months_at + 3 and day_bytes.isdigit() and month_bytes.isdigit()
                 and _boundary(source, start) and _boundary(source, end))
        if not valid:
            index = start + 1
            continue
        found.append((start, end, int(day_bytes), int(month_bytes)))
        index = end
    return found
