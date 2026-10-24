# Security audit v1

Operational audit contract for the AI Service. This is not a clinical record and not a tamper-proof log. SQLite stores the rows for one process. An operator who can open the file can change it outside the application. The application API only appends and reads.

## Events

`security-audit-v1` uses a closed allowlist:

| Event | Action | Audited boundary |
|---|---|---|
| `authentication` | `authenticate` | Development login |
| `workflow_start` | `start_workflow` | `POST /internal/workflows` |
| `workflow_resume` | `resume_workflow` | `POST /internal/workflows/{workflowId}/resume` |
| `human_review_decision` | `close_review_case` | `POST /review-cases/{reviewCaseId}/close` |

For development login, the actor is the configured development principal identifier, or `anonymous` when the credential is rejected. The stored reference is `development-login`.

For a workflow request authenticated with the shared service credential, the actor is the generic `service_client` / `internal-service`. This identifies the credential class, not a person, organization, clinician, or independently verified workload identity. A missing or invalid credential uses the `anonymous` actor. `organization_id` remains absent because these endpoints do not verify one.

A workflow reference, when the identifier is already canonical and trusted, is stored as `workflow/<workflowId>`. It is not a case identifier, patient reference, document, FHIR resource, prompt, tool response, or clinical payload. Start events may include an allowlisted `workflow_type`; rejected untrusted workflow-type text is not retained. The three recognized values remain `post_consultation`, `missed_follow_up`, and `cross_org_lab_result`, although the HTTP start boundary currently exposes only the first two.

For a Human Review close request, a live development session supplies the verified application principal. The actor is `development_principal` with that configured principal id. A missing, invalid, revoked, or expired session uses `anonymous`; the audit row never stores the cookie, token hash, session id, display name, development secret, or form-signing secret. This remains a synthetic laboratory principal, not verified clinical identity or clinician authorization. There is no organization verified at this boundary.

The Human Review resource reference is the already canonical UUIDv4 as `review-case/<reviewCaseId>`. It excludes the operational `caseId`, patient identity, matched-resource references, protocol reasons, clinical context, narrative, and FHIR content. An allowed new close includes only the allowlisted `human_decision` and submitted `case_version`. `human_decision` is the bounded choice in that authorized request; it does not state that Review committed or that a workflow completed.

Metadata is a strict allowlist containing `route` and, where applicable, a recognized `workflow_type`, `human_decision`, or decimal `case_version`. Each event builder and repository validation admit only the fields defined for that event type. Tokens, cookies, passwords, model keys, request bodies, clinical content, and arbitrary correlation values are rejected before insert. A canonical caller-supplied UUIDv4 correlation ID is preserved; a missing or malformed value is replaced with a generated UUIDv4.

Workflow reason codes distinguish credential failures (`service_token_missing`, `service_token_invalid`), a disabled workflow capability, an unsupported workflow type, and a Human Review decision mismatch. Missing, malformed, or non-suspended workflows remain request or execution-state errors; they are not recorded as authorization denials. `access_granted` means that the security and applicable resume preconditions permitted execution to begin. It does not claim that the workflow later completed successfully.

Human Review close reason codes distinguish a missing session, an invalid/revoked/expired session, a rejected same-origin check, and a rejected form signature. No role, assignment, per-case grant, organization, or production RBAC rule exists to audit. An unknown case, a closed case, an obsolete version, an invalid decision, malformed input, Review persistence failure, checkpoint failure, or workflow failure is not converted into an authorization denial. A repeated same-outcome close is not a new accepted decision and emits no second `human_review_decision` event.

The three relevant results remain separate:

- `outcome` is the security result (`allowed` or `denied`);
- `human_decision` is the bounded choice submitted for a permitted new close;
- workflow state or execution result is not a field of `human_review_decision`.

## Failure

Development login writes the audit row before it issues a session. Workflow start writes the allowed decision before invoking the graph. Workflow resume validates the persisted workflow and Human Review decision, then writes the allowed decision while holding the workflow gate and immediately before invoking the resume transition. A Human Review close validates the live session, canonical case id, same origin, exact form, bounded decision, expected version, signature, case existence, open state, and current version before appending the allowed audit event. The append runs while the Review repository holds its existing `BEGIN IMMEDIATE` transaction and before it updates the case. If the applicable row cannot be stored, the response is unavailable and the protected operation does not begin. A normal security rejection is returned only after its denied row is stored.

After a successful Human Review audit append, the existing Review transaction updates the case to version 2 and inserts the operational `closed` event plus the development attribution. Those three Review writes commit or roll back together. The audit database is separate and does not share that transaction. No distributed transaction or compensating delete is introduced.

Audit SQLite, Review SQLite, and workflow checkpoint SQLite are separate stores. There is intentionally no distributed transaction. A Review database failure or process termination after the audit append but before the Review commit can therefore leave an `allowed` access decision without a persisted human closure. A process failure after a workflow audit append can likewise leave an allowed decision without a completed workflow transition. The events remain accurate because they record permission to begin, not persistence or execution success. A later Review retry may write a second allowed access-decision row; only the successful Review transaction can append the single operational close and attribution. Stable workflow IDs, the existing checkpoint gate, and suspended-state validation prevent retry from duplicating workflow or clinical transitions.

Lock order for a new Human Review close is the existing Review write lock followed by the short audit append. No current path holds the audit transaction and then waits for the Review database. The supported topology remains one AI Service process and one writer boundary; this is not a multi-process deadlock or distributed-atomicity guarantee.

Clinical read failures, FHIR failures, provider failures, protocol results, and deterministic clinical decisions are execution outcomes, not security denials, and are not translated into audit reason codes.

## Scope boundary

The demo runner calls orchestration directly and does not cross an authenticated HTTP boundary, so TASK 002 does not invent an actor or audit it as a service request. Human Review automatic resume runs only after the close transaction commits. `human_review_decision` is sufficient for that browser request: the automatic path does not fabricate a `service_client`, does not emit `workflow_resume`, and does not claim successful workflow execution. The existing checkpoint gate accepts at most the workflow still in `waiting_human`; a repeated close cannot execute a completed workflow again. LangGraph nodes are not individually instrumented.

The service-token endpoint `POST /internal/follow-up-review-cases/{reviewCaseId}/close` is not a Human Review UI operation. It has no resolved human session, creates no human attribution, and does not emit `human_review_decision`. Adding audit coverage for that separate internal-service boundary requires its own explicit event contract.

## Later producers

The same fields can record, in later tasks and without a separate audit service:

- FHIR Integration Service access, using `source_service` and `organization_id`.
- A future read-only tool call, using a minimized `resource_reference` and a `correlation_id`.
- Document or data-lake reads, with the source identifier and not the document body.

New event types are added to the allowlist. They are not free-text strings.
