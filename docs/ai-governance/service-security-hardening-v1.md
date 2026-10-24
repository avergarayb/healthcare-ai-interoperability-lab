# Service security hardening v1

## Status and scope

This document records the inspected controls and the bounded changes made by Security & Governance V1 — TASK 005. It covers service authentication in Healthcare AI and Healthcare Interoperability, Clinical Federation authorization, and Human Review session/form protections. It does not claim production readiness or regulatory compliance and does not introduce IAM, enterprise RBAC, mTLS, MCP, a new agent, or a new service.

## Risk classification

### Confirmed and addressed in TASK 005

- Python internal service authentication compared secrets with ordinary string equality. It now compares SHA-256 digests with `hmac.compare_digest`.
- `MODEL_BOUNDARY_SERVICE_TOKEN` was included in the generated `Settings` representation. All credential fields are now excluded from that representation.
- Python startup did not reject reuse among the service token, form-signing secret, development-login secret and federation participant token. Configured values must now be pairwise distinct; errors identify variable names, never values.
- Java service authentication accepted an otherwise valid token with surrounding whitespace. Java and Python now require the exact credential bytes.
- Duplicate `X-Service-Token` headers were ambiguous. Protected Python internal routes, Java Model Boundary, Clinical Read and Clinical Federation now reject anything other than exactly one header value.
- The one-time AI-assistance handoff cookie did not set `Secure` over HTTPS. Creation and deletion now use matching `HttpOnly`, `SameSite=Strict`, case path and conditional `Secure` attributes.

### Potential risks not expanded in this task

- Some non-audit operational logs accept caller-provided correlation identifiers. They contain no credential or clinical payload, but a future correlation contract should canonicalize identifiers consistently across every workflow hop.
- A laboratory shared token authenticates several internal Python routes and Java Model Boundary/Clinical Read. Splitting every endpoint credential would change established consumers and requires a versioned authorization design.
- Static shared secrets have no built-in rotation, rate limiting or revocation protocol. Those controls belong with the future deployment identity and network boundary.

### Accepted laboratory limitations

- Human Review development login is loopback-only synthetic identity, not production IAM.
- Review, session and security-audit stores are single-process SQLite files and are not immutable or encrypted by the application.
- Demonstration runners and tests use explicit synthetic credentials. Checked-in environment examples leave protected credentials blank.
- Network isolation, protected secret storage, backup and host-file permissions remain operator responsibilities.

### Reserved for later EPICs

- Workload identity, enterprise RBAC, mTLS, centralized audit/retention, managed secret rotation, production multi-instance stores and end-to-end workflow correlation.
- MCP client/server, tool registry and autonomous execution. The readiness criteria below are requirements, not implemented controls.

## Credential-separation boundary

TASK 005 validates pairwise separation only for `MODEL_BOUNDARY_SERVICE_TOKEN`, `HUMAN_REVIEW_FORM_SIGNING_SECRET`, `HUMAN_REVIEW_DEVELOPMENT_AUTH_SECRET` and `AI_FEDERATION_PARTICIPANT_TOKEN` in the Python process. Empty variables are not treated as configured credentials. The E2E runner assigns distinct synthetic service and federation tokens and generates the two Human Review secrets independently.

Other credentials remain outside this validation: `GEMINI_API_KEY`; Java SMART/OAuth client secrets and access tokens; Exchange and Federation participant maps; Mini LIS HTTP tokens; and the HL7 shared secret. Their formats, ownership and lifecycles belong to their existing integration contracts. TASK 005 does not compare unrelated provider credentials across processes, introduce delegated credentials, or add enterprise IAM. Within the Java participant maps, the existing startup checks still require participant tokens to be distinct.

## Control matrix

