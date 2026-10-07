# INSTITUTIONAL_KNOWLEDGE_RETRIEVAL_V1

## Authority

This contract retrieves synthetic institutional procedure text. It does not supply patient facts, protocol decisions or generated explanations.

| Concern | Authority |
|---|---|
| Patient and case facts | FHIR, through the existing authorized read paths |
| Operational evaluation | `POST_CONSULTATION_RESULT_REVIEW_V1` and `MISSED_FOLLOW_UP_REVIEW_V1` |
| Institutional guidance | This retrieval contract |

Retrieval must not change `evaluationStatus`, `reasonCodes`, `matchedResources`, review-case identity, review-case creation, review-case closure or FHIR acquisition. A retrieval failure must not stop those workflows.

## Corpus

The only corpus root is `services/ai-service/knowledge/institutional/`. Callers cannot supply a path. V1 ships three English Markdown documents:

- Post-Consultation Results Follow-up Protocol 1.0, active, `POST_CONSULTATION_RESULT_REVIEW_V1`
- Missed Follow-up Management Protocol 1.0, active, `MISSED_FOLLOW_UP_REVIEW_V1`
- Care Coordination Procedures 1.0, active, both protocols

Care coordination includes Operational Trigger and states that it has no separate detection trigger.

Each document states: "Synthetic demonstration material. Not validated clinical guidance." The procedures describe operational handling. They do not execute or redefine the deterministic protocols.

There is no upload endpoint, document-management API, scheduler or watcher. The parser accepts only the closed metadata object and the required section structure. It does not claim that arbitrary text is free of personal data, and it does not implement NER, a PHI classifier, a FHIR parser or a clinical-data detector.

## Versions and chunks

Multiple versions of one `documentId` may exist. At most one version is `active`. Default retrieval uses active versions only. An optional `version` pin may return that version, including a superseded one. Status is explicit.

Two hashes are distinct.

The document body hash is SHA-256 of the normalized complete Markdown body after the metadata fence: UTF-8, LF, trailing spaces stripped per line, and one trailing newline. It is the document content-integrity value stored with the document. It is not the `contentHash` field of a retrieval result.

The chunk content hash is SHA-256 of the normalized text of that individual chunk. Chunk ids use the repository's canonical JSON hashing over `documentId`, `version`, section, ordinal and this chunk content hash. Maximum chunk length is 2000 characters. There is no overlap and no token-window chunking.

## Embeddings and index

The embedding adapter calls `client.models.embed_content` on `google-genai==2.24.0`. The model is `INSTITUTIONAL_KNOWLEDGE_EMBEDDING_MODEL` (`gemini-embedding-001` by default). Generation is not used. No other embedding model is substituted after a failure.

Indexing embeds chunk text and stores the vector with the model id. A semantic query also embeds `queryText` and compares it with cached vectors by cosine similarity in Python. Provider availability is required for both a new chunk and a query. Query embedding failure is `UNAVAILABLE`.

The SQLite index stores documents, chunks and vectors. `INSTITUTIONAL_KNOWLEDGE_DB_PATH` defaults to `./data/institutional-knowledge.sqlite3`. Rebuild does not keep a write transaction open during the embedding call. Validation or embedding failure sets the index not-ready. Previously stored rows are then not served. A successful rebuild replaces the indexed set, which removes versions that disappeared from the corpus. Vectors from a different embedding model are not mixed into the result.

## Request and response

`POST /internal/knowledge/retrieve` requires `X-Service-Token` equal to `MODEL_BOUNDARY_SERVICE_TOKEN`. Missing or blank authentication is HTTP 401 with an empty body, before request validation.

The request allows `protocolId`, `queryText` (1 to 400 characters), optional operational `reasonCodes`, optional `version`, and optional `topK` from 1 to 3. It rejects extra fields, including case, patient, FHIR and filesystem identifiers. `reasonCodes` are checked against the closed operational set and do not change ranking in this version. `queryText` is not logged.

| Retrieval status | HTTP | Meaning |
|---|---|---|
| `FOUND` | 200 | At least one protocol-eligible chunk is at or above `INSTITUTIONAL_KNOWLEDGE_MIN_SCORE` |
| `NO_RELEVANT_GUIDANCE` | 200 | The index and query embedding succeeded, and no eligible chunk meets the threshold |
| `UNAVAILABLE` | 503 | The index is not ready, integrity failed, the model or dimension does not match, or the embedding provider did not return a query vector |

Invalid requests use the existing bounded HTTP 422 validation behavior. Responses do not include exception traces or vectors.

Each returned chunk carries indexed provenance: `documentId`, `title`, `version`, `documentStatus`, `section`, `ordinal`, `chunkId`, `contentHash`, `language`, `synthetic`, `score`, `text` and `contentRole=institutional_document_data`. In that response, `contentHash` is the chunk content hash, not the document body hash. `score` is cosine similarity, not clinical confidence, clinical probability or protocol confidence. Markdown is returned as JSON text, not rendered as HTML.

`INSTITUTIONAL_KNOWLEDGE_MIN_SCORE` defaults to 0.68. That is the initial demonstration threshold selected from the first live embedding validation. It remains provisional. Reevaluate it when the institutional corpus grows, document versions change, the embedding model changes, or the retrieval evaluation set grows. It is not validated, calibrated, production-ready, or clinically meaningful. Passing deterministic tests does not make it so.

## Non-goals

This contract does not connect retrieval to Clinical Review Context, does not add a Human Review Client control, and does not generate an answer or a citation sentence. A future assisted review may cite a chunk only when that `chunkId` was in the retrieval result supplied to the model, and it must treat the text as untrusted institutional data.
