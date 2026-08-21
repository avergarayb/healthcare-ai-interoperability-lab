# Task 002 — FHIR Client

## Objective

Create the first real FHIR integration capability in `fhir-integration-service`.

The service must connect from Java to the local HAPI FHIR R4 server and retrieve its `CapabilityStatement` using the HAPI FHIR client framework.

This is the first implementation task after the project bootstrap.

## Branch

Create and use:

`feature/fhir-client`

Do not work directly on `main`.

## Teaching Mode — Mandatory

Act as a senior instructor and implementation mentor.

Do not silently implement the task.

Execute the work step by step and explain the work as you proceed, as if you were teaching the developer.

For every significant step, show:

1. What you are doing.
2. Why you are doing it.
3. Which file is being created or modified.
4. The relevant code or configuration change.
5. The command executed.
6. The command result.
7. The Java/FHIR/software-engineering concept being learned.

Do not provide only a final summary.

When introducing a new dependency, explain:
- what the dependency is;
- why it is needed;
- what responsibility it has;
- why it belongs in this service.

When introducing HAPI FHIR APIs/classes, explain their purpose before using them.

If an error occurs:
1. Show the error.
2. Explain the likely cause.
3. Explain the chosen fix.
4. Apply the fix.
5. Re-run the relevant verification.
6. Explain why the fix works.

At the end, provide both:
- a concise final summary; and
- a complete step-by-step execution report.

## Context

Repository:

`healthcare-ai-interoperability-lab`

Initial service:

`services/fhir-integration-service`

Technology:

- Java 21
- Spring Boot 3.5.x
- Maven
- HAPI FHIR
- FHIR R4

Local FHIR server:

`http://localhost:8080/fhir`

The HAPI FHIR server currently exposes FHIR R4 / `4.0.1`.

The Spring Boot application currently runs on:

`http://localhost:8081`

The application is the integration layer. HAPI FHIR is infrastructure.

Do not confuse the two.

## Architecture

For this task, implement only this flow:

```text
fhir-integration-service
        |
        | HAPI FHIR Client
        v
http://localhost:8080/fhir
        |
        v
FHIR R4 CapabilityStatement
```

The application must not expose a new public REST endpoint for this task.

We are first learning how our Java integration service acts as a FHIR client.

## Learning Goals

By the end of this task, the developer should understand:

- What a FHIR client is.
- What `FhirContext` is.
- Why the client must be configured for FHIR R4.
- What `IGenericClient` represents.
- How a FHIR client communicates with a FHIR server.
- How the FHIR server base URL is configured.
- How to retrieve `/metadata` programmatically.
- What a `CapabilityStatement` represents.
- The difference between:
  - our Spring Boot application;
  - the HAPI FHIR client library;
  - the remote/local HAPI FHIR server.
- How to test the integration without requiring a public HTTP endpoint.

## Scope

### In scope

1. Add the minimum HAPI FHIR Java dependencies required to create an R4 client.
2. Create a small FHIR client configuration/component.
3. Configure the FHIR base URL through application configuration.
4. Create a service/component that retrieves the server `CapabilityStatement`.
5. Add tests.
6. Verify communication with the local HAPI FHIR server.
7. Document the implementation.

### Out of scope

Do NOT implement:

- Patient endpoints.
- Patient search.
- Observation search.
- Condition search.
- FHIR CRUD operations beyond what is strictly required to retrieve metadata.
- FHIR resource persistence.
- HL7 v2.
- SMART on FHIR.
- OAuth.
- Epic.
- Oracle Health.
- AI.
- Python.
- RAG.
- Agents.
- MCP.
- Kubernetes.
- additional microservices.
- API Gateway.

These will be introduced later.

## Dependency Requirements

Use HAPI FHIR's supported client framework for R4.

Select the minimum appropriate HAPI FHIR client dependencies compatible with the current project and HAPI FHIR server version.

Do not blindly copy dependencies from unrelated examples.

Before modifying `pom.xml`, explain:

- which HAPI FHIR modules are being added;
- why each one is needed;
- why the selected version is appropriate;
- whether the dependency is compile-time or test-only.

Do not add a large collection of HAPI FHIR modules that are not needed.

## Configuration

Add a configuration property for the FHIR server base URL.

Preferred property:

```yaml
fhir:
  server:
    base-url: http://localhost:8080/fhir
```

Do not hard-code the URL inside Java classes.

Use Spring configuration to inject the value.

The configuration must allow the URL to be changed later for:

- another local FHIR server;
- a test environment;
- Epic;
- Oracle Health;
- another FHIR server.

Do not add real credentials.

## FHIR Client

Use HAPI FHIR's R4 client framework.

The implementation should conceptually create:

```text
FhirContext
    ↓
R4 context
    ↓
IGenericClient
    ↓
FHIR server base URL
```

The exact class/configuration structure should follow good Spring Boot practices and HAPI FHIR conventions.

Do not create unnecessary abstractions.

The first implementation should be simple enough for the developer to understand completely.

## CapabilityStatement Retrieval

Implement a service method whose responsibility is equivalent to:

```text
retrieveCapabilityStatement()
```

It must communicate with:

```text
GET /metadata
```

through the HAPI FHIR client.

The result should be represented as an R4 `CapabilityStatement`.

