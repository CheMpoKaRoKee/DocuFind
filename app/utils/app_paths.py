"""Application path resolution for portable and installed modes."""

from __future__ import annotations

import os
from dataclasses import dataclass
from pathlib import Path

APP_DIR_NAME = "DocuFind"
PORTABLE_ENV = "DOCUFIND_PORTABLE"


def _truthy(value: str | None) -> bool:
    return value is not None and value.strip().casefold() in {"1", "true", "yes", "on", "portable"}


@dataclass(frozen=True)
class AppPaths:
    """Resolved application paths."""

    base_dir: Path
    portable: bool = False

    @classmethod
    def from_environment(cls, *, base_dir: Path | None = None, portable: bool | None = None) -> "AppPaths":
        if portable is None:
            portable = _truthy(os.environ.get(PORTABLE_ENV))

        if portable:
            return cls(base_dir=base_dir or Path.cwd(), portable=True)

        local_app_data = os.environ.get("LOCALAPPDATA")
        if local_app_data:
            root = Path(local_app_data) / APP_DIR_NAME
        else:
            root = base_dir or Path.cwd()
        return cls(base_dir=root, portable=False)

    @property
    def data_dir(self) -> Path:
        return self.base_dir / "data" if self.portable else self.base_dir

    @property
    def logs_dir(self) -> Path:
        return self.base_dir / "logs"

    @property
    def backups_dir(self) -> Path:
        return self.base_dir / "backups"

    @property
    def database_path(self) -> Path:
        return self.data_dir / "docufind.db"

    def ensure_runtime_dirs(self) -> None:
        self.data_dir.mkdir(parents=True, exist_ok=True)
        self.logs_dir.mkdir(parents=True, exist_ok=True)
        self.backups_dir.mkdir(parents=True, exist_ok=True)


