# Security & Governance v1 closure

## Status

**Implementation complete; operational full-stack validation pending.**

Security & Governance V1 TASK 006 records the available laboratory validation evidence for the controls implemented in TASK 001 through TASK 005 and the reproducible checks added in TASK 006. It does not declare production readiness, regulatory compliance, verified clinical identity, enterprise IAM, or a complete end-to-end security trace.

The validation used synthetic data only. Gemini, HAPI, cloud resources, external sandboxes and production identity providers were not started or contacted. The operational multi-process demonstration was not rerun during TASK 006 because Docker Engine was unavailable. Its runner and isolated profile were validated deterministically, and the maximum non-container coverage was executed.

## Implemented scope by task

| Task | Implemented control |
|---|---|
| TASK 001 | File-backed Python `SECURITY_AUDIT_V1`, strict event/metadata allowlists, durable development-login decisions and fail-closed session issuance. |
| TASK 002 | Durable `workflow_start` and `workflow_resume` access decisions, minimized workflow references, stable correlation validation and fail-closed graph entry. |
| TASK 003 | Human Review close decisions, resolved development-principal attribution, transactional review writes and automatic resume without a fabricated service actor. |
| TASK 004 | Java Clinical Federation access audit, verified participant/organization attribution, authorization reason codes and fail-closed audit before connectors. |
| TASK 005 | Exact constant-time service-token checks, duplicate-header rejection, Python credential separation, secret-safe settings representation and HTTPS handoff-cookie hardening. |
| TASK 006 | Security coverage inventory, isolated audit paths in the existing E2E runner, regression automation, sensitive-data review and this closure evidence. |

No task in this epic implemented Keycloak, OIDC, enterprise RBAC, workload identity, mTLS, managed secret rotation, Azure/AWS authorization, MCP, a new agent, a new microservice or a new clinical protocol.

## Authentication controls

- Python `/internal/*` routes require exactly one exact `X-Service-Token`. Missing, empty, whitespace-altered, duplicated and invalid values fail closed.
- Java Model Boundary, Clinical Read and Clinical Federation apply the same single-header and exact-value rule before protected work.
- Python and Java compare derived or encoded credential bytes with constant-time primitives. Credential values are not placed in normal error responses or audit events.
- Configured Python service, form-signing, development-login and federation credentials must be pairwise distinct. Empty values remain unconfigured and protected boundaries fail closed.
- Human Review uses a development-only loopback authenticator and an opaque, hashed-at-rest application session. It is synthetic laboratory identity, not enterprise or clinician identity.

## Authorization controls

- A Clinical Federation participant is derived from the matched server-side token map. Request fields cannot choose the effective caller.
- The source registry owns the participant organization. The request organization and patient system must match the authenticated participant.
- Source grants are explicit. A mixed request containing an ungranted well-formed source rejects the whole request before connectors.
- Contractual denials remain `organization_mismatch`, `identity_system_mismatch` and `source_not_authorized`. Malformed identifiers and source keys remain HTTP 400 validation errors, not security denials.
- Connector failures, identity misses, timeouts and partial clinical results occur after authorization and are not relabeled as denied access.
- Human Review session resolution, same-origin validation, purpose-separated HMAC, optimistic version and case state remain independent checks. Authentication alone is not case authorization or assignment.

## Audit, attribution and durability

Python and Java own separate SQLite stores. TASK 006 makes both paths explicit inside each operational-demo execution directory:

- Python: `security-audit.sqlite3`.
- Java: `federation-security-audit.sqlite`.

The E2E profile does not reuse an operator's default audit database. Tests reopen stores through new repository instances, validate unique event ids and timestamps, enforce correlation formats and verify event-specific metadata allowlists.

Python covers `authentication`, `workflow_start`, `workflow_resume` and `human_review_decision`. Java covers `clinical_federation_access`. An `allowed` row means the validated operation was permitted to begin; it does not claim connector success, Review commit, workflow completion or a favorable clinical result.

Human attribution is stored with the operational Review transaction, while security audit is a separate transaction and database. The accepted inconsistency windows are therefore:

- an allowed Human Review audit can remain if the later Review transaction rolls back;
- an allowed workflow event can remain if graph execution later fails;
- an allowed Java federation event can remain if identity resolution or a connector later fails;
- retries can produce a new allowed access decision, while review/checkpoint idempotency prevents duplicate business transitions.

There is no distributed transaction among audit, Review, sessions, checkpoints, exchange storage or connector systems. The stores are mutable by their filesystem owner and are not a tamper-proof ledger.

## Human Review validation

Deterministic coverage validates:

