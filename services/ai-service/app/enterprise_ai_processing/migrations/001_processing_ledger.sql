CREATE TABLE aip_store (
    singleton INTEGER NOT NULL PRIMARY KEY CHECK (singleton = 1),
    schema_version INTEGER NOT NULL CHECK (schema_version = 1),
    contract TEXT NOT NULL CHECK (contract = 'enterprise-ai-processing-ledger-v1'),
    store_id TEXT NOT NULL UNIQUE CHECK (length(store_id) = 36),
    migration_checksum TEXT NOT NULL CHECK (length(migration_checksum) = 64),
    revision INTEGER NOT NULL CHECK (revision BETWEEN 1 AND 1000000),
    next_audit_seq INTEGER NOT NULL CHECK (next_audit_seq > 0)
) STRICT;

CREATE TABLE aip_profile (
    organization_id TEXT NOT NULL CHECK (length(organization_id) BETWEEN 1 AND 80),
    profile_id TEXT NOT NULL CHECK (profile_id = 'fake-enterprise-extractive-v1'),
    version INTEGER NOT NULL CHECK (version BETWEEN 1 AND 1000000),
    enabled INTEGER NOT NULL CHECK (enabled IN (0,1)),
    provider TEXT NOT NULL CHECK (provider = 'fake'),
    model_id TEXT NOT NULL CHECK (model_id = 'fake-enterprise-extractive-v1'),
    model_version TEXT NOT NULL CHECK (model_version = '1'),
    destination TEXT NOT NULL CHECK (destination = 'in-process-offline'),
    classification TEXT NOT NULL CHECK (classification = 'synthetic-internal'),
    processing_purpose TEXT NOT NULL CHECK (processing_purpose = 'synthetic-policy-question-answering'),
    retention TEXT NOT NULL CHECK (retention = 'ephemeral-no-retention'),
    tokenizer TEXT NOT NULL CHECK (tokenizer = 'fake-byte-v1'),
    question_set_id TEXT NOT NULL CHECK (question_set_id = 'vacation-question-v1'),
    valid_from_us INTEGER NOT NULL CHECK (valid_from_us >= 0),
    expires_at_us INTEGER NOT NULL,
    review_due_at_us INTEGER NOT NULL,
    max_sources INTEGER NOT NULL CHECK (max_sources = 1),
    max_source_bytes INTEGER NOT NULL CHECK (max_source_bytes BETWEEN 1 AND 1024),
    max_question_bytes INTEGER NOT NULL CHECK (max_question_bytes BETWEEN 1 AND 256),
    max_input_bytes INTEGER NOT NULL CHECK (max_input_bytes BETWEEN 1 AND 2048),
    max_output_bytes INTEGER NOT NULL CHECK (max_output_bytes BETWEEN 1 AND 512),
    max_output_units INTEGER NOT NULL CHECK (max_output_units BETWEEN 1 AND 256),
    max_seconds INTEGER NOT NULL CHECK (max_seconds BETWEEN 1 AND 5),
    max_retries INTEGER NOT NULL CHECK (max_retries = 0),
    max_concurrent INTEGER NOT NULL CHECK (max_concurrent = 1),
    PRIMARY KEY (organization_id, profile_id),
    CHECK (valid_from_us < expires_at_us AND valid_from_us < review_due_at_us)
) STRICT;

