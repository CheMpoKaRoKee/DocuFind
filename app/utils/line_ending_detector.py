"""Line ending detection."""

from __future__ import annotations


class LineEndingDetector:
    def detect(self, text: str) -> str:
        crlf = text.count("\r\n")
        normalized = text.replace("\r\n", "")
        cr = normalized.count("\r")
        lf = normalized.count("\n")

        if crlf >= cr and crlf >= lf and crlf > 0:
            return "crlf"
        if cr > lf and cr > 0:
            return "cr"
        if lf > 0:
            return "lf"
        return "none"

