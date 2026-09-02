# Task 035 — Oracle Health Authenticated FHIR Read

## Status
**Planned**

### Prerequisites completed
- Task 031 — FHIR Capability Discovery
- Task 032 — Oracle Health Sandbox Readiness
- Task 033 — Oracle Health Secure Sandbox SMART Authentication
- Task 034 — Oracle Health Real Capability Discovery

---

## 1. Objective

Implement the first **authenticated FHIR read operation against the real Oracle Health Millennium sandbox**.

The complete path to prove is:

```text
SMART authentication
→ Access token
→ AccessTokenProvider
→ Generic FHIR client
→ Authenticated HTTP request
→ Oracle Health Millennium
→ Safe diagnostic result
```

Task 035 must **not assume a Patient context**, because Task 033 ended with:

```text
hasAccessToken=true
hasPatient=false
```

---

## 2. Why this task exists

Task 033 proved:

```text
SMART discovery
→ Authorization Code
→ PKCE S256
→ Oracle login
→ Token exchange
→ HTTP 200
```

Task 034 proved:

```text
GET /metadata
→ Oracle Health Millennium
→ HTTP 200
→ CapabilityStatement
→ FhirServerCapabilities
```

Task 035 answers the missing question:

> Can the issued SMART access token actually be used by the generic FHIR layer to execute a real authorized FHIR read?

---

## 3. Architectural principle

Keep these boundaries separate:

```text
SMART authentication
≠
FHIR operation
≠
Oracle vendor implementation
```

Desired dependency flow:

```text
Oracle authentication
        ↓
IssuedAccessTokenProvider
        ↓
AccessTokenProvider SPI
        ↓
Generic FHIR operation
        ↓
Routing / resilience / audit
        ↓
Oracle FHIR endpoint
```

`FhirService` must not import Oracle classes.

---

## 4. Scope

### In scope

- Use a real access token issued by Task 033.
- Attach it as a Bearer credential to a FHIR request.
- Execute one safe authenticated read/search operation.
- Reuse `AccessTokenProvider`.
- Reuse generic routing/resilience infrastructure.
- Distinguish missing token, 401, 403 and dependency failures.
- Use runtime capabilities where applicable.
- Add opt-in Oracle live validation.
- Prevent token and clinical payload leakage.

### Out of scope

- EHR launch.
- Patient launch context.
- Write operations.
- Patient create/update/delete.
- Token refresh.
- Persistent token storage.
- `client_secret_basic`.
- `private_key_jwt`.
- Epic implementation.
- AI agent functionality.

---

## 5. First operation: authenticated Patient search

Because there is no SMART Patient context, do not assume:

```http
GET /Patient/{patientId}
```

The preferred first operation is a controlled search:

```http
GET {base-url}/Patient
Authorization: Bearer <access-token>
Accept: application/fhir+json
```

The actual Oracle response is evidence. Do not assume success.

Possible outcomes:

- `200 OK` → authenticated operation succeeded.
- `401` → token invalid, expired or rejected.
- `403` → token valid but insufficient permission.
- `404` → resource/endpoint mismatch.
- `429` → rate limited.
- `5xx` → dependency failure.

The live validation must minimize clinical data exposure.

---

## 6. Runtime capability gate

Task 034 discovered Oracle runtime support for:

```text
Patient:
- read
- search-type
- create
```

The generic model should be queried before the operation:

```java
capabilities.supports("Patient", FhirInteraction.SEARCH_TYPE)
```

Do not hardcode Oracle capabilities.

If the runtime model does not support the interaction, return a local capability diagnosis instead of sending an unsupported operation.

Concept:

```text
Vendor profile ≠ runtime capability
```

---

## 7. Authentication boundary

The generic FHIR layer receives credentials only through:

```java
AccessTokenProvider
```

It must not directly depend on:

```text
OracleSandboxAuthenticationService
```

Correct:

```text
Oracle auth → AccessTokenProvider → generic FHIR operation
```

Incorrect:

```text
FhirService → if Oracle → Oracle authentication service
```

No Oracle-specific branching inside generic FHIR operations.

---

## 8. Token lifecycle

