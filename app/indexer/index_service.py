"""High-level file indexing service."""

from __future__ import annotations

from collections.abc import Callable
from dataclasses import dataclass
from datetime import UTC, datetime
import hashlib
from math import ceil
from pathlib import Path
from time import monotonic

from app.indexer.chunker import Chunker, TextChunk
from app.indexer.deleted_file_detector import DeletedFileDetector
from app.indexer.document_state_service import DocumentStateService
from app.indexer.file_change_detector import FileChangeDetector
from app.indexer.folder_scanner import FolderScanError, FolderScanner
from app.indexer.term_collector import TermCollector
from app.indexer.text_extractor import TextExtractionError, TextExtractor
from app.models.index_progress import IndexProgress
from app.russian.lemma_index_builder import LemmaIndexBuilder
from app.storage.chunk_repository import ChunkRepository
from app.storage.database import Database
from app.storage.document_lemma_repository import DocumentLemmaRepository
from app.storage.document_repository import DocumentRepository
from app.storage.document_term_repository import DocumentTermRepository
from app.storage.fts_repository import FtsRepository
from app.storage.index_error_repository import IndexErrorRepository
from app.storage.index_folder_repository import IndexFolderRepository
from app.storage.index_run_repository import IndexRunRepository
from app.storage.lemma_repository import LemmaRepository
from app.storage.term_repository import TermRepository
from app.utils.logger import get_logger
from app.utils.path_normalizer import normalize_path
from app.utils.path_rules import read_file_attributes
from app.utils.text_normalizer import TextNormalizer

DEFAULT_ESTIMATED_FILES_PER_SECOND = 20.0


@dataclass(frozen=True)
class IndexSummary:
    files_seen: int = 0
    files_indexed: int = 0
    files_skipped: int = 0
    files_failed: int = 0
    files_new: int = 0
    files_changed: int = 0
    files_unchanged: int = 0
    files_deleted: int = 0
    files_restored: int = 0
    files_stale: int = 0
    files_reindexed: int = 0
    files_processed: int = 0


@dataclass(frozen=True)
class ProgressEstimate:
    percent: int | None
    eta_seconds: int | None
    files_per_second: float | None


