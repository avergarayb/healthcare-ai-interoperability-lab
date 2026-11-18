# ADR-108 — Single-VM demonstration deployment package

## Status

Accepted for this laboratory increment. It does not authorize a Hetzner purchase, a remote deployment, a public certificate, or a production clinical system.

## Context

PLATFORM-001 publishes each service on loopback and keeps the OIDC issuer at `http://127.0.0.1:18340`. Keycloak stores that realm in the development file database. A single Ubuntu VM needs one HTTPS entry point, a stable issuer, and a database that survives a restart. The VM, the DNS name, and the certificate are not available yet.

## Decision

1. `infra/demo-deploy-001` is a separate Compose project. It does not replace PLATFORM-001 and does not attach the HAPI, Mini LIS, or `platform-001` volumes.
2. Caddy is the only published service. Local verification binds `127.0.0.1:18080` and `127.0.0.1:18443` and uses a certificate generated outside Git for the `demo.localhost` names. The VM example is not mounted. Public certificate issuance stays disabled until a domain exists and `DEMO_VM_AUTHORIZED=true`.
3. The review redirect may use an HTTPS DNS name. `127.0.0.1` keeps the previous HTTP loopback rule. Any other HTTP host, any IP other than loopback, and any callback path other than `/lab-review-iam/callback` are rejected. Issuer, signature, audience, PKCE S256, and the binding file stay in force. The OIDC client still ignores proxy environment variables. It loads `DEMO_CA_FILE` only when that file exists, so the local test certificate can be verified without becoming the public trust store.
4. Keycloak for this project uses PostgreSQL. The realm is `demo-deploy`. Its data volume is new. The administrative console is not routed. Peru and Spain remain separate Compose profiles, ledgers, and review databases.
5. `NET_ADMIN` is not granted. The application policy still refuses a real provider send. Route deletion is not the control. A TCP connection from the AI container to the provider endpoint succeeded on Docker Desktop, so this package is not a network isolation control. Secrets stay in `DEMO_RUN_DIR`, outside Git.
6. Mini HIS has no image in this repository. The hospital HL7 demonstration is not part of this Compose project. The summary agent was not run on this Compose.
7. Caddy publishes only the `demo-deploy` realm. The master realm, `/admin`, and the metrics paths return 404. Access logs drop cookies, authorization headers, and the OIDC query parameters `code`, `state`, `nonce`, and the token names.
8. A backup is a PostgreSQL dump plus a SQLite backup API copy of each country's ledger, Human Review database, and federation audit. An IAM session file is copied when it exists. Restoring the ledger does not restore Human Review. Rebuilding image tag `0.1.0` records the previous image id and is not, by itself, a rollback between versions.

## Consequences

Local HTTPS, OIDC, the two longitudinal demonstrations, and the isolated restore were checked on Docker Desktop. That is `VERIFIED_LOCAL`. A remote VM, public DNS, a public certificate, and an egress firewall are `PENDING_REMOTE`. The hospital image and the summary agent on this Compose are `PENDING_STACK`. The open provider socket is `RISK_ACCEPTED_FOR_DEMO` until the VM firewall is proven. An image rollback does not undo a database migration; the backup has to be restored. This is one VM, not high availability.

## References

- [demo-deploy-001-v1](../contracts/demo-deploy-001-v1.md)
- [demo-deploy-001](../demos/demo-deploy-001.md)
- [ADR-105](ADR-105-platform-001-local-demonstration.md)
