# Task 050 — Epic Sandbox Authenticated Observation Search by Patient

## WHAT

Implement one authenticated Observation search against `epic-sandbox`, using the Patient context already configured in Task 048.

Target flow:

```text
SMART token in memory (Task 046)
        +
EPIC_SANDBOX_PATIENT_ID (Task 048; no new env)
        +
EpicSandboxCapabilityDiscoveryService
        ↓
FhirServerCapabilities.supports("Observation", SEARCH_TYPE)
        ↓
RoutingService.searchObservations("epic-sandbox", issuedTokenProvider, patientId)
        ↓
FhirService.searchObservationsByPatientWithCount(patientId, 5)
        ↓
GET /Observation?patient={id}&_count=5
Authorization: Bearer <token>
        ↓
FhirObservationSearchResult
        ↓
blind lab
```

The task must stop after proving one authenticated Observation search by the configured Patient.

---

## WHY

Task 049 proved the equivalent authenticated Condition search against Epic using the existing vendor-neutral routing and FHIR layers.

Oracle Task 038 established the generic Observation-search path:

```text
RoutingService.searchObservations(...)
        ↓
FhirService.searchObservationsByPatientWithCount(id, 5)
```

Task 048 established the Epic Patient context:

```text
PatientContextSource.CONFIGURED
EPIC_SANDBOX_PATIENT_ID
```

Task 047 established Epic runtime capability discovery through:

```text
EpicSandboxCapabilityDiscoveryService
        ↓
FhirCapabilityDiscoveryService
        ↓
FhirServerCapabilities
```

Task 050 must prove that the same vendor-neutral Observation search operates against Epic with the existing SMART token and configured Patient context.

---

# 1. HARD BOUNDARIES

## In scope

Only:

- `epic-sandbox`;
- authenticated Observation search;
- configured Patient context from Task 048;
- SMART access token from Task 046;
- runtime Observation SEARCH capability from Task 047;
- existing generic Observation-search abstractions;
- one Observation search operation;
- blind lab;
- local tests;
- opt-in Epic LiveIT.

## Explicitly out of scope

Do not implement:

- Patient search;
- Patient read;
- Condition search;
- Condition read;
- DiagnosticReport;
- MedicationRequest;
- snapshot;
- projection;
- `ModelBoundaryContract`;
- agent;
- LLM;
- `ai-service`;
- Production Epic;
- confidential OAuth;
- new SMART flow;
- Epic-specific Observation client;
- cache;
- new Patient ID configuration.

---

# 2. FIRST STEP — INSPECT EXISTING CODE

Before implementation, Cursor must inspect:

```text
RoutingService.searchObservations
FhirObservationSearchOutcome
FhirObservationSearchResult
FhirObservationSearchResults
OracleSandboxObservationSearchService
EpicSandboxConditionSearchService
EpicSandboxCapabilityDiscoveryService
EpicSandboxPatientContextService
```

Also inspect:

```text
Task 038 Oracle Observation search
Task 049 Epic Condition search
```

Reuse the established generic patterns.

Do not create a second Observation-search architecture.

---

# 3. PATIENT CONTEXT

Reuse the Patient context established by Task 048.

Do not add another environment variable.

The Patient ID remains:

```text
EPIC_SANDBOX_PATIENT_ID
```

with:

```text
PatientContextSource.CONFIGURED
```

Do not accept an arbitrary Patient ID from the HTTP endpoint.

If the configured Patient ID is absent or empty:

```text
PATIENT_CONTEXT_NOT_CONFIGURED
```

Return:

```text
HTTP 409
```

and perform:

```text
ZERO Observation HTTP requests
```

Do not search for a Patient.

Do not invent, guess, enumerate, or scrape a Patient ID.

The real Patient ID exists only in local `.env`.

---

# 4. SMART AUTHENTICATION

Reuse the existing:

```text
IssuedAccessTokenProvider
```

from Task 046.

Do not implement another authentication flow.

Do not add:

- confidential OAuth;
- client secret;
- new callback;
- new login;
- token persistence;
- refresh implementation.

If no usable token is available:

```text
AUTHENTICATION_REQUIRED
```

Return:

```text
HTTP 401
```

and perform:

```text
ZERO Observation HTTP requests
```

Never expose the token.

Because Epic standalone SMART authentication from Task 046 ended with:

```text
hasPatient=false
```

do not derive Patient context from `fhirUser` or SMART launch context.

---

# 5. CAPABILITY CHECK

Before the Observation HTTP operation, use the capability result from Task 047:

```text
EpicSandboxCapabilityDiscoveryService
        ↓
FhirServerCapabilities
```

Check:

```java
capabilities.supports("Observation", SEARCH_TYPE)
```

If Observation search is not advertised:

```text
CAPABILITY_UNSUPPORTED
```

Return:

