"""Binary file detection for supported text extensions."""

from __future__ import annotations

from pathlib import Path


class BinaryDetector:
    def __init__(self, sample_size: int = 8192, max_non_text_ratio: float = 0.30) -> None:
        self.sample_size = sample_size
        self.max_non_text_ratio = max_non_text_ratio

    def is_binary(self, path: Path) -> bool:
        try:
            sample = path.read_bytes()[: self.sample_size]
        except OSError:
            return False
        if not sample:
            return False
        if b"\x00" in sample:
            return True
        non_text = sum(1 for byte in sample if not _is_text_byte(byte))
        return (non_text / len(sample)) > self.max_non_text_ratio


def _is_text_byte(byte: int) -> bool:
    return byte in {9, 10, 13} or 32 <= byte <= 126 or byte >= 128

