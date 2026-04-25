"""
reference_constraints — Extract actionable hard constraints from VisualInvariants.

Public API
----------
    ReferenceConstraints        — Pydantic model (JSON-serialisable)
    ReferenceConstraintsExtractor.extract() — deterministic extraction
"""

from aiprod_adaptation.core.reference_constraints.extractor import (
    ReferenceConstraintsExtractor,
)
from aiprod_adaptation.core.reference_constraints.models import ReferenceConstraints

__all__ = [
    "ReferenceConstraints",
    "ReferenceConstraintsExtractor",
]
