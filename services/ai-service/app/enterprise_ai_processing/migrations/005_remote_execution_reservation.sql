CREATE TABLE aip_store_next (
    singleton INTEGER NOT NULL PRIMARY KEY CHECK (singleton = 1),
    schema_version INTEGER NOT NULL CHECK (schema_version = 5),
    contract TEXT NOT NULL CHECK (contract = 'enterprise-ai-processing-ledger-v5'),
    store_id TEXT NOT NULL UNIQUE CHECK (length(store_id) = 36),
    migration_checksum TEXT NOT NULL CHECK (length(migration_checksum) = 64),
    v1_checksum TEXT NOT NULL CHECK (length(v1_checksum) = 64),
    v2_checksum TEXT NOT NULL CHECK (length(v2_checksum) = 64),
    v3_checksum TEXT NOT NULL CHECK (length(v3_checksum) = 64),
    v4_checksum TEXT NOT NULL CHECK (length(v4_checksum) = 64),
    revision INTEGER NOT NULL CHECK (revision BETWEEN 1 AND 1000000),
    next_audit_seq INTEGER NOT NULL CHECK (next_audit_seq > 0),
    next_grounding_seq INTEGER NOT NULL CHECK (next_grounding_seq > 0),
    next_remote_seq INTEGER NOT NULL CHECK (next_remote_seq > 0)
) STRICT;

INSERT INTO aip_store_next (
    singleton, schema_version, contract, store_id, migration_checksum, v1_checksum, v2_checksum, v3_checksum,
    v4_checksum, revision, next_audit_seq, next_grounding_seq, next_remote_seq)
SELECT singleton, 5, 'enterprise-ai-processing-ledger-v5', store_id, ?, v1_checksum, v2_checksum, v3_checksum, ?,
    revision, next_audit_seq, next_grounding_seq, next_remote_seq
FROM aip_store;

DROP TABLE aip_store;

ALTER TABLE aip_store_next RENAME TO aip_store;

CREATE TABLE aip_remote_execution_reservation (
    reservation_id TEXT NOT NULL PRIMARY KEY CHECK (length(reservation_id) = 36),
    authorization_id TEXT NOT NULL UNIQUE REFERENCES aip_remote_execution_permit(authorization_id),
    organization_id TEXT NOT NULL CHECK (length(organization_id) BETWEEN 1 AND 80),
    status TEXT NOT NULL CHECK (status IN ('held', 'consumed')),
    held_at_us INTEGER NOT NULL CHECK (held_at_us >= 0),
    consumed_at_us INTEGER CHECK (consumed_at_us IS NULL OR consumed_at_us >= 0),
    CHECK ((status = 'held' AND consumed_at_us IS NULL) OR (status = 'consumed' AND consumed_at_us IS NOT NULL))
) STRICT;

CREATE UNIQUE INDEX aip_one_held_remote_reservation
    ON aip_remote_execution_reservation (authorization_id)
    WHERE status = 'held';

CREATE TABLE aip_remote_authorization_audit_next (
    event_id TEXT NOT NULL PRIMARY KEY CHECK (length(event_id) = 36),
    audit_seq INTEGER NOT NULL UNIQUE CHECK (audit_seq > 0),
    contract TEXT NOT NULL,
    timestamp_us INTEGER NOT NULL CHECK (timestamp_us >= 0),
    event TEXT NOT NULL CHECK (event IN (
        'remote_authorization_registered', 'remote_authorization_evaluated',
        'remote_authorization_denied', 'remote_authorization_expired',
        'remote_authorization_revoked', 'remote_authorization_storage_failed',
        'remote_reservation_consumed')),
    outcome TEXT NOT NULL CHECK (outcome IN ('RECORDED', 'ALLOW', 'DENY', 'UNAVAILABLE')),
    reason TEXT NOT NULL,
    organization_id TEXT NOT NULL CHECK (length(organization_id) BETWEEN 1 AND 80),
    authorization_id TEXT CHECK (authorization_id IS NULL OR length(authorization_id) BETWEEN 1 AND 80),
    deployment_id TEXT CHECK (deployment_id IS NULL OR length(deployment_id) BETWEEN 1 AND 80),
    provider_id TEXT CHECK (provider_id IS NULL OR provider_id IN ('openai', 'gemini')),
    model_id TEXT CHECK (model_id IS NULL OR length(model_id) BETWEEN 1 AND 80),
    operation_id TEXT CHECK (operation_id IS NULL OR operation_id = 'vacation-days-v1'),
    actor_ref TEXT CHECK (actor_ref IS NULL OR length(actor_ref) BETWEEN 1 AND 80),
    CHECK ((contract = 'enterprise-remote-authorization-audit-v1' AND event != 'remote_reservation_consumed' AND reason IN (
            'accepted', 'not_granted', 'scope_mismatch', 'not_yet_effective', 'authorization_expired',
            'revoked', 'wrong_deployment', 'wrong_provider', 'wrong_model', 'operation_denied',
            'revision_conflict', 'invalid_input', 'storage_unavailable', 'authority_unverifiable'))
        OR (contract = 'enterprise-remote-authorization-audit-v2' AND event != 'remote_reservation_consumed' AND reason IN (
            'accepted', 'not_granted', 'scope_mismatch', 'not_yet_effective', 'authorization_expired',
            'revoked', 'wrong_deployment', 'wrong_provider', 'wrong_model', 'operation_denied',
            'revision_conflict', 'invalid_input', 'storage_unavailable', 'authority_unverifiable',
            'budget_exceeded'))
        OR (contract = 'enterprise-remote-authorization-audit-v3' AND reason IN (
            'accepted', 'not_granted', 'scope_mismatch', 'not_yet_effective', 'authorization_expired',
            'revoked', 'wrong_deployment', 'wrong_provider', 'wrong_model', 'operation_denied',
            'revision_conflict', 'invalid_input', 'storage_unavailable', 'authority_unverifiable',
            'budget_exceeded', 'replay_denied')))
) STRICT;

INSERT INTO aip_remote_authorization_audit_next (
    event_id, audit_seq, contract, timestamp_us, event, outcome, reason, organization_id, authorization_id,
    deployment_id, provider_id, model_id, operation_id, actor_ref)
SELECT event_id, audit_seq, contract, timestamp_us, event, outcome, reason, organization_id, authorization_id,
    deployment_id, provider_id, model_id, operation_id, actor_ref
FROM aip_remote_authorization_audit;

DROP TABLE aip_remote_authorization_audit;

ALTER TABLE aip_remote_authorization_audit_next RENAME TO aip_remote_authorization_audit;

CREATE INDEX aip_remote_authorization_audit_org
    ON aip_remote_authorization_audit (organization_id, audit_seq);
