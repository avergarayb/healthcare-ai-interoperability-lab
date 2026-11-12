"""In-memory remote-execution permit. This is not a ledger grant and is not stored."""
from dataclasses import dataclass
from datetime import datetime

from .configuration import ALLOWED_MODEL
from .schema import QUESTION_ID


PROVIDER = "openai"
PURPOSE = "synthetic-policy-question-answering"
CLASSIFICATION = "synthetic-internal"


@dataclass(frozen=True, slots=True, repr=False)
class RemoteExecutionPermit:
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
        return "RemoteExecutionPermit(in-process)"


@dataclass(frozen=True, slots=True, repr=False)
class SyntheticRead:
    organization_id: str
    principal_id: str
    instance_id: str
    resource_id: str
    purpose: str
    classification: str
    question_id: str
    document: bytes

    def __repr__(self):
        return "SyntheticRead(in-process)"


def permit_matches(permit, reading, now):
    if (permit is None or type(permit) is not RemoteExecutionPermit or type(reading) is not SyntheticRead
            or type(now) is not datetime or permit.enabled is not True):
        return False
    if not (permit.valid_from <= now < permit.expires_at):
        return False
    return (permit.organization_id == reading.organization_id
            and permit.principal_id == reading.principal_id
            and permit.instance_id == reading.instance_id
            and permit.resource_id == reading.resource_id
            and permit.purpose == reading.purpose == PURPOSE
            and permit.classification == reading.classification == CLASSIFICATION
            and permit.provider == PROVIDER and permit.model_id == reading_model(permit)
            and permit.question_id == reading.question_id == QUESTION_ID
            and type(permit.authorization_revision) is int and permit.authorization_revision >= 1)


def reading_model(permit):
    return ALLOWED_MODEL if permit.model_id == ALLOWED_MODEL else ""
