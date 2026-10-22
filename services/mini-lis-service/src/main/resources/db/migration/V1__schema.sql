CREATE TABLE external_patients (
    patient_id TEXT PRIMARY KEY,
    organization_id TEXT NOT NULL,
    external_id TEXT NOT NULL,
    family_name TEXT NOT NULL,
    given_name TEXT NOT NULL,
    birth_date DATE NOT NULL,
    administrative_sex TEXT NOT NULL,
    created_at TIMESTAMPTZ NOT NULL,
    CONSTRAINT external_patients_sex CHECK (administrative_sex IN ('female', 'male', 'unknown')),
    CONSTRAINT external_patients_external UNIQUE (organization_id, external_id)
);

CREATE TABLE lab_orders (
    order_id TEXT PRIMARY KEY,
    patient_id TEXT NOT NULL REFERENCES external_patients (patient_id),
    requesting_organization_id TEXT NOT NULL,
    external_request_id TEXT NOT NULL,
    test_code TEXT NOT NULL,
    test_description TEXT NOT NULL,
    requested_at TIMESTAMPTZ NOT NULL,
    status TEXT NOT NULL,
    created_at TIMESTAMPTZ NOT NULL,
    CONSTRAINT lab_orders_status CHECK (status IN ('ORDERED', 'IN_PROGRESS', 'COMPLETED', 'CANCELLED')),
    CONSTRAINT lab_orders_external UNIQUE (requesting_organization_id, external_request_id)
);

CREATE INDEX lab_orders_patient ON lab_orders (patient_id);

CREATE TABLE lab_results (
    result_id TEXT PRIMARY KEY,
    order_id TEXT NOT NULL REFERENCES lab_orders (order_id),
    patient_id TEXT NOT NULL REFERENCES external_patients (patient_id),
    external_result_id TEXT NOT NULL,
    test_code TEXT NOT NULL,
    result_value TEXT NOT NULL,
    unit TEXT,
    reference_range TEXT,
    resulted_at TIMESTAMPTZ NOT NULL,
    status TEXT NOT NULL,
    created_at TIMESTAMPTZ NOT NULL,
    CONSTRAINT lab_results_status CHECK (status IN ('PRELIMINARY', 'FINAL', 'CANCELLED')),
    CONSTRAINT lab_results_external UNIQUE (order_id, external_result_id)
);

CREATE INDEX lab_results_order ON lab_results (order_id);
