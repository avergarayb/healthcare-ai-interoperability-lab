# Java OIDC Resource Server Foundation — TASK 005

Implementation and operational evidence approved by the Product Owner for laboratory scope, including the final-review NumericDate correction and its revalidation. The Product Owner authorized final integrity checks and commit/push of exactly the 24 TASK 005 paths; no additional functional change, PR, merge or TASK 006 is authorized. TASK 004 is integrated via PR #106; verify Git references on every session. [ADR-096](../adr/ADR-096-identity-provider-agnostic-v1.md), the [Java workload contract](../contracts/java-oidc-workload-v1.md) and [additive audit](../contracts/java-oidc-security-audit-v1.md) define this laboratory increment, not clinical OIDC adoption or enterprise IAM.

## Existing boundaries and isolation decision

| Existing boundary | Servlet filter / policy retained |
|---|---|
| `/api/clinical-read/v1/*`, `/api/interop/v1/*` | `ClinicalReadServiceAuthFilter`, exact single `X-Service-Token`, 401 |
| GET `/api/model-boundary/v1` | `ModelBoundaryServiceAuthFilter`, exact single service credential, 401 |
| `/api/clinical-federation/v1/*` | Independent participant-token filter, exact single header; authentication denial audited; 503 if mandatory Federation audit fails; domain source/caller grants remain separate |
| `/api/exchange/v1/*` | Independent participant filter with `getHeader` and `trim`; this known hardening gap remains unchanged, not corrected by IAM |
| Actuator liveness | Existing nonclinical startup endpoint; no IdP prerequisite |

All four existing registrations use `HIGHEST_PRECEDENCE`; previously no Spring `SecurityFilterChain` or Spring Security dependency existed. There is no conflicting IAM route or OpenAPI generator. The default Clinical Read source and `application.yml` remain unchanged.

Effective platform: Java 21, Spring Boot **3.5.16**. Direct Boot-managed modules `spring-security-oauth2-resource-server` and `spring-security-oauth2-jose` resolve Spring Security **6.5.11**, Nimbus **9.37.4**. No Boot/JDK/other manifest upgrade, global starter, `spring-security-config`, shared user directory or new service. The two modules expose recognized decoder/provider/web-chain components without installing `@EnableWebSecurity`.

The opt-in `DefaultSecurityFilterChain` has an exact GET/path matcher; its `FilterChainProxy` is registered only at IAM's URI with order `HIGHEST_PRECEDENCE + 10`. It cannot replace or bypass legacy registrations. No `springSecurityFilterChain` global bean, automatic username/password account, global permit-all, HTTP Basic/form login or scope-derived permission is introduced. A later dependency that adds Spring Security config/auto-enablement must be treated as a separate isolation change, not a harmless transitive update.

