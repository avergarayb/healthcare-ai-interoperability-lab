from app.clinical_federation_client import FederationClientError
from app.cross_org_lab_result_review import evaluate_cross_org_lab_result
from app.federated_protocol_evaluation import evaluate_federated_protocol
from datetime import datetime, timezone


def _entry(source: str, organization: str, resource: dict) -> dict:
    return {
        "sourceKey": source,
        "organizationId": organization,
        "fullUrl": f"http://127.0.0.1/{source}/{resource['resourceType']}/{resource['id']}",
        "resource": resource,
    }


def _patient(resource_id: str, source: str) -> dict:
    identifiers = [{"system": f"https://lab.local/{source}/patient", "value": resource_id}]
    if source == "mini-lis":
        identifiers.append(
            {"system": "https://lab.local/mini-lis/organization/org-mini-his/patient", "value": "MHS-PAT-001"}
        )
    return {
        "resourceType": "Patient",
        "id": resource_id,
        "meta": {"source": f"https://lab.local/{source}"},
        "identifier": identifiers,
    }


def _encounter() -> dict:
    return {
        "resourceType": "Encounter",
        "id": "MHS-CON-001",
        "status": "finished",
        "subject": {"reference": "http://127.0.0.1/mini-his/Patient/MHS-PAT-001"},
        "period": {"end": "2026-09-01T15:00:00Z"},
        "meta": {"source": "https://lab.local/mini-his"},
    }


def _his_order(order_id: str = "MHS-LAB-001", status: str = "active") -> dict:
    return {
        "resourceType": "ServiceRequest",
        "id": order_id,
        "status": status,
        "intent": "order",
        "subject": {"reference": "http://127.0.0.1/mini-his/Patient/MHS-PAT-001"},
        "identifier": [{"system": "https://lab.local/mini-his/order", "value": order_id}],
        "meta": {"source": "https://lab.local/mini-his"},
        "code": {"coding": [{"system": "https://lab.local/mini-his/test", "code": "GLU"}]},
    }


def _lis_order(order_id: str, external_id: str, patient_id: str = "MLS-PAT-001") -> dict:
    return {
        "resourceType": "ServiceRequest",
        "id": order_id,
        "status": "active",
        "intent": "order",
        "subject": {"reference": f"http://127.0.0.1/mini-lis/Patient/{patient_id}"},
        "identifier": [{"system": "https://lab.local/mini-lis/order", "value": external_id}],
        "requester": {"identifier": {"system": "https://lab.local/mini-lis/organization", "value": "org-mini-his"}},
        "meta": {"source": "https://lab.local/mini-lis"},
    }


def _result(result_id: str, order_id: str, status: str = "final", value: str = "141") -> dict:
    return {
        "resourceType": "Observation",
        "id": result_id,
        "status": status,
        "subject": {"reference": "http://127.0.0.1/mini-lis/Patient/MLS-PAT-001"},
        "basedOn": [{"reference": f"http://127.0.0.1/mini-lis/ServiceRequest/{order_id}"}],
        "meta": {"source": "https://lab.local/mini-lis"},
        "valueQuantity": {"value": value, "unit": "mmol/L"},
        "code": {"coding": [{"system": "https://lab.local/mini-lis/test", "code": "GLU"}]},
    }


def _envelope(entries: list[dict], status: str = "complete") -> dict:
    return {
        "status": status,
        "callerSystem": "mini-his",
        "requestingOrganizationId": "org-mini-his",
        "truncated": False,
        "sources": [
            {"sourceKey": "mini-his", "outcome": "complete"},
            {"sourceKey": "mini-lis", "outcome": "complete"},
        ],
        "entries": entries,
    }


def _base() -> list[dict]:
    return [
        _entry("mini-his", "org-mini-his", _patient("MHS-PAT-001", "mini-his")),
        _entry("mini-his", "org-mini-his", _encounter()),
        _entry("mini-his", "org-mini-his", _his_order()),
        _entry("mini-lis", "org-mini-lis", _patient("MLS-PAT-001", "mini-lis")),
        _entry("mini-lis", "org-mini-lis", _lis_order("MLS-ORD-001", "MHS-LAB-001")),
        _entry("mini-lis", "org-mini-lis", _result("MLS-RES-001", "MLS-ORD-001")),
    ]


