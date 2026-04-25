"""
rule_engine/models.py — DSL types for AIPROD_Cinematic's hierarchical rule system.

Priority scale (P1 = highest, P5 = lowest):
  P1  Identity & anatomy          — character wardrobe, physical signature (NEVER overridden)
  P2  Lighting                    — key direction, temperature, intensity
  P3  Spatial coherence / angle   — camera height, 180° axis continuity
  P4  Composition / depth         — rule of thirds, depth layer, headroom
  P5  Narrative intent            — beat type, pacing, emotional arc

ConflictType:
  HARD — invariant directly contradicted → resolution is mandatory
  SOFT — tension between P-levels → resolved by compromise or narrative yields
  NONE — informational only, no action required

All types are Pydantic models — fully JSON-serialisable via model.model_dump().
EvalContext is a plain dataclass (no Pydantic overhead) — passed by value during
evaluation, never mutated.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from enum import StrEnum
from typing import Any

from pydantic import BaseModel, Field

# ---------------------------------------------------------------------------
# Enumerations
# ---------------------------------------------------------------------------


class ConflictType(StrEnum):
    HARD = "HARD"   # mandatory resolution — invariant violated
    SOFT = "SOFT"   # try to resolve — tension between P-levels
    NONE = "NONE"   # no conflict — informational


class ResolutionStrategy(StrEnum):
    STRIP_AND_REPLACE   = "STRIP_AND_REPLACE"    # remove conflicting phrase, insert invariant
    DOWNGRADE_MOVEMENT  = "DOWNGRADE_MOVEMENT"   # reduce camera movement complexity one step
    ENFORCE_INVARIANT   = "ENFORCE_INVARIANT"    # append invariant fragment to prompt/directive
    NARRATIVE_YIELDS    = "NARRATIVE_YIELDS"     # narrative intent dropped; annotate only
    COMPROMISE          = "COMPROMISE"           # find a compatible middle value
    FLAG_AND_PASS       = "FLAG_AND_PASS"        # annotate conflict, shot passes unchanged
    NO_ACTION           = "NO_ACTION"            # nothing to do


class FieldOperator(StrEnum):
    EXISTS        = "exists"
    NOT_EXISTS    = "not_exists"
    EQ            = "eq"
    NEQ           = "neq"
    LT            = "lt"
    LTE           = "lte"
    GT            = "gt"
    GTE           = "gte"
    IN            = "in"
    NOT_IN        = "not_in"
    CONTAINS      = "contains"
    CONTAINS_ANY  = "contains_any"
    MATCHES_RE    = "matches_re"


class ConditionOperator(StrEnum):
    AND = "AND"
    OR  = "OR"
    NOT = "NOT"


# ---------------------------------------------------------------------------
# Condition DSL
# ---------------------------------------------------------------------------


class LeafCondition(BaseModel):
    """Single-field comparison in the rule DSL.

    field  : dot-path into EvalContext namespace, e.g. "shot.feasibility_score"
             Supported roots: shot, scene, visual_bible, ref_invariants, episode_index
    op     : comparison operator
    value  : scalar reference value (for EQ / NEQ / LT / LTE / GT / GTE / CONTAINS)
    values : list of values (for IN / NOT_IN / CONTAINS_ANY)
    """
    field: str
    op: FieldOperator
    value: Any = None
    values: list[Any] = Field(default_factory=list)


class CompoundCondition(BaseModel):
    """Boolean combination of leaf or compound conditions.

    Supports arbitrary nesting:
      AND / OR — all / any operands must be true
      NOT      — first operand is negated (operands[0])
    """
    operator: ConditionOperator
    operands: list[LeafCondition | CompoundCondition] = Field(
        default_factory=list
    )


# Required for Pydantic v2 self-referential models
CompoundCondition.model_rebuild()


# ---------------------------------------------------------------------------
# Rule action
# ---------------------------------------------------------------------------


class RuleAction(BaseModel):
    """What happens when a rule's condition matches.

    type           : "REWRITE" | "DOWNGRADE" | "ANNOTATE" | "REJECT"
    target_field   : dot-path of the field to mutate (if applicable)
    rewrite_template: optional human-readable description of the rewrite intent
    downgrade_to   : explicit target value for DOWNGRADE actions (optional — resolver
                     may compute from context if absent)
    annotation_key : key written into visual_invariants_applied for ANNOTATE
    annotation_value: value appended to annotation_key record
    """
    type: str
    target_field: str | None = None
    rewrite_template: str | None = None
    downgrade_to: str | None = None
    annotation_key: str | None = None
    annotation_value: str | None = None


# ---------------------------------------------------------------------------
# Rule specification
# ---------------------------------------------------------------------------


class RuleSpec(BaseModel):
    """
    One serialisable rule in the AIPROD Rule DSL.

    id           : globally unique, kebab-case (e.g. "SPC-01-overhead-crane-up")
    priority     : P1–P5 (1 = identity anchor, 5 = narrative intent)
    conflict_type: HARD → mandatory resolution, SOFT → best-effort, NONE → audit only
    """
    id: str
    priority: int                               # 1–5
    description: str = ""
    condition: LeafCondition | CompoundCondition
    action: RuleAction
    conflict_type: ConflictType = ConflictType.SOFT
    rewrite_template: str | None = None         # optional human-readable template string


# ---------------------------------------------------------------------------
# Conflict and resolution records (immutable audit trail)
# ---------------------------------------------------------------------------


class ConflictRecord(BaseModel):
    """Immutable record of a conflict detected between a rule and a shot."""
    rule_id: str
    conflict_type: ConflictType
    priority: int
    shot_id: str
    field_path: str                 # target_field from the triggering rule
    current_value: Any = None       # current value of the conflicting field
    invariant_value: Any = None     # reference / invariant value (if known)
    description: str = ""


class ResolutionRecord(BaseModel):
    """Immutable record of a conflict resolution action (one per conflict)."""
    conflict: ConflictRecord
    strategy: ResolutionStrategy
    original_value: Any = None
    resolved_value: Any = None
    was_modified: bool = False


class RuleEvalResult(BaseModel):
    """Result of evaluating one RuleSpec against one EvalContext."""
    rule_id: str
    matched: bool
    conflict_type: ConflictType = ConflictType.NONE
    conflict: ConflictRecord | None = None
    resolution: ResolutionRecord | None = None


# ---------------------------------------------------------------------------
# Evaluation context (local + global)
# ---------------------------------------------------------------------------


@dataclass
class EvalContext:
    """
    Stateless context window passed to RuleEvaluator.

    Combines local (shot/scene) and global (episode/season) data.
    Never mutated during evaluation — all mutations happen via
    model_copy(update=...) on the Shot and are tracked in ResolutionRecord.

    Fields
    ------
    shot          : Shot Pydantic object (aiprod_adaptation.models.schema.Shot)
    scene         : Scene Pydantic object
    visual_bible  : VisualBible instance (optional)
    ref_invariants: VisualInvariants from reference image (optional)
    episode_id    : e.g. "EP01"
    episode_index : 1-based episode number within the season (1–10)
    season_shots  : all shots compiled so far this season (for global checks)
    season_scenes : all scenes compiled so far this season
    """
    shot: Any
    scene: Any
    visual_bible: Any | None = None
    ref_invariants: Any | None = None
    episode_id: str = "EP01"
    episode_index: int = 1
    season_shots: list[Any] = field(default_factory=list)
    season_scenes: list[Any] = field(default_factory=list)
