CREATE TABLE specimen_case (
    order_id TEXT PRIMARY KEY REFERENCES lab_orders (order_id),
    state TEXT NOT NULL,
    specimen_id TEXT,
    draft_value TEXT,
    draft_unit TEXT,
    draft_note TEXT,
    result_id TEXT,
    publication TEXT,
    updated_at TEXT NOT NULL,
    CONSTRAINT specimen_case_state CHECK (state IN (
        'ORDER_RECEIVED', 'SPECIMEN_REGISTERED', 'SPECIMEN_RECEIVED', 'PROCESSING',
        'DRAFT', 'VALIDATED', 'PUBLISHED'))
);

CREATE TABLE critical_event (
    event_id TEXT PRIMARY KEY,
    order_id TEXT NOT NULL UNIQUE REFERENCES lab_orders (order_id),
    result_id TEXT NOT NULL,
    patient_id TEXT NOT NULL,
    organization_id TEXT NOT NULL,
    correlation_id TEXT NOT NULL,
    rule_id TEXT NOT NULL,
    rule_version TEXT NOT NULL,
    test_code TEXT NOT NULL,
    original_value TEXT NOT NULL,
    current_value TEXT NOT NULL,
    unit TEXT NOT NULL,
    status TEXT NOT NULL,
    recorded_at TEXT NOT NULL,
    corrected_at TEXT
);
