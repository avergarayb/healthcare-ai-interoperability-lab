"""Strict bounded Graph JSON projections; all response bodies are untrusted."""
import json

from ...models import Reason
from ...synthetic import SyntheticPage
from .types import GraphMetadata, GraphProvenance, reject


class GraphResponseParser:
    @staticmethod
    def load(body, limit):
        if type(body) is not bytes or len(body) > limit:
            raise reject(Reason.LIMIT)
        def unique(pairs):
            result = {}
            for key, value in pairs:
                if key in result:
                    raise ValueError("duplicate field")
                result[key] = value
            return result
        try:
            result = json.loads(body.decode("utf-8"), object_pairs_hook=unique,
                                parse_constant=lambda _: (_ for _ in ()).throw(ValueError("non-finite")))
        except (ValueError, TypeError, UnicodeError, RecursionError):
            raise reject(Reason.CONTENT) from None
        if type(result) is not dict:
            raise reject(Reason.CONTENT)
        return result

    def metadata(self, data, identity, clock, max_bytes):
        if (type(data) is not dict or set(data) - {"id", "name", "size", "eTag", "parentReference", "file", "folder"}
                or data.get("id") != identity.item_id or data.get("eTag") != identity.e_tag
                or type(data.get("size")) is not int or not 0 <= data["size"] <= max_bytes
                or ("name" in data and (type(data["name"]) is not str or len(data["name"]) > 256))):
            raise reject(Reason.RESOURCE)
        parent = data.get("parentReference")
        expected = {"driveId": identity.drive_id, "driveType": identity.drive_type}
        if identity.parent_item_id is not None:
            expected["id"] = identity.parent_item_id
        if identity.site_id is not None:
            expected["siteId"] = identity.site_id
        if parent != expected:
            raise reject(Reason.RESOURCE)
        mime = None
        if identity.resource_type == "folder":
            if "file" in data or type(data.get("folder")) is not dict or set(data["folder"]) != {"childCount"}:
                raise reject(Reason.CONTENT)
            if type(data["folder"]["childCount"]) is not int or data["folder"]["childCount"] < 0:
                raise reject(Reason.CONTENT)
        elif "folder" in data or type(data.get("file")) is not dict or data["file"] != {"mimeType": "text/plain"}:
            raise reject(Reason.CONTENT)
        else:
            mime = "text/plain"
        return GraphMetadata(GraphProvenance(identity.resource_id, identity.organization_id, identity.instance_id,
                                             identity.resource_version, identity.e_tag, clock()), data["size"], mime)

    @staticmethod
    def content(response, expected, max_bytes):
        if (type(response.body) is not bytes or len(response.body) > max_bytes or len(response.body) != expected.size
                or response.header("Content-Type") not in {"text/plain", "text/plain; charset=utf-8"}
                or response.header("Content-Encoding") is not None
                or response.header("ETag") != expected.provenance.e_tag
                or response.header("Content-Length") != str(expected.size)):
            raise reject(Reason.CONTENT)
        try:
            return response.body.decode("utf-8", errors="strict")
        except UnicodeError:
            raise reject(Reason.CONTENT) from None


class GraphErrorMapper:
    @staticmethod
    def page(status):
        # Existing service owns retries and phase audit. 304 is never cached ALLOW.
        if type(status) is not int:
            raise reject()
        mapped = 0 if status == 408 else status if status in {401, 403, 404, 429, 500, 502, 503, 504} else 400
        return SyntheticPage(status=mapped)
