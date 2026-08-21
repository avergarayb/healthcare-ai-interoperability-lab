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

### Phase 3 — SMART on FHIR

Authorization and app launch using SMART on FHIR.

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

The repository is completing Phase 1. The next implementation task is `feature/fhir-client` inside `fhir-integration-service`.
