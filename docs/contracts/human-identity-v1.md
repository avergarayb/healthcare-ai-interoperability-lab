# HUMAN_IDENTITY_V1

## Status

Accepted laboratory contract for development authentication. Not production identity. Not clinician authorization. Not a security audit. Not IAM, SSO or RBAC.

The five human review routes require a live development session, and each form HMAC includes that session. Manual validation and deterministic regression passed for this laboratory control. Production identity remains a separate decision.

## Authority

| Source | Owns |
|---|---|
| Development authenticator | Whether the configured synthetic principal is authenticated |
| `HumanSessionService` | Issue, resolve and revoke one application session |
| HTTP boundary | Whether a human review route may run |
| Existing review and coordination services | Operational case rules and the coordination policy |

A valid session means this application accepted the development assertion and the session record is live. It does not mean a clinician is authorized, a case is assigned, or a named person approved an action.

Gemini, institutional retrieval, FHIR context and browser-supplied names do not authenticate the principal. Healthcare Interoperability SMART Authorization Code + PKCE is not this login.

## Boundaries

`HumanPrincipal` carries `principalId`, `displayName` and `authenticatorId`. V1 `authenticatorId` is `DEVELOPMENT_AUTHENTICATOR_V1`. The request body cannot supply these values.

`HumanAuthenticator` accepts one assertion and either returns the configured principal or fails. It has no user directory and no password store.

`HumanSession` is one row created after success. `HumanSessionRepository` is the only writer of the session file. `HumanSessionService` is the only caller of that repository from product code.

The HTTP boundary calls the authenticator and then the session service. `FollowUpReviewCaseService` and `FollowUpCoordinationActionService` do not import either one. Their method signatures stay unchanged.

Authentication, authorization, attribution and security audit stay distinct:

- Authentication is a live application session.
- Authorization, meaning what a principal may do, is deferred. V1 does not add roles, assignment or per-case grants.
- Attribution, meaning which principal initiated a close or a coordination request, is deferred. V1 does not add a principal to review events or coordination rows.
- Security audit, meaning a durable record of security-relevant activity, is deferred. V1 does not add an audit table.

Review Case history remains the operational `created` and `closed` events.

## Development authenticator

The authenticator is development-only. It is active only when every guard below passes. Any failure leaves it inactive. Inactive behavior is fail closed: the human review routes do not fall back to anonymous access.

| Guard | Requirement |
|---|---|
| Explicit enablement | `HUMAN_REVIEW_DEVELOPMENT_AUTH_ENABLED` is exactly `true` |
| Bind address | `AI_SERVICE_HOST` is `127.0.0.1` or `::1` |
| Development secret | `HUMAN_REVIEW_DEVELOPMENT_AUTH_SECRET` is at least 32 characters |
| Secret separation | That secret differs from `MODEL_BOUNDARY_SERVICE_TOKEN` and from `HUMAN_REVIEW_FORM_SIGNING_SECRET` |
| Principal | `HUMAN_REVIEW_DEVELOPMENT_PRINCIPAL_ID` matches `^[a-z0-9](?:[a-z0-9-]{0,62}[a-z0-9])?$` |
| Display name | `HUMAN_REVIEW_DEVELOPMENT_PRINCIPAL_DISPLAY_NAME` is 1 to 80 characters and has no control characters |
| Session file | `HUMAN_SESSION_DB_PATH` is non-blank, is not `:memory:`, and differs from the review and knowledge database paths |

`AI_SERVICE_HOST` is still required and must be `127.0.0.1` or `::1`. It is not sufficient. Each login, logout and review request also reads `scope["server"]`, which Uvicorn fills from `getsockname()` of the accepted socket. That value is the listen address, not the `Host` header and not `X-Forwarded-For`. `0.0.0.0`, `::`, a LAN address, or an unparseable name leaves the authenticator inactive even when `AI_SERVICE_HOST` is loopback. A `Host: 127.0.0.1` header on that connection does not enable it.

The local procedure still sets both `AI_SERVICE_HOST` and `uvicorn --host` to `127.0.0.1`.