CREATE TABLE aip_grant (
    organization_id TEXT NOT NULL CHECK (length(organization_id) BETWEEN 1 AND 80),
    grant_id TEXT NOT NULL CHECK (length(grant_id) BETWEEN 1 AND 80),
    version INTEGER NOT NULL CHECK (version BETWEEN 1 AND 1000000),
    enabled INTEGER NOT NULL CHECK (enabled IN (0,1)),
    principal_id TEXT NOT NULL CHECK (length(principal_id) BETWEEN 1 AND 80),
    principal_type TEXT NOT NULL CHECK (principal_type = 'workload'),
    instance_id TEXT NOT NULL CHECK (length(instance_id) BETWEEN 1 AND 80),
    tenant_id TEXT NOT NULL CHECK (length(tenant_id) BETWEEN 1 AND 80),
    resource_id TEXT NOT NULL CHECK (length(resource_id) BETWEEN 1 AND 80),
    recipient_id TEXT NOT NULL CHECK (length(recipient_id) BETWEEN 1 AND 80),
    read_operation TEXT NOT NULL CHECK (read_operation = 'document.content.read'),
    read_purpose TEXT NOT NULL CHECK (read_purpose = 'synthetic-demonstration'),
    processing_operation TEXT NOT NULL CHECK (processing_operation = 'enterprise.document.answer'),
    processing_purpose TEXT NOT NULL CHECK (processing_purpose = 'synthetic-policy-question-answering'),
    classification TEXT NOT NULL CHECK (classification = 'synthetic-internal'),
    profile_id TEXT NOT NULL,
    profile_version INTEGER NOT NULL CHECK (profile_version BETWEEN 1 AND 1000000),
    approval TEXT NOT NULL CHECK (approval = 'not_required'),
    approval_ref TEXT NOT NULL CHECK (length(approval_ref) BETWEEN 1 AND 80),
    valid_from_us INTEGER NOT NULL CHECK (valid_from_us >= 0),
    expires_at_us INTEGER NOT NULL,
    review_due_at_us INTEGER NOT NULL,
    max_sources INTEGER NOT NULL CHECK (max_sources = 1),
    max_source_bytes INTEGER NOT NULL CHECK (max_source_bytes BETWEEN 1 AND 1024),
    max_question_bytes INTEGER NOT NULL CHECK (max_question_bytes BETWEEN 1 AND 256),
    max_input_bytes INTEGER NOT NULL CHECK (max_input_bytes BETWEEN 1 AND 2048),
    max_output_bytes INTEGER NOT NULL CHECK (max_output_bytes BETWEEN 1 AND 512),
    max_output_units INTEGER NOT NULL CHECK (max_output_units BETWEEN 1 AND 256),
    max_seconds INTEGER NOT NULL CHECK (max_seconds BETWEEN 1 AND 5),
    max_retries INTEGER NOT NULL CHECK (max_retries = 0),
    max_concurrent INTEGER NOT NULL CHECK (max_concurrent = 1),
    PRIMARY KEY (organization_id, grant_id),
    UNIQUE (organization_id, grant_id, profile_id),
    FOREIGN KEY (organization_id, profile_id)
        REFERENCES aip_profile (organization_id, profile_id),
    CHECK (valid_from_us < expires_at_us AND valid_from_us < review_due_at_us)
) STRICT;

