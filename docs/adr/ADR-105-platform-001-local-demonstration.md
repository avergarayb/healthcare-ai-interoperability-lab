# ADR-105 — Local demonstration stack

## Status

Accepted for this laboratory increment. It does not authorize a public deployment, production multi-tenancy, a live model call, or a migration from SQLite to PostgreSQL.

## Context

Peru and Spain already share one federation contract, and one Java process can load only one jurisdiction profile. The historical Keycloak realm, the HAPI database, and the Mini LIS database are evidence and support for other work. A repeatable demonstration needs its own processes and volumes without disturbing those stores.

Inside a container, `127.0.0.1` is that container. The browser and the token checks still need one issuer. The MCP clients previously accepted only loopback, so a Docker DNS name was denied.

## Decision

1. `infra/platform-001/compose.yaml` is a separate Compose project named `platform-001`. It does not attach the HAPI, Mini LIS, or `lab-review-iam` volumes. Mini HIS and Mini LIS remain available from their existing support stack. This demonstration uses the jurisdiction connector as the synthetic source.
2. Peru and Spain each get one federation container and one AI container. The profile is the process environment. A request parameter cannot select it.
3. Published ports bind to `127.0.0.1` only. Each container removes its default route at start, so it can reach other containers and the published host port but not a public model provider. An internal Docker network also blocked those published ports on Docker Desktop, so it is not used. No provider key is placed in the image or the Compose file.
4. The MCP host list adds `federation-pe` and `federation-es` and binds each name to one source. `127.0.0.1` and `localhost` stay valid. Any other host is denied. The list is not a jurisdiction selector.
5. Keycloak uses the same pinned image as IAM-001 and a new realm, `platform-001`. The issuer remains `http://127.0.0.1:18340/realms/platform-001`. Each AI container forwards that loopback address to the Keycloak service. Issuer, signature, and audience checks stay enabled.
6. Review, ledger, and federation audit data stay on SQLite. The ledger contract rejects every platform other than Windows, so the LangGraph runner stays on the Windows host and calls the published federation port. Federation, the review service, and Keycloak run in Compose. A container probe checks HTTP between containers and the blocked provider socket. This end-to-end path is not wholly inside Docker. Schema 9 is applied by the existing migrations. Historical files are not opened by this project.
7. `NET_ADMIN` is added only so the container can delete its default route. A process with that capability can also restore the route. That is a laboratory risk, not a production control.

## Consequences

The two demonstrations can start, stop, and be backed up without a second product runtime. Compose secrets are local files outside Git. They are not an enterprise secret manager. A container that is attached to another network, or a host process that calls a provider directly, is outside this control.

A later increment may adapt the Windows ledger so the graph can run in a Linux container. This increment does not make that change.

## References

- [platform-001](../demos/platform-001.md)
- [jurisdiction-lab-demo-v1](../contracts/jurisdiction-lab-demo-v1.md)
- [longitudinal-lab-comparison-v1](../contracts/longitudinal-lab-comparison-v1.md)
