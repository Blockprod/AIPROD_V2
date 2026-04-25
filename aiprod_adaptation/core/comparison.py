from __future__ import annotations

import re
from dataclasses import dataclass

from aiprod_adaptation.models.schema import AIPRODOutput, Episode, Scene


def _first_episode(output: AIPRODOutput) -> Episode | None:
    return output.episodes[0] if output.episodes else None


def _first_action(scene: Scene | None) -> str:
    if scene is None or not scene.visual_actions:
        return "n/a"
    return scene.visual_actions[0]


def _location_preview(episode: Episode | None, limit: int = 4) -> list[str]:
    if episode is None:
        return []
    return [scene.location for scene in episode.scenes[:limit]]


def _ordered_difference(left: list[str], right: list[str], *, casefold: bool = False) -> list[str]:
    if casefold:
        right_keys = {item.casefold() for item in right}
        return [item for item in left if item.casefold() not in right_keys]
    right_keys = set(right)
    return [item for item in left if item not in right_keys]


def _scene_ids(episode: Episode | None) -> list[str]:
    if episode is None:
        return []
    return [scene.scene_id for scene in episode.scenes]


def _known_locations(episode: Episode | None) -> list[str]:
    if episode is None:
        return []
    locations: list[str] = []
    seen: set[str] = set()
    for scene in episode.scenes:
        location = scene.location.strip()
        if not location or location.casefold() == "unknown":
            continue
        key = location.casefold()
        if key in seen:
            continue
        seen.add(key)
        locations.append(location)
    return locations


def _known_location_scene_count(episode: Episode | None) -> int:
    if episode is None:
        return 0
    return sum(1 for scene in episode.scenes if scene.location.strip().casefold() != "unknown")


def _dialogue_line_count(episode: Episode | None) -> int:
    if episode is None:
        return 0
    return sum(len(scene.dialogues) for scene in episode.scenes)


def _preview_items(items: list[str], limit: int = 6) -> str:
    if not items:
        return "n/a"
    if len(items) <= limit:
        return " | ".join(items)
    visible = " | ".join(items[:limit])
    return f"{visible} | +{len(items) - limit} more"


def _tokenize(text: str) -> set[str]:
    return set(re.findall(r"[a-z0-9]+", text.casefold()))


def _jaccard_similarity(left: set[str], right: set[str]) -> float:
    if not left or not right:
        return 0.0
    return len(left & right) / len(left | right)


_MIN_ALIGNMENT_SIMILARITY = 0.1


def _scene_lookup(episode: Episode | None) -> dict[str, Scene]:
    if episode is None:
        return {}
    return {scene.scene_id: scene for scene in episode.scenes}


@dataclass(frozen=True)
class SceneDiff:
    scene_id: str
    rules_location: str
    llm_location: str
    locations_equal: bool
    rules_action_count: int
    llm_action_count: int
    rules_dialogue_count: int
    llm_dialogue_count: int
    rules_first_action: str
    llm_first_action: str
    first_actions_equal: bool

    def to_dict(self) -> dict[str, object]:
        return {
            "scene_id": self.scene_id,
            "locations": {
                "rules": self.rules_location,
                "llm": self.llm_location,
                "equal": self.locations_equal,
            },
            "action_counts": {
                "rules": self.rules_action_count,
                "llm": self.llm_action_count,
                "delta": self.llm_action_count - self.rules_action_count,
            },
            "dialogue_counts": {
                "rules": self.rules_dialogue_count,
                "llm": self.llm_dialogue_count,
                "delta": self.llm_dialogue_count - self.rules_dialogue_count,
            },
            "first_actions": {
                "rules": self.rules_first_action,
                "llm": self.llm_first_action,
                "equal": self.first_actions_equal,
            },
        }


