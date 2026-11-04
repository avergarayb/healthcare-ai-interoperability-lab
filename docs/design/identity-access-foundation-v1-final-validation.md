# Identity & Access Foundation V1 — transversal laboratory validation

TASK 006 implementation and validation are functionally accepted by the Product Owner for laboratory scope. Controlled integrity review, commit/push of exactly its six files and a PR toward main are authorized; no functional change or merge is authorized. TASK 005 is integrated through PR #107. This is a proposed laboratory closure, **not an approved final EPIC closure or production readiness statement**. Verify Git references each session. [ADR-096](../adr/ADR-096-identity-provider-agnostic-v1.md) remains the architecture authority.

## Capability inventory before harness implementation

The comparison below was established from the implemented contracts and sources before adding the transversal runner. Sharing contract semantics does not require identical implementations or sharing a PrincipalContext instance between processes.

| Capability | Healthcare AI / Python | Healthcare Interoperability / Java |
|---|---|---|
| Existing technical route | GET `/iam-lab/v1/workload-context` | Same path, independent receiving API |
| Activation | `OIDC_WORKLOAD_LAB_ENABLED`, false by default; absent route/OpenAPI | `IAM_JAVA_WORKLOAD_LAB_ENABLED`, false by default; absent controller/scoped chain |
| Signature | PyJWT/cryptography; explicit RS256 | Spring Resource Server/Nimbus; explicit RS256 |
| Issuer | One exact approved registration; no default provider | Same constraint; independently configured |
| Audience | Exactly `healthcare-ai-api` | Exactly `healthcare-interop-api` |
| Access profile | Named `keycloak-client-credentials-v1`; signed Bearer purpose, bounded kid/jti, iat/exp/optional nbf | Same purpose semantics; not a claim of RFC 9068 emission |
| Workload binding | Exact approved issuer/client/subject, static or opt-in local registry | Exact approved issuer/client/subject, static only |
| Internal context | Frozen dataclass; PrincipalContext v1, workload, client-credentials method | Immutable record; same contract semantics, independently constructed |
| Organization | Static fixed membership or SQLite snapshot; explicit selection if several | One fixed registered organization per credential; candidate must match |
| Permission | `iam.workload-context.read`, calculated locally | `iam.java-workload-context.read`, calculated locally |
| Audit | Own `oidc-workload-security-audit-v1` SQLite; optional registry has separate atomic change audit | Own `java-oidc-security-audit-v1` SQLite, separate from Federation/exchange |
| Status | 200 / authentication 401 / policy 403 / required dependency 503 | Same broad semantics; reason/order differences are contractual |
| Disabled principal/binding | SQLite 401; historical static mode 403 | 401 |
| Keys/rotation | Provider-scoped monotonic locked bounded cache, throttled misses, replacement on rotation | Same semantics; synchronized Java cache, no shared cache |
| Time | Original token-bound context, strict integer dates; max lifetime 300s, skew <=60s | Same bounds, with original-integer admission before Nimbus date conversion |
| HTTP methods | FastAPI explicit GET; no global OIDC middleware | Exact GET matcher, controller guard rejects implicit HEAD with 401; REQUEST-only scoped proxy |
| Infrastructure | Python environment; live provider only for explicit integration | Java 21/current jar; live provider only for explicit integration |
| Limits | Local SQLite/CLI, no authenticated enterprise administration or global revocation | Static changes need controlled restart; no dynamic registry/revocation |

An issuer proves neither organization membership nor permission. A shared issuer does not make the two audiences or identity namespaces interchangeable. Neither permission grants clinical-source access. The APIs return only ten minimized contract fields; issuer, external subject and provider stay internal. Correlation is a request UUID, not global identity propagation.

## Validation architecture and planned evidence

One test-owned Keycloak, one owned Python child and one owned Java child, both ready before token acquisition. Separate loopback ports, configuration, binding, policy and audit/application stores. Python explicitly uses TASK 004 SQLite; Java retains static policy. The runner reuses TASK 002 ownership/digest/cleanup and TASK 003–005 launch/CLI mechanisms, not their sequential orchestration. No equivalent simultaneous runner existed in `infra/iam-lab/` at inventory time.

Real Client Credentials tokens will be used unchanged, with independent signature/issuer/audience and expiry checks before and after relevant HTTP responses. Same-token audience pairs and Python revoke/restore are recorded as such only while still valid. Expiry during a non-expiry control is inconclusive, not a successful audience/policy denial. Retry must identify a fresh issuance and repeat the affected sequence. The provider's 30-second lifetime is not extended.

