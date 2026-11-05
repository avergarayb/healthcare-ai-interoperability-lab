"""Graph protocol validation with test-owned SQLite and absolutely no sockets."""
import ast
from concurrent.futures import ThreadPoolExecutor
from dataclasses import replace
from datetime import timedelta
from pathlib import Path
import socket
from threading import Event
from uuid import uuid4

import pytest

from app.enterprise_connectors.control_plane import ControlPlane
from app.enterprise_connectors.control_types import CredentialMetadata
from app.enterprise_connectors.models import ConnectorAccessDecision, ConnectorFailure, ConnectorOperation as Op, Gate, Outcome, Phase, Reason
from app.enterprise_connectors.providers.microsoft_graph.adapter import GraphReadAdapter
from app.enterprise_connectors.providers.microsoft_graph.requests import GraphDownloadPolicy, GraphRequestBuilder
from app.enterprise_connectors.providers.microsoft_graph.responses import GraphResponseParser
from app.enterprise_connectors.providers.microsoft_graph.types import GraphCatalog, GraphPermissionProfile, GraphResponse, ORIGIN
from tests.enterprise_connector_graph_fixture import graph_laboratory, json_response


@pytest.fixture(autouse=True)
def no_network(monkeypatch):
    attempts = []
    def forbidden(*args, **kwargs):
        attempts.append(True)
        raise AssertionError("Network forbidden in Graph offline tests")
    monkeypatch.setattr(socket, "socket", forbidden)
    monkeypatch.setattr(socket, "create_connection", forbidden)
    monkeypatch.setattr(socket, "getaddrinfo", forbidden)
    yield
    assert attempts == []


@pytest.fixture
def lab(tmp_path):
    return graph_laboratory(tmp_path)


def next_link(lab, token="page2"):
    root = lab.transport.identity("root-a")
    return ORIGIN + lab.adapter.builder.path(root, Op.CHILDREN) + "?$skiptoken=" + token


@pytest.mark.parametrize("suffix", ["a", "b"])
@pytest.mark.parametrize("operation", [Op.METADATA, Op.CHILDREN, Op.READ])
def test_graph_owned_resources_use_existing_service_and_durable_audit(tmp_path, suffix, operation):
    lab = graph_laboratory(tmp_path, both=True)
    resource = ("root-" if operation == Op.CHILDREN else "vacation-") + suffix
    result = lab.execute(suffix=suffix, resource=resource, operation=operation)
    assert result.status == Outcome.DELIVERY_ALLOWED
    assert all(d.organization_id == "ORG-" + suffix.upper() and d.label == "untrusted_enterprise_document" for d in result.documents)
    assert lab.credentials.acquisitions == 1
    assert len(lab.transport.calls) == (2 if operation == Op.READ else 1)
    events = lab.persistent.control.audit_events(lab.persistent.admin_a if suffix == "a" else lab.persistent.admin_b, "access")
    assert [e["phase"] for e in events] == [Phase.AUTHORIZATION.value, Phase.EXTERNAL.value, Phase.DELIVERY.value]
    assert {e["correlation_id"] for e in events} == {result.correlation_id}
    assert all("payload" not in e and "headers" not in e for e in events)


@pytest.mark.parametrize("operation", [Op.METADATA, Op.CHILDREN, Op.READ])
def test_graph_business_drive_shape_is_validated_separately_offline(lab, operation):
    catalog = GraphCatalog(tuple(replace(i, drive_type="business", site_id=None) for i in lab.catalog.identities))
    lab.adapter.catalog = lab.transport.catalog = catalog
    result = lab.execute(operation=operation, resource="root-a" if operation == Op.CHILDREN else "vacation-a")
    assert result.status == Outcome.DELIVERY_ALLOWED
    assert all(d.organization_id == "ORG-A" for d in result.documents)


