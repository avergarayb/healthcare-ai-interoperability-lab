# POST_CONSULTATION_RESULT_REVIEW_V1

## 1. Purpose

`POST_CONSULTATION_RESULT_REVIEW_V1` is the authoritative internal, versioned product contract for **Clinical Follow-up Review**.

Its purpose is to identify a result made available after a completed consultation when there is no confirmed future follow-up, and to present that case for human review.

It is used by `POST /internal/agent/follow-up`. It is not currently a public or external API contract.

## 2. Scope

This contract defines:

- authorized case resolution;
- mandatory FHIR acquisition;
- collection completeness and bounded pagination;
- resource and reference integrity;
- deterministic protocol evaluation;
- HTTP response projection;
- separation between protocol authority and the legacy narrative model flow.

The protocol evaluates operational and temporal facts only. FHIR remains the source of those facts.

## 3. Non-goals

The protocol does not assess or infer:

- normal versus abnormal results;
- diagnosis;
- severity;
- urgency;
- treatment;
- medication or prescribing;
- clinical necessity of follow-up in general.

`NOT_MATCHED` means only that this protocol rule did not match. It does not mean clinical follow-up is unnecessary.

The contract does not provide a durable review queue, assignment, acknowledgement, autonomous message, FHIR write, or treatment action.

## 4. End-to-end sequence

```text
POST /internal/agent/follow-up
        -> inbound service authentication and feature gate
        -> authorized case scope
        -> mandatory application-owned FHIR acquisition
        -> immutable protocol snapshot
        -> deterministic POST_CONSULTATION_RESULT_REVIEW_V1 evaluation
        -> legacy/narrative LangGraph/Gemini subflow when allowed
        -> application-owned HTTP response composition
```

Mandatory acquisition and protocol evaluation are not model-controlled. If mandatory acquisition is unavailable, the workflow returns an unavailable result without asking Gemini to repair or reinterpret it.

## 5. Required FHIR resources

The V1 snapshot covers exactly these resource types:

- `Patient`;
- `Encounter`;
- `Observation`;
- `Appointment`.

This list is not permission to access other resource types.

## 6. Case resolution

`caseId` is an application identifier. It is not `Patient.id`.

The application searches `Patient.identifier` using:

```text
system=https://lab.local/followup-case
value=caseId
```

The Patient resolution search uses `_count=2` so the application can reject non-unique matches. Exactly one returned Patient must:

- contain the exact identifier system and value;
- have `resourceType=Patient`;
- have a valid, path-safe FHIR id.

For a `COMPLETE` Patient resolution search, no match, more than one match, an invalid identifier result, or an unsafe Patient id makes the authorized Patient unavailable. If the Patient search itself reaches a page or unique-resource limit while continuation remains, it is `PARTIAL` with `patient_resolution_incomplete`; partial precedence produces protocol `INSUFFICIENT` before collected match cardinality is interpreted. The compatibility identifier system is versioned implementation behavior and is not renamed by documentation.

## 7. Mandatory acquisition and completeness

After resolving the Patient, the application performs these mandatory operations:

| Resource | Operation |
|---|---|
| Patient | `GET Patient/{authorizedPatientId}` |
| Encounter | search by the authorized Patient and `status=finished` |
| Observation | search by the authorized Patient and `status=final` |
| Appointment | search by the authorized Patient |

The three collection searches use `_count=25` and these hard limits:

- maximum pages: `4`;
- maximum unique resources per type: `100`.

The application tracks collection state explicitly:

| State | Meaning |
|---|---|
| `COMPLETE` | The bounded traversal reached a valid end and the collected set may be used to establish presence or absence. |
| `PARTIAL` | Valid resources were collected, but a page or unique-resource limit was reached while continuation remained. Absence is not proven. |
| `UNAVAILABLE` | Transport, HTTP, structure, identity, integrity, pagination, or security validation failed. |
| `NOT_READ` | A required collection was not acquired; this is not a successful empty result. |

An empty `COMPLETE` search is different from `PARTIAL`, `UNAVAILABLE`, or `NOT_READ`. An incomplete search cannot prove absence.

## 8. Reference and identifier integrity

V1 accepts canonical relative references only:

- `Patient/{id}` for Patient association;
- `Encounter/{id}` for Observation-to-Encounter association.

