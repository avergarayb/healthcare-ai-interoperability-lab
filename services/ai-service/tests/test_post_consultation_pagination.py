from __future__ import annotations

from urllib.parse import urlencode

import httpx
import pytest

from app.langgraph_fhir_client import (
    FHIR_SEARCH_MAX_UNIQUE_RESOURCES_PER_TYPE,
    BoundedSearchStatus,
    ClientFHIRTransport,
    ReadClientError,
)
from app.langgraph_fhir_followup import FollowUpFHIRAdapter
from app.langgraph_fhir_hapi import HapiReadClient


BASE = "http://hapi.example/fhir"
HAPI_TOKEN = "synthetic-page-token"


def _resource(resource_type: str, resource_id: str, **values) -> dict:
    return {"resourceType": resource_type, "id": resource_id, **values}


def _bundle(resources=(), next_url: object = None, *, extra_links=()) -> dict:
    links = list(extra_links)
    if next_url is not None:
        links.append({"relation": "next", "url": next_url})
    result = {
        "resourceType": "Bundle",
        "type": "searchset",
        "entry": [{"resource": item} for item in resources],
    }
    if links:
        result["link"] = links
    return result


def _client(handler) -> tuple[HapiReadClient, httpx.Client]:
    http = httpx.Client(transport=httpx.MockTransport(handler), timeout=5.0)
    return HapiReadClient(BASE, http_client=http), http


def _hapi_next(
    *,
    token: str = HAPI_TOKEN,
    offset: object = 25,
    count: object = 25,
    pretty: bool = True,
) -> str:
    parts = [
        f"_getpages={token}",
        f"_getpagesoffset={offset}",
        f"_count={count}",
    ]
    if pretty:
        parts.append("_pretty=true")
    parts.append("_bundletype=searchset")
    return f"{BASE}?{'&'.join(parts)}"


def _resource_next(
    *semantic: tuple[str, str],
    page: int | None = None,
    token: str | None = None,
) -> str:
    pairs = list(semantic)
    if page is not None:
        pairs.append(("page", str(page)))
    if token is not None:
        pairs.append(("token", token))
    return f"?{urlencode(pairs)}"


def _resource_next_for_request(
    request: httpx.Request,
    *,
    page: int | None = None,
    token: str | None = None,
) -> str:
    semantic = tuple(
        (key, value)
        for key, value in request.url.params.multi_items()
        if key not in {"page", "token"}
    )
    return _resource_next(*semantic, page=page, token=token)


def test_two_pages_are_traversed_even_when_the_first_page_is_empty():
    seen: list[str] = []

    def handler(request: httpx.Request) -> httpx.Response:
        seen.append(str(request.url))
        if request.url.params.get("page") == "2":
            return httpx.Response(200, json=_bundle([_resource("Observation", "obs-2")]))
        return httpx.Response(
            200,
            json=_bundle(
                [],
                _resource_next(
                    ("subject", "Patient/p"),
                    ("_count", "25"),
                    page=2,
                    token="a/b",
                ),
            ),
        )

    client, http = _client(handler)
    try:
        result = client.search("Observation?subject=Patient/p&_count=25", "Observation")
    finally:
        http.close()
    assert result.status is BoundedSearchStatus.COMPLETE
    assert [item["id"] for item in result.resources] == ["obs-2"]
    assert len(seen) == 2


