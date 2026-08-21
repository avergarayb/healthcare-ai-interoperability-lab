# Project Definition

## Vision

Build a from-scratch Healthcare AI & Interoperability laboratory demonstrating practical expertise in FHIR, HL7 v2, SMART on FHIR, EHR integration, AI, RAG, agents, MCP, ML, security, containers, Kubernetes and Azure.

## Scope

This repository is independent. It is not CareFlow and must not import or reuse CareFlow application code.

## Technology Strategy

### Healthcare interoperability
- Java 21
- Spring Boot
- Spring Security
- FHIR
- HL7 v2
- SMART on FHIR
- PostgreSQL

### AI
- Python
- FastAPI
- LLMs
- RAG
- agents
- ML
- pgvector
- Ollama for local experiments
- provider-agnostic model gateway

### Infrastructure
- Docker / Docker Compose
- Kubernetes
- Azure
- CI/CD

## Initial Components

Only create components when their responsibility is justified.

Initial service:
- `fhir-integration-service` — Java 21 / Spring Boot

Initial infrastructure:
- HAPI FHIR
- PostgreSQL

Future service:
- `ai-service` — Python / FastAPI

## Git Strategy

`main` is always stable. Work is performed on `feature/*` branches and merged into `main` after tests and review.

Use Conventional Commits.

## Engineering Rule

Every implementation task must document objective, context, architecture impact, requirements, constraints, tests and acceptance criteria.

Evolve incrementally; do not build the final distributed architecture up front.

## Roadmap

The implementation sequence lives in [`roadmap.md`](roadmap.md). Do not implement later phases until the current phase justifies them.
