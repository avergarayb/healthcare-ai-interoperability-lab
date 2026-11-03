# Security & Governance v1 closure

## Status

**Security & Governance V1 implementation complete; operational laboratory E2E and isolated federation validated; broader validation remains partial.**

Security & Governance V1 TASK 006 and TASK 007 record the available laboratory validation evidence for the controls implemented in TASK 001 through TASK 005, the reproducible checks added in TASK 006 and the isolated federation boundary completed in TASK 007. They do not declare production readiness, regulatory compliance, verified clinical identity, enterprise IAM, or a complete end-to-end security trace.

The validation used synthetic data only. Gemini, local HAPI, cloud resources, external sandboxes and production identity providers were not started or contacted. On 2026-10-27 the operational multi-process demonstration was executed with isolated Mini HIS, Mini LIS, Java FHIR Integration, Python AI Service and PostgreSQL processes. The run passed its positive and negative scenarios, live security checks, Human Review close/resume, audit inspection and Demo Experience review. TASK 007 then separated the autonomous Clinical Federation proof from legacy HAPI exact-read compatibility and executed the federation proof against only test-owned Mini HIS, Mini LIS and PostgreSQL resources. Operational compatibility with a real, independently provisioned HAPI server remains an opt-in legacy validation and was not run.

## Implemented scope by task

| Task | Implemented control |
|---|---|
| TASK 001 | File-backed Python `SECURITY_AUDIT_V1`, strict event/metadata allowlists, durable development-login decisions and fail-closed session issuance. |
| TASK 002 | Durable `workflow_start` and `workflow_resume` access decisions, minimized workflow references, stable correlation validation and fail-closed graph entry. |
| TASK 003 | Human Review close decisions, resolved development-principal attribution, transactional review writes and automatic resume without a fabricated service actor. |
| TASK 004 | Java Clinical Federation access audit, verified participant/organization attribution, authorization reason codes and fail-closed audit before connectors. |
| TASK 005 | Exact constant-time service-token checks, duplicate-header rejection, Python credential separation, secret-safe settings representation and HTTPS handoff-cookie hardening. |
| TASK 006 | Security coverage inventory, isolated audit paths in the existing E2E runner, regression automation, sensitive-data review and this closure evidence. |
| TASK 007 | Autonomous Clinical Federation integration proof, explicit legacy HAPI opt-in boundary and preservation of the original federation/Clinical Read assertions. |

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

The operational run produced three allowed `authentication` events, one denied `human_review_decision` and one allowed `human_review_decision`. The log timestamps tie the three authentications to the runner opening Review, the operator session used to close the case, and the later Demo Experience detail review. It produced no `workflow_start` or `workflow_resume` event by contract: the runner calls `start_workflow(...)` directly in its process rather than `POST /internal/workflows`, and the successful Review close invokes the internal checkpoint auto-resume rather than `POST /internal/workflows/{workflowId}/resume`. Neither internal path invents the endpoint's generic `service_client` actor. The completed checkpoint proves execution and resume, not an audited service-token request.

The two workflow event types are implemented only at those authenticated HTTP boundaries and are covered by deterministic endpoint tests, including mandatory-audit failure and checkpoint preservation. The operational run did not exercise those boundaries or a live audit-storage failure. No workflow access event exists in another store: `agent-workflow.sqlite3` is business checkpoint/index state, while `security-audit.sqlite3` is the sole Python security-audit store for the execution.

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
| Python service authentication and secret separation | Executed | FastAPI/TestClient, temporary configuration | Live isolated process passed | Not required | Not required |
| Java service authentication | Executed | MockMvc/Spring | Live isolated process passed | Not required | Not required |
| Clinical Federation authorization and audit | Executed | Service/filter tests and temporary SQLite | Live allow/deny boundaries and audit passed | `FederationFlowTest` passed with isolated Mini HIS, Mini LIS, PostgreSQL and audit SQLite | Not required |
| Python audit and Human Review | Executed | Temporary Review, Session, Audit and checkpoint files | Live login, Review denial/close, attribution and internal resume passed; workflow HTTP audit remained deterministic | Not required | Not required |
| Cross-organization LangGraph flow | Executed with deterministic clients | Positive and negative correlation scenarios | Live positive and negative scenarios passed | Operational PostgreSQL and directly related isolated flow passed | Gemini disabled |
| Mini HIS | Executed | Spring/SQLite tests | Live isolated process passed | Not required | Not required |
| Mini LIS | Deterministic transition tests executed | REST/normalizer tests executed in Java consumer | Live isolated process passed | 16 Testcontainers tests passed across Mini LIS and Java consumer suites | Not required |
| Demo Experience V2 | Report rendering tests executed | Temporary stored reports | Live authenticated historical detail passed | Backed by the operational stack | Not required |
| IAM, enterprise connectors and MCP | Not implemented | Not applicable | Not applicable | Not applicable | Outside TASK 006 |

