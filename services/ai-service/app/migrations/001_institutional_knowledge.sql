BEGIN IMMEDIATE;

CREATE TABLE knowledge_index_state (
    id INTEGER PRIMARY KEY CHECK (id = 1),
    ready INTEGER NOT NULL CHECK (ready IN (0, 1)),
    embedding_model TEXT NOT NULL,
    vector_dimension INTEGER NOT NULL CHECK (vector_dimension >= 0),
    corpus_fingerprint TEXT NOT NULL
);

INSERT INTO knowledge_index_state (
    id, ready, embedding_model, vector_dimension, corpus_fingerprint
) VALUES (1, 0, '', 0, '');

CREATE TABLE institutional_documents (
    document_id TEXT NOT NULL CHECK (length(document_id) BETWEEN 1 AND 80),
    version TEXT NOT NULL CHECK (length(version) BETWEEN 1 AND 32),
    title TEXT NOT NULL CHECK (length(title) BETWEEN 1 AND 160),
    status TEXT NOT NULL CHECK (status IN ('active', 'superseded')),
    effective_date TEXT NOT NULL CHECK (length(effective_date) = 10),
    source_type TEXT NOT NULL CHECK (source_type = 'synthetic_institutional_procedure'),
    synthetic INTEGER NOT NULL CHECK (synthetic = 1),
    language TEXT NOT NULL CHECK (language = 'en'),
    protocol_ids_json TEXT NOT NULL,
    content_hash TEXT NOT NULL CHECK (
        length(content_hash) = 64
        AND content_hash NOT GLOB '*[^0-9a-f]*'
    ),
    PRIMARY KEY (document_id, version)
);

CREATE UNIQUE INDEX institutional_documents_one_active
    ON institutional_documents (document_id)
    WHERE status = 'active';

CREATE TABLE institutional_chunks (
    chunk_id TEXT PRIMARY KEY CHECK (
        length(chunk_id) = 64
        AND chunk_id NOT GLOB '*[^0-9a-f]*'
    ),
    document_id TEXT NOT NULL,
    version TEXT NOT NULL,
    title TEXT NOT NULL,
    document_status TEXT NOT NULL CHECK (document_status IN ('active', 'superseded')),
    section TEXT NOT NULL CHECK (length(section) BETWEEN 1 AND 80),
    ordinal INTEGER NOT NULL CHECK (ordinal >= 0),
    content_hash TEXT NOT NULL CHECK (
        length(content_hash) = 64
        AND content_hash NOT GLOB '*[^0-9a-f]*'
    ),
    language TEXT NOT NULL CHECK (language = 'en'),
    synthetic INTEGER NOT NULL CHECK (synthetic = 1),
    text TEXT NOT NULL CHECK (length(text) BETWEEN 1 AND 2000),
    FOREIGN KEY (document_id, version)
        REFERENCES institutional_documents (document_id, version)
        ON DELETE RESTRICT,
    UNIQUE (document_id, version, section, ordinal)
);

CREATE TABLE institutional_vectors (
    chunk_id TEXT PRIMARY KEY,
    embedding_model TEXT NOT NULL CHECK (length(embedding_model) BETWEEN 1 AND 128),
    dimension INTEGER NOT NULL CHECK (dimension BETWEEN 1 AND 4096),
    vector_json TEXT NOT NULL,
    FOREIGN KEY (chunk_id) REFERENCES institutional_chunks (chunk_id) ON DELETE RESTRICT
);

PRAGMA user_version = 1;

COMMIT;
