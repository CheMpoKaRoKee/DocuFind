"""Explicit index reset operations."""

from __future__ import annotations

from collections.abc import Callable
from dataclasses import dataclass
from math import ceil
import sqlite3
from time import monotonic

from app.models.index_progress import IndexProgress
from app.storage.database import Database


@dataclass(frozen=True)
class IndexResetSummary:
    documents_deleted: int = 0
    chunks_deleted: int = 0
    runs_deleted: int = 0
    queue_deleted: int = 0


class IndexResetCancelled(Exception):
    """Raised to roll back a partially completed index reset."""


class IndexResetLocked(Exception):
    """Raised when SQLite cannot acquire a write lock for index reset."""


class IndexResetService:
    def __init__(self, database: Database) -> None:
        self.database = database

    def clear_index(
        self,
        *,
        progress_callback: Callable[[IndexProgress], None] | None = None,
        cancel_checker: Callable[[], bool] | None = None,
    ) -> IndexResetSummary:
        self.database.initialize()
        connection = self.database.connect()
        try:
            connection.execute("PRAGMA busy_timeout=30000")
            summary = IndexResetSummary(
                documents_deleted=_count(connection, "documents"),
                chunks_deleted=_count(connection, "chunks"),
                runs_deleted=_count(connection, "index_runs"),
                queue_deleted=_count(connection, "reindex_queue"),
            )
            started_at = monotonic()
            table_counts = [(table, _count(connection, table)) for table in RESET_TABLES]
            recreate_units = len(RECREATE_INDEX_SQL) + len(INDEX_SQL)
            files_total = sum(max(count, 1) for _, count in table_counts) + recreate_units
            files_processed = 0
            _emit_progress(progress_callback, "clearing_index", files_total, files_processed, started_at)
            connection.execute("BEGIN IMMEDIATE")
            for table, rows in table_counts:
                if cancel_checker is not None and cancel_checker():
                    _emit_progress(progress_callback, "cancelled", files_total, files_processed, started_at, table)
                    raise IndexResetCancelled()
                connection.execute(f"DROP TABLE IF EXISTS {table}")
                files_processed += max(rows, 1)
                _emit_progress(progress_callback, "clearing_index", files_total, files_processed, started_at, table)
            for statement in RECREATE_INDEX_SQL:
                if cancel_checker is not None and cancel_checker():
                    _emit_progress(progress_callback, "cancelled", files_total, files_processed, started_at)
                    raise IndexResetCancelled()
                connection.execute(statement)
                files_processed += 1
                _emit_progress(progress_callback, "clearing_index", files_total, files_processed, started_at)
            for statement in INDEX_SQL:
                connection.execute(statement)
                files_processed += 1
                _emit_progress(progress_callback, "clearing_index", files_total, files_processed, started_at)
            _reset_sequences(connection, SEQUENCE_TABLES)
            connection.commit()
            _emit_progress(progress_callback, "clear_completed", files_total, files_total, started_at, percent=100)
            return summary
        except IndexResetCancelled:
            connection.rollback()
            raise
        except sqlite3.OperationalError as exc:
            connection.rollback()
            if "locked" in str(exc).casefold() or "busy" in str(exc).casefold():
                raise IndexResetLocked(str(exc)) from exc
            raise
        except Exception:
            connection.rollback()
            raise
        finally:
            connection.close()


RESET_TABLES = (
    "chunks_fts",
    "documents_fts",
    "document_terms",
    "document_lemmas",
    "indexed_terms",
    "indexed_lemmas",
    "chunks",
    "index_errors",
    "reindex_queue",
    "documents",
    "index_runs",
)

