# Healthcare AI & Interoperability Platform

An evolving platform for controlled healthcare interoperability and AI capabilities. The repository retains historical `lab` names where they are part of paths, Compose identifiers, fixtures, or compatibility contracts; those names do not define the current product direction.

The platform currently contains two independently deployable product units:

- **Healthcare Interoperability** — Java 21 / Spring Boot, FHIR R4, SMART authorization, Epic and Oracle sandbox integrations, local HAPI connectivity, controlled projections and bounded interoperability contracts.
- **Healthcare AI** — Python / FastAPI / LangGraph, the Model Boundary v1 consumer, the gated synthetic Gemini endpoint, and **Clinical Follow-up Review** with deterministic application-owned protocol authority. Operational clinical reads go through Java Clinical Read.

They may be deployed together or independently. Final pricing, packaging and commercial SKUs are not decided. The **Mini HIS Simulator** is a laboratory stand-in, not a third product unit. Java reads it only when `clinical-read.source` is `mini-his`.

## Current architecture

```text
Mini HIS Simulator or local HAPI
        |
        v
Healthcare Interoperability (Java)
        Clinical Read API v1
        clinical-read.source selects the backend
        |
        v
Healthcare AI (Python)
        ClinicalReadClient
        deterministic protocol authority
        LangGraph/Gemini narrative subflow where allowed
```

`clinical-read.source` defaults to `local-hapi` (`http://localhost:8080/fhir`). The other implemented value is `mini-his` (`http://127.0.0.1:8095`). Python calls Java for those operational reads. It does not call Mini HIS or HAPI on that path. Java still reaches configured FHIR endpoints for SMART, projections, and Model Boundary v1.

For Clinical Follow-up Review, mandatory Patient, Encounter, Observation and Appointment acquisition occurs before LangGraph. `POST_CONSULTATION_RESULT_REVIEW_V1` determines protocol, human-review and proposed-action fields. A separate SQLite-backed operational workflow creates or reuses a durable review case for a match before Gemini runs. Gemini does not own those decisions or durable state. The capability performs no FHIR writes.

Start here:

- [Product scope](docs/PROJECT.md)
- [Architecture authority and decision index](docs/architecture/README.md)
- [Healthcare Interoperability documentation](docs/fhir/README.md)
- [Clinical Read API v1](docs/contracts/clinical-read-v1.md)
- [Healthcare AI service runbook](services/ai-service/README.md)
- [Mini HIS Simulator runbook](services/mini-his-simulator/README.md)
- [ADR-085: Python FHIR and model authority boundary](docs/adr/ADR-085-python-follow-up-fhir-and-model-authority-boundary.md)
- [ADR-086: persistent follow-up review workflow](docs/adr/ADR-086-persistent-follow-up-review-workflow-and-operational-authority-boundary.md)
- [Clinical Follow-up Review V1 contract](docs/contracts/post-consultation-result-review-v1.md)
- [Operational Follow-up Review Workflow V1 contract](docs/contracts/follow-up-review-workflow-v1.md)

## Implemented versus not implemented

Implemented development capabilities include FHIR R4 client operations, local HAPI, sandbox SMART integrations, controlled Java projections, Clinical Read API v1, the Python internal APIs, deterministic follow-up review, durable single-instance operational review cases, a gated Gemini narrative flow, and one internal follow-up coordination request after an explicit human POST. The Mini HIS Simulator is the optional laboratory source for Clinical Read.

The repository does not establish production IAM/RBAC, tenancy, human assignment or verified reviewer identity, clinical decision support, autonomous treatment, multi-replica review persistence, production deployment, regulatory certification, or production processing approval for real patient data.

## Repository layout

```text
healthcare-ai-interoperability-lab/
├── docs/                         product, architecture, governance and contracts
├── services/
│   ├── fhir-integration-service/ Healthcare Interoperability
│   ├── ai-service/               Healthcare AI
│   └── mini-his-simulator/       laboratory Mini HIS Simulator
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

The Java service listens on port `8081`. Clinical Read is `GET /api/clinical-read/v1` on that process. The checked-in `clinical-read.source` in `application.yml` is `local-hapi`. Set it to `mini-his` to read the simulator at `http://127.0.0.1:8095`. Java and Python share `MODEL_BOUNDARY_SERVICE_TOKEN` as `X-Service-Token`. A blank token fails closed. Vendor sandbox features are disabled/configuration-dependent and default tests do not require live Epic or Oracle credentials. This service has no README of its own. See [FHIR documentation](docs/fhir/README.md) and [Clinical Read API v1](docs/contracts/clinical-read-v1.md).

## Mini HIS Simulator

Laboratory stand-in on `127.0.0.1:8095`. It uses its own SQLite file and does not call Java, Python, or HAPI.

```text
mvn -f services/mini-his-simulator/pom.xml spring-boot:run
```

Start it when `clinical-read.source` is `mini-his`. See the [Mini HIS Simulator runbook](services/mini-his-simulator/README.md).

## Healthcare AI

```powershell
cd services/ai-service
py -3 -m venv .venv
.venv\Scripts\activate
pip install -r requirements.txt
py -3 -m pytest
python -m uvicorn app.main:app --host 0.0.0.0 --port 8090
```

Operational follow-up reads use `MODEL_BOUNDARY_BASE_URL` (default `http://localhost:8081`) and the same `MODEL_BOUNDARY_SERVICE_TOKEN` Java expects. `FOLLOWUP_AGENT_ENABLED=true` enables the follow-up routes. `FHIR_BASE_URL` is the laboratory direct HAPI reader. The operational factories do not read it.

The default Python suite does not require Gemini, Epic, or Oracle. One test still calls local HAPI and is not behind `RUN_HAPI_INTEGRATION_TESTS`: `test_local_server_missing_patient_is_not_a_clinical_result`. Confirm `GET http://localhost:8080/fhir/metadata` before that suite. A refused connection fails that test with `transport failed`. Other live HAPI and Gemini tests stay opt-in. See the [AI service runbook](services/ai-service/README.md).

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
