# DocuFind Local

## Русский

DocuFind Local — локальное Windows-приложение для индексирования выбранных папок и поиска по имени файла, пути и содержимому. Приложение показывает найденные совпадения, preview-фрагмент, поддерживает русские словоформы, fuzzy-поиск и безопасное редактирование поддерживаемых текстовых файлов с backup перед сохранением.

### Возможности MVP

- Индексация выбранной папки.
- Поиск по имени файла, пути и содержимому.
- Поддержка русской морфологии через fallback-анализатор, если `pymorphy3` недоступен.
- Fuzzy-поиск по опечаткам.
- Preview найденного фрагмента и предупреждение о stale state.
- Безопасный редактор текстовых файлов: conflict detection, backup, atomic save, reindex after save.
- Переключение интерфейса RU/EN.
- Логи в portable/installed runtime-папках.

### Запуск из исходников

Рекомендуемый интерпретатор для UI: обычный Python 3.13, не free-threaded `3.13t`.

```powershell
py -3.13 -m app.main
```

### Тесты

```powershell
py -3.13 -m unittest tests.test_stage2_app_paths_i18n tests.test_stage3_database tests.test_stage4_scanner_filter tests.test_stage5_text_extraction tests.test_stage6_russian_morphology tests.test_stage7_chunker tests.test_stage8_index_service tests.test_stage9_deleted_lifecycle tests.test_stage10_query_parser_fts tests.test_stage11_search_core tests.test_stage12_fuzzy_search tests.test_stage13_workers tests.test_stage14_ui tests.test_stage15_editor tests.test_stage16_quality_gates tests.test_stage17_build
```

### Сборка Windows-приложения

```powershell
py -3.13 build_exe.py
```

Готовый файл ожидается в `dist/DocuFindLocal.exe`. Папки `dist/` и `build/` не коммитятся.

### Релизная проверка и ручной тест

См. подробный чеклист: RELEASE_CHECKLIST.md.

### Runtime-папки

- Portable mode: `./data/`, `./logs/`, `./backups/`.
- Installed mode: `%LOCALAPPDATA%\DocuFind\`.

## English

DocuFind Local is a local Windows application for indexing selected folders and searching with filename, path, and file content. It shows matches, preview snippets, supports Russian word forms, fuzzy search, and safe editing for supported text files with backups before save.

### MVP Features

- Index a selected folder.
- Search with filename, path, and content.
- Russian morphology through the fallback analyzer when `pymorphy3` is unavailable.
- Typo-tolerant fuzzy search.
- Preview for matched snippets and stale-state warnings.
- Safe text editor: conflict detection, backup, atomic save, reindex after save.
- RU/EN interface switching.
- Logs in portable/installed runtime folders.

### Run From Source

Use regular Python 3.13 for the UI, not free-threaded `3.13t`.

```powershell
py -3.13 -m app.main
```

### Tests

```powershell
py -3.13 -m unittest tests.test_stage2_app_paths_i18n tests.test_stage3_database tests.test_stage4_scanner_filter tests.test_stage5_text_extraction tests.test_stage6_russian_morphology tests.test_stage7_chunker tests.test_stage8_index_service tests.test_stage9_deleted_lifecycle tests.test_stage10_query_parser_fts tests.test_stage11_search_core tests.test_stage12_fuzzy_search tests.test_stage13_workers tests.test_stage14_ui tests.test_stage15_editor tests.test_stage16_quality_gates tests.test_stage17_build
```

### Build Windows Executable

```powershell
py -3.13 build_exe.py
```

The executable is expected at `dist/DocuFindLocal.exe`. The `dist/` and `build/` folders are not committed.

### Release Validation and Manual Test

See the detailed checklist: RELEASE_CHECKLIST.md.

### Runtime Folders

- Portable mode: `./data/`, `./logs/`, `./backups/`.
- Installed mode: `%LOCALAPPDATA%\DocuFind\`.


