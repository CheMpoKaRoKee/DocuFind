"""High-level file indexing service."""

from __future__ import annotations

import hashlib
from dataclasses import dataclass
from datetime import UTC, datetime
from pathlib import Path

from app.indexer.chunker import Chunker, TextChunk
from app.indexer.deleted_file_detector import DeletedFileDetector
from app.indexer.folder_scanner import FolderScanner
from app.indexer.term_collector import TermCollector
from app.indexer.text_extractor import TextExtractionError, TextExtractor
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


@dataclass(frozen=True)
class IndexSummary:
    files_seen: int = 0
    files_indexed: int = 0
    files_skipped: int = 0
    files_failed: int = 0


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
        batch_size: int = 100,
    ) -> None:
        self.database = database
        self.scanner = scanner or FolderScanner()
        self.text_extractor = text_extractor or TextExtractor()
        self.chunker = chunker or Chunker()
        self.term_collector = term_collector or TermCollector()
        self.lemma_builder = lemma_builder or LemmaIndexBuilder()
        self.deleted_file_detector = deleted_file_detector or DeletedFileDetector()
        self.normalizer = TextNormalizer()
        self.batch_size = batch_size
        self.logger = get_logger("indexing")

    def index_folder(self, folder: Path) -> IndexSummary:
        self.database.initialize()
        folder = Path(folder)
        seen = indexed = skipped = failed = batch_count = 0
        seen_paths: set[str] = set()
        run_id: int | None = None

        connection = self.database.connect()
        try:
            folder_id = IndexFolderRepository(connection).add(str(folder), normalize_path(folder))
            run_repo = IndexRunRepository(connection)
            run_id = run_repo.start(folder_id)
            connection.commit()

            for filter_result in self.scanner.scan(folder):
                seen += 1
                seen_paths.add(str(filter_result.path))
                try:
                    if filter_result.can_index:
                        self._index_file(connection, folder_id, filter_result.path)
                        indexed += 1
                    else:
                        self._write_skipped_document(connection, folder_id, filter_result.path, filter_result.status)
                        skipped += 1
                except Exception as exc:
                    failed += 1
                    self._write_failed_document(connection, folder_id, filter_result.path, exc, run_id)

                batch_count += 1
                if batch_count >= self.batch_size:
                    self._refresh_caches(connection)
                    connection.commit()
                    batch_count = 0

            deleted_ids = self.deleted_file_detector.find_deleted_document_ids(connection, folder_id, seen_paths)
            self.deleted_file_detector.mark_deleted(connection, deleted_ids)
            self._refresh_caches(connection)
            run_repo.finish(
                run_id,
                status="completed",
                files_seen=seen,
                files_indexed=indexed,
                files_skipped=skipped,
                files_failed=failed,
            )
            connection.commit()
            return IndexSummary(files_seen=seen, files_indexed=indexed, files_skipped=skipped, files_failed=failed)
        except Exception:
            connection.rollback()
            if run_id is not None:
                try:
                    IndexRunRepository(connection).finish(
                        run_id,
                        status="failed",
                        files_seen=seen,
                        files_indexed=indexed,
                        files_skipped=skipped,
                        files_failed=failed,
                    )
                    connection.commit()
                except Exception:
                    connection.rollback()
            raise
        finally:
            connection.close()

    def reindex_file(self, path: Path) -> IndexSummary:
        self.database.initialize()
        path = Path(path)
        connection = self.database.connect()
        try:
            document_repo = DocumentRepository(connection)
            existing = document_repo.get_by_path(str(path))
            if not path.exists():
                if existing is not None:
                    document_id = int(existing["id"])
                    document_repo.mark_deleted(document_id)
                    self._clear_index_payload(connection, document_id)
                    self._refresh_caches(connection)
                connection.commit()
                return IndexSummary()

            if existing is not None and existing["folder_id"] is not None:
                folder_id = int(existing["folder_id"])
            else:
                folder_id = IndexFolderRepository(connection).add(str(path.parent), normalize_path(path.parent))

            filter_result = self.scanner.file_filter.evaluate(path)
            if filter_result.can_index:
                self._index_file(connection, folder_id, path)
                summary = IndexSummary(files_seen=1, files_indexed=1)
            else:
                self._write_skipped_document(connection, folder_id, path, filter_result.status)
                summary = IndexSummary(files_seen=1, files_skipped=1)
            self._refresh_caches(connection)
            connection.commit()
            return summary
        except Exception:
            connection.rollback()
            raise
        finally:
            connection.close()
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
        }
        for chunk in chunks
    ]


def _content_hash(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as file:
        for block in iter(lambda: file.read(1024 * 1024), b""):
            digest.update(block)
    return digest.hexdigest()