- accepted development login and valid session;
- missing, invalid, expired and revoked sessions;
- manipulated cookies, cross-origin POSTs and invalid, expired, cross-session or wrong-purpose HMACs;
- optimistic version checks, repeated closure and concurrent decisions;
- one durable `human_review_decision` for the accepted new closure;
- one synthetic development attribution committed with the Review transition;
- rollback when mandatory audit cannot be appended;
- automatic LangGraph resume only after the successful close commit;
- no second closure, attribution or resume effect on an idempotent repeat.

A denied close does not change the case. A completed case does not record another operational closure. The displayed principal remains explicitly labeled as a synthetic development principal.

## End-to-end coverage matrix

| Area | Unit / component | Isolated local integration | Real laboratory processes | Dedicated container | External infrastructure |
|---|---|---|---|---|---|
| Python service authentication and secret separation | Executed | FastAPI/TestClient, temporary configuration | Runner profile inspected; live process not started | Not required | Not required |
| Java service authentication | Executed | MockMvc/Spring | Runner profile inspected; live process not started | Not required | Not required |
| Clinical Federation authorization and audit | Executed | Service/filter tests and temporary SQLite | Blocked by Docker Engine | PostgreSQL path blocked | Not required |
| Python audit and Human Review | Executed | Temporary Review, Session, Audit and checkpoint files | Blocked with the stack | Not required | Not required |
| Cross-organization LangGraph flow | Executed with deterministic clients | Positive and negative correlation scenarios | Blocked by Docker Engine | PostgreSQL path blocked | Gemini disabled |
| Mini HIS | Executed | Spring/SQLite tests | Not started | Not required | Not required |
| Mini LIS | Deterministic transition tests executed | REST/normalizer tests executed in Java consumer | Not started | PostgreSQL tests blocked | Not required |
| Demo Experience V2 | Report rendering tests executed | Temporary stored reports | Live view not started | Depends on the operational stack | Not required |
| IAM, enterprise connectors and MCP | Not implemented | Not applicable | Not applicable | Not applicable | Outside TASK 006 |

## Validation execution

The following non-container results were obtained on the TASK 006 branch:

- Python security, audit, Human Review, federation consumer, three workflow types and demo runner: `295 passed`, `1 skipped`, `4 deselected`.
- Existing runner focal coverage after audit-path isolation: `13 passed`, `1 deselected`.
- Java authentication, Clinical Federation authorization/audit and fail-closed behavior: `48 tests`, no failures.
- Java Mini HIS/Mini LIS connector, normalization and exchange regression: `31 tests`, no failures.
- Mini HIS module: `14 tests`, no failures.
- Mini LIS deterministic transition suite: `4 tests`, no failures.

The four deliberate Python deselections were the three known CRLF byte-hash checks for `001_follow_up_review.sql` and the Windows ACL mutation check. The CRLF tests were also executed separately and reproduced exactly their three known failures: expected LF hash `94a043...be80`, working-tree CRLF hash `c58dc0...2676`. Historical migrations were not modified. The ACL test was not executed because TASK 006 forbids permission changes.

One Java test defect was found during validation: a raw SQLite leakage assertion rejected the generic substring `141`, which randomly occurred inside a generated event UUID. The assertion was removed because no tested input supplied that substring. Assertions for the actual synthetic patient marker, participant token, FHIR resource labels and name marker remain.

Representative commands:

```text
services\ai-service\.venv\Scripts\python.exe scripts\end-to-end-demo\run_demo.py check
services\ai-service\.venv\Scripts\python.exe -m pytest -p no:cacheprovider <security-and-workflow-files> -k <documented exclusions> -q
mvn -q -Dtest=FederationSecurityConfigurationTest,FederationServiceTest,FederationSecurityAuditTest,ModelBoundaryServiceAuthFilterTest,ModelBoundaryServiceAuthUnconfiguredTest,ClinicalReadControllerTest,ClinicalReadAuthUnconfiguredTest test
mvn -q -Dtest=MiniLisExchangeConnectorTest,ExchangeServiceTest,Hl7ExchangeCodecTest,MiniHisConnectorTest,MiniHisLongitudinalNormalizationTest,MiniHisServiceRequestTest,MiniLisConnectorTest,MiniLisNormalizerTest test
```

## Positive and negative scenarios

The deterministic baseline preserves both `cross_org_lab_result` scenarios:

- correlated Mini HIS order, linked Mini LIS order and final result: `matched`, `waiting_human`, open Review case;
- final result on another order: `not_matched`, completed workflow, no Review case.

Security scenarios cover valid, missing, invalid, empty, whitespace-altered and duplicate service tokens; valid and reused credential configuration; wrong organization and caller system; allowed, ungranted, mixed and syntactically invalid source requests; unauthenticated Review; bad Origin/HMAC; stale version; repeated and concurrent closure; and unavailable mandatory audit.

Rejected authentication and authorization paths assert that protected providers, connectors, graph transitions or Review writes are not invoked. Java operational connector errors remain authorized operational failures rather than false security denials.