def test_same_resource_paging_may_change_only_recognized_paging_state():
    seen: list[httpx.URL] = []
    semantic = (
        ("subject", "Patient/p"),
        ("status", "final"),
        ("_count", "25"),
    )

    def handler(request: httpx.Request) -> httpx.Response:
        seen.append(request.url)
        page = request.url.params.get("page")
        if page == "2":
            return httpx.Response(
                200,
                json=_bundle(
                    [_resource("Observation", "obs-2")],
                    _resource_next(*semantic, page=3, token="cursor-2"),
                ),
            )
        if page == "3":
            return httpx.Response(200, json=_bundle([_resource("Observation", "obs-3")]))
        return httpx.Response(
            200,
            json=_bundle(
                [_resource("Observation", "obs-1")],
                _resource_next(*semantic, page=2, token="cursor-1"),
            ),
        )

    client, http = _client(handler)
    try:
        result = client.search(
            "Observation?subject=Patient/p&status=final&_count=25",
            "Observation",
        )
    finally:
        http.close()

    assert result.status is BoundedSearchStatus.COMPLETE
    assert [item["id"] for item in result.resources] == ["obs-1", "obs-2", "obs-3"]
    assert [url.params.get("page") for url in seen] == [None, "2", "3"]
    assert [url.params.get("token") for url in seen] == [None, "cursor-1", "cursor-2"]
    assert all(url.params.get("subject") == "Patient/p" for url in seen)
    assert all(url.params.get("status") == "final" for url in seen)
    assert all(url.params.get("_count") == "25" for url in seen)


def test_malformed_utf8_in_ordinary_paging_token_fails_before_fetch():
    seen = 0

    def handler(_request: httpx.Request) -> httpx.Response:
        nonlocal seen
        seen += 1
        return httpx.Response(
            200,
            json=_bundle(
                [],
                "?subject=Patient%2Fp&_count=25&token=%FF",
            ),
        )

    client, http = _client(handler)
    try:
        result = client.search("Observation?subject=Patient/p&_count=25", "Observation")
    finally:
        http.close()

    assert result.status is BoundedSearchStatus.FAILED
    assert result.reason == "FHIR continuation query is malformed"
    assert seen == 1


def test_malformed_utf8_in_ordinary_semantic_parameter_fails_before_fetch():
    seen = 0

    def handler(_request: httpx.Request) -> httpx.Response:
        nonlocal seen
        seen += 1
        return httpx.Response(
            200,
            json=_bundle(
                [],
                "?subject=Patient%2F%FF&_count=25&page=2",
            ),
        )

    client, http = _client(handler)
    try:
        result = client.search("Observation?subject=Patient/p&_count=25", "Observation")
    finally:
        http.close()

    assert result.status is BoundedSearchStatus.FAILED
    assert result.reason == "FHIR continuation query is malformed"
    assert seen == 1


def test_malformed_utf8_in_initial_semantic_query_fails_before_first_request():
    seen = 0

    def handler(_request: httpx.Request) -> httpx.Response:
        nonlocal seen
        seen += 1
        return httpx.Response(200, json=_bundle())

    client, http = _client(handler)
    try:
        result = client.search("Observation?subject=Patient/%FF&_count=25", "Observation")
    finally:
        http.close()

    assert result.status is BoundedSearchStatus.FAILED
    assert result.reason == "FHIR continuation query is malformed"
    assert seen == 0


def test_valid_utf8_percent_encoding_and_reordered_query_are_accepted():
    seen: list[httpx.URL] = []

    def handler(request: httpx.Request) -> httpx.Response:
        seen.append(request.url)
        next_url = (
            "?_count=25&n%6Fte=caf%C3%A9&subject=Patient%2Fp"
            "&token=suiv%C3%A1&page=2"
            if len(seen) == 1
            else None
        )
        return httpx.Response(200, json=_bundle([], next_url))

    client, http = _client(handler)
    try:
        result = client.search(
            "Observation?subject=Patient/p&note=caf%C3%A9&_count=25",
            "Observation",
        )
    finally:
        http.close()

    assert result.status is BoundedSearchStatus.COMPLETE
    assert len(seen) == 2
    assert seen[1].params["note"] == "café"
    assert seen[1].params["token"] == "suivá"


