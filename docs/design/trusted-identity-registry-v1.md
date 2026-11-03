# Trusted Identity Registry — TASK 004

Identity & Access Foundation V1 — TASK 004: trusted workload registry and local revocation validated for laboratory scope.

Implementation and operational evidence approved by the Product Owner; final security review and commit/push of the twenty-one TASK 004 paths authorized, main integration pending. No PR, merge or TASK 005 authorized. TASK 003 is integrated via PR #105; verify current Git references each session. The [registry contract](../contracts/trusted-identity-registry-v1.md) owns schema, local administration, organizational selection, HTTP semantics, audit and revocation limits. [ADR-096](../adr/ADR-096-identity-provider-agnostic-v1.md) remains the architectural direction.

## Existing source inventory and minimum evolution

TASK 003 loads strict `TrustConfig` once when the opt-in route is configured inside FastAPI lifespan. `AccessVerifier` validates exact signature/issuer/audience/time/profile, returning only subject, registered client identity and expiry. Static matching then resolves exact client + subject under that provider, chooses its fixed organization, checks active binding/principal/membership/provider organization and computes the route permission locally. `WorkloadAudit.append` must commit before response; a final original-token expiry check can still suppress delivery. Memory contains immutable trust/bindings and the bounded JWKS cache, not live policy.

TASK 004 adds only a policy resolver and offline operator, not another verifier:

```text
Existing JWT verifier -> static binding OR fresh SQLite snapshot
                     -> selected membership + local route grant
                     -> mandatory separate access audit -> minimized context

Offline trusted lab CLI -> policy mutation + change audit in one registry transaction
```

| Source | Responsibility |
|---|---|
| `app/identity_registry_migrations/001_trusted_identity_registry.sql` | Initial dedicated versioned schema, constraints and FKs; historical migrations untouched |
| `app/trusted_identity_registry.py` | Strict trusted fixture, exclusive init, schema verification, consistent fresh reads, transactional changes and minimized change audit |
| `app/trusted_identity_registry_cli.py` | Explicit offline `init/list` and enable/revoke/grant operations with sanitized errors |
| `app/oidc_workload.py` | Select static/SQLite mode from deployment settings; verify JWT before organization policy; no credential fallback |
| `app/config.py` | Two optional deployment settings, static default |
| `app/oidc_workload_audit.py` | Add only `registry_unavailable` to existing closed reason vocabulary |
| `trusted-identity-registry.example.json` | Synthetic explicit initial registration; no provider credentials |
| `tests/test_trusted_identity_registry.py` | Offline lifecycle, actual SQLite failures, atomic rollback, concurrency, HTTP and unchanged static/legacy behavior |
| `infra/iam-lab/verify_trusted_identity_registry.py` | Explicit own Keycloak/AI live revocation using unchanged real JWT; never starts Java/HAPI |

`app/main.py`, `oidc_config.py`, `oidc_verifier.py`, existing OIDC tests, requirements, Human Review, clinical modules, LangGraph and Java are unchanged. Existing live helper gets only an optional registry path parameter; its no-argument static behavior is retained.

## Explicit local operation

Use the existing AI virtual environment/dependencies. Create a new trusted ignored runtime directory yourself, without changing ACLs. Adapt the synthetic fixture's provider id/issuer/binding to the explicitly approved trust registration; do not import identities from arbitrary token claims or Keycloak. Directory must already exist; `init` never replaces an existing database.

```powershell
# From services/ai-service; replace these non-runnable placeholders with approved absolute paths.
& .\.venv\Scripts\python.exe -B -m app.trusted_identity_registry_cli init --db ABSOLUTE_REGISTRY_PATH --fixture APPROVED_FIXTURE_PATH
& .\.venv\Scripts\python.exe -B -m app.trusted_identity_registry_cli list --db ABSOLUTE_REGISTRY_PATH
$env:OIDC_WORKLOAD_LAB_ENABLED='true'
$env:OIDC_WORKLOAD_TRUST_CONFIG_PATH='ABSOLUTE_APPROVED_PROVIDER_CONFIG'
$env:OIDC_WORKLOAD_AUDIT_DB_PATH='ABSOLUTE_SEPARATE_ACCESS_AUDIT_PATH'
$env:OIDC_WORKLOAD_POLICY_MODE='sqlite'
$env:OIDC_WORKLOAD_REGISTRY_DB_PATH='ABSOLUTE_REGISTRY_PATH'
# Start only an explicitly owned AI Service process with its own stores and no access logging.
```

Omitting `OIDC_WORKLOAD_POLICY_MODE` retains static TASK 003 behavior. Invalid/missing registry in SQLite mode does not downgrade. Changing modes requires controlled process configuration/restart; restoring an old mode is an operator action, not outage recovery. Membership/grant/principal changes within SQLite mode require no AI or IdP restart. Startup performs no IdP network call; database state is checked on each protected decision.

