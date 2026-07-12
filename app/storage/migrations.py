"""Database migrations for DocuFind Local."""

from __future__ import annotations

import sqlite3

SCHEMA_VERSION = 3

SCHEMA_SQL = """
CREATE TABLE IF NOT EXISTS schema_migrations (
    version INTEGER PRIMARY KEY,
    applied_at TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP
);

CREATE TABLE IF NOT EXISTS index_folders (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    path TEXT NOT NULL UNIQUE,
    path_norm TEXT NOT NULL,
    enabled INTEGER NOT NULL DEFAULT 1,
    created_at TEXT NOT NULL
);

CREATE TABLE IF NOT EXISTS index_runs (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    folder_id INTEGER,
    started_at TEXT NOT NULL,
    finished_at TEXT,
    status TEXT NOT NULL,
    files_seen INTEGER DEFAULT 0,
    files_indexed INTEGER DEFAULT 0,
    files_skipped INTEGER DEFAULT 0,
    files_failed INTEGER DEFAULT 0,
    files_new INTEGER DEFAULT 0,
    files_changed INTEGER DEFAULT 0,
    files_unchanged INTEGER DEFAULT 0,
    files_deleted INTEGER DEFAULT 0,
    files_restored INTEGER DEFAULT 0,
    files_stale INTEGER DEFAULT 0,
    files_reindexed INTEGER DEFAULT 0,
    FOREIGN KEY(folder_id) REFERENCES index_folders(id)
);

CREATE TABLE IF NOT EXISTS documents (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    folder_id INTEGER,
    path TEXT NOT NULL UNIQUE,
    path_norm TEXT NOT NULL,
    filename TEXT NOT NULL,
    filename_norm TEXT NOT NULL,
    extension TEXT,
    extension_norm TEXT,
    size_bytes INTEGER NOT NULL,
    modified_at TEXT NOT NULL,
    modified_ns INTEGER,
    indexed_at TEXT NOT NULL,
    last_seen_at TEXT NOT NULL,
    last_verified_at TEXT,
    last_missing_at TEXT,
    payload_retained INTEGER DEFAULT 0,
    state_reason TEXT,
    stale_detected_at TEXT,
    content_hash TEXT,
    encoding TEXT,
    line_ending TEXT,
    is_hidden INTEGER DEFAULT 0,
    is_system INTEGER DEFAULT 0,
    is_readonly INTEGER DEFAULT 0,
    index_status TEXT NOT NULL DEFAULT 'indexed',
    error_message TEXT,
    FOREIGN KEY(folder_id) REFERENCES index_folders(id)
);

CREATE TABLE IF NOT EXISTS chunks (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    document_id INTEGER NOT NULL,
    chunk_index INTEGER NOT NULL,
    text TEXT NOT NULL,
    line_start INTEGER,
    line_end INTEGER,
    char_start INTEGER,
    char_end INTEGER,
    column_start INTEGER NOT NULL DEFAULT 1,
    FOREIGN KEY(document_id) REFERENCES documents(id) ON DELETE CASCADE
);

CREATE TABLE IF NOT EXISTS document_terms (
    document_id INTEGER NOT NULL,
    normalized_term TEXT NOT NULL,
    source TEXT NOT NULL,
    occurrence_count INTEGER DEFAULT 1,
    PRIMARY KEY (document_id, normalized_term, source),
    FOREIGN KEY(document_id) REFERENCES documents(id) ON DELETE CASCADE
);

CREATE TABLE IF NOT EXISTS indexed_terms (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    term TEXT NOT NULL,
    normalized_term TEXT NOT NULL,
    source TEXT NOT NULL,
    first_char TEXT,
    length INTEGER,
    document_count INTEGER DEFAULT 0,
    occurrence_count INTEGER DEFAULT 0,
    UNIQUE(normalized_term, source)
);

CREATE TABLE IF NOT EXISTS document_lemmas (
    document_id INTEGER NOT NULL,
    lemma TEXT NOT NULL,
    source TEXT NOT NULL,
    occurrence_count INTEGER DEFAULT 1,
    PRIMARY KEY (document_id, lemma, source),
    FOREIGN KEY(document_id) REFERENCES documents(id) ON DELETE CASCADE
);

CREATE TABLE IF NOT EXISTS indexed_lemmas (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    lemma TEXT NOT NULL,
    source TEXT NOT NULL,
    first_char TEXT,
    length INTEGER,
    document_count INTEGER DEFAULT 0,
    occurrence_count INTEGER DEFAULT 0,
    UNIQUE(lemma, source)
);

CREATE VIRTUAL TABLE IF NOT EXISTS documents_fts USING fts5(
    document_id UNINDEXED,
    filename_norm,
    path_norm
);

CREATE VIRTUAL TABLE IF NOT EXISTS chunks_fts USING fts5(
    chunk_id UNINDEXED,
    document_id UNINDEXED,
    text
);

CREATE TABLE IF NOT EXISTS index_errors (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    run_id INTEGER,
    path TEXT NOT NULL,
    error_type TEXT NOT NULL,
    error_message TEXT,
    created_at TEXT NOT NULL,
    FOREIGN KEY(run_id) REFERENCES index_runs(id)
);

CREATE TABLE IF NOT EXISTS settings (
    key TEXT PRIMARY KEY,
    value TEXT NOT NULL
);

CREATE TABLE IF NOT EXISTS reindex_queue (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    path TEXT NOT NULL,
    path_norm TEXT NOT NULL,
    document_id INTEGER,
    reason TEXT NOT NULL,
    status TEXT NOT NULL DEFAULT 'pending',
    priority INTEGER NOT NULL DEFAULT 100,
    attempts INTEGER NOT NULL DEFAULT 0,
    last_error TEXT,
    created_at TEXT NOT NULL,
    updated_at TEXT NOT NULL,
    locked_at TEXT,
    FOREIGN KEY(document_id) REFERENCES documents(id)
);

CREATE INDEX IF NOT EXISTS idx_documents_folder_id ON documents(folder_id);
CREATE INDEX IF NOT EXISTS idx_documents_extension_norm ON documents(extension_norm);
CREATE INDEX IF NOT EXISTS idx_documents_index_status ON documents(index_status);
CREATE INDEX IF NOT EXISTS idx_documents_last_seen_at ON documents(last_seen_at);
CREATE INDEX IF NOT EXISTS idx_chunks_document_id ON chunks(document_id);
CREATE INDEX IF NOT EXISTS idx_document_terms_lookup ON document_terms(source, normalized_term);
CREATE INDEX IF NOT EXISTS idx_document_lemmas_lookup ON document_lemmas(source, lemma);
CREATE INDEX IF NOT EXISTS idx_indexed_terms_fuzzy ON indexed_terms(source, length, first_char);
CREATE INDEX IF NOT EXISTS idx_indexed_lemmas_fuzzy ON indexed_lemmas(source, length, first_char);
CREATE INDEX IF NOT EXISTS idx_index_errors_run_id ON index_errors(run_id);
CREATE INDEX IF NOT EXISTS idx_reindex_queue_status_priority
ON reindex_queue(status, priority, created_at);
"""