## Correlation boundary

The Python federation client generates `FED-[A-F0-9]{16}` immediately before its Java request. Java reuses that value in the access event, operational federation logs and successful response, and Python logs the returned value. This proves correlation only across the Python-to-Java federation hop.

The identifier is not propagated from workflow start, an earlier Python audit event, checkpoint state, Human Review or Mini HIS/Mini LIS exchange correlation. The current platform therefore does not provide end-to-end correlation from AI Service through Human Review. A future change requires an explicit propagation contract; TASK 006 does not alter functional APIs to add one.

## Sensitive-data analysis

Automated and manual inspection covered Python/Java log templates, HTTP denials, both audit schemas, E2E report projection and generated test stores. The controls exclude credentials, cookies, token hashes, HMAC secrets, model keys, request bodies, unrestricted metadata, patient identifiers and clinical payloads from security audit.

Synthetic clinical identifiers and results may legitimately appear in functional clinical responses and isolated connector tests. They must not appear in access-decision audit rows. The E2E public report retains only the documented synthetic references and provenance needed to demonstrate the protocol; it excludes tokens, names and secret files.

No real secret or clinical data was added to versioned files. High-entropy runtime secrets remain untracked inside the ignored execution directory and are not printed by the runner.

## Blocked or deferred validation

- The real multi-process operational run, `FederationFlowTest`, Mini LIS Testcontainers suites and Demo Experience V2 live page were blocked because Docker Engine was unavailable. The executable was present, all dedicated ports were free and the recorded previous run was not active.
- Live HAPI tests were not run and `local-hapi` was not started, stopped, seeded or modified.
- Gemini, Epic, Oracle, Azure and AWS paths were not run because they require external infrastructure or credentials and are outside this task.
- No operating-system ACL test was run because TASK 006 prohibits ACL changes.

## Residual risks and laboratory restrictions

- Shared static secrets lack managed rotation, revocation and workload identity.
- Development login represents one configured synthetic principal and has no roles, assignment, organization or clinical authorization.
- SQLite supports the documented single-process laboratory topology; it is neither encrypted by the application nor immutable, centralized or replicated.
- Human Review audit, business state and checkpoint are not transactionally atomic with each other.
- The network boundary, TLS termination, rate limiting, protected secret storage, retention and backup remain deployment responsibilities.
- The real container-backed E2E result must be obtained on a host with Docker Engine before claiming current full-stack evidence.
- The three CRLF hash failures remain a Windows checkout issue and must not be hidden by editing historical migrations.

## Readiness for later epics

### Identity & Access Foundation V1

Required decisions include local Keycloak for development, provider-agnostic OIDC, an internal identity independent of provider claims, strict issuer/audience/signature validation, session migration for new authenticators, workload identity, logout/revocation behavior and separation between login and resource authorization. Development identity must remain visibly non-production.

### Enterprise Connector Authorization V1

Required controls include organization-specific credentials and grants, delegated versus application access, Microsoft Entra ID for Azure resources, Azure RBAC, a future AWS IAM/STS design, managed secret storage and rotation, revocation, tenant isolation, minimized external audit and explicit data-purpose contracts. Connector errors must remain distinct from authorization decisions.

### MCP Integration Foundation V1

Required controls include an explicit tool registry, organization/purpose allowlists, verified caller identity, per-tool credentials, bounded inputs/outputs, timeouts and execution budgets, provenance, prompt-injection and tool-poisoning defenses, exfiltration tests, minimized invocation audit and authenticated Human Review before sensitive or irreversible actions. Documents, API results and MCP responses remain untrusted content and cannot modify privileged instructions or effective permissions.

## Client implementation criteria

A future client is acceptable only when it has a versioned contract, identifies the owner of authentication and authorization, uses scoped credentials, validates all input and output, preserves source provenance and bounded correlation, fails closed without translating operational failure into clinical absence, emits minimized audit evidence, provides deterministic negative tests and documents retention and Human Review requirements. It must not broaden Java/Python responsibilities or bypass the existing normalization boundary.

## References

- [Service security hardening v1](service-security-hardening-v1.md)
- [Security audit v1](../contracts/security-audit-v1.md)
- [Clinical Federation v1](../contracts/clinical-federation-v1.md)
- [AI clinical federation consumer v1](../contracts/ai-clinical-federation-v1.md)
- [Human identity v1](../contracts/human-identity-v1.md)
- [Human attribution v1](../contracts/human-attribution-v1.md)
- [Follow-up review workflow v1](../contracts/follow-up-review-workflow-v1.md)
- [Operational E2E demonstration](../demos/end-to-end-operational-v1.md)
- [Demo Experience v2](../demos/demo-experience-v2.md)
