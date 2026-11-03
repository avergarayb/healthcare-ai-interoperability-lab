# Python OIDC Resource Server Foundation — TASK 003

Implementation and evidence approved by the Product Owner for laboratory scope; commit/push of the eighteen TASK 003 paths authorized, main integration pending. No PR, merge or TASK 004 authorized. [ADR-096](../adr/ADR-096-identity-provider-agnostic-v1.md) remains the architectural direction; the [new boundary contract](../contracts/python-oidc-workload-v1.md) and [additive audit contract](../contracts/oidc-workload-security-audit-v1.md) define this increment. Workloads only, one explicit provider registration, no human OIDC session adoption or clinical authorization.

## Files and ownership

| Component | Responsibility |
|---|---|
| `app/oidc_config.py` | Strict immutable JSON registration, URL/algorithm/numeric limits, closed binding schema |
| `app/oidc_verifier.py` | Recognized JWT verification, explicit provider-profile adapters, minimized verified workload and bounded key cache |
| `app/oidc_workload.py` | Credential policy, internal PrincipalContext adapter, local organization/route authorization, sanitized HTTP projection |
| `app/oidc_workload_audit.py` | Separate versioned append-only SQLite audit API |
| `app/config.py`, `app/main.py` | Three opt-in settings and startup route registration; no legacy handler migration |
| `oidc-workload.example.json` | Disabled, secret-free registration using reserved example HTTPS URLs |
| `tests/test_oidc_workload.py` | Offline cryptographic, transport, policy, persistence and FastAPI conformance |
| `infra/iam-lab/verify_python_resource_server.py` | Explicit live fixture/AI-process runner with owned-resource cleanup |

The main app has no conflicting router or global authentication middleware. Existing handlers enforce `X-Service-Token` through `service_auth.py`; Human Review uses its separate synthetic session/HMAC contract. The new route has its own handler policy, never a broad `/internal/*` exception. Authentication code has no graph, model or clinical imports. It consumes no Python-to-Java federation tokens.

## Explicit activation

Install the service requirements, including pinned `PyJWT[crypto]==2.15.1` and `cryptography==50.0.2`, in the AI Service virtual environment. No Java dependencies change. Adapt [the disabled example](../../services/ai-service/oidc-workload.example.json) into an operator-owned local file; no client/admin secrets belong in resource-server configuration.

```powershell
$env:OIDC_WORKLOAD_LAB_ENABLED='true'
$env:OIDC_WORKLOAD_TRUST_CONFIG_PATH='ABSOLUTE_PATH_TO_APPROVED_JSON'
$env:OIDC_WORKLOAD_AUDIT_DB_PATH='ABSOLUTE_PATH_TO_DEDICATED_SQLITE'
# Run in services/ai-service; all existing service configuration still applies.
& .\.venv\Scripts\python.exe -m uvicorn app.main:app --host 127.0.0.1 --port 18392 --no-access-log
```

Do not paste credentials into command arguments, chat or reports. Use the explicit live runner below to generate fresh laboratory credentials and pass tokens only in memory. Keep access logs disabled for this laboratory operation; arbitrary URLs must not become a place to log credentials. No localhost issuer is a product default. HTTP loopback is an explicit registration exception for a test-owned provider, never disabled TLS verification.

Default `OIDC_WORKLOAD_LAB_ENABLED=false` means no new route/OpenAPI operation and no provider/audit I/O. With activation but bad registration, only this boundary is unavailable. The trusted file and membership/principal state are a static laboratory registry: changes, disablement or revocation require controlled process restart. No dynamic onboarding, tenant discovery, user database or enterprise membership administration exists.

## Response, authorization and audit

GET `/iam-lab/v1/workload-context` accepts one exact Bearer credential and refuses legacy service headers/cookies at this boundary. The response omits external issuer/subject/provider and raw claims. Effective permissions are restricted to this route's `iam.workload-context.read`; token roles/groups/organization never add authority. Workload classification requires the explicit service-account subject + client registration, active principal/binding/membership, selected fixed organization and allowed API audience. A JWT cannot become a human.