```text
HTTP 409
```

and perform:

```text
ZERO Observation HTTP requests
```

Do not fall back to:

- Observation read;
- Patient search;
- another resource.

The runtime `CapabilityStatement` is authoritative.

Do not infer support from Epic documentation or application registration.

---

# 6. CRITICAL ROUTING RULE

Do not use:

```java
RoutingService.discoverCapabilities("epic-sandbox")
```

Task 047 established that this profile is SMART-authenticated and the generic routing discovery path may attach the synthetic `smart-lab` token.

Capability discovery must continue through:

```text
EpicSandboxCapabilityDiscoveryService
        ↓
temporary NONE metadata profile
        ↓
FhirCapabilityDiscoveryService
        ↓
FhirServerCapabilities
```

Task 050 only consumes that vendor-neutral result.

Do not modify generic routing to accommodate Epic.

---

# 7. OBSERVATION SEARCH QUERY

Reuse the exact generic query already used by Oracle and exposed through:

```java
RoutingService.searchObservations(...)
```

The query semantics are:

```text
patient + _count=5
```

with:

```text
NO category
```

The logical HTTP operation is:

```http
GET /Observation?patient={id}&_count=5
Authorization: Bearer <token>
```

Do not add:

```text
category=
```

Do not add an Observation code.

Do not add Epic-specific parameters.

Do not change the generic query because the destination is Epic.

There must be no:

```java
if (epic)
```

inside `FhirService`, query construction, or timeout handling.

---

# 8. `_count=5` SEMANTICS

The `_count=5` parameter is an operational request to the FHIR server.

It is not a guaranteed five-record ceiling.

Oracle already demonstrated that:

```text
_count=5
```

can result in more than five returned resources.

Therefore Task 050 must not:

- assume exactly five Observations;
- implement client-side retention of five;
- treat five as a clinical ranking;
- introduce projection behavior;
- modify snapshot behavior.

The later controlled projection layer owns the retention ceiling.

---

# 9. EPIC-SPECIFIC QUERY MATIZ

Task 050 must use the generic:

```text
patient + _count=5
```

query.

Do not invent an Epic-specific Observation category or code.

If Epic sandbox rejects the generic query:

1. preserve the actual HTTP/outcome information;
2. use the existing generic Observation-search outcome/error mapping;
3. expose only safe diagnostics in the blind lab;
4. do not add `if Epic` query logic;
5. do not silently alter the query.

Any Epic-specific query variation would require a separate design decision and is outside Task 050.

---

# 10. FhirService BOUNDARY

Do not modify `FhirService` with Epic-specific logic.

The existing generic method:

```text
FhirService.searchObservationsByPatientWithCount(patientId, 5)
```

must remain sufficient.

Do not add:

```text
searchEpicObservations(...)
EpicObservationService
EpicFhirService
```

Do not modify:

```text
FhirClientFactory.SOCKET_TIMEOUT_MS = 60_000
```

No Epic-specific timeout is permitted.

`FhirService` must remain vendor-neutral and must not import:

```text
vendor
capability
SMART
snapshot
projection
modelboundary
agentstub
```

---

# 11. NO EPIC-SPECIFIC CLIENT

Do not create:

```text
EpicObservationClient
EpicObservationSearch
EpicObservationService
EpicFhirService
```

The architecture must remain:

```text
vendor.epic
    ↓
RoutingService
    ↓
FhirService
    ↓
HAPI FHIR
```

---

# 12. EXPECTED OUTCOMES

Reuse the existing generic Observation-search outcome model.

## Success

```text
SUCCEEDED
```

HTTP:

```text
200
```

An empty Bundle is still successful:

```text
hasEntries=false
```

There is no `EMPTY` outcome.

The lab may show:

```text
status=SUCCESS
httpStatus=200
destination=epic-sandbox
resourceType=Observation
hasEntries=false
```

or the exact safe equivalent of the existing result model.

## Patient context missing

```text
PATIENT_CONTEXT_NOT_CONFIGURED
```

HTTP:

```text
409
```

Zero Observation HTTP requests.

## Authentication required

```text
AUTHENTICATION_REQUIRED
```

HTTP:

```text
401
```

Zero Observation HTTP requests.

## Authentication rejected

Reuse:

```text
AUTHENTICATION_REJECTED
```

HTTP:

```text
401
```

No fallback.

## Authorization denied

```text
AUTHORIZATION_DENIED
```

HTTP:

```text
403
```

No fallback.

## Capability unsupported

```text
CAPABILITY_UNSUPPORTED
```

HTTP:

```text
409
```

Zero Observation HTTP requests.

## Dependency failure

Reuse the existing generic dependency/error mapping:

```text
HTTP 502
```

Do not create an Epic-specific taxonomy.

---

# 13. LAB ENDPOINT

Add:

```http
GET /epic/sandbox/fhir/observation-search
```

Follow the existing blind lab patterns from:

```text
GET /oracle/sandbox/fhir/observation-search
GET /epic/sandbox/fhir/condition-search
```

Safe output may include:

```text
status
httpStatus
destination
resourceType
hasEntries
```

Never expose:

- Patient ID;
- access token;
- Authorization header;
- raw FHIR Bundle;
- Observation JSON;
- Observation codes;
- Observation values;
- units;
- clinical text;
- dates;
- performer;
- encounter;
- subject;
- identifiers.

The purpose is to demonstrate that the search succeeded, not to expose clinical data.

---

# 14. NO OBSERVATION READ

Task 050 is an Observation **search**, not an Observation read.

Do not implement:

```http
GET /Observation/{id}
```

Do not consume Observation IDs from search results.

Do not create Observation context.

---

# 15. NO PATIENT SEARCH / READ

Do not add:

```http
GET /Patient?...
```

or another:

```http
GET /Patient/{id}
```

The Patient context/read has already been established by Task 048.

No fallback is allowed for:

- missing Patient context;
- authentication failure;
- authorization failure;
- unsupported Observation search;
- Observation dependency failure.

---

# 16. TEST STRATEGY

## Default tests

Normal:

```text
*Test.java
*IT.java
```

must not require Epic network access.

## Unit tests

Cover at least:

1. configured Patient context is reused;
2. missing Patient context returns `PATIENT_CONTEXT_NOT_CONFIGURED` / 409;
3. missing Patient context causes zero Observation HTTP;
4. missing token returns `AUTHENTICATION_REQUIRED` / 401;
5. missing token causes zero Observation HTTP;
6. `supports("Observation", SEARCH_TYPE)` is checked before clinical HTTP;
7. unsupported Observation search returns `CAPABILITY_UNSUPPORTED` / 409;
8. unsupported capability causes zero Observation HTTP;
9. successful capability check delegates to `RoutingService.searchObservations(...)`;
10. the generic Observation-search result is preserved;
11. empty Bundle is successful with `hasEntries=false`;
12. no `EMPTY` outcome is introduced;
13. authentication rejection uses the generic 401 outcome;
14. authorization denial uses the generic 403 outcome;
15. dependency failure uses the generic 502 mapping;
16. no Patient search occurs;
17. no Patient read occurs;
18. no Observation read occurs.

---

# 17. HTTP-LEVEL TEST

If the repository has a reusable local HTTP test-server/mock pattern, verify the generic request:

```http
GET /Observation?patient={test-id}&_count=5
Authorization: Bearer <synthetic-token>
```

Use only synthetic test data.

Assert:

- HTTP method = GET;
- resource = Observation;
- query contains Patient and `_count=5`;
- query contains no category;
- Authorization header is present;
- no Patient search occurs;
- no Patient read occurs;
- no Observation read occurs;
- generic Observation-search result is produced;
- raw Bundle is not exposed by the lab.

---

# 18. LIVE TEST

Create/adapt:

```text
*LiveIT.java
```

Epic live execution must be opt-in:

```powershell
$env:EPIC_SANDBOX_LIVE_IT="true"
```

Without the flag:

```text
SKIPPED
```

with zero Epic network access.

LiveIT must:

1. reuse SMART authentication from Task 046;
2. reuse Patient context from Task 048;
3. reuse capability discovery from Task 047;
4. verify Observation SEARCH capability;
5. execute one authenticated Observation search;
6. verify the generic result;
7. never print Patient ID;
8. never print token;
9. never print raw Observation JSON;
10. never print clinical values, codes, or text.

Because Maven LiveIT cannot perform the browser-based Epic login, if no usable token/session is available, diagnose the existing:

```text
AUTHENTICATION_REQUIRED
```

or:

```text
PATIENT_CONTEXT_NOT_CONFIGURED
```

condition as applicable rather than inventing authentication.

---

# 19. EPIC SCOPES / CAPABILITYSTATEMENT MATIZ

Do not assume Observation search is available merely because the Epic app was configured for clinical APIs.

Use the runtime:

```text
FhirServerCapabilities
```

from Task 047 and check:

```java
supports("Observation", SEARCH_TYPE)
```

If the issued SMART token does not authorize the operation, preserve the existing generic authentication/authorization outcome.

Do not add confidential OAuth.

Do not modify Task 046 as part of Task 050.

---

# 20. URL / HOST BOUNDARY

Do not hardcode:

```text
https://fhir.epic.com
```

or any new Epic host under `vendor.epic`.

Reuse the configured Epic base URL.

Do not introduce another Epic base URL configuration.

---

# 21. NO CACHE

Do not introduce caching of:

- capabilities;
- Observation results;
- Patient context;
- tokens.

Keep the existing cache-rejected architecture.

---