Required behavior:

```text
No token      → AUTHENTICATION_REQUIRED
Expired token → AUTHENTICATION_REQUIRED
Valid token   → attempt FHIR request
```

Do not fabricate or silently refresh tokens.

Tokens must never be:

- committed;
- persisted;
- printed;
- returned by diagnostics;
- included in exception messages.

---

## 9. Result model

Create or extend a safe explicit diagnostic result.

Suggested outcomes:

### AUTHENTICATED_READ_SUCCEEDED

Oracle returned a valid FHIR response.

### AUTHENTICATION_REQUIRED

No usable token exists.

### AUTHENTICATION_REJECTED

Oracle rejected authentication, for example HTTP 401.

### AUTHORIZATION_DENIED

The token was accepted but permissions are insufficient, for example HTTP 403.

### CAPABILITY_UNSUPPORTED

The runtime capability model does not declare the interaction.

### DEPENDENCY_FAILURE

Network/server/rate-limit failures mapped through the existing taxonomy.

The result must never contain the token.

---

## 10. Clinical payload handling

This is the first task that may receive real clinical FHIR data.

### Logs

Do not log:

- Patient JSON;
- names;
- identifiers;
- addresses;
- birth dates;
- phone numbers;
- tokens.

### Live tests

Assert safe metadata such as:

- result category;
- FHIR resource type;
- Bundle vs Patient;
- safe response status.

Do not dump clinical payloads to the console.

---

## 11. Generic operation design

Prefer extending the existing generic abstraction.

Conceptual example:

```java
FhirAuthenticatedReadResult result =
    routingService.searchPatients("oracle-health-sandbox");
```

The exact API can be adapted to the current architecture.

Required conceptual composition:

```text
Destination selection
+
Generic Patient SEARCH_TYPE
+
AccessTokenProvider
```

Do not create an Oracle-specific Patient HTTP client.

---

## 12. Routing and resilience

This is a real remote dependency operation and should reuse the existing dependency policy:

```text
Rate limiter
→ Bulkhead
→ Circuit breaker
→ Retry
→ FHIR operation
```

Do not retry:

```text
401
403
AUTHENTICATION_REQUIRED
CAPABILITY_UNSUPPORTED
```

Transient failures may continue through the existing resilience policy.

Do not create:

```text
OraclePatientRetryExecutor
```

---

## 13. Audit and observability

Add a safe operation-level event, for example:

```text
PATIENT_SEARCH
```

Include only:

```text
destination
operation
outcome
status
duration
```

Never include:

- Authorization header;
- access token;
- Patient JSON;
- Bundle JSON.

Observability describes the operation, not clinical content.

---

## 14. Interactive lab flow

Expected validation:

### Step 1
Configure `.env`.

### Step 2
Start the integration service.

### Step 3
Run Task 033 SMART authorization.

### Step 4
Confirm:

```text
access token issued
```

without showing the token.

### Step 5
Execute the authenticated FHIR read endpoint.

### Step 6
Receive a safe diagnosis:

```text
AUTHENTICATED_READ_SUCCEEDED
AUTHENTICATION_REQUIRED
AUTHENTICATION_REJECTED
AUTHORIZATION_DENIED
CAPABILITY_UNSUPPORTED
DEPENDENCY_FAILURE
```

---

## 15. Lab endpoint

A minimal diagnostic endpoint may be added, conceptually:

```http
GET /oracle/sandbox/fhir/patient-search
```

It should:

1. verify Oracle profile readiness;
2. verify a usable token;
3. verify runtime capability when available;
4. execute the generic operation;
5. return only a safe diagnostic result.

This is a laboratory endpoint, not a production clinical API.

Full clinical payload rendering is outside this task.

---

## 16. Architecture boundaries

Add or update tests proving:

### Generic FHIR layer

Must not import:

```text
vendor.oracle
```

### No hardcoded Oracle hosts

Production Java must not contain Oracle/Cerner hosts.

Endpoint identity comes from configuration/discovery.

### No token leakage

Tokens must not appear in:

- `toString()`;
- exceptions;
- diagnostics;
- logs.

### No Oracle Patient client

Do not add:

