# Java OIDC Security Audit v1

Additive TASK 005 laboratory contract for the [Java workload boundary](java-oidc-workload-v1.md). Existing Federation audit has participant-specific events/actors and cannot safely label these workload decisions. Its producers, schema and store are untouched; no actor is renamed to force compatibility.

`IAM_JAVA_WORKLOAD_AUDIT_DB_PATH` explicitly names a dedicated absolute SQLite file, distinct from configured Federation audit and exchange correlation stores. No default or shared Python database. Initialization is lazy at the first decision, never disabled startup. Foreign objects/schema/version, invalid paths, symlinks/reparse points or unavailable storage fail closed. Operator/OS-owned file permissions remain trusted; path checks are not an OS sandbox or encryption.

Own [initial schema](../../services/fhir-integration-service/src/main/resources/iam/001_java_oidc_security_audit.sql), table `java_oidc_security_audit_v1`, schema version 1. Each normal GET boundary decision appends one event before allowing projection or returning a normal denial:

- UUID event id, UTC timestamp and canonical UUID correlation.
- Contract `java-oidc-security-audit-v1`, event `workload_authentication`.
- Source `fhir-integration-service`, action `authenticate_workload`, fixed IAM route.
- Outcome `allowed`/`denied`, bounded server-controlled reason.
- Allowed actor `workload` with internal principal/organization; denied actor `anonymous` with null identity/organization.
- Optional provider id only from locally validated configuration.

Closed reasons cover access granted; credential missing/ambiguous/malformed/conflicting; incomplete/disabled configuration; provider unavailable; discovery/key trust/availability/unknown kid; algorithm/key-source/signature rejection; expiry/time/purpose/audience/issuer; unknown/disabled binding or principal; organization denial and insufficient local permission. No JWT, token hash, Authorization/cookie, client secret, external subject/issuer, full key/JWKS, claims, request body, arbitrary metadata, clinical payload or raw exception is stored.

The append owns a process-local writer lock, validates the event combination, checks the expected schema, then uses WAL, a bounded 1,000 ms busy timeout, parameterized insertion and `BEGIN IMMEDIATE`/commit. Initial schema/version and event are in the same transaction. Insert/storage failure rolls back and suppresses context. Foreign stores are inspected before journal-mode/schema changes; they are not adopted or migrated. Historical migrations remain untouched.

Mandatory audit failure returns generic 503 even after valid authentication/permission or for an otherwise normal denial. It cannot reliably persist an error into the same failed sink. Instead a fixed diagnostic `java_oidc_audit_unavailable` with sanitized correlation is logged, without exception/token/path, and **no fabricated success/error row or fallback sink** is claimed. This diagnostic is not equivalent to durable error-event coverage. HTTP/parser/firewall failures before this filter are likewise not fabricated as application audit events.

Expiry is rechecked after persistence and by the controller. An allowed row may precede a final 401 if expiry occurs before delivery; it records an access decision, not business success. Authentication, authorization, access audit and clinical business attribution remain distinct. There is no business write or distributed transaction with Python's registry/audit or Java's other stores.

One-process local laboratory persistence only: no tamper evidence, encryption, retention service, enterprise SIEM, production administrator identity, global correlation or distributed writer guarantee. Actual fault-injection categories and persistence evidence are reported in the [runbook](../design/java-oidc-resource-server-v1.md).
