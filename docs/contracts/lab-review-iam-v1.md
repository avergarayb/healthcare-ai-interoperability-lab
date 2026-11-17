# Lab review IAM v1

Laboratory contract for OIDC authentication and organization authorization on the lab-summary human review pages. It is not production healthcare certification, distributed IAM, or a corporate directory integration.

## Routes

When `LAB_REVIEW_IAM_ENABLED` is exactly `true`:

| Route | Rule |
|---|---|
| `GET /lab-summaries` | Live IAM session with `read`. Rows and counts are limited to the bound organization. |
| `GET /lab-summaries/{id}` | Same session and organization. Otherwise the page denies access. |
| `POST /lab-summaries/{id}/decision` | `clinical-reviewer` only, same organization, same-origin, and the server CSRF token. |
| `GET /lab-review-iam/login` | Local page that starts the provider flow. |
| `POST /lab-review-iam/start` | Creates a single-use state, nonce, and PKCE S256 challenge. |
| `POST /lab-review-iam/callback` | Redeems the code from the form body and validates the ID token. A GET does not redeem a code. |
| `POST /lab-review-iam/logout` | Revokes the server session. |

The development authenticator cannot satisfy these routes while IAM is enabled. If `HUMAN_REVIEW_DEVELOPMENT_AUTH_ENABLED` is also true, the configuration is rejected and the routes do not run.

When IAM is disabled, the previous development session remains the only laboratory control for these three review routes. Follow-up review routes are unchanged.

## Identity

The ID token must use RS256, the configured issuer, the client audience, `exp`, `iat`, and the transaction nonce. Lifetime accepted from the token is at most 600 seconds, with 60 seconds of clock skew. RSA keys must be at least 2048 bits and must come from the configured JWKS. Token roles are ignored.

The binding file maps one subject to one organization and one role:

| Role | Read | Decide | Audit on a readable review |
|---|---|---|---|
| `clinical-reviewer` | Yes | Yes | Yes |
| `clinical-auditor` | Yes | No | Yes |
| `clinical-admin` | Only an explicit `read` grant | Never | Only an explicit `audit` grant |

An unknown subject, organization, or missing association is denied. Patient identifiers are not organizations.

## Evidence

`prepare_organization_store` and `assign_review_organization` create and fill `lab_summary_organization`. They do not change the original summary. `prepare_decision_store` also creates `lab_summary_decision_identity`. A decision still does not update the original row and still rejects a second decision.

The identity row stores issuer, subject, organization, role, and the stable local principal `iam-` plus twenty hex characters of SHA-256 over `issuer + newline + subject`.

## Loopback HTTP

Production callers use HTTPS. This laboratory profile may set `LAB_REVIEW_IAM_ALLOW_HTTP_LOOPBACK=true` only when the issuer, discovery URL, JWKS URL, and redirect URI are `http://127.0.0.1` and the service host is loopback. That exception is not acceptable outside this local demonstration. Logout revokes the local session and, when discovery publishes an `end_session_endpoint` under the same issuer, redirects there with the client id and the login URL. The ID token is not stored and is not placed in that URL. The session cookie is `Secure` when the request scheme is HTTPS and stays SameSite=Lax. The single-use transaction cookie is always `Secure` and SameSite=None so the provider's cross-port form POST can return the authorization code without placing it in the browser address bar. Browsers accept that cookie on `http://127.0.0.1` and reject it on any other plain-HTTP host. Keycloak 26.8.1 also marks its own login cookies `Secure` and SameSite=None; there is no supported switch to remove that attribute.

## Not in this contract

Distributed IAM for every service, production multi-tenancy, an external corporate directory, OAuth for every MCP server, Epic or Oracle identity, and an enterprise administration console remain future work. This session does not authorize a model call.
