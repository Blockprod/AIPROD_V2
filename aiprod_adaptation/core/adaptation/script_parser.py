from __future__ import annotations

from aiprod_adaptation.models.intermediate import VisualScene

_SCENE_PREFIXES: tuple[str, ...] = ("INT.", "EXT.")


class ScriptParser:
    def parse(self, text: str) -> list[VisualScene]:
        scenes: list[VisualScene] = []
        scene_counter = 0

        # Mutable accumulators for the current scene being built
        cur_location: str = ""
        cur_characters: list[str] = []
        cur_visual_actions: list[str] = []
        cur_dialogues: list[str] = []
        in_scene = False

        def _flush() -> None:
            if in_scene:
                scenes.append(
                    VisualScene(
                        scene_id=f"SCN_{scene_counter:03d}",
                        characters=list(cur_characters),
                        location=cur_location,
                        time_of_day=None,
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
                in_scene = True

            elif in_scene:
                # Fountain convention: character cue = all-uppercase, ≤ 4 words
                if line.isupper() and len(line.split()) <= 4:
                    if line not in cur_characters:
                        cur_characters.append(line)
                else:
                    cur_visual_actions.append(line)

        _flush()
        return scenes
