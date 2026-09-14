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

## Service authentication (Task 075)

`GET /api/model-boundary/v1` requires header `X-Service-Token` matching `MODEL_BOUNDARY_SERVICE_TOKEN` on both processes.

Missing, empty, or wrong token: Java returns HTTP 401 **before** `currentContract()`, with no contract body and no Oracle/Epic call. If the Java variable is blank, that HTTP surface stays fail-closed; Spring Boot, `/lab/*`, and SMART stay up.

A valid token only lets the request reach the existing controller. HTTP still follows `ModelBoundaryHttpStatuses` (200 / 401 / 409 / 502). Service 401 is not SMART `AUTHENTICATION_REQUIRED`. Python maps any Java 4xx to `rejected` / `boundary_http_4xx`.

This is a laboratory shared secret, not production identity. Fine-grained authorization and Task 076 (LLM) remain open.

See `services/ai-service/README.md`.
