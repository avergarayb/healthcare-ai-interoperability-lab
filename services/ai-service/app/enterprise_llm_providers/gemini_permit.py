"""In-memory Gemini permit. It is not stored and does not authorize OpenAI."""
from dataclasses import dataclass
from datetime import datetime

from .gemini_configuration import ALLOWED_MODEL
from .permit import CLASSIFICATION, PURPOSE
from .schema import QUESTION_ID


PROVIDER = "gemini"


@dataclass(frozen=True, slots=True, repr=False)
class GeminiExecutionPermit:
    organization_id: str
    principal_id: str
    instance_id: str
    resource_id: str
    purpose: str
    classification: str
    provider: str
    model_id: str
    question_id: str
    authorization_revision: int
    valid_from: datetime
    expires_at: datetime
    enabled: bool = True

    def __repr__(self):
        return "GeminiExecutionPermit(in-process)"


def gemini_permit_matches(permit, reading, now):
    if (permit is None or type(permit) is not GeminiExecutionPermit or type(now) is not datetime
            or permit.enabled is not True or not (permit.valid_from <= now < permit.expires_at)):
        return False
    return (permit.organization_id == reading.organization_id
            and permit.principal_id == reading.principal_id
            and permit.instance_id == reading.instance_id
            and permit.resource_id == reading.resource_id
            and permit.purpose == reading.purpose == PURPOSE
            and permit.classification == reading.classification == CLASSIFICATION
            and permit.provider == PROVIDER and permit.model_id == ALLOWED_MODEL
            and permit.question_id == reading.question_id == QUESTION_ID
            and type(permit.authorization_revision) is int and permit.authorization_revision >= 1)