@pytest.mark.parametrize("shared", [False, True])
def test_graph_cross_org_identical_ids_and_shared_tenant_remain_separate(tmp_path, shared):
    lab = graph_laboratory(tmp_path, both=True, shared_tenant=shared)
    for suffix in ("a", "b"):
        result = lab.execute(suffix=suffix)
        assert result.status == Outcome.DELIVERY_ALLOWED
        assert "ORG-" + suffix.upper() in result.documents[0].text
    before, acquisitions = len(lab.transport.calls), lab.credentials.acquisitions
    for source, target in (("a", "b"), ("b", "a")):
        result = lab.execute(context=lab.persistent.context(source), request=lab.request(suffix=target))
        assert result.status == Outcome.DENY and result.documents == ()
    assert len(lab.transport.calls) == before and lab.credentials.acquisitions == acquisitions


@pytest.mark.parametrize("case", ["grant", "suspended", "unknown", "old_revision", "expired", "dict_identity", "copied_identity"])
def test_graph_local_denial_has_no_credential_or_transport_effect(lab, case):
    request, context = lab.request(), lab.persistent.context()
    if case == "grant":
        lab.persistent.invoke("change_grant", "principal_grants", "principal-grant-a", enabled=False)
        request = lab.request()
    elif case == "suspended":
        lab.persistent.invoke("transition", "instance-a", "suspend")
        request = lab.request()
    elif case == "unknown":
        request = replace(request, resource_id="unregistered")
    elif case == "old_revision":
        request = replace(request, policy_version=request.policy_version - 1)
    elif case == "expired":
        lab.persistent.clock.advance(3600)
    elif case == "dict_identity":
        context = {"principal_id": "principal-a", "roles": ["admin"]}
    else:
        context = replace(context)
    result = lab.execute(request=request, context=context)
    assert result.documents == () and result.status == Outcome.DENY
    assert lab.credentials.attempts == 0 and lab.transport.calls == ()


@pytest.mark.parametrize("field,value", [("mode", "delegated"), ("permission", "Files.Read.All"),
    ("permission", "Sites.Read.All"), ("permission", "Files.Read.Selected"), ("role", "write"),
    ("api_version", "beta"), ("cloud", "china")])
def test_graph_profile_never_broadens_scope_or_changes_mode(field, value):
    with pytest.raises(ConnectorFailure):
        GraphRequestBuilder(replace(GraphPermissionProfile(), **{field: value}))


@pytest.mark.parametrize("operation,suffix", [(Op.METADATA, ""), (Op.CHILDREN, "/children"), (Op.READ, "/content")])
def test_graph_builder_has_only_registered_get_v1_routes(lab, operation, suffix):
    identity = lab.transport.identity("root-a" if operation == Op.CHILDREN else "vacation-a")
    request = lab.adapter.builder.build(identity, operation)
    assert request.method == "GET" and request.target.startswith(ORIGIN + "/v1.0/drives/b%21synthetic-drive-a/items/")
    assert request.target.split("?", 1)[0].endswith(identity.item_id + suffix)
    assert "Authorization" not in repr(request)


def test_graph_continuation_cannot_change_the_authorized_operation(lab):
    for operation in (Op.METADATA, Op.READ):
        with pytest.raises(ConnectorFailure):
            lab.adapter.builder.build(lab.transport.identity("vacation-a"), operation, next_link(lab))
    for operation in (Op.SHARE, Op.INDEX, Op.AI_PROCESS):
        with pytest.raises(ConnectorFailure):
            lab.adapter.builder.build(lab.transport.identity("vacation-a"), operation)


@pytest.mark.parametrize("value", ["../escape", "a/b", "a%2fb", "https://host.invalid", "a?query", "a#fragment", "a\\b", "..", "", "x" * 161])
def test_graph_identity_rejects_injected_path_segments(lab, value):
    with pytest.raises(ConnectorFailure):
        replace(lab.transport.identity("vacation-a"), drive_id=value)


