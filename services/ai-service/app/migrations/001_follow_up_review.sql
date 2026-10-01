BEGIN IMMEDIATE;

CREATE TABLE follow_up_review_cases (
    id TEXT PRIMARY KEY,
    review_identity TEXT NOT NULL UNIQUE CHECK (
        length(review_identity) = 64
        AND review_identity NOT GLOB '*[^0-9a-f]*'
    ),
    case_id TEXT NOT NULL CHECK (length(case_id) BETWEEN 1 AND 255),
    protocol_id TEXT NOT NULL CHECK (length(protocol_id) BETWEEN 1 AND 128),
    protocol_evaluation_status TEXT NOT NULL CHECK (protocol_evaluation_status = 'matched'),
    reason_codes_json TEXT NOT NULL,
    matched_resources_json TEXT NOT NULL,
    status TEXT NOT NULL CHECK (status IN ('open', 'closed')),
    outcome TEXT CHECK (
        outcome IS NULL OR outcome IN (
            'follow_up_coordination_planned',
            'review_completed_no_operational_action'
        )
    ),
    version INTEGER NOT NULL CHECK (version IN (1, 2)),
    created_at TEXT NOT NULL CHECK (substr(created_at, -1) = 'Z'),
    updated_at TEXT NOT NULL CHECK (substr(updated_at, -1) = 'Z'),
    closed_at TEXT CHECK (closed_at IS NULL OR substr(closed_at, -1) = 'Z'),
    CHECK (
        (status = 'open' AND outcome IS NULL AND closed_at IS NULL AND version = 1)
        OR
        (status = 'closed' AND outcome IS NOT NULL AND closed_at IS NOT NULL AND version = 2)
    )
);

CREATE INDEX follow_up_review_cases_queue_idx
    ON follow_up_review_cases (status, created_at, id);

CREATE INDEX follow_up_review_cases_case_idx
    ON follow_up_review_cases (case_id, created_at, id);

CREATE TABLE follow_up_review_case_events (
    event_id TEXT PRIMARY KEY,
    review_case_id TEXT NOT NULL,
    case_version INTEGER NOT NULL CHECK (case_version IN (1, 2)),
    event_type TEXT NOT NULL CHECK (event_type IN ('created', 'closed')),
    from_status TEXT CHECK (from_status IS NULL OR from_status IN ('open', 'closed')),
    to_status TEXT NOT NULL CHECK (to_status IN ('open', 'closed')),
    outcome TEXT CHECK (
        outcome IS NULL OR outcome IN (
            'follow_up_coordination_planned',
            'review_completed_no_operational_action'
        )
    ),
    occurred_at TEXT NOT NULL CHECK (substr(occurred_at, -1) = 'Z'),
    FOREIGN KEY (review_case_id) REFERENCES follow_up_review_cases(id) ON DELETE RESTRICT,
    UNIQUE (review_case_id, case_version),
    CHECK (
        (event_type = 'created' AND case_version = 1 AND from_status IS NULL AND to_status = 'open' AND outcome IS NULL)
        OR
        (event_type = 'closed' AND case_version = 2 AND from_status = 'open' AND to_status = 'closed' AND outcome IS NOT NULL)
    )
);

PRAGMA user_version = 1;

COMMIT;
