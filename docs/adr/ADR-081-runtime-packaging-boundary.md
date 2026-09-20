# ADR-081 — Runtime Packaging Boundary

## Status

Proposed

## Date

2026-09-20

## Context

Phase C1 showed two application processes on the host and a Docker Compose stack that does not start them. Operators can treat HAPI or Postgres as “the product database” or assume Compose *is* the commercial runtime. C2 asked whether Java/Python should join Compose without choosing Kubernetes or a cloud.

## Current State

**Product applications (not in Compose):**

- `services/fhir-integration-service` — Java, port 8081 (`application.yml`).
- `services/ai-service` — Python, port 8090 (`AI_SERVICE_PORT`).

**Local development support (`infra/docker/docker-compose.yml`):**

- `hapi-fhir` image `hapiproject/hapi:v8.10.0-3` on host port 8080.
- `hapi-fhir-postgres` (Postgres 16) — datasource **for that HAPI container only**.
- `lab-oauth` on 9090.
- `fhir-gateway` nginx on 8180.

Java default `fhir.active-server` is `local-hapi` (`http://localhost:8080/fhir`). Epic/Oracle sandboxes are separate YAML destinations. Compose project name remains `healthcare-ai-interoperability-lab` (historical). No Kubernetes manifests were found. No product JPA/Postgres dependency exists on the Java app `pom.xml`.

## Decision

1. **Product runtime** is the Interoperability Surface (Java) and the AI Surface (Python). Those two processes are what a future commercial deploy must account for.
2. **Local development support** is HAPI FHIR, HAPI’s Postgres volume, lab-oauth, and nginx. They exist to exercise a local FHIR server and optional SMART lab profiles.
3. **Local HAPI is not the product EHR** and is not a customer HIS/SIHCE.
4. **HAPI Postgres is not a product business database.** The applications do not persist v1, prompts, or tenants there.
5. **lab-oauth and nginx are local-lab support**, not the platform’s identity or edge architecture.
6. **Future packaging may change** (host, Compose including Java/Python, or other). This ADR **does not** select SaaS vs customer-hosted vs hybrid, and **does not** select Docker Compose or Kubernetes as the commercial architecture.

## Rationale

C1 inventory: apps off-Compose; HAPI stack optional for `local-hapi`. C2: classifying HAPI as support can be stated now; choosing a commercial orchestrator cannot. Keeps ADR-078 destinations (Epic/Oracle/HAPI) as *config of Java*, not as “the platform is a FHIR server”.

## Alternatives Considered

- **Treat Compose as the product.** Would imply a FHIR server + Postgres are core SKUs; they are not in the Java/Python apps.
- **Require Java/Python inside Compose immediately.** Packaging implementation; out of C3.
- **Declare Kubernetes/cloud now.** C2 “should not be made yet”.
- **Ignore HAPI in architecture.** Leaves ports 8080/8180/9090 unexplained.

## Consequences

Positive: commercial and deployment talks start from two apps; local FHIR remains optional.

Negative / trade-off: local DX still depends on an extra stack; naming (`healthcare-ai-interoperability-lab`) lags product identity (ADR-077) until a later rename, which this ADR does not perform.

## Boundaries

No Docker/YAML edits; no new services; no cloud/K8s/mesh; no new database; no tenancy.

## Related Decisions

- ADR-077 — support vs technical surfaces.
- ADR-078 — HAPI is a *possible Java destination*, not Gemini input.
- ADR-080 — packaging does not replace the internal-API intention.
- `docs/ai-governance/product-governance-boundary.md` §11 (deployment models remain future considerations).
- `infra/docker/docker-compose.yml`

## Future Reconsideration

Revisit when a written packaging/release decision exists, when Java/Python are added to Compose as optional profiles, or if the product introduces its own datastore (a new ADR — not implied here).