The implementation should demonstrate the relationship:

```text
FHIR Server
    |
    | /metadata
    v
CapabilityStatement
```

Do not expose the CapabilityStatement through a new controller yet.

## Error Handling

Add appropriate basic error handling.

The service should not silently swallow connection or FHIR errors.

Do not introduce a complex global exception architecture yet.

For this task, prefer a clear and maintainable approach that can evolve later.

## Testing Strategy

Create unit tests for configuration/client creation where practical.

Also create an integration test that communicates with the local HAPI FHIR server when the server is available.

The integration test should verify at minimum:

1. The client can connect to the configured FHIR server.
2. `/metadata` can be retrieved.
3. The response is a FHIR R4 `CapabilityStatement`.
4. The CapabilityStatement reports the expected FHIR version (`4.0.1`) if that is what the current local server returns.

Do not make the normal Maven test lifecycle dependent on an external public internet service.

Prefer the local HAPI FHIR instance.

If an integration test requires the local Docker infrastructure, document how to run it.

## Test Design

Clearly distinguish:

### Unit tests

Test application logic without requiring HAPI FHIR to be running.

### Integration tests

Test actual communication with:

`http://localhost:8080/fhir`

Do not mix the two concepts.

If a Maven profile is useful for integration tests, explain why before adding it.

Do not introduce Testcontainers yet unless there is a concrete need.

## Documentation

Update the relevant documentation under:

`docs/fhir/`

Create a document such as:

`docs/fhir/fhir-client.md`

It should explain:

- what a FHIR client is;
- what HAPI FHIR client provides;
- what `FhirContext` does;
- what `IGenericClient` does;
- how the base URL is configured;
- how `/metadata` is retrieved;
- what `CapabilityStatement` means;
- how to run the local FHIR server;
- how to run the application/tests.

Write the documentation as educational material for the developer.

## Verification

Before finishing, execute at least:

```bash
java -version
```

```bash
cd services/fhir-integration-service
mvn test
```

Verify that the local HAPI FHIR infrastructure is running:

```bash
docker compose -f ../../infra/docker/docker-compose.yml ps
```

Run the relevant integration verification against:

```text
http://localhost:8080/fhir
```

If the integration test is separated from normal tests, execute it explicitly and show the exact command.

Do not claim success without actually running the verification.

## Code Quality

Follow these principles:

- Keep the implementation small.
- Use constructor injection.
- Keep configuration separate from business logic.
- Use meaningful class and method names.
- Avoid static mutable state.
- Avoid unnecessary utility classes.
- Avoid premature abstraction.
- Do not expose internal implementation details through REST endpoints.
- Add tests for meaningful behavior.
- Keep secrets out of source control.

## Expected Initial Structure

The exact structure may vary if there is a strong reason, but it should remain close to:

```text
services/fhir-integration-service/
└── src/
    ├── main/
    │   ├── java/
    │   │   └── .../
    │   │       ├── FhirIntegrationServiceApplication.java
    │   │       └── fhir/
    │   │           ├── FhirClientConfiguration.java
    │   │           └── FhirService.java
    │   │
    │   └── resources/
    │       └── application.yml
    │
    └── test/
        └── java/
            └── .../
```

Do not blindly create exactly these classes if a simpler, clearer structure is appropriate. Explain the chosen structure.

## Git Rules

Do not commit automatically.

At the end show:

```bash
git status
```

and:

```bash
git diff --stat
```

Also show:

```bash
git diff -- pom.xml
```

and the relevant source/configuration changes.

The developer will review the implementation before committing.

## Acceptance Criteria

The task is complete only when:

- [ ] Work is on `feature/fhir-client`.
- [ ] HAPI FHIR R4 client dependencies are correctly configured.
- [ ] FHIR base URL is externalized in configuration.
- [ ] Java can create an R4 FHIR client.
- [ ] The client can communicate with local HAPI FHIR.
- [ ] `/metadata` is retrieved programmatically.
- [ ] Result is represented as an R4 `CapabilityStatement`.
- [ ] Unit tests pass.
- [ ] Integration verification passes against local HAPI FHIR.
- [ ] No public REST controller has been added for this task.
- [ ] No unrelated technologies/components were introduced.
- [ ] Documentation explains the implementation.
- [ ] No secrets or PHI were introduced.
- [ ] No Git commit was created by Cursor.
- [ ] The final report contains the complete step-by-step execution history.

## Final Report Format

Do NOT provide only a summary.

Use this structure:

### Step-by-step execution

#### Step 1 — ...
- What I did:
- Why:
- Files:
- Commands:
- Result:
- Concept learned:

#### Step 2 — ...
...

### Files created

List every new file.

### Files modified

List every modified file and explain the change.

### Dependencies

For every new dependency:
- name
- version
- purpose

### Tests

Show:
- exact command;
- result;
- what was verified.

### FHIR verification

Show:
- FHIR base URL;
- operation performed;
- HTTP/result;
- FHIR version returned.

### Git status

Show the actual output of:

```bash
git status
```

### Git diff stat

Show the actual output of:

```bash
git diff --stat
```

### Problems encountered

List each problem and how it was resolved.

### Concepts learned

Explain the new FHIR/Java concepts introduced in this task.

### Next step

State only the next planned task:

`feature/fhir-search`

Do not implement it.
