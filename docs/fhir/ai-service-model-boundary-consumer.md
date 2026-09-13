# AI Service Model Boundary Consumer

Task 074 adds `services/ai-service`, a FastAPI consumer of the existing Model Boundary Contract v1. This file lives under `docs/fhir` for laboratory documentation layout. The Python service does not speak FHIR, Epic, Oracle, or SMART.

## Purpose

```text
GET /api/model-boundary/v1
        ↓
ai-service
        ↓
received | rejected
modelCalled = false
```

The first Product B process is an external consumer, not a language-model runtime.

## Contract consumed

The Java body is `ModelBoundaryContract` v1. The consumer does not wrap it as `{ context }` and does not add `usable`, `requiresHumanReview`, or `modelCallAuthorized`.

Empty context uses collection `retainedCount` only, the same idea as `AgentStub.hasClinicalData`. `medicationRequests: null` is valid.

## Surfaces

- Consumer: `GET /internal/agent-context` on port `8090`
- Health: `GET /health`
- Upstream: `GET /api/model-boundary/v1` on port `8081`

## Known debt

The Java contract endpoint is unauthenticated. Task 075 is service-to-service authentication. Task 076 is a language-model call behind an explicit authorization check.

See `services/ai-service/README.md`.
