# Interactive SMART authorization

Task 033 adds an explicit Authorization Code + PKCE S256 boundary and a minimal local callback.

Browser login is not routed through rate-limit → bulkhead → circuit → retry. The first authenticated Patient search after a token is issued is Task 035 (`GET /oracle/sandbox/fhir/patient-search`). A controlled Patient read (Task 036) is `GET /oracle/sandbox/fhir/patient` and requires an explicit sandbox Patient ID. An authenticated Condition search by that Patient (Task 037) is `GET /oracle/sandbox/fhir/condition-search`.

Read this after [fhir-smart-real-world-readiness.md](fhir-smart-real-world-readiness.md). Oracle Health wiring: [vendors/oracle-health.md](vendors/oracle-health.md).

Java does **not** hardcode Cerner/Oracle hosts. Authorization and token URLs come from the configured `/.well-known/smart-configuration`.

## Flow

```text
GET /oracle/sandbox/smart/start
        ↓
SMART discovery  (ORACLE_HEALTH_SANDBOX_SMART_CONFIGURATION_URL)
        ↓
authorization URL
        ↓
browser login / consent
        ↓
GET /smart/callback?code=...&state=...
        ↓
validate state / expiry / single-use
        ↓
POST token  (code + code_verifier, public PKCE only)
        ↓
Result A: AccessToken issued
   or
Result B: explicit confidential-auth diagnosis
```

`SmartTokenProvider.authorizeSynthetically` remains the **smart-lab** 302 shortcut. It is not used for Oracle Health.

## Local pages

| URL | Purpose |
|---|---|
| `http://localhost:8081/oracle/sandbox/smart` | short instructions |
| `http://localhost:8081/oracle/sandbox/smart/start` | discover SMART and show the authorization URL |
| `http://localhost:8081/smart/callback` | registered redirect; validates callback and attempts token exchange |
| `http://localhost:8081/oracle/sandbox/fhir/patient-search` | after a token is issued: safe authenticated Patient search diagnosis |
| `http://localhost:8081/oracle/sandbox/fhir/patient` | after a token and `ORACLE_HEALTH_SANDBOX_PATIENT_ID`: controlled Patient read diagnosis |
| `http://localhost:8081/oracle/sandbox/fhir/condition-search` | after a token and Patient ID: safe authenticated Condition search by Patient |

These are lab pages, not a product frontend. They never print access tokens, authorization codes, PKCE verifiers, or secrets.

## Pending session

`PendingAuthorizationSession` holds `state`, `code_verifier`, token endpoint, client id, redirect URI, and discovered `token_endpoint_auth_methods_supported` for about 10 minutes. `consume(state)` is one-shot.

Failed `state` / missing code / expired session is rejected **before** the token POST.

OAuth authorize errors (`error`, `error_description`) invalidate the session and do not call the token endpoint.

## Token-exchange diagnosis

Oracle Code sandbox discovery currently advertises:

```text
token_endpoint_auth_methods_supported:
  client_secret_basic
  private_key_jwt
```

It does **not** advertise `none`. It may still list `client-public` in `capabilities`. This lab attempts public PKCE anyway.

If the token POST is rejected, `SmartTokenExchangeDiagnoser` reports one of:

| Incompatibility | Meaning | Next change |
|---|---|---|
| `CONFIDENTIAL_CLIENT_REQUIRED` | Discovery lists confidential methods only | Confirm the registered app type; implement that mode later |
| `CLIENT_SECRET_BASIC` | Error/discovery names HTTP Basic | Implement `client_secret_basic` later. Do not invent a secret |
| `PRIVATE_KEY_JWT` | Error/discovery names JWT assertion | Implement `private_key_jwt` later. Do not fake a JWT |
| `TOKEN_ENDPOINT_REJECTED` | Other OAuth token error | Inspect the error code |
| `AUTHORIZATION_REJECTED` | Authorize redirect had `error=` | Fix consent/scope/redirect; no token POST happened |

## Configure `.env`

Copy [`.env.example`](../../.env.example) to `.env` at the repository root (gitignored):

```text
ORACLE_HEALTH_SANDBOX_ENABLED=true
ORACLE_HEALTH_SANDBOX_CLIENT_ID=<Oracle-issued client id>
ORACLE_HEALTH_SANDBOX_BASE_URL=<FHIR base from Oracle>
ORACLE_HEALTH_SANDBOX_AUD=<same FHIR base unless Oracle says otherwise>
ORACLE_HEALTH_SANDBOX_REDIRECT_URI=http://localhost:8081/smart/callback
ORACLE_HEALTH_SANDBOX_SCOPE=openid profile fhirUser online_access user/Patient.read
ORACLE_HEALTH_SANDBOX_SMART_CONFIGURATION_URL=<.../.well-known/smart-configuration>
```

`mvn spring-boot:run` from `services/fhir-integration-service` loads that file. Tests do not.

Register the redirect URI **exactly** as `http://localhost:8081/smart/callback` in the Oracle application.

## Run the live flow

```bash
cd services/fhir-integration-service
mvn spring-boot:run
```

1. Open `http://localhost:8081/oracle/sandbox/smart/start`
2. Open the printed authorization URL in a browser
3. Complete Oracle login/consent
4. Wait for the redirect to `/smart/callback`
5. Read Result A or Result B on that page

Automated live IT (`mvn verify -Poracle-live` + `ORACLE_HEALTH_LIVE_IT=true`) still proves discovery + URL generation only. Human login cannot be scripted. Synthetic `lab-oauth` proves callback → token in `SmartAuthorizationCoordinatorIT`.