MIGRATION_2_SQL = """
CREATE TABLE IF NOT EXISTS reindex_queue (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    path TEXT NOT NULL,
    path_norm TEXT NOT NULL,
    document_id INTEGER,
    reason TEXT NOT NULL,
    status TEXT NOT NULL DEFAULT 'pending',
    priority INTEGER NOT NULL DEFAULT 100,
    attempts INTEGER NOT NULL DEFAULT 0,
    last_error TEXT,
    created_at TEXT NOT NULL,
    updated_at TEXT NOT NULL,
    locked_at TEXT,
    FOREIGN KEY(document_id) REFERENCES documents(id)
);

CREATE INDEX IF NOT EXISTS idx_reindex_queue_status_priority
ON reindex_queue(status, priority, created_at);
"""


def migrate(connection: sqlite3.Connection) -> None:
    migration_table = connection.execute(
        "SELECT name FROM sqlite_master WHERE type='table' AND name='schema_migrations'"
    ).fetchone()
    if migration_table is None:
        connection.executescript(SCHEMA_SQL)
        connection.execute("INSERT OR IGNORE INTO schema_migrations(version) VALUES (?)", (SCHEMA_VERSION,))
        return

    current = connection.execute("SELECT MAX(version) AS version FROM schema_migrations").fetchone()["version"]
    if current is None or current < SCHEMA_VERSION:
        if current is None or current < 2:
            _migrate_to_2(connection)
        if current is None or current < 3:
            _migrate_to_3(connection)
        connection.execute("INSERT OR IGNORE INTO schema_migrations(version) VALUES (?)", (SCHEMA_VERSION,))


def _migrate_to_2(connection: sqlite3.Connection) -> None:
    _add_column_if_missing(connection, "documents", "last_verified_at", "TEXT")
    _add_column_if_missing(connection, "documents", "last_missing_at", "TEXT")
    _add_column_if_missing(connection, "documents", "payload_retained", "INTEGER DEFAULT 0")
    _add_column_if_missing(connection, "documents", "state_reason", "TEXT")
    _add_column_if_missing(connection, "documents", "stale_detected_at", "TEXT")
    _add_column_if_missing(connection, "index_runs", "files_new", "INTEGER DEFAULT 0")
    _add_column_if_missing(connection, "index_runs", "files_changed", "INTEGER DEFAULT 0")
    _add_column_if_missing(connection, "index_runs", "files_unchanged", "INTEGER DEFAULT 0")
    _add_column_if_missing(connection, "index_runs", "files_deleted", "INTEGER DEFAULT 0")
    _add_column_if_missing(connection, "index_runs", "files_restored", "INTEGER DEFAULT 0")
    _add_column_if_missing(connection, "index_runs", "files_stale", "INTEGER DEFAULT 0")
    _add_column_if_missing(connection, "index_runs", "files_reindexed", "INTEGER DEFAULT 0")
    connection.executescript(MIGRATION_2_SQL)


def _migrate_to_3(connection: sqlite3.Connection) -> None:
    _add_column_if_missing(connection, "chunks", "column_start", "INTEGER NOT NULL DEFAULT 1")


def _add_column_if_missing(connection: sqlite3.Connection, table: str, column: str, definition: str) -> None:
    columns = {str(row["name"]) for row in connection.execute(f"PRAGMA table_info({table})")}
    if column not in columns:
        connection.execute(f"ALTER TABLE {table} ADD COLUMN {column} {definition}")