RECREATE_INDEX_SQL = (
    """
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
    )
    """,
    """
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
    )
    """,
    """
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
    )
    """,
    """
    CREATE TABLE IF NOT EXISTS document_terms (
        document_id INTEGER NOT NULL,
        normalized_term TEXT NOT NULL,
        source TEXT NOT NULL,
        occurrence_count INTEGER DEFAULT 1,
        PRIMARY KEY (document_id, normalized_term, source),
        FOREIGN KEY(document_id) REFERENCES documents(id) ON DELETE CASCADE
    )
    """,
    """
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
    )
    """,
    """
    CREATE TABLE IF NOT EXISTS document_lemmas (
        document_id INTEGER NOT NULL,
        lemma TEXT NOT NULL,
        source TEXT NOT NULL,
        occurrence_count INTEGER DEFAULT 1,
        PRIMARY KEY (document_id, lemma, source),
        FOREIGN KEY(document_id) REFERENCES documents(id) ON DELETE CASCADE
    )
    """,
    """
    CREATE TABLE IF NOT EXISTS indexed_lemmas (
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        lemma TEXT NOT NULL,
        source TEXT NOT NULL,
        first_char TEXT,
        length INTEGER,
        document_count INTEGER DEFAULT 0,
        occurrence_count INTEGER DEFAULT 0,
        UNIQUE(lemma, source)
    )
    """,
    """
    CREATE VIRTUAL TABLE IF NOT EXISTS documents_fts USING fts5(
        document_id UNINDEXED,
        filename_norm,
        path_norm
    )
    """,
    """
    CREATE VIRTUAL TABLE IF NOT EXISTS chunks_fts USING fts5(
        chunk_id UNINDEXED,
        document_id UNINDEXED,
        text
    )
    """,
    """
    CREATE TABLE IF NOT EXISTS index_errors (
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        run_id INTEGER,
        path TEXT NOT NULL,
        error_type TEXT NOT NULL,
        error_message TEXT,
        created_at TEXT NOT NULL,
        FOREIGN KEY(run_id) REFERENCES index_runs(id)
    )
    """,
    """
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
    )
    """,
)

INDEX_SQL = (
    "CREATE INDEX IF NOT EXISTS idx_documents_folder_id ON documents(folder_id)",
    "CREATE INDEX IF NOT EXISTS idx_documents_extension_norm ON documents(extension_norm)",
    "CREATE INDEX IF NOT EXISTS idx_documents_index_status ON documents(index_status)",
    "CREATE INDEX IF NOT EXISTS idx_documents_last_seen_at ON documents(last_seen_at)",
    "CREATE INDEX IF NOT EXISTS idx_chunks_document_id ON chunks(document_id)",
    "CREATE INDEX IF NOT EXISTS idx_document_terms_lookup ON document_terms(source, normalized_term)",
    "CREATE INDEX IF NOT EXISTS idx_document_lemmas_lookup ON document_lemmas(source, lemma)",
    "CREATE INDEX IF NOT EXISTS idx_indexed_terms_fuzzy ON indexed_terms(source, length, first_char)",
    "CREATE INDEX IF NOT EXISTS idx_indexed_lemmas_fuzzy ON indexed_lemmas(source, length, first_char)",
    "CREATE INDEX IF NOT EXISTS idx_index_errors_run_id ON index_errors(run_id)",
    "CREATE INDEX IF NOT EXISTS idx_reindex_queue_status_priority ON reindex_queue(status, priority, created_at)",
)

SEQUENCE_TABLES = (
    "documents",
    "chunks",
    "indexed_terms",
    "indexed_lemmas",
    "index_errors",
    "reindex_queue",
    "index_runs",
)


def _count(connection, table: str) -> int:
    return int(connection.execute(f"SELECT count(*) FROM {table}").fetchone()[0])


def _reset_sequences(connection, tables: tuple[str, ...]) -> None:
    placeholders = ", ".join("?" for _ in tables)
    connection.execute(f"DELETE FROM sqlite_sequence WHERE name IN ({placeholders})", tables)


def _emit_progress(
    callback: Callable[[IndexProgress], None] | None,
    phase: str,
    files_total: int,
    files_processed: int,
    started_at: float,
    table: str | None = None,
    *,
    percent: int | None = None,
) -> None:
    if callback is None:
        return
    elapsed = max(monotonic() - started_at, 0.001)
    speed = files_processed / elapsed if files_processed > 0 else None
    remaining = max(files_total - files_processed, 0)
    eta_seconds = None
    if speed is not None and remaining > 0:
        eta_seconds = max(1, int(ceil(remaining / speed)))
    if percent is None:
        percent = min(99, int(files_processed / files_total * 100)) if files_total > 0 else 0
    callback(
        IndexProgress(
            phase=phase,
            current_path=table,
            files_total=files_total,
            files_seen=files_processed,
            files_processed=files_processed,
            percent=percent,
            eta_seconds=eta_seconds,
            files_per_second=speed,
            message=table or "",
        )
    )
