# Healthcare AI & Interoperability Platform

An evolving platform for controlled healthcare interoperability and AI capabilities. The repository retains historical `lab` names where they are part of paths, Compose identifiers, fixtures, or compatibility contracts; those names do not define the current product direction.

The platform currently contains two independently deployable product units:

- **Healthcare Interoperability** — Java 21 / Spring Boot, FHIR R4, SMART authorization, Epic and Oracle sandbox integrations, local HAPI connectivity, controlled projections and bounded interoperability contracts.
- **Healthcare AI** — Python / FastAPI / LangGraph, the Model Boundary v1 consumer, the gated synthetic Gemini endpoint, and **Clinical Follow-up Review** with deterministic application-owned FHIR acquisition and protocol authority.

They may be deployed together or independently. Final pricing, packaging and commercial SKUs are not decided.

## Current architecture

```text
Healthcare systems / FHIR endpoints
        |
        +--> Healthcare Interoperability (Java)
        |       FHIR + SMART + routing + projections + v1 contracts
        |
        +--> Healthcare AI (Python)
                authorized bounded FHIR reads for explicit capabilities
                deterministic protocol authority
                LangGraph/Gemini narrative subflow where allowed
```

For Clinical Follow-up Review, mandatory Patient, Encounter, Observation and Appointment acquisition occurs before LangGraph. `POST_CONSULTATION_RESULT_REVIEW_V1` determines protocol, human-review and proposed-action fields. A separate SQLite-backed operational workflow creates or reuses a durable review case for a match before Gemini runs. Gemini does not own those decisions or durable state. The capability performs no FHIR writes.

Start here:

- [Product scope](docs/PROJECT.md)
- [Architecture authority and decision index](docs/architecture/README.md)
- [Healthcare Interoperability documentation](docs/fhir/README.md)
- [Healthcare AI service runbook](services/ai-service/README.md)
- [ADR-085: Python FHIR and model authority boundary](docs/adr/ADR-085-python-follow-up-fhir-and-model-authority-boundary.md)
- [ADR-086: persistent follow-up review workflow](docs/adr/ADR-086-persistent-follow-up-review-workflow-and-operational-authority-boundary.md)
- [Clinical Follow-up Review V1 contract](docs/contracts/post-consultation-result-review-v1.md)
- [Operational Follow-up Review Workflow V1 contract](docs/contracts/follow-up-review-workflow-v1.md)

## Implemented versus not implemented

Implemented development capabilities include FHIR R4 client operations, local HAPI, sandbox SMART integrations, controlled Java projections, the Python internal APIs, bounded HAPI reads, deterministic follow-up review, durable single-instance operational review cases, a gated Gemini narrative flow, and one internal follow-up coordination request after an explicit human POST.

The repository does not establish production IAM/RBAC, tenancy, human assignment or verified reviewer identity, clinical decision support, autonomous treatment, multi-replica review persistence, production deployment, regulatory certification, or production processing approval for real patient data.

## Repository layout

```text
healthcare-ai-interoperability-lab/
├── docs/                         product, architecture, governance and contracts
├── services/
│   ├── fhir-integration-service/ Healthcare Interoperability
│   └── ai-service/               Healthcare AI
├── infra/docker/                 local HAPI and support infrastructure
├── experiments/                  reserved experimental workspace
├── tests/
└── scripts/
```

The Compose project name remains `healthcare-ai-interoperability-lab`. Its HAPI FHIR, PostgreSQL, optional `lab-oauth` and gateway services are local-development support, not a production product estate or customer EHR.

## Prerequisites

- Java 21
- Maven 3.9+
- Python 3.11+
- Docker and Docker Compose

## Local HAPI setup

From the repository root:

```bash
docker compose -f infra/docker/docker-compose.yml up -d
```

HAPI may take a minute or two on first startup. Verify:

```http
GET http://localhost:8080/fhir/metadata
```

The default local FHIR base URL is `http://localhost:8080/fhir`. Configuration under `infra/docker/` belongs to the local support stack.

## Healthcare Interoperability

```bash
cd services/fhir-integration-service
mvn test
mvn spring-boot:run
```

The Java service listens on port `8081`. Vendor sandbox features are disabled/configuration-dependent and default tests do not require live Epic or Oracle credentials. See [FHIR documentation](docs/fhir/README.md).

## Healthcare AI

```powershell
cd services/ai-service
py -3 -m venv .venv
.venv\Scripts\activate
pip install -r requirements.txt
py -3 -m pytest
python -m uvicorn app.main:app --host 0.0.0.0 --port 8090
```

Live HAPI and Gemini tests are separate opt-ins. See the [AI service runbook](services/ai-service/README.md) before enabling either.

## Stop local infrastructure

```bash
docker compose -f infra/docker/docker-compose.yml down
```

## Engineering principles

1. Explicit product and authority boundaries.
2. Vendor-neutral interoperability where the implemented contract supports it.
3. Application-owned security, data-integrity and protocol decisions.
4. Models are not trusted decision authorities.
5. Bounded, observable and fail-closed external access.
6. Historical evidence remains historical; current documents identify present behavior.
