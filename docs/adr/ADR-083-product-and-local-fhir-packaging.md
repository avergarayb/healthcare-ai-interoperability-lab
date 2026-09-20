# ADR-083 — Product and Local-FHIR Packaging

## Status

Proposed

## Date

2026-09-20

## Context

ADR-077 defines one **Healthcare AI & Interoperability Platform** with two technical surfaces. ADR-081 classifies Java and Python as product runtime and the Compose HAPI stack as local development support. It does not select a commercial orchestrator.

Phase C4.1 asked what *packaging boundary* must exist so a future release cannot ship HAPI, HAPI Postgres, lab-oauth, or nginx as if they were the product — without choosing Docker Compose profiles, images, an installer, a VM, or Kubernetes.

This ADR names two **delivery identities** of that single product. It does not create a second commercial product and does not implement packaging.

## Current State

**Product applications (not started by Compose):**

- `services/fhir-integration-service` — Java Interoperability Surface, port 8081.
- `services/ai-service` — Python AI Surface, port 8090.

**Local development support (`infra/docker/docker-compose.yml`):**

- `hapi-fhir` (`hapiproject/hapi:v8.10.0-3`) on host port 8080.
- `hapi-fhir-postgres` (Postgres 16) — datasource **for that HAPI container only**.
- `lab-oauth` on 9090.
- `fhir-gateway` nginx on 8180.

Compose does not include Java or Python. There are no Compose `profiles` and no Kubernetes manifests in the repository. The Java application has no product JPA/Postgres dependency in `pom.xml`.

Java default `fhir.active-server` is `local-hapi` (`http://localhost:8080/fhir`). Epic and Oracle sandboxes are separate YAML destinations. HAPI is a possible Java FHIR *destination*, not a product EHR (ADR-078, ADR-081).

The Compose project name `healthcare-ai-interoperability-lab` is historical. It does not override product identity (ADR-077).

Java packages for Tasks 057–073 and `/lab/*` remain an in-process simulation surface (ADR-079). They are **out of scope** for this packaging split.

## Decision

1. **The commercial identity remains one product:** Healthcare AI & Interoperability Platform (ADR-077). Two delivery identities are not two products.
2. **Product Runtime** is the Interoperability Surface (Java) and the AI Surface (Python). That pair is what a future commercial deploy must be able to account for.
3. **Local-FHIR Support Pack** is HAPI FHIR, HAPI Postgres, lab-oauth, and nginx.
4. **The Support Pack is optional.** It exists for local development and laboratory FHIR/SMART exercise. It is not required to run Product Runtime against Epic or Oracle sandbox destinations.
5. **The Support Pack is not** the product EHR, a customer HIS/SIHCE, commercial IAM, the product API gateway / edge architecture, or a product business database. Applications do not persist v1, prompts, or tenants in HAPI Postgres.
6. **A future commercial release must be able to distinguish Product Runtime from the Local-FHIR Support Pack.** HAPI must not be presented as the customer’s clinical infrastructure or as part of the product EHR.
7. **Java may keep `local-hapi` as a configurable destination.** That does not make HAPI a mandatory component of the commercial runtime.
8. **This ADR does not choose how those identities are materialized** (Compose profiles, multiple Compose files, images, installer, VM, Kubernetes, registry, CI/CD, or other release tooling).

## Rationale

C4.1: ADR-081 already classified the stacks; the repository already lays them out as `services/` versus `infra/docker/`. What was missing was a packaging *contract*: future delivery must keep that split visible. Runtime profiles inside a single blob would still let HAPI travel with the product. Declaring Kubernetes now would pick an orchestrator ADR-081 deferred. Naming two delivery identities of one product is enough to stop treating Compose as the commercial platform.

## Alternatives Considered

- **Conceptual separation only (restate ADR-081).** Accurate as classification; weak as a release contract. Operators could still ship the HAPI stack as “the product.”
- **Runtime profiles inside one delivery unit.** Convenient for local flags later, but a single blob with modes does not by itself prevent HAPI from appearing in a customer or SaaS install. A profile may be a future *tactic* for local DX; it is not this ADR’s packaging boundary.
- **Separate delivery identities (Product Runtime vs Local-FHIR Support Pack).** This ADR records that boundary. It does not pick zip files, image names, or Compose file layout.
- **Ship everything in one package and call it the product.** Would imply a FHIR server, Postgres, lab-oauth, and nginx are core SKUs. They are not in the Java/Python applications (ADR-081).
- **Declare Kubernetes (or another cloud orchestrator) now.** Packaging implementation and commercial architecture; out of this ADR (ADR-081).

## Consequences

Positive: commercial and deployment talk starts from two product processes; local FHIR remains an optional support pack; ADR-077’s single product identity is preserved.

Negative / trade-off: local development still uses Product Runtime plus the Support Pack as two pieces — which matches the current host + Compose habit. Historical Compose naming is not renamed here. How artifacts are built remains a later decision.

## Boundaries

No Docker, YAML, or Compose edits. No new services, databases, or tenancy. No Docker Compose profiles, multiple Compose files, images, installer, VM, Kubernetes, cloud provider, registry, or CI/CD. No SaaS vs customer-hosted vs hybrid choice. No move, deletion, or refactor of `/lab/*` or Tasks 057–073 (ADR-079). No claim that this ADR is a legal or compliance result.

## Related Decisions

- ADR-077 — one product, two technical surfaces, three logical boundaries.
- ADR-078 — HAPI is a possible Java destination, not Gemini input.
- ADR-079 — 057–073 and `/lab/*` are a simulation surface; not decided here.
- ADR-080 / ADR-082 — inbound protection of AI internals is independent of this packaging split; packaging does not replace authentication.
- ADR-081 — runtime vs local support classification that this ADR turns into delivery identities.
- `docs/ai-governance/product-governance-boundary.md` §11 (SaaS / customer-hosted / hybrid remain future considerations).
- `infra/docker/docker-compose.yml`

## Future Reconsideration

Revisit when a written release exists, when Java/Python are containerized, if the product introduces its own datastore (a new ADR — not implied here), or if `/lab/*` is omitted from a runtime artifact (that would be an ADR-079 follow-up, not a silent change here). If the product were sold as a FHIR server, this ADR and ADR-081 would need to be reopened.
