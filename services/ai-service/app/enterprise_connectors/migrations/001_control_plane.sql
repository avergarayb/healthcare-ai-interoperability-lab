CREATE TABLE eca_metadata (
    singleton INTEGER PRIMARY KEY CHECK(singleton=1),
    contract_version TEXT NOT NULL CHECK(contract_version='enterprise-connector-control-plane-v1'),
    migration_sha256 TEXT NOT NULL CHECK(length(migration_sha256)=64),
    revision INTEGER NOT NULL CHECK(revision>=1)
);
CREATE TABLE eca_definition (
    definition_id TEXT PRIMARY KEY, organization_id TEXT NOT NULL,
    version INTEGER NOT NULL CHECK(version>0), payload TEXT NOT NULL CHECK(json_valid(payload)),
    UNIQUE(organization_id,definition_id)
);
CREATE TABLE eca_principal (
    principal_id TEXT PRIMARY KEY, organization_id TEXT NOT NULL,
    payload TEXT NOT NULL CHECK(json_valid(payload)), UNIQUE(organization_id,principal_id)
);
CREATE TABLE eca_instance (
    instance_id TEXT PRIMARY KEY, organization_id TEXT NOT NULL, definition_id TEXT NOT NULL,
    binding_id TEXT, credential_ref TEXT,
    state TEXT NOT NULL CHECK(state IN ('DRAFT','PENDING_APPROVAL','ACTIVE','SUSPENDED','REVOKED','OFFBOARDED')),
    version INTEGER NOT NULL CHECK(version>0), approved_version INTEGER,
    UNIQUE(organization_id,instance_id),
    FOREIGN KEY(organization_id,definition_id) REFERENCES eca_definition(organization_id,definition_id),
    FOREIGN KEY(organization_id,instance_id,binding_id) REFERENCES eca_binding(organization_id,instance_id,binding_id) DEFERRABLE INITIALLY DEFERRED,
    FOREIGN KEY(organization_id,instance_id,credential_ref) REFERENCES eca_credential(organization_id,instance_id,reference_id) DEFERRABLE INITIALLY DEFERRED
);
CREATE TABLE eca_binding (
    binding_id TEXT PRIMARY KEY, organization_id TEXT NOT NULL, instance_id TEXT NOT NULL UNIQUE,
    payload TEXT NOT NULL CHECK(json_valid(payload)), version INTEGER NOT NULL CHECK(version>0),
    UNIQUE(organization_id,instance_id,binding_id),
    FOREIGN KEY(organization_id,instance_id) REFERENCES eca_instance(organization_id,instance_id)
);
CREATE TABLE eca_resource (
    resource_id TEXT PRIMARY KEY, organization_id TEXT NOT NULL, instance_id TEXT NOT NULL,
    parent_id TEXT, version INTEGER NOT NULL CHECK(version>0), payload TEXT NOT NULL CHECK(json_valid(payload)),
    UNIQUE(organization_id,instance_id,resource_id),
    FOREIGN KEY(organization_id,instance_id) REFERENCES eca_instance(organization_id,instance_id),
    FOREIGN KEY(organization_id,instance_id,parent_id) REFERENCES eca_resource(organization_id,instance_id,resource_id)
);
CREATE TABLE eca_credential (
    reference_id TEXT PRIMARY KEY, organization_id TEXT NOT NULL, instance_id TEXT NOT NULL, binding_id TEXT NOT NULL,
    reference_type TEXT NOT NULL CHECK(reference_type='synthetic'), custody_ref TEXT NOT NULL,
    review_due_at TEXT NOT NULL,
    state TEXT NOT NULL CHECK(state IN ('PENDING','ACTIVE','SUSPENDED','REVOKED','EXPIRED','REPLACED')),
    version INTEGER NOT NULL CHECK(version>0), payload TEXT NOT NULL CHECK(json_valid(payload)),
    UNIQUE(organization_id,instance_id,reference_id),
    FOREIGN KEY(organization_id,instance_id,binding_id) REFERENCES eca_binding(organization_id,instance_id,binding_id)
);
CREATE TABLE eca_external_grant (
    grant_id TEXT PRIMARY KEY, organization_id TEXT NOT NULL, instance_id TEXT NOT NULL, resource_id TEXT NOT NULL,
    version INTEGER NOT NULL CHECK(version>0), payload TEXT NOT NULL CHECK(json_valid(payload)),
    FOREIGN KEY(organization_id,instance_id,resource_id) REFERENCES eca_resource(organization_id,instance_id,resource_id)
);
CREATE TABLE eca_principal_grant (
    grant_id TEXT PRIMARY KEY, organization_id TEXT NOT NULL, instance_id TEXT NOT NULL, resource_id TEXT NOT NULL,
    principal_id TEXT NOT NULL, version INTEGER NOT NULL CHECK(version>0), payload TEXT NOT NULL CHECK(json_valid(payload)),
    FOREIGN KEY(organization_id,instance_id,resource_id) REFERENCES eca_resource(organization_id,instance_id,resource_id),
    FOREIGN KEY(organization_id,principal_id) REFERENCES eca_principal(organization_id,principal_id)
);
CREATE TABLE eca_admin_audit (
    event_id TEXT PRIMARY KEY, correlation_id TEXT NOT NULL, timestamp_utc TEXT NOT NULL,
    contract_version TEXT NOT NULL CHECK(contract_version='enterprise-connector-administration-audit-v1'),
    actor_type TEXT NOT NULL CHECK(actor_type IN ('synthetic_administrator','synthetic_operator','anonymous')),
    actor_id TEXT, organization_id TEXT, operation TEXT NOT NULL,
    entity_type TEXT NOT NULL, entity_id TEXT, related_entity_id TEXT,
    previous_revision INTEGER NOT NULL, revision INTEGER NOT NULL,
    previous_version INTEGER, version INTEGER, previous_state TEXT, state TEXT,
    outcome TEXT NOT NULL CHECK(outcome IN ('allowed','denied')), reason TEXT NOT NULL,
    CHECK((outcome='allowed' AND revision=previous_revision+1 AND actor_id IS NOT NULL AND organization_id IS NOT NULL)
       OR (outcome='denied' AND revision=previous_revision))
);
CREATE UNIQUE INDEX eca_admin_committed_revision ON eca_admin_audit(revision) WHERE outcome='allowed';
CREATE TABLE eca_access_audit (
    event_id TEXT PRIMARY KEY, correlation_id TEXT NOT NULL, timestamp_utc TEXT NOT NULL,
    contract_version TEXT NOT NULL CHECK(contract_version='connector-security-audit-v1'),
    phase TEXT NOT NULL CHECK(phase IN ('local_authorization','external_execution','delivery')),
    outcome TEXT NOT NULL CHECK(outcome IN ('LOCAL_ALLOW','DENY','UNAVAILABLE','EXTERNAL_SUCCESS','EXTERNAL_DENIED','DELIVERY_ALLOWED','DELIVERY_SUPPRESSED')),
    reason TEXT NOT NULL, policy_revision INTEGER NOT NULL CHECK(policy_revision>=1),
    actor_type TEXT NOT NULL CHECK(actor_type IN ('workload','anonymous')),
    actor_id TEXT, organization_id TEXT, instance_id TEXT, resource_id TEXT, operation TEXT,
    CHECK((actor_type='anonymous' AND actor_id IS NULL AND organization_id IS NULL)
       OR (actor_type='workload' AND actor_id IS NOT NULL AND organization_id IS NOT NULL))
);
