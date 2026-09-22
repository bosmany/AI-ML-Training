"""The rule interface. PROVIDED."""

from __future__ import annotations

from abc import ABC, abstractmethod
from typing import ClassVar

from lab.models import Document, Finding, Severity


class Rule(ABC):
    """A rule is a small object with metadata and a pure ``check(doc) -> list[Finding]``."""

    id: ClassVar[str]
    severity: ClassVar[Severity]
    description: ClassVar[str]

    @abstractmethod
    def check(self, doc: Document) -> list[Finding]:
        """Return the findings for one document (empty list when it is fine). Must not mutate ``doc``."""

    def finding(self, doc: Document, pointer: str, message: str) -> Finding:
        """Build a Finding for ``pointer`` with this rule's id/severity and the right file and line."""
        return Finding(self.id, self.severity, message, doc.file, pointer, doc.line_for(pointer))