class IndexService:
    def __init__(
        self,
        database: Database,
        *,
        scanner: FolderScanner | None = None,
        text_extractor: TextExtractor | None = None,
        chunker: Chunker | None = None,
        term_collector: TermCollector | None = None,
        lemma_builder: LemmaIndexBuilder | None = None,
        deleted_file_detector: DeletedFileDetector | None = None,
        change_detector: FileChangeDetector | None = None,
        batch_size: int = 100,
    ) -> None:
        self.database = database
        self.scanner = scanner or FolderScanner()
        self.text_extractor = text_extractor or TextExtractor()
        self.chunker = chunker or Chunker()
        self.term_collector = term_collector or TermCollector()
        self.lemma_builder = lemma_builder or LemmaIndexBuilder()
        self.deleted_file_detector = deleted_file_detector or DeletedFileDetector()
        self.change_detector = change_detector or FileChangeDetector()
        self.normalizer = TextNormalizer()
        self.batch_size = batch_size
        self.logger = get_logger("indexing")

    def index_folder(
        self,
        folder: Path,
        *,
        progress_callback: Callable[[IndexProgress], None] | None = None,
        cancel_checker: Callable[[], bool] | None = None,
    ) -> IndexSummary:
        self.database.initialize()
        folder = Path(folder)
        counters = _new_counters()
        run_id: int | None = None
        files_total: int | None = None
        started_at = monotonic()
        _emit(progress_callback, "scanning", counters, files_total=files_total, started_at=started_at)
        files_total = 0
        try:
            for filter_result in self.scanner.scan(folder):
                if cancel_checker is not None and cancel_checker():
                    _emit(progress_callback, "cancelled", counters, files_total=files_total, started_at=started_at)
                    return _summary(counters)
                files_total += 1
                if files_total == 1 or files_total % self.batch_size == 0:
                    _emit(
                        progress_callback,
                        "scanning",
                        counters,
                        files_total=None,
                        current_path=str(filter_result.path),
                        started_at=started_at,
                        message=str(files_total),
                    )
        except FolderScanError:
            _emit(progress_callback, "failed", counters, files_total=None, started_at=started_at)
            raise
        # ETA and throughput describe the processing pass, not the preliminary
        # directory count, which can dominate on very large trees.
        started_at = monotonic()
        connection = self.database.connect()
        try:
            historical_rate = _historical_files_per_second(connection)
            _emit(
                progress_callback,
                "analyzing",
                counters,
                files_total=files_total,
                started_at=started_at,
                historical_rate=historical_rate,
            )
            folder_id = IndexFolderRepository(connection).add(str(folder), normalize_path(folder))
            run_repo = IndexRunRepository(connection)
            run_id = run_repo.start(folder_id)
            connection.commit()
            seen_paths: set[str] = set()
            batch_count = 0

            # The second pass is intentionally streamed.  Large folder trees are
            # never retained as a full in-memory list; commits split the work
            # into bounded batches while the first pass supplies an exact total.
            for filter_result in self.scanner.scan(folder):
                if cancel_checker is not None and cancel_checker():
                    summary = _summary(counters)
                    run_repo.finish(run_id, status="cancelled", **_run_finish_kwargs(summary))
                    connection.commit()
                    _emit(
                        progress_callback,
                        "cancelled",
                        counters,
                        files_total=files_total,
                        started_at=started_at,
                        historical_rate=historical_rate,
                    )
                    return summary

                path = filter_result.path
                counters["files_seen"] += 1
                seen_paths.add(str(path))
                _emit(
                    progress_callback,
                    "indexing",
                    counters,
                    files_total=files_total,
                    current_path=str(path),
                    started_at=started_at,
                    historical_rate=historical_rate,
                )
                try:
                    if filter_result.can_index:
                        self._process_indexable_file(connection, folder_id, path, counters)
                    else:
                        self._write_skipped_document(connection, folder_id, path, filter_result.status)
                        counters["files_skipped"] += 1
                except Exception as exc:
                    counters["files_failed"] += 1
                    self._write_failed_document(connection, folder_id, path, exc, run_id)
                counters["files_processed"] += 1
                batch_count += 1
                _emit(
                    progress_callback,
                    "indexing",
                    counters,
                    files_total=files_total,
                    current_path=str(path),
                    started_at=started_at,
                    historical_rate=historical_rate,
                )
                if batch_count >= self.batch_size:
                    connection.commit()
                    batch_count = 0

            error_repo = IndexErrorRepository(connection)
            for unavailable in getattr(self.scanner, "unavailable_subtrees", []):
                error_repo.add(run_id, str(unavailable), "subtree_unavailable", "Directory could not be scanned")

            if cancel_checker is not None and cancel_checker():
                summary = _summary(counters)
                run_repo.finish(run_id, status="cancelled", **_run_finish_kwargs(summary))
                connection.commit()
                _emit(
                    progress_callback,
                    "cancelled",
                    counters,
                    files_total=files_total,
                    started_at=started_at,
                    historical_rate=historical_rate,
                )
                return summary

            _emit(
                progress_callback,
                "marking_deleted",
                counters,
                files_total=files_total,
                started_at=started_at,
                historical_rate=historical_rate,
            )
            deleted_ids = self.deleted_file_detector.find_deleted_document_ids(
                connection,
                folder_id,
                seen_paths,
                protected_subtrees=getattr(self.scanner, "unavailable_subtrees", []),
            )
            self.deleted_file_detector.mark_deleted(connection, deleted_ids)
            counters["files_deleted"] += len(deleted_ids)

            if cancel_checker is not None and cancel_checker():
                summary = _summary(counters)
                run_repo.finish(run_id, status="cancelled", **_run_finish_kwargs(summary))
                connection.commit()
                _emit(
                    progress_callback,
                    "cancelled",
                    counters,
                    files_total=files_total,
                    started_at=started_at,
                    historical_rate=historical_rate,
                )
                return summary

            _emit(
                progress_callback,
                "refreshing_caches",
                counters,
                files_total=files_total,
                started_at=started_at,
                historical_rate=historical_rate,
            )
            self._refresh_caches(connection)
            summary = _summary(counters)
            if cancel_checker is not None and cancel_checker():
                run_repo.finish(run_id, status="cancelled", **_run_finish_kwargs(summary))
                connection.commit()
                _emit(
                    progress_callback,
                    "cancelled",
                    counters,
                    files_total=files_total,
                    started_at=started_at,
                    historical_rate=historical_rate,
                )
                return summary
            run_repo.finish(run_id, status="completed", **_run_finish_kwargs(summary))
            connection.commit()
            _emit(
                progress_callback,
                "completed",
                counters,
                files_total=files_total,
                percent=100,
                started_at=started_at,
                historical_rate=historical_rate,
            )
            return summary
        except Exception:
            connection.rollback()
            if run_id is not None:
                try:
                    summary = _summary(counters)
                    IndexRunRepository(connection).finish(run_id, status="failed", **_run_finish_kwargs(summary))
                    connection.commit()
                except Exception:
                    connection.rollback()
            _emit(progress_callback, "failed", counters, files_total=files_total, started_at=started_at)
            raise
        finally:
            connection.close()

    def reindex_file(
        self,
        path: Path,
        *,
        cancel_checker: Callable[[], bool] | None = None,
    ) -> IndexSummary:
        self.database.initialize()
        path = Path(path)
        if cancel_checker is not None and not cancel_checker():
            return IndexSummary()
        connection = self.database.connect()
        try:
            if cancel_checker is not None and not cancel_checker():
                return IndexSummary()
            document_repo = DocumentRepository(connection)
            existing = document_repo.get_by_path(str(path))
            if not path.exists():
                if existing is not None:
                    DocumentStateService(connection).mark_deleted_retained(int(existing["id"]), reason="manual_reindex")
                    self._refresh_caches(connection)
                    connection.commit()
                    return IndexSummary(files_deleted=1)
                connection.commit()
                return IndexSummary()

            if existing is not None and existing["folder_id"] is not None:
                folder_id = int(existing["folder_id"])
            else:
                folder_id = IndexFolderRepository(connection).add(str(path.parent), normalize_path(path.parent))

            filter_result = self.scanner.file_filter.evaluate(path)
            if cancel_checker is not None and not cancel_checker():
                return IndexSummary()
            if filter_result.can_index:
                self._index_file(connection, folder_id, path)
                summary = IndexSummary(
                    files_seen=1,
                    files_processed=1,
                    files_indexed=0 if existing is not None else 1,
                    files_reindexed=1 if existing is not None else 0,
                    files_new=0 if existing is not None else 1,
                    files_changed=1 if existing is not None else 0,
                )
            else:
                self._write_skipped_document(connection, folder_id, path, filter_result.status)
                summary = IndexSummary(files_seen=1, files_processed=1, files_skipped=1)
            if cancel_checker is not None and not cancel_checker():
                connection.rollback()
                return IndexSummary()
            self._refresh_caches(connection)
            connection.commit()
            return summary
        except Exception:
            connection.rollback()
            raise
        finally:
            connection.close()

    def _process_indexable_file(self, connection, folder_id: int, path: Path, counters: dict[str, int]) -> None:
        document_repo = DocumentRepository(connection)
        existing = document_repo.get_by_path(str(path))
        decision = self.change_detector.detect(existing, path)
        if decision.decision == "new":
            self._index_file(connection, folder_id, path)
            counters["files_new"] += 1
            counters["files_indexed"] += 1
            return
        if decision.decision in {"unchanged", "changed_metadata"}:
            if existing is not None:
                if decision.decision == "changed_metadata":
                    document_repo.update_metadata_from_signature(int(existing["id"]), decision.signature, status="indexed")
                else:
                    document_repo.touch_verified(int(existing["id"]))
            counters["files_unchanged"] += 1
            return
        if decision.decision == "restored_unchanged" and existing is not None:
            DocumentStateService(connection).restore_indexed(int(existing["id"]), reason="restored_without_reindex")
            counters["files_restored"] += 1
            return
        if decision.decision in {"changed_hash", "restored_changed"}:
            self._index_file(connection, folder_id, path)
            counters["files_changed"] += 1
            counters["files_reindexed"] += 1
            if decision.decision == "restored_changed":
                counters["files_restored"] += 1
            return
        if decision.decision == "missing" and existing is not None:
            DocumentStateService(connection).mark_deleted_retained(int(existing["id"]), reason="missing_on_scan")
            counters["files_deleted"] += 1
            return
        if decision.decision == "error":
            raise OSError(decision.signature.error or "file signature error")

    def _index_file(self, connection, folder_id: int, path: Path) -> None:
        extracted = self.text_extractor.extract(path)
        stat_result = path.stat()
        attributes = read_file_attributes(path)
        now = datetime.now(UTC).isoformat()
        chunks = self.chunker.chunk(extracted.text)

        document_id = DocumentRepository(connection).upsert(
            {
                "folder_id": folder_id,
                "path": str(path),
                "path_norm": normalize_path(path),
                "filename": path.name,
                "filename_norm": self.normalizer.normalize(path.name),
                "extension": path.suffix,
                "extension_norm": path.suffix.casefold().lstrip("."),
                "size_bytes": int(stat_result.st_size),
                "modified_at": datetime.fromtimestamp(stat_result.st_mtime, UTC).isoformat(),
                "modified_ns": getattr(stat_result, "st_mtime_ns", None),
                "indexed_at": now,
                "last_seen_at": now,
                "last_verified_at": now,
                "last_missing_at": None,
                "payload_retained": 1,
                "state_reason": None,
                "stale_detected_at": None,
                "content_hash": _content_hash(path),
                "encoding": extracted.encoding,
                "line_ending": extracted.line_ending,
                "is_hidden": int(attributes.is_hidden),
                "is_system": int(attributes.is_system),
                "is_readonly": int(attributes.is_readonly),
                "index_status": "indexed",
                "error_message": None,
            }
        )

        self._clear_index_payload(connection, document_id)
        chunk_rows = _chunk_rows(chunks)
        chunk_ids = ChunkRepository(connection).replace_for_document(document_id, chunk_rows)
        fts = FtsRepository(connection)
        fts.replace_document(document_id, self.normalizer.normalize(path.name), normalize_path(path))
        fts.replace_chunks(document_id, [(chunk_id, chunk.text) for chunk_id, chunk in zip(chunk_ids, chunks, strict=True)])
        DocumentTermRepository(connection).replace_for_document(
            document_id,
            [
                *self.term_collector.collect(path.name, "filename"),
                *self.term_collector.collect(str(path), "path"),
                *self.term_collector.collect(extracted.text, "content"),
            ],
        )
        DocumentLemmaRepository(connection).replace_for_document(
            document_id,
            [
                *self.lemma_builder.collect(path.name, "filename"),
                *self.lemma_builder.collect(str(path), "path"),
                *self.lemma_builder.collect(extracted.text, "content"),
            ],
        )

    def _write_skipped_document(self, connection, folder_id: int, path: Path, status: str) -> None:
        stat_result = path.stat()
        attributes = read_file_attributes(path)
        now = datetime.now(UTC).isoformat()
        document_id = DocumentRepository(connection).upsert(
            {
                "folder_id": folder_id,
                "path": str(path),
                "path_norm": normalize_path(path),
                "filename": path.name,
                "filename_norm": self.normalizer.normalize(path.name),
                "extension": path.suffix,
                "extension_norm": path.suffix.casefold().lstrip("."),
                "size_bytes": int(stat_result.st_size),
                "modified_at": datetime.fromtimestamp(stat_result.st_mtime, UTC).isoformat(),
                "modified_ns": getattr(stat_result, "st_mtime_ns", None),
                "indexed_at": now,
                "last_seen_at": now,
                "last_verified_at": now,
                "last_missing_at": None,
                "payload_retained": 0,
                "state_reason": status,
                "stale_detected_at": None,
                "content_hash": None,
                "encoding": None,
                "line_ending": None,
                "is_hidden": int(attributes.is_hidden),
                "is_system": int(attributes.is_system),
                "is_readonly": int(attributes.is_readonly),
                "index_status": status,
                "error_message": None,
            }
        )
        self._clear_index_payload(connection, document_id)

    def _write_failed_document(self, connection, folder_id: int, path: Path, exc: Exception, run_id: int | None) -> None:
        status = exc.status if isinstance(exc, TextExtractionError) else "error_extract"
        if status.startswith("skipped_"):
            self._write_skipped_document(connection, folder_id, path, status)
            return

        try:
            stat_result = path.stat()
            size_bytes = int(stat_result.st_size)
            modified_at = datetime.fromtimestamp(stat_result.st_mtime, UTC).isoformat()
            modified_ns = getattr(stat_result, "st_mtime_ns", None)
        except OSError:
            size_bytes = 0
            modified_at = datetime.now(UTC).isoformat()
            modified_ns = None
        now = datetime.now(UTC).isoformat()
        document_id = DocumentRepository(connection).upsert(
            {
                "folder_id": folder_id,
                "path": str(path),
                "path_norm": normalize_path(path),
                "filename": path.name,
                "filename_norm": self.normalizer.normalize(path.name),
                "extension": path.suffix,
                "extension_norm": path.suffix.casefold().lstrip("."),
                "size_bytes": size_bytes,
                "modified_at": modified_at,
                "modified_ns": modified_ns,
                "indexed_at": now,
                "last_seen_at": now,
                "last_verified_at": now,
                "last_missing_at": None,
                "payload_retained": 0,
                "state_reason": status,
                "stale_detected_at": None,
                "content_hash": None,
                "encoding": None,
                "line_ending": None,
                "is_hidden": 0,
                "is_system": 0,
                "is_readonly": 0,
                "index_status": status,
                "error_message": str(exc),
            }
        )
        self._clear_index_payload(connection, document_id)
        IndexErrorRepository(connection).add(run_id, str(path), status, str(exc))
        if self.logger.hasHandlers():
            self.logger.warning("Index failed: status=%s path=%s", status, path)

    def _clear_index_payload(self, connection, document_id: int) -> None:
        connection.execute("DELETE FROM chunks_fts WHERE document_id = ?", (document_id,))
        connection.execute("DELETE FROM documents_fts WHERE document_id = ?", (document_id,))
        connection.execute("DELETE FROM chunks WHERE document_id = ?", (document_id,))
        connection.execute("DELETE FROM document_terms WHERE document_id = ?", (document_id,))
        connection.execute("DELETE FROM document_lemmas WHERE document_id = ?", (document_id,))

    def _refresh_caches(self, connection) -> None:
        TermRepository(connection).rebuild()
        LemmaRepository(connection).rebuild()