@pytest.mark.parametrize(
    "next_link",
    [
        "?status=final&_count=25&page=2",
        "?subject=Patient%2Fother&status=final&_count=25&page=2",
        "?subject=Patient%2Fp&_count=25&page=2",
        "?subject=Patient%2Fp&status=preliminary&_count=25&page=2",
        "?subject=Patient%2Fp&status=final&_count=24&page=2",
        "?subject=Patient%2Fp&subject=Patient%2Fother&status=final&_count=25&page=2",
        "?subject=Patient%2Fp&patient=Patient%2Fother&status=final&_count=25&page=2",
        f"{BASE}/Encounter?subject=Patient%2Fp&status=final&_count=25&page=2",
        f"{BASE}/Observation/$everything?subject=Patient%2Fp&status=final&_count=25&page=2",
        "http://evil.example/fhir/Observation?subject=Patient%2Fp&status=final&_count=25&page=2",
        "https://hapi.example/fhir/Observation?subject=Patient%2Fp&status=final&_count=25&page=2",
        "http://hapi.example:8081/fhir/Observation?subject=Patient%2Fp&status=final&_count=25&page=2",
        "http://user:password@hapi.example/fhir/Observation?subject=Patient%2Fp&status=final&_count=25&page=2",
        f"{BASE}/Observation?subject=Patient%2Fp&status=final&_count=25&page=2#fragment",
        f"{BASE}/%2e%2e/Observation?subject=Patient%2Fp&status=final&_count=25&page=2",
        f"{BASE}/Observation%2F..%2FPatient?subject=Patient%2Fp&status=final&_count=25&page=2",
        "?subject=Patient%2Fp&status=final&_count=25&_include=Observation%3Asubject&page=2",
    ],
)
def test_same_resource_continuation_cannot_change_authorized_search_before_fetch(
    next_link: str,
):
    seen = 0

    def handler(_request: httpx.Request) -> httpx.Response:
        nonlocal seen
        seen += 1
        return httpx.Response(200, json=_bundle([], next_link))

    client, http = _client(handler)
    try:
        result = client.search(
            "Observation?subject=Patient/p&status=final&_count=25",
            "Observation",
        )
    finally:
        http.close()

    assert result.status is BoundedSearchStatus.FAILED
    assert seen == 1


@pytest.mark.parametrize(
    "next_link",
    [
        "?_count=25&page=2",
        "?patient=Patient%2Fother&_count=25&page=2",
        "?patient=Patient%2Fp&patient=Patient%2Fother&_count=25&page=2",
    ],
)
def test_same_resource_continuation_cannot_remove_or_change_patient_filter(
    next_link: str,
):
    seen = 0

    def handler(_request: httpx.Request) -> httpx.Response:
        nonlocal seen
        seen += 1
        return httpx.Response(200, json=_bundle([], next_link))

    client, http = _client(handler)
    try:
        result = client.search("Appointment?patient=Patient/p&_count=25", "Appointment")
    finally:
        http.close()

    assert result.status is BoundedSearchStatus.FAILED
    assert seen == 1


def test_exact_duplicate_is_kept_once_but_conflicting_duplicate_fails():
    original = _resource("Encounter", "enc-1", status="finished")

    def run(second: dict):
        def handler(request: httpx.Request) -> httpx.Response:
            if request.url.params.get("page") == "2":
                return httpx.Response(200, json=_bundle([second]))
            return httpx.Response(
                200,
                json=_bundle(
                    [original],
                    _resource_next(
                        ("patient", "Patient/p"),
                        ("status", "finished"),
                        ("_count", "25"),
                        page=2,
                    ),
                ),
            )

        client, http = _client(handler)
        try:
            return client.search("Encounter?patient=Patient/p&status=finished&_count=25", "Encounter")
        finally:
            http.close()

    exact = run(dict(original))
    assert exact.status is BoundedSearchStatus.COMPLETE
    assert len(exact.resources) == 1
    conflict = run({**original, "status": "in-progress"})
    assert conflict.status is BoundedSearchStatus.FAILED
    assert conflict.resources == (original,)
    assert conflict.reason == "conflicting duplicate search resource"