CREATE TABLE aip_execution (
    organization_id TEXT NOT NULL,
    operation_id TEXT NOT NULL CHECK (length(operation_id) = 36),
    attempt_version INTEGER NOT NULL CHECK (attempt_version BETWEEN 1 AND 1000000),
    owner_ref TEXT NOT NULL CHECK (length(owner_ref) = 36),
    process_epoch TEXT NOT NULL CHECK (length(process_epoch) = 36),
    lease_id TEXT NOT NULL UNIQUE CHECK (length(lease_id) = 36),
    decision_ref TEXT NOT NULL CHECK (length(decision_ref) = 36),
    principal_id TEXT NOT NULL,
    principal_type TEXT NOT NULL CHECK (principal_type = 'workload'),
    instance_id TEXT NOT NULL,
    binding_id TEXT NOT NULL,
    tenant_id TEXT NOT NULL,
    resource_id TEXT NOT NULL,
    recipient_id TEXT NOT NULL,
    source_ref TEXT NOT NULL,
    read_correlation_id TEXT NOT NULL CHECK (length(read_correlation_id) = 36),
    registered_version INTEGER NOT NULL CHECK (registered_version BETWEEN 1 AND 1000000),
    content_revision INTEGER NOT NULL CHECK (content_revision BETWEEN 1 AND 1000000),
    connector_revision INTEGER NOT NULL CHECK (connector_revision BETWEEN 1 AND 1000000),
    processing_revision INTEGER NOT NULL CHECK (processing_revision BETWEEN 1 AND 1000000),
    grant_id TEXT NOT NULL,
    grant_version INTEGER NOT NULL CHECK (grant_version BETWEEN 1 AND 1000000),
    approval_ref TEXT NOT NULL,
    profile_id TEXT NOT NULL,
    profile_version INTEGER NOT NULL CHECK (profile_version BETWEEN 1 AND 1000000),
    destination TEXT NOT NULL CHECK (destination = 'in-process-offline'),
    classification TEXT NOT NULL CHECK (classification = 'synthetic-internal'),
    read_operation TEXT NOT NULL CHECK (read_operation = 'document.content.read'),
    read_purpose TEXT NOT NULL CHECK (read_purpose = 'synthetic-demonstration'),
    processing_operation TEXT NOT NULL CHECK (processing_operation = 'enterprise.document.answer'),
    processing_purpose TEXT NOT NULL CHECK (processing_purpose = 'synthetic-policy-question-answering'),
    question_id TEXT NOT NULL CHECK (question_id = 'vacation-days-v1'),
    source_bytes INTEGER NOT NULL CHECK (source_bytes BETWEEN 1 AND 1024),
    question_bytes INTEGER NOT NULL CHECK (question_bytes BETWEEN 1 AND 256),
    input_bytes INTEGER NOT NULL CHECK (input_bytes BETWEEN 1 AND 2048),
    reserved_output_bytes INTEGER NOT NULL CHECK (reserved_output_bytes BETWEEN 1 AND 512),
    reserved_output_units INTEGER NOT NULL CHECK (reserved_output_units BETWEEN 1 AND 256),
    max_seconds INTEGER NOT NULL CHECK (max_seconds BETWEEN 1 AND 5),
    authorized_at_us INTEGER NOT NULL CHECK (authorized_at_us >= 0),
    expires_at_us INTEGER NOT NULL,
    consumed_at_us INTEGER,
    entered_at_us INTEGER,
    finished_at_us INTEGER,
    lease_state TEXT NOT NULL CHECK (lease_state IN ('ISSUED','CONSUMED','EXPIRED','REVOKED','CLOSED')),
    run_state TEXT NOT NULL CHECK (run_state IN
        ('INTENT','CONSUMED','ENTERED','COMPLETED','INVALID','FAILED','CANCELLED','TIMED_OUT','REVOKED','EXPIRED','UNKNOWN')),
    reservation_state TEXT NOT NULL CHECK (reservation_state IN ('HELD','RELEASED','CHARGED','UNCERTAIN')),
    result_code TEXT CHECK (result_code IN ('CANDIDATE','NO_EVIDENCE','INVALID','ERROR','TIMEOUT','CANCELLED','UNKNOWN','REVOKED')),
    input_units_observed INTEGER CHECK (input_units_observed BETWEEN 0 AND 2048),
    output_bytes_observed INTEGER CHECK (output_bytes_observed BETWEEN 0 AND 1000000),
    output_units_observed INTEGER CHECK (output_units_observed BETWEEN 0 AND 1000000),
    elapsed_us INTEGER CHECK (elapsed_us >= 0),
    PRIMARY KEY (organization_id, operation_id),
    FOREIGN KEY (organization_id, grant_id, profile_id)
        REFERENCES aip_grant (organization_id, grant_id, profile_id),
    CHECK (input_bytes >= source_bytes + question_bytes),
    CHECK (expires_at_us > authorized_at_us
        AND expires_at_us <= authorized_at_us + max_seconds * 1000000),
    CHECK (consumed_at_us IS NULL OR consumed_at_us >= authorized_at_us),
    CHECK (entered_at_us IS NULL OR (consumed_at_us IS NOT NULL AND entered_at_us >= consumed_at_us)),
    CHECK (finished_at_us IS NULL OR finished_at_us >= authorized_at_us),
    CHECK ((run_state = 'INTENT' AND lease_state = 'ISSUED' AND consumed_at_us IS NULL AND reservation_state = 'HELD')
        OR (run_state = 'CONSUMED' AND lease_state = 'CONSUMED' AND consumed_at_us IS NOT NULL AND reservation_state = 'HELD')
        OR (run_state = 'ENTERED' AND lease_state = 'CONSUMED' AND entered_at_us IS NOT NULL AND reservation_state = 'HELD')
        OR (run_state IN ('COMPLETED','INVALID','FAILED','CANCELLED','TIMED_OUT','REVOKED','EXPIRED','UNKNOWN')
            AND lease_state IN ('CLOSED','REVOKED','EXPIRED') AND reservation_state <> 'HELD'))
) STRICT;

CREATE UNIQUE INDEX aip_one_active_scope
    ON aip_execution (organization_id, instance_id, profile_id)
    WHERE reservation_state IN ('HELD','UNCERTAIN');
CREATE INDEX aip_execution_recovery ON aip_execution (process_epoch, run_state);