@dataclass(frozen=True)
class AlignedSceneDiff:
    rules_scene_id: str
    llm_scene_id: str
    similarity: float
    rules_location: str
    llm_location: str
    locations_equal: bool
    rules_action_count: int
    llm_action_count: int
    rules_dialogue_count: int
    llm_dialogue_count: int
    rules_first_action: str
    llm_first_action: str
    first_actions_equal: bool

    def to_dict(self) -> dict[str, object]:
        return {
            "rules_scene_id": self.rules_scene_id,
            "llm_scene_id": self.llm_scene_id,
            "similarity": self.similarity,
            "locations": {
                "rules": self.rules_location,
                "llm": self.llm_location,
                "equal": self.locations_equal,
            },
            "action_counts": {
                "rules": self.rules_action_count,
                "llm": self.llm_action_count,
                "delta": self.llm_action_count - self.rules_action_count,
            },
            "dialogue_counts": {
                "rules": self.rules_dialogue_count,
                "llm": self.llm_dialogue_count,
                "delta": self.llm_dialogue_count - self.rules_dialogue_count,
            },
            "first_actions": {
                "rules": self.rules_first_action,
                "llm": self.llm_first_action,
                "equal": self.first_actions_equal,
            },
        }


def _scene_similarity(rules_scene: Scene, llm_scene: Scene) -> float:
    rules_location_tokens = _tokenize(rules_scene.location)
    llm_location_tokens = _tokenize(llm_scene.location)
    rules_character_tokens = {name.casefold() for name in rules_scene.characters}
    llm_character_tokens = {name.casefold() for name in llm_scene.characters}
    rules_action_tokens = _tokenize(_first_action(rules_scene))
    llm_action_tokens = _tokenize(_first_action(llm_scene))
    location_score = _jaccard_similarity(rules_location_tokens, llm_location_tokens)
    character_score = _jaccard_similarity(rules_character_tokens, llm_character_tokens)
    action_score = _jaccard_similarity(rules_action_tokens, llm_action_tokens)
    return (0.5 * location_score) + (0.3 * character_score) + (0.2 * action_score)


def _aligned_scene_diffs(
    rules_episode: Episode | None,
    llm_episode: Episode | None,
) -> list[AlignedSceneDiff]:
    if rules_episode is None or llm_episode is None:
        return []
    diffs: list[AlignedSceneDiff] = []
    next_rules_index = 0
    for llm_scene in llm_episode.scenes:
        best_match_index: int | None = None
        best_match_score = -1.0
        best_match_similarity = 0.0
        for rules_index in range(next_rules_index, len(rules_episode.scenes)):
            rules_scene = rules_episode.scenes[rules_index]
            similarity = _scene_similarity(rules_scene, llm_scene)
            locality_bonus = max(0.0, 0.05 - (0.01 * (rules_index - next_rules_index)))
            score = similarity + locality_bonus
            if score > best_match_score:
                best_match_score = score
                best_match_index = rules_index
                best_match_similarity = similarity
        if best_match_index is None:
            continue
        if best_match_similarity < _MIN_ALIGNMENT_SIMILARITY:
            continue
        rules_scene = rules_episode.scenes[best_match_index]
        diffs.append(
            AlignedSceneDiff(
                rules_scene_id=rules_scene.scene_id,
                llm_scene_id=llm_scene.scene_id,
                similarity=round(best_match_similarity, 3),
                rules_location=rules_scene.location,
                llm_location=llm_scene.location,
                locations_equal=(
                    rules_scene.location.strip().casefold()
                    == llm_scene.location.strip().casefold()
                ),
                rules_action_count=len(rules_scene.visual_actions),
                llm_action_count=len(llm_scene.visual_actions),
                rules_dialogue_count=len(rules_scene.dialogues),
                llm_dialogue_count=len(llm_scene.dialogues),
                rules_first_action=_first_action(rules_scene),
                llm_first_action=_first_action(llm_scene),
                first_actions_equal=(
                    _first_action(rules_scene).strip().casefold()
                    == _first_action(llm_scene).strip().casefold()
                ),
            )
        )
        next_rules_index = best_match_index + 1
    return diffs