def test_each_page_reuses_retry_without_duplicating_resources(monkeypatch):
    monkeypatch.setattr("app.langgraph_fhir_hapi._retry_sleep", lambda _delay: None)
    page_two_calls = 0

    def handler(request: httpx.Request) -> httpx.Response:
        nonlocal page_two_calls
        if request.url.params.get("page") == "2":
            page_two_calls += 1
            if page_two_calls == 1:
                return httpx.Response(503, json={"resourceType": "OperationOutcome"})
            return httpx.Response(200, json=_bundle([_resource("Observation", "obs-2")]))
        return httpx.Response(
            200,
            json=_bundle(
                [_resource("Observation", "obs-1")],
                _resource_next(
                    ("subject", "Patient/p"),
                    ("status", "final"),
                    ("_count", "25"),
                    page=2,
                ),
            ),
        )

    client, http = _client(handler)
    try:
        result = client.search("Observation?subject=Patient/p&status=final&_count=25", "Observation")
    finally:
        http.close()
    assert result.status is BoundedSearchStatus.COMPLETE
    assert [item["id"] for item in result.resources] == ["obs-1", "obs-2"]
    assert page_two_calls == 2


def test_page_limit_with_a_next_link_is_incomplete_not_failed():
    def handler(request: httpx.Request) -> httpx.Response:
        page = int(request.url.params.get("page", "1"))
        return httpx.Response(
            200,
            json=_bundle(
                [_resource("Appointment", f"appt-{page}")],
                _resource_next(
                    ("patient", "Patient/p"),
                    ("_count", "25"),
                    page=page + 1,
                ),
            ),
        )

    client, http = _client(handler)
    try:
        result = client.search("Appointment?patient=Patient/p&_count=25", "Appointment")
    finally:
        http.close()
    assert result.status is BoundedSearchStatus.INCOMPLETE_LIMIT
    assert len(result.resources) == 4
    assert len(client.calls) == 4


def test_unsafe_next_link_at_the_page_limit_is_still_failed():
    def handler(request: httpx.Request) -> httpx.Response:
        page = int(request.url.params.get("page", "1"))
        next_url = (
            "http://evil.example/fhir/Appointment?page=5"
            if page == 4
            else _resource_next(
                ("patient", "Patient/p"),
                ("_count", "25"),
                page=page + 1,
            )
        )
        return httpx.Response(
            200,
            json=_bundle([_resource("Appointment", f"appt-{page}")], next_url),
        )

    client, http = _client(handler)
    try:
        result = client.search("Appointment?patient=Patient/p&_count=25", "Appointment")
    finally:
        http.close()
    assert result.status is BoundedSearchStatus.FAILED
    assert len(result.resources) == 4
    assert len(client.calls) == 4


@pytest.mark.parametrize(
    "next_link",
    [
        "http://evil.example/fhir/Observation?page=2",
        "https://hapi.example/fhir/Observation?page=2",
        "http://hapi.example:8081/fhir/Observation?page=2",
        "http://[malformed/fhir/Observation?page=2",
        "/fhir/Observation?token=%ZZ",
        "http://user:password@hapi.example/fhir/Observation?page=2",
        "/fhir/Observation?page=2#fragment",
        "/fhir/Observation/$export?page=2",
        "/fhir/Observation%2F..%2FPatient?page=2",
        "/fhir/../Observation?page=2",
    ],
)
def test_unsafe_next_links_fail_before_a_second_http_request(next_link: str):
    seen = 0

    def handler(_request: httpx.Request) -> httpx.Response:
        nonlocal seen
        seen += 1
        return httpx.Response(200, json=_bundle([], next_link))

    client, http = _client(handler)
    try:
        result = client.search("Observation?subject=Patient/p&_count=25", "Observation")
    finally:
        http.close()
    assert result.status is BoundedSearchStatus.FAILED
    assert seen == 1


def test_cycle_multiple_and_malformed_next_links_fail_closed():
    initial = f"{BASE}/Observation?subject=Patient/p&_count=25"
    payloads = [
        _bundle([], initial),
        _bundle([], "?page=2", extra_links=({"relation": "next", "url": "?page=3"},)),
        _bundle([], extra_links=({"relation": "next", "url": ""},)),
    ]
    for payload in payloads:
        client, http = _client(lambda _request, item=payload: httpx.Response(200, json=item))
        try:
            result = client.search("Observation?subject=Patient/p&_count=25", "Observation")
        finally:
            http.close()
        assert result.status is BoundedSearchStatus.FAILED