## Validation execution

The following non-container results were obtained on the TASK 006 branch:

- Python security, audit, Human Review, federation consumer, three workflow types and demo runner: `295 passed`, `1 skipped`, `4 deselected`.
- Existing runner focal coverage after audit-path isolation: `13 passed`, `1 deselected`.
- Java authentication, Clinical Federation authorization/audit and fail-closed behavior: `48 tests`, no failures.
- Java Mini HIS/Mini LIS connector, normalization and exchange regression: `31 tests`, no failures.
- Mini HIS module: `14 tests`, no failures.
- Mini LIS deterministic transition suite: `4 tests`, no failures.
- Operational run `E2E-20261027T213944Z-541B0A`: started at `2026-10-27T21:39:44Z`, report written at `2026-10-27T21:40:31Z`, inspected live and stopped at `2026-10-27T21:55:52Z`.
- Live services: Mini HIS `127.0.0.1:18295`, Mini LIS `127.0.0.1:18296`, Java FHIR Integration `127.0.0.1:18281`, Python AI Service `127.0.0.1:18290` and PostgreSQL `127.0.0.1:15434`; all health checks passed.
- Live Clinical Federation: valid token returned `200`; missing and invalid tokens returned `401`; wrong organization, wrong caller system and ungranted source returned `403` with the expected fail-closed reasons.
- Python audit persisted five minimized events—three allowed authentications, one denied Review decision and one allowed Review decision—and Java audit persisted ten minimized events in separate execution-local SQLite files. Event ids and correlation ids were valid and unique, metadata matched the allowlists, and structured review found no credentials or clinical payloads. Python workflow start/resume events were absent for the contractual direct-execution reason described above, not because they were written elsewhere.
- Mini LIS Testcontainers suites: `MiniLisApiTest` (`8`) and `MiniLisHl7Test` (`5`), `13 tests`, no failures or skips.
- Direct Java consumer Testcontainers suites: `MiniLisClinicalFlowTest` (`2`) and `CrossOrgLabExchangeFlowTest` (`1`), `3 tests`, no failures or skips.

TASK 007 added and executed the following non-duplicated evidence:

- Isolated federation: `FederationFlowTest` (`1`), no failures or skips. It verified complete and partial federation, normalized resources, source-qualified provenance, strict FHIR parsing, identity unresolved, connector unavailable, source grants, 401, organization/caller/source 403 denials and seven persisted access decisions.
- Mini LIS Testcontainers: `MiniLisApiTest` (`8`) and `MiniLisHl7Test` (`5`), `13 tests`, no failures or skips.
- Java consumer Testcontainers: `MiniLisClinicalFlowTest` (`2`) and `CrossOrgLabExchangeFlowTest` (`1`), `3 tests`, no failures or skips. Together with the isolated federation proof this is `17` unique container-backed tests.
- Mini HIS: `MiniHisSimulatorTest` (`9`), `MiniHisSchemaMigrationTest` (`4`) and `MiniHisLabOrderTest` (`1`), `14 tests`, no failures or skips. Mini LIS transition regression: `OrderTransitionTest` (`4`), no failures or skips.
- Federation authorization/audit, Model Boundary authentication, Clinical Read and Mini HIS/LIS connector/normalizer regression: `76 tests` across 14 explicitly selected classes, no failures or skips.
- Test compilation, including `LegacyHapiClinicalReadCompatibilityLiveIT`, passed. The legacy class was not executed.

### TASK 007 final review — 2026-11-02

Test compilation and the seven related Java security/audit classes passed again: `48 tests`, no failures or skips. The earlier `17` container-backed tests and `111` total Java tests remain evidence from the previous TASK 007 execution, not results of this review.

