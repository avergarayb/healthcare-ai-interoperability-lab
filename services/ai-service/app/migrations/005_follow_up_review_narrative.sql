BEGIN IMMEDIATE;

CREATE TABLE follow_up_review_narratives (
    review_case_id TEXT PRIMARY KEY,
    origin TEXT NOT NULL CHECK (origin = 'gemini'),
    narrative_text TEXT NOT NULL CHECK (length(narrative_text) BETWEEN 1 AND 4000),
    recorded_at TEXT NOT NULL CHECK (substr(recorded_at, -1) = 'Z'),
    FOREIGN KEY (review_case_id) REFERENCES follow_up_review_cases(id) ON DELETE RESTRICT
);

PRAGMA user_version = 5;

COMMIT;
