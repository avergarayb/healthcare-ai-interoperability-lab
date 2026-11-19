CREATE TABLE IF NOT EXISTS security_event (
    event_id BIGSERIAL PRIMARY KEY,
    actor TEXT NOT NULL,
    role TEXT NOT NULL,
    organization_id TEXT NOT NULL,
    action TEXT NOT NULL,
    resource TEXT NOT NULL,
    outcome TEXT NOT NULL,
    correlation TEXT NOT NULL,
    recorded_at TIMESTAMPTZ NOT NULL
);
