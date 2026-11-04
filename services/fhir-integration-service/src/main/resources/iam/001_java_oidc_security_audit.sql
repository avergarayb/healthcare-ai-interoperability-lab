CREATE TABLE java_oidc_security_audit_v1 (
    event_id TEXT PRIMARY KEY,
    timestamp_utc TEXT NOT NULL,
    contract_version TEXT NOT NULL CHECK(contract_version='java-oidc-security-audit-v1'),
    event_type TEXT NOT NULL CHECK(event_type='workload_authentication'),
    source_service TEXT NOT NULL CHECK(source_service='fhir-integration-service'),
    action TEXT NOT NULL CHECK(action='authenticate_workload'),
    route TEXT NOT NULL CHECK(route='/iam-lab/v1/workload-context'),
    outcome TEXT NOT NULL CHECK(outcome IN ('allowed','denied')),
    reason_code TEXT NOT NULL,
    actor_type TEXT NOT NULL CHECK(actor_type IN ('workload','anonymous')),
    actor_id TEXT,
    organization_id TEXT,
    provider_id TEXT,
    correlation_id TEXT NOT NULL,
    CHECK((outcome='allowed' AND actor_type='workload' AND actor_id IS NOT NULL AND organization_id IS NOT NULL)
       OR (outcome='denied' AND actor_type='anonymous' AND actor_id IS NULL AND organization_id IS NULL))
)
