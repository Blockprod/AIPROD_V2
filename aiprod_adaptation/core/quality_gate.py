"""
Quality Gate — post-compile validation for AIPROD_Cinematic v3.0.

Runs after Pass 4 (compile_episode) and validates the complete AIPRODOutput
against cinematographic and structural quality criteria.

The gate produces a QualityReport containing:
  - errors   : list of blocking violations (must be fixed before production use)
  - warnings : list of non-blocking issues (should be reviewed)

Design principles:
  - Pure function: QualityGate.check() has no side effects.
  - All validation rules are deterministic and rule-based.
  - Optional VisualBible integration: if provided, shot ratios and character
    presence are validated against series targets.
  - Backward compatible: runs on v2 IR (no v3.0 fields required).
"""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import TYPE_CHECKING

from aiprod_adaptation.models.schema import AIPRODOutput, Episode, Shot

if TYPE_CHECKING:
    from aiprod_adaptation.core.visual_bible import VisualBible

# ---------------------------------------------------------------------------
# Shot ratio defaults (used when no VisualBible is provided)
# ---------------------------------------------------------------------------

_DEFAULT_SHOT_RATIO_TARGETS: dict[str, float] = {
    "wide": 0.20,
    "medium": 0.45,
    "close_up": 0.20,
    "other": 0.15,
}
_SHOT_RATIO_TOLERANCE: float = 0.15  # ±15 pp before a warning is raised

# ---------------------------------------------------------------------------
# Completeness thresholds
# ---------------------------------------------------------------------------

_MIN_SHOTS_PER_SCENE: int = 1
_MAX_SHOTS_PER_SCENE: int = 20  # cap for sanity check
_MIN_SCENES_PER_EPISODE: int = 1
_MAX_DURATION_SEC: int = 8
_MIN_DURATION_SEC: int = 3


# ---------------------------------------------------------------------------
# Data structures
# ---------------------------------------------------------------------------

@dataclass
class QualityIssue:
    code: str          # machine-readable identifier (e.g. "MISSING_PROMPT")
    level: str         # "error" | "warning"
    episode_id: str
    scene_id: str
    shot_id: str
    message: str


@dataclass
class QualityReport:
    errors: list[QualityIssue] = field(default_factory=list)
    warnings: list[QualityIssue] = field(default_factory=list)

    @property
    def is_clean(self) -> bool:
        return len(self.errors) == 0

    def summary(self) -> str:
        lines = [
            f"Quality Gate: {len(self.errors)} error(s), {len(self.warnings)} warning(s)."
        ]
        for issue in self.errors:
            lines.append(f"  [ERROR] [{issue.episode_id}:{issue.scene_id}:{issue.shot_id}] "
                         f"({issue.code}) {issue.message}")
        for issue in self.warnings:
            lines.append(f"  [WARN]  [{issue.episode_id}:{issue.scene_id}:{issue.shot_id}] "
                         f"({issue.code}) {issue.message}")
        return "\n".join(lines)


# ---------------------------------------------------------------------------
# QualityGate
# ---------------------------------------------------------------------------

