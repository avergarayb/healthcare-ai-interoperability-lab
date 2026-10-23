# Security audit v1

Operational audit contract for the AI Service. This is not a clinical record and not a tamper-proof log. SQLite stores the rows for one process. An operator who can open the file can change it outside the application. The application API only appends and reads.

## Event

`security-audit-v1` has one event type in this task: `authentication` for the development login. Optional organization is omitted when the flow has no organization. The actor is the configured development principal identifier, or `anonymous` when the credential is rejected. The stored reference is `development-login`. It is not a patient, document, or tool response.

Metadata is an allowlist. This task allows only `route`. Tokens, cookies, passwords, model keys, and request bodies are rejected before insert.

## Failure

Development login writes the audit row before it issues a session. If the row cannot be stored, the response is unavailable and no session cookie is set. A normal rejection is returned only after the denied row is stored.

## Later producers

The same fields can record, in later tasks and without a separate audit service:

- FHIR Integration Service access, using `source_service` and `organization_id`.
- A future read-only tool call, using a minimized `resource_reference` and a `correlation_id`.
- Document or data-lake reads, with the source identifier and not the document body.
- Human Review closure, with the case identifier and outcome, not the clinical narrative.

New event types are added to the allowlist. They are not free-text strings.
