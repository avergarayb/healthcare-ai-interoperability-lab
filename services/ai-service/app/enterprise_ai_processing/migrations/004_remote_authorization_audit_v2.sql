CREATE TABLE aip_remote_authorization_audit_next (
    event_id TEXT NOT NULL PRIMARY KEY CHECK (length(event_id) = 36),
    audit_seq INTEGER NOT NULL UNIQUE CHECK (audit_seq > 0),
    contract TEXT NOT NULL,
    timestamp_us INTEGER NOT NULL CHECK (timestamp_us >= 0),
    event TEXT NOT NULL CHECK (event IN (
        'remote_authorization_registered', 'remote_authorization_evaluated',
        'remote_authorization_denied', 'remote_authorization_expired',
        'remote_authorization_revoked', 'remote_authorization_storage_failed')),
    outcome TEXT NOT NULL CHECK (outcome IN ('RECORDED', 'ALLOW', 'DENY', 'UNAVAILABLE')),
    reason TEXT NOT NULL,
    organization_id TEXT NOT NULL CHECK (length(organization_id) BETWEEN 1 AND 80),
    authorization_id TEXT CHECK (authorization_id IS NULL OR length(authorization_id) BETWEEN 1 AND 80),
    deployment_id TEXT CHECK (deployment_id IS NULL OR length(deployment_id) BETWEEN 1 AND 80),
    provider_id TEXT CHECK (provider_id IS NULL OR provider_id IN ('openai', 'gemini')),
    model_id TEXT CHECK (model_id IS NULL OR length(model_id) BETWEEN 1 AND 80),
    operation_id TEXT CHECK (operation_id IS NULL OR operation_id = 'vacation-days-v1'),
    actor_ref TEXT CHECK (actor_ref IS NULL OR length(actor_ref) BETWEEN 1 AND 80),
    CHECK ((contract = 'enterprise-remote-authorization-audit-v1' AND reason IN (
            'accepted', 'not_granted', 'scope_mismatch', 'not_yet_effective', 'authorization_expired',
            'revoked', 'wrong_deployment', 'wrong_provider', 'wrong_model', 'operation_denied',
            'revision_conflict', 'invalid_input', 'storage_unavailable', 'authority_unverifiable'))
        OR (contract = 'enterprise-remote-authorization-audit-v2' AND reason IN (
            'accepted', 'not_granted', 'scope_mismatch', 'not_yet_effective', 'authorization_expired',
            'revoked', 'wrong_deployment', 'wrong_provider', 'wrong_model', 'operation_denied',
            'revision_conflict', 'invalid_input', 'storage_unavailable', 'authority_unverifiable',
            'budget_exceeded')))
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
