"""Offline dry-run for the fixed Gemini fixture. It cannot select the SDK transport."""
import json

from .errors import ProviderError
from .gemini_adapter import GeminiResponsesAdapter
from .gemini_configuration import GeminiSettings
from .gemini_permit import GeminiExecutionPermit
from .permit import CLASSIFICATION, PURPOSE
from .schema import QUESTION_ID
from .smoke import (
    FIXED_DOCUMENT, FIXED_INSTANCE, FIXED_ORGANIZATION, FIXED_PRINCIPAL, FIXED_RESOURCE,
    SyntheticRead,
)


class _ScriptedTransport:
    def __init__(self, body):
        self.body = body
        self.calls = 0

    def send(self, generation, timeout_seconds):
        self.calls += 1
        return self.body


def dry_run_fixed_fixture(clock, scripted_body):
    if type(scripted_body) is not dict or not callable(clock):
        raise ProviderError("invalid_input")
    now = clock()
    settings = GeminiSettings(True, "gemini-3.5-flash-lite", 15, 128, 2048, 1_000, "dry-run")
    permit = GeminiExecutionPermit(
        FIXED_ORGANIZATION, FIXED_PRINCIPAL, FIXED_INSTANCE, FIXED_RESOURCE,
        PURPOSE, CLASSIFICATION, "gemini", "gemini-3.5-flash-lite", QUESTION_ID, 1,
        now, _later(now), True)
    reading = SyntheticRead(
        FIXED_ORGANIZATION, FIXED_PRINCIPAL, FIXED_INSTANCE, FIXED_RESOURCE,
        PURPOSE, CLASSIFICATION, QUESTION_ID, FIXED_DOCUMENT.encode("utf-8"))
    return GeminiResponsesAdapter(settings, _ScriptedTransport(scripted_body), clock).observe(reading, permit)


def simulated_success():
    encoded = FIXED_DOCUMENT.encode("utf-8")
    observation = {
        "question_id": QUESTION_ID, "evidence_found": True, "proposed_days": 20, "proposed_months": 12,
        "source_excerpt": FIXED_DOCUMENT, "evidence_start": 0, "evidence_end": len(encoded),
        "refusal_or_insufficient": False,
    }
    return {
        "status": "completed",
        "output": [{"type": "message", "content": [{"type": "output_text", "text": json.dumps(observation)}]}],
        "usage": {"input_tokens": 40, "output_tokens": 20},
    }


def _later(now):
    from datetime import timedelta
    return now + timedelta(minutes=5)
