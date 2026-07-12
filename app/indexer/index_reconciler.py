"""Basic reconciliation service for indexed folders and filesystem state."""

from __future__ import annotations

from pathlib import Path

from app.indexer.index_service import IndexService, IndexSummary
from app.storage.database import Database
from app.storage.index_folder_repository import IndexFolderRepository


class IndexReconciler:
    def __init__(self, database: Database) -> None:
        self.database = database

    def reconcile_enabled_folders(self) -> list[IndexSummary]:
        self.database.initialize()
        summaries: list[IndexSummary] = []
        with self.database.session() as connection:
            folders = [str(row["path"]) for row in IndexFolderRepository(connection).list_enabled()]
        service = IndexService(self.database)
        for folder in folders:
            summaries.append(service.index_folder(Path(folder)))
        return summaries
