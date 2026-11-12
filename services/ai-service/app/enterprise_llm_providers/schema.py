"""Strict Structured Outputs schema for one synthetic vacation observation.

The schema constrains shape. It does not establish that a number is true.
"""

SCHEMA_NAME = "vacation_clause_observation"
QUESTION_ID = "vacation-days-v1"
NULLABLE_INTEGER = {"anyOf": [{"type": "integer"}, {"type": "null"}]}

RESPONSE_SCHEMA = {
    "type": "object",
    "additionalProperties": False,
    "properties": {
        "question_id": {"type": "string", "enum": [QUESTION_ID]},
        "evidence_found": {"type": "boolean"},
        "proposed_days": NULLABLE_INTEGER,
        "proposed_months": NULLABLE_INTEGER,
        "source_excerpt": {"type": "string"},
        "evidence_start": NULLABLE_INTEGER,
        "evidence_end": NULLABLE_INTEGER,
        "refusal_or_insufficient": {"type": "boolean"},
    },
    "required": [
        "question_id", "evidence_found", "proposed_days", "proposed_months",
        "source_excerpt", "evidence_start", "evidence_end", "refusal_or_insufficient",
    ],
}
