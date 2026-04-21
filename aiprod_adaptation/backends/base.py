"""
Base class for all AIPROD backends.

Every backend receives an AIPRODOutput (the IR) and returns a string
representation suitable for its target renderer or export format.
"""

from __future__ import annotations

from abc import ABC, abstractmethod

from aiprod_adaptation.models.schema import AIPRODOutput


class BackendBase(ABC):
    @abstractmethod
    def export(self, output: AIPRODOutput) -> str:
        """Convert AIPRODOutput to a string representation."""
        ...
