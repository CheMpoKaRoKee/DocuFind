# CHANGELOG.md

## 2026-07-08

- Bootstrapped the project structure.
- Added project metadata and initial README.
- Added safe rotating logging setup.
- Added developer CLI bootstrap check.
- Added `.gitignore` for local runtime and Python cache artifacts.
- Verified bootstrap CLI and Python syntax.
- Added `AppPaths` for portable and installed runtime paths.
- Added RU/EN localization JSON files.
- Added `I18nService` and Stage 2 unit tests.
- Added SQLite database connection/session management.
- Added schema migrations for architecture tables, FTS5 tables, and indexes.
- Added storage repositories and Stage 3 database tests.
- Added path normalization, path rules, and file attribute detection.
- Added binary detection, `FileFilter`, `FolderScanner`, and Stage 4 scanner/filter tests.
- Added encoding detection, line ending detection, long-line handling, and `TextExtractor`.
- Added Stage 5 text extraction tests.
- Added Russian tokenizer, morphology analyzer with fallback, lemmatizer, lemma index builder, and query expander.
- Added Stage 6 Russian morphology tests, including required Russian word-form coverage.
- Added line-aware `Chunker` with overlap, line/char ranges, and very long line handling.
- Added Stage 7 chunker tests.
- Added `TextNormalizer`, `TermCollector`, and `IndexService`.
- Integrated indexing writes for documents, chunks, FTS, document terms, document lemmas, indexed term/lemma caches, index errors, and batch commits.
- Added Stage 8 indexing tests for success, skipped files, reindex replacement, and error recording.
- Added `IndexRunRepository` and `DeletedFileDetector`.
- Extended `IndexService` with index run tracking and deleted-file lifecycle cleanup.
- Fixed `DocumentRepository.upsert` id handling after SQLite conflict updates.
- Added Stage 9 deleted-file lifecycle tests.
- Added `SearchQuery` and `QueryTermGroup` models.
- Added `QueryParser` for words, phrases, `ext:`, and `folder:` syntax.
- Added whitelist-based `FtsQueryBuilder` and bad-query tests preventing raw user input from reaching SQLite `MATCH`.
- Added search result models and search helpers for occurrence location, snippets, deduplication, and ranking.
- Added filename, content, and lemma search plus `SearchService` aggregation.
- Added Stage 11 search core tests for filename/path/content/lemma search, filters, match positions, and lazy loading markers.
- Added `FuzzySearch` over indexed terms and lemmas with source/length/first-char candidate filtering.
- Integrated fuzzy matches into `SearchService` and added Stage 12 fuzzy search tests.
- Added worker state plus `IndexWorker`, `SearchWorker`, and `ReindexWorker` wrappers.
- Added Stage 13 worker tests for indexing, searching, reindexing, and pre-run cancellation.
- Checked Stage 14 UI dependency and recorded the current `PySide6` blocker.
- Normalized duplicate Stage 14 entries in `TASKS.md`.
- Removed stale intermediate `Later stages` headings from `TASKS.md`.
- Enabled Stage 14 UI work through regular Python 3.13 where PySide6 6.11.1 is available.
- Added PySide6 UI panels and main window wiring for indexing, searching, preview, settings, and RU/EN language switching.
- Updated the application entry point to launch the PySide6 main window.
- Extended RU/EN localization keys for Stage 14 UI.
- Updated `I18nService` to read UTF-8 locale files with an optional BOM.
- Added Stage 14 UI tests with graceful skips when PySide6 is unavailable in the selected Python interpreter.
- Initialized git repository, committed the full project, and pushed `main` to `https://github.com/CheMpoKaRoKee/DocuFind-Local..git`.
- Added editor file loading with editable/read-only/blocked modes and external-change snapshots.
- Added conflict detection, backup creation, backup cleanup, and atomic safe-save services.
- Added optional reindex after editor save through `ReindexWorker`.
- Added PySide6 `EditorPanel` and connected it to the main window alongside preview.
- Extended RU/EN localization keys for the editor UI.
- Added Stage 15 editor tests for loading, blocked modes, conflict detection, backup cleanup, safe save, reindex, and editor panel localization.
- Added Stage 16 quality gate tests for i18n catalog parity, required UI/editor localization keys, and stage test module coverage.
- Passed full Stage 2-16 unittest suites on Python 3.13 and default Python 3.13t with expected UI skips.
- Added PyInstaller spec and `build_exe.py` for Windows executable builds.
- Updated README with RU/EN usage, testing, build, and runtime folder instructions.
- Added Stage 17 build configuration tests.
- Verified PyInstaller build: `dist\\DocuFindLocal.exe` was created successfully.
- Passed full Stage 2-17 unittest suites on Python 3.13 and default Python 3.13t with expected UI skips.
- Installed and verified `pymorphy3` 2.0.6 in the regular Python 3.13 environment.
- Updated `MorphologyAnalyzer` to use `pymorphy3` as the primary analyzer with deterministic fallback for incompatible environments.
- Added noun/domain disambiguation so `данные` remains searchable as `данные` in the required Russian morphology scenario.
- Added `IndexService.reindex_file()` and updated `ReindexWorker` to reindex only the target file.
- Added tests for `pymorphy3` activation and single-file reindex behavior that leaves sibling documents untouched.
- Updated PyInstaller spec to include `pymorphy3` dictionaries.
- Added `RELEASE_CHECKLIST.md` with RU/EN release validation and manual smoke test instructions.
- Rebuilt `dist\\DocuFindLocal.exe` successfully after adding full morphology support.


- Fixed the Settings button: it now opens a full settings dialog using SQLite settings.
- Added runtime settings for indexing folders, exclusions, file size, extensions, fuzzy search, result limits, language, and backup policy.
- Added an index state block to the UI with document/chunk/folder counts, last indexing time, database path, and saved/empty/running/reindex-required status.
- Applied settings to indexing, search, editor backup, and language switching without restart where possible.

- Added editor mention navigation for selected search results: mention dropdown, previous/next controls, and text selection using indexed character ranges.