401 means invalid authentication; 403 means verified workload denied by local policy; 503 means unavailable mandatory trust/keys/configuration/audit. Public errors contain no detailed reason or credentials. Correlation accepts only one canonical UUIDv4 and never grants authority.

The additive database stores one minimized access decision before a normal response. Legacy audit actors/events/schema/store and historical migrations are untouched. Positive append failure suppresses the entire projection. An allowed audit row records the decision at append time, not guaranteed response delivery: if the original token expires while persisting it, a final check returns 401 without disclosing an expired context. That allowed row is not a workflow/business success or a fabricated denial. SQLite remains one-process laboratory persistence, without encryption, immutability, retention service or distributed transaction.

## Verification and evidence

From `services/ai-service`, deterministic tests are explicit and require no Docker/IdP:

```powershell
$env:PYTHONDONTWRITEBYTECODE='1'
& .\.venv\Scripts\python.exe -m pytest -p no:cacheprovider --basetemp .tmp-e2e-demo/task003-verification tests/test_oidc_workload.py -q
& .\.venv\Scripts\python.exe -m pip check
```

The suite covers signature/algorithm, issuer/audience, temporal bounds, token purpose, unknown/disabled bindings/principals, memberships, privilege-injection claims, missing/duplicate/conflicting credentials, unavailable trust/audit, actual SQLite write locking, exact discovery/JWKS, redirects/response limits/timeouts, unknown-key throttling/concurrency, rotation/removal, hard expiry, disabled routing/OpenAPI and unchanged legacy policy. API-ID-token rejection vectors here are synthetic signed vectors, not live browser evidence.

The live runner is **opt-in** from repository root, using the existing [TASK 002 fixture](identity-keycloak-lab-v1.md):

```powershell
& .\infra\iam-lab\.venv\Scripts\python.exe -B infra/iam-lab/verify_python_resource_server.py
```

It creates a unique owned IAM instance and isolated AI processes/stores on 127.0.0.1:18392 (normal policy), then 18393 (denied policy); no Java or HAPI is started or called. It validates real AI tokens, Java-audience rejection, unknown workload, missing/contradictory credentials, actual expiry, unchanged legacy Bearer rejection and 403 for a registered workload without the local route grant. The last case restarts only its own AI process with a new local policy, not Keycloak configuration. Tokens remain in memory; audit/evidence files are minimized under ignored `.runtime/`. Distinct ports avoid Windows TCP TIME_WAIT after stopping the first child. Cleanup verifies listener closure without force/reuse; exclusive rebinding may still wait for the OS TCP timeout.

The TASK 002 human ID token was never persisted and has expired. TASK 003 does not repeat an unnecessary interactive login or pretend that TASK 002 harness rejection exercised this new product boundary. Live ID-token rejection remains unexecuted here; the new boundary's synthetic rejection coverage is separate and required.

Operational results and cleanup are recorded after verification. The first two attempts failed closed with `provider_unavailable` during discovery and cleaned their own resources; they are not counted as successful live validations.

A separate owned diagnostic measured unchanged discovery URI via normal localhost connection at 2.021 seconds versus 0.010 seconds with a local IPv4 bind. The explicit HTTP-loopback transport now binds to `127.0.0.1` while keeping the canonical localhost URL, Host and issuer. The two-second network deadline and 1 MiB limit remain; HTTPS certificate verification is never disabled. Client/TLS-context construction precedes the network deadline. The diagnostic instance was also cleaned.

### Results

The selected final regression passes **205 tests**, including **69 new OIDC tests** and **136 existing regression tests** for service/development authentication, session gates, existing audit producers, Clinical Read/Federation clients, federated mode and deterministic LangGraph orchestration. Dependency consistency passes. The existing Starlette/AnyIO deprecation warning remains. The three preexisting CRLF migration-hash tests and live HAPI/provider tests are not part of this selected suite; historical migrations were not edited.

