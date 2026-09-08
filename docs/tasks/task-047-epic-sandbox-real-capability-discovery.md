# Task 047 — Epic Sandbox Real Capability Discovery

## 1. WHAT

Implement the first real FHIR capability-discovery operation against the configured `epic-sandbox` profile.

The task must perform exactly one real:

```http
GET /metadata
```

against the Epic sandbox FHIR R4 service and normalize the response through the existing vendor-neutral capability-discovery flow:

```text
Epic sandbox
    ↓
temporary unauthenticated metadata profile (only if /metadata is public)
    ↓
FhirCapabilityDiscoveryService
    ↓
FhirServerCapabilities
    ↓
STOP
```

The output of this task is capability metadata only. It must not read or search any clinical resource.

## 2. WHY

Task 046 established that the Epic sandbox SMART Authorization Code + PKCE flow works and that an access token can be issued.

The next interoperability step is to discover the actual FHIR capabilities exposed by the configured Epic sandbox at runtime.

The purpose is to prove that:

- the configured Epic sandbox exposes a FHIR R4 `CapabilityStatement`;
- the existing generic `FhirCapabilityDiscoveryService` can consume it;
- Epic does not require a vendor-specific capability model;
- the normalized result is represented by the existing vendor-neutral `FhirServerCapabilities`;
- capability discovery remains independent from Patient context, clinical snapshot, projection, model boundary, agent, and AI.

The runtime `CapabilityStatement` is the source of truth. Do not infer capabilities from Epic documentation or from the application's configured API list.

# 3. HARD BOUNDARIES

## 3.1 In scope

Only:

- Epic sandbox profile: `epic-sandbox`
- FHIR R4
- one real `GET /metadata`
- existing `FhirCapabilityDiscoveryService`
- existing vendor-neutral `FhirServerCapabilities`
- minimal Epic orchestration needed to invoke generic discovery correctly
- blind lab output containing capability/discovery status
- tests proving the behavior

## 3.2 Explicitly out of scope

Do **not** implement:

- Patient read
- Patient search
- Condition search
- Observation search
- DiagnosticReport search
- MedicationRequest search
- clinical snapshot
- projection
- `ModelBoundaryContract`
- agent stub
- real agent
- LLM
- `ai-service`
- Production Epic
- Epic Connection Hub
- confidential OAuth client
- additional SMART authentication flows
- caching
- new resource allowlists
- new clinical fields

# 4. CRITICAL ROUTING RULE

Do **not** start this task with:

```java
routingService.discoverCapabilities("epic-sandbox")
```

The reason is that `epic-sandbox` is configured with:

```text
SMART_AUTHORIZATION_CODE
```

and the generic routing path may attach the synthetic `smart-lab` token used by the existing test infrastructure.

That token must not be sent to the real Epic `/metadata` endpoint.

Instead, capability discovery for Epic must use the configured Epic base URL and, if Epic exposes `/metadata` publicly, create a temporary metadata-only profile using:

```text
FhirAuthenticationSettings.none()
```

Then delegate to the existing generic:

```text
FhirCapabilityDiscoveryService
```

This is the same architectural pattern already proven with Oracle in Task 034.

Do not modify the global routing behavior merely to make this task work.

# 5. EXPECTED FLOW

## Case A — Epic `/metadata` is public

Preferred path:

```text
GET /epic/sandbox/fhir/capabilities
        ↓
resolve configured epic-sandbox base URL
        ↓
construct temporary FHIR profile:
  baseUrl = configured Epic base URL
  authentication = NONE
        ↓
FhirCapabilityDiscoveryService
        ↓
HTTP GET {baseUrl}/metadata
        ↓
CapabilityStatement
        ↓
FhirServerCapabilities
        ↓
blind lab response
```

The metadata request must contain no invented Bearer token.

There must be exactly one real HTTP request to `/metadata`.

## Case B — Epic `/metadata` requires authentication

Do not silently invent or reuse the SMART access token.

The task is not a second SMART-authentication task.

If `/metadata` rejects unauthenticated access:

1. preserve the existing diagnostic/error model if one exists;
2. expose the failure in the blind lab output;
3. do not fall back to Patient operations;
4. do not turn this task into an authenticated capability-discovery redesign.

If the existing generic discovery service already supports the required authenticated profile without introducing the synthetic token problem, it may be reused, but do not expand the task beyond the minimum necessary behavior.

# 6. ARCHITECTURAL REQUIREMENTS

## 6.1 Reuse generic capability discovery

The existing:

```java
FhirCapabilityDiscoveryService
```

must remain responsible for:

