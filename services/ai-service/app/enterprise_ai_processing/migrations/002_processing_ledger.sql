CREATE TABLE aip_store_next (
    singleton INTEGER NOT NULL PRIMARY KEY CHECK (singleton = 1),
    schema_version INTEGER NOT NULL CHECK (schema_version = 2),
    contract TEXT NOT NULL CHECK (contract = 'enterprise-ai-processing-ledger-v2'),
    store_id TEXT NOT NULL UNIQUE CHECK (length(store_id) = 36),
    migration_checksum TEXT NOT NULL CHECK (length(migration_checksum) = 64),
    v1_checksum TEXT NOT NULL CHECK (length(v1_checksum) = 64),
    revision INTEGER NOT NULL CHECK (revision BETWEEN 1 AND 1000000),
    next_audit_seq INTEGER NOT NULL CHECK (next_audit_seq > 0),
    next_grounding_seq INTEGER NOT NULL CHECK (next_grounding_seq > 0)
) STRICT;

INSERT INTO aip_store_next (
    singleton, schema_version, contract, store_id, migration_checksum, v1_checksum,
    revision, next_audit_seq, next_grounding_seq)
SELECT singleton, 2, 'enterprise-ai-processing-ledger-v2', store_id, ?, ?,
    revision, next_audit_seq, 1
FROM aip_store;

DROP TABLE aip_store;

ALTER TABLE aip_store_next RENAME TO aip_store;

CREATE TABLE aip_derived_revision (
    organization_id TEXT NOT NULL PRIMARY KEY CHECK (length(organization_id) BETWEEN 1 AND 80),
    revision INTEGER NOT NULL CHECK (revision BETWEEN 1 AND 1000000)
) STRICT;

CREATE TABLE aip_derived_delivery_grant (
    organization_id TEXT NOT NULL CHECK (length(organization_id) BETWEEN 1 AND 80),
    derived_grant_id TEXT NOT NULL CHECK (length(derived_grant_id) BETWEEN 1 AND 80),
    version INTEGER NOT NULL CHECK (version BETWEEN 1 AND 1000000),
    enabled INTEGER NOT NULL CHECK (enabled IN (0, 1)),
    principal_id TEXT NOT NULL CHECK (length(principal_id) BETWEEN 1 AND 80),
    instance_id TEXT NOT NULL CHECK (length(instance_id) BETWEEN 1 AND 80),
    tenant_id TEXT NOT NULL CHECK (length(tenant_id) BETWEEN 1 AND 80),
    resource_id TEXT NOT NULL CHECK (length(resource_id) BETWEEN 1 AND 80),
    recipient_id TEXT NOT NULL CHECK (length(recipient_id) BETWEEN 1 AND 80),
    content_kind TEXT NOT NULL CHECK (content_kind = 'grounded_extractive_answer'),
    delivery_operation TEXT NOT NULL CHECK (delivery_operation = 'enterprise.answer.deliver'),
    purpose TEXT NOT NULL CHECK (purpose = 'synthetic-policy-question-answering'),
    classification TEXT NOT NULL CHECK (classification = 'synthetic-internal'),
    registered_version INTEGER NOT NULL CHECK (registered_version BETWEEN 1 AND 1000000),
    processing_grant_id TEXT NOT NULL CHECK (length(processing_grant_id) BETWEEN 1 AND 80),
    processing_grant_version INTEGER NOT NULL CHECK (processing_grant_version BETWEEN 1 AND 1000000),
    processing_revision INTEGER NOT NULL CHECK (processing_revision BETWEEN 1 AND 1000000),
    derived_delivery_revision INTEGER NOT NULL CHECK (derived_delivery_revision BETWEEN 1 AND 1000000),
    valid_from_us INTEGER NOT NULL CHECK (valid_from_us >= 0),
    expires_at_us INTEGER NOT NULL,
    review_due_at_us INTEGER NOT NULL,
    PRIMARY KEY (organization_id, derived_grant_id),
    FOREIGN KEY (organization_id, processing_grant_id)
        REFERENCES aip_grant (organization_id, grant_id),
    CHECK (valid_from_us < expires_at_us AND valid_from_us < review_due_at_us)
) STRICT;

