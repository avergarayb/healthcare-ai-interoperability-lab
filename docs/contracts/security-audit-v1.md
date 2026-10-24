# Security audit v1

Operational security-audit semantics shared by the two product units. This is not a clinical record, enterprise IAM, or a tamper-proof log. Each service owns its own store; Java never writes the AI Service database. An operator who can open either SQLite file can change it outside the application.

## Events

`security-audit-v1` uses a closed allowlist:

| Event | Action | Audited boundary |
|---|---|---|
| `authentication` | `authenticate` | Development login |
| `workflow_start` | `start_workflow` | `POST /internal/workflows` |
| `workflow_resume` | `resume_workflow` | `POST /internal/workflows/{workflowId}/resume` |
| `human_review_decision` | `close_review_case` | `POST /review-cases/{reviewCaseId}/close` |
| `clinical_federation_access` | `read_federated_context` | Java `POST /api/clinical-federation/v1/context` |

For development login, the actor is the configured development principal identifier, or `anonymous` when the credential is rejected. The stored reference is `development-login`.

For a workflow request authenticated with the shared service credential, the actor is the generic `service_client` / `internal-service`. This identifies the credential class, not a person, organization, clinician, or independently verified workload identity. A missing or invalid credential uses the `anonymous` actor. `organization_id` remains absent because these endpoints do not verify one.

A workflow reference, when the identifier is already canonical and trusted, is stored as `workflow/<workflowId>`. It is not a case identifier, patient reference, document, FHIR resource, prompt, tool response, or clinical payload. Start events may include an allowlisted `workflow_type`; rejected untrusted workflow-type text is not retained. The three recognized values remain `post_consultation`, `missed_follow_up`, and `cross_org_lab_result`, although the HTTP start boundary currently exposes only the first two.

For a Human Review close request, a live development session supplies the verified application principal. The actor is `development_principal` with that configured principal id. A missing, invalid, revoked, or expired session uses `anonymous`; the audit row never stores the cookie, token hash, session id, display name, development secret, or form-signing secret. This remains a synthetic laboratory principal, not verified clinical identity or clinician authorization. There is no organization verified at this boundary.

The Human Review resource reference is the already canonical UUIDv4 as `review-case/<reviewCaseId>`. It excludes the operational `caseId`, patient identity, matched-resource references, protocol reasons, clinical context, narrative, and FHIR content. An allowed new close includes only the allowlisted `human_decision` and submitted `case_version`. `human_decision` is the bounded choice in that authorized request; it does not state that Review committed or that a workflow completed.

Metadata is a strict allowlist containing `route` and, where applicable, a recognized `workflow_type`, `human_decision`, or decimal `case_version`. Each event builder and repository validation admit only the fields defined for that event type. Tokens, cookies, passwords, model keys, request bodies, clinical content, and arbitrary correlation values are rejected before insert. A canonical caller-supplied UUIDv4 correlation ID is preserved; a missing or malformed value is replaced with a generated UUIDv4.

Workflow reason codes distinguish credential failures (`service_token_missing`, `service_token_invalid`), a disabled workflow capability, an unsupported workflow type, and a Human Review decision mismatch. Missing, malformed, or non-suspended workflows remain request or execution-state errors; they are not recorded as authorization denials. `access_granted` means that the security and applicable resume preconditions permitted execution to begin. It does not claim that the workflow later completed successfully.

Human Review close reason codes distinguish a missing session, an invalid/revoked/expired session, a rejected same-origin check, and a rejected form signature. No role, assignment, per-case grant, organization, or production RBAC rule exists to audit. An unknown case, a closed case, an obsolete version, an invalid decision, malformed input, Review persistence failure, checkpoint failure, or workflow failure is not converted into an authorization denial. A repeated same-outcome close is not a new accepted decision and emits no second `human_review_decision` event.

For Java Clinical Federation, a token match supplies the verified technical actor `federation_participant` and its source-registry key. `organization_id` is stored only from that registry, after the request organization matches it; body fields cannot establish the actor or organization. Authentication failures use `anonymous` and no organization. The resource reference is the constant `clinical-federation/context`, never a patient, order, FHIR, HIS, or LIS identifier.