def test_correlated_final_result_matches_both_sources():
    result, review = evaluate_cross_org_lab_result(_envelope(_base()))
    assert review is not None
    assert result["evaluationStatus"] == "matched"
    assert result["evidence"] == [
        "Encounter/MHS-CON-001",
        "ServiceRequest/MHS-LAB-001",
        "ServiceRequest/MLS-ORD-001",
        "Observation/MLS-RES-001",
    ]
    assert "141" not in result["reasonCodes"]


def test_requester_must_match_the_authenticated_organization():
    envelope = _envelope(_base())
    envelope["requestingOrganizationId"] = "org-other"
    forged = _lis_order("MLS-ORD-001", "MHS-LAB-001")
    forged["requester"] = {"identifier": {"system": "https://lab.local/mini-lis/organization", "value": "org-other"}}
    envelope["entries"][4] = _entry("mini-lis", "org-mini-lis", forged)
    result, review = evaluate_cross_org_lab_result(envelope)
    assert review is None
    assert result["reasonCodes"] == ["organization_correlation_missing"]


def test_two_lis_orders_for_one_his_order_are_ambiguous():
    entries = _base() + [_entry("mini-lis", "org-mini-lis", _lis_order("MLS-ORD-009", "MHS-LAB-001"))]
    result, review = evaluate_cross_org_lab_result(_envelope(entries))
    assert review is None
    assert result["evaluationStatus"] == "insufficient"
    assert result["reasonCodes"] == ["order_correlation_ambiguous"]


def test_preliminary_result_does_not_match():
    entries = _base()
    entries[-1] = _entry("mini-lis", "org-mini-lis", _result("MLS-RES-001", "MLS-ORD-001", "preliminary"))
    result, review = evaluate_cross_org_lab_result(_envelope(entries))
    assert review is None
    assert result["evaluationStatus"] == "not_matched"
    assert result["reasonCodes"] == ["result_not_final"]


def test_recorded_order_is_not_a_submitted_order():
    entries = _base()[:2] + [_entry("mini-his", "org-mini-his", _his_order(status="draft"))]
    result, review = evaluate_cross_org_lab_result(_envelope(entries))
    assert review is None
    assert result["reasonCodes"] == ["order_not_submitted"]


def test_missing_exchange_identifier_is_insufficient():
    entries = _base()
    entries[4] = _entry("mini-lis", "org-mini-lis", _lis_order("MLS-ORD-001", "OTHER-ORDER"))
    result, review = evaluate_cross_org_lab_result(_envelope(entries))
    assert review is None
    assert result["evaluationStatus"] == "insufficient"
    assert result["reasonCodes"] == ["order_correlation_missing"]


def test_patient_without_explicit_link_is_insufficient():
    patient = _patient("MLS-PAT-001", "mini-lis")
    patient["identifier"] = [{"system": "https://lab.local/mini-lis/patient", "value": "MLS-PAT-001"}]
    entries = _base()
    entries[3] = _entry("mini-lis", "org-mini-lis", patient)
    result, review = evaluate_cross_org_lab_result(_envelope(entries))
    assert review is None
    assert result["reasonCodes"] == ["patient_correlation_missing"]


def test_second_order_does_not_replace_the_correlated_one():
    entries = _base() + [
        _entry("mini-his", "org-mini-his", _his_order("MHS-LAB-002")),
        _entry("mini-lis", "org-mini-lis", _lis_order("MLS-ORD-002", "MHS-LAB-002")),
        _entry("mini-lis", "org-mini-lis", _result("MLS-RES-002", "MLS-ORD-009")),
    ]
    result, review = evaluate_cross_org_lab_result(_envelope(entries))
    assert review is not None
    assert "ServiceRequest/MHS-LAB-001" in result["evidence"]
    assert "ServiceRequest/MLS-ORD-002" not in result["evidence"]


def test_same_local_identifier_does_not_cross_sources():
    entries = _base()
    entries[4] = _entry("mini-lis", "org-mini-lis", _lis_order("MHS-LAB-001", "NOT-THE-HIS-ORDER"))
    entries[5] = _entry("mini-lis", "org-mini-lis", _result("MHS-CON-001", "MHS-LAB-001"))
    result, review = evaluate_cross_org_lab_result(_envelope(entries))
    assert review is None
    assert result["reasonCodes"] == ["order_correlation_missing"]