def _shared_scene_diffs(
    rules_episode: Episode | None,
    llm_episode: Episode | None,
) -> list[SceneDiff]:
    rules_lookup = _scene_lookup(rules_episode)
    llm_lookup = _scene_lookup(llm_episode)
    shared_ids = [scene_id for scene_id in rules_lookup if scene_id in llm_lookup]
    diffs: list[SceneDiff] = []
    for scene_id in shared_ids:
        rules_scene = rules_lookup[scene_id]
        llm_scene = llm_lookup[scene_id]
        diffs.append(
            SceneDiff(
                scene_id=scene_id,
                rules_location=rules_scene.location,
                llm_location=llm_scene.location,
                locations_equal=(
                    rules_scene.location.strip().casefold()
                    == llm_scene.location.strip().casefold()
                ),
                rules_action_count=len(rules_scene.visual_actions),
                llm_action_count=len(llm_scene.visual_actions),
                rules_dialogue_count=len(rules_scene.dialogues),
                llm_dialogue_count=len(llm_scene.dialogues),
                rules_first_action=_first_action(rules_scene),
                llm_first_action=_first_action(llm_scene),
                first_actions_equal=(
                    _first_action(rules_scene).strip().casefold()
                    == _first_action(llm_scene).strip().casefold()
                ),
            )
        )
    return diffs


@dataclass(frozen=True)
class OutputComparison:
    title: str
    llm_adapter: str
    outputs_equal: bool
    rules_scene_count: int
    llm_scene_count: int
    rules_shot_count: int
    llm_shot_count: int
    rules_first_action: str
    llm_first_action: str
    rules_locations: list[str]
    llm_locations: list[str]
    rules_dialogue_line_count: int
    llm_dialogue_line_count: int
    rules_known_location_scene_count: int
    llm_known_location_scene_count: int
    rules_only_scene_ids: list[str]
    llm_only_scene_ids: list[str]
    rules_only_locations: list[str]
    llm_only_locations: list[str]
    shared_scene_diffs: list[SceneDiff]
    aligned_scene_diffs: list[AlignedSceneDiff]

    def to_dict(self) -> dict[str, object]:
        return {
            "title": self.title,
            "llm_adapter": self.llm_adapter,
            "outputs_equal": self.outputs_equal,
            "scene_counts": {
                "rules": self.rules_scene_count,
                "llm": self.llm_scene_count,
                "delta": self.llm_scene_count - self.rules_scene_count,
            },
            "shot_counts": {
                "rules": self.rules_shot_count,
                "llm": self.llm_shot_count,
                "delta": self.llm_shot_count - self.rules_shot_count,
            },
            "dialogue_line_counts": {
                "rules": self.rules_dialogue_line_count,
                "llm": self.llm_dialogue_line_count,
                "delta": self.llm_dialogue_line_count - self.rules_dialogue_line_count,
            },
            "known_location_scene_counts": {
                "rules": self.rules_known_location_scene_count,
                "llm": self.llm_known_location_scene_count,
                "delta": (
                    self.llm_known_location_scene_count - self.rules_known_location_scene_count
                ),
            },
            "first_actions": {
                "rules": self.rules_first_action,
                "llm": self.llm_first_action,
            },
            "location_preview": {
                "rules": self.rules_locations,
                "llm": self.llm_locations,
            },
            "scene_ids_only_in": {
                "rules": self.rules_only_scene_ids,
                "llm": self.llm_only_scene_ids,
            },
            "locations_only_in": {
                "rules": self.rules_only_locations,
                "llm": self.llm_only_locations,
            },
            "shared_scene_diffs": [diff.to_dict() for diff in self.shared_scene_diffs],
            "aligned_scene_diffs": [diff.to_dict() for diff in self.aligned_scene_diffs],
        }

    def to_summary_str(self) -> str:
        rules_locations = _preview_items(self.rules_locations)
        llm_locations = _preview_items(self.llm_locations)
        return "\n".join(
            [
                f"Comparison for '{self.title}'",
                f"LLM adapter: {self.llm_adapter}",
                f"Outputs identical: {'yes' if self.outputs_equal else 'no'}",
                (
                    "Scene counts: "
                    f"rules={self.rules_scene_count}, llm={self.llm_scene_count}, "
                    f"delta={self.llm_scene_count - self.rules_scene_count}"
                ),
                (
                    "Shot counts: "
                    f"rules={self.rules_shot_count}, llm={self.llm_shot_count}, "
                    f"delta={self.llm_shot_count - self.rules_shot_count}"
                ),
                (
                    "Dialogue lines: "
                    f"rules={self.rules_dialogue_line_count}, "
                    f"llm={self.llm_dialogue_line_count}, "
                    f"delta={self.llm_dialogue_line_count - self.rules_dialogue_line_count}"
                ),
                (
                    "Known-location scenes: "
                    f"rules={self.rules_known_location_scene_count}, "
                    f"llm={self.llm_known_location_scene_count}, "
                    "delta="
                    f"{self.llm_known_location_scene_count - self.rules_known_location_scene_count}"
                ),
                f"First rules action: {self.rules_first_action}",
                f"First LLM action: {self.llm_first_action}",
                f"Rules locations: {rules_locations}",
                f"LLM locations: {llm_locations}",
                f"Scene IDs only in rules: {_preview_items(self.rules_only_scene_ids)}",
                f"Scene IDs only in LLM: {_preview_items(self.llm_only_scene_ids)}",
                f"Locations only in rules: {_preview_items(self.rules_only_locations)}",
                f"Locations only in LLM: {_preview_items(self.llm_only_locations)}",
            ]
        )


