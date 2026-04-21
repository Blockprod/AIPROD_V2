from __future__ import annotations

_SCRIPT_MARKERS: tuple[str, ...] = (
    "INT.",
    "EXT.",
    "FADE IN",
    "FADE OUT",
    "CUT TO:",
    "SMASH CUT",
    "DISSOLVE TO:",
)


class InputClassifier:
    def classify(self, text: str) -> str:  # "script" | "novel"
        for marker in _SCRIPT_MARKERS:
            if marker in text:
                return "script"
        return "novel"