def test_final_result_for_another_order_does_not_match():
    entries = _base()
    entries[5] = _entry("mini-lis", "org-mini-lis", _result("MLS-RES-001", "MLS-ORD-OTHER"))
    result, review = evaluate_cross_org_lab_result(_envelope(entries))
    assert review is None
    assert result["evaluationStatus"] == "not_matched"
    assert result["reasonCodes"] == ["result_order_mismatch"]


def test_partial_envelope_stays_insufficient_before_the_rule():
    result, review = evaluate_federated_protocol(
        _envelope(_base(), status="partial"),
        "cross_org_lab_result",
        datetime(2026, 10, 1, tzinfo=timezone.utc),
    )
    assert review is None
    assert result["evaluationStatus"] == "insufficient"
    assert "federated_context_partial" in result["reasonCodes"]


def test_failed_envelope_is_not_a_clinical_result():
    envelope = _envelope(_base(), status="failed")
    result, review = evaluate_federated_protocol(
        envelope,
        "cross_org_lab_result",
        datetime(2026, 10, 1, tzinfo=timezone.utc),
    )
    assert review is None
    assert result["evaluationStatus"] == "unavailable"


def test_existing_post_consultation_still_matches_without_lis():
    observation = {
        "resourceType": "Observation",
        "id": "MHS-RES-001",
        "status": "final",
        "issued": "2026-09-01T15:10:00Z",
        "subject": {"reference": "http://127.0.0.1/mini-his/Patient/MHS-PAT-001"},
        "encounter": {"reference": "http://127.0.0.1/mini-his/Encounter/MHS-CON-001"},
        "meta": {"source": "https://lab.local/mini-his"},
        "valueQuantity": {"value": 13.4, "unit": "g/dL"},
    }
    entries = [
        _entry("mini-his", "org-mini-his", _patient("MHS-PAT-001", "mini-his")),
        _entry("mini-his", "org-mini-his", _encounter()),
        _entry("mini-his", "org-mini-his", observation),
    ]
    envelope = _envelope(entries)
    instant = datetime(2026, 10, 1, tzinfo=timezone.utc)
    post, post_review = evaluate_federated_protocol(envelope, "post_consultation", instant)
    cross, cross_review = evaluate_federated_protocol(envelope, "cross_org_lab_result", instant)
    assert post_review is not None
    assert post["evaluationStatus"] == "matched"
    assert cross_review is None
    assert cross["evaluationStatus"] == "insufficient"
    assert cross["protocolId"] == "CROSS_ORG_LAB_RESULT_REVIEW_V1"


def test_single_mode_does_not_read_clinical_read_for_the_new_protocol(tmp_path):
    from app.config import Settings
    from app.langgraph_workflow_orchestration import LivePorts, SqliteCheckpointSaver, start_workflow

    class Guard:
        calls = 0

        def search(self, path, expected_resource_type):
            self.calls += 1
            raise AssertionError(path)

        def get(self, path):
            self.calls += 1
            raise AssertionError(path)

    guard = Guard()
    ports = LivePorts(
        Settings(
            model_boundary_base_url="http://interop.test",
            model_boundary_path="/api/model-boundary/v1",
            model_boundary_timeout_seconds=5,
            model_boundary_service_token="read-token",
            host="127.0.0.1",
            port=8090,
            clinical_context_mode="single",
        ),
        object(),
        guard,
        None,
    )
    view = start_workflow(SqliteCheckpointSaver(tmp_path / "single.sqlite3"), ports, "MHS-PAT-001", "cross_org_lab_result")
    assert guard.calls == 0
    assert view["status"] == "completed"
    assert view["protocol"]["reasonCodes"] == ["cross_org_requires_federated_context"]
    assert "human_review" not in view["steps"]