Java reason codes distinguish missing or invalid participant tokens, an unconfigured participant-token map, a caller that is not registered, an organization mismatch, a caller-system mismatch, and a source outside the caller grant. The existing HTTP error codes remain `organization_mismatch`, `identity_system_mismatch`, and `source_not_authorized`; audit reason codes describe the security decision without copying request values. Malformed fields and source identifiers are validation failures, while identity resolution, connector, timeout, correlation, and clinical-source failures are operational outcomes. They are not recorded as authorization denials.

The Java event metadata allowlist contains only `route=/api/clinical-federation/v1/context`. Its actor, action, resource, outcome, reason, metadata, and contract combinations are validated before insert. It contains no token, body, source list, identifier system/value, resource type list, FHIR payload, patient data, laboratory value, or connector response.

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

Clinical Federation appends one `allowed` decision after authentication, organization, caller-system, source-grant, and request validation succeed, and before any HIS/LIS connector call. `allowed` means that connector execution may begin; it does not mean that identity resolved, a source was available, the response was complete, or the query succeeded clinically. Connector and query outcomes do not append another access event. Authentication and authorization denials append exactly one denied event before returning. If the mandatory append fails, Java returns HTTP 503 `audit_unavailable` and does not invoke a connector. For an authentication rejection this replaces the normal empty 401 response with an empty 503 response because the denial could not be recorded. The internal error log retains the persistence exception for diagnosis but adds no token, request field, organization, source list, or clinical content.

Java stores these rows in its own SQLite file configured by `federation.security-audit.store-path`, using verified WAL mode, a bounded per-connection busy timeout, one parameterized insert transaction, schema version 1, and no application update/delete API. The default is `${java.io.tmpdir}/healthcare-lab-federation/security-audit.sqlite`. Missing parent directories are created. Failure to initialize or validate that store prevents startup; a runtime append failure is handled fail-closed as described above. This is durable across an ordinary process restart on that host, but an operating-system temporary-file cleanup can remove it. The default supports one local laboratory instance; simultaneous instances must configure distinct paths. It is not permanent retention, replicated, encrypted by the application, immutable, or a production SIEM. A successful access-decision append can remain when a later connector or response operation fails, which is semantically correct because the event records permission to begin.

The Java REST contract still accepts its existing bounded correlation syntax. Security audit and operational logs reuse only the canonical value emitted by the Python federation client, `FED-` plus 16 uppercase hexadecimal characters. Any other accepted REST value is returned for compatibility but replaced with a generated canonical value in audit and logs, so arbitrary client text is not trusted as audit data. Python currently creates that id for the federation POST itself. It can correlate the Python client call with the Java event, logs, and successful response, but it is not propagated from the surrounding workflow or an earlier AI Service audit event and therefore is not complete end-to-end workflow traceability.

## Scope boundary

The demo runner calls orchestration directly and does not cross an authenticated HTTP boundary, so TASK 002 does not invent an actor or audit it as a service request. Human Review automatic resume runs only after the close transaction commits. `human_review_decision` is sufficient for that browser request: the automatic path does not fabricate a `service_client`, does not emit `workflow_resume`, and does not claim successful workflow execution. The existing checkpoint gate accepts at most the workflow still in `waiting_human`; a repeated close cannot execute a completed workflow again. LangGraph nodes are not individually instrumented.

The service-token endpoint `POST /internal/follow-up-review-cases/{reviewCaseId}/close` is not a Human Review UI operation. It has no resolved human session, creates no human attribution, and does not emit `human_review_decision`. Adding audit coverage for that separate internal-service boundary requires its own explicit event contract.

## Later producers

The same fields can record, in later tasks and without a separate audit service:

- FHIR Integration Service access, using `source_service` and `organization_id`.
- A future read-only tool call, using a minimized `resource_reference` and a `correlation_id`.
- Document or data-lake reads, with the source identifier and not the document body.

New event types are added to the allowlist. They are not free-text strings.