| Control | Current implementation | TASK 005 change | Deterministic evidence | Residual risk |
|---|---|---|---|---|
| Internal Python authentication | `/internal/*` uses `service_auth.authenticate`; blank configuration fails closed | Constant-time digest comparison; exact single header required | `test_service_auth.py`; `test_human_review_session_gate.py::test_internal_service_token_boundary_is_unchanged` | One laboratory credential spans multiple internal contracts |
| Java Model Boundary and Clinical Read authentication | Filters reject before controller/provider and return empty 401 | Exact token bytes and duplicate-header rejection | `ModelBoundaryServiceAuthFilterTest`; `ModelBoundaryServiceAuthUnconfiguredTest`; `ClinicalReadControllerTest`; `ClinicalReadAuthUnconfiguredTest` | Shared secret is not workload identity |
| Federation participant identity | Caller is derived from a distinct configured token; declarative caller headers are ignored | Exact token bytes and duplicate-header rejection | `FederationSecurityConfigurationTest` | Static participant tokens need an external lifecycle |
| Federation authorization | Registry organization, authenticated system and explicit source grants are authoritative | No behavior change; inspected and regression-tested | `FederationServiceTest::authorizationDenialsUseVerifiedCallerIdentityAndSpecificReasons`; `unauthorizedSourceRejectsTheWholeQuery` | Laboratory registry/grants are static configuration |
| Denial disclosure | Authentication returns empty 401; federation authorization errors omit clinical entries | No contract expansion | Java filter/service tests | Network metadata remains outside application control |
| Secret separation | Form, development login and federation contracts already described distinct uses | Python startup rejects pairwise reuse of four security credentials; development guard includes federation token | Pairwise reuse and valid absent/distinct cases in `test_service_auth.py`; `test_disabled_or_non_loopback_configuration_hides_login` | Java cannot prove that independently supplied deployment secrets differ across processes |
| Secret exposure | Clients avoid token logging; audits use minimized fields | Service token removed from `Settings` representation; tests assert exception and representation secrecy | `test_settings_repr_omits_all_security_secrets`; Human Review and Federation audit tests | Process environment and host diagnostics remain operator-controlled |
| Human session | Random token stored only as hash; fixed expiry, revocation and fail-closed store; cookie is `HttpOnly`, `SameSite=Strict`, `/`, and `Secure` on HTTPS | No mechanism change | `test_human_development_auth.py`; `test_human_review_session_gate.py` | Synthetic fixed principal; no production identity provider |
| Review form integrity and origin | Purpose-separated, session-bound, expiring HMAC plus same-origin checks | No mechanism change | HMAC, wrong-purpose, tamper, expiry and origin cases in `test_human_review_session_gate.py` | HMAC is presentation integrity, not clinical authorization |
| AI-assistance one-time handoff | Random 60-second, case-bound, in-memory ticket in an `HttpOnly`, case-scoped, `SameSite=Strict` cookie | Conditional `Secure` on HTTPS and matching deletion attributes | `test_assistance_handoff_cookie_is_secure_on_https_and_scope_matched_on_delete`; cross-case test | HTTP loopback demos cannot use `Secure`; ticket store is process-local |
| Security audit compatibility | Python Human Review and Java Federation append minimized, decision-specific events and fail closed when required audit is unavailable | Existing event schema and reason codes preserved | `test_human_review_security_audit.py`; `FederationSecurityConfigurationTest`; `FederationServiceTest` | SQLite audit is not immutable or centralized |
| Protocol regression | Clinical Read remains the default; federation, Human Review and three LangGraph workflows retain their contracts | No routing, model-authority or protocol changes | Relevant Python and Java regression suites | Live HAPI, Gemini and container tests remain opt-in |

## Negative scenarios

The required negative evidence maps to real boundaries as follows:

1. Missing, invalid and empty token: Python `test_service_auth_rejects_invalid_or_ambiguous_credentials`; Java authentication filter tests.
2. Authentication unconfigured: the same Python test plus Java `*AuthUnconfiguredTest` classes.
3. Manipulated caller identity: `FederationSecurityConfigurationTest::validTokenSetsOnlyTheServerResolvedCallerAndDefersAuditToAuthorization`.
4. Unauthorized organization and absent source grant: `FederationServiceTest::authorizationDenialsUseVerifiedCallerIdentityAndSpecificReasons` and `unauthorizedSourceRejectsTheWholeQuery`.
5. Credentials in logs or persisted audit: Human Review `test_audit_contains_no_secrets_session_material_or_clinical_identifiers`, federation denial assertions and the new settings/error tests.
6. Expired, revoked, invalid or manipulated session cookie: `test_human_review_session_gate.py` and `test_human_development_auth.py`.
7. Incorrect, cross-session, wrong-purpose, expired or tampered HMAC and invalid origin: `test_human_review_session_gate.py`.
8. Protected endpoint without authentication: session-gate anonymous route tests and Java controller/provider non-invocation tests.
9. Configuration error: development-auth guard tests, pairwise credential-reuse test and Java unconfigured tests.
10. `SECURITY_AUDIT_V1` compatibility and protocol regression: Human Review security-audit, federation audit, LangGraph and service regression suites.

## Minimum security criteria for Agent Runtime & MCP Foundation V1

Before any MCP implementation is accepted, its contract must define and test all of these controls:

1. Resolve the effective requester identity from verified credentials; tool arguments or external content cannot select or elevate that identity.
2. Register tools explicitly and authorize each invocation against a per-tool allowlist, purpose and tenant/organization scope. Deny by default.
3. Use separate credentials per integration and prevent one tool or tenant from reading another's credentials or results.
4. Apply bounded timeouts, concurrency, request/response sizes, retry rules and total execution budgets.
5. Validate and minimize tool inputs and outputs against explicit schemas before either reaches another tool, an LLM or a user.
6. Treat documents, API results and MCP responses as untrusted content. They cannot alter privileged instructions, effective permissions, authorization policies or execution limits.
7. Test prompt-injection, tool-poisoning, confused-deputy and data-exfiltration attempts, including indirect instructions inside retrieved content.
8. Audit the verified actor, tool, purpose, authorization decision, timing and coarse outcome without credentials, prompts containing sensitive data or unrestricted payloads.
9. Preserve result provenance: integration, tool version, source, retrieval time and transformations must remain attributable.
10. Require an authenticated Human Review decision before any sensitive, clinical, irreversible or external action; an LLM cannot approve or close that review.

These are readiness gates only. This repository does not yet contain an MCP client, server, registry or MCP tool execution path.