Java no-permission/unknown-binding under a correct Java audience and JWT role/group escalation have existing signed deterministic tests; these must not be mislabeled as new live controls when the unmodified fixture cannot emit an additional Java-audience workload. Live Python permission revocation and Java organization denial supplement, not replace, those distinctions. Mandatory audit failure and provider/cache outages use deterministic evidence, not forced live outages.

## Executive result and original objectives

**Foundation implemented; laboratory validation completed within the declared scope; production-ready: no.** TASK 006 is functionally accepted for laboratory scope; formal EPIC closure still requires a separate Product Owner decision. Its controlled six-file staging/commit/push/PR is authorized after verification, not merge or another TASK/EPIC. No product source, dependency, historical migration, clinical protocol, Keycloak fixture or legacy filter changed.

The original objectives were provider-independent identity semantics, separate authentication/binding/membership/resource authorization, exact API audiences and token purposes, internal minimized contexts, mandatory audit and incremental adoption without disrupting clinical/workflow authority. These foundations now exist at the two opt-in technical workload routes. Human product OIDC, source authorization and enterprise IAM were not implemented by those workload increments.

| Task | Delivered foundation / evidence |
|---|---|
| 001 | Approved ADR-096, provider/PrincipalContext contracts, migration boundaries; documentary evidence, not runtime |
| 002 | Owned digest-pinned Keycloak fixture, independent audiences, Client Credentials; historical real browser Code/PKCE and ID-token rejection in fixture run `f343e3f085274c9a941c9a5b65768f67`, not product login |
| 003 | Opt-in Python verifier/context/audit; historical selected 205 tests and eight product live controls |
| 004 | Python opt-in SQLite registry, atomic change audit, fresh local policy/revocation; historical 268 selected tests and thirteen same-token live controls |
| 005 | Independent static Java boundary; integrated PR #107 including approved NumericDate correction, 161 selected tests and historical post-fix live run `cf486f677c16e89420b6b52ed1d312a5` (20 controls) |
| 006 | Simultaneous cross-service harness and regression/closure evidence below; Functionally accepted for laboratory scope; controlled PR integration and formal EPIC closure pending |

The final laboratory architecture is one approved issuer feeding two independent receiving boundaries, not Python calling Java with a newly integrated OAuth client:

```text
Owned Keycloak: exact approved issuer
  -> AI-audience workload -> Python technical IAM -> own registry + own access audit
  -> Java-audience workload -> Java technical IAM -> static policy + own access audit
```

The registry change audit is inside Python's registry transaction. The two access audits are not consolidated, do not share identity instances, and have no distributed transaction or global end-to-end correlation guarantee.

## Actual simultaneous execution

Run **`19308f79c295c95b15115024753026ab`** completed **29/29 HTTP controls**, with no inconclusive result or token reissuance. Both children were ready before issuance. One fresh unchanged Client Credentials token was issued per client:

| In-memory issuance reference | Client / actual sole audience |
|---|---|
| 1 | `lab-ai-workload` / `healthcare-ai-api` |
| 2 | `lab-python-to-java` / `healthcare-interop-api` |
| 3 | `lab-unregistered-workload` / `healthcare-ai-api` |

Issuance references are runner counters, not JWTs, JWT ids or token hashes. Signatures/issuer/audiences were independently checked. Every non-expiry token control passed actual expiry checks before and after its response. Original AI/Java tokens were then allowed to expire naturally and rejected with audited `token_expired`, not mutated or treated as policy failures. The realm's 30-second lifetime, clients, scopes and roles were unchanged. No password grant, browser login or token refresh occurred.

Python listened on `127.0.0.1:18402`, Java on `127.0.0.1:18403`; issuer was exactly `http://localhost:18090/realms/healthcare-iam-lab`. HTTP loopback is the explicit lab exception, not an alias rewrite/TLS disablement. The existing image tag/digest in the fixture was unchanged. Java used its own static trust file; Python used empty static bindings plus explicitly initialized own SQLite registry. Separate working directories and stores prevented reuse of preexisting product data. Existing launchers drop inherited credentials/proxies/JVM options; no `.env` is adopted in the run directories.

All rows below are PASS. **L** means integration HTTP with an unchanged real Keycloak token. **H** means actual HTTP with missing/malformed credentials, not synthetic-token or provider-issuance evidence. These 29 requests are distinct from the 25 requirement rows below.

