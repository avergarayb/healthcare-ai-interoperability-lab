# ADR-093 — Human review session

## Status

Accepted for development authentication. Not production identity.

## Date

2026-10-07

## Context

The Human Review Client serves the follow-up queue, case page, close form, AI assistance and controlled action from the Healthcare AI process. Those routes do not identify a person. `HUMAN_REVIEW_FORM_SIGNING_SECRET` binds a form to a case and a short expiry. `MODEL_BOUNDARY_SERVICE_TOKEN` authenticates `/internal/*` callers. Neither secret is a human session.

A later OIDC authenticator may replace how a person proves identity. Review Case closure and `FOLLOW_UP_COORDINATION_ACTION_POLICY_V1` must stay the operational rules they are now. This ADR accepts the laboratory development session. It does not accept production identity.

## Decision

`HUMAN_IDENTITY_V1` adds an application session in front of the Human Review Client. The contract is [HUMAN_IDENTITY_V1](../contracts/human-identity-v1.md).

Six boundaries stay separate:

- `HumanPrincipal` is the application identity established after successful authentication. V1 has one synthetic principal taken from server configuration.
- `HumanAuthenticator` checks one assertion and returns that principal. The development authenticator is the only V1 implementation. An OIDC authenticator can replace it later without a change to review or coordination services.
- `HumanSession` is the server record of one successful authentication. The browser receives an opaque token. SQLite stores only the SHA-256 of that token.
- `HumanSessionRepository` persists sessions in a third SQLite file. It does not read or write the review database or the institutional knowledge database.
- `HumanSessionService` creates, resolves and revokes sessions. It does not apply review policy or coordination policy.
- The HTTP boundary demands a live session before the five human review routes run. It then keeps the existing same-origin check and purpose-separated HMAC.

The session cookie uses `Path=/`. `/internal/*` may receive that cookie and still authenticates only with `X-Service-Token`. The cookie is not service authorization.

Session persistence, the development authenticator and the route gate shipped together. The five review routes require a live session. A login cookie is not service authorization and is not production identity.

The development authenticator is enabled only when the explicit flag is on, `AI_SERVICE_HOST` is loopback, the accepted socket address reported by Uvicorn is loopback, and the development secret, principal and session path are present and distinct from the service token, the form secret and the other SQLite files. A flag or `AI_SERVICE_HOST` by itself does not enable it. `uvicorn --host 0.0.0.0` keeps the authenticator inactive. A proxy in front of a loopback listener is not detected. SMART Authorization Code + PKCE in Healthcare Interoperability is not this login.

V1 is authentication and session lifetime. A valid session is not clinician authorization, not attribution and not a security audit. Review Case events stay `created` and `closed`. Coordination requests stay unattributed.

Each HMAC message covers the session id, so a form issued to one session fails under another. Manual validation and deterministic regression passed for this development session. Production identity, attribution and security audit remain deferred.

## Consequences

Local demonstration of the review pages requires the development guard and a session. The authenticator stays off unless the accepted socket is loopback, so `--host 0.0.0.0` does not expose login. `/health` and `/internal/*` stay as they are. Gemini, retrieval, FHIR reads and protocol evaluation are unchanged. The session file is unencrypted SQLite for one process. A reverse proxy in front of loopback is not a covered deployment. This is not a production network boundary, enterprise IAM or institutional SSO.
