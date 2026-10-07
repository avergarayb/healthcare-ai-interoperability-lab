"""Deterministic AI-assisted review. No network, Gemini, embeddings, or HAPI."""

from __future__ import annotations

import inspect
import json
import logging
import sqlite3
from datetime import datetime, timedelta, timezone
from pathlib import Path
from urllib.parse import urlencode

import pytest
from fastapi.testclient import TestClient

from app.ai_assisted_review import (
    ASSISTANCE_TYPE,
    MAX_OUTPUT_TOKENS,
    OUTPUT_JSON_SCHEMA,
    RAG_QUERIES,
    SYSTEM_INSTRUCTION,
    AssistanceResult,
    ModelAssistanceOutput,
    build_model_input,
    generate_ai_assistance,
)
from app.clinical_review_context import ClinicalReviewContextResponse
from app.config import Settings
from app.followup_review import (
    FollowUpReviewCase,
    FollowUpReviewCaseService,
    ReviewCaseStatus,
    ReviewOutcome,
)
from app.followup_review_sqlite import SQLiteFollowUpReviewCaseRepository
from app.gemini_provider import GeminiProvider
from google.genai.types import ThinkingLevel
from app.human_review_client import (
    FORM_TTL_SECONDS,
    MSG_ASSISTANCE_ORIGIN_INVALID,
    MSG_ASSISTANCE_REQUEST_INVALID,
    MSG_ASSISTANCE_TOKEN_INVALID,
    MSG_CLOSE_INVALID,
    MSG_FORM_INVALID,
    MSG_ORIGIN_INVALID,
    assistance_token_is_valid,
    form_token_is_valid,
    issue_assistance_token,
    issue_form_token,
)
from app.institutional_knowledge import CORPUS_ROOT, RetrievalResult, RetrievedChunk, load_corpus
from app.langgraph_fhir_client import BoundedSearchResult, BoundedSearchStatus, CASE_IDENTIFIER_SYSTEM
from app.llm_provider import ProviderGeneration
from app.main import app, get_settings
from app.missed_follow_up_review import MISSED_FOLLOW_UP_REVIEW_V1
from app.post_consultation_review import (
    POST_CONSULTATION_RESULT_REVIEW_V1,
    ProtocolEvaluationStatus,
    ProtocolReviewResult,
)
from app.review_reason_explanations import REASON_EXPLANATIONS

SIGNING_SECRET = "synthetic-form-signing-secret-b"
ORIGIN = {"origin": "http://testserver"}
CASE = "SENTINEL-CASE"
PATIENT = "SENTINEL-PATIENT"
NOW = datetime(2026, 9, 30, 12, 0, tzinfo=timezone.utc)
CHUNK_A = "a" * 64
CHUNK_B = "b" * 64
SUMMARY = "Review the operational follow-up step."
POINT = "Confirm the recorded operational status."


class Clock:
    def __init__(self) -> None:
        self.value = NOW

    def __call__(self):
        current = self.value
        self.value += timedelta(seconds=1)
        return current


class ScriptedFhir:
    def __init__(self) -> None:
        self.calls: list[tuple] = []
        self.encounter = {
            "resourceType": "Encounter",
            "id": "SENTINEL-ENC",
            "status": "finished",
            "subject": {"reference": f"Patient/{PATIENT}"},
            "period": {"start": "2026-09-30T11:00:00Z", "end": "2026-09-30T11:30:00Z"},
        }
        self.observation = {
            "resourceType": "Observation",
            "id": "SENTINEL-OBS",
            "status": "final",
            "subject": {"reference": f"Patient/{PATIENT}"},
            "encounter": {"reference": "Encounter/SENTINEL-ENC"},
            "issued": "2026-09-30T11:20:00Z",
            "code": {
                "coding": [{"system": "http://loinc.org", "code": "1234-5", "display": "Allowed Display"}],
                "text": "SENTINEL-CODE-TEXT",
            },
            "valueString": "SENTINEL-OBS-VALUE",
        }
        self.appointments = [
            {
                "resourceType": "Appointment",
                "id": "SENTINEL-APPT",
                "status": "booked",
                "start": "2099-01-01T00:00:00Z",
                "participant": [{"actor": {"reference": f"Patient/{PATIENT}"}, "status": "accepted"}],
            }
        ]
        self.patient_status = BoundedSearchStatus.COMPLETE
        self.appointment_status = BoundedSearchStatus.COMPLETE

    def search(self, path: str, expected_resource_type: str):
        self.calls.append(("search", expected_resource_type, path))
        if expected_resource_type == "Patient":
            patient = {
                "resourceType": "Patient",
                "id": PATIENT,
                "name": [{"text": "SENTINEL-NAME"}],
                "birthDate": "SENTINEL-DOB",
                "identifier": [
                    {"system": CASE_IDENTIFIER_SYSTEM, "value": CASE},
                    {"system": "http://example.test/mrn", "value": "SENTINEL-MRN"},
                ],
            }
            return BoundedSearchResult(self.patient_status, (patient,))
        return BoundedSearchResult(self.appointment_status, tuple(self.appointments))

    def read_exact(self, resource_type: str, resource_id: str) -> dict:
        self.calls.append(("exact", resource_type, resource_id))
        if resource_type == "Encounter":
            return dict(self.encounter)
        if resource_type == "Observation":
            return dict(self.observation)
        if resource_type == "Appointment":
            for item in self.appointments:
                if item.get("id") == resource_id:
                    return dict(item)
        from app.langgraph_fhir_hapi import ExactResourceNotFound

        raise ExactResourceNotFound()

    def update(self, *args, **kwargs):
        raise AssertionError("FHIR write")

    def create(self, *args, **kwargs):
        raise AssertionError("FHIR write")


class FakeKnowledge:
    def __init__(self, status="FOUND", chunks=(), explode: Exception | None = None) -> None:
        self.status = status
        self.chunks = tuple(chunks)
        self.explode = explode
        self.requests = []

    def retrieve(self, request):
        self.requests.append(request)
        if self.explode is not None:
            raise self.explode
        return RetrievalResult(status=self.status, protocol_id=request.protocolId, chunks=self.chunks)


class FakeProvider:
    def __init__(self, text: str | None = None, error: str | None = None, explode: Exception | None = None) -> None:
        self.text = text
        self.error = error
        self.explode = explode
        self.calls = []

    def generate_structured(self, *, system_instruction, contents, response_json_schema, max_output_tokens):
        self.calls.append(
            {
                "system_instruction": system_instruction,
                "contents": contents,
                "response_json_schema": response_json_schema,
                "max_output_tokens": max_output_tokens,
            }
        )
        if self.explode is not None:
            raise self.explode
        if self.error is not None:
            return ProviderGeneration(invocation_started=True, error=self.error)
        return ProviderGeneration(invocation_started=True, text=self.text)


