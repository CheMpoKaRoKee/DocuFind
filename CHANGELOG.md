# Changelog

All notable changes to DocuFind Local are documented here.

## 2026-07-13

- Optimized large-folder indexing by making the counting pass metadata-only, caching repeated morphology, reusing extraction hashes, and removing redundant payload deletes.
- Sanitized HTML markup and non-visible script/style content while preserving source offsets; blank HTML chunks are no longer stored in FTS.
- Added honest save/reindex partial-success states and cooperative cancellation checkpoints.
- Added synchronized indexed-folder state and safe handling of inaccessible roots and subtrees.
- Fixed absolute line, column, and character coordinates for exact, lemma, and fuzzy matches.
- Added streamed, batched indexing for large folders with phase-aware progress and ETA.
- Simplified the UI to Results and Editor tabs and added an Explorer button to every result.
- Removed duplicate result rendering and nested result-card backgrounds.
- Added the supplied PNG as the application and Windows executable icon.
- Passed the full 108-test suite and rebuilt the Windows executable.

## 0.1.0 — MVP

### Added

- Local Windows desktop application for folder indexing and file search.
- PySide6 interface with RU/EN localization.
- SQLite storage with migrations, WAL mode, document metadata, chunks, terms, lemmas, and FTS5 tables.
- Folder scanner, file filters, binary detection, long-line handling, encoding detection, and text extraction.
- Search by filename, path, content, exact phrase, Russian word forms, and typo-tolerant fuzzy matching.
- Russian morphology through `pymorphy3` with deterministic fallback for compatible degraded environments.
- Preview panel with matched snippet display and stale-file warning.
- Safe text editor with external-change detection, backup before save, atomic save, and single-file reindex after save.
- Background workers for indexing, search, and reindexing without blocking the UI.
- Settings dialog for indexing folders, exclusions, file size, extensions, fuzzy search, result limits, language, and backup policy.
- Index state block with document/chunk/folder counts, last indexing time, database path, and reindex-required status.
- Editor navigation across multiple mentions inside the selected search result.
- PyInstaller build configuration and `build_exe.py` for Windows executable builds.
- Release validation checklist with manual smoke-test steps.

### Tested

- Storage, scanner/filter, text extraction, Russian morphology, chunking, indexing, deleted-file lifecycle, query parsing, search core, fuzzy search, workers, UI, editor, quality gates, and build configuration.
- Verified Windows executable build through PyInstaller.

### Known limitations

- The project currently targets Windows desktop usage, not web or cloud deployment.
- Single-file reindex updates only the selected file; deleted sibling files are detected during full folder reindex.
- PyInstaller builds can be large because they include PySide6 and morphology dictionaries.