CREATE TABLE aip_audit (
    event_id TEXT NOT NULL PRIMARY KEY CHECK (length(event_id) = 36),
    audit_seq INTEGER NOT NULL UNIQUE CHECK (audit_seq > 0),
    contract TEXT NOT NULL CHECK (contract = 'enterprise-ai-processing-audit-v1'),
    timestamp_us INTEGER NOT NULL CHECK (timestamp_us >= 0),
    event TEXT NOT NULL CHECK (event IN
        ('ai_processing_evaluated','ai_processing_profile_selected','ai_processing_budget_approved',
         'ai_processing_authorized','ai_provider_invocation_observed','ai_provider_result_observed',
         'ai_processing_cancelled','ai_processing_error','ai_processing_revocation_detected',
         'ai_processing_policy_changed')),
    phase TEXT NOT NULL CHECK (phase IN ('evaluation','preparation','entry','result','cleanup','administration')),
    outcome TEXT NOT NULL CHECK (outcome IN
        ('ALLOW','DENY','UNAVAILABLE','AUTHORIZED','OBSERVED','CANCELLED','ERROR','REVOKED','CHANGED','UNKNOWN')),
    reason TEXT NOT NULL CHECK (reason IN
        ('processing_eligible_not_executable','invalid_input','identity_invalid','scope_mismatch',
         'source_evidence_invalid','processing_not_granted','classification_denied','purpose_denied',
         'profile_denied','destination_denied','retention_unverified','approval_required',
         'policy_changed','authorization_expired','budget_exceeded','authority_unverifiable',
         'provider_unavailable','provider_result_invalid','audit_unavailable','cancelled','internal_failure',
         'accepted','lease_invalid','execution_unknown','deadline_exceeded','revision_conflict')),
    actor_kind TEXT NOT NULL CHECK (actor_kind IN ('anonymous','workload','synthetic_administrator')),
    actor_ref TEXT,
    organization_id TEXT,
    operation_id TEXT,
    decision_ref TEXT,
    read_correlation_id TEXT,
    instance_id TEXT,
    resource_id TEXT,
    grant_id TEXT,
    grant_version INTEGER CHECK (grant_version BETWEEN 1 AND 1000000),
    profile_id TEXT,
    profile_version INTEGER CHECK (profile_version BETWEEN 1 AND 1000000),
    connector_revision INTEGER CHECK (connector_revision BETWEEN 1 AND 1000000),
    previous_revision INTEGER NOT NULL CHECK (previous_revision BETWEEN 0 AND 1000000),
    revision INTEGER NOT NULL CHECK (revision BETWEEN 1 AND 1000000),
    attempt_version INTEGER CHECK (attempt_version BETWEEN 1 AND 1000000),
    lease_ref TEXT,
    input_units INTEGER CHECK (input_units BETWEEN 0 AND 2048),
    output_units INTEGER CHECK (output_units BETWEEN 0 AND 1000000),
    entity_kind TEXT CHECK (entity_kind IN ('store','profile','grant','execution')),
    entity_ref TEXT,
    CHECK ((actor_kind = 'anonymous' AND actor_ref IS NULL AND organization_id IS NULL
        AND operation_id IS NULL AND decision_ref IS NULL AND read_correlation_id IS NULL
        AND instance_id IS NULL AND resource_id IS NULL AND grant_id IS NULL AND grant_version IS NULL
        AND profile_id IS NULL AND profile_version IS NULL AND connector_revision IS NULL
        AND attempt_version IS NULL AND lease_ref IS NULL AND input_units IS NULL
        AND output_units IS NULL AND entity_kind IS NULL AND entity_ref IS NULL)
        OR (actor_kind <> 'anonymous' AND actor_ref IS NOT NULL AND organization_id IS NOT NULL)),
    CHECK ((event = 'ai_processing_policy_changed' AND outcome = 'CHANGED'
        AND actor_kind = 'synthetic_administrator' AND revision = previous_revision + 1)
        OR (event <> 'ai_processing_policy_changed' AND revision = previous_revision))
) STRICT;

CREATE INDEX aip_audit_org ON aip_audit (organization_id, audit_seq);
CREATE INDEX aip_audit_operation ON aip_audit (organization_id, operation_id, audit_seq);
CREATE UNIQUE INDEX aip_policy_change_revision ON aip_audit (revision)
    WHERE event = 'ai_processing_policy_changed';
