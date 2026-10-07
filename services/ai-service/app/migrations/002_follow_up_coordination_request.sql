BEGIN IMMEDIATE;

CREATE TABLE follow_up_coordination_requests (
    id TEXT PRIMARY KEY,
    action_identity TEXT NOT NULL UNIQUE CHECK (
        length(action_identity) = 64
        AND action_identity NOT GLOB '*[^0-9a-f]*'
    ),
    review_case_id TEXT NOT NULL,
    protocol_id TEXT NOT NULL CHECK (
        protocol_id IN (
            'POST_CONSULTATION_RESULT_REVIEW_V1',
            'MISSED_FOLLOW_UP_REVIEW_V1'
        )
    ),
    action_type TEXT NOT NULL CHECK (
        action_type = 'create_follow_up_coordination_request'
    ),
    status TEXT NOT NULL CHECK (status = 'requested'),
    created_at TEXT NOT NULL CHECK (substr(created_at, -1) = 'Z'),
    FOREIGN KEY (review_case_id) REFERENCES follow_up_review_cases(id) ON DELETE RESTRICT,
    UNIQUE (review_case_id, action_type)
);

PRAGMA user_version = 2;

COMMIT;
