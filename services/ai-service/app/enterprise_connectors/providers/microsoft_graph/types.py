"""Closed offline protocol types, not Microsoft credentials or local grants."""
from dataclasses import dataclass, field
from datetime import datetime
import re
from typing import Protocol

from ...models import ConnectorFailure, ConnectorOperation as Op, Reason

ORIGIN = "https://graph.microsoft.com"
SELECT = "id,size,eTag,parentReference,file,folder"
SEGMENT = re.compile(r"[A-Za-z0-9!_.-]{1,160}\Z")
SELECTED = frozenset({"Sites.Selected", "Lists.SelectedOperations.Selected",
                      "ListItems.SelectedOperations.Selected", "Files.SelectedOperations.Selected"})


def reject(reason=Reason.TRANSPORT):
    return ConnectorFailure(reason, unavailable=True)


def segment(value):
    if type(value) is not str or not SEGMENT.fullmatch(value) or value in {".", ".."}:
        raise reject()
    return value


@dataclass(frozen=True, slots=True)
class GraphPermissionProfile:
    permission: str = "Files.SelectedOperations.Selected"
    role: str = "read"
    mode: str = "application"
    api_version: str = "v1.0"
    cloud: str = "global"

    def validate(self):
        if (self.permission not in SELECTED or self.role != "read" or self.mode != "application"
                or self.api_version != "v1.0" or self.cloud != "global"):
            raise reject(Reason.GRANT)


@dataclass(frozen=True, slots=True)
class GraphResourceIdentity:
    organization_id: str
    instance_id: str
    resource_id: str
    tenant_id: str
    drive_id: str
    item_id: str
    parent_item_id: str | None
    resource_type: str
    resource_version: int
    e_tag: str
    site_id: str | None = None
    drive_type: str = "documentLibrary"
    provider: str = "microsoft-graph"
    cloud: str = "global"
    # Explicit offline projection; NOT a real Graph binding admitted by TASK 003.
    policy_provider: str = "synthetic-documents"
    policy_cloud: str = "synthetic"

    def __post_init__(self):
        for value in (self.organization_id, self.instance_id, self.resource_id, self.tenant_id,
                      self.drive_id, self.item_id):
            segment(value)
        if self.parent_item_id is not None:
            segment(self.parent_item_id)
        if (self.provider != "microsoft-graph" or self.cloud != "global"
                or (self.policy_provider, self.policy_cloud) != ("synthetic-documents", "synthetic")
                or self.drive_type not in {"business", "documentLibrary"}
                or self.resource_type not in {"folder", "document"}
                or type(self.resource_version) is not int or self.resource_version < 1
                or type(self.e_tag) is not str or not re.fullmatch(r'[A-Za-z0-9"!_.-]{1,128}', self.e_tag)
                or (self.site_id is not None and (type(self.site_id) is not str
                    or not re.fullmatch(r"[A-Za-z0-9.,-]{1,200}", self.site_id)))
                or (self.drive_type == "documentLibrary" and self.site_id is None)):
            raise reject(Reason.RESOURCE)


class GraphCatalog:
    """Trusted test composition mapping; entries never create policy resources/grants."""
    def __init__(self, identities):
        if type(identities) is not tuple or not 1 <= len(identities) <= 1024:
            raise reject(Reason.RESOURCE)
        if any(type(i) is not GraphResourceIdentity for i in identities):
            raise reject(Reason.RESOURCE)
        keys = {(i.organization_id, i.instance_id, i.resource_id) for i in identities}
        external = {(i.organization_id, i.instance_id, i.drive_id, i.item_id) for i in identities}
        if len(keys) != len(identities) or len(external) != len(identities):
            raise reject(Reason.RESOURCE)
        self.identities = identities

    def resolve(self, resource, snapshot):
        found = [i for i in self.identities if (i.organization_id, i.instance_id, i.resource_id)
                 == (resource.organization_id, resource.instance_id, resource.resource_id)]
        if len(found) != 1:
            raise reject(Reason.RESOURCE)
        i = found[0]
        if ((i.tenant_id, i.item_id, i.resource_type, i.resource_version, i.policy_provider, i.policy_cloud)
                != (resource.tenant_id, resource.external_id, resource.resource_type, resource.version,
                    resource.provider, resource.cloud) or not resource.enabled or resource.kind != "registered"):
            raise reject(Reason.RESOURCE)
        if resource.parent_id is None:
            if i.parent_item_id is not None:
                raise reject(Reason.RESOURCE)
        else:
            parents = [p for p in snapshot.resources if p.resource_id == resource.parent_id
                       and p.organization_id == resource.organization_id and p.instance_id == resource.instance_id
                       and p.enabled and p.resource_type == "folder"]
            parent_ids = [p for p in self.identities if parents and p.resource_id == parents[0].resource_id
                          and (p.organization_id, p.instance_id) == (i.organization_id, i.instance_id)]
            if (len(parents) != 1 or len(parent_ids) != 1 or parent_ids[0].item_id != i.parent_item_id
                    or (parent_ids[0].drive_id, parent_ids[0].site_id, parent_ids[0].tenant_id)
                    != (i.drive_id, i.site_id, i.tenant_id)):
                raise reject(Reason.RESOURCE)
        return i

    def child(self, item_id, parent, snapshot):
        candidates = [r for r in snapshot.resources if r.external_id == item_id
                      and (r.organization_id, r.instance_id, r.parent_id)
                      == (parent.organization_id, parent.instance_id, parent.resource_id)]
        if len(candidates) != 1:
            raise reject(Reason.RESOURCE)
        child = self.resolve(candidates[0], snapshot)
        if (child.drive_id, child.site_id, child.tenant_id) != (parent.drive_id, parent.site_id, parent.tenant_id):
            raise reject(Reason.RESOURCE)
        return child


@dataclass(frozen=True, slots=True, repr=False)
class GraphRequest:
    operation: Op
    resource: GraphResourceIdentity
    target: str
    purpose: str = "graph"
    method: str = "GET"


@dataclass(frozen=True, slots=True, repr=False)
class GraphResponse:
    status: int
    body: bytes = b""
    headers: tuple[tuple[str, str], ...] = ()

    def header(self, name):
        if type(self.headers) is not tuple or len(self.headers) > 24:
            raise reject()
        result, seen = None, set()
        for pair in self.headers:
            if type(pair) is not tuple or len(pair) != 2:
                raise reject()
            key, value = pair
            if (type(key) is not str or type(value) is not str or not re.fullmatch(r"[A-Za-z-]{1,64}", key)
                    or len(value) > 4096 or any(ord(c) < 32 or ord(c) == 127 for c in value)
                    or key.lower() in seen):
                raise reject()
            seen.add(key.lower())
            if key.lower() == name.lower():
                result = value
        return result


@dataclass(frozen=True, slots=True)
class GraphProvenance:
    resource_id: str
    organization_id: str
    instance_id: str
    version: int
    e_tag: str
    observed_at: datetime
    evidence: str = "offline-protocol"


@dataclass(frozen=True, slots=True)
class GraphMetadata:
    provenance: GraphProvenance
    size: int
    mime: str | None


class GraphTransport(Protocol):
    """Offline implementations ONLY. No live implementation is shipped."""
    offline: bool
    def send(self, request: GraphRequest, authorization: object | None) -> GraphResponse: ...
    def authorize_delivery(self, identities: tuple[GraphResourceIdentity, ...]) -> None: ...


class GraphCredentialProvider(Protocol):
    """Test-only composition supplies opaque non-secret transport authority."""
    offline: bool
    def validate(self, use): ...
    def authorization(self, use, identity: GraphResourceIdentity) -> object: ...