def _settings(**overrides) -> Settings:
    values = dict(
        model_boundary_base_url="http://model-boundary.test",
        model_boundary_path="/api/model-boundary/v1",
        model_boundary_timeout_seconds=5,
        model_boundary_service_token="synthetic-service-token-a",
        human_review_form_signing_secret=SIGNING_SECRET,
        host="127.0.0.1",
        port=8090,
        followup_agent_enabled=True,
        ai_review_db_path="unused-by-explicit-test-repository.sqlite3",
        gemini_api_key="",
        gemini_model="gemini-flash-latest",
    )
    values.update(overrides)
    return Settings(**values)


def _protocol(protocol_id=POST_CONSULTATION_RESULT_REVIEW_V1):
    if protocol_id == MISSED_FOLLOW_UP_REVIEW_V1:
        return ProtocolReviewResult(
            id=protocol_id,
            evaluation_status=ProtocolEvaluationStatus.MATCHED,
            reason_codes=("missed_follow_up_without_confirmed_replacement",),
            matched_resources=("Appointment/SENTINEL-APPT",),
            human_review_status="required",
            human_review_reason="deterministic_missed_follow_up_protocol_match",
            action_status="proposed",
            action_type="review_follow_up_case",
        )
    return ProtocolReviewResult(
        id=protocol_id,
        evaluation_status=ProtocolEvaluationStatus.MATCHED,
        reason_codes=("post_consultation_result_requires_review",),
        matched_resources=("Encounter/SENTINEL-ENC", "Observation/SENTINEL-OBS"),
        human_review_status="required",
        human_review_reason="deterministic_post_consultation_protocol_match",
        action_status="proposed",
        action_type="review_follow_up_case",
    )


def _repository(tmp_path):
    repository = SQLiteFollowUpReviewCaseRepository(tmp_path / "review.sqlite3", clock=Clock())
    repository.initialize()
    return repository


def _create(repository, protocol_id=POST_CONSULTATION_RESULT_REVIEW_V1, case_id=CASE):
    case = FollowUpReviewCaseService(repository).ensure_for_protocol(case_id, _protocol(protocol_id))
    assert case is not None
    return case


def _chunk(chunk_id=CHUNK_A, text="Institutional procedure text.", title="Procedure title", section="Purpose") -> RetrievedChunk:
    return RetrievedChunk(
        document_id="SENTINEL-DOC",
        title=title,
        version="1.0",
        document_status="active",
        section=section,
        ordinal=1,
        chunk_id=chunk_id,
        content_hash="c" * 64,
        language="en",
        synthetic=True,
        score=0.9137,
        text=text,
    )


def _valid_output(chunk_ids=(CHUNK_A,), summary=SUMMARY, point=POINT, limitations=("Synthetic guidance only.",)) -> str:
    return json.dumps(
        {
            "summary": {"text": summary, "citedChunkIds": list(chunk_ids)},
            "reviewPoints": [{"text": point, "citedChunkIds": list(chunk_ids)}],
            "limitations": list(limitations),
        }
    )


def _context_payload(case: FollowUpReviewCase) -> ClinicalReviewContextResponse:
    body = {
        "schema": "CLINICAL_REVIEW_CONTEXT_V1",
        "reviewCase": {"reviewCaseId": case.id, "status": "open", "version": case.version},
        "triggerProvenance": {
            "protocolId": case.protocol_id,
            "evaluationStatus": "matched",
            "reasonCodes": list(case.reason_codes),
            "matchedResources": list(case.matched_resources),
            "createdAt": case.created_at,
        },
        "retrieval": {
            "status": "complete",
            "retrievedAt": "2026-10-07T00:00:00.000000Z",
            "source": "fhir_current",
            "reasonCodes": ["current_context_complete"],
        },
        "currentContext": {
            "patient": {"resolution": "resolved"},
            "appointments": {
                "collectionStatus": "complete",
                "classifications": ["UPCOMING_CONFIRMED"],
                "items": [
                    {
                        "reference": "Appointment/SENTINEL-APPT",
                        "status": "booked",
                        "start": "2099-01-01T00:00:00Z",
                        "classification": "UPCOMING_CONFIRMED",
                    }
                ],
            },
        },
    }
    if case.protocol_id == MISSED_FOLLOW_UP_REVIEW_V1:
        body["currentContext"]["triggerAppointment"] = {
            "reference": "Appointment/SENTINEL-APPT",
            "availability": "available",
            "status": "noshow",
            "start": "2020-01-01T00:00:00Z",
        }
    else:
        body["currentContext"]["encounter"] = {
            "reference": "Encounter/SENTINEL-ENC",
            "availability": "available",
            "status": "finished",
            "period": {"start": "2026-09-30T11:00:00Z"},
        }
        body["currentContext"]["observation"] = {
            "reference": "Observation/SENTINEL-OBS",
            "availability": "available",
            "status": "final",
            "issued": "2026-09-30T11:20:00Z",
            "encounterReference": "Encounter/SENTINEL-ENC",
            "code": {
                "status": "available",
                "coding": [{"code": "1234-5", "display": "Allowed Display"}],
                "text": "SENTINEL-CODE-TEXT",
            },
            "content": {"status": "available", "kind": "string", "value": "SENTINEL-OBS-VALUE"},
        }
    return ClinicalReviewContextResponse.model_validate(body)


@pytest.fixture(autouse=True)
def _clean_state():
    app.dependency_overrides.clear()
    for name in (
        "followup_review_repository",
        "clinical_context_fhir_client",
        "institutional_knowledge",
        "ai_assistance_provider",
    ):
        if hasattr(app.state, name):
            delattr(app.state, name)
    yield
    app.dependency_overrides.clear()
    for name in (
        "followup_review_repository",
        "clinical_context_fhir_client",
        "institutional_knowledge",
        "ai_assistance_provider",
    ):
        if hasattr(app.state, name):
            delattr(app.state, name)


def _client(repository, fhir=None, knowledge=None, provider=None, settings=None):
    app.state.followup_review_repository = repository
    if fhir is not None:
        app.state.clinical_context_fhir_client = lambda: fhir
    if knowledge is not None:
        app.state.institutional_knowledge = knowledge
    if provider is not None:
        app.state.ai_assistance_provider = provider
    app.dependency_overrides[get_settings] = lambda: settings or _settings()
    return TestClient(app)


def _assistance_fields(html: str) -> dict[str, str]:
    fields = {}
    for name in ("assistanceExpiry", "assistanceToken"):
        marker = f'name="{name}" value="'
        start = html.index(marker) + len(marker)
        fields[name] = html[start:html.index('"', start)]
    return fields


def _close_fields(html: str) -> dict[str, str]:
    fields = {}
    for name in ("expectedVersion", "formToken", "formExpiry"):
        marker = f'name="{name}" value="'
        start = html.index(marker) + len(marker)
        fields[name] = html[start:html.index('"', start)]
    return fields