def test_oversized_next_link_and_redirect_response_fail_closed():
    oversized = "/fhir/Observation?token=" + ("a" * 4096)
    client, http = _client(
        lambda _request: httpx.Response(200, json=_bundle([], oversized))
    )
    try:
        result = client.search("Observation?subject=Patient/p&_count=25", "Observation")
    finally:
        http.close()
    assert result.status is BoundedSearchStatus.FAILED

    seen = 0

    def redirect(_request: httpx.Request) -> httpx.Response:
        nonlocal seen
        seen += 1
        return httpx.Response(302, headers={"Location": "http://evil.example/fhir/Observation"})

    redirecting, redirect_http = _client(redirect)
    try:
        redirected = redirecting.search(
            "Observation?subject=Patient/p&_count=25", "Observation"
        )
    finally:
        redirect_http.close()
    assert redirected.status is BoundedSearchStatus.FAILED
    assert redirected.reason == "redirect response is not allowed"
    assert seen == 1


def test_patient_uniqueness_is_checked_across_all_pages():
    def patient(patient_id: str) -> dict:
        return _resource(
            "Patient",
            patient_id,
            identifier=[{"system": "https://lab.local/followup-case", "value": "case-a"}],
        )

    def handler(request: httpx.Request) -> httpx.Response:
        if request.url.params.get("page") == "2":
            return httpx.Response(200, json=_bundle([patient("p-2")]))
        return httpx.Response(
            200,
            json=_bundle([patient("p-1")], _resource_next_for_request(request, page=2)),
        )

    client, http = _client(handler)
    adapter = FollowUpFHIRAdapter(ClientFHIRTransport(client))
    try:
        with adapter.bind_read("case-a"):
            with pytest.raises(ReadClientError, match="more than one patient"):
                adapter.resolve_patient_for_protocol("case-a")
            assert adapter.ledger.patient_collection.value == "unavailable"
    finally:
        http.close()


@pytest.mark.parametrize("field", ["entry", "link"])
@pytest.mark.parametrize("invalid", [{}, "", 0, False, None])
def test_present_falsy_bundle_arrays_fail_instead_of_becoming_absence(field: str, invalid):
    payload = _bundle([])
    payload[field] = invalid
    client, http = _client(lambda _request: httpx.Response(200, json=payload))
    try:
        result = client.search("Appointment?patient=Patient/p&_count=25", "Appointment")
    finally:
        http.close()
    assert result.status is BoundedSearchStatus.FAILED
    assert "list" in (result.reason or "")


@pytest.mark.parametrize(
    "payload",
    [
        {"resourceType": "Bundle", "type": "searchset"},
        {"resourceType": "Bundle", "type": "searchset", "entry": []},
        {"resourceType": "Bundle", "type": "searchset", "entry": [], "link": []},
    ],
)
def test_absent_or_empty_bundle_arrays_keep_valid_empty_search_semantics(payload: dict):
    client, http = _client(lambda _request: httpx.Response(200, json=payload))
    try:
        result = client.search("Appointment?patient=Patient/p&_count=25", "Appointment")
    finally:
        http.close()
    assert result.status is BoundedSearchStatus.COMPLETE
    assert result.resources == ()


def _run_resource_boundary(first_page: list[dict], next_url: str | None):
    requests: list[str] = []

    def handler(request: httpx.Request) -> httpx.Response:
        requests.append(str(request.url))
        if request.url.params.get("page") == "2":
            return httpx.Response(200, json=_bundle([_resource("Appointment", "page-2")]))
        return httpx.Response(200, json=_bundle(first_page, next_url))

    client, http = _client(handler)
    try:
        result = client.search("Appointment?patient=Patient/p&_count=25", "Appointment")
    finally:
        http.close()
    return result, requests


