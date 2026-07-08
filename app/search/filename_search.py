"""Filename and path search."""

from __future__ import annotations

import sqlite3

from app.models.file_match import FileMatch
from app.models.search_query import SearchQuery


class FilenameSearch:
    def search(self, connection: sqlite3.Connection, query: SearchQuery) -> dict[int, list[FileMatch]]:
        results: dict[int, list[FileMatch]] = {}
        where, params = _document_filters(query)
        rows = connection.execute(
            f"""
            SELECT id, filename, filename_norm, path, path_norm
            FROM documents
            WHERE index_status = 'indexed' {where}
            """,
            params,
        )
        for row in rows:
            for group in query.groups:
                for variant in group.variants:
                    if variant and variant in row["filename_norm"]:
                        results.setdefault(int(row["id"]), []).append(
                            FileMatch(int(row["id"]), "filename", group.original, row["filename"], "exact")
                        )
                    if variant and variant in row["path_norm"]:
                        results.setdefault(int(row["id"]), []).append(
                            FileMatch(int(row["id"]), "path", group.original, row["path"], "exact")
                        )
        return results


def _document_filters(query: SearchQuery) -> tuple[str, list[str]]:
    clauses: list[str] = []
    params: list[str] = []
    if query.extension:
        clauses.append("extension_norm = ?")
        params.append(query.extension)
    if query.folder:
        clauses.append("path LIKE ?")
        params.append(query.folder.rstrip("\\/") + "%")
    return (" AND " + " AND ".join(clauses) if clauses else ""), params