def _post_assistance(client, case_id, html, **overrides):
    fields = _assistance_fields(html)
    payload = {"assistanceExpiry": fields["assistanceExpiry"], "assistanceToken": fields["assistanceToken"]}
    payload.update(overrides)
    return client.post(
        f"/review-cases/{case_id}/ai-assistance",
        content=urlencode(payload),
        headers={**ORIGIN, "content-type": "application/x-www-form-urlencoded"},
    )


def _tables(path) -> list:
    connection = sqlite3.connect(path)
    try:
        names = connection.execute(
            "SELECT name FROM sqlite_master WHERE type='table' ORDER BY 1"
        ).fetchall()
        version = connection.execute("PRAGMA user_version").fetchone()
        return [names, version]
    finally:
        connection.close()


def test_reason_explanations_have_one_source():
    sentence = "A post-consultation result was selected for operational review."
    missed = "No confirmed future follow-up was recorded at the time the case was created."
    root = Path(__file__).resolve().parents[1] / "app"
    shared = (root / "review_reason_explanations.py").read_text(encoding="utf-8")
    human = (root / "human_review_client.py").read_text(encoding="utf-8")
    assisted = (root / "ai_assisted_review.py").read_text(encoding="utf-8")
    assert sentence in shared and missed in shared
    assert sentence not in human and missed not in human
    assert sentence not in assisted and missed not in assisted
    assert set(REASON_EXPLANATIONS) == {
        "post_consultation_result_requires_review",
        "missed_follow_up_without_confirmed_replacement",
    }


def test_module_does_not_use_langgraph_or_legacy_summary():
    source = Path(__file__).resolve().parents[1].joinpath("app", "ai_assisted_review.py").read_text(encoding="utf-8")
    for token in ("langgraph", "generate_summary", "ToolNode", "generate_content"):
        assert token not in source
    provider = inspect.getsource(GeminiProvider.generate_structured)
    assert "attempts=1" in provider
    assert "response_json_schema" in provider
    assert "max_output_tokens" in provider
    assert "tools=" not in provider


def test_structured_provider_sends_json_schema_without_tools(monkeypatch):
    captured = {}

    class Models:
        def generate_content(self, *, model, contents, config):
            captured["model"] = model
            captured["contents"] = contents
            captured["config"] = config

            class Response:
                text = '{"summary":{"text":"ok","citedChunkIds":["aa"]}}'

            return Response()

    class Client:
        def __init__(self, **kwargs):
            captured["options"] = kwargs
            self.models = Models()

    import google.genai

    monkeypatch.setattr(google.genai, "Client", Client)
    provider = GeminiProvider(api_key="test-key", model="gemini-flash-latest")
    result = provider.generate_structured(
        system_instruction="instructions",
        contents="SENTINEL-PAYLOAD",
        response_json_schema=OUTPUT_JSON_SCHEMA,
        max_output_tokens=MAX_OUTPUT_TOKENS,
    )
    assert result.text is not None
    assert captured["model"] == "gemini-flash-latest"
    assert captured["contents"] == "SENTINEL-PAYLOAD"
    assert captured["config"].response_mime_type == "application/json"
    assert captured["config"].max_output_tokens == 1024
    assert captured["config"].response_json_schema == OUTPUT_JSON_SCHEMA
    assert captured["config"].tools is None
    assert captured["config"].thinking_config.thinking_level == ThinkingLevel.LOW
    assert captured["config"].thinking_config.thinking_budget is None
    assert captured["options"]["http_options"].retry_options.attempts == 1
    for forbidden in ("diagnosis", "riskScore", "urgency", "severity", "treatment", "reviewOutcome"):
        assert forbidden not in OUTPUT_JSON_SCHEMA["properties"]


def test_gemini_25_flash_structured_generation_disables_thinking(monkeypatch):
    captured = _capture_structured_call(monkeypatch, _response(text='{"ok":true}', finish="STOP"))
    provider = GeminiProvider(api_key="test-key", model="gemini-2.5-flash")
    result = provider.generate_structured(
        system_instruction="instructions",
        contents="payload",
        response_json_schema=OUTPUT_JSON_SCHEMA,
        max_output_tokens=MAX_OUTPUT_TOKENS,
    )
    thinking = captured["config"].thinking_config
    assert result.text == '{"ok":true}'
    assert thinking.thinking_budget == 0
    assert thinking.thinking_level in (None, ThinkingLevel.THINKING_LEVEL_UNSPECIFIED)
    assert captured["config"].max_output_tokens == 1024


def test_max_tokens_discards_partial_json_without_retry(monkeypatch):
    captured = _capture_structured_call(
        monkeypatch,
        _response(text='{"summary":{"text":"partial"', finish="MAX_TOKENS"),
    )
    provider = GeminiProvider(api_key="test-key", model="gemini-flash-latest")
    result = provider.generate_structured(
        system_instruction="instructions",
        contents="payload",
        response_json_schema=OUTPUT_JSON_SCHEMA,
        max_output_tokens=MAX_OUTPUT_TOKENS,
    )
    assert result.error == "max_tokens"
    assert result.text is None
    assert captured["calls"] == 1
    assert captured["options"]["http_options"].retry_options.attempts == 1


def test_max_tokens_does_not_reach_output_validation():
    case = _standalone_case(POST_CONSULTATION_RESULT_REVIEW_V1)

    class _TruncatedProvider:
        def __init__(self) -> None:
            self.calls = []

        def generate_structured(self, **kwargs):
            self.calls.append(kwargs)
            return ProviderGeneration(invocation_started=True, error="max_tokens", text=_valid_output())

    provider = _TruncatedProvider()
    outcome = generate_ai_assistance(
        case=case,
        context_reader=lambda: _context_payload(case),
        knowledge=FakeKnowledge(chunks=(_chunk(),)),
        provider=provider,
        correlation_id="corr-max-tokens",
    )
    assert provider.calls[0]["max_output_tokens"] == 1024
    assert len(provider.calls) == 1
    assert outcome.result.status == "unavailable"
    assert outcome.result.reason == "invalid_output"
    assert outcome.result.summary is None
    assert outcome.result.model_called is True


