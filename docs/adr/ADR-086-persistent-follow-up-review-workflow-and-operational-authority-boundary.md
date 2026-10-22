# ADR-086 — Persistent Follow-up Review Workflow and Operational Authority Boundary

## Status

Accepted

## Date

2026-09-30

## Context

`POST_CONSULTATION_RESULT_REVIEW_V1` deterministically projects `humanReview.status=required` and `action.type=review_follow_up_case` when its bounded FHIR rule matches. Those fields remain response-level protocol facts. They did not previously create a durable work item that an operational caller could discover and close.

Healthcare AI had no product database, ORM, migration system, persistent LangGraph checkpoint, assignment system, or production human identity. The PostgreSQL instance under `infra/docker` belongs only to the local HAPI support stack and is not a product business database.

## Decision

Healthcare AI implements `FOLLOW_UP_REVIEW_WORKFLOW_V1`, a separate operational workflow. A deterministic `MATCHED` result synchronously creates or reuses a durable `FollowUpReviewCase` before the narrative Gemini/LangGraph subflow runs.

The deterministic protocol remains pure and authoritative for match semantics. The review workflow is authoritative only for operational state, outcome and transition history. FHIR remains authoritative for clinical facts. Gemini has no authority over review-case creation, identity, state, outcome or closure.

## Persistence and deployment boundary

V1 uses a dedicated product-owned file-backed SQLite database through Python standard-library `sqlite3`. It does not reuse HAPI PostgreSQL. `AI_REVIEW_DB_PATH` selects the file; the default is `./data/follow-up-review.sqlite3` relative to the service working directory.

The supported V1 deployment boundary is one `ai-service` instance using one writer store. SQLite connections are created per operation, use foreign-key enforcement, WAL mode and a bounded busy timeout. Transactions never span FHIR, Gemini or LangGraph execution.

The application depends on a `FollowUpReviewCaseRepository` port rather than SQLite directly. A future separately approved increment may replace the adapter with a product PostgreSQL repository.

FastAPI lifespan initialization validates configuration, applies the supported versioned migration and rejects corrupt, invalid or future schema versions before readiness.

## Identity and idempotency

The identity schema is `FOLLOW_UP_REVIEW_EVENT_IDENTITY_V1`. SHA-256 is applied to canonical JSON containing exactly:

- exact `caseId`;
- exact versioned `protocolId`;
- sorted, unique, validated `matchedResources`.

It excludes run ids, timestamps, reason codes, HTTP executions and all Gemini output. A unique database constraint makes concurrent identical creation converge on one review case. The same identity reuses an existing open or closed case. A different matched-resource set or protocol id creates a different case.

FHIR `meta.versionId` is deliberately absent. Updating the contents of the same logical resource IDs does not create another V1 review event.

## Lifecycle and outcomes

The lifecycle is exactly:

```text
open -> closed
```

Creation produces version 1. Closure is terminal and increments the version once. The allowed outcomes are exactly:

- `follow_up_coordination_planned`;
- `review_completed_no_operational_action`.

These are operational records. They do not express normality, urgency, severity, diagnosis, treatment, clinical necessity or a clinical recommendation.

Closure uses an expected version and a conditional update. Retrying the same outcome on a closed case returns the existing result without another event. A different outcome or stale open version conflicts.

## Operational transition history

The store appends `created` and `closed` events. State update and event insertion occur in the same transaction. This is durable operational provenance, not a security, clinical or verified-human audit.

## Authentication limitation

The internal APIs use the existing `X-Service-Token`. It authenticates an internal service caller only. V1 has no verified human identity, assignment, claim, owner, `X-Actor-Id` or RBAC. No fictional reviewer is stored.

## Data minimization

The store contains operational metadata that may itself be sensitive: case id, reason codes, matched resource references, timestamps and outcome. It does not store Patient ids as separate domain fields, raw FHIR resources or Bundles, prompts, completions, narrative answers, tool evidence, free-text notes or human identifiers.

The immutable creation provenance is not rewritten when source FHIR data changes. Detail APIs do not retrieve live FHIR. Standard SQLite does not provide encrypted-at-rest storage; appropriate protected storage is a deployment requirement before using real clinical data. No retention duration, purge job or delete API is introduced.

## Failure semantics

If a deterministic match cannot be durably created or reused, the follow-up endpoint returns HTTP 503, does not invoke Gemini and does not claim a review case exists. Retry is safe through deterministic identity.

Once persistence commits, a later Gemini failure cannot roll it back. The current request may retain its model/workflow failure response while the open case remains discoverable. SQLite and SQL details, configured paths and provenance hash inputs are not exposed through HTTP errors.

## Consequences

Cases matched by the deterministic protocol become durable, bounded internal work items that survive restart and can be listed, inspected at the provenance level and closed. The new workflow does not alter `humanReview`, `action`, `clinicalAssessment` or protocol semantics.

SQLite keeps the increment small but does not support multi-replica operation. Backup, file permissions, durable volume management, retention and encryption at rest remain deployment responsibilities.

## Non-goals

This decision does not introduce clinical interpretation, live clinical-detail projection, FHIR writes, messaging, assignment, reviewer identity, reopen, escalation, deletion, retention automation, frontend, multi-tenancy, production IAM/RBAC, a broker, Redis, another service, PostgreSQL, SQLAlchemy, Alembic, SQLCipher, application-level encryption or a new model/agent.

## Related decisions and contracts

- [ADR-085](ADR-085-python-follow-up-fhir-and-model-authority-boundary.md)
- [POST_CONSULTATION_RESULT_REVIEW_V1](../contracts/post-consultation-result-review-v1.md)
- [FOLLOW_UP_REVIEW_WORKFLOW_V1](../contracts/follow-up-review-workflow-v1.md)
- [ADR-087](ADR-087-case-bound-current-clinical-review-context.md) supersedes only this decision's non-goal that excluded live clinical-detail projection.