| Service | Control | Expected = observed | Evidence |
|---|---|---|---|
| Python | AI own audience | 200 | L, issuance 1 |
| Java | Same AI token, wrong audience | 401 | L, same issuance 1; `audience_rejected` |
| Java | Java own audience | 200 | L, issuance 2 |
| Python | Same Java token, wrong audience | 401 | L, same issuance 2; `audience_rejected` |
| Python | Unregistered valid AI workload | 401 | L, issuance 3; `binding_unknown` |
| Python | Missing credential | 401 | H |
| Python | Malformed Authorization | 401 | H |
| Python | Bearer plus service token | 401 | L; credential conflict |
| Python | Bearer plus cookie | 401 | L; credential conflict |
| Python | Organization B without membership | 403 | L; organization rejected |
| Python | Existing internal route rejects Bearer | 401 | L; no clinical client call |
| Java | Missing credential | 401 | H |
| Java | Malformed Authorization | 401 | H |
| Java | Bearer plus service token | 401 | L; credential conflict |
| Java | Bearer plus cookie | 401 | L; credential conflict |
| Java | Organization A without membership | 403 | L; organization rejected |
| Java | Model Boundary rejects Bearer | 401 | L |
| Java | Clinical Read rejects Bearer | 401 | L; no HAPI read |
| Java | Federation rejects Bearer | 401 | L; no connector |
| Java | Exchange rejects Bearer | 401 | L; no order |
| Python | Before local revocation | 200 | L, original issuance 1 |
| Python | Permission revoked | 403 | L, same unexpired issuance 1; policy rejected |
| Java | During Python revocation | 200 | L, own issuance 2; unchanged static policy |
| Python | Only Java-named permission enabled | 403 | L, issuance 1; no Python permission inheritance |
| Python | Local grant cannot override wrong audience | 401 | L, issuance 2; audience rejected before local policy |
| Python | Explicit Python permission restoration | 200 | L, same unexpired issuance 1 |
| Java | After Python restoration | 200 | L, own issuance 2 |
| Python | Original AI token actually expired | 401 | L; audited token expiry |
| Java | Original Java token actually expired | 401 | L; audited token expiry |

Revocation/restoration used only the existing explicit offline CLI and recorded unverified synthetic operator labels. Revision 7 contains initialization plus six explicit grant/revoke operations, including setup/final removal of the temporary Java-named Python grant. The required Python permission was restored. Java's config hash was unchanged and Java was not restarted. This proves local policy isolation, not Java dynamic revocation or enterprise-wide propagation. Same-token sequences retry as a whole on expiry; the offline tests verify bounded reissuance and INCONCLUSIVE classification, but that retry was not needed live.

## Audit and minimization evidence

Python persisted **14 access decisions: 3 allowed / 11 denied**; Java persisted **10: 3 allowed / 7 denied**. Five rejected legacy requests correctly do not fabricate IAM audit events. Each IAM response was matched to exactly one independently reopened audit row using its non-sensitive request UUID. Expected audience/policy/expiry reasons were checked, preventing an expired token from masquerading as a wrong-audience/policy rejection. Denials remained anonymous with null principal/organization. Successful contexts had exactly ten allowed projection fields and locally defined identity/organization/permission; their expiry did not exceed the signed token expiry.

Both internal contexts implement PrincipalContext v1 and are request-local/immutable; the HTTP projection deliberately excludes provider id, exact external issuer and subject. `authenticated_at` is technical validation time, not fresh human presence. Access rows record UTC decision time/outcome/reason, not full context, external subject, token, authentication/expiry context fields or arbitrary metadata. Registry revisions/change records are independent of access-audit appends. An allowed row is a decision, not guaranteed delivery if expiry occurs before projection.

Live audit visibility after a response supports persistence, but does not alone prove ordering before delivery: source inspection and deterministic mandatory-write-failure tests provide that guarantee. No live audit-storage or provider outage was injected. Java's fixed unavailable-sink diagnostic is not a fabricated durable failure event. SQLite remains local single-writer laboratory persistence, without tamper evidence, application encryption, automated retention/SIEM or distributed atomicity. Correlation is per request; no authorization or global actor chain is inferred.

Owned Java/Python logs were checked for full JWTs, actual client secrets, provider-issuer URLs and generated-password disclosure. No raw response, Authorization header, signing private key, token hash or clinical payload is recorded by the new runner. Only fixture lifecycle creates the established ignored ephemeral bootstrap/client/import files; cleanup removes them. Resource/configuration manifests and the trusted registry necessarily contain synthetic registration identifiers, not operational tokens. They remain ignored, not a production secret-management solution.