def test_resource_cap_boundary_with_and_without_continuation():
    maximum = FHIR_SEARCH_MAX_UNIQUE_RESOURCES_PER_TYPE
    ninety_nine = [_resource("Appointment", f"a-{index}") for index in range(99)]
    appointment_next = _resource_next(
        ("patient", "Patient/p"),
        ("_count", "25"),
        page=2,
    )
    result_99, requests_99 = _run_resource_boundary(ninety_nine, appointment_next)
    assert result_99.status is BoundedSearchStatus.COMPLETE
    assert len(result_99.resources) == maximum
    assert len(requests_99) == 2

    one_hundred = [_resource("Appointment", f"a-{index}") for index in range(maximum)]
    complete, complete_requests = _run_resource_boundary(one_hundred, None)
    assert complete.status is BoundedSearchStatus.COMPLETE
    assert len(complete.resources) == maximum
    assert len(complete_requests) == 1

    incomplete, incomplete_requests = _run_resource_boundary(one_hundred, appointment_next)
    assert incomplete.status is BoundedSearchStatus.INCOMPLETE_LIMIT
    assert len(incomplete.resources) == maximum
    assert len(incomplete_requests) == 1


def test_resource_cap_handles_oversized_page_and_duplicates_at_boundary():
    maximum = FHIR_SEARCH_MAX_UNIQUE_RESOURCES_PER_TYPE
    one_hundred = [_resource("Appointment", f"a-{index}") for index in range(maximum)]
    oversized, oversized_requests = _run_resource_boundary(
        one_hundred + [_resource("Appointment", "a-overflow")],
        None,
    )
    assert oversized.status is BoundedSearchStatus.INCOMPLETE_LIMIT
    assert len(oversized.resources) == maximum
    assert len(oversized_requests) == 1

    duplicate_boundary, duplicate_requests = _run_resource_boundary(
        one_hundred + [dict(one_hundred[-1])],
        _resource_next(
            ("patient", "Patient/p"),
            ("_count", "25"),
            page=2,
        ),
    )
    assert duplicate_boundary.status is BoundedSearchStatus.INCOMPLETE_LIMIT
    assert len(duplicate_boundary.resources) == maximum
    assert len(duplicate_requests) == 1


@pytest.mark.parametrize("pretty", [True, False])
def test_hapi_base_continuation_accepts_observed_shape_and_optional_pretty(pretty: bool):
    requested_paths: list[str] = []

    def handler(request: httpx.Request) -> httpx.Response:
        requested_paths.append(request.url.path)
        if request.url.path == "/fhir":
            return httpx.Response(200, json=_bundle([_resource("Observation", "obs-2")]))
        return httpx.Response(
            200,
            json=_bundle(
                [_resource("Observation", "obs-1")],
                _hapi_next(pretty=pretty),
            ),
        )

    client, http = _client(handler)
    try:
        result = client.search("Observation?subject=Patient/p&_count=25", "Observation")
    finally:
        http.close()
    assert result.status is BoundedSearchStatus.COMPLETE
    assert [item["id"] for item in result.resources] == ["obs-1", "obs-2"]
    assert requested_paths == ["/fhir/Observation", "/fhir"]
    assert client.calls == [
        "Observation?subject=Patient/p&_count=25",
        "Observation:continuation:2",
    ]


def test_malformed_hapi_token_mutation_fails_before_third_request():
    seen = 0

    def handler(_request: httpx.Request) -> httpx.Response:
        nonlocal seen
        seen += 1
        next_link = (
            _hapi_next(token="%FF", offset=25, pretty=False)
            if seen == 1
            else _hapi_next(token="%FE", offset=50, pretty=False)
        )
        return httpx.Response(200, json=_bundle([], next_link))

    client, http = _client(handler)
    try:
        result = client.search("Observation?subject=Patient/p&_count=25", "Observation")
    finally:
        http.close()

    assert result.status is BoundedSearchStatus.FAILED
    assert result.reason == "FHIR continuation query is malformed"
    assert seen == 1