An initial-concurrency regression reproduced a first-write audit initialization race that failed closed with 503. The writer lock resolves it; sixteen concurrent first appends persist without lost records. A real SQLite write lock still produces 503 with no context projection. These are **deterministic** storage-failure tests, not claims of a live fault-injection E2E.

Completed live execution `312b28aed7caeabdf350ed2c335aabe8` passed the eight cases below. Repeat `1504d744cca59cac096a1e332267f01d` passed after the writer-lock fix; final execution `0368d18f94812921a2a6fcb857ac6acf` passed with scoped metadata-log suppression. These repeat the same eight controls. Earlier failed/diagnostic runs are retained as such; a partial run before policy-process restart is not a completed matrix.

| Real FastAPI / provider case | Expected and observed |
|---|---|
| AI-audience token, registered workload | 200; minimized internal workload context |
| Interoperability-audience token | 401 |
| Actual signed token from unregistered workload | 401 |
| No Authorization | 401 |
| Bearer plus legacy credential | 401 |
| Bearer alone on existing `/internal/agent-context` | 401; no Java call |
| Original actual token after its expiry | 401 |
| Registered workload without local route permission | 403 |

Each successful execution persists seven new-boundary audit decisions: one allowed and six denied, including exact audience, unknown-binding, credential, expiry and policy reasons. The legacy GET does not invent a new OIDC audit event. Local audit is durable across the owned AI process restart used for policy denial. These checks exercise the real AI Service endpoint; TASK 002's harness evidence is separate. No real human ID token is claimed for this new boundary, and no live storage-outage claim is made.

Final cleanup covers seven owned IAM container/volume/network sets (failed attempts, diagnostic and successful repetitions) and all recorded AI child processes. The original inventory remains 15 containers, 36 volumes and 8 networks. HAPI container IDs/start times/status/restart counts are unchanged by read-only Docker metadata comparison; no HAPI HTTP or lifecycle operation occurred. Listeners on 18090/18392/18393 are closed. Ephemeral credentials/imports and empty temporary application stores are removed by verified run-directory/filename cleanup; minimized audit databases, source configuration and sanitized evidence remain ignored locally. Those runtime artifacts are not versioned, and no ACL is modified.

The metadata client suppresses its own `httpx`/`httpcore` SDK logs in a context-local scope, so provider URLs do not enter ordinary logs and concurrent/legacy clients retain their existing logging. No raw claims or tokens are logged. The final live execution's logs were checked for token/issuer disclosure. The runbook is evidence of laboratory scope, not approval for production IAM or verified clinical identity.

Implementation validation used Git status/fetch/ancestry/switch and stash/hash checks; installation of the two pinned crypto packages; the selected pytest suite above plus existing authentication/audit/client/orchestration suites; `pip check`; explicit live runner; read-only Docker inventories; guarded cleanup of owned temporary stores; JSON/Python/Markdown/secret/diff checks. Final review repeats deterministic checks before the authorized commit/push. The approved live evidence is retained without claiming a new live run; no verification/binding/audit/FastAPI behavior changed during this review. No PR or merge is authorized.

## Remaining limits / TASK 004

Only `keycloak-client-credentials-v1` is approved initially. Core verification/cache and normalized workload identity are separate from the profile adapter and business logic; Entra/Auth0/Okta/corporate Keycloak require registration and conformance work, not automatic acceptance. No OIDC reaches existing endpoints, Human Review sessions/attribution, Java, LangGraph checkpoints or clinical protocols. No RBAC enterprise, SaaS tenant data isolation, cloud resource access, MCP or new agents are introduced.

Further work needs an approved TASK 004 scope: production trust/transport and secret-management deployment, provider lifecycle/rotation/revocation operation, bounded admission/rate limits, durable production audit and any separate endpoint/session adoption contracts. No such follow-up is started by this task.