This check does not see a reverse proxy. If Uvicorn listens only on loopback and a proxy forwards public traffic to that socket, `getsockname()` remains loopback and the authenticator can be active. That deployment is outside this contract. ADR-082's unresolved production network boundary stays unresolved. The flag is not production security, a network boundary or an identity provider.

The login assertion is the development secret posted by the browser. There is no username field. FHIR client credentials are not accepted. The comparison hashes both values with SHA-256 and uses a constant-time compare, so the presented secret is not stored and a length mismatch is still a denial.

The principal id and display name are copied from configuration onto the session at issue time. Changing the request cannot select a different principal.

## Session

The session file is a third SQLite database. Review migrations `001` and `002` stay unchanged. The institutional knowledge database stays unchanged.

`HUMAN_SESSION_DB_PATH` defaults to `./data/human-session.sqlite3` when the implementation adds the setting. The default does not by itself enable the authenticator.

The cookie name is `human_review_session`. Its value is the raw token from `secrets.token_urlsafe(32)` (256 bits). SQLite stores `token_hash`, the hex SHA-256 of the UTF-8 token. The raw token is not stored, logged or placed in a URL.

Cookie attributes:

| Attribute | Value |
|---|---|
| HttpOnly | Set |
| SameSite | `Strict` |
| Path | `/` |
| Secure | Set when the application request scheme is `https` |
| Max-Age | 28800 seconds, set once at issuance. It does not slide |

On `http://127.0.0.1` or `http://[::1]`, browsers reject a `Secure` cookie, so the local cookie is set without `Secure`. That exception exists only because the development guard already required a loopback bind. The application does not trust a forwarded protocol header. This mode is not defined for a TLS terminator in front of a non-loopback process. That deployment fails the bind guard.

Lifetime is absolute. `expires_at` is `issued_at` plus 28800 seconds (8 hours). V1 has no environment override and no sliding renewal. A request at expiry fails closed. Logout sets `revoked_at` and clears the cookie. A new login inserts a new `session_id` and a new token. It does not reuse a presented cookie as the new session.

Invalid, expired, revoked and unknown tokens produce the same browser response. More than one live session for the same synthetic principal is allowed. Logout revokes only the session in that browser.

Restart keeps unexpired, unrevoked rows. The process-local AI assistance handoff remains separate and still disappears on restart.

Rows are not patient data and do not contain FHIR, review case ids, observation values, prompts or secrets. Cleanup deletes rows whose `expires_at` is more than 24 hours in the past. Cleanup runs inside a session-repository transaction. There is no background worker. Revoked rows stay until that window so a reused token remains a revocation, while the browser still sees the same login response.

## Session schema

Schema version is 1. A new file applies `001_human_session.sql` and sets `user_version = 1`. Version 1 opens only when the table and checks match. A higher version fails closed. A failed migration rolls back and leaves the human routes unavailable. The review database is not opened for this migration.

```sql
BEGIN IMMEDIATE;

CREATE TABLE human_sessions (
    session_id TEXT PRIMARY KEY,
    token_hash TEXT NOT NULL UNIQUE CHECK (
        length(token_hash) = 64
        AND token_hash NOT GLOB '*[^0-9a-f]*'
    ),
    principal_id TEXT NOT NULL CHECK (
        length(principal_id) BETWEEN 1 AND 64
    ),
    display_name TEXT NOT NULL CHECK (
        length(display_name) BETWEEN 1 AND 80
    ),
    authenticator_id TEXT NOT NULL CHECK (
        authenticator_id = 'DEVELOPMENT_AUTHENTICATOR_V1'
    ),
    issued_at TEXT NOT NULL CHECK (substr(issued_at, -1) = 'Z'),
    expires_at TEXT NOT NULL CHECK (substr(expires_at, -1) = 'Z'),
    revoked_at TEXT CHECK (revoked_at IS NULL OR substr(revoked_at, -1) = 'Z'),
    CHECK (expires_at > issued_at)
);

CREATE INDEX human_sessions_expires_at_idx
    ON human_sessions (expires_at);

PRAGMA user_version = 1;

COMMIT;
```

`session_id` is a server-generated UUID. It is not the cookie value. Later HMAC binding uses `session_id`.

