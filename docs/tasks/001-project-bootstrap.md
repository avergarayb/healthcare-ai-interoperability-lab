# Task 001 — Project Bootstrap

## Objective

Bootstrap the `healthcare-ai-interoperability-lab` monorepo so it is ready for the first FHIR integration implementation.

## Context

This is an independent project. Do not import or reference CareFlow code.

Target architecture:
- Java 21 / Spring Boot for healthcare interoperability.
- Python / FastAPI for AI/ML.
- Docker/Kubernetes/Azure for infrastructure.

Do not create the AI service yet.

## Required structure

```text
healthcare-ai-interoperability-lab/
├── README.md
├── docs/
│   ├── PROJECT.md
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

## Requirements

1. Initialize Git if necessary.
2. Use Java 21.
3. Create a Maven Spring Boot application at `services/fhir-integration-service`.
4. Use a stable Spring Boot 3.x release compatible with Java 21.
5. Add only Spring Web, Actuator and Test.
6. Do not add FHIR SDK dependencies yet.
7. Do not implement business endpoints yet.
8. Add a minimal Actuator health endpoint.
9. Add Docker Compose at `infra/docker/docker-compose.yml`.
10. Run HAPI FHIR locally as the FHIR server.
11. Use PostgreSQL for HAPI FHIR persistence if supported by the selected HAPI FHIR image/configuration.
12. Keep HAPI configuration isolated from application code.
13. Do not commit secrets or `.env` files.
14. Add/update `.gitignore`.
15. Add basic documentation.
16. Add at least one Spring Boot context/health test.
17. Document reproducible local startup.

## Naming

Service: `fhir-integration-service`
Future AI service: `ai-service`

Do not create future services now.

## Branch

`feature/project-bootstrap`

## Acceptance Criteria

- Java 21 build succeeds.
- Spring Boot tests pass.
- Integration service starts locally.
- HAPI FHIR and PostgreSQL start through Docker Compose.
- HAPI FHIR exposes its FHIR endpoint.
- `GET /metadata` works against HAPI FHIR.
- Application health endpoint works.
- No secrets are committed.
- README documents local setup.
- `PROJECT.md` remains the architecture source of truth.

## Verification

```bash
java -version
mvn test
docker compose -f infra/docker/docker-compose.yml config
docker compose -f infra/docker/docker-compose.yml up -d
```

Then verify:

```http
GET <FHIR_BASE_URL>/metadata
```

and the application health endpoint.

## Important

Do not over-engineer this task.

The next task will be `feature/fhir-client`.
