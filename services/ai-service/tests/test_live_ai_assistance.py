"""Opt-in live AI assistance check.

Run only when RUN_LIVE_AI_ASSISTANCE_TESTS=true and GEMINI_API_KEY is already
in the environment. This file does not load a dotenv file and does not print
the key. It is not part of the deterministic suite.
"""

from __future__ import annotations

import os
from dataclasses import replace
from datetime import datetime, timedelta, timezone

import pytest

from app.ai_assisted_review import generate_ai_assistance
from app.clinical_review_context import ClinicalReviewContextResponse
from app.config import Settings
from app.followup_review import FollowUpReviewCaseService
from app.followup_review_sqlite import SQLiteFollowUpReviewCaseRepository
from app.gemini_provider import GeminiProvider
from app.institutional_knowledge import CORPUS_ROOT, open_institutional_knowledge
from app.post_consultation_review import (
    POST_CONSULTATION_RESULT_REVIEW_V1,
    ProtocolEvaluationStatus,
    ProtocolReviewResult,
)

pytestmark = pytest.mark.skipif(
    os.getenv("RUN_LIVE_AI_ASSISTANCE_TESTS", "").strip().lower() != "true",
    reason="set RUN_LIVE_AI_ASSISTANCE_TESTS=true to validate live assistance",
)


class _RecordingKnowledge:
    def __init__(self, inner) -> None:
        self.inner = inner
        self.last = None

    def retrieve(self, request):
        self.last = self.inner.retrieve(request)
        return self.last


class _RecordingProvider:
    def __init__(self, inner) -> None:
        self.inner = inner
        self.contents = ""

    def generate_structured(self, **kwargs):
        self.contents = kwargs["contents"]
        return self.inner.generate_structured(**kwargs)


def test_live_ai_assistance_validates_synthetic_generation(tmp_path):
    settings = Settings.from_env()
    if not settings.gemini_api_key or not settings.gemini_model:
        pytest.fail("GEMINI_API_KEY and GEMINI_MODEL must already be configured")
    configured = replace(
        settings,
        ai_review_db_path=str(tmp_path / "review.sqlite3"),
        institutional_knowledge_db_path=str(tmp_path / "knowledge.sqlite3"),
    )
    repository = SQLiteFollowUpReviewCaseRepository(configured.ai_review_db_path)
    repository.initialize()
    case = FollowUpReviewCaseService(repository).ensure_for_protocol(
        "SYN-AI-ASSIST-001",
        ProtocolReviewResult(
            id=POST_CONSULTATION_RESULT_REVIEW_V1,
            evaluation_status=ProtocolEvaluationStatus.MATCHED,
            reason_codes=("post_consultation_result_requires_review",),
            matched_resources=("Encounter/synthetic-enc", "Observation/synthetic-obs"),
            human_review_status="required",
            human_review_reason="deterministic_post_consultation_protocol_match",
            action_status="proposed",
            action_type="review_follow_up_case",
        ),
    )
    assert case is not None
    context = ClinicalReviewContextResponse.model_validate(
        {
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
                "retrievedAt": "2026-10-07T12:00:00.000000Z",
                "source": "fhir_current",
                "reasonCodes": ["current_context_complete"],
            },
            "currentContext": {
                "patient": {"resolution": "resolved"},
                "encounter": {
                    "reference": "Encounter/synthetic-enc",
                    "availability": "available",
                    "status": "finished",
                },
                "observation": {
                    "reference": "Observation/synthetic-obs",
                    "availability": "available",
                    "status": "final",
                    "encounterReference": "Encounter/synthetic-enc",
                    "code": {"status": "available", "coding": [{"code": "1234-5", "display": "Synthetic"}]},
                    "content": {"status": "not_projected"},
                },
                "appointments": {"collectionStatus": "complete", "classifications": ["NONE"], "items": []},
            },
        }
    )
    knowledge = _RecordingKnowledge(
        open_institutional_knowledge(configured, corpus_root=CORPUS_ROOT)
    )
    provider = _RecordingProvider(
        GeminiProvider(api_key=configured.gemini_api_key, model=configured.gemini_model)
    )
    before = datetime.now(timezone.utc)
    outcome = generate_ai_assistance(
        case=case,
        context_reader=lambda: context,
        knowledge=knowledge,
        provider=provider,
        correlation_id="live-ai-assistance",
    )
    assert datetime.now(timezone.utc) - before < timedelta(minutes=2)
    assert outcome.result.status == "available"
    assert outcome.result.assistance_type == "explanatory"
    assert outcome.result.human_review_required is True
    assert outcome.result.summary is not None
    assert outcome.result.review_points
    retrieved = {chunk.chunk_id for chunk in knowledge.last.chunks}
    cited = {source.chunk_id for source in outcome.result.sources}
    assert cited and cited <= retrieved
    for claim in (outcome.result.summary, *outcome.result.review_points):
        assert claim.citations
        assert {item.chunk_id for item in claim.citations} <= retrieved
    for hidden in (case.id, "synthetic-enc", "synthetic-obs", "SYN-AI-ASSIST-001", "Patient/"):
        assert hidden not in provider.contents
    stored = FollowUpReviewCaseService(repository).get(case.id)
    assert stored.status.value == "open"
    assert stored.version == case.version
