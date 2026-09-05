# Task 044 — Contract Consumer Surface v1

## Status

**Implementation**

Depends on Task 043. Does not implement an agent, an LLM, or Epic.

## WHAT

Expose `ModelBoundaryContract` v1 on a versioned machine surface, separate from the laboratory HTML page.

```text
Lab (human):     GET /oracle/sandbox/fhir/model-boundary   text/html  (counts only)
Consumer (machine): GET /api/model-boundary/v1             application/json  (exact contract)
```

## WHY

043 left the contract inside Java. A future agent cannot call an HTML diagnosis page. 044 is the cable, not the agent.

## HOW

```text
existing projection (one fetch)
        ↓
existing 043 mapper
        ↓
ModelBoundaryContract v1
        ↓
GET /api/model-boundary/v1
        ↓
STOP
```

Rules:

- No Patient ID in the path or query.
- Same session gate as 043: AUTH 401, CONTEXT 409, UNAVAILABLE 502, COMPLETE/PARTIAL 200.
- JSON is the contract as approved by 043, including `records`.
- No new FHIR fetch, no allowlist expansion, no clinical transform, no LLM.
- `FhirService` does not import `modelboundary`.
- The consumer controller does not import `vendor.oracle` or `vendor.epic`.

## Out of scope

Agent stub, `ai-service`, prompts, Epic live, event bus, persistence.