Connections are per operation, with foreign keys, WAL and a bounded busy timeout, matching the review repository. Issue, resolve-with-cleanup and revoke each run in `BEGIN IMMEDIATE`. The supported topology is one `ai-service` process. Two logins insert two rows. A repeated revoke of the same token is success and does not create a row.

SQLite errors, a missing parent directory and a future schema version are persistence failures. The response does not include the path, the SQL text or the exception text. Logs may record `human_session result=unavailable` without the token, the hash or the secret.

A session-store failure does not stop `/health` or `/internal/*`.

## Routes

These routes require a live session before any review, clinical, Gemini, retrieval or coordination work:

| Method | Path |
|---|---|
| GET | `/review-cases` |
| GET | `/review-cases/{reviewCaseId}` |
| POST | `/review-cases/{reviewCaseId}/close` |
| POST | `/review-cases/{reviewCaseId}/ai-assistance` |
| POST | `/review-cases/{reviewCaseId}/controlled-action` |

The session check comes first. Unknown and known case ids return the same response. The handler does not query the review database for an unauthenticated request, so the response does not reveal that a case exists.

`/review-static` stays public. It may serve only the non-sensitive files already mounted from `app/static/human_review`. Case data, tokens and secrets must not be placed there. The login page may use that stylesheet.

`GET /health` stays public. `/internal/*` stays on `X-Service-Token`. Cookie `Path=/` may send `human_review_session` to those routes. They do not accept that cookie as service authorization. A service token does not create a human session. Same-origin checks and the purpose-separated HMAC on close, AI assistance and controlled action stay in place.

Authenticated pages, login responses, logout responses and the redirects below use `Cache-Control: no-store`.

## Login and logout

Server-rendered HTML. No frontend framework.

| Method | Path | When the guard is active |
|---|---|---|
| GET | `/review-login` | Login form |
| POST | `/review-login` | Authenticate, then create a session |
| POST | `/review-logout` | Revoke the presented session |

The login form posts `application/x-www-form-urlencoded` with exactly one field, `developmentSecret`. The body is limited to 1024 bytes. The secret is not written to the URL, the log, the page or the session row. There is no `next` or other return parameter. After success the browser is sent to `GET /review-cases`.

Login POST also requires same-origin, using the existing origin comparison. A session row is inserted only after the secret matches. Failure inserts nothing and sets no cookie. Logout POST has an empty body. A non-empty logout body is rejected and does not revoke.

A review route without a live session does not return review data. Accepted local login-CSRF posture: another origin cannot complete login; the server chooses the session id; and a forced login on loopback still yields only the configured principal.

Logout is POST only. It requires same-origin and a resolvable session, then sets `revoked_at` and clears the cookie. A GET logout route is not part of this contract. Logout without a live session returns the same login redirect as any other missing session.

When the development guard fails, `GET` and `POST` login and logout return 404 with a generic page and no form. The five review routes return 503 with a generic unavailable page and no case content. Neither page names a setting, a path or a secret.

## Browser behavior

| Condition | Response |
|---|---|
| Guard inactive, review route | 503 generic unavailable page |
| Guard inactive, login or logout | 404 generic page, no form |
| Store unavailable | 503 generic unavailable page |
| No, unknown, expired or revoked session on a review GET or POST | 303 to `/review-login` |
| Login GET while active | 200 login form |
| Login POST, origin or body rejected | 400 generic failure page |
| Login POST, secret rejected | 401 generic failure page, no cookie |
| Login POST, secret accepted | 303 to `/review-cases` and `Set-Cookie` |
| Logout POST with a live session | Revoke, clear cookie, 303 to `/review-login` |
| Authenticated review GET or POST | Existing handler, after the session check |

Failure pages use one sentence: sign-in failed, or this demo is not available. They do not say which guard, cookie or database check failed.

Logs for these routes record a coarse result such as `denied`, `unavailable` or `accepted`, plus the route and status. They omit the cookie, the token, the token hash, the posted secret, FHIR payloads and clinical values.

## HMAC and CSRF

After the session check, close, AI assistance and controlled action still require same-origin and their existing HMAC. A session without a valid HMAC does not close a case, call Gemini or insert a coordination request. The HMAC does not create or replace a session.

