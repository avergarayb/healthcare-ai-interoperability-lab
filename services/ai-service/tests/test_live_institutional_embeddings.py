"""Opt-in compatibility check for google-genai embeddings.

Run only when RUN_LIVE_EMBEDDING_TESTS=true and GEMINI_API_KEY is already
in the environment. This file does not load a dotenv file and does not print
the key. It is not part of the deterministic suite.
"""

from __future__ import annotations

import os

import pytest

from app.institutional_embeddings import GeminiEmbeddingProvider
from app.institutional_knowledge import (
    CORPUS_ROOT,
    MISSED_FOLLOW_UP_REVIEW_V1,
    POST_CONSULTATION_RESULT_REVIEW_V1,
    KnowledgeRetrieveRequest,
    open_institutional_knowledge,
)
from app.config import Settings

pytestmark = pytest.mark.skipif(
    os.getenv("RUN_LIVE_EMBEDDING_TESTS", "").strip().lower() != "true",
    reason="set RUN_LIVE_EMBEDDING_TESTS=true to validate the embedding provider",
)


def test_live_embedding_model_and_golden_queries(tmp_path):
    api_key = os.getenv("GEMINI_API_KEY", "").strip()
    if not api_key:
        pytest.skip("GEMINI_API_KEY is not set")
    model = os.getenv("INSTITUTIONAL_KNOWLEDGE_EMBEDDING_MODEL", "gemini-embedding-001").strip()
    provider = GeminiEmbeddingProvider(api_key=api_key, model=model)
    probe = provider.embed_texts(["institutional retrieval probe"])
    assert provider.model_id == model
    assert len(probe) == 1
    assert len(probe[0]) >= 8
    print("LIVE_EMBEDDING_DIMENSION", len(probe[0]))
    assert all(value == value and abs(value) != float("inf") for value in probe[0])
    configured = Settings(
        model_boundary_base_url="http://model-boundary.test",
        model_boundary_path="/api/model-boundary/v1",
        model_boundary_timeout_seconds=5,
        model_boundary_service_token="unused",
        host="127.0.0.1",
        port=8090,
        gemini_api_key=api_key,
        institutional_knowledge_db_path=str(tmp_path / "institutional-knowledge.sqlite3"),
        institutional_knowledge_embedding_model=model,
        institutional_knowledge_min_score=0.68,
    )
    index = open_institutional_knowledge(configured, embedder=provider, corpus_root=CORPUS_ROOT)
    queries = (
        ("post-consultation", POST_CONSULTATION_RESULT_REVIEW_V1, "post consultation result follow-up", {"post-consultation-results-follow-up", "care-coordination-procedures"}),
        ("missed-follow-up", MISSED_FOLLOW_UP_REVIEW_V1, "missed follow-up appointment", {"missed-follow-up-management", "care-coordination-procedures"}),
        ("care-coordination", POST_CONSULTATION_RESULT_REVIEW_V1, "care coordination", {"post-consultation-results-follow-up", "care-coordination-procedures"}),
    )
    for name, protocol_id, query, allowed in queries:
        result = index.retrieve(
            KnowledgeRetrieveRequest.model_validate(
                {"protocolId": protocol_id, "queryText": query, "topK": 3}
            )
        )
        print(
            "LIVE_EMBEDDING",
            model,
            name,
            result.status,
            [(chunk.document_id, chunk.section, round(chunk.score, 4)) for chunk in result.chunks],
        )
        assert result.status == "FOUND"
        assert result.chunks[0].document_id in allowed
    unrelated = index.retrieve(
        KnowledgeRetrieveRequest.model_validate(
            {
                "protocolId": POST_CONSULTATION_RESULT_REVIEW_V1,
                "queryText": "warehouse pallet inventory cycle count",
                "topK": 3,
            }
        )
    )
    print(
        "LIVE_EMBEDDING",
        model,
        "unrelated",
        unrelated.status,
        [(chunk.document_id, chunk.section, round(chunk.score, 4)) for chunk in unrelated.chunks],
    )
    print("LIVE_EMBEDDING_THRESHOLD", configured.institutional_knowledge_min_score)
    assert unrelated.status == "NO_RELEVANT_GUIDANCE"
    assert unrelated.chunks == ()
