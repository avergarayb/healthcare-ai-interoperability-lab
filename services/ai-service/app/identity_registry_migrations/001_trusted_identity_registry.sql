CREATE TABLE registry_metadata (
    singleton INTEGER PRIMARY KEY CHECK(singleton=1),
    contract_version TEXT NOT NULL CHECK(contract_version='trusted-identity-registry-v1'),
    provider_id TEXT NOT NULL,
    issuer TEXT NOT NULL,
    audience TEXT NOT NULL CHECK(audience='healthcare-ai-api'),
    revision INTEGER NOT NULL CHECK(revision>=1)
);
CREATE TABLE registry_principal (
    principal_id TEXT PRIMARY KEY,
    principal_type TEXT NOT NULL CHECK(principal_type='workload'),
    enabled INTEGER NOT NULL CHECK(enabled IN (0,1)),
    version INTEGER NOT NULL CHECK(version>=1),
    updated_at TEXT NOT NULL
);
CREATE TABLE registry_organization (
    organization_id TEXT PRIMARY KEY,
    enabled INTEGER NOT NULL CHECK(enabled IN (0,1))
);
CREATE TABLE registry_binding (
    binding_id TEXT PRIMARY KEY,
    issuer TEXT NOT NULL,
    external_subject TEXT NOT NULL,
    client_id TEXT NOT NULL,
    principal_id TEXT NOT NULL REFERENCES registry_principal(principal_id),
    enabled INTEGER NOT NULL CHECK(enabled IN (0,1)),
    version INTEGER NOT NULL CHECK(version>=1),
    updated_at TEXT NOT NULL,
    UNIQUE(issuer,external_subject),
    UNIQUE(issuer,client_id)
);
CREATE TABLE registry_membership (
    principal_id TEXT NOT NULL REFERENCES registry_principal(principal_id),
    organization_id TEXT NOT NULL REFERENCES registry_organization(organization_id),
    enabled INTEGER NOT NULL CHECK(enabled IN (0,1)),
    version INTEGER NOT NULL CHECK(version>=1),
    updated_at TEXT NOT NULL,
    PRIMARY KEY(principal_id,organization_id)
);
CREATE TABLE registry_permission (
    principal_id TEXT NOT NULL,
    organization_id TEXT NOT NULL,
    permission TEXT NOT NULL,
    enabled INTEGER NOT NULL CHECK(enabled IN (0,1)),
    version INTEGER NOT NULL CHECK(version>=1),
    updated_at TEXT NOT NULL,
    PRIMARY KEY(principal_id,organization_id,permission),
    FOREIGN KEY(principal_id,organization_id) REFERENCES registry_membership(principal_id,organization_id)
);
CREATE TABLE registry_policy_change_audit (
    revision INTEGER PRIMARY KEY CHECK(revision>=1),
    event_id TEXT NOT NULL UNIQUE,
    contract_version TEXT NOT NULL CHECK(contract_version='trusted-identity-registry-change-v1'),
    timestamp_utc TEXT NOT NULL,
    operation TEXT NOT NULL CHECK(operation IN ('init','enable-principal','disable-principal','enable-binding','disable-binding','grant-membership','revoke-membership','grant-permission','revoke-permission')),
    target_id TEXT NOT NULL,
    organization_id TEXT,
    permission TEXT,
    enabled INTEGER NOT NULL CHECK(enabled IN (0,1)),
    operator_kind TEXT NOT NULL CHECK(operator_kind='local_operator_unverified'),
    operator_label TEXT,
    operator_verified INTEGER NOT NULL CHECK(operator_verified=0)
);