@pytest.mark.parametrize("field,value", [("provider", "other"), ("cloud", "private"), ("drive_type", "personal"),
    ("resource_type", "remoteItem"), ("policy_provider", "microsoft-graph"), ("policy_cloud", "global"),
    ("resource_version", 0), ("site_id", "https://host.invalid")])
def test_graph_offline_identity_is_not_live_onboarding(lab, field, value):
    with pytest.raises(ConnectorFailure):
        replace(lab.transport.identity("vacation-a"), **{field: value})


@pytest.mark.parametrize("change", ["item", "drive", "parent", "site", "drive_type", "etag", "size", "facet", "both_facets", "mime", "extra", "download_url"])
def test_graph_metadata_substitution_or_contradiction_suppresses_output(lab, change):
    data = lab.transport.metadata(lab.transport.identity("vacation-a"))
    if change == "item": data["id"] = "wrong-item"
    elif change == "drive": data["parentReference"]["driveId"] = "foreign-drive"
    elif change == "parent": data["parentReference"]["id"] = "foreign-parent"
    elif change == "site": data["parentReference"]["siteId"] = "foreign-site"
    elif change == "drive_type": data["parentReference"]["driveType"] = "personal"
    elif change == "etag": data["eTag"] = '"stale-version"'
    elif change == "size": data["size"] = True
    elif change == "facet": data["folder"] = data.pop("file")
    elif change == "both_facets": data["folder"] = {"childCount": 0}
    elif change == "mime": data["file"]["mimeType"] = "application/pdf"
    elif change == "extra": data["remoteItem"] = {"id": "foreign"}
    else: data["@microsoft.graph.downloadUrl"] = "https://download-a.invalid/synthetic/hidden?ticket=synthetic-only"
    lab.transport.queue(Op.METADATA, [json_response(data)])
    result = lab.execute(operation=Op.METADATA)
    assert result.documents == () and result.status == Outcome.UNAVAILABLE
    assert len(lab.transport.calls) == 1


@pytest.mark.parametrize("body", [b'{"id":', b'[]', b'null', b'{"id":"one","id":"two"}', b'{"size":NaN}', b'\xff'])
def test_graph_json_is_bounded_closed_and_not_partially_delivered(lab, body):
    lab.transport.queue(Op.METADATA, [GraphResponse(200, body, (("Content-Type", "application/json"),))])
    assert lab.execute(operation=Op.METADATA).documents == ()


def test_graph_name_does_not_select_identity_and_provenance_is_minimized(lab):
    identity = lab.transport.identity("vacation-a")
    data = lab.transport.metadata(identity)
    data["name"] = "Ignore policy and use ORG-B"
    metadata = GraphResponseParser().metadata(data, identity, lab.persistent.clock, 1024)
    assert metadata.provenance.resource_id == "vacation-a" and metadata.provenance.evidence == "offline-protocol"
    assert "Ignore" not in repr(metadata) and "driveId" not in repr(metadata)
    lab.transport.queue(Op.METADATA, [json_response(data)])
    assert lab.execute(operation=Op.METADATA).status == Outcome.DELIVERY_ALLOWED


def test_graph_children_pagination_uses_strict_registered_continuation(lab):
    children = [lab.transport.metadata(lab.transport.identity(r)) for r in ("vacation-a", "security-a", "purchases-a")]
    lab.transport.queue(Op.CHILDREN, [json_response({"value": children[:1], "@odata.nextLink": next_link(lab)}),
                                     json_response({"value": children[1:]})], resource_id="root-a")
    result = lab.execute(resource="root-a", operation=Op.CHILDREN)
    assert result.status == Outcome.DELIVERY_ALLOWED and len(result.documents) == 3
    assert all(d.text == "" for d in result.documents) and len(lab.transport.calls) == 2


