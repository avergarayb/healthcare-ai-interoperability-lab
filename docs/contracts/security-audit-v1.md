# Security audit v1

Operational audit contract for the AI Service. This is not a clinical record and not a tamper-proof log. SQLite stores the rows for one process. An operator who can open the file can change it outside the application. The application API only appends and reads.

## Events

`security-audit-v1` uses a closed allowlist:

| Event | Action | Audited boundary |
|---|---|---|
| `authentication` | `authenticate` | Development login |
| `workflow_start` | `start_workflow` | `POST /internal/workflows` |
| `workflow_resume` | `resume_workflow` | `POST /internal/workflows/{workflowId}/resume` |

For development login, the actor is the configured development principal identifier, or `anonymous` when the credential is rejected. The stored reference is `development-login`.

For a workflow request authenticated with the shared service credential, the actor is the generic `service_client` / `internal-service`. This identifies the credential class, not a person, organization, clinician, or independently verified workload identity. A missing or invalid credential uses the `anonymous` actor. `organization_id` remains absent because these endpoints do not verify one.

A workflow reference, when the identifier is already canonical and trusted, is stored as `workflow/<workflowId>`. It is not a case identifier, patient reference, document, FHIR resource, prompt, tool response, or clinical payload. Start events may include an allowlisted `workflow_type`; rejected untrusted workflow-type text is not retained. The three recognized values remain `post_consultation`, `missed_follow_up`, and `cross_org_lab_result`, although the HTTP start boundary currently exposes only the first two.

Metadata is a strict allowlist containing only `route` and, for workflow events, a recognized `workflow_type`. Tokens, cookies, passwords, model keys, request bodies, clinical content, and arbitrary correlation values are rejected before insert. A canonical caller-supplied UUIDv4 correlation ID is preserved; a missing or malformed value is replaced with a generated UUIDv4.

Workflow reason codes distinguish credential failures (`service_token_missing`, `service_token_invalid`), a disabled workflow capability, an unsupported workflow type, and a Human Review decision mismatch. Missing, malformed, or non-suspended workflows remain request or execution-state errors; they are not recorded as authorization denials. `access_granted` means that the security and applicable resume preconditions permitted execution to begin. It does not claim that the workflow later completed successfully.

## Failure

Development login writes the audit row before it issues a session. Workflow start writes the allowed decision before invoking the graph. Workflow resume validates the persisted workflow and Human Review decision, then writes the allowed decision while holding the workflow gate and immediately before invoking the resume transition. If the applicable row cannot be stored, the response is unavailable and the protected operation does not begin. A normal security rejection is returned only after its denied row is stored.

Audit SQLite and workflow checkpoint SQLite are separate stores. There is intentionally no distributed transaction. A process failure after the audit append but before or during graph invocation can therefore leave an `allowed` access decision without a completed workflow transition. The event remains accurate because it records authorization to begin, not execution success. Stable workflow IDs, the existing checkpoint gate, and suspended-state validation prevent retry from duplicating workflow or clinical transitions; separate retry requests can legitimately produce separate access-decision rows.

Clinical read failures, FHIR failures, provider failures, protocol results, and deterministic clinical decisions are execution outcomes, not security denials, and are not translated into audit reason codes.

## Scope boundary

The demo runner calls orchestration directly and does not cross an authenticated HTTP boundary, so TASK 002 does not invent an actor or audit it as a service request. The Human Review close flow can automatically resume a waiting workflow using the already authenticated browser session. Its complete actor-aware audit belongs with Human Review security work in TASK 003; the shared orchestration resume function therefore keeps an optional pre-transition hook and does not emit a second event by itself. LangGraph nodes are not individually instrumented.

## Later producers

The same fields can record, in later tasks and without a separate audit service:

- FHIR Integration Service access, using `source_service` and `organization_id`.
- A future read-only tool call, using a minimized `resource_reference` and a `correlation_id`.
- Document or data-lake reads, with the source identifier and not the document body.
- Human Review closure and its automatic resume, with minimized identifiers and outcome, not the clinical narrative.

New event types are added to the allowlist. They are not free-text strings.
