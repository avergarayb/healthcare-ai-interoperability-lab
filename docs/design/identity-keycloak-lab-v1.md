# Identity & Access Foundation V1 — TASK 002: isolated Keycloak lab

## Scope and authority

This opt-in fixture implements laboratory provider evidence under [ADR-096](../adr/ADR-096-identity-provider-agnostic-v1.md), [OIDC provider integration](../contracts/oidc-provider-integration-v1.md) and [Principal Context](../contracts/identity-principal-context-v1.md). It is isolated from both product units. Neither service imports the harness or gains an OIDC middleware, dependency, session, user database, tenant isolation or new authorization method. Keycloak is optional laboratory infrastructure, not a required customer IdP. All identities and grants are synthetic.

## Verified provider and infrastructure

- Image: `quay.io/keycloak/keycloak:26.8.1`.
- Immutable multi-platform index: `sha256:3f3c5f8e03c614774b4bd9173b88391fefa4153bfc010d8012d59ad825377332`.
- Verified Linux amd64 child: `sha256:de6ed510b59cfcd25f129ba4118696fa10d4165eee921a8d846178b6d35d30f7`.
- Selection checked against the [official 26.8.1 release](https://www.keycloak.org/2026/10/keycloak-2681-released), [container guide](https://www.keycloak.org/server/containers), [hostname guide](https://www.keycloak.org/server/hostname) and [import guide](https://www.keycloak.org/server/importExport). Registry verification: `docker buildx imagetools inspect quay.io/keycloak/keycloak:26.8.1 --format '{{json .Manifest}}'`. Compose pins both tag and index digest; startup checks the downloaded RepoDigest and never falls back to a tag.
- Local evidence environment: Docker 29.4.0, Linux x86_64, 4 CPUs, approximately 6 GiB available to the engine; Compose 5.1.2. Keycloak receives a 1 GiB memory limit and 2 CPUs. The official container guide's heap sizing allows non-heap overhead; this small `dev-file` fixture is not production capacity sizing.
- Own Compose project `iam-lab-<random-run-id>`, container, named H2/dev-file volume and bridge network. Owner/run/workspace and Compose project labels identify every resource. No fixed container name, external volume or HAPI configuration is reused.
- Only `127.0.0.1:<port>:8080` is published. A dedicated bridge is used: `internal: true` suppressed host publication in this Docker environment, so the initial attempt could not reach discovery and was cleaned as a failed attempt. This network is not an outbound firewall; no corporate providers, SMTP, brokers or external integrations are configured.
- `start-dev --import-realm`, no restart policy, dropped Linux capabilities and `no-new-privileges`. No ordinary build or pytest invocation starts Docker.

## Canonical trust and token profiles

Default origin is `http://localhost:18090`; realm/issuer is `http://localhost:18090/realms/healthcare-iam-lab`. `--port` changes the origin, `KC_HOSTNAME`, discovery and verification together. Browser and host-based Java/Python clients must use this exact issuer. No container alias, issuer rewrite, wildcard issuer, dynamic backchannel or TLS bypass is accepted. HTTP is solely the local loopback laboratory exception; production requires its own approved HTTPS deployment.

Discovery must publish exactly that issuer and its `/protocol/openid-connect/certs`, `/token` and `/auth` endpoints. The HTTP client allows only the configured discovery, JWKS and token endpoints, disables environment proxies and redirects, and bounds responses/timeouts. It cannot discover a provider chosen by token claims. JWKS is loaded once per explicit verification and kept in memory for that run; unknown keys deny without network refresh. Rotation/cache conformance for future product verifiers remains separate work.

The fixture uses PyJWT with cryptography, RS256 and approved public RSA keys of at least 2048 bits. It validates `kid`, signature, exact issuer, audience, expiry, issued-at, not-before when present and required claims. Duplicate JSON claims, token-supplied key URLs, excess audiences, unsupported algorithms and invalid time ranges deny. The fixture's maximum lifetime is 300 seconds, zero clock tolerance; the realm emits 30-second access tokens to make actual expiry observable.

This is a **Keycloak-specific access profile**, not an assumption of RFC 9068 conformance: signed payload `typ=Bearer`, JOSE type `JWT` or `at+jwt`, required `jti` and `azp`, and an exact `(issuer, subject, authorized client, resource audience)` binding. ID tokens use the separate human profile with web-client audience, signed `typ=ID` and transaction nonce; they are not API credentials. Results are immediate fixture decisions, not reusable product PrincipalContexts or sessions.

The login evidence checks the **unchanged real ID token** against both API profiles. API audience validation precedes the access-purpose predicate, so a web-only ID token reports `audience_mismatch`. To prove that purpose is an independent control, the harness also verifies the original token cryptographically under its actual web audience and applies the **same** `typ=Bearer` predicate used by `Trust.access`; it must reject with `access_token_required`. This diagnostic does not accept the web audience for either API, skip cryptography, add an ID-token exception or mutate the token. Missing workload-only claims cannot substitute for these two controls.

## Realm, clients and trusted policy

Versioned sources: [Compose](../../infra/iam-lab/compose.yaml), [sanitized realm](../../infra/iam-lab/realm.json), [policy](../../infra/iam-lab/policy.json), [harness](../../infra/iam-lab/oidc_harness.py), [lifecycle CLI](../../infra/iam-lab/lab.py).

| Client | Flow / effective audience |
|---|---|
| `healthcare-review-web` | Public Authorization Code + mandatory PKCE S256; exact `http://127.0.0.1:18190/callback` by default |
| `healthcare-ai-api` | Bearer-only resource identifier; no login/service-account grant |
| `healthcare-interop-api` | Separate bearer-only resource identifier |
| `lab-ai-workload` | Client Credentials; only `healthcare-ai-api` via default scope `iam-ai` |
| `lab-python-to-java` | Client Credentials; only `healthcare-interop-api` via default scope `iam-interop` |
| `lab-unregistered-workload` | Valid Keycloak client/service account with AI audience, intentionally absent from trusted workload bindings |

All clients disable implicit and password grants, broad scope and optional scopes. Workloads disable browser code flow and have no administrative roles. The human client has no service account. The `basic` scope explicitly emits subject; dedicated audience mappers apply only to access tokens. The resource identifiers alone grant no access. Neither workload may request the other's unassigned audience scope.

One realm serves `org-lab-a` and `org-lab-b`. Application organizations are not equated with Keycloak realms. Policy binds exact synthetic subjects to internal fixture principals:

| Identity | Trusted membership / grant |
|---|---|
| `lab-human-a` | A / `fixture.ai.read` |
| `lab-human-b` | B / `fixture.interop.read` |
| `lab-human-both` | A and B separately; explicit selection required |
| `lab-human-none` | No authorized membership |
| `lab-ai-workload` | A / `fixture.ai.read` |
| `lab-python-to-java` | B / `fixture.interop.read` |

Policy never derives membership or permissions from JWT groups/roles. Selecting an organization cannot create membership, and grants from two memberships cannot be unioned. These are harness policy checks, not evidence of clinical-source or product multi-tenant authorization.

Human fixtures include synthetic first/last names and `@example.invalid` email addresses solely to satisfy the provider's browser user-profile requirements. Email remains unverified, login-by-email remains disabled, and identity binding continues to use the exact issuer/subject, never email. This avoids a mandatory profile-completion screen without disabling the provider's profile validation.

## Prerequisites and secrets

Use Python 3.11+ and a separate virtual environment. Dependencies are pinned in [requirements](../../infra/iam-lab/requirements.txt); neither product dependency manifest/environment is changed. Commands below run from repository root in PowerShell:

```powershell
python -m venv infra/iam-lab/.venv
& .\infra\iam-lab\.venv\Scripts\python.exe -m pip install -r infra/iam-lab/requirements.txt
New-Item -ItemType Directory -Force infra/iam-lab/.runtime | Out-Null
& .\infra\iam-lab\.venv\Scripts\python.exe -B -m pytest -p no:cacheprovider --basetemp infra/iam-lab/.runtime/unit-validation infra/iam-lab/tests -q
```

Each start creates an exclusive random directory below ignored `.runtime/` with an ownership manifest and independent CSPRNG bootstrap, three client and four human passwords. Files are created exclusively; existing files/directories and ACLs are not altered. Windows permissions are inherited: this is not encrypted storage, isolation from other local users or enterprise secret management. Run only in a trusted local workspace; do not use a shared/synchronized directory for runtime secrets.

The versioned realm has no credentials. Its ignored materialized import contains ephemeral credentials solely for the local container. Bootstrap is a Compose file secret read inside the container entrypoint, never a literal Compose environment value/command argument; workload tokens never use it. Tokens remain in harness memory. CLI errors suppress upstream bodies, request forms and raw Docker output; do not publish container logs or dump runtime files. Cleanup deletes the known secret/import/login URL files after verified Docker cleanup; it does not claim forensic secure erasure of host files or deleted volumes. The isolated test suite also creates synthetic secret files in its ignored temporary test directories; those are not operational provider credentials.

## Explicit operation and cleanup

```powershell
# A fresh import, matrix, actual token expiry and automatic owned-resource cleanup:
& .\infra\iam-lab\.venv\Scripts\python.exe -B infra/iam-lab/lab.py run
# Alternative loopback port updates canonical trust coherently:
& .\infra\iam-lab\.venv\Scripts\python.exe -B infra/iam-lab/lab.py run --port 18091
```

`run_id=...` is non-sensitive. `.runtime/<run-id>/evidence.json` records sanitized outcomes and `state.json` records baseline/owned resource identities. An unavailable local Docker engine, occupied port, unexpected ownership or failed verification causes denial, not takeover. The CLI rejects remote Docker contexts. A fresh run uses a new volume; startup refuses to reimport/adopt an existing run or project. Keycloak startup import is never used to overwrite another realm/volume. Failed startup/matrix attempts still clean owned resources.

To retain **only this fixture** temporarily for manual PKCE:

```powershell
& .\infra\iam-lab\.venv\Scripts\python.exe -B infra/iam-lab/lab.py start
# Replace RUN_ID below with the printed id; do not use another execution's manifest.
& .\infra\iam-lab\.venv\Scripts\python.exe -B infra/iam-lab/lab.py verify --run-id RUN_ID
& .\infra\iam-lab\.venv\Scripts\python.exe -B infra/iam-lab/lab.py login --run-id RUN_ID --organization org-lab-a
& .\infra\iam-lab\.venv\Scripts\python.exe -B infra/iam-lab/lab.py stop --run-id RUN_ID
```

For login, open the ignored `login-url.txt` locally in the browser and use `lab-human-a`, reading its password only from `humans` → `lab-human-a` in that run's ignored `secrets.json`. Do not paste passwords, the authorization URL, callback URL or tokens into chat/logs. State, nonce and verifier stay in memory; authorization URL is a temporary private local file, not ordinary output. The five-minute callback binds only `127.0.0.1`, exact Host/path, issuer and state, rejects duplicate callback fields and replay, exchanges the code with the original verifier/redirect and verifies the ID token before trusted policy selection. It writes only sanitized `pkce-evidence.json`, including separate audience and purpose rejection outcomes for both API profiles. No Human Review cookie/session is created. Always execute `stop` in a shell `finally` block when using retained `start`, including callback failure/timeout; after cleanup, a retry needs a fresh instance and credentials.

Cleanup checks full container/network IDs, exact volume identity, all four ownership labels and exclusion from the initial inventory. It refuses occupied volumes/networks and never uses force, prune, global cleanup or name-only matching. It removes only recorded/verified resources; missing own resources are tolerated for idempotent cleanup. Sanitized evidence remains ignored locally. The image cache is retained intentionally; no unrelated image is removed.

## Validation record and limits

Validation performed on 2026-11-02 (America/Lima):

| Verification | Observed result |
|---|---|
| Offline fixture suite, initial implementation | 77 passed; no Docker/network calls |
| Offline fixture suite, interactive follow-up final code | 85 passed; no Docker/network calls |
| Dependency consistency in fixture-only virtual environment | `pip check` passed |
| Fresh live imports on 18091, 18090, then final lifecycle guard on 18090 | Three successes, 15 matrix cases each; same cases repeated, not 45 distinct controls |
| Actual Client Credentials tokens | Three separate service-account tokens per successful run, held only in memory |
| Existing Java security/federation/Clinical Read suites | 48 passed, no Keycloak, HAPI or Testcontainers |
| Existing Python service-auth, development-login and session-gate suites | 54 passed; one existing Starlette/AnyIO deprecation warning |
| Separate product startup without Keycloak | Java liveness 200 and legacy gate 401; Python health 200 and legacy gate 401 |
| Initial implementation Docker cleanup and baseline | Four own container/volume/network sets removed, including the failed initial attempt; original 15 containers, 36 volumes and 8 networks preserved |
| HAPI protection | Docker metadata only: original container IDs, start times and restart counts unchanged; no HAPI HTTP, start, stop or mutation |
| Git/integrity | Eight foreign-file SHA-256 values and stash OID preserved; product code, dependency manifests, historical migrations and HAPI Compose unchanged; no staging/commit/push |

The first attempt used an internal bridge without an actual host publication. During overlapping laboratory attempts, that older process later reached the new test-owned instance on the same canonical port and failed client authentication (`unauthorized_client`); it generated no successful matrix report. The final lifecycle now checks the recorded container's running state, pinned image, declared binding **and actual network publication before any OIDC HTTP**, so an unpublished instance fails immediately. Both attempts were confined to owned infrastructure. Ordinary test builds do not retry or start this infrastructure.

A means unchanged tokens actually emitted by Keycloak; B means mutated/synthetic JWT vectors; C means deterministic trusted policy. A valid provider token plus a fixture-policy decision is labeled A + policy. None proves product OIDC implementation. Each successful 15-case matrix contains nine A, one A + policy, three B and two C checks.

| Case | Evidence classification / intended result |
|---|---|
| AI and Interoperability own audience | A / accepted |
| Both cross-audience directions | A / denied |
| Wrong expected issuer with real signed token | A / denied |
| Unknown workload with actual valid signature | A / denied |
| Unassigned scope in both directions | A / `invalid_scope` |
| Actual expiry after waiting for `exp` | A / denied |
| Organization not authorized for real workload | A + policy / denied |
| Modified signature, algorithm and key id | B / denied |
| ID token used as API token, including synthetic overlapping audience | B / denied; unchanged real ID token also rejected by both API profiles in the interactive follow-up below |
| Missing claims, future time, duplicate claims, key/discovery restrictions | B / denied |
| Ambiguous membership and cross-organization permission union | C / denied |
| Explicit membership selection, no membership, nonce/state/replay | B/C / expected accept or deny |

### Interactive follow-up: real Code + PKCE and ID token

Final successful execution: `f343e3f085274c9a941c9a5b65768f67`, using canonical issuer `http://localhost:18090/realms/healthcare-iam-lab` and exact callback `http://127.0.0.1:18190/callback`. The operator authenticated `lab-human-a` in the real browser and confirmed the callback page. The harness, rather than that confirmation alone, recorded the following in ignored `.runtime/<run-id>/pkce-evidence.json`:

| Operational check | Recorded result |
|---|---|
| Browser Authorization Code + PKCE S256; code exchanged with original verifier/redirect | PASS |
| Exact callback URI/Host, state, issuer and consumed transaction | PASS |
| Real ID token: RS256 signature/JWKS, issuer, web-client audience, nonce, issued-at and expiry | PASS |
| Trusted internal binding and membership | `fixture-human-a`, `org-lab-a`; only synthetic `fixture.ai.read` policy permission |
| Unchanged real ID token under `healthcare-ai-api` profile | DENIED: `audience_mismatch` |
| Unchanged real ID token under `healthcare-interop-api` profile | DENIED: `audience_mismatch` |
| Independent shared access-purpose predicate, after crypto verification under actual web audience | DENIED: `access_token_required` for both API diagnostics |
| Full tokens persisted / Human Review sessions created | false / false |
| New instance's Client Credentials matrix before browser login | 15/15 |
| Cleanup | Both follow-up instances' own container/volume/network sets removed, including the incomplete attempt; credentials/import/authorization URLs removed; sanitized evidence retained |
| Final inventory and integrity | Same 15 preexisting containers, 36 volumes and 8 networks; HAPI IDs/start times/status/restart counts unchanged; ports 18090/18190 released; eight foreign SHA-256 values and stash OID unchanged |

These are A checks on a real Keycloak ID token. It was neither modified nor sent to current product API endpoints. The separate purpose diagnostic is a rejection predicate on cryptographically verified claims, not an API authorization with a relaxed audience. The fixture-only policy permission gives no clinical-source, business or product access. The pre-login `evidence.json` retains its historical pending browser fields; `pkce-evidence.json` is the subsequent authoritative browser outcome, and `closure-evidence.json` records post-cleanup integrity.

Earlier interactive execution `811659ab27a5fd8724ac2c9167dd8b68` passed its 15-case Client Credentials matrix but timed out with `INCOMPLETE / awaiting_browser / browser_callback_timeout`. The operator reported the provider's profile-completion page. It is not counted as a successful PKCE run. Its own resources and credentials were cleaned. The synthetic profile fields described above resolved that requirement in a fresh instance without disabling profile validation, switching grants, changing subjects/bindings or using real personal data.

Current offline regression: 85 passed, including real-token diagnostic structure with synthetic signed vectors, the shared purpose predicate, missing workload claims, exact/duplicate Host handling, nonce/state/issuer failures, ambiguous callback fields, timeout and transaction replay. Dependency check, JSON, Python syntax, document links, source secret scan and whitespace checks passed. No Java/Python product suite or product process was rerun/started in this follow-up because no product component changed. The previous 48 Java / 54 Python / independent-startup results remain historical evidence.

The callback binds explicitly to loopback; absolute/unicode callbacks deny and socket reads have a two-second configured timeout. A live slow-client test was not performed. Rotation, corporate provider onboarding, product session adoption, audit actor evolution, enterprise secret storage and SaaS data isolation remain out of scope. The laboratory's original HTTP/dev-file/host-permission limitations still apply.

**Identity & Access Foundation V1 — TASK 002: laboratory Keycloak fixture operationally validated.** Laboratory implementation and final evidence approved by the Product Owner, with commit/push of the fifteen TASK 002 files authorized. Creating a PR, merging and starting TASK 003 remain unauthorized. This is not production IAM readiness, OIDC integration in Java/Python, enterprise RBAC, SaaS multi-tenancy, Azure/AWS resource authorization or verified clinical identity.

Product independence is separately checked with existing Java/Python auth suites and the explicit [startup smoke](../../infra/iam-lab/product_smoke.py), after Keycloak cleanup:

```powershell
mvn -q -DskipTests package -f services/fhir-integration-service/pom.xml
& .\infra\iam-lab\.venv\Scripts\python.exe -B infra/iam-lab/product_smoke.py
```

This launches only recorded child processes on free ports 18390/18391, uses isolated ignored SQLite stores, clears inherited credentials/provider settings and checks Java liveness, Python health and unauthenticated legacy gates. It never calls clinical sources, `/actuator/health` aggregations, a model or Keycloak. For this smoke only, the Java HAPI URL points to closed loopback port 9 to guard accidental reads; product source defaults/configuration files are unchanged. Processes are stopped by their own PIDs. Existing session/login and federation test doubles establish regression behavior; this smoke is not another clinical E2E or HAPI integration test.

Regression commands used (in each service directory respectively):

```powershell
mvn -q "-Dtest=FederationSecurityConfigurationTest,FederationServiceTest,FederationSecurityAuditTest,ModelBoundaryServiceAuthFilterTest,ModelBoundaryServiceAuthUnconfiguredTest,ClinicalReadControllerTest,ClinicalReadAuthUnconfiguredTest" test
$env:PYTHONDONTWRITEBYTECODE='1'
& .\.venv\Scripts\python.exe -m pytest -p no:cacheprovider --basetemp .tmp-e2e-demo/iam2-auth tests/test_service_auth.py tests/test_human_development_auth.py tests/test_human_review_session_gate.py -q
```

Preparation also used `git status`, `git branch`, `git fetch origin`, `git rev-parse`, `git merge-base --is-ancestor`, `git stash list` and the authorized `git switch -c feature/identity-access-v1-task-002 origin/main`. Docker preflight used `docker info`, `docker ps -a`, `docker volume ls`, `docker network ls` and read-only inspect. The lifecycle performs digest-pinned `docker pull`, `docker image inspect`, `docker compose config --quiet` and explicit-profile `up -d --no-recreate --pull never keycloak`; cleanup performs only verified-ID `stop`/`rm`, verified volume `rm` and verified network-ID `rm`. Final checks include `git diff --check`, untracked-file `git diff --no-index --check`, document links, SHA-256 comparison, ignored-secret exclusion and empty staging. Existing CRLF migration-hash and restricted-ACL limitations in the [handoff](../agent-handoff.md) were not repaired or hidden by this task; the three hash tests were not part of this selected regression run.

TASK 003 needs its own Product Owner authorization and an explicit receiving-boundary/profile/session/audit contract before any OIDC adoption in either product. The operational TASK 002 evidence is approved for laboratory scope, with the remaining product/deployment limitations above; integration in main is a separate decision. No business functionality, enterprise connectors, MCP, cloud resources or new deployable product unit is introduced here.
