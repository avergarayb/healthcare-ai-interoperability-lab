BEGIN IMMEDIATE;

CREATE TABLE security_audit_events (
    event_id TEXT PRIMARY KEY CHECK (
        length(event_id) = 36
        AND event_id NOT GLOB '*[^0-9a-f-]*'
    ),
    timestamp_utc TEXT NOT NULL CHECK (substr(timestamp_utc, -1) = 'Z'),
    event_type TEXT NOT NULL,
    actor_type TEXT NOT NULL,
    actor_id TEXT NOT NULL,
    organization_id TEXT,
    source_service TEXT NOT NULL,
    resource_type TEXT NOT NULL,
    resource_reference TEXT,
    action TEXT NOT NULL,
    outcome TEXT NOT NULL,
    reason_code TEXT NOT NULL,
    correlation_id TEXT NOT NULL,
    metadata_json TEXT NOT NULL,
    contract_version TEXT NOT NULL
);

CREATE INDEX security_audit_events_correlation_idx
    ON security_audit_events (correlation_id);

PRAGMA user_version = 1;

COMMIT;
