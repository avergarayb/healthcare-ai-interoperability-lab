BEGIN IMMEDIATE;

CREATE TABLE follow_up_human_attributions (
    attribution_id TEXT PRIMARY KEY,
    review_case_id TEXT NOT NULL,
    operation TEXT NOT NULL CHECK (
        operation IN ('review_case_closed', 'coordination_request_created')
    ),
    subject_version INTEGER CHECK (subject_version IS NULL OR subject_version = 2),
    coordination_request_id TEXT,
    principal_id TEXT NOT NULL CHECK (
        length(principal_id) BETWEEN 1 AND 64
        AND principal_id NOT GLOB '*[^a-z0-9-]*'
        AND principal_id NOT GLOB '-*'
        AND principal_id NOT GLOB '*-'
    ),
    authenticator_id TEXT NOT NULL CHECK (
        authenticator_id = 'DEVELOPMENT_AUTHENTICATOR_V1'
    ),
    session_id TEXT NOT NULL CHECK (
        length(session_id) = 36
        AND session_id NOT GLOB '*[^0-9a-fA-F-]*'
    ),
    occurred_at TEXT NOT NULL CHECK (substr(occurred_at, -1) = 'Z'),
    UNIQUE (review_case_id, operation),
    CHECK (
        (
            operation = 'review_case_closed'
            AND subject_version = 2
            AND coordination_request_id IS NULL
        )
        OR
        (
            operation = 'coordination_request_created'
            AND subject_version IS NULL
            AND coordination_request_id IS NOT NULL
        )
    ),
    FOREIGN KEY (review_case_id) REFERENCES follow_up_review_cases(id) ON DELETE RESTRICT,
    FOREIGN KEY (review_case_id, subject_version)
        REFERENCES follow_up_review_case_events(review_case_id, case_version)
        ON DELETE RESTRICT,
    FOREIGN KEY (coordination_request_id)
        REFERENCES follow_up_coordination_requests(id) ON DELETE RESTRICT
);

CREATE TRIGGER follow_up_human_attributions_coordination_case
BEFORE INSERT ON follow_up_human_attributions
WHEN NEW.operation = 'coordination_request_created'
BEGIN
    SELECT RAISE(ABORT, 'attribution coordination case mismatch')
    WHERE NOT EXISTS (
        SELECT 1 FROM follow_up_coordination_requests
        WHERE id = NEW.coordination_request_id
          AND review_case_id = NEW.review_case_id
    );
END;

PRAGMA user_version = 3;

COMMIT;