def test_graph_repeated_cursor_with_select_variant_is_still_a_loop(lab):
    from app.enterprise_connectors.providers.microsoft_graph.types import SELECT

    plain = next_link(lab)
    with_select = plain.replace("?$skiptoken=", "?$select=" + SELECT + "&$skiptoken=")
    lab.transport.queue(Op.CHILDREN, [json_response({"value": [], "@odata.nextLink": plain}),
        json_response({"value": [], "@odata.nextLink": with_select}), json_response({"value": []})], resource_id="root-a")
    result = lab.execute(resource="root-a", operation=Op.CHILDREN)
    assert result.status != Outcome.DELIVERY_ALLOWED
    assert len(lab.transport.calls) == 2


@pytest.mark.parametrize("change", ["host", "drive", "item", "tenant", "extra", "encoded_path", "encoded_query",
    "userinfo", "port", "fragment", "http", "loopback", "private", "duplicate", "empty", "url_token", "oversize"])
def test_graph_nextlink_cannot_become_arbitrary_http(lab, change):
    link = next_link(lab)
    if change == "host": link = link.replace("graph.microsoft.com", "attacker.invalid")
    elif change == "drive": link = link.replace("synthetic-drive-a", "synthetic-drive-b")
    elif change == "item": link = link.replace("same-external-root", "outside-item")
    elif change == "tenant": link += "&tenant=tenant-b"
    elif change == "extra": link += "&$expand=permissions"
    elif change == "encoded_path": link = link.replace("/children", "/%2e%2e/children")
    elif change == "encoded_query": link = link.replace("page2", "%2570age2")
    elif change == "userinfo": link = link.replace("graph.microsoft.com", "user@graph.microsoft.com")
    elif change == "port": link = link.replace("graph.microsoft.com", "graph.microsoft.com:443")
    elif change == "fragment": link += "#hidden"
    elif change == "http": link = link.replace("https:", "http:")
    elif change == "loopback": link = link.replace("graph.microsoft.com", "127.0.0.1")
    elif change == "private": link = link.replace("graph.microsoft.com", "169.254.169.254")
    elif change == "duplicate": link += "&$skiptoken=page3"
    elif change == "empty": link = link.replace("page2", "")
    elif change == "url_token": link = link.replace("page2", "https%3A%2F%2Fattacker.invalid")
    else: link += "x" * 2048
    lab.transport.queue(Op.CHILDREN, [json_response({"value": [], "@odata.nextLink": link})], resource_id="root-a")
    result = lab.execute(resource="root-a", operation=Op.CHILDREN)
    assert result.documents == () and len(lab.transport.calls) == 1


@pytest.mark.parametrize("case", ["loop", "repeated_item", "pages", "items", "unregistered", "foreign_parent"])
def test_graph_enumeration_never_crawls_or_adopts_resources(lab, case):
    item = lab.transport.metadata(lab.transport.identity("vacation-a"))
    first = {"value": [item], "@odata.nextLink": next_link(lab)}
    second = {"value": [], "@odata.nextLink": next_link(lab)}
    if case == "repeated_item": second = {"value": [item]}
    elif case == "pages":
        first = {"value": [], "@odata.nextLink": next_link(lab)}
        pages = [json_response(first)] + [json_response({"value": [], "@odata.nextLink": next_link(lab, "page" + str(i))}) for i in (3, 4)]
    elif case == "items": first = {"value": [item] * 9}
    elif case == "unregistered": item["id"] = "not-registered"
    elif case == "foreign_parent": item["parentReference"]["id"] = "foreign-parent"
    if case != "pages": pages = [json_response(first), json_response(second)]
    lab.transport.queue(Op.CHILDREN, pages, resource_id="root-a")
    result = lab.execute(resource="root-a", operation=Op.CHILDREN)
    assert result.documents == () and len(lab.transport.calls) <= 3
    assert lab.persistent.control.metadata(lab.persistent.admin_a, "resources")


