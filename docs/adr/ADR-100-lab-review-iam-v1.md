# ADR-100 — Laboratory OIDC for lab-summary human review

## Status

Accepted for this laboratory increment. It is not a certification, a production healthcare IAM deployment, or a replacement for every existing session.

## Context

Lab-summary human review authenticates with a loopback development secret and one configured principal. [ADR-096](ADR-096-identity-provider-agnostic-v1.md) already separates human Authorization Code + PKCE from workload client credentials and says a provider role is not a local permission. The stored summaries do not carry a trustworthy organization. The historical Gemini review, its receipt, and its original row must stay unchanged.

## Decision

1. When `LAB_REVIEW_IAM_ENABLED` is false, the three lab-summary routes keep the development session. When it is true, those routes accept only the OIDC session. Enabling both the development authenticator and this IAM flag is a configuration error and fails closed.
2. The human proof is an ID token from one configured issuer, validated for signature, audience, issuer, expiry, and nonce. The application then resolves `(issuer, subject)` in a server binding file. That file, not the token and not the browser, supplies one organization and one role.
3. `clinical-reviewer` may read and decide inside that organization. `clinical-auditor` may read and see audit, and may not decide. `clinical-admin` has no clinical permission unless the binding explicitly grants `read` or `audit`. `decide` is rejected for an administrator even if the file asks for it.
4. A review without an explicit organization association is not visible. Association is a separate row created by an explicit preparation step. It does not update `summary_json` or the original pending status. A query parameter cannot change the caller's organization.
5. The local session is an opaque HttpOnly, SameSite=Lax cookie. Its token is stored only as a SHA-256. Login rotates that cookie after the ID token is accepted. State is single-use and travels in a separate HttpOnly cookie with SameSite=None and Secure, because the provider posts the authorization code from another loopback port. HTTPS sets `Secure` on the session cookie. HTTP is allowed only for the documented loopback exception, and only `127.0.0.1` may carry the Secure transaction cookie without TLS.
6. The decision row stays immutable and unique. An additional identity row records issuer, subject, organization, and role. Workload permits and model calls are unchanged.

## Consequences

Keycloak in this increment is a local demonstration provider, pinned by image digest, not a corporate directory. Other services, MCP, and LLM authorization do not accept this session. A reverse proxy, multi-tenant storage, and production TLS are outside this decision.

## References

- [Lab review IAM contract](../contracts/lab-review-iam-v1.md)
- [ADR-093](ADR-093-human-review-session.md)
- [ADR-096](ADR-096-identity-provider-agnostic-v1.md)