def test_stop_response_continues_through_output_validation(monkeypatch):
    text = _valid_output()
    captured = _capture_structured_call(monkeypatch, _response(text=text, finish="STOP"))
    provider = GeminiProvider(api_key="test-key", model="gemini-flash-latest")
    generation = provider.generate_structured(
        system_instruction="instructions",
        contents="payload",
        response_json_schema=OUTPUT_JSON_SCHEMA,
        max_output_tokens=MAX_OUTPUT_TOKENS,
    )
    assert generation.error is None
    assert generation.text == text
    assert captured["calls"] == 1

    class _StoppedProvider(FakeProvider):
        def generate_structured(self, **kwargs):
            self.calls.append(kwargs)
            return ProviderGeneration(invocation_started=True, text=generation.text)

    case = _standalone_case(POST_CONSULTATION_RESULT_REVIEW_V1)
    stopped = _StoppedProvider()
    outcome = generate_ai_assistance(
        case=case,
        context_reader=lambda: _context_payload(case),
        knowledge=FakeKnowledge(chunks=(_chunk(),)),
        provider=stopped,
        correlation_id="corr-stop",
    )
    assert outcome.result.status == "available"
    assert outcome.result.summary is not None
    assert outcome.result.summary.citations[0].chunk_id == CHUNK_A


def test_empty_and_malformed_provider_responses_stay_rejected(monkeypatch):
    empty = _capture_structured_call(monkeypatch, _response(text="   ", finish="STOP"))
    provider = GeminiProvider(api_key="test-key", model="gemini-flash-latest")
    empty_result = provider.generate_structured(
        system_instruction="instructions",
        contents="payload",
        response_json_schema=OUTPUT_JSON_SCHEMA,
        max_output_tokens=MAX_OUTPUT_TOKENS,
    )
    assert empty_result.error == "empty"
    assert empty_result.text is None
    assert empty["calls"] == 1

    malformed = _capture_structured_call(monkeypatch, _response(text=None, finish="STOP"))
    malformed_result = provider.generate_structured(
        system_instruction="instructions",
        contents="payload",
        response_json_schema=OUTPUT_JSON_SCHEMA,
        max_output_tokens=MAX_OUTPUT_TOKENS,
    )
    assert malformed_result.error == "malformed"
    assert malformed_result.text is None
    assert malformed["calls"] == 1


def _capture_structured_call(monkeypatch, response):
    captured = {"calls": 0}

    class Models:
        def generate_content(self, *, model, contents, config):
            captured["calls"] += 1
            captured["model"] = model
            captured["contents"] = contents
            captured["config"] = config
            return response

    class Client:
        def __init__(self, **kwargs):
            captured["options"] = kwargs
            self.models = Models()

    import google.genai

    monkeypatch.setattr(google.genai, "Client", Client)
    return captured


def _response(*, text, finish: str):
    class Finish:
        name = finish

    class Candidate:
        finish_reason = Finish()

    class Response:
        candidates = [Candidate()]

    response = Response()
    response.text = text
    return response


def test_tokens_are_purpose_separated():
    review_case_id = "00000000-0000-4000-8000-000000000001"
    close_token, expiry = issue_form_token(
        secret=SIGNING_SECRET,
        review_case_id=review_case_id,
        expected_version=1,
        now=1_000,
    )
    assistance_token, assistance_expiry = issue_assistance_token(
        secret=SIGNING_SECRET,
        review_case_id=review_case_id,
        now=1_000,
    )
    assert expiry == assistance_expiry
    assert close_token != assistance_token
    other_case_id = "00000000-0000-4000-8000-000000000002"
    assert assistance_token_is_valid(
        secret=SIGNING_SECRET,
        review_case_id=review_case_id,
        expiry=expiry,
        token=assistance_token,
        now=expiry - 1,
    )
    assert not assistance_token_is_valid(
        secret=SIGNING_SECRET,
        review_case_id=review_case_id,
        expiry=expiry,
        token=assistance_token,
        now=expiry,
    )
    assert not assistance_token_is_valid(
        secret=SIGNING_SECRET,
        review_case_id=other_case_id,
        expiry=expiry,
        token=assistance_token,
        now=1_000,
    )
    assert expiry == 1_000 + FORM_TTL_SECONDS
    assert not assistance_token_is_valid(
        secret=SIGNING_SECRET,
        review_case_id=review_case_id,
        expiry=expiry,
        token=close_token,
        now=1_000,
    )
    assert not form_token_is_valid(
        secret=SIGNING_SECRET,
        review_case_id=review_case_id,
        expected_version=1,
        expiry=expiry,
        token=assistance_token,
        now=1_000,
    )


@pytest.mark.parametrize("protocol_id", [POST_CONSULTATION_RESULT_REVIEW_V1, MISSED_FOLLOW_UP_REVIEW_V1])
def test_open_case_generation_projects_trusted_sources(protocol_id):
    case = _standalone_case(protocol_id)
    context = _context_payload(case)
    knowledge = FakeKnowledge(chunks=(_chunk(),))
    provider = FakeProvider(text=_valid_output())
    outcome = generate_ai_assistance(
        case=case,
        context_reader=lambda: context,
        knowledge=knowledge,
        provider=provider,
        correlation_id="corr-1",
    )
    assert outcome.result.status == "available"
    assert outcome.result.assistance_type == ASSISTANCE_TYPE
    assert outcome.result.human_review_required is True
    assert outcome.result.summary is not None
    assert outcome.result.summary.citations[0].title == "Procedure title"
    assert outcome.result.summary.citations[0].chunk_id == CHUNK_A
    assert outcome.result.sources[0].text == "Institutional procedure text."
    assert knowledge.requests[0].queryText == RAG_QUERIES[protocol_id]
    assert knowledge.requests[0].topK == 3
    payload = provider.calls[0]["contents"]
    parsed = json.loads(payload)
    assert parsed["deterministicCaseFacts"]["protocolId"] == protocol_id
    assert "evaluationStatus" not in json.dumps(parsed["deterministicCaseFacts"])
    assert parsed["institutionalDocumentData"][0]["contentRole"] == "institutional_document_data"
    assert "score" not in parsed["institutionalDocumentData"][0]
    assert "0.9137" not in payload
    assert "SENTINEL-DOC" not in payload
    assert "Procedure title" not in payload
    assert provider.calls[0]["max_output_tokens"] == 1024
    assert provider.calls[0]["system_instruction"] == SYSTEM_INSTRUCTION


def test_model_input_excludes_identity_values_and_timestamps():
    case = _standalone_case(POST_CONSULTATION_RESULT_REVIEW_V1)
    context = _context_payload(case)
    payload = json.dumps(build_model_input(case, context, (_chunk(),)))
    for secret in (
        CASE,
        case.id,
        PATIENT,
        "SENTINEL-NAME",
        "SENTINEL-MRN",
        "SENTINEL-DOB",
        "SENTINEL-OBS",
        "SENTINEL-ENC",
        "SENTINEL-APPT",
        "SENTINEL-OBS-VALUE",
        "SENTINEL-CODE-TEXT",
        "SENTINEL-DOC",
        "2026-09-30T11:00:00Z",
        "2026-09-30T11:20:00Z",
        "2099-01-01T00:00:00Z",
        "matchedResources",
        "valueString",
        "valueQuantity",
    ):
        assert secret not in payload
    parsed = json.loads(payload)
    assert parsed["currentFhirFacts"]["observation"] == {
        "availability": "available",
        "status": "final",
        "code": [{"code": "1234-5", "display": "Allowed Display"}],
    }
    assert parsed["currentFhirFacts"]["encounter"] == {"availability": "available", "status": "finished"}
    assert parsed["currentFhirFacts"]["appointments"]["confirmedFutureFollowUpPresent"] is True
    assert parsed["currentFhirFacts"]["appointments"]["count"] == 1
    assert "items" not in parsed["currentFhirFacts"]["appointments"]


