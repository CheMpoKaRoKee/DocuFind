"""Encoding detection for MVP text formats."""

from __future__ import annotations


class EncodingDetector:
    def detect(self, data: bytes) -> str:
        if data.startswith(b"\xef\xbb\xbf"):
            return "utf-8-sig"
        if data.startswith(b"\xff\xfe"):
            return "utf-16-le"
        if data.startswith(b"\xfe\xff"):
            return "utf-16-be"

        for encoding in ("utf-8", "cp1251", "latin-1"):
            try:
                data.decode(encoding)
                return encoding
            except UnicodeDecodeError:
                continue
        return "utf-8"