class QualityGate:
    """
    Validates a compiled AIPRODOutput.

    Usage
    -----
    gate = QualityGate()
    report = gate.check(output)
    report = gate.check(output, visual_bible=bible)
    if not report.is_clean:
        raise RuntimeError(report.summary())
    """

    def check(
        self,
        output: AIPRODOutput,
        visual_bible: "VisualBible | None" = None,
    ) -> QualityReport:
        report = QualityReport()
        for episode in output.episodes:
            self._check_episode(episode, report, visual_bible)
        return report

    # ------------------------------------------------------------------
    # Episode-level checks
    # ------------------------------------------------------------------

    def _check_episode(
        self,
        episode: Episode,
        report: QualityReport,
        visual_bible: "VisualBible | None",
    ) -> None:
        ep_id = episode.episode_id

        if len(episode.scenes) < _MIN_SCENES_PER_EPISODE:
            report.errors.append(QualityIssue(
                code="EMPTY_EPISODE",
                level="error",
                episode_id=ep_id,
                scene_id="",
                shot_id="",
                message=f"Episode '{ep_id}' has no scenes.",
            ))
            return

        # Shot-ratio check across the full episode
        self._check_shot_ratio(episode, report, visual_bible)

        # Character introduction order
        self._check_character_introduction(episode, report)

        for scene in episode.scenes:
            scene_shots = [s for s in episode.shots if s.scene_id == scene.scene_id]
            self._check_scene_completeness(ep_id, scene.scene_id, scene_shots, report)

    # ------------------------------------------------------------------
    # Scene-level completeness checks
    # ------------------------------------------------------------------

    def _check_scene_completeness(
        self,
        ep_id: str,
        scene_id: str,
        shots: list[Shot],
        report: QualityReport,
    ) -> None:
        if len(shots) < _MIN_SHOTS_PER_SCENE:
            report.errors.append(QualityIssue(
                code="EMPTY_SCENE",
                level="error",
                episode_id=ep_id,
                scene_id=scene_id,
                shot_id="",
                message=f"Scene '{scene_id}' has no shots.",
            ))
            return

        if len(shots) > _MAX_SHOTS_PER_SCENE:
            report.warnings.append(QualityIssue(
                code="SCENE_SHOT_COUNT_HIGH",
                level="warning",
                episode_id=ep_id,
                scene_id=scene_id,
                shot_id="",
                message=(
                    f"Scene '{scene_id}' has {len(shots)} shots "
                    f"(>{_MAX_SHOTS_PER_SCENE}). Consider splitting."
                ),
            ))

        for shot in shots:
            self._check_shot(ep_id, scene_id, shot, report)

    def _check_shot(
        self,
        ep_id: str,
        scene_id: str,
        shot: Shot,
        report: QualityReport,
    ) -> None:
        # Prompt must be non-empty
        if not shot.prompt or not shot.prompt.strip():
            report.errors.append(QualityIssue(
                code="MISSING_PROMPT",
                level="error",
                episode_id=ep_id,
                scene_id=scene_id,
                shot_id=shot.shot_id,
                message=f"Shot '{shot.shot_id}' has an empty prompt.",
            ))

        # Duration bounds (already enforced by Pydantic, but belt-and-suspenders)
        if not (_MIN_DURATION_SEC <= shot.duration_sec <= _MAX_DURATION_SEC):
            report.errors.append(QualityIssue(
                code="INVALID_DURATION",
                level="error",
                episode_id=ep_id,
                scene_id=scene_id,
                shot_id=shot.shot_id,
                message=(
                    f"Shot '{shot.shot_id}' duration_sec={shot.duration_sec} "
                    f"out of bounds [{_MIN_DURATION_SEC}, {_MAX_DURATION_SEC}]."
                ),
            ))

        # extreme_close_up without an emotion: warn
        if shot.shot_type == "extreme_close_up" and not shot.emotion:
            report.warnings.append(QualityIssue(
                code="ECU_NO_EMOTION",
                level="warning",
                episode_id=ep_id,
                scene_id=scene_id,
                shot_id=shot.shot_id,
                message=(
                    f"Shot '{shot.shot_id}' is extreme_close_up but has no emotion set. "
                    "Extreme close-ups without emotional motivation are rarely justified."
                ),
            ))

    # ------------------------------------------------------------------
    # Shot ratio check
    # ------------------------------------------------------------------

    def _check_shot_ratio(
        self,
        episode: Episode,
        report: QualityReport,
        visual_bible: "VisualBible | None",
    ) -> None:
        ep_id = episode.episode_id
        total = len(episode.shots)
        if total == 0:
            return

        # Determine targets
        if visual_bible is not None:
            targets = dict(visual_bible.series_style["default_shot_ratio"])
        else:
            targets = dict(_DEFAULT_SHOT_RATIO_TARGETS)

        # Count shot types, grouping non-standard into "other"
        standard = {"wide", "medium", "close_up"}
        counts: dict[str, int] = {"wide": 0, "medium": 0, "close_up": 0, "other": 0}
        for shot in episode.shots:
            if shot.shot_type in standard:
                counts[shot.shot_type] += 1
            else:
                counts["other"] += 1

        for category, target in targets.items():
            actual = counts.get(category, 0) / total
            deviation = abs(actual - target)
            if deviation > _SHOT_RATIO_TOLERANCE:
                report.warnings.append(QualityIssue(
                    code="SHOT_RATIO_DEVIATION",
                    level="warning",
                    episode_id=ep_id,
                    scene_id="",
                    shot_id="",
                    message=(
                        f"Episode '{ep_id}' shot ratio for '{category}': "
                        f"actual={actual:.0%}, target={target:.0%}, "
                        f"deviation={deviation:.0%} (tolerance={_SHOT_RATIO_TOLERANCE:.0%})."
                    ),
                ))

    # ------------------------------------------------------------------
    # Character introduction order check
    # ------------------------------------------------------------------

    def _check_character_introduction(
        self,
        episode: Episode,
        report: QualityReport,
    ) -> None:
        """
        Verify that every character referenced in shots appears in at least one
        scene before (or in the same scene as) their first shot.
        This catches copy-paste errors where a character is in a shot but was
        never added to the scene's character list.
        """
        ep_id = episode.episode_id
        # Build set of characters declared per scene
        chars_per_scene: dict[str, set[str]] = {
            scene.scene_id: set(c.strip() for c in scene.characters)
            for scene in episode.scenes
        }

        for shot in episode.shots:
            if shot.action is None:
                continue
            subject_id = shot.action.subject_id
            if subject_id in {"unknown_subject", "unknown", ""}:
                continue
            declared = chars_per_scene.get(shot.scene_id, set())
            # subject_id is a slug (lower-case, underscores) — normalise declared names
            declared_slugs = {
                c.lower().replace(" ", "_").replace("-", "_")
                for c in declared
            }
            if subject_id not in declared_slugs and declared:
                report.warnings.append(QualityIssue(
                    code="UNDECLARED_SUBJECT",
                    level="warning",
                    episode_id=ep_id,
                    scene_id=shot.scene_id,
                    shot_id=shot.shot_id,
                    message=(
                        f"Shot '{shot.shot_id}': subject '{subject_id}' "
                        f"not in scene character list {sorted(declared_slugs)}."
                    ),
                ))