def test_malformed_hapi_token_on_first_continuation_fails_before_fetch():
    seen = 0

    def handler(_request: httpx.Request) -> httpx.Response:
        nonlocal seen
        seen += 1
        return httpx.Response(
            200,
            json=_bundle([], _hapi_next(token="%C3%28", pretty=False)),
        )

    client, http = _client(handler)
    try:
        result = client.search("Observation?subject=Patient/p&_count=25", "Observation")
    finally:
        http.close()

    assert result.status is BoundedSearchStatus.FAILED
    assert result.reason == "FHIR continuation query is malformed"
    assert seen == 1


def test_valid_utf8_percent_encoded_hapi_token_is_accepted():
    seen: list[httpx.URL] = []

    def handler(request: httpx.Request) -> httpx.Response:
        seen.append(request.url)
        next_link = _hapi_next(token="caf%C3%A9", pretty=False) if len(seen) == 1 else None
        return httpx.Response(200, json=_bundle([], next_link))

    client, http = _client(handler)
    try:
        result = client.search("Observation?subject=Patient/p&_count=25", "Observation")
    finally:
        http.close()

    assert result.status is BoundedSearchStatus.COMPLETE
    assert len(seen) == 2
    assert seen[1].params["_getpages"] == "café"


def test_hapi_continuation_token_and_offsets_are_bound_to_one_traversal():
    requested_offsets: list[str | None] = []

    def handler(request: httpx.Request) -> httpx.Response:
        requested_offsets.append(request.url.params.get("_getpagesoffset"))
        if request.url.path.endswith("/Observation"):
            return httpx.Response(
                200,
                json=_bundle([_resource("Observation", "obs-1")], _hapi_next(offset=25)),
            )
        if request.url.params.get("_getpagesoffset") == "25":
            return httpx.Response(
                200,
                json=_bundle([_resource("Observation", "obs-2")], _hapi_next(offset=50)),
            )
        return httpx.Response(200, json=_bundle([_resource("Observation", "obs-3")]))

    client, http = _client(handler)
    try:
        result = client.search("Observation?subject=Patient/p&_count=25", "Observation")
    finally:
        http.close()
    assert result.status is BoundedSearchStatus.COMPLETE
    assert [item["id"] for item in result.resources] == ["obs-1", "obs-2", "obs-3"]
    assert requested_offsets == [None, "25", "50"]


@pytest.mark.parametrize("first_kind", ["resource", "hapi"])
def test_continuation_shape_cannot_switch_during_traversal(first_kind: str):
    seen = 0
    resource_next = (
        f"{BASE}/Observation?subject=Patient%2Fp&_count=25&page=2&token=cursor"
    )

    def handler(_request: httpx.Request) -> httpx.Response:
        nonlocal seen
        seen += 1
        if seen == 1:
            next_link = resource_next if first_kind == "resource" else _hapi_next(offset=25)
        else:
            next_link = _hapi_next(offset=25) if first_kind == "resource" else resource_next
        return httpx.Response(200, json=_bundle([], next_link))

    client, http = _client(handler)
    try:
        result = client.search("Observation?subject=Patient/p&_count=25", "Observation")
    finally:
        http.close()

    assert result.status is BoundedSearchStatus.FAILED
    assert seen == 2


