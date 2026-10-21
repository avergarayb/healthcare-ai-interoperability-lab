"""Operational narrative for one matched missed-follow-up review case.

The text is produced from appointment facts already read by the protocol.
This module does not evaluate the protocol and does not import the follow-up workflow.
"""

from __future__ import annotations

import json
from dataclasses import dataclass

from app.followup_review import validate_narrative_text
from app.missed_follow_up_review import REASON_MISSED


MAX_OUTPUT_TOKENS = 1024
NARRATIVE_INSTRUCTION = "\n".join(
    (
        "You write one operational review proposal for a missed follow-up appointment.",
        "Write answer in clear Spanish for health professionals in Peru and Latin America.",
        "Use only the appointment facts in the input.",
        "Keep FHIR resource identifiers unchanged.",
        "Describe the evidence that was read and its limits.",
        "State that the responsible professional reviews the case.",
        "Do not diagnose.",
        "Do not recommend treatment.",
        "Do not assign clinical urgency.",
        "Do not order a message, a call, or any other communication.",
        "Do not select an operational outcome.",
        "Do not state that follow-up is unnecessary.",
        "Return JSON with answer and no other decision.",
    )
)
NARRATIVE_SCHEMA = {
    "type": "object",
    "additionalProperties": False,
    "required": ["answer"],
    "properties": {
        "answer": {"type": "string", "minLength": 1, "maxLength": 4000},
    },
}


@dataclass(frozen=True)
class NarrativeGeneration:
    text: str | None
    reason: str | None


def configured_provider(settings):
    """Use the configured generation provider when both values exist."""
    if not settings.gemini_api_key or not settings.gemini_model:
        return None
    from app.gemini_provider import GeminiProvider

    return GeminiProvider(api_key=settings.gemini_api_key, model=settings.gemini_model)


def appointment_facts(views: object) -> list[dict[str, str | None]]:
    """Status, start, and reference for appointments already read. Nothing else."""
    if not isinstance(views, list) and not isinstance(views, tuple):
        return []
    facts: list[dict[str, str | None]] = []
    for view in views:
        if not isinstance(view, dict):
            continue
        appointment_id = view.get("id")
        if not isinstance(appointment_id, str) or not appointment_id:
            continue
        status = view.get("status")
        start = view.get("start")
        facts.append(
            {
                "reference": f"Appointment/{appointment_id}",
                "status": status if isinstance(status, str) else "",
                "start": start if isinstance(start, str) else None,
            }
        )
    return facts


def generate_operational_narrative(
    provider,
    *,
    matched_resource: str,
    appointments: list[dict[str, str | None]],
) -> NarrativeGeneration:
    """One structured generation. Provider failures stay explicit and are not stored."""
    payload = json.dumps(
        {
            "reasonCode": REASON_MISSED,
            "matchedResource": matched_resource,
            "retrievedAppointments": appointments,
        },
        ensure_ascii=False,
        sort_keys=True,
        separators=(",", ":"),
    )
    try:
        generation = provider.generate_structured(
            system_instruction=NARRATIVE_INSTRUCTION,
            contents=payload,
            response_json_schema=NARRATIVE_SCHEMA,
            max_output_tokens=MAX_OUTPUT_TOKENS,
        )
    except Exception:
        return NarrativeGeneration(text=None, reason="provider_unavailable")
    if generation.error or not isinstance(generation.text, str):
        return NarrativeGeneration(text=None, reason="provider_unavailable")
    answer = _answer(generation.text)
    if answer is None:
        return NarrativeGeneration(text=None, reason="invalid_output")
    return NarrativeGeneration(text=answer, reason=None)


def _answer(text: str) -> str | None:
    try:
        parsed = json.loads(text)
    except json.JSONDecodeError:
        return None
    if not isinstance(parsed, dict):
        return None
    answer = parsed.get("answer")
    if not isinstance(answer, str):
        return None
    try:
        return validate_narrative_text(answer)
    except ValueError:
        return None