The effective Maven configuration was checked for default, HAPI, Epic and Oracle live profiles. Surefire and default Failsafe exclude `LiveIT`; the HAPI profile marker is false outside its dedicated Failsafe profile, and invocation ownership confirmation defaults to false. Five safe discovery checks skipped the legacy class before Spring startup: Surefire with inherited HAPI environment opt-ins; Failsafe without the HAPI profile; Failsafe with the Epic profile; the HAPI profile without explicit ownership confirmation; and the HAPI profile without the environment opt-in. None executed the HAPI test body or contacted HAPI. These are gate checks, not five successful HAPI compatibility tests.

Docker Engine was unavailable at preflight, including a check outside the filesystem sandbox. The isolated Federation Testcontainers rerun was therefore not started, and no Docker resource was created or changed. The Product Owner explicitly approved committing and pushing TASK 007 without an immediate rerun, based on the earlier passing FederationFlowTest, 111 Java tests, the current 48 passing security/audit tests, five legacy-HAPI gate checks, successful compilation and no production changes. FederationFlowTest was not rerun after the final gate adjustments; the previous container results were not relabeled as current validation. The final container rerun remains deferred and does not block the authorized commit/push.

The four deliberate Python deselections were the three known CRLF byte-hash checks for `001_follow_up_review.sql` and the Windows ACL mutation check. The CRLF tests were also executed separately and reproduced exactly their three known failures: expected LF hash `94a043...be80`, working-tree CRLF hash `c58dc0...2676`. Historical migrations were not modified. The ACL test was not executed because TASK 006 forbids permission changes.

One Java test defect was found during validation: a raw SQLite leakage assertion rejected the generic substring `141`, which randomly occurred inside a generated event UUID. The assertion was removed because no tested input supplied that substring. Assertions for the actual synthetic patient marker, participant token, FHIR resource labels and name marker remain.

Representative commands:

```text
services\ai-service\.venv\Scripts\python.exe scripts\end-to-end-demo\run_demo.py check
services\ai-service\.venv\Scripts\python.exe scripts\end-to-end-demo\run_demo.py run --keep
services\ai-service\.venv\Scripts\python.exe scripts\end-to-end-demo\run_demo.py stop
services\ai-service\.venv\Scripts\python.exe -m pytest -p no:cacheprovider <security-and-workflow-files> -k <documented exclusions> -q
mvn -q -Dtest=FederationSecurityConfigurationTest,FederationServiceTest,FederationSecurityAuditTest,ModelBoundaryServiceAuthFilterTest,ModelBoundaryServiceAuthUnconfiguredTest,ClinicalReadControllerTest,ClinicalReadAuthUnconfiguredTest test
mvn -q -Dtest=MiniLisExchangeConnectorTest,ExchangeServiceTest,Hl7ExchangeCodecTest,MiniHisConnectorTest,MiniHisLongitudinalNormalizationTest,MiniHisServiceRequestTest,MiniLisConnectorTest,MiniLisNormalizerTest test
mvn -q -Dtest=MiniLisApiTest,MiniLisHl7Test test
mvn -q -Dtest=MiniLisClinicalFlowTest,CrossOrgLabExchangeFlowTest test
```

## Positive and negative scenarios

The operational run and deterministic baseline preserve both `cross_org_lab_result` scenarios:

- correlated Mini HIS order, linked Mini LIS order and final result: `matched`, `waiting_human`, Review case `7034e356-bd45-43c2-96b9-3ed40c597bfb`; an authenticated synthetic operator closed it as `follow_up_coordination_planned`, attribution was persisted and workflow `wf-84a5260a30ad7d6ee9cf18d552f0e8c3` resumed to `completed`;
- final result on another order: `not_matched`, reason `result_order_mismatch`, completed workflow and no Review case.

Live security scenarios covered valid, missing and invalid Java federation tokens; wrong organization and caller system; an ungranted source; unauthenticated Review; and an authorized Review close. Empty, whitespace-altered and duplicate credentials, mixed and syntactically invalid sources, bad Origin/HMAC, stale version, repeated and concurrent closure, Python workflow service-token boundaries, and unavailable mandatory audit remain deterministic test evidence.

