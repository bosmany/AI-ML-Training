"""Data model. PROVIDED - read it, do not edit it."""

from __future__ import annotations

import enum
from dataclasses import dataclass, field
from typing import Any


class Severity(enum.IntEnum):
    """Ordered: ``Severity.HIGH >= Severity.MEDIUM``."""

    LOW = 1
    MEDIUM = 2
    HIGH = 3
    CRITICAL = 4

    @property
    def label(self) -> str:
        return self.name.lower()

    @classmethod
    def parse(cls, text: str) -> Severity:
        try:
            return cls[str(text).strip().upper()]
        except KeyError:
            raise ValueError(f"unknown severity {text!r} (use low, medium, high or critical)") from None


@dataclass(frozen=True)
class Finding:
    rule_id: str
    severity: Severity
    message: str
    file: str
    path: str  # JSON pointer inside the document, e.g. /services/web/image
    line: int | None  # 1-based line of that key, None if unknown

    def to_dict(self) -> dict[str, Any]:
        return {
            "rule_id": self.rule_id,
            "severity": self.severity.label,
            "message": self.message,
            "file": self.file,
            "path": self.path,
            "line": self.line,
        }


@dataclass
class Document:
    """One YAML document of a file: the parsed data plus a JSON-pointer -> line index."""

    file: str
    data: Any
    lines: dict[str, int] = field(default_factory=dict)

    def line_for(self, pointer: str) -> int | None:
        """Line of ``pointer``, or of its closest ancestor that has one (``""`` is the whole document)."""
        while True:
            if pointer in self.lines:
                return self.lines[pointer]
            if not pointer:
                return None
            pointer = pointer.rsplit("/", 1)[0]


class ConfigParseError(Exception):
    """A file that is not valid YAML/JSON. Carries the position the parser reported."""

    def __init__(self, file: str, line: int | None, column: int | None, message: str) -> None:
        where = f"{file}:{line}:{column}" if line is not None else file
        super().__init__(f"{where}: {message}")
        self.file, self.line, self.column, self.message = file, line, column, message
