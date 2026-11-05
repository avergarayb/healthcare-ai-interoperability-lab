"""Additive laboratory control-plane metadata; never an authentication adapter."""
from dataclasses import asdict, dataclass, fields
from datetime import datetime, timezone
from enum import Enum
import json
from typing import Protocol

from .models import ConnectorOperation, CredentialReference, Gate


class InstanceState(str, Enum):
    DRAFT = "DRAFT"
    PENDING_APPROVAL = "PENDING_APPROVAL"
    ACTIVE = "ACTIVE"
    SUSPENDED = "SUSPENDED"
    REVOKED = "REVOKED"
    OFFBOARDED = "OFFBOARDED"


class CredentialState(str, Enum):
    PENDING = "PENDING"
    ACTIVE = "ACTIVE"
    SUSPENDED = "SUSPENDED"
    REVOKED = "REVOKED"
    EXPIRED = "EXPIRED"
    REPLACED = "REPLACED"


@dataclass(frozen=True, slots=True, repr=False)
class AdministrativeContext:
    principal_id: str
    organization_id: str
    role: str
    expires_at: datetime
    actor_type: str = "synthetic_administrator"


class AdministrativeAuthority(Protocol):
    def recognizes(self, context: AdministrativeContext) -> bool: ...


@dataclass(frozen=True, slots=True)
class CredentialMetadata:
    reference: CredentialReference
    binding_id: str
    custody_ref: str
    review_due_at: datetime
    state: CredentialState = CredentialState.PENDING
    reference_type: str = "synthetic"


def utc(value: datetime) -> str:
    if not isinstance(value, datetime) or value.tzinfo is None or value.utcoffset() != timezone.utc.utcoffset(value):
        raise ValueError("UTC required")
    return value.isoformat().replace("+00:00", "Z")


def instant(value: str) -> datetime:
    if type(value) is not str or not value.endswith("Z"):
        raise ValueError("UTC timestamp required")
    result = datetime.fromisoformat(value.replace("Z", "+00:00"))
    utc(result)
    return result


def encode(record) -> str:
    def convert(value):
        if isinstance(value, datetime):
            return utc(value)
        if isinstance(value, Enum):
            return value.value
        if isinstance(value, frozenset):
            return sorted(convert(item) for item in value)
        if isinstance(value, dict):
            return {key: convert(item) for key, item in value.items()}
        return value
    return json.dumps(convert(asdict(record)), sort_keys=True, separators=(",", ":"), allow_nan=False)


def decode(record_type, payload):
    from .models import ConnectorDefinition, ExecutionLimits
    def unique_object(pairs):
        result = {}
        for key, value in pairs:
            if key in result:
                raise ValueError("duplicate field")
            result[key] = value
        return result
    data = json.loads(payload, object_pairs_hook=unique_object)
    if type(data) is not dict or set(data) != {f.name for f in fields(record_type)}:
        raise ValueError("closed record required")
    for key in ("expires_at",):
        if key in data:
            data[key] = instant(data[key])
    for key in ("operations", "gates", "purposes", "recipients", "classifications", "allowed_mimes"):
        if key in data:
            values = data[key]
            if type(values) is not list or len(values) != len(set(values)):
                raise ValueError("unique set required")
            transform = ConnectorOperation if key == "operations" else Gate if key == "gates" else str
            if any(type(v) is not str for v in values):
                raise ValueError("string set required")
            data[key] = frozenset(transform(v) for v in values)
    if record_type is ConnectorDefinition:
        if set(data["limits"]) != {f.name for f in fields(ExecutionLimits)}:
            raise ValueError("closed limits required")
        data["limits"] = ExecutionLimits(**data["limits"])
    return record_type(**data)
