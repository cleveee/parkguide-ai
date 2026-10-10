PRAGMA foreign_keys = ON;
CREATE TABLE IF NOT EXISTS metadata (
    name TEXT PRIMARY KEY,
    value TEXT NOT NULL
);
CREATE TABLE IF NOT EXISTS documents (
    doc_id TEXT PRIMARY KEY,
    source_url TEXT NOT NULL UNIQUE,
    content_hash TEXT NOT NULL,
    title TEXT NOT NULL,
    page_type TEXT NOT NULL CHECK (page_type IN ('html', 'pdf')),
    effective_date TEXT,
    crawled_at TEXT NOT NULL,
    normalized_blocks_json TEXT NOT NULL
);
CREATE TABLE IF NOT EXISTS index_builds (
    build_id TEXT PRIMARY KEY,
    manifest_json TEXT NOT NULL,
    active INTEGER NOT NULL DEFAULT 0 CHECK (active IN (0, 1))
);
CREATE UNIQUE INDEX IF NOT EXISTS one_active_build ON index_builds(active) WHERE active = 1;
CREATE TABLE IF NOT EXISTS chunks (
    build_id TEXT NOT NULL REFERENCES index_builds(build_id) ON DELETE CASCADE,
    chunk_id TEXT NOT NULL,
    doc_id TEXT NOT NULL REFERENCES documents(doc_id) ON DELETE CASCADE,
    text TEXT NOT NULL,
    heading_path TEXT NOT NULL,
    source_span_json TEXT NOT NULL,
    token_count INTEGER NOT NULL CHECK (token_count > 0),
    PRIMARY KEY (build_id, chunk_id)
);
CREATE TABLE IF NOT EXISTS embeddings (
    build_id TEXT NOT NULL,
    chunk_id TEXT NOT NULL,
    dimension INTEGER NOT NULL CHECK (dimension > 0),
    vector_f32 BLOB NOT NULL CHECK (length(vector_f32) = dimension * 4),
    PRIMARY KEY (build_id, chunk_id),
    FOREIGN KEY (build_id, chunk_id) REFERENCES chunks(build_id, chunk_id) ON DELETE CASCADE
);
CREATE INDEX IF NOT EXISTS chunks_document ON chunks(doc_id);