def test_rag_query_is_the_server_phrase_only():
    case = _standalone_case(MISSED_FOLLOW_UP_REVIEW_V1)
    knowledge = FakeKnowledge(chunks=(_chunk(),))
    provider = FakeProvider(text=_valid_output())
    generate_ai_assistance(
        case=case,
        context_reader=lambda: _context_payload(case),
        knowledge=knowledge,
        provider=provider,
        correlation_id="corr-rag",
    )
    request = knowledge.requests[0]
    assert request.queryText == "missed follow-up appointment"
    rendered = json.dumps(request.model_dump())
    for secret in (CASE, case.id, PATIENT, "SENTINEL-OBS-VALUE", "SENTINEL-APPT", "2099-01-01T00:00:00Z"):
        assert secret not in rendered
    assert request.reasonCodes is None


@pytest.mark.parametrize(
    ("status", "reason"),
    [("NO_RELEVANT_GUIDANCE", "no_relevant_guidance"), ("UNAVAILABLE", "retrieval_unavailable")],
)
def test_retrieval_failure_does_not_call_generation(status, reason):
    case = _standalone_case(POST_CONSULTATION_RESULT_REVIEW_V1)
    provider = FakeProvider(text=_valid_output())
    calls = {"context": 0}

    def reader():
        calls["context"] += 1
        return _context_payload(case)

    outcome = generate_ai_assistance(
        case=case,
        context_reader=reader,
        knowledge=FakeKnowledge(status=status),
        provider=provider,
        correlation_id="corr-rag-fail",
    )
    assert outcome.result.status == "unavailable"
    assert outcome.result.reason == reason
    assert outcome.result.model_called is False
    assert provider.calls == []
    assert calls["context"] == 1


def test_closed_and_unsupported_cases_stop_before_context():
    closed = _standalone_case(POST_CONSULTATION_RESULT_REVIEW_V1, status=ReviewCaseStatus.CLOSED)
    unsupported = _standalone_case(
        POST_CONSULTATION_RESULT_REVIEW_V1,
        reason_codes=("confirmed_future_follow_up_exists",),
    )

    def explode():
        raise AssertionError("context was read")

    closed_result = generate_ai_assistance(
        case=closed,
        context_reader=explode,
        knowledge=FakeKnowledge(),
        provider=FakeProvider(text=_valid_output()),
        correlation_id="corr-closed",
    )
    unsupported_result = generate_ai_assistance(
        case=unsupported,
        context_reader=explode,
        knowledge=FakeKnowledge(),
        provider=FakeProvider(text=_valid_output()),
        correlation_id="corr-invalid",
    )
    assert closed_result.result.reason == "case_not_open"
    assert unsupported_result.result.reason == "invalid_case_context"
    assert closed_result.context is None
    assert unsupported_result.context is None


@pytest.mark.parametrize(
    "text",
    [
        "not-json",
        json.dumps({"summary": {"text": SUMMARY, "citedChunkIds": [CHUNK_A]}, "reviewPoints": [], "limitations": []}),
        json.dumps(
            {
                "summary": {"text": SUMMARY, "citedChunkIds": [CHUNK_A]},
                "reviewPoints": [{"text": POINT, "citedChunkIds": [CHUNK_A]}],
                "limitations": [],
                "diagnosis": "not allowed",
            }
        ),
        json.dumps(
            {
                "summary": {"text": SUMMARY, "citedChunkIds": [CHUNK_B]},
                "reviewPoints": [{"text": POINT, "citedChunkIds": [CHUNK_A]}],
                "limitations": [],
            }
        ),
        json.dumps(
            {
                "summary": {"text": SUMMARY, "citedChunkIds": [CHUNK_A, CHUNK_A]},
                "reviewPoints": [{"text": POINT, "citedChunkIds": [CHUNK_A]}],
                "limitations": [],
            }
        ),
        json.dumps(
            {
                "summary": {"text": "", "citedChunkIds": [CHUNK_A]},
                "reviewPoints": [{"text": POINT, "citedChunkIds": [CHUNK_A]}],
                "limitations": [],
            }
        ),
        json.dumps(
            {
                "summary": {"text": "x" * 601, "citedChunkIds": [CHUNK_A]},
                "reviewPoints": [{"text": POINT, "citedChunkIds": [CHUNK_A]}],
                "limitations": [],
            }
        ),
        json.dumps(
            {
                "summary": {"text": SUMMARY, "citedChunkIds": []},
                "reviewPoints": [{"text": POINT, "citedChunkIds": [CHUNK_A]}],
                "limitations": [],
            }
        ),
    ],
)
def test_invalid_output_discards_the_whole_response(text):
    case = _standalone_case(POST_CONSULTATION_RESULT_REVIEW_V1)
    outcome = generate_ai_assistance(
        case=case,
        context_reader=lambda: _context_payload(case),
        knowledge=FakeKnowledge(chunks=(_chunk(),)),
        provider=FakeProvider(text=text),
        correlation_id="corr-invalid-output",
    )
    assert outcome.result.status == "unavailable"
    assert outcome.result.reason == "invalid_output"
    assert outcome.result.summary is None
    assert outcome.result.review_points == ()


@pytest.mark.parametrize("blank", [" ", "\n", "\t", " \n\t "])
def test_whitespace_only_summary_review_point_and_limitation_are_invalid(blank):
    case = _standalone_case(POST_CONSULTATION_RESULT_REVIEW_V1)
    bodies = (
        _valid_output(summary=blank),
        _valid_output(point=blank),
        _valid_output(limitations=(blank,)),
    )
    for text in bodies:
        outcome = generate_ai_assistance(
            case=case,
            context_reader=lambda: _context_payload(case),
            knowledge=FakeKnowledge(chunks=(_chunk(),)),
            provider=FakeProvider(text=text),
            correlation_id="corr-blank",
        )
        assert outcome.result.status == "unavailable"
        assert outcome.result.reason == "invalid_output"
        assert outcome.result.summary is None


