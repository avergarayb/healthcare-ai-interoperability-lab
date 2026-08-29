# Healthcare AI & Interoperability Lab

Independent laboratory project for building healthcare interoperability and AI capabilities from scratch.

Architecture decisions live in [`docs/PROJECT.md`](docs/PROJECT.md). The implementation sequence lives in [`docs/roadmap.md`](docs/roadmap.md).

## Target Architecture

EHRs (FHIR / HL7 v2)
→ Java / Spring Boot Integration Layer
→ normalized healthcare context
→ Python / FastAPI AI Service
→ RAG / Agents / ML
→ model gateway

## Initial Phase

- FHIR R4 fundamentals
- Local HAPI FHIR
- Java 21 + Spring Boot `fhir-integration-service`
- PostgreSQL
- Docker Compose
- Postman
- Git / GitHub

## Repository Layout

```text
healthcare-ai-interoperability-lab/
├── README.md
├── .gitignore
├── docs/
│   ├── PROJECT.md
│   ├── roadmap.md
│   ├── architecture/
│   ├── fhir/
│   └── tasks/
├── services/
│   └── fhir-integration-service/
├── infra/
│   └── docker/
├── experiments/
├── tests/
└── scripts/
```

The Docker Compose project name is `healthcare-ai-interoperability-lab`. Services remain `hapi-fhir` and `hapi-fhir-postgres`, plus optional `lab-oauth` and `fhir-gateway` for OAuth/SMART. The initial application is `fhir-integration-service` (Java packages: `client`, `server`, `auth`, `smart`, `mapping`, `routing`, `observability`, `exception`, `resilience` — see [`docs/fhir/fhir-architecture.md`](docs/fhir/fhir-architecture.md)). The future Python service `ai-service` is not created yet.

## Prerequisites

- Java 21
- Maven 3.9+
- Docker and Docker Compose

## Local Setup

The FHIR server runs in Docker. The integration service runs on the host.

### 1. Start HAPI FHIR and PostgreSQL

From the repository root:

```bash
docker compose -f infra/docker/docker-compose.yml up -d
```

HAPI FHIR uses PostgreSQL for persistence. Configuration stays in `infra/docker/` and is not part of the application code.

Optional overrides: copy `infra/docker/.env.example` to `infra/docker/.env`. Do not commit `.env` files.

HAPI takes a minute or two to become ready on first start.

### 2. Verify the FHIR endpoint

Capability Statement:

```http
GET http://localhost:8080/fhir/metadata
```

Example:

```bash
curl http://localhost:8080/fhir/metadata
```

FHIR base URL: `http://localhost:8080/fhir`

### 3. Build and test the integration service

```bash
cd services/fhir-integration-service
mvn test
```

### 4. Start the integration service

```bash
cd services/fhir-integration-service
mvn spring-boot:run
```

Health endpoint:

```http
GET http://localhost:8081/actuator/health
```

Example:

```bash
curl http://localhost:8081/actuator/health
```

The service listens on port `8081` so it does not collide with HAPI FHIR on `8080`.

## Stop Local Infrastructure

```bash
docker compose -f infra/docker/docker-compose.yml down
```

## Branch Strategy

- `main`: stable
- `feature/*`: isolated work

## Principles

1. Interoperability first.
2. Vendor-neutral architecture.
3. Java for enterprise healthcare integration.
4. Python for AI/ML.
5. Security and observability from the beginning.
6. No unnecessary microservices before there is a clear boundary.
