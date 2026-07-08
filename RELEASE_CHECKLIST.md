# Release and Manual Test Checklist

## Russian

### 1. Подготовка среды

```powershell
py -3.13 -c "import PySide6, pymorphy3; print(PySide6.__version__); print(pymorphy3.__version__)"
py -3.13 -m unittest tests.test_stage2_app_paths_i18n tests.test_stage3_database tests.test_stage4_scanner_filter tests.test_stage5_text_extraction tests.test_stage6_russian_morphology tests.test_stage7_chunker tests.test_stage8_index_service tests.test_stage9_deleted_lifecycle tests.test_stage10_query_parser_fts tests.test_stage11_search_core tests.test_stage12_fuzzy_search tests.test_stage13_workers tests.test_stage14_ui tests.test_stage15_editor tests.test_stage16_quality_gates tests.test_stage17_build
```

Ожидаемо: все тесты проходят без skipped на `py -3.13`.

### 2. Сборка

```powershell
py -3.13 build_exe.py
```

Ожидаемо: создан `dist\DocuFindLocal.exe`.

### 3. Ручной smoke test из исходников

```powershell
py -3.13 -m app.main
```

Проверить:

- окно запускается без ошибок;
- язык по умолчанию русский;
- переключение RU/EN в настройках меняет подписи;
- можно выбрать небольшую тестовую папку;
- индексация завершается без зависания UI;
- поиск по имени файла возвращает результат;
- поиск по содержимому возвращает строку, колонку и snippet;
- запрос `персональные данные` находит формы `персональных данных`, `персональными данными`, `персональным данным`;
- typo/fuzzy запрос возвращает ожидаемые близкие совпадения;
- preview показывает фрагмент;
- editor открывает `.txt`/`.md`, сохраняет файл, создаёт backup и после сохранения результат переиндексируется;
- если файл изменён внешне перед сохранением, editor блокирует save до reload.

### 4. Ручной smoke test executable

```powershell
.\dist\DocuFindLocal.exe
```

Повторить проверки из пункта 3. Дополнительно проверить, что создаются runtime-папки:

- portable/dev mode near project: `data`, `logs`, `backups`;
- installed mode при обычном запуске из exe: `%LOCALAPPDATA%\DocuFind`.

### 5. Большая папка

На папке с 1000+ текстовыми файлами проверить:

- индексация не падает;
- UI реагирует во время индексации;
- поиск выполняется за приемлемое время;
- логи не содержат полного содержимого пользовательских файлов.

## English

### 1. Environment

```powershell
py -3.13 -c "import PySide6, pymorphy3; print(PySide6.__version__); print(pymorphy3.__version__)"
py -3.13 -m unittest tests.test_stage2_app_paths_i18n tests.test_stage3_database tests.test_stage4_scanner_filter tests.test_stage5_text_extraction tests.test_stage6_russian_morphology tests.test_stage7_chunker tests.test_stage8_index_service tests.test_stage9_deleted_lifecycle tests.test_stage10_query_parser_fts tests.test_stage11_search_core tests.test_stage12_fuzzy_search tests.test_stage13_workers tests.test_stage14_ui tests.test_stage15_editor tests.test_stage16_quality_gates tests.test_stage17_build
```

Expected: all tests pass without skips on `py -3.13`.

### 2. Build

```powershell
py -3.13 build_exe.py
```

Expected: `dist\DocuFindLocal.exe` is created.

### 3. Manual Smoke Test From Source

```powershell
py -3.13 -m app.main
```

Check:

- the window opens without errors;
- default language is Russian;
- RU/EN switch updates labels;
- a small test folder can be selected;
- indexing finishes without freezing the UI;
- filename search returns a result;
- content search returns line, column, and snippet;
- query `персональные данные` finds `персональных данных`, `персональными данными`, `персональным данным`;
- typo/fuzzy query returns expected close matches;
- preview shows a fragment;
- editor opens `.txt`/`.md`, saves, creates a backup, and reindexes after save;
- external file changes block save until reload.

### 4. Manual Executable Smoke Test

```powershell
.\dist\DocuFindLocal.exe
```

Repeat section 3. Also verify runtime folders:

- portable/dev mode near project: `data`, `logs`, `backups`;
- installed mode from exe: `%LOCALAPPDATA%\DocuFind`.

### 5. Larger Folder

On a folder with 1000+ text files, verify:

- indexing does not crash;
- UI remains responsive during indexing;
- search latency is acceptable;
- logs do not contain full user file contents.