def test_surrounding_whitespace_around_meaningful_text_is_preserved():
    case = _standalone_case(POST_CONSULTATION_RESULT_REVIEW_V1)
    summary = f"  {SUMMARY}  "
    point = f"\n{POINT}\t"
    limitation = f"  Synthetic guidance only.  "
    outcome = generate_ai_assistance(
        case=case,
        context_reader=lambda: _context_payload(case),
        knowledge=FakeKnowledge(chunks=(_chunk(),)),
        provider=FakeProvider(text=_valid_output(summary=summary, point=point, limitations=(limitation,))),
        correlation_id="corr-whitespace",
    )
    assert outcome.result.status == "available"
    assert outcome.result.summary is not None
    assert outcome.result.summary.text == summary
    assert outcome.result.review_points[0].text == point
    assert outcome.result.limitations == (limitation,)


@pytest.mark.parametrize(
    "text",
    [
        (
            '{"summary":{"text":"%s","citedChunkIds":["%s"]},"summary":{"text":"%s","citedChunkIds":["%s"]},'
            '"reviewPoints":[{"text":"%s","citedChunkIds":["%s"]}],"limitations":[]}'
        ) % (SUMMARY, CHUNK_A, SUMMARY, CHUNK_A, POINT, CHUNK_A),
        (
            '{"summary":{"text":"%s","text":"%s","citedChunkIds":["%s"]},'
            '"reviewPoints":[{"text":"%s","citedChunkIds":["%s"]}],"limitations":[]}'
        ) % (SUMMARY, SUMMARY, CHUNK_A, POINT, CHUNK_A),
        (
            '{"summary":{"text":"%s","citedChunkIds":["%s"]},'
            '"reviewPoints":[{"text":"%s","text":"%s","citedChunkIds":["%s"]}],"limitations":[]}'
        ) % (SUMMARY, CHUNK_A, POINT, POINT, CHUNK_A),
    ],
)
def test_duplicate_json_keys_are_invalid_output(text):
    case = _standalone_case(POST_CONSULTATION_RESULT_REVIEW_V1)
    outcome = generate_ai_assistance(
        case=case,
        context_reader=lambda: _context_payload(case),
        knowledge=FakeKnowledge(chunks=(_chunk(),)),
        provider=FakeProvider(text=text),
        correlation_id="corr-duplicate-key",
    )
    assert outcome.result.status == "unavailable"
    assert outcome.result.reason == "invalid_output"
    assert outcome.result.summary is None


def test_empty_gemini_response_is_invalid_output():
    case = _standalone_case(POST_CONSULTATION_RESULT_REVIEW_V1)
    for provider in (FakeProvider(text=""), FakeProvider(error="empty")):
        outcome = generate_ai_assistance(
            case=case,
            context_reader=lambda: _context_payload(case),
            knowledge=FakeKnowledge(chunks=(_chunk(),)),
            provider=provider,
            correlation_id="corr-empty",
        )
        assert outcome.result.status == "unavailable"
        assert outcome.result.reason == "invalid_output"
        assert outcome.result.summary is None


def test_provider_failure_is_coarse(caplog):
    case = _standalone_case(POST_CONSULTATION_RESULT_REVIEW_V1)
    caplog.set_level(logging.INFO, logger="ai-service.ai-assistance")
    outcome = generate_ai_assistance(
        case=case,
        context_reader=lambda: _context_payload(case),
        knowledge=FakeKnowledge(chunks=(_chunk(text="SENTINEL-CHUNK-TEXT"),)),
        provider=FakeProvider(explode=RuntimeError("SENTINEL-PROVIDER-PAYLOAD")),
        correlation_id="corr-provider",
    )
    assert outcome.result.reason == "provider_unavailable"
    assert outcome.result.model_called is True
    assert "SENTINEL-PROVIDER-PAYLOAD" not in caplog.text
    assert "SENTINEL-CHUNK-TEXT" not in caplog.text
    assert "post consultation result follow-up" not in caplog.text


def test_refresh_after_generation_does_not_call_gemini_again(tmp_path):
    repository = _repository(tmp_path)
    case = _create(repository)
    before = _tables(repository.database_path)
    fhir = ScriptedFhir()
    knowledge = FakeKnowledge(chunks=(_chunk(),))
    provider = FakeProvider(text=_valid_output(summary="SENTINEL-GENERATED-ONCE"))
    client = _client(repository, fhir, knowledge, provider)
    page = client.get(f"/review-cases/{case.id}")
    assert "Not generated." in page.text
    assert 'method="post"' in page.text
    posted = client.post(
        f"/review-cases/{case.id}/ai-assistance",
        content=urlencode(_assistance_fields(page.text)),
        headers={**ORIGIN, "content-type": "application/x-www-form-urlencoded"},
        follow_redirects=False,
    )
    assert posted.status_code == 303
    assert posted.headers["location"] == f"/review-cases/{case.id}"
    assert "SENTINEL-GENERATED-ONCE" not in posted.text
    assert len(provider.calls) == 1
    shown = client.get(posted.headers["location"])
    assert shown.status_code == 200
    assert "SENTINEL-GENERATED-ONCE" in shown.text
    assert "Not generated." not in shown.text
    refreshed = client.get(f"/review-cases/{case.id}")
    assert "Not generated." in refreshed.text
    assert "SENTINEL-GENERATED-ONCE" not in refreshed.text
    assert "Generate AI assistance" in refreshed.text
    assert len(provider.calls) == 1
    assert len(knowledge.requests) == 1
    stored = FollowUpReviewCaseService(repository).get(case.id)
    assert stored.status is ReviewCaseStatus.OPEN
    assert stored.version == 1
    assert _tables(repository.database_path) == before
    explicit = _post_assistance(client, case.id, refreshed.text)
    assert explicit.status_code == 200
    assert len(provider.calls) == 2


def test_assistance_ticket_does_not_cross_cases(tmp_path):
    repository = _repository(tmp_path)
    case = _create(repository)
    other = _create(repository, case_id="SENTINEL-CASE-2")
    fhir = ScriptedFhir()
    knowledge = FakeKnowledge(chunks=(_chunk(),))
    provider = FakeProvider(text=_valid_output(summary="SENTINEL-CASE-A-ONLY"))
    client = _client(repository, fhir, knowledge, provider)
    page = client.get(f"/review-cases/{case.id}")
    posted = client.post(
        f"/review-cases/{case.id}/ai-assistance",
        content=urlencode(_assistance_fields(page.text)),
        headers={**ORIGIN, "content-type": "application/x-www-form-urlencoded"},
        follow_redirects=False,
    )
    cookie = posted.cookies.get("ai_assistance_once")
    assert cookie
    client.cookies.set("ai_assistance_once", cookie)
    crossed = client.get(f"/review-cases/{other.id}")
    assert "SENTINEL-CASE-A-ONLY" not in crossed.text
    assert "Not generated." in crossed.text
    shown = client.get(f"/review-cases/{case.id}")
    assert "SENTINEL-CASE-A-ONLY" in shown.text
    assert len(provider.calls) == 1