## Current deterministic and compatibility validation

- **Java 161/161 selected**, no failures/errors/skips: 96 IAM (including six NumericDate regressions and real-container HEAD/path/filter tests) + 65 legacy regressions. Compile/package passed. Unit FHIR contexts do not contact HAPI.
- **Python 268/268 selected**: 69 OIDC + 63 registry + 136 service/development auth, Human Review session/HMAC/Origin, audit, clinical-client doubles, federated mode and deterministic LangGraph regressions.
- **IAM fixture/harness 115/115**, including 26 new offline tests for projection/minimization, exact audiences/profile/lifetime, token-safe evidence, expiry/reissuance, child failure, route restrictions and cleanup on failure. No offline test starts Docker or product processes.
- Dependency checks pass in both Python virtual environments. Existing Mockito/Byte Buddy/JVM-agent and Starlette/AnyIO deprecation warnings remain; no dependency was added or changed.
- Neither language's full suite was run. HAPI/live-provider/clinical/Testcontainers suites were not selected. The three known Python CRLF migration-hash failures are outside this selection, unchanged and not hidden by editing their migration. Restricted preexisting ACL directories were not repaired.

Java mandatory audit write lock/foreign schema, expiry after audit, provider outage/hard TTL, removed keys, concurrency, invalid configuration and scoped filter registration pass through the existing IAM suites. Python corresponding crypto/cache/provider/storage/registry tests pass without disabling verification. An unknown key with successfully fetched valid trust yields 401; unavailable required trust/initial or hard-expired keys yields 503. Known validated cached keys can survive a transport outage only within hard TTL. Invalid trust never creates anonymous or legacy fallback. Python static disabled-state 403 versus SQLite/Java 401 is a preserved contract difference.

## Requirement → implementation → test → evidence → status

Statuses apply to the stated scope: PASS, PARTIAL, BLOCKED, NOT IMPLEMENTED, NOT APPLICABLE. A deterministic PASS is not a live control. **L/H** refer to the actual run above; **D** to currently re-executed deterministic suites; **C** to contractual/source review; **historical L** to the identified earlier run.