def test_matched_cross_org_case_reaches_human_review(tmp_path):
    from app.config import Settings
    from app.followup_review import FollowUpReviewCaseService
    from app.followup_review_sqlite import SQLiteFollowUpReviewCaseRepository
    from app.human_review_client import _one_workflow
    from app.langgraph_workflow_orchestration import LivePorts, SqliteCheckpointSaver, start_workflow

    class Federation:
        def query(self, identifier_value: str) -> dict:
            assert identifier_value == "MHS-PAT-001"
            return _envelope(_base())

    repository = SQLiteFollowUpReviewCaseRepository(tmp_path / "review.sqlite3")
    repository.initialize()
    ports = LivePorts(
        Settings(
            model_boundary_base_url="http://interop.test",
            model_boundary_path="/api/model-boundary/v1",
            model_boundary_timeout_seconds=5,
            model_boundary_service_token="read-token",
            host="127.0.0.1",
            port=8090,
            clinical_context_mode="federated",
            federation_participant_token="token",
            federation_requesting_organization_id="org-mini-his",
            federation_patient_system_key="mini-his",
            federation_patient_identifier_system="https://lab.local/mini-his/patient",
            federation_sources=("mini-his", "mini-lis"),
            federation_timeout_seconds=5,
        ),
        FollowUpReviewCaseService(repository),
        object(),
        Federation(),
    )
    view = start_workflow(SqliteCheckpointSaver(tmp_path / "workflow.sqlite3"), ports, "MHS-PAT-001", "cross_org_lab_result")
    assert view["status"] == "waiting_human"
    assert view["currentStep"] == "await_human"
    case = repository.get(view["reviewCaseId"])
    assert set(case.matched_resources) == set(view["evidence"])
    assert "Encounter/MHS-CON-001" in case.matched_resources
    assert "ServiceRequest/MHS-LAB-001" in case.matched_resources
    assert "ServiceRequest/MLS-ORD-001" in case.matched_resources
    assert "Observation/MLS-RES-001" in case.matched_resources
    assert "Encounter/MHS-CON-001" in case.narrative_text
    assert "ServiceRequest/MHS-LAB-001" in case.narrative_text
    assert "ServiceRequest/MLS-ORD-001" in case.narrative_text
    assert "Observation/MLS-RES-001" in case.narrative_text
    assert "mini-his" in case.narrative_text
    assert "mini-lis" in case.narrative_text
    assert "no se interpretan" in case.narrative_text
    assert "Quispe" not in case.narrative_text
    html = _one_workflow(case, view)
    assert "Encounter/MHS-CON-001 origen mini-his" in html
    assert "ServiceRequest/MHS-LAB-001 origen mini-his" in html
    assert "ServiceRequest/MLS-ORD-001 origen mini-lis" in html
    assert "Observation/MLS-RES-001 origen mini-lis" in html
    assert "Clinical Read" not in html


def test_federation_auth_and_timeout_do_not_evaluate(tmp_path):
    from app.config import Settings
    from app.langgraph_workflow_orchestration import LivePorts, SqliteCheckpointSaver, start_workflow

    class Denied:
        def __init__(self, code: str) -> None:
            self.code = code

        def query(self, identifier_value: str) -> dict:
            raise FederationClientError(self.code)

    def run(code: str) -> dict:
        ports = LivePorts(
            Settings(
                model_boundary_base_url="http://interop.test",
                model_boundary_path="/api/model-boundary/v1",
                model_boundary_timeout_seconds=5,
                model_boundary_service_token="read-token",
                host="127.0.0.1",
                port=8090,
                clinical_context_mode="federated",
                federation_participant_token="token",
                federation_requesting_organization_id="org-mini-his",
                federation_patient_system_key="mini-his",
                federation_patient_identifier_system="https://lab.local/mini-his/patient",
                federation_sources=("mini-his", "mini-lis"),
                federation_timeout_seconds=5,
            ),
            object(),
            object(),
            Denied(code),
        )
        return start_workflow(SqliteCheckpointSaver(tmp_path / f"{code}.sqlite3"), ports, "MHS-PAT-001", "cross_org_lab_result")

    for code in ("federation_unauthenticated", "federation_unauthorized", "federation_timeout"):
        view = run(code)
        assert view["status"] == "failed"
        assert view.get("protocol", {}).get("evaluationStatus") != "matched"
        assert "human_review" not in view["steps"]


def test_missing_final_result_does_not_open_review():
    result, review = evaluate_cross_org_lab_result(_envelope(_base()[:-1]))
    assert review is None
    assert result["reasonCodes"] == ["final_result_missing"]