CREATE TABLE aip_grounding_audit (
    event_id TEXT NOT NULL PRIMARY KEY CHECK (length(event_id) = 36),
    audit_seq INTEGER NOT NULL UNIQUE CHECK (audit_seq > 0),
    contract TEXT NOT NULL CHECK (contract = 'enterprise-ai-processing-audit-v1'),
    timestamp_us INTEGER NOT NULL CHECK (timestamp_us >= 0),
    event TEXT NOT NULL CHECK (event IN (
        'derived_delivery_grant_changed', 'ai_derived_delivery_denied', 'ai_derived_delivery_suppressed')),
    outcome TEXT NOT NULL CHECK (outcome IN ('CHANGED', 'DENY', 'UNAVAILABLE', 'SUPPRESSED')),
    reason TEXT NOT NULL CHECK (reason IN (
        'accepted', 'derived_delivery_not_granted', 'scope_mismatch', 'authority_unverifiable',
        'authorization_expired', 'policy_changed', 'revision_conflict', 'lease_invalid', 'internal_failure')),
    organization_id TEXT CHECK (organization_id IS NULL OR length(organization_id) BETWEEN 1 AND 80),
    operation_id TEXT CHECK (operation_id IS NULL OR length(operation_id) = 36),
    principal_id TEXT CHECK (principal_id IS NULL OR length(principal_id) BETWEEN 1 AND 80),
    instance_id TEXT CHECK (instance_id IS NULL OR length(instance_id) BETWEEN 1 AND 80),
    tenant_id TEXT CHECK (tenant_id IS NULL OR length(tenant_id) BETWEEN 1 AND 80),
    resource_id TEXT CHECK (resource_id IS NULL OR length(resource_id) BETWEEN 1 AND 80),
    recipient_id TEXT CHECK (recipient_id IS NULL OR length(recipient_id) BETWEEN 1 AND 80),
    derived_grant_id TEXT CHECK (derived_grant_id IS NULL OR length(derived_grant_id) BETWEEN 1 AND 80),
    processing_grant_id TEXT CHECK (processing_grant_id IS NULL OR length(processing_grant_id) BETWEEN 1 AND 80),
    registered_version INTEGER CHECK (registered_version IS NULL OR registered_version BETWEEN 1 AND 1000000),
    processing_revision INTEGER CHECK (processing_revision IS NULL OR processing_revision BETWEEN 1 AND 1000000),
    derived_revision INTEGER CHECK (derived_revision IS NULL OR derived_revision BETWEEN 0 AND 1000000),
    previous_revision INTEGER NOT NULL CHECK (previous_revision BETWEEN 0 AND 1000000),
    revision INTEGER NOT NULL CHECK (revision BETWEEN 0 AND 1000000),
    CHECK ((organization_id IS NULL AND operation_id IS NULL AND principal_id IS NULL AND instance_id IS NULL
            AND tenant_id IS NULL AND resource_id IS NULL AND recipient_id IS NULL AND derived_grant_id IS NULL
            AND processing_grant_id IS NULL AND registered_version IS NULL AND processing_revision IS NULL
            AND event = 'ai_derived_delivery_denied' AND outcome = 'UNAVAILABLE'
            AND reason = 'authority_unverifiable' AND derived_revision = 0
            AND previous_revision = 0 AND revision = 0)
        OR organization_id IS NOT NULL),
    CHECK ((event = 'derived_delivery_grant_changed' AND outcome = 'CHANGED' AND reason = 'accepted'
            AND revision = previous_revision + 1)
        OR (event <> 'derived_delivery_grant_changed' AND revision = previous_revision))
) STRICT;

CREATE TABLE aip_delivery_decision (
    organization_id TEXT NOT NULL CHECK (length(organization_id) BETWEEN 1 AND 80),
    operation_id TEXT NOT NULL CHECK (length(operation_id) = 36),
    decision_ref TEXT NOT NULL UNIQUE CHECK (length(decision_ref) = 36),
    state TEXT NOT NULL CHECK (state IN ('SUPPRESSED', 'AUTHORIZED', 'RELEASE_UNCERTAIN')),
    derived_grant_id TEXT CHECK (derived_grant_id IS NULL OR length(derived_grant_id) BETWEEN 1 AND 80),
    processing_grant_id TEXT CHECK (processing_grant_id IS NULL OR length(processing_grant_id) BETWEEN 1 AND 80),
    recipient_id TEXT NOT NULL CHECK (length(recipient_id) BETWEEN 1 AND 80),
    processing_revision INTEGER NOT NULL CHECK (processing_revision BETWEEN 1 AND 1000000),
    derived_revision INTEGER NOT NULL CHECK (derived_revision BETWEEN 0 AND 1000000),
    decided_at_us INTEGER NOT NULL CHECK (decided_at_us >= 0),
    uncertainty_recorded INTEGER NOT NULL CHECK (uncertainty_recorded IN (0, 1)),
    PRIMARY KEY (organization_id, operation_id),
    FOREIGN KEY (organization_id, operation_id)
        REFERENCES aip_execution (organization_id, operation_id),
    FOREIGN KEY (organization_id, derived_grant_id)
        REFERENCES aip_derived_delivery_grant (organization_id, derived_grant_id),
    CHECK ((state = 'SUPPRESSED' AND uncertainty_recorded = 0)
        OR (state = 'AUTHORIZED' AND uncertainty_recorded = 0 AND derived_grant_id IS NOT NULL)
        OR (state = 'RELEASE_UNCERTAIN' AND uncertainty_recorded = 1))
) STRICT;

CREATE UNIQUE INDEX aip_one_enabled_derived_grant
    ON aip_derived_delivery_grant (organization_id, principal_id, resource_id, recipient_id)
    WHERE enabled = 1;
CREATE INDEX aip_grounding_audit_org
    ON aip_grounding_audit (organization_id, audit_seq);
CREATE UNIQUE INDEX aip_derived_grant_revision
    ON aip_grounding_audit (organization_id, revision)
    WHERE event = 'derived_delivery_grant_changed';