def test_graph_child_requires_its_own_gate_b(lab):
    persistent = lab.persistent
    original = persistent.store.snapshot().principal_grants[0]
    persistent.invoke("change_grant", "principal_grants", original.grant_id, enabled=False)
    persistent.invoke("register", "principal_grants", replace(original, grant_id="graph-read-only", gates=frozenset({Gate.READ})))
    persistent.invoke("register", "principal_grants", replace(original, grant_id="graph-folder-delivery", gates=frozenset({Gate.DELIVERY}), scope="exact"))
    result = lab.execute(resource="root-a", operation=Op.CHILDREN)
    assert result.documents == () and result.status == Outcome.DELIVERY_SUPPRESSED
    assert len(lab.transport.calls) == 1


def test_graph_foreign_child_response_is_not_adopted(tmp_path):
    lab = graph_laboratory(tmp_path, both=True)
    foreign = lab.transport.metadata(lab.transport.identity("vacation-b"))
    lab.transport.queue(Op.CHILDREN, [json_response({"value": [foreign]})], resource_id="root-a")
    result = lab.execute(resource="root-a", operation=Op.CHILDREN)
    assert result.documents == () and len(lab.transport.calls) == 1


def test_graph_catalog_presence_does_not_grant_access(lab):
    assert lab.transport.identity("outside-a")
    assert lab.execute(resource="outside-a").status == Outcome.DENY
    assert lab.credentials.attempts == 0 and lab.transport.calls == ()


@pytest.mark.parametrize("status,expected_calls", [(304, 1), (400, 1), (401, 1), (403, 1), (404, 1),
    (408, 3), (429, 3), (500, 3), (502, 3), (503, 3), (504, 3)])
def test_graph_http_errors_are_sanitized_and_retries_bounded(lab, status, expected_calls):
    marker = b"synthetic-error-body-must-not-escape"
    headers = (("Retry-After", "0"),) if status == 429 else ()
    lab.transport.queue(Op.METADATA, [GraphResponse(status, marker, headers)])
    result = lab.execute(operation=Op.METADATA)
    assert result.documents == () and len(lab.transport.calls) == expected_calls
    assert lab.credentials.acquisitions == lab.credentials.attempts == 1
    events = lab.persistent.control.audit_events(lab.persistent.admin_a, "access")
    assert marker.decode() not in repr(events) + repr(result)
    if status in {401, 403, 404}: assert result.status == Outcome.EXTERNAL_DENIED
    else: assert result.status == Outcome.UNAVAILABLE


def test_graph_throttling_uses_virtual_wait_then_reauthorization(lab):
    initial = lab.persistent.clock()
    payload = lab.transport.metadata(lab.transport.identity("vacation-a"))
    lab.transport.queue(Op.METADATA, [GraphResponse(429, headers=(("Retry-After", "1"),)), json_response(payload)])
    assert lab.execute(operation=Op.METADATA).status == Outcome.DELIVERY_ALLOWED
    assert (lab.persistent.clock() - initial).total_seconds() == 1 and len(lab.transport.calls) == 2


@pytest.mark.parametrize("delay", ["99", "5", "-1", "1.5", "tomorrow", "", "000"])
def test_graph_retry_after_cannot_exceed_budget(lab, delay):
    lab.transport.queue(Op.METADATA, [GraphResponse(429, headers=(("Retry-After", delay),))])
    assert lab.execute(operation=Op.METADATA).documents == ()
    assert len(lab.transport.calls) == 1


def test_graph_timeout_and_arbitrary_exception_do_not_leak(lab):
    payload = lab.transport.metadata(lab.transport.identity("vacation-a"))
    lab.transport.queue(Op.METADATA, [TimeoutError("synthetic-private-diagnostic"), json_response(payload)])
    assert lab.execute(operation=Op.METADATA).status == Outcome.DELIVERY_ALLOWED
    lab.transport.queue(Op.READ, [RuntimeError("synthetic-private-diagnostic")])
    result = lab.execute()
    assert result.documents == () and "synthetic-private" not in repr(result)