```powershell
& .\.venv\Scripts\python.exe -B -m app.trusted_identity_registry_cli revoke-permission --db ABSOLUTE_REGISTRY_PATH --target fixture-ai-workload --organization org-lab-a --permission iam.workload-context.read
& .\.venv\Scripts\python.exe -B -m app.trusted_identity_registry_cli grant-permission --db ABSOLUTE_REGISTRY_PATH --target fixture-ai-workload --organization org-lab-a --permission iam.workload-context.read
& .\.venv\Scripts\python.exe -B -m app.trusted_identity_registry_cli disable-principal --db ABSOLUTE_REGISTRY_PATH --target fixture-ai-workload
```

Only an unverified trusted local laboratory operator is claimed. No CLI credential is inherited from Keycloak. Requests/agents/documents cannot operate it through any added HTTP/MCP endpoint. IDs, permission names and labels must contain no secret or clinical data. Keep runtime databases/evidence ignored, unsynchronized and out of commits; SQLite has no application encryption or local-user isolation.

## Validation procedure

Deterministic focused verification from `services/ai-service`:

```powershell
$env:PYTHONDONTWRITEBYTECODE='1'
& .\.venv\Scripts\python.exe -m pytest -p no:cacheprovider --basetemp .tmp-e2e-demo/task004-validation tests/test_trusted_identity_registry.py tests/test_oidc_workload.py -q
& .\.venv\Scripts\python.exe -m pip check
```

The selected regression additionally covers service/development authentication, session gates, legacy access-audit producers, Clinical Read/Federation clients, federated mode and deterministic graph orchestration. It does not execute the unrestricted Python suite or HAPI. The three known CRLF migration-hash failures remain excluded/preexisting; no migration is rewritten. Existing Starlette/AnyIO deprecation warning is reported separately.

The explicit live runner, from repository root:

```powershell
& .\infra\iam-lab\.venv\Scripts\python.exe -B infra/iam-lab/verify_trusted_identity_registry.py
```

