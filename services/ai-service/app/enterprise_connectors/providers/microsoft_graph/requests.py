"""Fixed Graph routes and bounded offline URL validation, never HTTP execution."""
from dataclasses import dataclass
import ipaddress
import re
from urllib.parse import parse_qsl, quote, urlsplit

from ...models import ConnectorOperation as Op, Reason
from .types import GraphPermissionProfile, GraphRequest, ORIGIN, SELECT, reject, segment


class GraphRequestBuilder:
    def __init__(self, profile=GraphPermissionProfile()):
        if type(profile) is not GraphPermissionProfile:
            raise reject()
        profile.validate()
        self.profile = profile

    def path(self, identity, operation):
        if operation not in {Op.METADATA, Op.CHILDREN, Op.READ}:
            raise reject(Reason.OPERATION)
        if operation == Op.CHILDREN and identity.resource_type != "folder":
            raise reject(Reason.OPERATION)
        if operation == Op.READ and identity.resource_type != "document":
            raise reject(Reason.OPERATION)
        path = "/v1.0/drives/" + quote(segment(identity.drive_id), safe="") + "/items/" + quote(segment(identity.item_id), safe="")
        return path + ("/children" if operation == Op.CHILDREN else "/content" if operation == Op.READ else "")

    def build(self, identity, operation, continuation=None):
        path = self.path(identity, operation)
        if continuation is not None:
            if operation != Op.CHILDREN:
                raise reject(Reason.OPERATION)
            self.continuation(identity, continuation)
            target = continuation
        else:
            target = ORIGIN + path + ("?$select=" + SELECT if operation != Op.READ else "")
        return GraphRequest(operation, identity, target)

    def continuation(self, identity, link):
        if type(link) is not str or len(link) > 2048 or any(ord(c) <= 32 or ord(c) == 127 for c in link):
            raise reject()
        parsed = urlsplit(link)
        if (parsed.scheme != "https" or parsed.netloc != "graph.microsoft.com" or parsed.fragment
                or parsed.path != self.path(identity, Op.CHILDREN)):
            raise reject()
        try:
            pairs = parse_qsl(parsed.query, keep_blank_values=True, strict_parsing=True, max_num_fields=2)
        except ValueError:
            raise reject() from None
        values = dict(pairs)
        token = values.get("$skiptoken")
        if (len(pairs) != len(values) or set(values) - {"$select", "$skiptoken"}
                or type(token) is not str or not re.fullmatch(r"[A-Za-z0-9._~+=-]{1,128}", token)
                or ("$select" in values and values["$select"] != SELECT)):
            raise reject()
        canonical = "$skiptoken=" + quote(token, safe="")
        if "$select" in values:
            canonical = "$select=" + SELECT + "&" + canonical
        if link != ORIGIN + parsed.path + "?" + canonical:
            raise reject()
        # Optional, fixed $select does not make the same cursor a new page.
        return token


@dataclass(frozen=True, slots=True)
class GraphDownloadPolicy:
    # Only reserved .invalid fixture hosts can be approved in this increment.
    enabled: bool = False
    hosts: frozenset[str] = frozenset()

    def validate(self, location):
        if (self.enabled is not True or type(self.hosts) is not frozenset or not self.hosts
                or any(type(h) is not str or not re.fullmatch(r"[a-z0-9-]+\.invalid", h) for h in self.hosts)
                or type(location) is not str or len(location) > 2048
                or any(ord(c) <= 32 or ord(c) == 127 for c in location)):
            raise reject()
        parsed = urlsplit(location)
        if (parsed.scheme != "https" or parsed.netloc not in self.hosts or parsed.fragment
                or not re.fullmatch(r"/synthetic/[A-Za-z0-9._-]{1,128}", parsed.path)
                or parsed.query != "ticket=synthetic-only"):
            raise reject()
        try:
            ipaddress.ip_address(parsed.hostname)
        except ValueError:
            return location
        raise reject()