Official implementation references: [Boot 3.5 security defaults](https://docs.spring.io/spring-boot/3.5/reference/web/spring-security.html), [Boot 3.5.16 conditional web-security source](https://github.com/spring-projects/spring-boot/blob/v3.5.16/spring-boot-project/spring-boot-autoconfigure/src/main/java/org/springframework/boot/autoconfigure/security/servlet/SpringBootWebSecurityConfiguration.java), and [Spring Resource Server JWT](https://docs.spring.io/spring-security/reference/6.5/servlet/oauth2/resource-server/jwt.html). Local transport/cache/profile/binding rules below are explicit laboratory policy, not assumptions about those defaults.

## Components and authority

All new Java modules live in `lab.healthcare.fhir.iam`:

- `JavaOidcTrust`: strict immutable bounded local registration and named Keycloak profile.
- `BoundedOidcKeys`: approved HTTP discovery/JWKS only, deadlines/body cap, coalesced refresh and hard lifetime; Nimbus public-key conversion.
- `JavaWorkloadVerifier`: strict envelope/profile, `NimbusJwtDecoder`, `JwtAuthenticationProvider`, explicit `OAuth2TokenValidator`; no manual cryptography or automatic `SCOPE_*` grants.
- `JavaPrincipalContext`: immutable internal identity, explicit minimized projection, redacted string representation.
- `JavaOidcAudit`: separate schema/version/closed vocabulary and mandatory durable local append.
- `JavaOidcBoundary`: exact credential policy, static local binding/membership/permission and audited response gate.
- `JavaOidcConfiguration` / `JavaOidcController`: conditional scoped chain/mapping; no clinical integration imports.

Provider trust, cryptographic token validity, local identity, organization membership, Java route authorization and audit are separate. Neither a Keycloak role nor a Python permission is a Java grant. Clinical-source authorization and Federation participant authentication are unchanged and are not implied by obtaining this technical context.

## Operation

Adapt [the disabled example](../../services/fhir-integration-service/java-oidc-workload.example.json) into an approved local file with no credentials. Initial Java registration binds `lab-python-to-java` / synthetic service-account subject 202 to `fixture-python-to-java`, `org-lab-b`, permission `iam.java-workload-context.read`. No provider is trusted by default.

```powershell
$env:IAM_JAVA_WORKLOAD_LAB_ENABLED='true'
$env:IAM_JAVA_WORKLOAD_TRUST_CONFIG_PATH='ABSOLUTE_APPROVED_JAVA_JSON'
$env:IAM_JAVA_WORKLOAD_AUDIT_DB_PATH='ABSOLUTE_DEDICATED_AUDIT_SQLITE'
# Start only an explicitly owned laboratory process; no secrets in command arguments.
```

An enabled but incomplete boundary returns 503, not static/legacy fallback. Startup performs no discovery/JWKS. Default disabled mode has no new mapping/filter/IAM file or provider initialization. Static bindings and grants require controlled Java restart for changes; Java neither reads TASK 004's dynamic SQLite policy nor shares a base with Python.

Use the existing [Keycloak fixture](identity-keycloak-lab-v1.md) only through explicit owned lifecycle. Canonical issuer remains unchanged, actual Interop audience is required, and plain JWT type is not presented as RFC 9068 conformance. One fixed organization per binding; candidate headers cannot create membership or union grants. Multi-organization Java resolution, provider onboarding, dynamic policy/revocation and migration of current endpoints require later authorized work.

## Deterministic validation

New suites: `JavaOidcBoundaryTest`, `JavaOidcKeysTest`, `JavaOidcDisabledStartupTest` and `JavaOidcHttpMethodsTest` (the latter is a separate package-private class in the disabled-startup test source file); test support generates RSA keys in memory using Nimbus and signs synthetic vectors. No operational token/private key is persisted. Tests cover credential/header conflicts; signature, algorithm, issuer, audience, purpose and temporal rejection; exact binding/membership/local permission; no claim elevation; cache coalescing, rotation/removal, hard expiry and provider outages; bounded actual loopback HTTP, redirects and malformed metadata; mandatory SQLite lock/foreign-schema failure and sanitized response.

The full disabled-startup test isolates exchange/Federation stores and verifies real liveness, absent mapping/route/global security/user-account beans and all four legacy anonymous gates. Its test-only JDBC auto-configuration exclusion matches existing Federation tests: Mini LIS contributes JDBC on the **test** classpath, not the packaged product runtime. No datasource or HAPI is started to satisfy it. A separate live check starts the actual jar with IAM disabled and no Keycloak, without that test-only exclusion.

Selected Maven command from repository root:

```powershell
mvn -f services/fhir-integration-service/pom.xml "-Dtest=JavaOidcBoundaryTest,JavaOidcKeysTest,JavaOidcDisabledStartupTest,JavaOidcHttpMethodsTest,ModelBoundaryServiceAuthFilterTest,ModelBoundaryServiceAuthUnconfiguredTest,ModelBoundaryContractControllerTest,ModelBoundaryHttpStatusesTest,ClinicalReadControllerTest,ClinicalReadAuthUnconfiguredTest,ClinicalReadServiceTest,FederationSecurityConfigurationTest,FederationSecurityAuditTest,FederationServiceTest,ExchangeServiceTest,Hl7ExchangeCodecTest" test
mvn -f services/fhir-integration-service/pom.xml -DskipTests package
```

No unrestricted suite, `LocalHapiModelBoundaryTest`, legacy HAPI live or Testcontainers/clinical flow is invoked by this selection. Unit FHIR contexts are not live HAPI requests. Existing Mockito/Byte Buddy dynamic-agent warnings remain separate from test failures. Dependencies are resolved through the existing Boot management; no production SCA/certification claim is made.

## Explicit live verification

```powershell
& .\infra\iam-lab\.venv\Scripts\python.exe -B infra/iam-lab/verify_java_resource_server.py
```

The runner requires a current packaged jar, local Docker and free dedicated ports 18396–18399. It inventories Docker and uses only the fixture's verified owner/run/workspace/project resources. No inherited application credentials/proxies/JVM options or `.env` is adopted. It starts only recorded own Java children, with separate ignored exchange/Federation/OIDC stores and warning-level logs. No Python product service, human login/password grant, HAPI, Mini HIS/LIS or LLM is started/called.

First, while Keycloak is absent, the disabled jar must return liveness 200, IAM 404 and four legacy 401s. Next an owned Keycloak and enabled Java are started: real `lab-python-to-java` token 200, actual AI token 401, missing/malformed/duplicate/conflicting credentials 401, old endpoints still reject Bearer, and the original actual Java token after real expiry returns 401. Separate own Java processes demonstrate valid token without local permission 403 and valid Java-audience token without local binding 401. Static policy changes deliberately restart only own Java processes, not Keycloak; this is not immediate dynamic revocation.

The fixture's intentionally unregistered workload emits **AI audience only**. It cannot prove Java binding rejection because audience rejection comes first. Without changing the fixture, the live binding control therefore uses a real `lab-python-to-java` Interop token against an isolated Java registration whose bindings are explicitly empty. Unknown client/subject under Java audience also has signed synthetic test coverage. These categories are not conflated.

Expected evidence is ten OIDC access decisions plus separate startup/legacy checks. API ID-token rejection here remains synthetic; prior interactive human-token evidence belongs to TASK 002. Audit-outage fail-closed is deterministic SQLite evidence, not live fault injection. Expired-token rejection uses actual expiry, not a mutated live claim. Tokens remain in memory; only sanitized case/status/audit summaries are retained.

Cleanup stops only recorded Java children and verifies closed listeners, then removes only verified own Keycloak container/volume/network and ephemeral credentials/imports. Exact original Docker ID inventories must match after cleanup; no HAPI inspection/lifecycle/API operation is used as proof. Minimized local configuration/audit/evidence and own incidental application stores remain ignored for review; they are not production retention, encryption or OS-user isolation.

## Executed results

The original implementation's selected Java execution passed **139/139**, zero failures/errors/skips: **74 new IAM tests** (44 boundary, 29 keys/config/transport, 1 full disabled-startup) plus **65 unchanged focal regressions** from the existing suites in the command above. Its separately executed IAM fixture/harness suite passed **89/89**, including four new runner-safety cases. Compilation, packaging, dependency-tree inspection and JSON/SQL/Python-AST checks passed. At that original implementation stage, the packaged IAM classes and audit SQL matched the build/source, and no productive Java logic changed after its successful live run; six additional boundary assertions were added and passed afterward. The later final-review correction/results are recorded separately below, not attributed retroactively to this original run.

Development failures are retained honestly: one new test helper initially used an invalid Java String overload; the new full-context test initially needed the existing test-only JDBC exclusion, then an explicit MVC mapping qualifier because Actuator adds another handler mapping. These were corrected without modifying legacy tests or application configuration. The initial runner also hit an `http` name collision while preparing duplicate headers; it was fixed with an unambiguous module alias, explicit connection closing and four offline regression cases. None of those failed attempts is counted as a successful full validation. A sandbox Maven repository-path denial was resolved by approved normal Maven execution, not repository/ACL changes.

### Operational execution

Successful run **`a2b4f57d81f2e2706933e617dec794b8`** passed **20/20 checks**, distinguished as follows:

| Category | Checks / observed result |
|---|---|
| Actual packaged Java, Keycloak absent | 6: liveness 200, IAM mapping absent/404, Model Boundary/Clinical Read/Federation/Exchange anonymous gates 401 |
| Actual Keycloak tokens at IAM | 10: registered Java workload 200; AI audience 401; missing 401; contradictory legacy credential 401; cookie conflict 401; malformed 401; duplicate Authorization 401; original token after actual expiry 401; valid Java workload without Java grant 403; valid Java-audience token without local binding 401 |
| Existing endpoints with real provider Bearer | 4: Model Boundary/Clinical Read/Federation/Exchange remain 401; no clinical operation executed |

Ten minimized persistent OIDC events were verified across the owned Java process restarts: **1 allowed, 9 denied**. The closed reasons match access granted, audience rejected, unknown binding, ambiguous/malformed/missing/conflicting credentials, actual expiry and policy denial. Denials remain anonymous with null internal identity/organization. The unknown-binding control uses the actual `lab-python-to-java` Interop token with an explicitly empty local registration, not an AI-audience token relabeled as a binding check. The no-grant control likewise changes only local Java configuration. Keycloak realm, audiences, 30-second token lifetime and fixture source were unchanged.

Failed/partial run **`dfeaa37f3ae106111dd3681d6d431fae`** completed six provider-absent and six initial OIDC controls before the runner-name error; it has a failure report, not a completed matrix report. Both that run and the successful repetition stopped their own Java children and removed their own IAM resources/ephemeral credentials. Total across attempts: **two owned container/volume/network sets cleaned**. Each exact baseline/final inventory is **15 containers / 36 volumes / 8 networks**, with original resource IDs preserved. Ports 18396–18399 had no remaining listener after cleanup; OS TCP TIME_WAIT is not force-cleared. No HAPI HTTP/inspection/lifecycle or Mini HIS/LIS call occurred, and no Python product process was started.

Only sanitized `java-resource-server-evidence.json`, `java-resource-server-failure.json` where applicable, and `java-resource-server-cleanup.json` are used as reports under ignored `.runtime/<run-id>/`. Real tokens stayed in memory; the known ephemeral credential/import files were removed. Own Java logs were checked for tokens, provider URLs and generated-password disclosure. Retained configuration/audit/local application stores are ignored, not production retention or secret management.

The 503 provider path, actual mandatory-audit SQLite write-lock failure, concurrent first append and final expiry suppression are **deterministic** tests. No live provider/storage outage, new human ID token, production readiness, complete Java suite or live HAPI integration is claimed. Mockito/Byte Buddy/JVM agent warnings remain; three historical Python CRLF hash failures are outside this Java selection and their migrations remain byte-for-byte unchanged.

Original implementation checks compared all 453 protected preexisting files (including eight foreign files, historical Python migrations and preexisting Java sources/resources), stash OID, exact own-file scope, Markdown links, secret patterns, SQL/JSON, source/build/jar correspondence and persisted live audit counts. Source was limited to **24 own paths: 4 modified and 20 new**. At that handoff no staging, commit, push, PR, merge, stash/ACL operation, clinical-default change or global Docker cleanup had occurred. Commands included Git status/fetch/ancestry/switch/stash checks, Maven dependency tree/compile/focal tests/package, offline harness pytest, the explicit live runner twice, Docker preflight/owned lifecycle and read-only final validation. The later review and publication authorization are separate below. TASK 006 is not started.

## Final security review — correction approved

### Real HTTP methods, paths and filter registration

The final review added real HTTP requests against a random-port full Spring application context and an owned loopback JWKS test server. This is deterministic signed-synthetic-token coverage, not a Keycloak live run. No clinical operation or HAPI request is made.

| Request | Observed result / protected effect |
|---|---|
| Canonical GET, missing / malformed / valid credential | 401 / 401 / 200; exactly three mandatory audit rows for three requests |
| HEAD, missing / invalid / valid credential | 401 in all cases, empty body, no context or GET audit event; unsupported HEAD, not authenticated HEAD coverage |
| POST / PUT / PATCH / DELETE, missing and valid credential | 405; no protected projection or OIDC event |
| OPTIONS, missing and valid credential | 200, empty body, protocol metadata only; no protected projection or OIDC event |
| Trailing slash / duplicate slash / dot segment / encoded path / matrix parameter, missing and valid credential | 404 / 400 / 400 / 401 / 400 respectively; no protected projection |
| Identity/organization spoofing in query parameters | Missing credential 401; valid credential retains the locally registered identity/organization and produces one event |

Spring MVC implicitly maps HEAD, but the exact GET matcher does not authenticate it; the controller rejects the absent request context before producing a projection. HEAD is deliberately unsupported under this contract. Supporting authenticated HEAD later would require an explicit contract/matcher/audit change, not treating these 401 responses as successful HEAD authentication.

The actual Tomcat registration has one `FilterChainProxy`, the exact IAM URL pattern, order `HIGHEST_PRECEDENCE + 10` and **REQUEST only** dispatching. The internal boundary is not a second container filter/bean. There is one scoped security chain, no global `springSecurityFilterChain`, and no double audit invocation. The disabled context still has no IAM controller/chain and preserves liveness and the four legacy gates. An initial new registration assertion expected ASYNC as well as REQUEST; inspecting the actual container showed REQUEST only, and only that test expectation was corrected. No production registration, matcher, dispatcher or endpoint logic changed during this review.

### Blocking NumericDate finding and bounded correction

Before correction, three correctly signed synthetic JWT vectors were admitted with HTTP **200 instead of 401**: overflowing `iat`/`exp` together, overflowing `nbf`, and overflowing `exp` alone. Local inspection of the resolved Nimbus 9.37.4 `DateUtils.fromSecondsSinceEpoch` confirmed unchecked multiplication of long seconds by 1,000. Validation only after conversion could see wrapped present-time dates instead of the original out-of-range integers. This violates this boundary's temporal/lifetime policy. Reproduction required a valid trusted signature and registered client/subject; it did not forge a signature, provision identity or grant a new permission.

The only production correction in this final review is in `JavaWorkloadVerifier`: reject expired, future, unordered or over-lifetime **original nonnegative integer** NumericDates before library conversion. Ordered nonnegative subtraction avoids overflow. These envelope checks can only reject; accepted tokens still undergo Nimbus signature verification and the existing signed Spring/profile validation. No manual cryptography, claim rewriting, dependency change, audit change or legacy change was introduced. Three direct boundary regressions and three real-container HTTP regressions now return 401; the real HTTP cases also verify exactly one denied audit row each.

### Validation after correction

- Selected Java suites: **161/161**, zero failures/errors/skips: **96 IAM** (47 boundary, 29 keys/config/transport, 1 disabled startup, 19 real-container method/path/registration cases) plus **65 unchanged regressions**. This is not the full Java suite. Compile and package passed after the correction.
- IAM fixture/harness offline suite: **89/89** in this review. JSON, SQL, AST, relative links, bounded secret-pattern checks, source/build/jar correspondence, scope and protected-file checks are separately verified before handoff.
- Actual post-correction packaged-Java/Keycloak repetition **`cf486f677c16e89420b6b52ed1d312a5`**: **20/20** controls (6 provider-absent startup, 10 OIDC, 4 legacy isolation), with the same 200/401/403 matrix described above. This is a new execution, not a relabeling of historical run `a2b4f57d81f2e2706933e617dec794b8`. Ten persistent OIDC decisions: **1 allowed, 9 denied**. Keycloak fixture source/profile was unchanged.
- The new run stopped its own Java children, closed its listeners and removed its own one-container/one-volume/one-network set and ephemeral credentials/imports. Exact preexisting Docker resource IDs were preserved: **15 containers / 36 volumes / 8 networks** before and after. Together with the two historical attempts, three owned resource sets were cleaned. No global cleanup or HAPI operation occurred.
- Mandatory audit failure/503, overflow vectors and API ID-token rejection remain deterministic evidence; no live storage outage or new human OIDC login is claimed. Historical evidence and failed attempts above remain historical.

Publication was held when the blocking defect was reproduced. The Product Owner subsequently reviewed and approved the finding's bounded correction and the 161/161 Java, 89/89 fixture and post-correction 20/20 live evidence. Final integrity/staging checks and commit/push of exactly the 24 TASK 005 paths are now explicitly authorized. Reuse the approved live run when IAM logic is unchanged; do not imply a new Keycloak execution during Git closure. Verify current Git references and actual publication results separately rather than treating a commit SHA or branch state as permanent context. No PR, merge or TASK 006 is authorized.

## Residual limits / TASK 006

Laboratory workload-only static Java policy, local SQLite audit and one named provider profile. No human SSO, clinical identity, clinical OIDC endpoints, shared Java/Python identity database, dynamic/distributed revocation, enterprise IAM/RBAC, SaaS isolation, production secret/network deployment, enterprise connectors or MCP. Existing Exchange `getHeader`/trim behavior is unchanged and remains independently pending. Audit cannot durably record its own unavailable sink; fixed diagnostic plus denied response is not a fabricated persisted event. New TASK 006 scope, implementation or publication requires explicit Product Owner authorization.