def test_post_consultation_review_procedure_stays_operational():
    document = next(
        item
        for item in load_corpus(CORPUS_ROOT)
        if item.document_id == "post-consultation-results-follow-up"
    )
    procedure = next(chunk.text for chunk in document.chunks if chunk.section == "Review Procedure")
    for required in (
        "post consultation result follow-up",
        "human review is already required",
        "confirmed future follow-up",
        "follow-up coordination",
        "without operational action",
        "records the operational outcome",
        "does not interpret an observation value",
    ):
        assert required in procedure
    lowered = procedure.casefold()
    for forbidden in (
        "diagnosis",
        "treatment",
        "medication",
        "severity",
        "urgency",
        "abnormal",
        "normal",
        "risk",
    ):
        assert forbidden not in lowered


def test_http_generation_escapes_html_and_keeps_the_case(tmp_path, caplog):
    repository = _repository(tmp_path)
    case = _create(repository)
    before = _tables(repository.database_path)
    fhir = ScriptedFhir()
    knowledge = FakeKnowledge(chunks=(_chunk(text="<script>alert(1)</script> institutional"),))
    provider = FakeProvider(text=_valid_output(summary="<script>alert(1)</script>", point=POINT))
    caplog.set_level(logging.INFO, logger="ai-service.ai-assistance")
    client = _client(repository, fhir, knowledge, provider)
    page = client.get(f"/review-cases/{case.id}")
    assert "Not generated." in page.text
    assert "Generate AI assistance" in page.text
    assert "SENTINEL-OBS-VALUE" in page.text
    response = _post_assistance(client, case.id, page.text)
    assert response.status_code == 200
    assert response.text.count("&lt;script&gt;alert(1)&lt;/script&gt;") >= 2
    assert "<script>alert(1)</script>" not in response.text
    assert 'class="generated-assistance"' in response.text
    assert 'class="institutional-source"' in response.text
    assert "Institutional source." in response.text
    assert "Procedure title" in response.text
    assert "0.9137" not in response.text
    assert "Close review" in response.text
    assert "<script>alert(1)</script>" not in caplog.text
    assert "SENTINEL-OBS-VALUE" not in caplog.text
    assert "SENTINEL-NAME" not in provider.calls[0]["contents"]
    assert "SENTINEL-OBS-VALUE" not in provider.calls[0]["contents"]
    assert "1234-5" in provider.calls[0]["contents"]
    assert knowledge.requests[0].queryText == "post consultation result follow-up"
    stored = FollowUpReviewCaseService(repository).get(case.id)
    assert stored.status is ReviewCaseStatus.OPEN
    assert stored.version == case.version
    assert stored.reason_codes == case.reason_codes
    assert _tables(repository.database_path) == before
    assert all(call[0] in {"search", "exact"} for call in fhir.calls)
    close = client.post(
        f"/review-cases/{case.id}/close",
        content=urlencode(
            {
                **_close_fields(response.text),
                "outcome": ReviewOutcome.REVIEW_COMPLETED_NO_OPERATIONAL_ACTION.value,
            }
        ),
        headers={**ORIGIN, "content-type": "application/x-www-form-urlencoded"},
        follow_redirects=False,
    )
    assert close.status_code == 303
    assert FollowUpReviewCaseService(repository).get(case.id).status is ReviewCaseStatus.CLOSED


def test_missed_follow_up_http_uses_its_own_query(tmp_path):
    repository = _repository(tmp_path)
    case = _create(repository, MISSED_FOLLOW_UP_REVIEW_V1)
    fhir = ScriptedFhir()
    fhir.appointments = [
        {
            "resourceType": "Appointment",
            "id": "SENTINEL-APPT",
            "status": "noshow",
            "start": "2020-01-01T00:00:00Z",
            "participant": [{"actor": {"reference": f"Patient/{PATIENT}"}, "status": "accepted"}],
        }
    ]
    knowledge = FakeKnowledge(chunks=(_chunk(),))
    provider = FakeProvider(text=_valid_output())
    client = _client(repository, fhir, knowledge, provider)
    page = client.get(f"/review-cases/{case.id}")
    response = _post_assistance(client, case.id, page.text)
    assert response.status_code == 200
    assert "Summary" in response.text
    assert knowledge.requests[0].queryText == "missed follow-up appointment"
    assert "2020-01-01T00:00:00Z" not in provider.calls[0]["contents"]
    assert FollowUpReviewCaseService(repository).get(case.id).version == 1


def test_failures_leave_close_available(tmp_path):
    repository = _repository(tmp_path)
    case = _create(repository)
    fhir = ScriptedFhir()
    knowledge = FakeKnowledge(status="NO_RELEVANT_GUIDANCE")
    provider = FakeProvider(text=_valid_output())
    client = _client(repository, fhir, knowledge, provider)
    page = client.get(f"/review-cases/{case.id}")
    response = _post_assistance(client, case.id, page.text)
    assert response.status_code == 200
    assert "No relevant institutional guidance was retrieved." in response.text
    assert provider.calls == []
    assert "Close review" in response.text
    assert FollowUpReviewCaseService(repository).get(case.id).status is ReviewCaseStatus.OPEN
    unavailable = FakeKnowledge(status="UNAVAILABLE")
    client_unavailable = _client(repository, fhir, unavailable, provider)
    again = _post_assistance(client_unavailable, case.id, page.text)
    assert "Institutional guidance is temporarily unavailable." in again.text
    assert provider.calls == []
    invalid = FakeProvider(text="not-json")
    client_invalid = _client(repository, fhir, FakeKnowledge(chunks=(_chunk(),)), invalid)
    rejected = _post_assistance(client_invalid, case.id, page.text)
    assert "AI assistance could not be shown." in rejected.text
    assert FollowUpReviewCaseService(repository).get(case.id).version == case.version


def test_closed_post_and_missing_secret_do_not_call_providers(tmp_path):
    repository = _repository(tmp_path)
    case = _create(repository)
    repository.close(case.id, expected_version=1, outcome=ReviewOutcome.FOLLOW_UP_COORDINATION_PLANNED)
    fhir = ScriptedFhir()
    knowledge = FakeKnowledge(chunks=(_chunk(),))
    provider = FakeProvider(text=_valid_output())
    client = _client(repository, fhir, knowledge, provider)
    closed_page = client.get(f"/review-cases/{case.id}")
    assert "Generate AI assistance" not in closed_page.text
    assert "Not generated." in closed_page.text
    assert fhir.calls == []
    token, expiry = issue_assistance_token(secret=SIGNING_SECRET, review_case_id=case.id)
    posted = client.post(
        f"/review-cases/{case.id}/ai-assistance",
        content=urlencode({"assistanceExpiry": expiry, "assistanceToken": token}),
        headers={**ORIGIN, "content-type": "application/x-www-form-urlencoded"},
    )
    assert posted.status_code == 409
    assert knowledge.requests == []
    assert provider.calls == []
    assert fhir.calls == []
    blank = _client(repository, fhir, knowledge, provider, settings=_settings(human_review_form_signing_secret=""))
    open_case = _create(repository, case_id="SENTINEL-CASE-2")
    detail = blank.get(f"/review-cases/{open_case.id}")
    assert detail.status_code == 200
    assert "Generate AI assistance" not in detail.text
    refused = blank.post(
        f"/review-cases/{open_case.id}/ai-assistance",
        content=urlencode({"assistanceExpiry": "1", "assistanceToken": "ab"}),
        headers={**ORIGIN, "content-type": "application/x-www-form-urlencoded"},
    )
    assert refused.status_code == 400
    assert "This demo is not configured." in refused.text
    assert knowledge.requests == []
    assert provider.calls == []


