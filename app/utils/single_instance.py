"""Single-instance guard for the desktop application."""

from __future__ import annotations

from pathlib import Path


class SingleInstanceError(Exception):
    """Raised when another DocuFind process already owns the app lock."""


class SingleInstanceLock:
    def __init__(self, path: Path) -> None:
        self.path = Path(path)
        self.path.parent.mkdir(parents=True, exist_ok=True)
        self._file = self.path.open("a+b")
        try:
            _lock_file(self._file)
        except OSError as exc:
            self._file.close()
            raise SingleInstanceError(str(exc)) from exc

    def release(self) -> None:
        if self._file.closed:
            return
        try:
            _unlock_file(self._file)
        finally:
            self._file.close()


def _lock_file(file) -> None:
    try:
        import msvcrt

        file.seek(0)
        msvcrt.locking(file.fileno(), msvcrt.LK_NBLCK, 1)
    except ImportError:
        import fcntl

        fcntl.flock(file.fileno(), fcntl.LOCK_EX | fcntl.LOCK_NB)


def _unlock_file(file) -> None:
    try:
        import msvcrt

        file.seek(0)
        msvcrt.locking(file.fileno(), msvcrt.LK_UNLCK, 1)
    except ImportError:
        import fcntl

        fcntl.flock(file.fileno(), fcntl.LOCK_UN)
