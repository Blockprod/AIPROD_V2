"""
runway_prompt_formatter.py — Converts Shot narrative prompts to Runway i2v motion prompts.

Runway image-to-video is optimised for camera-motion instructions, not narrative
descriptions.  This module reformats shot.prompt into the official Runway structure:

    The camera [motion] as the subject [action].  [anti-cut clause]

Rules applied:
    PM-01  camera_movement → prefixed motion instruction
    PM-02  shot.action.modifiers ≥ 2 AND duration_sec ≥ 6 → inject timestamps
    PM-03  duration_sec ≥ 5 AND beat_type != "transition" → append anti-cut clause
"""

from __future__ import annotations

from aiprod_adaptation.models.schema import Shot

_CAMERA_MOTION_MAP: dict[str, str] = {
    "static":     "The locked-off camera remains perfectly still. Minimal subject motion only.",
    "dolly_in":   "The camera slowly dollies in",
    "dolly_out":  "The camera slowly dollies out",
    "tracking":   "A tracking shot follows the subject",
    "pan":        "The camera pans",
    "tilt_up":    "The camera tilts upward",
    "tilt_down":  "The camera tilts downward",
    "crane_up":   "A crane shot moves smoothly upward",
    "crane_down": "A crane shot moves smoothly downward",
    "handheld":   "Handheld camera. Natural camera shake.",
    "steadicam":  "Smooth steadicam follows the subject",
    "whip_pan":   "Whip pan",
    "rack_focus": "Rack focus",
    "follow":     "The camera follows the subject",
}

_ANTI_CUT = "Continuous, seamless shot."


def _inject_timestamps(base: str, shot: Shot) -> str:
    """
    Distribute shot.action.modifiers as Runway timestamps over shot.duration_sec.

    Only applied when ≥ 2 modifiers exist; replaces the plain base string.
    """
    if shot.action is None or len(shot.action.modifiers) < 2:
        return base
    mid = max(3, shot.duration_sec * 2 // 3)
    ts_parts = [
        f"[00:01] {shot.action.modifiers[0]}.",
        f"[00:{mid:02d}] {shot.action.modifiers[1]}.",
    ]
    return " ".join(ts_parts)


def format_runway_prompt(shot: Shot) -> str:
    """
    Convert a Shot's narrative prompt to a Runway i2v motion prompt.

    PM-01: Prefix with camera motion instruction.
    PM-02: Inject timestamps for long shots with multiple modifiers.
    PM-03: Append anti-cut clause for non-transition shots >= 5s.
    """
    motion = _CAMERA_MOTION_MAP.get(shot.camera_movement, "The camera moves")

    # Static has its own self-contained sentence; don't double-append "as the subject"
    if shot.camera_movement == "static":
        base = f"{motion} {shot.prompt}"
    else:
        base = f"{motion} as the subject {shot.prompt}"

    if shot.action is not None and shot.duration_sec >= 6:
        base = _inject_timestamps(base, shot)

    beat = shot.metadata.get("beat_type", "")
    if shot.duration_sec >= 5 and beat != "transition":
        base = base.rstrip() + " " + _ANTI_CUT

    return base