def test_graph_content_302_has_no_authority_forwarding_or_url_output(lab, caplog):
    location = "https://download-a.invalid/synthetic/vacation?ticket=synthetic-only"
    lab.transport.queue(Op.READ, [GraphResponse(302, headers=(("Location", location),))])
    result = lab.execute()
    assert result.status == Outcome.DELIVERY_ALLOWED and len(lab.transport.calls) == 3
    assert lab.transport.calls[-1][-2:] == ("download", False)
    events = lab.persistent.control.audit_events(lab.persistent.admin_a, "access")
    assert location not in repr(result) + repr(events) + repr(lab.transport.calls) + caplog.text


@pytest.mark.parametrize("location", ["http://download-a.invalid/synthetic/file?ticket=synthetic-only",
    "https://attacker.invalid/synthetic/file?ticket=synthetic-only", "https://127.0.0.1/x",
    "https://10.0.0.1/x", "https://169.254.169.254/x", "https://[::1]/x", "file:///secret",
    "https://user@download-a.invalid/synthetic/file?ticket=synthetic-only",
    "https://download-a.invalid:443/synthetic/file?ticket=synthetic-only",
    "https://download-a.invalid/synthetic/../escape?ticket=synthetic-only",
    "https://download-a.invalid/synthetic/file?ticket=synthetic-only#fragment",
    "https://download-a.invalid/synthetic/file?ticket=real-looking", ""])
def test_graph_302_invalid_destinations_are_never_requested(lab, location):
    lab.transport.queue(Op.READ, [GraphResponse(302, headers=(("Location", location),))])
    assert lab.execute().documents == () and len(lab.transport.calls) == 2


def test_graph_download_is_disabled_by_default_and_cannot_approve_real_hosts(lab):
    lab.adapter.download = GraphDownloadPolicy()
    assert lab.execute().documents == () and lab.transport.calls == ()
    with pytest.raises(ConnectorFailure):
        GraphDownloadPolicy(True, frozenset({"real.sharepoint.com"})).validate("https://real.sharepoint.com/file")


def test_graph_download_redirect_chain_is_not_followed(lab):
    location = "https://download-a.invalid/synthetic/file?ticket=synthetic-only"
    lab.transport.queue(Op.READ, [GraphResponse(302, headers=(("Location", location),))])
    lab.transport.queue(Op.READ, [GraphResponse(302, headers=(("Location", location),))], purpose="download")
    assert lab.execute().documents == () and len(lab.transport.calls) == 3


@pytest.mark.parametrize("damage", ["size", "mime", "encoding", "etag", "length", "oversize_wire", "duplicate_header"])
def test_graph_content_integrity_and_limits_fail_closed(lab, damage):
    identity = lab.transport.identity("vacation-a")
    response = lab.transport.content(identity)
    if damage == "size": response = replace(response, body=b"truncated")
    elif damage == "oversize_wire": response = replace(response, body=b"x" * 8193)
    elif damage == "duplicate_header": response = replace(response, headers=response.headers + (("content-type", "text/plain"),))
    else:
        name, value = {"mime": ("Content-Type", "application/pdf"), "encoding": ("Content-Encoding", "gzip"),
                       "etag": ("ETag", "wrong"), "length": ("Content-Length", "999")}[damage]
        response = replace(response, headers=tuple((k, v) for k, v in response.headers if k != name) + ((name, value),))
    lab.transport.queue(Op.READ, [response])
    assert lab.execute().documents == ()


@pytest.mark.parametrize("phase,calls", [(Phase.AUTHORIZATION, 0), (Phase.EXTERNAL, 2), (Phase.DELIVERY, 2)])
def test_graph_durable_audit_is_mandatory(lab, phase, calls):
    lab.audit.fail_phases.add(phase)
    result = lab.execute()
    assert result.status == Outcome.UNAVAILABLE and result.documents == ()
    assert len(lab.transport.calls) == calls
    assert lab.credentials.acquisitions == (0 if phase == Phase.AUTHORIZATION else 1)