Absolute URLs, history URLs, query-bearing references, fragments, nested paths, foreign types, and malformed references are not normalized into accepted references.

FHIR ids must match the R4 id character/length shape used by the application and must not be the unsafe path segments `.` or `..`. Patient IDs are validated before resource paths are constructed.

Returned Encounter, Observation, and Appointment resources must belong to the authorized Patient. A foreign or malformed resource fails closed; it is not silently treated as absent.

## 9. Encounter eligibility

An eligible Encounter must:

- be an `Encounter` with a valid id;
- have `status=finished`;
- have `subject.reference` exactly equal to `Patient/{authorizedPatientId}`.

If a complete snapshot contains no eligible finished Encounter, evaluation is `INSUFFICIENT` with `finished_encounter_missing`.

## 10. Observation eligibility and association

An eligible Observation must:

- be an `Observation` with a valid id;
- have `status=final`;
- have `subject.reference` exactly equal to `Patient/{authorizedPatientId}`;
- explicitly reference an eligible Encounter with `encounter.reference=Encounter/{id}`.

The referenced Encounter id must identify an eligible Encounter in the same authorized snapshot.

There is no temporal fallback and no “latest Encounter” heuristic. If no final Observation has an explicit eligible Encounter association, evaluation is `INSUFFICIENT` with `explicit_encounter_association_missing`.

## 11. Temporal semantics

For an explicitly associated pair:

- `Encounter.period.end` is `T1`;
- `Observation.issued` is `T2`;
- the pair qualifies when `T2 >= T1`.

`Observation.issued` is the protocol authority. `effectiveDateTime` is not used as a substitute.

Both timestamps must be complete date-times with seconds and an explicit `Z` or numeric timezone offset. V1 accepts zero to six fractional-second digits. Values are normalized to UTC for comparison.

The temporal predicate is existential: any valid explicit pair with `T2 >= T1` establishes a qualifying pair, even if another explicit pair has an invalid timestamp. If no qualifying pair has been established, missing, invalid, timezone-free, ambiguous, or more precise timestamps are not silently repaired or truncated and produce `INSUFFICIENT` information with the applicable reason code:

- `encounter_end_missing_or_invalid`;
- `observation_issued_missing_or_invalid`.

When every valid explicit pair has `Observation.issued < Encounter.period.end`, evaluation is `NOT_MATCHED` with `observation_issued_before_encounter_end`.

## 12. Appointment gate

Appointments are operationally classified at evaluation time:

| Classification | Current meaning |
|---|---|
| `UPCOMING_CONFIRMED` | `status=booked` and an application-parseable start at or after evaluation time. |
| `UPCOMING_UNCONFIRMED` | `status=pending` or `proposed`, with an application-parseable start at or after evaluation time. |
| `CANCELLED` | `status=cancelled`. |
| `PAST` | `status=booked` or `fulfilled`, with a valid past start. |
| `OTHER` | Any other status/start combination, including an unclassifiable start. |
| `NONE` | The complete Appointment search returned no appointments for the authorized Patient. |

For appointment classification, the current implementation trims the string, replaces a terminal `Z` with `+00:00`, and uses Python `datetime.fromisoformat`. A parseable timezone-free value is assigned UTC before comparison; this means a parseable date-only value is also treated as UTC midnight. This application parser is not a provider-neutral FHIR-instant validation guarantee. Both upcoming classifications use `start >= evaluation_time`; past uses `start < evaluation_time`.

After a qualifying Encounter/Observation pair is found:

- any `UPCOMING_CONFIRMED` Appointment produces `NOT_MATCHED` with `upcoming_confirmed_appointment`;
- otherwise, any `OTHER` classification produces `INSUFFICIENT` with `appointment_classification_ambiguous`;
- `UPCOMING_UNCONFIRMED`, `CANCELLED`, `PAST`, and `NONE` do not block this protocol match.

These classifications do not assert clinical adequacy, attendance, urgency, or whether follow-up is medically necessary. A confirmed appointment takes precedence over an `OTHER` classification when both are present.

For the confirmed-appointment result, `protocol.matchedResources` contains the qualifying Encounter/Observation pair and the confirmed Appointment references considered by the gate.

## 13. Protocol taxonomy

