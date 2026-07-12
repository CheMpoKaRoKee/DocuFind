"""Indexing progress model independent from UI frameworks."""

from __future__ import annotations

from dataclasses import dataclass


@dataclass(frozen=True)
class IndexProgress:
    phase: str
    current_path: str | None = None
    files_total: int | None = None
    files_seen: int = 0
    files_processed: int = 0
    files_indexed: int = 0
    files_reindexed: int = 0
    files_new: int = 0
    files_changed: int = 0
    files_unchanged: int = 0
    files_deleted: int = 0
    files_restored: int = 0
    files_skipped: int = 0
    files_failed: int = 0
    percent: int | None = None
    eta_seconds: int | None = None
    files_per_second: float | None = None
    message: str = ""