- making the `/metadata` request;
- parsing the FHIR `CapabilityStatement`;
- normalizing it into:
  ```java
  FhirServerCapabilities
  ```

Do not create:

```java
EpicCapabilityStatement
EpicFhirServerCapabilities
EpicCapabilityDiscoveryResult
```

or equivalent vendor-specific capability models.

## 6.2 Epic-specific code

Epic-specific code may only resolve/configure the Epic sandbox invocation boundary.

For example, a thin orchestrator under:

```text
vendor.epic
```

may:

1. resolve the configured `epic-sandbox` base URL;
2. construct the temporary unauthenticated metadata profile when applicable;
3. delegate to `FhirCapabilityDiscoveryService`.

It must not parse or reinterpret the `CapabilityStatement`.

## 6.3 No vendor host hardcoding

Do not introduce:

```java
https://fhir.epic.com
```

or any other Epic host into Java source under:

```text
vendor.epic
```

The Epic base URL must come from configuration.

The implementation must continue to respect the existing `.env` / configuration model.

Do not expose secrets in:

- Java source;
- tests;
- `.env.example`;
- documentation;
- PR descriptions;
- lab output.

# 7. EXISTING GENERIC COMPONENTS TO REUSE

Before implementing anything, inspect the existing project for:

- `FhirCapabilityDiscoveryService`
- `FhirServerCapabilities`
- FHIR client/profile abstractions
- `FhirAuthenticationSettings`
- `FhirClientFactory`
- existing Oracle capability-discovery implementation from Task 034
- existing Epic profile/configuration from Task 046
- existing generic diagnostics/error model
- existing lab controller/page patterns

Do not duplicate an abstraction that already exists.

The implementation should follow the same generic contracts already used by Oracle wherever the behavior is equivalent.

# 8. HTTP OPERATION

The real operation must be:

```http
GET {EPIC_SANDBOX_BASE_URL}/metadata
```

Requirements:

- exactly one request;
- no Patient ID;
- no clinical query;
- no `_count`;
- no `_elements`;
- no resource-specific endpoint;
- no synthetic `smart-lab` token when using the public metadata path;
- no persistence.

Expected successful response:

```text
HTTP 200
Content-Type: application/fhir+json
CapabilityStatement
```

The implementation must not assume HTTP 200 blindly; use the existing generic HTTP/error handling conventions.

# 9. NORMALIZED OUTPUT

The result must be the existing:

```java
FhirServerCapabilities
```

Do not add Epic-specific fields.

The normalized result should expose whatever fields are already defined by the existing model, such as the existing representation of:

- FHIR version;
- resource types;
- interactions;
- server/software metadata;
- discovery status.

Do not expand `FhirServerCapabilities` merely to accommodate Epic.

If a CapabilityStatement field is not represented by the current vendor-neutral model, leave it out rather than creating an Epic-only representation.

# 10. LAB SURFACE

Add:

```http
GET /epic/sandbox/fhir/capabilities
```

The page is a blind interoperability lab.

It should show only:

- discovery status;
- HTTP status when available;
- FHIR version;
- normalized capability summary;
- resource-type/capability counts or equivalent existing normalized metadata;
- useful diagnostics on failure.

It must **not** show:

- Patient ID;
- access token;
- authorization code;
- SMART state;
- raw `CapabilityStatement` JSON;
- raw FHIR JSON;
- clinical resources;
- Patient names;
- clinical values.

The lab page should follow the existing Oracle capability-discovery presentation pattern where practical.

# 11. NO CLINICAL DATA

This task is capability discovery only.

There must be no code path from this task to:

```text
Patient
Condition
Observation
DiagnosticReport
MedicationRequest
```

No clinical snapshot should be invoked.

No projection should be invoked.

No model-boundary contract should be invoked.

No agent should be invoked.

# 12. CONFIGURATION

Use the existing Epic sandbox configuration introduced in Task 046.

The implementation must resolve the base URL from configuration.

Do not add a second Epic base URL configuration unless the existing configuration genuinely cannot support the task.

Do not duplicate:

```text
EPIC_FHIR_BASE_URL
```

or equivalent configuration under another name if it already exists.

Do not put credentials or Patient IDs into new configuration.

# 13. TEST STRATEGY

## 13.1 Default test behavior

Normal unit/integration tests must not require network access to the Epic sandbox.

Epic live access must be opt-in/manual, following the project's existing integration-test conventions.

## 13.2 Unit tests

Add or update tests for:

1. Epic capability-discovery orchestration resolves the configured base URL.
2. Public metadata path constructs an unauthenticated temporary profile.
3. The generic `FhirCapabilityDiscoveryService` is delegated to.
4. No synthetic SMART token is attached to the public metadata request.
5. Successful generic capability discovery is returned as `FhirServerCapabilities`.
6. Failure is propagated using the existing diagnostic/error model.
7. No clinical operation is triggered.

Use mocks/stubs for the generic service where appropriate.

Do not require Epic network access.

## 13.3 HTTP-level test

Where the project already has a reusable local HTTP test server pattern, verify:

```text
GET /metadata
```

is the only request.

The test should assert:

- method = GET;
- path = `/metadata`;
- no Authorization header on the public metadata path;
- successful `CapabilityStatement` parsing;
- normalized `FhirServerCapabilities`.

Do not make the unit test depend on `fhir.epic.com`.

## 13.4 Live/manual test

A live test may be added or documented as opt-in only.

The live test must use the real configured Epic sandbox.

The acceptance evidence should capture only safe metadata such as:

```text
status=SUCCESS
httpStatus=200
fhirVersion=4.0.1
resourceTypes=<count>
```

Do not include:

- token;
- Patient ID;
- raw CapabilityStatement;
- clinical JSON.

# 14. ACCEPTANCE CRITERIA

Task 047 is complete only if all of the following are true:

- [ ] `epic-sandbox` can perform real FHIR capability discovery.
- [ ] The operation is exactly one `GET /metadata`.
- [ ] The Epic base URL comes from configuration.
- [ ] No Epic host is hardcoded in `vendor.epic`.
- [ ] The implementation does not enter generic routing through `RoutingService.discoverCapabilities("epic-sandbox")`.
- [ ] Public `/metadata` uses a temporary profile with `FhirAuthenticationSettings.none()`.
- [ ] No synthetic `smart-lab` token is sent to public Epic metadata.
- [ ] `FhirCapabilityDiscoveryService` performs the actual generic discovery.
- [ ] The response is normalized to the existing vendor-neutral `FhirServerCapabilities`.
- [ ] No `EpicCapabilityStatement` or other Epic-specific capability model exists.
- [ ] No Patient or other clinical resource is read/searched.
- [ ] No snapshot is created.
- [ ] No projection is created.
- [ ] No `ModelBoundaryContract` is created.
- [ ] No agent is called.
- [ ] No LLM is called.
- [ ] No `ai-service` work is introduced.
- [ ] No cache is introduced.
- [ ] The lab surface exposes only safe capability/discovery information.
- [ ] Tokens and Patient IDs are not exposed.
- [ ] Default tests do not require Epic network access.
- [ ] Live testing is opt-in/manual.
- [ ] Existing generic abstractions are reused rather than duplicated.

# 15. EXPECTED LIVE EVIDENCE

For a successful Epic sandbox run, record evidence similar to:

```text
Epic capability discovery
status=SUCCESS
httpStatus=200
fhirVersion=4.0.1
resourceTypes=<runtime count>
```

The exact runtime resource count must come from the actual Epic `CapabilityStatement`.

Do not hardcode or claim a count based on Epic documentation.

The `CapabilityStatement` returned by the running sandbox is authoritative for this task.

# 16. IMPLEMENTATION CHECKLIST FOR CURSOR

1. Inspect Task 034 Oracle capability-discovery implementation.
2. Inspect the current generic `FhirCapabilityDiscoveryService`.
3. Inspect `FhirServerCapabilities`.
4. Inspect Epic configuration introduced by Task 046.
5. Confirm how the configured Epic base URL is resolved.
6. Confirm whether the existing FHIR client abstraction can construct a temporary unauthenticated profile.
7. Implement only the minimal Epic orchestration necessary.
8. Delegate `/metadata` discovery to `FhirCapabilityDiscoveryService`.
9. Add the Epic lab endpoint.
10. Add safe blind lab output.
11. Add unit/local HTTP tests without Epic network access.
12. Run the normal Maven verification.
13. If live testing is available, run it manually against the configured Epic sandbox.
14. Verify that no token, Patient ID, or raw FHIR JSON appears in the output.
15. Update `docs/progress/progress-log.md` with Task 047 evidence.
16. Create the feature branch:
    ```text
    feature/epic-sandbox-capability-discovery
    ```
17. Use the conventional commit:
    ```text
    feat: add Epic sandbox real capability discovery
    ```

# 17. STOP CONDITION

Once:

```text
Epic /metadata
    ↓
FhirCapabilityDiscoveryService
    ↓
FhirServerCapabilities
```

is proven, **STOP**.

Do not continue into Patient context or clinical data.

The next task must be designed separately and only when explicitly requested.