```text
OraclePatientClient
```

The operation remains generic.

---

## 17. Unit tests

At minimum:

### Token handling

- no token → `AUTHENTICATION_REQUIRED`;
- expired token → `AUTHENTICATION_REQUIRED`;
- valid token → operation can proceed.

### Capability gate

- Patient + SEARCH_TYPE supported → proceed;
- Patient absent → `CAPABILITY_UNSUPPORTED`;
- interaction absent → `CAPABILITY_UNSUPPORTED`.

### Error mapping

- 401 → `AUTHENTICATION_REJECTED`;
- 403 → `AUTHORIZATION_DENIED`;
- connection failure → existing connection category;
- timeout → existing timeout category;
- server failure → existing server category.

### Security

Assert that token values do not appear in diagnostics, exceptions or `toString()`.

---

## 18. Integration tests

### Standard integration profile

Must run without contacting Oracle.

Verify:

```text
Oracle disabled → no Oracle network call
```

Existing HAPI integration tests must remain green.

### Oracle live test

Create an explicit opt-in test, for example:

```text
OracleHealthSandboxAuthenticatedPatientSearchLiveIT
```

It must:

1. require explicit enablement;
2. require a valid runtime authentication mechanism;
3. avoid printing clinical data;
4. assert the safe result.

If browser authentication is unavailable to Maven, fail clearly as:

```text
AUTHENTICATION_REQUIRED
```

Do not fabricate credentials.

---

## 19. Documentation

Document the real validation chain:

```text
Task 033
SMART authentication
        ↓
Access token

Task 034
FHIR /metadata
        ↓
Runtime capabilities

Task 035
Authenticated FHIR operation
        ↓
First clinical interoperability proof
```

Also document:

```text
Authenticated
≠
Authorized for every resource
```

and:

```text
FHIR capability
≠
SMART scope authorization
```

Successful operation requires both:

```text
Server capability
+
Token authorization
```

---

## 20. Acceptance criteria

Task 035 is complete when:

- [ ] A Task 033 token is consumed through `AccessTokenProvider`.
- [ ] The generic FHIR layer executes an authenticated Oracle request.
- [ ] `FhirService` contains no Oracle-specific branching.
- [ ] Runtime capability discovery can prevent unsupported operations.
- [ ] Missing/expired token produces `AUTHENTICATION_REQUIRED`.
- [ ] HTTP 401 and 403 are distinguished.
- [ ] Dependency failures remain aligned with the existing taxonomy.
- [ ] Tokens and clinical payloads are not leaked.
- [ ] Default tests do not contact Oracle.
- [ ] Oracle live validation is explicitly opt-in.
- [ ] `mvn clean test` passes.
- [ ] `mvn clean verify -Pintegration` passes.
- [ ] Architecture boundary tests pass.
- [ ] No write operation is implemented.

---

## 21. Explicit non-goals

Do not implement:

```text
POST /Patient
PUT /Patient
DELETE /Patient
```

even though runtime capabilities may declare `create`.

Capability discovery does not generate application features.

Also do not add:

- AI reasoning;
- summarization;
- embeddings;
- RAG;
- agents.

Those come after safe, authorized clinical interoperability is established.

---

## 22. Expected outcome

After Task 035:

```text
REAL ORACLE HEALTH

Configuration                 ✅
SMART Discovery               ✅
Authorization Code + PKCE     ✅
Access Token                  ✅
FHIR Capability Discovery     ✅
Authenticated FHIR Read       ← Task 035
```

The task must distinguish three independent boundaries:

```text
Authentication succeeded
        ≠
FHIR authorization succeeded
        ≠
FHIR operation succeeded
```

---

## 23. Future direction

After Task 035, future decisions can be evidence-based:

1. Controlled Patient read using an approved sandbox identifier.
2. EHR launch and Patient context.
3. Additional generic FHIR resource reads.
4. Normalized clinical data layer.
5. Heterogeneous EHR adapters.
6. AI agent over authorized normalized data.
7. Epic implementation.

Do not implement these in Task 035.

---

## Proposed commit message

```text
feat: add Oracle Health authenticated FHIR read
```
