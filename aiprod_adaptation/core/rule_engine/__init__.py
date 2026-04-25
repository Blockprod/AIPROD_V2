"""rule_engine — hierarchical, conflict-aware rule evaluation for AIPROD_Cinematic."""
from aiprod_adaptation.core.rule_engine.conflict_resolver import ConflictResolutionEngine
from aiprod_adaptation.core.rule_engine.evaluator import RuleEvaluator
from aiprod_adaptation.core.rule_engine.models import (
    CompoundCondition,
    ConditionOperator,
    ConflictRecord,
    ConflictType,
    EvalContext,
    FieldOperator,
    LeafCondition,
    ResolutionRecord,
    ResolutionStrategy,
    RuleAction,
    RuleEvalResult,
    RuleSpec,
)

__all__ = [
    "CompoundCondition",
    "ConditionOperator",
    "ConflictRecord",
    "ConflictResolutionEngine",
    "ConflictType",
    "EvalContext",
    "FieldOperator",
    "LeafCondition",
    "ResolutionRecord",
    "ResolutionStrategy",
    "RuleAction",
    "RuleEvalResult",
    "RuleEvaluator",
    "RuleSpec",
]