Deterministic rejected authentication and authorization paths assert that protected providers, connectors, graph transitions or Review writes are not invoked. In the live run, an unauthenticated Review close redirected to login, recorded `human_session_missing` and left the case open; the later authorized close succeeded. Java operational connector errors remain authorized operational failures rather than false security denials. Fail-closed behavior for an unavailable audit store was not induced in the live stack.

## Correlation boundary

The Python federation client generates `FED-[A-F0-9]{16}` immediately before its Java request. Java reuses that value in the access event, operational federation logs and successful response, and Python logs the returned value. This proves correlation only across the Python-to-Java federation hop.

The identifier is not propagated from workflow start, an earlier Python audit event, checkpoint state, Human Review or Mini HIS/Mini LIS exchange correlation. The current platform therefore does not provide end-to-end correlation from AI Service through Human Review. A future change requires an explicit propagation contract; TASK 006 does not alter functional APIs to add one.

## Sensitive-data analysis

Automated and manual inspection covered Python/Java log templates, HTTP denials, both audit schemas, E2E report projection and generated test stores. The controls exclude credentials, cookies, token hashes, HMAC secrets, model keys, request bodies, unrestricted metadata, patient identifiers and clinical payloads from security audit.

Synthetic clinical identifiers and results may legitimately appear in functional clinical responses and isolated connector tests. They must not appear in access-decision audit rows. The E2E public report retains only the documented synthetic references and provenance needed to demonstrate the protocol; it excludes tokens, names and secret files.

No real secret or clinical data was added to versioned files. High-entropy runtime secrets were not printed or found in reports, logs or audit stores; the two execution-local secret files were removed after the stack stopped. The synthetic report and both audit databases remain untracked in the ignored execution directory as review evidence.

## Blocked or deferred validation

- The historical mixed-test constraint is resolved: `FederationFlowTest` now selects only the isolated Mini HIS source in its Spring context, assigns any unused local-HAPI endpoint to an inaccessible loopback port and contains no Clinical Read request or `syn-demo-patient-102` dependency. All original federation assertions execute there; explicit wrong-organization and wrong-caller assertions plus persisted audit-decision checks strengthen the live boundary.
- The original legacy Clinical Read assertions now live in `LegacyHapiClinicalReadCompatibilityLiveIT`. Surefire and default Failsafe explicitly exclude it. JUnit requires the dedicated `hapi-legacy-live` profile marker, the invocation flag `-Dhapi.legacy.testOwnedConfirmed=true`, `HAPI_LEGACY_LIVE_IT=true`, an explicit loopback `HAPI_LEGACY_BASE_URL` and `HAPI_LEGACY_TEST_OWNED=true`. Inherited environment variables alone cannot enable it. The operator must verify ownership of the dedicated HAPI R4 server and storage before confirming; loopback and flags do not prove ownership. The server must already contain synthetic Patient `syn-demo-patient-102`; this test only reads.
- That opt-in compatibility test was compiled and its disabled gates were checked, but its live body was not executed. Therefore startup, readiness, seeding, persistence and exact-read interoperability against a real HAPI deployment remain unvalidated. Deterministic Clinical Read tests preserve contract behavior but do not substitute for this evidence.
- A future bounded task can supply a dedicated HAPI Testcontainers fixture with an approved image, readiness check, synthetic seed and automatic cleanup. Until then, the preexisting `local-hapi` is not an admissible test dependency.
- `local-hapi` was not started, stopped, seeded, queried or modified.
- Gemini, Epic, Oracle, Azure and AWS paths were not run because they require external infrastructure or credentials and are outside this task.
- No operating-system ACL test was run because TASK 006 prohibits ACL changes.

## Residual risks and laboratory restrictions

- Shared static secrets lack managed rotation, revocation and workload identity.
- Development login represents one configured synthetic principal and has no roles, assignment, organization or clinical authorization.
- SQLite supports the documented single-process laboratory topology; it is neither encrypted by the application nor immutable, centralized or replicated.
- Human Review audit, business state and checkpoint are not transactionally atomic with each other.
- The network boundary, TLS termination, rate limiting, protected secret storage, retention and backup remain deployment responsibilities.
- Security & Governance V1 now has both the operational multi-process E2E and autonomous Federation Testcontainers evidence. Broader interoperability validation remains partial because the separate legacy HAPI live compatibility boundary has not been executed against a dedicated test-owned server.
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
