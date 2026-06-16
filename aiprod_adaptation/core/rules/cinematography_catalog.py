from __future__ import annotations

SHOT_TYPES: tuple[str, ...] = (
    "extreme_close_up",
    "close_up",
    "extreme_wide",
    "wide",
    "pov",
    "two_shot",
    "insert",
    "over_shoulder",
    "medium_wide",
    "medium_close",
    "medium",
)

CAMERA_MOVEMENTS: tuple[str, ...] = (
    "static",
    "follow",
    "pan",
    "dolly_in",
    "dolly_out",
    "tilt_up",
    "tilt_down",
    "crane_up",
    "crane_down",
    "tracking",
    "handheld",
    "steadicam",
    "rack_focus",
    "whip_pan",
    "zoom_in",
    "zoom_out",
)

# Ordered rules. The first matching row wins.
SHOT_TYPE_RULES: tuple[tuple[str, tuple[str, ...]], ...] = (
    ("extreme_close_up", ("iris detail", "pupil detail", "extreme close")),
    ("close_up", ("face", "eyes", "stare", "glare", "smile", "frown", "jaw")),
    ("extreme_wide", ("panorama", "establishing vista", "vast landscape")),
    ("pov", ("point of view", "pov")),
    ("two_shot", ("two characters", "together in frame", "face each other")),
    ("insert", ("insert shot", "object detail", "hand detail")),
    ("over_shoulder", ("over the shoulder", "over-shoulder")),
    ("medium_wide", ("full body", "medium wide")),
    ("medium_close", ("chest up", "medium close")),
    ("wide", ("walk", "run", "sprint", "crosses the room", "rush")),
)

CAMERA_MOVEMENT_RULES: tuple[tuple[str, tuple[str, ...]], ...] = (
    ("whip_pan", ("whip pan", "snap pan")),
    ("rack_focus", ("rack focus", "focus shifts")),
    ("crane_up", ("crane up", "vertical reveal")),
    ("crane_down", ("crane down", "descending crane")),
    ("dolly_in", ("dolly in", "push in")),
    ("dolly_out", ("dolly out", "pull back")),
    ("zoom_in", ("zoom in",)),
    ("zoom_out", ("zoom out",)),
    ("tilt_up", ("tilt up",)),
    ("tilt_down", ("tilt down",)),
    ("steadicam", ("steadicam", "smooth walk and talk")),
    ("tracking", ("tracking shot", "parallel tracking")),
    ("handheld", ("handheld", "unstable camera")),
    ("follow", ("follow camera", "camera follows")),
    ("pan", ("camera pans", "pan across")),
)


def resolve_first_match(
    text: str,
    rules: tuple[tuple[str, tuple[str, ...]], ...],
    default: str,
) -> str:
    lowered = text.casefold()
    for value, keywords in rules:
        if any(keyword in lowered for keyword in keywords):
            return value
    return default
