from __future__ import annotations

from aiprod_adaptation.models.intermediate import VisualScene

_SCENE_PREFIXES: tuple[str, ...] = ("INT.", "EXT.")
_DIRECTION_LINES: frozenset[str] = frozenset(
    {
        "WIDE SHOT",
        "MEDIUM SHOT",
        "CLOSE ON",
        "CLOSE UP",
        "TRACKING SHOT",
        "INSERT SHOT",
        "OVER THE SHOULDER",
        "CUT TO:",
        "SMASH CUT TO:",
        "INTERCUT WITH:",
    }
)
_DIRECTION_PREFIXES: tuple[str, ...] = (
    "WIDE SHOT",
    "MEDIUM SHOT",
    "CLOSE ON",
    "CLOSE UP",
    "TRACKING SHOT",
    "INSERT SHOT",
    "OVER THE SHOULDER",
    "CUT TO:",
    "SMASH CUT TO:",
    "INTERCUT WITH:",
)


def _is_direction_line(line: str) -> bool:
    normalized = line.strip()
    if normalized in _DIRECTION_LINES or normalized.rstrip(":") in _DIRECTION_LINES:
        return True
    if normalized.isupper() and any(marker in normalized for marker in {",", ":"}):
        return True
    return normalized.startswith(_DIRECTION_PREFIXES)


def _scene_time_of_day(scene_heading: str) -> str | None:
    lowered = scene_heading.casefold()
    for token in ("dawn", "day", "dusk", "night"):
        if token in lowered:
            return token
    if scene_heading.startswith("INT."):
        return "interior"
    return None


def _is_character_cue(line: str) -> bool:
    normalized = line.strip()
    if not normalized.isupper():
        return False
    if len(normalized.split()) > 4:
        return False
    # Screenplay ambience notes like "LOW LIGHT, HANDHELD FEEL" should not open dialogue mode.
    if any(marker in normalized for marker in {",", ":", "."}):
        return False
    return True


class ScriptParser:
    def parse(self, text: str) -> list[VisualScene]:
        scenes: list[VisualScene] = []
        scene_counter = 0

        # Mutable accumulators for the current scene being built
        cur_location: str = ""
        cur_characters: list[str] = []
        cur_visual_actions: list[str] = []
        cur_dialogues: list[str] = []
        pending_character: str | None = None
        in_scene = False

        def _flush() -> None:
            if in_scene:
                time_of_day = _scene_time_of_day(cur_location)
                scenes.append(
                    VisualScene(
                        scene_id=f"SCN_{scene_counter:03d}",
                        characters=list(cur_characters),
                        location=cur_location,
                        time_of_day=time_of_day,
                        time_of_day_visual=time_of_day,
                        visual_actions=list(cur_visual_actions),
                        dialogues=list(cur_dialogues),
                        emotion="neutral",
                    )
                )

        for raw_line in text.splitlines():
            line = raw_line.strip()
            if not line:
                continue

            if line.startswith(_SCENE_PREFIXES):
                _flush()
                scene_counter += 1
                cur_location = line
                cur_characters = []
                cur_visual_actions = []
                cur_dialogues = []
                pending_character = None
                in_scene = True

            elif in_scene:
                if _is_direction_line(line):
                    pending_character = None
                    continue
                # Fountain convention: character cue = all-uppercase, ≤ 4 words
                if _is_character_cue(line):
                    if line not in cur_characters:
                        cur_characters.append(line)
                    pending_character = line
                elif pending_character is not None:
                    cur_dialogues.append(line)
                    pending_character = None
                else:
                    cur_visual_actions.append(line)

        _flush()
        return scenes