| Status | Meaning |
|---|---|
| `NOT_EVALUATED` | A required collection was not read, so the protocol did not run to a decision. |
| `MATCHED` | A qualifying post-consultation result exists and no confirmed future appointment blocks presentation for review. |
| `NOT_MATCHED` | This specific rule did not match: either valid observations precede encounter end or a confirmed future appointment exists. |
| `INSUFFICIENT` | Acquisition was incomplete or complete data lacked an unambiguous fact needed by the rule. |
| `UNAVAILABLE` | Mandatory acquisition or integrity/security validation was unavailable or invalid. |

Reason codes provide the bounded explanation. Consumers must not reinterpret one status as another.

The names above are the contract taxonomy. Their JSON values in `protocol.evaluationStatus` are serialized in lowercase: `not_evaluated`, `matched`, `not_matched`, `insufficient`, and `unavailable`.

## 14. Protocol authority

The protocol id is exactly:

```text
POST_CONSULTATION_RESULT_REVIEW_V1
```

The evaluator is deterministic and application-owned. Gemini cannot set, replace, override, or repair the protocol status, reasons, matched resources, clinical-assessment state, human-review state, or action state.

## 15. HTTP projection

The HTTP response includes:

```text
protocol.id
protocol.evaluationStatus
protocol.reasonCodes
protocol.matchedResources
clinicalAssessment
humanReview
action
answer
followUpRequired
```

`clinicalAssessment.status` is always `not_performed` in V1.

| Protocol result | `humanReview` | `action` |
|---|---|---|
| `MATCHED` | `status=required`, `reason=deterministic_post_consultation_protocol_match` | `status=proposed`, `type=review_follow_up_case` |
| `NOT_MATCHED` | `status=not_proposed`; reason omitted | `status=not_proposed`; type omitted |
| `INSUFFICIENT` | `status=not_determined`; reason omitted | `status=not_determined`; type omitted |
| `UNAVAILABLE` | `status=not_determined`; reason omitted | `status=not_determined`; type omitted |
| `NOT_EVALUATED` | `status=not_evaluated`; reason omitted | `status=not_determined`; type omitted |

`answer` and `followUpRequired` are legacy model-owned fields. They do not control any row in this table.

The top-level `status` describes workflow execution (`completed`, `denied`, `unavailable`, or `limit`); it is not the protocol evaluation status.

## 16. Evidence

`evidence` contains references returned through the legacy Gemini tool path and identifies the tool that read them. It describes narrative-agent provenance.

`protocol.matchedResources` contains resources used by the deterministic rule. It describes protocol reasoning.

The two collections have different owners and meanings. Tool evidence does not prove a protocol match, and protocol matched resources do not imply that Gemini used or interpreted them.

## 17. Partial and failure behavior

The evaluator applies these precedence rules to the mandatory snapshot:

1. Any `UNAVAILABLE` required collection produces protocol `UNAVAILABLE`.
2. Otherwise, any `PARTIAL` required collection produces `INSUFFICIENT`.
3. Otherwise, any `NOT_READ` required collection produces `NOT_EVALUATED`.
4. Only a complete snapshot proceeds to deterministic fact evaluation.

Examples of `UNAVAILABLE` conditions include transport/HTTP failure after bounded retry, malformed JSON or Bundle structure, invalid resource identity, foreign Patient association, unsafe references, invalid continuation URLs, conflicting duplicate resources, or non-unique Patient resolution established by a complete search.

Examples of `INSUFFICIENT` conditions include a page/resource safety limit, missing eligible Encounter/Observation facts, missing explicit association, ambiguous timestamps, or an `OTHER` Appointment classification.

A technical, security, or data-integrity failure is never converted into an empty successful result. Resources collected before a failed or incomplete mandatory read cannot masquerade as complete legacy tool evidence.

## 18. Continuation and HAPI pagination

V1 supports two explicit continuation branches. Once a traversal uses one branch, it cannot switch to the other branch during that traversal.

### Ordinary same-resource continuation

An ordinary continuation must remain on the same scheme, host, effective port and exact resource endpoint as the initial search. Every application-controlled initial query parameter must appear exactly once with the same value. This binds `identifier`, `patient` or `subject`, `status`, and `_count` where they were part of the initial search.

The only additional paging keys currently accepted are:

- `page`, with one positive ASCII-decimal value;
- `token`, with one non-empty value of at most 512 characters.