| Requirement | Implementation | Test / evidence | Status |
|---|---|---|---|
| 1 AI token accepted by Python | Python boundary/registry | L `AI_own_audience` 200 | PASS |
| 2 Same AI token rejected by Java | Java audience validator | L `same_AI_cross_audience` 401 | PASS |
| 3 Java token accepted by Java | Java verifier/static binding | L `Java_own_audience` 200 | PASS |
| 4 Same Java token rejected by Python | Python verifier | L `same_Java_cross_audience` 401 | PASS |
| 5 Missing token rejected | Both credential gates | H `missing_credential`, both 401 | PASS |
| 6 Malformed header rejected | Both credential gates | H `malformed_credential`, both 401 | PASS |
| 7 Contradictory credentials rejected | Both credential gates | L service-token/cookie conflicts, both 401 | PASS |
| 8 Unregistered valid workload rejected | Local exact bindings | Current L Python 401; Java D `invalidTokensDenyWithoutContext`, historical L TASK 005 empty local binding; no new Java-audience unbound client available | PARTIAL |
| 9 Actual expiry rejected | Both temporal validators | L original AI/Java tokens after expiry, 401 | PASS |
| 10 Workload without local permission | Local route policies | Current L Python 403; Java D `trustedLocalPolicyCannotBeExpandedByClaims` permission vector, historical L TASK 005 no-grant 403 | PASS |
| 11 Python permission cannot authorize Java | Java-only permission namespace | D Java permission vector with correct Java-audience synthetic token; C contract. Current cross-audience 401 is not presented as proof of this independent permission check | PASS |
| 12 Java permission cannot authorize Python | Python registry grant resolver | L `Java_permission_is_not_Python_permission` 403 | PASS |
| 13 AI organization not automatic Java membership | Fixed trusted memberships | L Java rejects A; Python rejects B, both 403 | PASS |
| 14 JWT roles/groups cannot add grants | Local-only grant computation | D Python `test_claims_cannot_grant_permissions_or_select_organization` and registry malicious-claims test; Java `trustedLocalPolicyCannotBeExpandedByClaims` | PASS |
| 15 Local grants cannot override wrong audience | Crypto before local policy | L wrong-audience Java token at Python with Java-named grant, 401; Java D closed configuration/audience vectors | PASS |
| 16 Python PrincipalContext v1 | Frozen internal dataclass | L exact minimized projection + D OIDC/registry conformance, C internal fields | PASS |
| 17 Java PrincipalContext v1 | Immutable internal record | L exact minimized projection + D IAM conformance, C internal fields | PASS |
| 18 No external subject/issuer/token/secret in response | Explicit projections/generic errors | L exact ten-field projections; D sanitized denials; C error paths | PASS |
| 19 Identity minimization | Both projections | L exact field/identity/permission checks; D harness disclosure vectors | PASS |
| 20 Context expiry bounded by token | Both context/last-response checks | L original exp checked pre/post; D late-audit expiry suppression and harness expiry vectors | PASS |
| 21 Python durable own access audit | WorkloadAudit | L 14 independently read events; D SQLite persistence | PASS |
| 22 Java durable own access audit | JavaOidcAudit | L 10 independently read events; D SQLite persistence | PASS |
| 23 Audit before authorized response | Boundary append gates | D actual write-lock/failure suppresses projection; C control flow; L row visible after response, not a standalone temporal proof | PASS |
| 24 No clinical/JWT/secret logging | Closed schemas/minimized evidence | C schema/record producers; L owned log scan and separate audit summaries; no clinical acquisition | PASS |
| 25 Mandatory audit unavailable denies | Both fail-closed boundaries | D Python storage/lock/registry tests; Java `mandatoryAuditWriteLockSuppressesContext`/foreign schema. Not live injected | PASS |
| Python revocation / Java isolation | Fresh Python snapshots/static Java | L same original token 200→403→200; independent Java remains 200, config unchanged | PASS |
| Provider/JWKS unavailable, unknown kid, hard TTL, unapproved trust | Existing bounded caches/configuration | D both IAM suites; no shared-provider shutdown | PASS |
| Legacy compatibility | Existing service/session/filter/domain code | Five L Bearer denials + D selected regression suites; no productive source changes | PASS |
| New live Java unbound/no-grant and live role-injection/storage outage | Not claimed by this runner | Existing D/historical L above; current live coverage deliberately narrower | PARTIAL |
| Product human OIDC, enterprise directory/admin, distributed revocation, SaaS/clinical OIDC | No authorized implementation | C non-goals | NOT IMPLEMENTED |
| Real clinical E2E / legacy HAPI compatibility in TASK 006 | Outside IAM technical harness | Pending separate owned-HAPI validation, not an IAM regression run | NOT APPLICABLE |
| Formal laboratory EPIC closure | Product Owner decision | This document is evidence/proposal, not approval | PARTIAL |

## Infrastructure and integrity

Exactly one owned Keycloak container/volume/network set was removed, and both recorded child processes exited. Ports 18402/18403 and Keycloak's listener closed; no orphan child remained. Baseline and final resource IDs matched exactly: **15 containers / 36 volumes / 8 networks**. Bootstrap/client/import/login secret files were removed. The image cache remains intentionally. No global cleanup, force, HAPI inspection/API/lifecycle, Mini HIS/LIS, LLM or cloud operation occurred.

Sanitized evidence is retained only under ignored `.runtime/19308f79c295c95b15115024753026ab/`: `cross-service-evidence.json`, `cross-service-cleanup.json`, separate access audits and registry. No failure report was produced for this successful attempt. The eight foreign files, stash and 556 protected baseline file hashes are checked separately before handoff. Git state is not permanent context; The Product Owner authorized controlled six-file publication by PR; verify actual branch/commit/PR state each session rather than treating it as permanent context.

## Reproduction commands

From repository root, after verifying ownership/prerequisites; never use unrestricted suites to satisfy this task:

```powershell
mvn -q -f services/fhir-integration-service/pom.xml "-Dtest=JavaOidcBoundaryTest,JavaOidcKeysTest,JavaOidcDisabledStartupTest,JavaOidcHttpMethodsTest,ModelBoundaryServiceAuthFilterTest,ModelBoundaryServiceAuthUnconfiguredTest,ModelBoundaryContractControllerTest,ModelBoundaryHttpStatusesTest,ClinicalReadControllerTest,ClinicalReadAuthUnconfiguredTest,ClinicalReadServiceTest,FederationSecurityConfigurationTest,FederationSecurityAuditTest,FederationServiceTest,ExchangeServiceTest,Hl7ExchangeCodecTest" test
mvn -q -f services/fhir-integration-service/pom.xml -DskipTests package
& .\infra\iam-lab\.venv\Scripts\python.exe -B -m pytest -p no:cacheprovider --basetemp infra/iam-lab/.runtime/task006-offline-tests infra/iam-lab/tests -q
& .\infra\iam-lab\.venv\Scripts\python.exe -B infra/iam-lab/verify_cross_service_identity.py
```

