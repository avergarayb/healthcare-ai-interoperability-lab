BEGIN IMMEDIATE;

CREATE TABLE human_sessions (
    session_id TEXT PRIMARY KEY,
    token_hash TEXT NOT NULL UNIQUE CHECK (
        length(token_hash) = 64
        AND token_hash NOT GLOB '*[^0-9a-f]*'
    ),
    principal_id TEXT NOT NULL CHECK (
        length(principal_id) BETWEEN 1 AND 64
    ),
    display_name TEXT NOT NULL CHECK (
        length(display_name) BETWEEN 1 AND 80
    ),
    authenticator_id TEXT NOT NULL CHECK (
        authenticator_id = 'DEVELOPMENT_AUTHENTICATOR_V1'
    ),
    issued_at TEXT NOT NULL CHECK (substr(issued_at, -1) = 'Z'),
    expires_at TEXT NOT NULL CHECK (substr(expires_at, -1) = 'Z'),
    revoked_at TEXT CHECK (revoked_at IS NULL OR substr(revoked_at, -1) = 'Z'),
    CHECK (expires_at > issued_at)
);

CREATE INDEX human_sessions_expires_at_idx
    ON human_sessions (expires_at);

PRAGMA user_version = 1;

COMMIT;
