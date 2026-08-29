# Roadmap

This is the official implementation roadmap for `healthcare-ai-interoperability-lab`.

Architecture decisions live in [`PROJECT.md`](PROJECT.md). This file records the planned progression only. Do not treat later phases as permission to implement them early.

## Target Architecture

The laboratory is polyglot:

- **Java / Spring Boot** for healthcare interoperability and enterprise integration.
- **Python / FastAPI** for AI/ML.
- **Docker / Kubernetes / Azure** for infrastructure.

Initial integration component:

- `fhir-integration-service` — Java 21 / Spring Boot

Future AI component, not created yet:

- `ai-service` — Python / FastAPI

## Phases

### Phase 0 — FHIR Fundamentals

FHIR R4 resources, search, Capability Statement, and vendor-neutral interoperability basics.

### Phase 1 — Local FHIR

Local HAPI FHIR, PostgreSQL persistence, Docker Compose, and `fhir-integration-service`.

Current bootstrap belongs to this phase.

### Phase 2 — Real EHR Integration

Connect the integration layer to real EHR FHIR APIs without coupling the lab to a single vendor.

Phase 2 starts with **named FHIR server profiles** and external configuration (`local-hapi` today). OAuth 2.0 Client Credentials is available on the optional `secured-lab` profile. SMART on FHIR Authorization Code + PKCE is available on the optional `smart-lab` profile.

### Phase 3 — SMART on FHIR

Authorization and app launch using SMART on FHIR. This laboratory implements a **synthetic** Authorization Code + PKCE flow (`smart-lab`). Commercial EHR SMART launch is not in this step.

### Phase 4 — HL7 v2

HL7 v2 message handling as a complement to FHIR, not a replacement.

### Phase 5 — AI Foundation

Python / FastAPI `ai-service`, model gateway, and the first AI boundary behind the Java integration layer.

### Phase 6 — RAG

Retrieval-augmented generation over healthcare context produced by the interoperability layer.

### Phase 7 — Healthcare Agent

Agent workflows that act on normalized healthcare context, not raw EHR payloads.

### Phase 8 — MCP

Model Context Protocol as a controlled tool interface for healthcare capabilities.

### Phase 9 — Local AI

Local model experiments, including Ollama, without changing the provider-agnostic gateway.

### Phase 10 — LangGraph

Graph-based agent orchestration for multi-step healthcare workflows.

### Phase 11 — Healthcare ML

Machine learning on healthcare data after interoperability and security boundaries are in place.

### Phase 12 — Security & Enterprise

Authentication, authorization, auditability, and enterprise integration practices.

### Phase 13 — Azure

Cloud deployment, Kubernetes, and CI/CD on Azure.

### Phase 14 — Portfolio

Package the laboratory as a coherent demonstration of healthcare interoperability and AI.

## Current Position

The repository is in Phase 2–3. `fhir-integration-service` remains a FHIR R4 **client**. Named server profiles (`fhir.active-server`) select connectivity. OAuth 2.0 Client Credentials is optional (`secured-lab`). SMART Authorization Code + PKCE is optional (`smart-lab`). Java packages are split by responsibility (`client`, `server`, `auth`, `auth.oauth2`, `smart`, `mapping`, `routing`, `observability`, `exception`, `resilience`); see [`docs/fhir/fhir-architecture.md`](fhir/fhir-architecture.md). External JSON can be mapped to HAPI R4 `Patient` / `Observation` without changing `FhirService`; see [`docs/fhir/fhir-mapping.md`](fhir/fhir-mapping.md). A request can be routed to a named profile without putting destination rules in `FhirService`; see [`docs/fhir/fhir-routing.md`](fhir/fhir-routing.md). Routed Patient reads emit a structured audit event (correlation ID, destination, outcome, duration) without logging FHIR payloads or tokens; see [`docs/fhir/fhir-audit-observability.md`](fhir/fhir-audit-observability.md). The same completed operations increment in-memory counters by bounded dimensions (operation, destination, resource type, outcome) without Prometheus; see [`docs/fhir/fhir-metrics-observability.md`](fhir/fhir-metrics-observability.md). FHIR/HAPI/OAuth/routing failures are classified into a bounded safe category (`NOT_FOUND`, `TIMEOUT`, `CONNECTION_ERROR`, …) without inventing HAPI types; see [`docs/fhir/fhir-error-handling.md`](fhir/fhir-error-handling.md). Routed Patient READ retries only transient categories (`TIMEOUT`, `CONNECTION_ERROR`, `SERVER_ERROR`) up to three attempts; see [`docs/fhir/fhir-retry-resilience.md`](fhir/fhir-retry-resilience.md). Neither talks to a commercial EHR. Local HAPI does not ship LOINC/SNOMED CodeSystems.