def test_origin_and_close_token_do_not_authorize_generation(tmp_path):
    repository = _repository(tmp_path)
    case = _create(repository)
    fhir = ScriptedFhir()
    knowledge = FakeKnowledge(chunks=(_chunk(),))
    provider = FakeProvider(text=_valid_output())
    client = _client(repository, fhir, knowledge, provider)
    page = client.get(f"/review-cases/{case.id}")
    fields = _assistance_fields(page.text)
    calls_after_get = len(fhir.calls)
    wrong_origin = client.post(
        f"/review-cases/{case.id}/ai-assistance",
        content=urlencode(fields),
        headers={"origin": "http://evil.test", "content-type": "application/x-www-form-urlencoded"},
    )
    assert wrong_origin.status_code == 400
    assert MSG_ASSISTANCE_ORIGIN_INVALID in wrong_origin.text
    assert "close form" not in wrong_origin.text.casefold()
    assert len(fhir.calls) == calls_after_get
    malformed = client.post(
        f"/review-cases/{case.id}/ai-assistance",
        content=b"not-a-form",
        headers={**ORIGIN, "content-type": "application/x-www-form-urlencoded"},
    )
    assert malformed.status_code == 400
    assert MSG_ASSISTANCE_REQUEST_INVALID in malformed.text
    assert "close form" not in malformed.text.casefold()
    close_fields = _close_fields(page.text)
    crossed = client.post(
        f"/review-cases/{case.id}/ai-assistance",
        content=urlencode(
            {"assistanceExpiry": close_fields["formExpiry"], "assistanceToken": close_fields["formToken"]}
        ),
        headers={**ORIGIN, "content-type": "application/x-www-form-urlencoded"},
    )
    assert crossed.status_code == 400
    assert MSG_ASSISTANCE_TOKEN_INVALID in crossed.text
    assert "close form" not in crossed.text.casefold()
    assert len(fhir.calls) == calls_after_get
    assert provider.calls == []
    wrong_case = _create(repository, case_id="SENTINEL-CASE-2")
    rebound = client.post(
        f"/review-cases/{wrong_case.id}/ai-assistance",
        content=urlencode(fields),
        headers={**ORIGIN, "content-type": "application/x-www-form-urlencoded"},
    )
    assert rebound.status_code == 400
    assert MSG_ASSISTANCE_TOKEN_INVALID in rebound.text
    assert provider.calls == []
    close_origin = client.post(
        f"/review-cases/{case.id}/close",
        content=urlencode(
            {
                "outcome": ReviewOutcome.FOLLOW_UP_COORDINATION_PLANNED.value,
                "expectedVersion": close_fields["expectedVersion"],
                "formExpiry": close_fields["formExpiry"],
                "formToken": close_fields["formToken"],
            }
        ),
        headers={"origin": "http://evil.test", "content-type": "application/x-www-form-urlencoded"},
        follow_redirects=False,
    )
    assert MSG_ORIGIN_INVALID in close_origin.text
    assert MSG_CLOSE_INVALID not in close_origin.text
    bad_close = client.post(
        f"/review-cases/{case.id}/close",
        content=b"not-a-form",
        headers={**ORIGIN, "content-type": "application/x-www-form-urlencoded"},
        follow_redirects=False,
    )
    assert MSG_CLOSE_INVALID in bad_close.text
    stale_close = client.post(
        f"/review-cases/{case.id}/close",
        content=urlencode(
            {
                "outcome": ReviewOutcome.FOLLOW_UP_COORDINATION_PLANNED.value,
                "expectedVersion": close_fields["expectedVersion"],
                "formExpiry": close_fields["formExpiry"],
                "formToken": fields["assistanceToken"],
            }
        ),
        headers={**ORIGIN, "content-type": "application/x-www-form-urlencoded"},
        follow_redirects=False,
    )
    assert MSG_FORM_INVALID in stale_close.text
    back = client.post(
        f"/review-cases/{case.id}/close",
        content=urlencode(
            {
                "outcome": ReviewOutcome.FOLLOW_UP_COORDINATION_PLANNED.value,
                "expectedVersion": close_fields["expectedVersion"],
                "formExpiry": close_fields["formExpiry"],
                "formToken": fields["assistanceToken"],
            }
        ),
        headers={**ORIGIN, "content-type": "application/x-www-form-urlencoded"},
        follow_redirects=False,
    )
    assert back.status_code == 400
    assert FollowUpReviewCaseService(repository).get(case.id).status is ReviewCaseStatus.OPEN


def test_output_bounds_reject_extra_limitations():
    with pytest.raises(Exception):
        ModelAssistanceOutput.model_validate(
            {
                "summary": {"text": SUMMARY, "citedChunkIds": [CHUNK_A]},
                "reviewPoints": [{"text": "x" * 241, "citedChunkIds": [CHUNK_A]}],
                "limitations": ["one", "two", "three", "four"],
            }
        )


def _standalone_case(
    protocol_id: str,
    *,
    status: ReviewCaseStatus = ReviewCaseStatus.OPEN,
    reason_codes: tuple[str, ...] | None = None,
) -> FollowUpReviewCase:
    reasons = reason_codes or (
        ("missed_follow_up_without_confirmed_replacement",)
        if protocol_id == MISSED_FOLLOW_UP_REVIEW_V1
        else ("post_consultation_result_requires_review",)
    )
    resources = (
        ("Appointment/SENTINEL-APPT",)
        if protocol_id == MISSED_FOLLOW_UP_REVIEW_V1
        else ("Encounter/SENTINEL-ENC", "Observation/SENTINEL-OBS")
    )
    return FollowUpReviewCase(
        id="00000000-0000-4000-8000-0000000000ab",
        review_identity="a" * 64,
        case_id=CASE,
        protocol_id=protocol_id,
        protocol_evaluation_status="matched",
        reason_codes=reasons,
        matched_resources=resources,
        status=status,
        outcome=None,
        version=1,
        created_at="2026-09-30T12:00:00.000000Z",
        updated_at="2026-09-30T12:00:00.000000Z",
        closed_at=None,
    )