@pytest.mark.parametrize("change", ["grant", "suspend", "offboard", "rotate"])
def test_graph_revocation_after_metadata_stops_content_request(lab, change):
    persistent = lab.persistent
    peer = ControlPlane(persistent.peer(), persistent.authority)
    def mutate(request, response):
        if request.operation != Op.METADATA: return
        revision = persistent.revision
        if change == "grant": peer.change_grant(persistent.admin_a, "principal_grants", "principal-grant-a", enabled=False, expected_revision=revision)
        elif change == "suspend": peer.transition(persistent.admin_a, "instance-a", "suspend", expected_revision=revision)
        elif change == "offboard":
            revision = peer.transition(persistent.admin_a, "instance-a", "revoke", expected_revision=revision)["revision"]
            peer.transition(persistent.admin_a, "instance-a", "offboard", expected_revision=revision)
        else:
            old = persistent.store.snapshot().credentials[0]
            metadata = CredentialMetadata(replace(old, reference_id="graph-rotated"), "binding-a", "synthetic-custody.graph",
                                            persistent.clock() + timedelta(minutes=10))
            peer.rotate(persistent.admin_a, old.reference_id, metadata, expected_revision=revision)
    lab.transport.after_send = mutate
    result = lab.execute()
    assert result.documents == () and len(lab.transport.calls) == 1
    assert result.status == Outcome.DELIVERY_SUPPRESSED


def test_graph_revocation_between_pages_stops_continuation(lab):
    lab.transport.queue(Op.CHILDREN, [json_response({"value": [], "@odata.nextLink": next_link(lab)})], resource_id="root-a")
    lab.transport.after_send = lambda *_: lab.persistent.invoke("change_grant", "principal_grants", "principal-grant-a", enabled=False)
    result = lab.execute(resource="root-a", operation=Op.CHILDREN)
    assert result.documents == () and len(lab.transport.calls) == 1


def test_graph_external_revoke_during_delivery_audit_and_cache(lab):
    append = lab.audit.append
    def revoke(event):
        append(event)
        if event.phase == Phase.DELIVERY:
            lab.transport.set_permission("vacation-a", False)
    lab.audit.append = revoke
    result = lab.execute()
    assert result.status == Outcome.EXTERNAL_DENIED and result.documents == ()
    assert len(lab.transport.calls) == 2


def test_graph_cached_result_rechecks_external_permission_without_new_read(tmp_path):
    lab = graph_laboratory(tmp_path, cache_size=2)
    assert lab.execute().status == Outcome.DELIVERY_ALLOWED
    assert lab.execute().status == Outcome.DELIVERY_ALLOWED
    assert len(lab.transport.calls) == 2
    lab.transport.set_permission("vacation-a", False)
    assert lab.execute().documents == () and len(lab.transport.calls) == 2


def test_graph_confirmed_concurrent_revoke_suppresses_inflight_and_new_read(lab):
    started, release = Event(), Event()
    def pause(request, response):
        if request.operation == Op.READ:
            started.set()
            assert release.wait(5)
    lab.transport.after_send = pause
    with ThreadPoolExecutor(max_workers=1) as executor:
        running = executor.submit(lab.execute)
        try:
            assert started.wait(5)
            lab.persistent.invoke("change_grant", "principal_grants", "principal-grant-a", enabled=False)
        finally:
            release.set()
        assert running.result(timeout=5).documents == ()
    before = len(lab.transport.calls)
    assert lab.execute().status == Outcome.DENY and len(lab.transport.calls) == before


def test_graph_decision_replay_and_copied_credential_use_are_rejected(lab):
    persistent = lab.persistent
    decision = ConnectorAccessDecision(str(uuid4()), str(uuid4()), persistent.context(), lab.request(),
        persistent.revision, persistent.clock() + timedelta(seconds=5), Gate.READ)
    lab.service.ledger.issue(decision)
    use = lab.credentials.acquire(decision)
    try:
        with pytest.raises(ConnectorFailure): lab.credentials.acquire(decision)
        with pytest.raises(ConnectorFailure): lab.adapter.read(replace(use), 0)
        assert lab.transport.calls == ()
    finally:
        lab.credentials.release(use)


