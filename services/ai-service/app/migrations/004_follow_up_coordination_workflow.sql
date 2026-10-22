PRAGMA foreign_keys=OFF;

BEGIN IMMEDIATE;

DROP TRIGGER IF EXISTS follow_up_human_attributions_coordination_case;

CREATE TABLE follow_up_coordination_requests_next (
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
    status TEXT NOT NULL CHECK (
        status IN ('requested', 'in_progress', 'completed')
    ),
    created_at TEXT NOT NULL CHECK (substr(created_at, -1) = 'Z'),
    FOREIGN KEY (review_case_id) REFERENCES follow_up_review_cases(id) ON DELETE RESTRICT,
    UNIQUE (review_case_id, action_type)
);

INSERT INTO follow_up_coordination_requests_next (
    id, action_identity, review_case_id, protocol_id, action_type, status, created_at
)
SELECT id, action_identity, review_case_id, protocol_id, action_type, status, created_at
FROM follow_up_coordination_requests;

DROP TABLE follow_up_coordination_requests;

ALTER TABLE follow_up_coordination_requests_next
    RENAME TO follow_up_coordination_requests;

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

CREATE TRIGGER follow_up_coordination_requests_status_guard
BEFORE UPDATE ON follow_up_coordination_requests
BEGIN
    SELECT RAISE(ABORT, 'coordination request fields are immutable')
    WHERE OLD.id != NEW.id
       OR OLD.action_identity != NEW.action_identity
       OR OLD.review_case_id != NEW.review_case_id
       OR OLD.protocol_id != NEW.protocol_id
       OR OLD.action_type != NEW.action_type
       OR OLD.created_at != NEW.created_at
       OR NOT (
            (OLD.status = 'requested' AND NEW.status = 'in_progress')
            OR (OLD.status = 'in_progress' AND NEW.status = 'completed')
            OR OLD.status = NEW.status
       );
END;

CREATE TABLE follow_up_coordination_request_events (
    event_id TEXT PRIMARY KEY,
    coordination_request_id TEXT NOT NULL,
    review_case_id TEXT NOT NULL,
    from_status TEXT NOT NULL CHECK (from_status IN ('requested', 'in_progress')),
    to_status TEXT NOT NULL CHECK (to_status IN ('in_progress', 'completed')),
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
    CHECK (
        (from_status = 'requested' AND to_status = 'in_progress')
        OR (from_status = 'in_progress' AND to_status = 'completed')
    ),
    UNIQUE (coordination_request_id, to_status),
    FOREIGN KEY (coordination_request_id)
        REFERENCES follow_up_coordination_requests(id) ON DELETE CASCADE,
    FOREIGN KEY (review_case_id)
        REFERENCES follow_up_review_cases(id) ON DELETE RESTRICT
);

CREATE TRIGGER follow_up_coordination_request_events_case
BEFORE INSERT ON follow_up_coordination_request_events
BEGIN
    SELECT RAISE(ABORT, 'coordination event case mismatch')
    WHERE NOT EXISTS (
        SELECT 1 FROM follow_up_coordination_requests
        WHERE id = NEW.coordination_request_id
          AND review_case_id = NEW.review_case_id
    );
END;

CREATE TRIGGER follow_up_coordination_request_events_append_only
BEFORE UPDATE ON follow_up_coordination_request_events
BEGIN
    SELECT RAISE(ABORT, 'coordination request events are append-only');
END;

PRAGMA user_version = 4;

COMMIT;

PRAGMA foreign_keys=ON;