def compare_outputs(
    rules_output: AIPRODOutput,
    llm_output: AIPRODOutput,
    llm_adapter: str,
) -> OutputComparison:
    rules_episode = _first_episode(rules_output)
    llm_episode = _first_episode(llm_output)
    rules_first_scene = rules_episode.scenes[0] if rules_episode and rules_episode.scenes else None
    llm_first_scene = llm_episode.scenes[0] if llm_episode and llm_episode.scenes else None
    rules_scene_ids = _scene_ids(rules_episode)
    llm_scene_ids = _scene_ids(llm_episode)
    rules_known_locations = _known_locations(rules_episode)
    llm_known_locations = _known_locations(llm_episode)
    shared_scene_diffs = _shared_scene_diffs(rules_episode, llm_episode)
    aligned_scene_diffs = _aligned_scene_diffs(rules_episode, llm_episode)
    return OutputComparison(
        title=rules_output.title,
        llm_adapter=llm_adapter,
        outputs_equal=rules_output.model_dump() == llm_output.model_dump(),
        rules_scene_count=len(rules_episode.scenes) if rules_episode else 0,
        llm_scene_count=len(llm_episode.scenes) if llm_episode else 0,
        rules_shot_count=len(rules_episode.shots) if rules_episode else 0,
        llm_shot_count=len(llm_episode.shots) if llm_episode else 0,
        rules_first_action=_first_action(rules_first_scene),
        llm_first_action=_first_action(llm_first_scene),
        rules_locations=_location_preview(rules_episode),
        llm_locations=_location_preview(llm_episode),
        rules_dialogue_line_count=_dialogue_line_count(rules_episode),
        llm_dialogue_line_count=_dialogue_line_count(llm_episode),
        rules_known_location_scene_count=_known_location_scene_count(rules_episode),
        llm_known_location_scene_count=_known_location_scene_count(llm_episode),
        rules_only_scene_ids=_ordered_difference(rules_scene_ids, llm_scene_ids),
        llm_only_scene_ids=_ordered_difference(llm_scene_ids, rules_scene_ids),
        rules_only_locations=_ordered_difference(
            rules_known_locations,
            llm_known_locations,
            casefold=True,
        ),
        llm_only_locations=_ordered_difference(
            llm_known_locations,
            rules_known_locations,
            casefold=True,
        ),
        shared_scene_diffs=shared_scene_diffs,
        aligned_scene_diffs=aligned_scene_diffs,
    )
