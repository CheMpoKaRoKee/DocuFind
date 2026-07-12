"""Compare file signatures with stored document rows."""

from __future__ import annotations

import sqlite3
from dataclasses import dataclass
from pathlib import Path

from app.indexer.file_signature_service import FileSignature, FileSignatureService


@dataclass(frozen=True)
class FileChangeDecision:
    decision: str
    signature: FileSignature


class FileChangeDetector:
    def __init__(self, signature_service: FileSignatureService | None = None) -> None:
        self.signature_service = signature_service or FileSignatureService()

    def detect(self, document: sqlite3.Row | None, path: Path) -> FileChangeDecision:
        signature = self.signature_service.get_signature(path)
        if not signature.exists or not signature.is_file:
            return FileChangeDecision("missing", signature)
        if signature.error:
            return FileChangeDecision("error", signature)
        if document is None:
            return FileChangeDecision("new", signature)

        status = str(document["index_status"])
        if status == "deleted_retained":
            signature = self.signature_service.get_signature(path, include_hash=True)
            if _hash_matches(document, signature):
                return FileChangeDecision("restored_unchanged", signature)
            return FileChangeDecision("restored_changed", signature)

        if _metadata_matches(document, signature):
            return FileChangeDecision("unchanged", signature)

        signature = self.signature_service.get_signature(path, include_hash=True)
        if _hash_matches(document, signature):
            return FileChangeDecision("changed_metadata", signature)
        return FileChangeDecision("changed_hash", signature)


def _metadata_matches(document: sqlite3.Row, signature: FileSignature) -> bool:
    return (
        int(document["size_bytes"]) == int(signature.size_bytes or -1)
        and document["modified_ns"] is not None
        and signature.modified_ns is not None
        and int(document["modified_ns"]) == int(signature.modified_ns)
    )


def _hash_matches(document: sqlite3.Row, signature: FileSignature) -> bool:
    stored_hash = document["content_hash"]
    return stored_hash is not None and signature.content_hash is not None and str(stored_hash) == signature.content_hash