It uses only [TASK 002's owned fixture](identity-keycloak-lab-v1.md), default loopback provider 18090, one owned AI child on 18394 and dedicated ignored registry/access/application files. It performs CLI operations in subprocesses, never admin HTTP. Acquire the one real workload token **after AI startup**; fixture lifetime stays 30 seconds. Every control independently verifies the original token's signature/issuer/audience and checks actual expiry again after the response. Expiry means inconclusive failure, not successful revocation. There is no token renewal, token modification, password grant, human browser login or silent lifetime change.

Controls include initial 200, permission revoke 403/explicit restore 200, membership revoke 403/restore 200, principal disable 401/restore 200, cross-org no membership 403, binding disable 401/restore 200, explicit selection required with two memberships, no cross-org grant union and explicit authorized A 200. Registry change evidence and independent access decisions are checked persistently. Mandatory-storage failures are deterministic tests, not live fault-injection claims.

Cleanup verifies full IDs, owner/run/workspace/project labels and initial inventory exclusion using the existing fixture lifecycle. It removes only owned IAM container/volume/network, stops only its recorded AI child, removes ephemeral credential/import/login files and checks the listener closed. It compares global resource ID inventories without inspecting or contacting HAPI; no lifecycle/API operation targets `local-hapi`. Sanitized registry/audit/config/evidence may remain locally ignored for review, not encrypted/tamper-proof or committed.

## Executed evidence

The final selected AI regression passes **268/268**: **63 new registry tests**, all **69 unchanged TASK 003 OIDC tests**, and **136 existing regressions**. The separately executed offline IAM fixture suite passes **85/85**. `pip check` reports no broken requirements. These are selected suites, not the entire Python suite or Java/HAPI integration. The Starlette/AnyIO deprecation warning remains.

Registry tests cover clean/exclusive initialization, duplicate external bindings/client identities, missing FK parents, altered/foreign schema/version/audit continuity, disabled principals/bindings/organizations, permission and membership revoke/restore, persistent reopen, zero/multiple memberships and ambiguous headers, provider organization bounds, no permission union, malicious claims/body/headers, missing/corrupt/unavailable policy with no static fallback, locked access audit, actual change-audit constraint failure with complete rollback, concurrent readers/revocation, serialized writers, disabled OpenAPI/lifespan and unchanged legacy/static behavior. One old read snapshot can retain pre-commit state; sixteen fresh requests after confirmed revocation all deny. Twelve concurrent administrative transactions retain twelve distinct sequential audit revisions.

An initial test collection used an incorrect helper import; it was corrected to the existing `tests` package. A later synthetic read-failure test initially patched the setup registry rather than the boundary's independently constructed instance; it was corrected to inject the failure at the actual resolver. These preliminary failures are not successful validation, and no TASK 003 assertion was weakened or removed. Intermediate focused executions passed 119 and 131 tests; the final 268-test selection supersedes them. No productive defect or silent fallback was accepted.

### Real provider run

Completed live run `03438f399bc4304994fbe7b4a969b2f0` passed **13/13** real FastAPI controls using **one unchanged Keycloak access token**. Its signature, exact issuer and AI audience were independently verified for each control and the token was still unexpired **after every response**. The minimum remaining validity was **25.970 seconds**. The provider's 30-second lifetime and fixture were not changed; no refresh/replacement token or password grant was used. Workload principal/permission changes occurred only through the local CLI, without restarting AI or changing Keycloak.

| Control | Observed HTTP |
|---|---|
| Active workload | 200 |
| Permission revoked, original valid token | 403 |
| Permission explicitly restored | 200 |
| Membership revoked, original valid token | 403 |
| Membership explicitly restored | 200 |
| Principal disabled, original valid token | 401 |
| Principal explicitly restored | 200 |
| Cross-org B without membership | 403 |
| Binding disabled, original valid token | 401 |
| Binding explicitly restored | 200 |
| Two memberships without explicit selection | 403 |
| B membership but no B permission; no grant union | 403 |
| Explicit authorized organization A | 200 |

Persistent evidence contains **13 access decisions: 6 allowed / 7 denied**, and **10 atomic registry change records: initialization + 9 operations**, revision 10. Denials include binding/principal disablement, organization denial and permission denial; actors remain anonymous on denials. All change-operator labels explicitly remain unverified. No registry/access-audit distributed atomicity or live storage-failure injection is claimed; fail-closed storage/rollback is deterministic evidence.

The run created and removed exactly **one own Keycloak container, one own volume and one own network**. Its recorded AI process stopped, listener 18394 closed, and ephemeral credential/import/login files were removed. All original Docker resource IDs remain present; original and final inventories are **15 containers / 36 volumes / 8 networks**. No operation started, stopped, inspected or contacted HAPI; Java was neither started nor called. Inventories compare IDs, not live HAPI compatibility or every process's mutable state. Minimized registry/access databases, configuration, logs and sanitized evidence remain locally ignored for review; incidental isolated application stores also remain ignored, not shared with existing stores.

Sanitized local files are `trusted-registry-evidence.json` and `trusted-registry-cleanup.json` beneath that run's ignored `.runtime/` directory. They contain no token, token hash, credential or clinical payload. The AI log was checked for token/provider disclosure. Source review, Python AST/JSON/strict fixture loading, relative Markdown paths, secret-pattern review, exact own-file manifest, Git diff/whitespace checks and protected-file/stash hash comparisons passed. Runtime artifacts and local review helpers are not staged/versioned.

Implementation-phase commands included `git status/branch/rev-parse/stash list`, `git fetch origin`, TASK 003 ancestry verification, `git switch -c feature/identity-access-v1-task-004 origin/main`, selected pytest commands above (expanded with the existing authentication/audit/client/orchestration modules), offline IAM pytest, `pip check`, `docker info`, the explicit live runner and read-only integrity/diff checks. That implementation phase performed no staging/commit/push. The subsequent Product Owner authorization permits final review and staging/commit/push of exactly the twenty-one reviewed paths; PR, merge, reset, clean, force, stash operations, ACL changes and TASK 005 remain outside this authorization.

### Final security review

The authorized final review re-executed **268/268 selected AI tests** and **85/85 offline IAM fixture tests**, plus `pip check`, SQL/JSON/AST, relative-link, secret-pattern, exact-path and protected-file/stash checks. It inspected the original live reports and persistent policy/access evidence without repeating the live run or making Docker/HAPI operations. The only final-review edits clarify approved laboratory status and commit/push authority; code, schema, tests and operational harness behavior are unchanged from the approved live implementation. Therefore the thirteen live controls remain explicitly historical evidence, not a newly executed E2E claim. The known Starlette/AnyIO warning and excluded CRLF/HAPI limitations remain as stated above.

## Limits and follow-up

Revocation is a fresh local policy decision, not invalidation of the OAuth credential or a cancellation mechanism for already authorized work. Separate registry/access-audit files have no distributed atomic commit. Static mode has restart-bound policy and retains TASK 003 semantics. Only workloads, one approved provider profile and one new technical route are covered. Production IAM/admin authentication, OS security, distributed policy/invalidation, secret management, tenant-bound clinical data, human sessions, enterprise connectors and MCP remain out of scope. Propose TASK 005 only after Product Owner review and an explicit new task; do not infer its implementation scope.