Those paging values may change between pages. Removing or changing an initial parameter, duplicating a query key, adding another Patient/subject predicate, adding an unrelated search predicate, changing the resource path, or switching to an operation fails before the continuation request is issued. This is an explicit adapter contract for the forms currently supported; it is not a provider-neutral paging guarantee.

### HAPI base-endpoint continuation

The current base-endpoint continuation support is intentionally HAPI-specific. It supports HAPI 8.10 links whose path is the configured FHIR base, for example the shape `/fhir?_getpages=...`, without publishing an opaque token in documentation or logs.

The continuation validator requires:

- the same scheme, host, and effective port as the configured FHIR base;
- the exact configured base path for HAPI base-endpoint continuation;
- one value for each required key: `_getpages`, `_getpagesoffset`, `_count`, `_bundletype`;
- no unapproved query keys or duplicate keys;
- a non-empty, length-bounded, stable traversal token;
- an ASCII decimal offset that advances by the fixed page size;
- an unchanged `_count`;
- `_bundletype=searchset`;
- only the supported optional `_pretty=true` value;
- no credentials, fragments, encoded separators, unsafe path segments, cycles, or path changes.

HTTP redirects are disabled and redirect responses fail the read. The paging token is traversal state, not authorization; case and resource validation still applies to every returned page. Page and unique-resource limits remain authoritative even when a valid next link exists.

Other FHIR servers may require a separate adapter or a separately designed continuation contract. This V1 behavior is not presented as a provider-neutral paging standard.

## 19. Case isolation

The invariant is:

> The application must never issue a continuation request that changes the application-authorized semantic search from case X to case Y. Any returned clinical resource that does not belong to the authorized case or Patient must fail validation and must not be accepted or exposed by the workflow.

The authorized case is bound to one execution context. Model-proposed reads must use the same `caseId`; a different or missing id is denied before query construction. The resolved Patient id constrains all subsequent paths, subjects, participants, Encounter associations, and returned resources.

Isolation applies to the initial response and every continuation page. An ordinary continuation cannot change the application-authorized semantic search, and the HAPI paging token never replaces or expands the authorized case scope. Returned-resource Patient/reference validation remains mandatory defense in depth for both branches. These controls do not claim to prevent a faulty upstream server from transmitting an incorrect resource; they require the workflow to reject it rather than accept or expose it.

## 20. Model boundary

Mandatory acquisition and deterministic evaluation occur before LangGraph. Gemini does not choose whether the protocol reads Patient, Encounter, Observation, or Appointment.

The narrative subflow may use only its explicitly authorized tools and data contracts. Its structured `followUpRequired` value (`true`, `false`, or `unknown`) and free-text `answer` remain legacy output. They neither prove nor override `MATCHED`, `NOT_MATCHED`, `INSUFFICIENT`, `UNAVAILABLE`, human review, or proposed action.

## 21. Writes and actions

V1 performs no:

- FHIR create, update, patch, or delete;
- autonomous message delivery;
- prescription or medication action;
- diagnosis or treatment action;
- external execution of `review_follow_up_case`.

The action in the response is a proposal only.

## 22. Human-review semantics

`humanReview.status=required` means that the deterministic protocol determined the case should be presented for human review.

It does not prove that a durable work item, queue entry, reviewer assignment, acknowledgement, disposition, or service-level workflow exists. Those operational capabilities are outside V1.

## 23. Testing and acceptance properties

The contract is protected by complementary categories rather than a fixed permanent test count:

- pure protocol tests for taxonomy, temporal rules, appointment gating and projection;
- workflow tests for mandatory acquisition ordering and separation from LangGraph;
- case-isolation and concurrency tests;
- pagination tests for completeness, limits, malformed Bundles, duplicate resources and continuation security;
- endpoint/model-contract tests for closed request/response schemas and legacy-field independence;
- deterministic evaluation scenarios using scripted models and in-memory FHIR data;
- opt-in real HAPI tests, including productive multipage traversal;
- separately opt-in live Gemini tests.

The default deterministic suite must not require HAPI, an API key, Epic, Oracle, or live Gemini. `RUN_HAPI_INTEGRATION_TESTS=true` opts into local HAPI coverage. `RUN_LIVE_GEMINI_TESTS=true` opts into live Gemini coverage; follow-up live tests also require their HAPI prerequisites. Passing model behavior alone is not evidence of protocol correctness, and these tests do not establish clinical safety or regulatory approval.
