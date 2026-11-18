# Single-VM demonstration deployment v1

## Status

Laboratory package for a future Ubuntu VM. It is not a remote deployment and not a production system.

## Entry

Only Caddy publishes ports. Local mode uses `127.0.0.1:18080` and `127.0.0.1:18443`. Java, Python, and PostgreSQL have no published ports. The administrative Keycloak path is not routed.

## Identity

The local issuer is `https://demo.localhost:18443/realms/demo-deploy`. Peru and Spain use `https://pe.demo.localhost:18443` and `https://es.demo.localhost:18443`. The callback path remains `/lab-review-iam/callback`. PKCE is S256. A public hostname is a placeholder until the Product Owner confirms DNS.

## Data

Keycloak uses a new PostgreSQL volume. Each country keeps its own SQLite ledger, Human Review database, and federation audit on one volume. Those three are separate files. The backup copies each one with the SQLite backup API, and dumps PostgreSQL separately. An IAM session file is included only when a login has created it. Follow-up and knowledge files created empty at startup are not part of the demonstration backup. Restoring them is required after a migration; starting an older image does not rewind the database. Recording the previous image id lets an operator retarget that image. Rebuilding the same `0.1.0` tag does not prove a version rollback.

## Provider

No provider key is part of the configuration. `request_real_provider_send` stays closed and the demonstration transport stays intercepted. `DEMO_VM_AUTHORIZED` only unlocks the unpublished VM configuration. It does not close outbound network access. A provider firewall remains a remote activation check.

## Out of scope

Hetzner provisioning, Kubernetes, high availability, a hospital image, real patient data, and a live model call.

## References

- [ADR-108](../adr/ADR-108-demo-deploy-001.md)
- [demo-deploy-001](../demos/demo-deploy-001.md)
