CREATE TABLE aip_store_next (
    singleton INTEGER NOT NULL PRIMARY KEY CHECK (singleton = 1),
    schema_version INTEGER NOT NULL CHECK (schema_version = 6),
    contract TEXT NOT NULL CHECK (contract = 'enterprise-ai-processing-ledger-v6'),
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
SELECT singleton, 6, 'enterprise-ai-processing-ledger-v6', store_id, ?, v1_checksum, v2_checksum, v3_checksum,
    v4_checksum, revision, next_audit_seq, next_grounding_seq, next_remote_seq
FROM aip_store;

DROP TABLE aip_store;

ALTER TABLE aip_store_next RENAME TO aip_store;

CREATE TABLE aip_remote_execution_permit_next (
    authorization_id TEXT NOT NULL PRIMARY KEY CHECK (length(authorization_id) BETWEEN 1 AND 80),
    organization_id TEXT NOT NULL CHECK (length(organization_id) BETWEEN 1 AND 80),
    deployment_id TEXT NOT NULL CHECK (length(deployment_id) BETWEEN 1 AND 80),
    provider_id TEXT NOT NULL CHECK (provider_id IN ('openai', 'gemini')),
    model_id TEXT NOT NULL CHECK (length(model_id) BETWEEN 1 AND 80),
    operation_id TEXT NOT NULL,
    capability TEXT NOT NULL CHECK (capability = 'structured_output+usage_report'),
    policy_ref TEXT NOT NULL,
    policy_version INTEGER NOT NULL CHECK (policy_version = 1),
    status TEXT NOT NULL CHECK (status IN ('active', 'revoked')),
    valid_from_us INTEGER NOT NULL CHECK (valid_from_us >= 0),
    expires_at_us INTEGER NOT NULL,
    registered_at_us INTEGER NOT NULL CHECK (registered_at_us >= 0),
    registered_by TEXT NOT NULL CHECK (length(registered_by) BETWEEN 1 AND 80),
    revoked_at_us INTEGER CHECK (revoked_at_us IS NULL OR revoked_at_us >= 0),
    revoked_by TEXT CHECK (revoked_by IS NULL OR length(revoked_by) BETWEEN 1 AND 80),
    revocation_reason TEXT CHECK (revocation_reason IS NULL OR revocation_reason IN ('operator_revoked', 'scope_withdrawn')),
    principal_id TEXT NOT NULL CHECK (length(principal_id) BETWEEN 1 AND 64),
    resource_id TEXT NOT NULL CHECK (length(resource_id) BETWEEN 1 AND 64),
    budget_ceiling_microusd INTEGER NOT NULL CHECK (
        budget_ceiling_microusd >= 1 AND budget_ceiling_microusd <= 5000000),
    CHECK (valid_from_us < expires_at_us),
    CHECK ((operation_id = 'vacation-days-v1' AND policy_ref = 'model-gateway-policy-v1')
        OR (operation_id = 'lab-result-summary-v1' AND policy_ref = 'lab-result-summary-policy-v1')),
    CHECK ((deployment_id = 'openai-sdk-a' AND provider_id = 'openai' AND model_id = 'gpt-6-luna'
            AND budget_ceiling_microusd >= 303)
        OR (deployment_id = 'openai-offline-a' AND provider_id = 'openai' AND model_id = 'gpt-6-luna'
            AND budget_ceiling_microusd >= 191)
        OR (deployment_id = 'gemini-sdk-a' AND provider_id = 'gemini' AND model_id = 'gemini-3.5-flash-lite'
            AND budget_ceiling_microusd >= 657)
        OR (deployment_id = 'gemini-offline-a' AND provider_id = 'gemini' AND model_id = 'gemini-3.5-flash-lite'
            AND budget_ceiling_microusd >= 470)),
    CHECK ((status = 'active' AND revoked_at_us IS NULL AND revoked_by IS NULL AND revocation_reason IS NULL)
        OR (status = 'revoked' AND revoked_at_us IS NOT NULL AND revoked_by IS NOT NULL AND revocation_reason IS NOT NULL))
) STRICT;

INSERT INTO aip_remote_execution_permit_next (
    authorization_id, organization_id, deployment_id, provider_id, model_id, operation_id, capability,
    policy_ref, policy_version, status, valid_from_us, expires_at_us, registered_at_us, registered_by,
    revoked_at_us, revoked_by, revocation_reason, principal_id, resource_id, budget_ceiling_microusd)
SELECT authorization_id, organization_id, deployment_id, provider_id, model_id, operation_id, capability,
    policy_ref, policy_version, status, valid_from_us, expires_at_us, registered_at_us, registered_by,
    revoked_at_us, revoked_by, revocation_reason, principal_id, resource_id, budget_ceiling_microusd
FROM aip_remote_execution_permit;

CREATE TABLE aip_remote_execution_reservation_keep (
    reservation_id TEXT NOT NULL PRIMARY KEY,
    authorization_id TEXT NOT NULL UNIQUE,
    organization_id TEXT NOT NULL,
    status TEXT NOT NULL,
    held_at_us INTEGER NOT NULL,
    consumed_at_us INTEGER
);

INSERT INTO aip_remote_execution_reservation_keep
SELECT reservation_id, authorization_id, organization_id, status, held_at_us, consumed_at_us
FROM aip_remote_execution_reservation;

DROP TABLE aip_remote_execution_reservation;

DROP TABLE aip_remote_execution_permit;

ALTER TABLE aip_remote_execution_permit_next RENAME TO aip_remote_execution_permit;

CREATE UNIQUE INDEX aip_one_active_remote_permit
    ON aip_remote_execution_permit (
        organization_id, principal_id, resource_id, deployment_id, provider_id, model_id, operation_id)
    WHERE status = 'active';

CREATE TABLE aip_remote_execution_reservation (
    reservation_id TEXT NOT NULL PRIMARY KEY CHECK (length(reservation_id) = 36),
    authorization_id TEXT NOT NULL UNIQUE REFERENCES aip_remote_execution_permit(authorization_id),
    organization_id TEXT NOT NULL CHECK (length(organization_id) BETWEEN 1 AND 80),
    status TEXT NOT NULL CHECK (status IN ('held', 'consumed')),
    held_at_us INTEGER NOT NULL CHECK (held_at_us >= 0),
    consumed_at_us INTEGER CHECK (consumed_at_us IS NULL OR consumed_at_us >= 0),
    CHECK ((status = 'held' AND consumed_at_us IS NULL) OR (status = 'consumed' AND consumed_at_us IS NOT NULL))
) STRICT;

INSERT INTO aip_remote_execution_reservation (
    reservation_id, authorization_id, organization_id, status, held_at_us, consumed_at_us)
SELECT reservation_id, authorization_id, organization_id, status, held_at_us, consumed_at_us
FROM aip_remote_execution_reservation_keep;

DROP TABLE aip_remote_execution_reservation_keep;

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
    operation_id TEXT CHECK (
        operation_id IS NULL OR operation_id = 'vacation-days-v1' OR operation_id = 'lab-result-summary-v1'),
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
