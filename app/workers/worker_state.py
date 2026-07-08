"""Shared worker state for pause/cancel semantics."""

from __future__ import annotations

from dataclasses import dataclass
from threading import Event
from time import sleep


@dataclass(frozen=True)
class WorkerResult:
    status: str
    payload: object | None = None
    error: str | None = None


class WorkerState:
    def __init__(self) -> None:
        self._cancelled = Event()
        self._paused = Event()

    def cancel(self) -> None:
        self._cancelled.set()

    def pause(self) -> None:
        self._paused.set()

    def resume(self) -> None:
        self._paused.clear()

    @property
    def is_cancelled(self) -> bool:
        return self._cancelled.is_set()

    @property
    def is_paused(self) -> bool:
        return self._paused.is_set()

    def checkpoint(self) -> bool:
        while self.is_paused and not self.is_cancelled:
            sleep(0.01)
        return not self.is_cancelled