def _chunk_rows(chunks: list[TextChunk]) -> list[dict[str, object]]:
    return [
        {
            "chunk_index": chunk.chunk_index,
            "text": chunk.text,
            "line_start": chunk.line_start,
            "line_end": chunk.line_end,
            "char_start": chunk.char_start,
            "char_end": chunk.char_end,
            "column_start": chunk.column_start,
        }
        for chunk in chunks
    ]


def _content_hash(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as file:
        for block in iter(lambda: file.read(1024 * 1024), b""):
            digest.update(block)
    return digest.hexdigest()


def _new_counters() -> dict[str, int]:
    return {
        "files_seen": 0,
        "files_indexed": 0,
        "files_skipped": 0,
        "files_failed": 0,
        "files_new": 0,
        "files_changed": 0,
        "files_unchanged": 0,
        "files_deleted": 0,
        "files_restored": 0,
        "files_stale": 0,
        "files_reindexed": 0,
        "files_processed": 0,
    }


def _summary(counters: dict[str, int]) -> IndexSummary:
    return IndexSummary(**counters)


def _run_finish_kwargs(summary: IndexSummary) -> dict[str, int]:
    return {
        "files_seen": summary.files_seen,
        "files_indexed": summary.files_indexed,
        "files_skipped": summary.files_skipped,
        "files_failed": summary.files_failed,
        "files_new": summary.files_new,
        "files_changed": summary.files_changed,
        "files_unchanged": summary.files_unchanged,
        "files_deleted": summary.files_deleted,
        "files_restored": summary.files_restored,
        "files_stale": summary.files_stale,
        "files_reindexed": summary.files_reindexed,
    }


def _historical_files_per_second(connection) -> float | None:
    rows = connection.execute(
        """
        SELECT
            files_seen,
            (julianday(finished_at) - julianday(started_at)) * 86400.0 AS seconds
        FROM index_runs
        WHERE status = 'completed'
          AND files_seen > 0
          AND started_at IS NOT NULL
          AND finished_at IS NOT NULL
        ORDER BY id DESC
        LIMIT 5
        """
    ).fetchall()
    files = 0
    seconds = 0.0
    for row in rows:
        row_seconds = float(row["seconds"] or 0)
        if row_seconds <= 0:
            continue
        files += int(row["files_seen"])
        seconds += row_seconds
    if files <= 0 or seconds <= 0:
        return None
    return files / seconds


def _emit(
    callback: Callable[[IndexProgress], None] | None,
    phase: str,
    counters: dict[str, int],
    *,
    files_total: int | None,
    current_path: str | None = None,
    percent: int | None = None,
    started_at: float | None = None,
    historical_rate: float | None = None,
    message: str = "",
) -> None:
    if callback is None:
        return
    estimate = _progress_estimate(phase, counters, files_total, percent, started_at, historical_rate)
    callback(
        IndexProgress(
            phase=phase,
            current_path=current_path,
            files_total=files_total,
            files_seen=counters["files_seen"],
            files_processed=counters["files_processed"],
            files_indexed=counters["files_indexed"],
            files_reindexed=counters["files_reindexed"],
            files_new=counters["files_new"],
            files_changed=counters["files_changed"],
            files_unchanged=counters["files_unchanged"],
            files_deleted=counters["files_deleted"],
            files_restored=counters["files_restored"],
            files_skipped=counters["files_skipped"],
            files_failed=counters["files_failed"],
            percent=estimate.percent,
            eta_seconds=estimate.eta_seconds,
            files_per_second=estimate.files_per_second,
            message=message,
        )
    )


def _progress_estimate(
    phase: str,
    counters: dict[str, int],
    files_total: int | None,
    explicit_percent: int | None,
    started_at: float | None,
    historical_rate: float | None,
) -> ProgressEstimate:
    current_rate = _current_files_per_second(counters["files_processed"], started_at)
    rate = current_rate or historical_rate
    if rate is None and files_total is not None:
        rate = DEFAULT_ESTIMATED_FILES_PER_SECOND
    if explicit_percent is not None:
        return ProgressEstimate(percent=explicit_percent, eta_seconds=0 if explicit_percent >= 100 else None, files_per_second=rate)
    if phase == "scanning" or files_total is None:
        return ProgressEstimate(percent=None, eta_seconds=None, files_per_second=rate)
    if phase == "completed":
        return ProgressEstimate(percent=100, eta_seconds=0, files_per_second=rate)

    eta_seconds = _estimate_eta_seconds(phase, counters, files_total, started_at, rate)
    percent = _estimate_percent(phase, counters, files_total, started_at, eta_seconds)
    return ProgressEstimate(percent=percent, eta_seconds=eta_seconds, files_per_second=rate)


def _estimate_eta_seconds(
    phase: str,
    counters: dict[str, int],
    files_total: int,
    started_at: float | None,
    files_per_second: float | None,
) -> int | None:
    if phase in {"cancelled", "failed"}:
        return None
    if files_per_second is None or files_per_second <= 0:
        return None
    remaining = max(files_total - counters["files_processed"], 0)
    if remaining > 0:
        return max(1, int(ceil(remaining / files_per_second)))
    if phase not in {"marking_deleted", "refreshing_caches"}:
        return None
    if started_at is None:
        return None
    expected_total_seconds = files_total / files_per_second
    remaining_seconds = expected_total_seconds - (monotonic() - started_at)
    if remaining_seconds <= 0:
        return None
    return max(1, int(ceil(remaining_seconds)))


def _estimate_percent(
    phase: str,
    counters: dict[str, int],
    files_total: int,
    started_at: float | None,
    eta_seconds: int | None,
) -> int:
    if phase == "analyzing" or files_total <= 0:
        return 0
    if phase in {"cancelled", "failed"}:
        return min(95, int(counters["files_processed"] / files_total * 95))
    if phase == "marking_deleted":
        return 96
    if phase == "refreshing_caches":
        return 98
    return min(95, int(counters["files_processed"] / files_total * 95))


def _current_files_per_second(files_processed: int, started_at: float | None) -> float | None:
    if files_processed <= 0 or started_at is None:
        return None
    elapsed = monotonic() - started_at
    if elapsed <= 0:
        return None
    return files_processed / elapsed
