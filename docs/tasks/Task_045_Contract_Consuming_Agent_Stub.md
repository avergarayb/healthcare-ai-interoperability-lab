# Task 045 — Contract-Consuming Agent Stub

## Status

**Implementation**

Depends on Task 044. Does not implement an LLM, `ai-service`, Epic, or cache.

---

# 1. WHAT

A vendor-neutral stub that **consumes** `ModelBoundaryContract` v1 and stops.

It proves a future agent can sit after the cable without knowing Oracle, Epic, HAPI, or FHIR Bundles.

It is not an agent product. It does not call a model.

```text
GET /api/model-boundary/v1          (044, contrato)
        ↓
Agent stub (045)
        ↓
bounded observation
        ↓
STOP
```

---

# 2. WHY

044 exposed the contract as JSON. Nothing yet **reads** it as a consumer.

Without 045, the next jump tends to be:

```text
agente → Oracle
```

or:

```text
contrato → LLM
```

045 inserts an explicit consumer that only understands the contract type.

---

# 3. CONCEPT

```text
EHR heterogéneo
        ↓
snapshot → proyección → contrato v1 → superficie 044
        ↓
stub 045
        ↓
STOP
```

The stub may **see** allowlisted `records` inside the contract.

The stub must **not** republish those record values on a laboratory page or as a new clinical API.

Its public output is operational:

```text
I consumed contract v1
outcome=…
counts / truncated
modelCalled=false
```

---

# 4. Input

The stub receives only:

```text
lab.healthcare.fhir.modelboundary.ModelBoundaryContract
```

How it is obtained in this service:

```text
ModelBoundaryContractProvider.currentContract()
        ↓
AgentStub.observe(contract)
```

One fetch, same as 044. The stub does **not** call `RoutingService`, `FhirService`, or HTTP back to `/api/model-boundary/v1` from inside the same JVM (that would double-fetch Oracle).

A future out-of-process agent (Python) would use `GET /api/model-boundary/v1`. That client is **not** this task.

---

# 5. Output — AgentStubObservation

v1 observation may contain only:

```text
contractVersion
destination
contextSource
outcome
patientStatus
conditions status / receivedCount / retainedCount / truncated
observations status / receivedCount / retainedCount / truncated
diagnosticReports status / receivedCount / retainedCount / truncated
medicationRequests status / receivedCount / retainedCount / truncated
consumed          (true when a contract object was received)
modelCalled       (always false in Task 045)
```

Must not contain:

- `records` / clinicalStatus / intent / Observation.status values as a list;
- Patient ID;
- tokens;
- raw FHIR;
- recommendations;
- prompts;
- “insights”.

`toString()` follows the same rule.

The stub may assert internally that `records.size()` equals `retainedCount` when status is SUCCESS. That check does not become public output.

---

# 6. Package

```text
lab.healthcare.fhir.agentstub
```

Must not import:

```text
vendor.oracle
vendor.epic
projection
routing
client.FhirService
org.hl7.fhir
IGenericClient
OpenAI / Gemini / Anthropic
```

May import:

```text
modelboundary   (contract + provider)
snapshot        (outcome / resource status enums only)
patient         (PatientContextSource only)
```

`FhirService` must not import `agentstub`.

---

# 7. Laboratory surfaces

Keep 044 as the machine contract API.

Add:

| Surface | Path | Body |
|---|---|---|
| Human | `GET /lab/agent-stub` | HTML: observation fields only |
| Machine | `GET /api/agent-stub/v1` | JSON: `AgentStubObservation` only |

Vendor-neutral paths. Oracle remains the live provider behind `ModelBoundaryContractProvider`.

No Patient ID in path or query.

HTTP, same as 043/044:

| Outcome | HTTP |
|---|---|
| COMPLETE / PARTIAL | 200 |
| AUTHENTICATION_REQUIRED | 401 |
| PATIENT_CONTEXT_NOT_CONFIGURED | 409 |
| SNAPSHOT_UNAVAILABLE | 502 |

The HTML page stays blind. The JSON observation stays blind to record values.

---

# 8. Mapping rules

```text
contrato v1
        ↓
copy operational metadata
        ↓
consumed=true
modelCalled=false
        ↓
STOP
```

Must not:

- fetch FHIR;
- expand the allowlist;
- rank or interpret;
- call a model;
- cache;
- invent `active` when `clinicalStatusCode` is empty.

Empty and partial upstream states are preserved.

---

# 9. Tests

- Observation contains only the approved fields.
- `modelCalled` is false.
- Stub package does not import Oracle, Epic, HAPI, or `FhirService`.
- `FhirService` does not import `agentstub`.
- AUTH / CONTEXT / UNAVAILABLE do not invent SUCCESS collections.
- SUCCESS empty collection: received=0 retained=0 truncated=false.
- No Patient ID or token in `toString`, HTML, or observation JSON.

Default Maven stays offline from Oracle. Live remains opt-in.

---

# 10. Out of scope

- LLM / prompts / OpenAI / Gemini
- `ai-service`
- RAG / embeddings
- session cache
- Epic
- allowlist expansion
- HTTP self-call to `/api/model-boundary/v1`
- clinical recommendations

---

# 11. Acceptance

1. A dedicated `agentstub` package exists.
2. It consumes `ModelBoundaryContract` only.
3. It does not call a model (`modelCalled=false`).
4. Lab HTML and `/api/agent-stub/v1` expose observation metadata only.
5. No second FHIR fetch.
6. `FhirService` remains vendor-neutral.

---

# 12. After this task

```text
045 stub (consume and stop)
        ↓
later: a real agent, still only via the contract
        ↓
later: Epic, same /api/model-boundary/v1
```