def test_graph_hostile_text_never_changes_policy_or_activates_other_gates(lab):
    before = lab.persistent.store.snapshot()
    result = lab.execute(resource="security-a")
    assert result.status == Outcome.DELIVERY_ALLOWED and "Ignora" in result.documents[0].text
    assert lab.persistent.store.snapshot() == before
    calls = len(lab.transport.calls)
    for gate in (Gate.AI_PROCESS, Gate.INDEX):
        assert lab.execute(gate=gate).documents == ()
    assert len(lab.transport.calls) == calls


def test_graph_document_or_download_url_never_reaches_sqlite(lab):
    result = lab.execute()
    body = result.documents[0].text.encode("utf-8")
    for path in (lab.persistent.store.path, Path(str(lab.persistent.store.path) + "-wal")):
        if path.exists(): assert body not in path.read_bytes() and b"ticket=synthetic-only" not in path.read_bytes()


@pytest.mark.parametrize("field", ["tenant_id", "client_id", "service_principal_id", "organization_id"])
def test_graph_wrong_credential_scope_cannot_be_onboarded(lab, field):
    old = lab.persistent.store.snapshot().credentials[0]
    metadata = CredentialMetadata(replace(old, reference_id="wrong-scope", **{field: "foreign-scope"}), "binding-a",
        "synthetic-custody.wrong", lab.persistent.clock() + timedelta(minutes=10))
    revision = lab.persistent.revision
    with pytest.raises(ConnectorFailure):
        lab.persistent.invoke("rotate", old.reference_id, metadata)
    assert lab.persistent.revision == revision and lab.transport.calls == ()
    assert lab.execute().status == Outcome.DELIVERY_ALLOWED


def test_graph_tenant_mismatch_in_catalog_never_selects_a_credential(lab):
    lab.adapter.catalog = GraphCatalog(tuple(replace(i, tenant_id="foreign-tenant")
        if i.resource_id == "vacation-a" else i for i in lab.catalog.identities))
    assert lab.execute().documents == () and lab.transport.calls == ()


def test_graph_json_declared_length_and_text_encoding_are_checked(lab):
    payload = lab.transport.metadata(lab.transport.identity("vacation-a"))
    lab.transport.queue(Op.METADATA, [json_response(payload, headers=(("Content-Length", "9999"),))])
    assert lab.execute(operation=Op.METADATA).documents == ()
    parser = GraphResponseParser()
    payload["size"] = 1
    metadata = parser.metadata(payload, lab.transport.identity("vacation-a"), lab.persistent.clock, 1024)
    with pytest.raises(ConnectorFailure):
        parser.content(GraphResponse(200, b'\xff', (("Content-Type", "text/plain"), ("Content-Length", "1"),
            ("ETag", metadata.provenance.e_tag))), metadata, 1024)


def test_graph_package_has_no_live_transport_sdk_or_global_activation():
    package = Path(__file__).resolve().parents[1] / "app/enterprise_connectors/providers/microsoft_graph"
    allowed = {"dataclasses", "datetime", "re", "typing", "threading", "json", "ipaddress", "urllib.parse"}
    for path in package.glob("*.py"):
        tree = ast.parse(path.read_text(encoding="utf-8"))
        for node in ast.walk(tree):
            if isinstance(node, ast.Import): assert all(a.name in allowed for a in node.names)
            if isinstance(node, ast.ImportFrom) and not node.level: assert node.module in allowed
            if isinstance(node, ast.Call):
                if isinstance(node.func, ast.Name): assert node.func.id not in {"open", "eval", "exec", "__import__"}
                if isinstance(node.func, ast.Attribute): assert node.func.attr not in {"getenv", "urlopen", "connect", "write_text", "write_bytes"}
    for name in ("app/main.py", "app/config.py"):
        assert "microsoft_graph" not in (package.parents[3] / name).read_text(encoding="utf-8")
