# production/dashboard.py
from __future__ import annotations
import json
from pathlib import Path

_DIR = Path(__file__).resolve().parent


def _load(name: str) -> dict:
    return json.loads((_DIR / name).read_text(encoding="utf-8"))


def load_scene(scene_id: str) -> dict:
    data = _load("dashboard.json")
    if scene_id not in data:
        raise KeyError(f"Scene '{scene_id}' not found in dashboard.json")
    scene = data[scene_id]
    scene["location"] = load_location(scene["location_key"])
    return scene


def load_all_scenes() -> dict:
    dash = _load("dashboard.json")
    locs = _load("locations.json")
    for sid, scene in dash.items():
        scene["location"] = locs[scene["location_key"]]
    return dash


def load_all_characters() -> dict:
    return _load("characters.json")


def load_character(char_id: str) -> dict:
    data = _load("characters.json")
    if char_id not in data:
        raise KeyError(f"Character '{char_id}' not found in characters.json")
    return data[char_id]


def load_location(location_key: str) -> dict:
    data = _load("locations.json")
    if location_key not in data:
        raise KeyError(f"Location '{location_key}' not found in locations.json")
    return data[location_key]


def load_storyboard() -> list[dict]:
    return _load("storyboard.json")["shots"]


def load_shot_brief(shot_id: str) -> dict:
    shots = {s["shot_id"]: s for s in load_storyboard()}
    if shot_id not in shots:
        raise KeyError(f"Shot '{shot_id}' not found in storyboard.json")
    return shots[shot_id]


def update_master_plate_path(scene_id: str, path: str) -> None:
    data = _load("dashboard.json")
    data[scene_id]["master_plate_path"] = path
    (_DIR / "dashboard.json").write_text(
        json.dumps(data, indent=2, ensure_ascii=False), encoding="utf-8"
    )


def update_character_ref(char_id: str, path: str) -> None:
    data = _load("characters.json")
    data[char_id]["ref_image"] = path
    (_DIR / "characters.json").write_text(
        json.dumps(data, indent=2, ensure_ascii=False), encoding="utf-8"
    )