@pytest.mark.parametrize(
    "next_link",
    [
        BASE,
        f"{BASE}?foo=bar",
        f"{BASE}?_getpagesoffset=25&_count=25&_bundletype=searchset",
        f"{BASE}?_getpages=&_getpagesoffset=25&_count=25&_bundletype=searchset",
        f"{BASE}?_getpages={HAPI_TOKEN}&_getpages=other&_getpagesoffset=25&_count=25&_bundletype=searchset",
        f"{BASE}?_getpages={HAPI_TOKEN}&_count=25&_bundletype=searchset",
        f"{BASE}?_getpages={HAPI_TOKEN}&_getpagesoffset=-25&_count=25&_bundletype=searchset",
        f"{BASE}?_getpages={HAPI_TOKEN}&_getpagesoffset=+25&_count=25&_bundletype=searchset",
        f"{BASE}?_getpages={HAPI_TOKEN}&_getpagesoffset=25.0&_count=25&_bundletype=searchset",
        f"{BASE}?_getpages={HAPI_TOKEN}&_getpagesoffset=%2025&_count=25&_bundletype=searchset",
        f"{BASE}?_getpages={HAPI_TOKEN}&_getpagesoffset=25&_bundletype=searchset",
        f"{BASE}?_getpages={HAPI_TOKEN}&_getpagesoffset=25&_count=24&_bundletype=searchset",
        f"{BASE}?_getpages={HAPI_TOKEN}&_getpagesoffset=25&_count=25",
        f"{BASE}?_getpages={HAPI_TOKEN}&_getpagesoffset=25&_count=25&_bundletype=collection",
        f"{BASE}?_getpages={HAPI_TOKEN}&_getpagesoffset=25&_count=25&_bundletype=searchset&evil=x",
        f"{BASE}?_getpages={HAPI_TOKEN}&_getpagesoffset=25&_count=25&_count=25&_bundletype=searchset",
        f"{BASE}?_getpages={HAPI_TOKEN}&_getpagesoffset=25&_count=25&_pretty=false&_bundletype=searchset",
        f"{BASE}?_getpages={'x' * 513}&_getpagesoffset=25&_count=25&_bundletype=searchset",
        f"{BASE}/other?_getpages={HAPI_TOKEN}&_getpagesoffset=25&_count=25&_bundletype=searchset",
        f"{BASE}/Observation?_getpages={HAPI_TOKEN}&_getpagesoffset=25&_count=25&_bundletype=searchset",
        f"{BASE}/$export?_getpages={HAPI_TOKEN}&_getpagesoffset=25&_count=25&_bundletype=searchset",
        f"http://evil.example/fhir?_getpages={HAPI_TOKEN}&_getpagesoffset=25&_count=25&_bundletype=searchset",
        f"//evil.example/fhir?_getpages={HAPI_TOKEN}&_getpagesoffset=25&_count=25&_bundletype=searchset",
        f"http://user:password@hapi.example/fhir?_getpages={HAPI_TOKEN}&_getpagesoffset=25&_count=25&_bundletype=searchset",
        f"{BASE}?_getpages={HAPI_TOKEN}&_getpagesoffset=25&_count=25&_bundletype=searchset#fragment",
        f"{BASE}/%2e%2e/admin?_getpages={HAPI_TOKEN}&_getpagesoffset=25&_count=25&_bundletype=searchset",
        f"{BASE}%2Fadmin?_getpages={HAPI_TOKEN}&_getpagesoffset=25&_count=25&_bundletype=searchset",
    ],
)
def test_invalid_hapi_base_continuations_fail_before_fetch(next_link: str):
    seen = 0

    def handler(_request: httpx.Request) -> httpx.Response:
        nonlocal seen
        seen += 1
        return httpx.Response(200, json=_bundle([], next_link))

    client, http = _client(handler)
    try:
        result = client.search("Observation?subject=Patient/p&_count=25", "Observation")
    finally:
        http.close()
    assert result.status is BoundedSearchStatus.FAILED
    assert seen == 1


@pytest.mark.parametrize(
    ("second_token", "second_offset"),
    [
        ("changed-page-token", 50),
        (HAPI_TOKEN, 25),
        (HAPI_TOKEN, 1),
        (HAPI_TOKEN, 51),
    ],
)
def test_changed_token_or_inconsistent_hapi_offset_fails_before_next_fetch(
    second_token: str,
    second_offset: int,
):
    seen = 0

    def handler(request: httpx.Request) -> httpx.Response:
        nonlocal seen
        seen += 1
        if request.url.path.endswith("/Observation"):
            next_link = _hapi_next(offset=25)
        else:
            next_link = _hapi_next(token=second_token, offset=second_offset)
        return httpx.Response(200, json=_bundle([], next_link))

    client, http = _client(handler)
    try:
        result = client.search("Observation?subject=Patient/p&_count=25", "Observation")
    finally:
        http.close()
    assert result.status is BoundedSearchStatus.FAILED
    assert seen == 2