Python regression from `services/ai-service`, with bytecode disabled:

```powershell
$env:PYTHONDONTWRITEBYTECODE='1'
& .\.venv\Scripts\python.exe -B -m pytest -p no:cacheprovider --basetemp .tmp-e2e-demo/task006-regression tests/test_oidc_workload.py tests/test_trusted_identity_registry.py tests/test_service_auth.py tests/test_human_development_auth.py tests/test_human_review_session_gate.py tests/test_security_audit.py tests/test_human_review_security_audit.py tests/test_workflow_security_audit.py tests/test_clinical_read_client.py tests/test_clinical_federation_client.py tests/test_federated_langgraph_mode.py tests/test_langgraph_workflow_orchestration.py -q
```

Preparation additionally used Git status/branch/fetch/rev-parse/merge-base/stash, safe branch creation from `origin/main`, protected SHA-256 snapshots and Docker local-context/info preflight. Final validation checks Git diff/empty staging, relative paths, source AST/secret patterns and read-only SQLite evidence. Both virtual environments passed `pip check`. The initial unprivileged Docker preflight was sandbox-denied; approved execution confirmed a local Linux engine. The inherited Git warning for the restricted `.pytest-tmp` directory is reported without changing its ACL. No new dependency/install, product code correction or fixture-contract modification was required.

## Controlled integration review

The Product Owner accepted the reported laboratory implementation/evidence and authorized a six-file commit/push/PR, without merge, new functionality or formal EPIC closure. The pre-commit review re-executed **115/115 offline fixture/harness tests**, Python AST checks, local Markdown paths, SQL/JSON, bounded secret-pattern and protected-file/stash checks. No product code or harness behavior changed. The 161 Java, 268 Python and 29 real HTTP controls remain the identified earlier execution, **not a repetition during Git integration**. No Docker/Keycloak/HAPI or product service was started for this review. Publication state must be checked in Git/GitHub; this document does not predeclare a successful PR or merge.

## Residual risks, debt and future EPIC readiness

| Category | Pending work; not implemented by TASK 006 |
|---|---|
| Laboratory limitations | HTTP loopback/dev-file Keycloak, host-owned ephemeral secrets, local SQLite/single writer, static Java policy/restart, no distributed policy/audit transaction or automated retention |
| Technical debt / independent validation | Exchange `getHeader`/trim; legacy Clinical Read/HAPI live compatibility; historical CRLF hash failures; restricted ACL test directories; existing deprecation/agent warnings |
| Enterprise identity capabilities | Enterprise identity registry, authenticated corporate administration, corporate human OIDC/session adoption, distributed revocation and safe inter-service identity/actor propagation |
| Production deployment controls | Approved HTTPS OIDC/network deployment, enterprise secret management, IAM HA, operational key/credential rotation/recovery, durable tamper-evident retention/monitoring |
| Resource authorization | SaaS data/storage isolation, clinical-endpoint OIDC migration with object/source/case authorization; successful technical login is not clinical access |
| Future integrations | Azure/AWS credentials and resource permissions; enterprise connectors; MCP registration/per-tool grants, validation, execution audit and sensitive-action review |

The foundation supports proposing those later EPICs through explicit contracts, threat models and bounded tasks. It does not authorize starting them, implementing productive Python→Java OAuth, treating a product token as a cloud credential, or claiming regulatory compliance. Following functional laboratory acceptance, recommend controlled PR integration with the declared partial live coverage preserved, then a separate Product Owner decision on laboratory EPIC closure. **Do not declare formal closure before that approval.**

## References

- [PrincipalContext v1](../contracts/identity-principal-context-v1.md), [provider integration](../contracts/oidc-provider-integration-v1.md), [original design](identity-access-foundation-v1.md).
- [Keycloak fixture](identity-keycloak-lab-v1.md), [Python boundary](python-oidc-resource-server-v1.md), [registry](trusted-identity-registry-v1.md), [Java boundary](java-oidc-resource-server-v1.md).
- [Python workload](../contracts/python-oidc-workload-v1.md), [Java workload](../contracts/java-oidc-workload-v1.md), [registry contract](../contracts/trusted-identity-registry-v1.md).
- [Python audit](../contracts/oidc-workload-security-audit-v1.md), [Java audit](../contracts/java-oidc-security-audit-v1.md).
