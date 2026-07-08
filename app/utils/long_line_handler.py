"""Long line handling before chunking."""

from __future__ import annotations

from dataclasses import dataclass


@dataclass(frozen=True)
class LongLineResult:
    text: str
    long_line_count: int


class LongLineHandler:
    def __init__(self, max_line_length: int = 20_000) -> None:
        self.max_line_length = max_line_length

    def process(self, text: str) -> LongLineResult:
        output: list[str] = []
        long_line_count = 0
        lines = text.splitlines(keepends=True)

        for line in lines:
            body = line.rstrip("\r\n")
            ending = line[len(body) :]
            if len(body) <= self.max_line_length:
                output.append(line)
                continue

            long_line_count += 1
            for start in range(0, len(body), self.max_line_length):
                output.append(body[start : start + self.max_line_length])
                if start + self.max_line_length < len(body):
                    output.append("\n")
            output.append(ending)

        return LongLineResult(text="".join(output), long_line_count=long_line_count)