Signed messages:

- Close: `{reviewCaseId}|{expectedVersion}|{expiry}|{sessionId}`
- Assistance: `ai-assistance|{reviewCaseId}|{expiry}|{sessionId}`
- Controlled action: `controlled-action|{reviewCaseId}|{actionType}|{expiry}|{sessionId}`

`sessionId` is the session row id, not the raw cookie token and not `token_hash`. The form still carries the expiry and the HMAC. The server signs with the session it resolved and recomputes the HMAC for that same session. Purpose separation and the 900-second lifetime stay as they are.

A form captured from one session fails under another session's cookie, including a session created by a later login. Same-session replay inside the 900-second TTL remains the HMAC behavior. Close and coordination stay idempotent under their own rules. An invalid signature does not close a case, call Gemini or insert a coordination request.

CSRF for the session:

- `SameSite=Strict` withholds the cookie on cross-site requests, so a foreign page does not arrive authenticated.
- Same-origin remains mandatory for login, logout, close, assistance and controlled action.
- Login does not accept a caller-chosen session id, which closes session fixation.
- Login CSRF from another origin fails the origin check. Forcing a login would still yield the single configured principal. It would not attach a different person's identity, because V1 has no second principal.
- Logout CSRF from another origin fails both `SameSite=Strict` and the origin check. Logout is not available as GET.
- A same-origin page can still post if it is served by this application. `/review-static` must not become an upload target.

No extra anonymous CSRF cookie is required for V1 beyond origin checks, `SameSite=Strict` and the session-bound HMAC.

## Failure behavior

| Scenario | Behavior |
|---|---|
| Missing or invalid authentication configuration | Guard inactive. Review routes 503. Login hidden. |
| Incorrect development secret | 401. No session row. No cookie. |
| Invalid session cookie | 303 to login. Clear the cookie. No review lookup. |
| Expired session | Same as an invalid cookie. |
| Revoked session | Same as an invalid cookie. |
| Missing session database or SQLite error | 503 on human routes. `/health` and `/internal/*` continue. |
| Login or logout CSRF from another origin | 400. No session created or revoked. |
| Cross-session form replay | 400 after the session check, once the HMAC covers `sessionId`. |
| Direct POST without a session | 303 to login before HMAC, FHIR, Gemini or coordination. |
| Invalid Origin on an authenticated POST | Existing 400. The session is left in place. |
| Application restart | Unexpired unrevoked sessions remain. Assistance handoff memory does not. |
| Two browsers signed in | Two rows. Each logout revokes one row. |

## OIDC compatibility

A future authenticator implements the same `HumanAuthenticator` shape: it validates its own assertion and returns a `HumanPrincipal`. The HTTP callback for OIDC is new. `HumanSessionService.issue` is the same method the development login calls after success.

The session table's `authenticator_id` check currently allows only `DEVELOPMENT_AUTHENTICATOR_V1`. Supporting OIDC adds a later session-database migration for the new id. It does not migrate the review database and does not change review or coordination services.

The development authenticator remains available for the local laboratory and stays labeled as development-only. Institutional SSO is a separate decision. It is not this contract.

## Implementation slices

Slices 2, 3 and 4 shipped together as one development-authentication release. None of them is production identity. The review UI is protected only with slice 4.

| Slice | Work | Review UI |
|---|---|---|
| 1 | Design contract and ADR | Unchanged |
| 2 | Session domain, repository and service | Unchanged and still anonymous |
| 3 | Development authenticator, login and logout | Historical intermediate state; the gate now covers the queue |
| 4 | Gate all five routes and bind HMAC to `sessionId` | Accepted for the laboratory. Manual validation and deterministic regression passed. Not production identity |

Slice 4 is atomic. Partial route coverage is a bypass. Slices 2 and 3 do not add an anonymous fallback, and they do not present the demo as authenticated.

## Non-goals

No local user accounts, password hashes, self-registration, OIDC, SMART login, RBAC, multi-tenancy, reviewer assignment, attribution, security-audit storage, MCP, or a generic authentication framework. No changes to Gemini, retrieval, FHIR clients or protocol evaluation. No production IAM claim.
