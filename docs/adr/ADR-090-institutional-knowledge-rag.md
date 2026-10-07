# ADR-090 — Institutional knowledge retrieval

## Status

Accepted

## Date

2026-10-06

## Context

Follow-up review already separates FHIR facts, deterministic protocol evaluation and human operational authority. A later assisted-review step needs a bounded way to retrieve institutional procedure text. That retrieval must not become a second protocol, a patient index or a generated explanation.

## Decision

`INSTITUTIONAL_KNOWLEDGE_RETRIEVAL_V1` retrieves repository-controlled synthetic institutional procedures. It is not clinical decision support and it is not production-ready.

The corpus is the fixed directory `services/ai-service/knowledge/institutional/`. V1 contains three English Markdown procedures. Each file starts with a closed JSON metadata block parsed by the Python standard library. `sourceType` is `synthetic_institutional_procedure`, `synthetic` is true, `language` is `en`, and `status` is `active` or `superseded`. At most one active version exists per `documentId`. Active status is explicit. Version strings are not sorted to infer the current document.

Chunking is deterministic and section-aware. A `#` heading is the title. A `##` heading starts a section. A section within 2000 characters is one chunk. A longer section splits on paragraph boundaries without overlap. The chunk id is a SHA-256 over canonical JSON of `documentId`, `version`, section, ordinal and the chunk content hash. Vectors are not part of the chunk id and are not returned.

Embeddings use a dedicated adapter over pinned `google-genai==2.24.0`, method `client.models.embed_content`. The configured model is `INSTITUTIONAL_KNOWLEDGE_EMBEDDING_MODEL`, default `gemini-embedding-001`. There is no fallback model and no call to text generation. Both indexing a missing chunk and embedding `queryText` require the provider. If query embedding fails, retrieval is `UNAVAILABLE`. There is no lexical fallback presented as semantic success.

Vectors are cached in a separate SQLite file, `INSTITUTIONAL_KNOWLEDGE_DB_PATH`, default `./data/institutional-knowledge.sqlite3`. That file is not `AI_REVIEW_DB_PATH` and it is not HAPI PostgreSQL. An unchanged chunk content hash and embedding model is not embedded again. A different model does not mix with old vectors. Rebuild marks the index unavailable before embedding, embeds outside any SQLite transaction, then replaces documents, chunks and vectors in one transaction. If corpus validation or embedding fails, the index stays unavailable until a later rebuild succeeds. A document version removed from the authorized corpus is not left retrievable after a successful rebuild.

Retrieval filters by the requested protocol before cosine ranking. Post-consultation retrieval can see the post-consultation procedure and care coordination. Missed-follow-up retrieval can see the missed-follow-up procedure and care coordination. `topK` is at most 3. `INSTITUTIONAL_KNOWLEDGE_MIN_SCORE` defaults to 0.68. That value is the initial Demo Product V1 retrieval-quality threshold selected from the first live embedding validation. It is provisional and must be reevaluated when the institutional corpus grows, document versions change, the embedding model changes, or the retrieval evaluation set grows. It is not validated, calibrated, production-ready, or clinically meaningful.

`POST /internal/knowledge/retrieve` uses the existing `X-Service-Token`. `FOUND` and `NO_RELEVANT_GUIDANCE` are HTTP 200. `UNAVAILABLE` is HTTP 503. Technical failure is not an empty successful retrieval. The Human Review Client does not expose this route.

The parser does not prove that arbitrary text contains no personal data. The trust boundary is the reviewed repository corpus: fixed directory, no upload, no caller-supplied path, required `synthetic=true`, closed `sourceType`, and known metadata. Simple rejection of application identifiers in the request is not a PHI detector.

Citation fields come only from indexed chunk metadata. `contentRole` is `institutional_document_data`. The score is retrieval similarity. This increment does not write citation prose. Retrieved Markdown is data. A future assisted review must treat it as untrusted institutional data, not as instructions, and must not invent `title`, `version`, `section` or `chunkId`.

## Consequences

FHIR facts, deterministic protocol output, review-case identity and review-case closure stay unchanged when retrieval fails or succeeds. No patient, FHIR or review-case body is embedded. No new dependency, database server, port or secret is added. `GEMINI_API_KEY` is reused only for embeddings. The index is single-instance SQLite and is not a vector database.