# 22. DOCUMENTATION / PROGRESS

Update:

```text
docs/progress/progress-log.md
```

with safe evidence, for example:

```text
Task 050 — Epic Sandbox Authenticated Observation Search by Patient
status=SUCCESS
destination=epic-sandbox
resourceType=Observation
httpStatus=200
hasEntries=true
```

The exact runtime value must be used.

Do not include:

- Patient ID;
- token;
- raw Bundle;
- Observation JSON;
- codes;
- values;
- clinical text.

---

# 23. GIT

Branch:

```text
feature/epic-sandbox-observation-search
```

Commit:

```text
feat: add Epic sandbox authenticated Observation search by Patient
```

Never commit:

```text
.env
```

Never commit secrets, tokens, client IDs, or real Patient IDs.

---

# 24. VALIDATION

Run normal Maven verification.

For PowerShell:

- do not use `&&`;
- use `curl.exe`.

Keep local tests separate from Epic LiveIT.

Live testing must remain explicit and opt-in.

---

# 25. ACCEPTANCE CRITERIA

- [ ] Existing SMART authentication from Task 046 is reused.
- [ ] Existing configured Patient context from Task 048 is reused.
- [ ] No new Patient ID environment variable is added.
- [ ] `EPIC_SANDBOX_PATIENT_ID` remains the only configured Patient context.
- [ ] `PatientContextSource.CONFIGURED` is reused.
- [ ] Existing `EpicSandboxCapabilityDiscoveryService` is reused.
- [ ] `FhirServerCapabilities` is reused.
- [ ] `supports("Observation", SEARCH_TYPE)` is checked before clinical HTTP.
- [ ] `RoutingService.searchObservations(...)` is reused.
- [ ] `FhirService.searchObservationsByPatientWithCount(id, 5)` is reused.
- [ ] No Epic-specific Observation client/service is created.
- [ ] No Epic-specific logic is added to `FhirService`.
- [ ] No Epic-specific timeout is added.
- [ ] Query remains `patient + _count=5`.
- [ ] No category is added.
- [ ] `_count=5` is treated as a request, not a retention ceiling.
- [ ] Empty Bundle is `SUCCEEDED` with `hasEntries=false`.
- [ ] No `EMPTY` outcome is introduced.
- [ ] If Epic rejects the generic query, the existing generic outcome/error path is used; no `if Epic` workaround is added.
- [ ] Missing Patient context returns 409.
- [ ] Missing Patient context causes zero Observation HTTP.
- [ ] Missing authentication returns 401.
- [ ] Missing authentication causes zero Observation HTTP.
- [ ] Unsupported Observation SEARCH returns 409.
- [ ] Unsupported capability causes zero Observation HTTP.
- [ ] Authentication rejection uses the generic 401 mapping.
- [ ] Authorization denial uses the generic 403 mapping.
- [ ] Dependency failure uses the generic 502 mapping.
- [ ] No Patient search is implemented.
- [ ] No Patient read is implemented.
- [ ] No Observation read is implemented.
- [ ] Lab endpoint is `GET /epic/sandbox/fhir/observation-search`.
- [ ] Lab output is blind.
- [ ] Patient ID is not exposed.
- [ ] Token is not exposed.
- [ ] Observation JSON is not exposed.
- [ ] Observation codes/values/text are not exposed.
- [ ] Default tests do not access Epic.
- [ ] LiveIT requires `EPIC_SANDBOX_LIVE_IT=true`.
- [ ] No new Epic host is hardcoded.
- [ ] Generic timeout remains `60_000` ms.
- [ ] No cache is introduced.
- [ ] No snapshot/projection/contract/agent/LLM/`ai-service` work is introduced.

---

# 26. CONCEPT

Task 050 proves:

```text
configured Patient context
        +
SMART authentication
        +
runtime Observation SEARCH capability
        ↓
generic Observation search
        ↓
Epic FHIR
        ↓
controlled blind result
```

The vendor-specific layer identifies the Epic destination and supplies the already-established authentication/context inputs.

The actual Observation search remains:

```text
RoutingService
    ↓
FhirService
    ↓
HAPI FHIR
```

No Epic-specific clinical service is introduced.

---

# 27. STOP CONDITION

Once this is proven:

```text
SMART token
    +
configured Patient context
    +
Observation SEARCH capability
        ↓
RoutingService.searchObservations(...)
        ↓
FhirService.searchObservationsByPatientWithCount(id, 5)
        ↓
GET /Observation?patient={id}&_count=5
        ↓
FhirObservationSearchResult
        ↓
blind lab
```

**STOP.**

Do not continue into:

```text
Patient search
Patient read
Condition
DiagnosticReport
MedicationRequest
snapshot
projection
contract
agent
LLM
ai-service
```

Those belong to later tasks and are explicitly outside Task 050.
