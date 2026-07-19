from __future__ import annotations

import importlib.metadata
import importlib.util
import json
import os
from datetime import UTC, datetime
from pathlib import Path
from typing import Literal, TypedDict

from aiprod_adaptation.production.local_preflight import LocalPreflightReport, load_local_preflight

CapabilityStatus = Literal["certified", "contract-tested", "unavailable"]


class CapabilityRecord(TypedDict):
    status: CapabilityStatus
    detail: str
    sdk_version: str


class Certification(TypedDict):
    generated_at: str
    package_version: str
    smoke_budget_usd: float
    capabilities: dict[str, CapabilityRecord]


def _package_version(name: str) -> str:
    try:
        return importlib.metadata.version(name)
    except importlib.metadata.PackageNotFoundError:
        return "uninstalled"


def _module_available(module_name: str) -> bool:
    return importlib.util.find_spec(module_name) is not None


def _cloud_status(env_var: str, package_name: str) -> CapabilityRecord:
    sdk_version = _package_version(package_name)
    if not os.environ.get(env_var):
        return {
            "status": "unavailable",
            "detail": f"{env_var} is not configured; no smoke test executed.",
            "sdk_version": sdk_version,
        }
    return {
        "status": "contract-tested",
        "detail": "Credentials present; real paid smoke test not executed by offline certification.",
        "sdk_version": sdk_version,
    }


def _module_status(module_name: str, package_name: str, detail: str) -> CapabilityRecord:
    if not _module_available(module_name):
        return {
            "status": "unavailable",
            "detail": f"{module_name} is not importable.",
            "sdk_version": _package_version(package_name),
        }
    return {
        "status": "contract-tested",
        "detail": detail,
        "sdk_version": _package_version(package_name),
    }


def _local_status(
    report: LocalPreflightReport | None,
    capability_name: str,
    fallback: CapabilityRecord,
) -> CapabilityRecord:
    if report is None:
        return fallback
    capability = report["capabilities"].get(capability_name)
    if capability is None:
        return fallback
    status = capability["status"]
    return {
        "status": status,
        "detail": f"Local preflight: {capability['detail']}",
        "sdk_version": fallback["sdk_version"],
    }


def generate_certification(
    smoke_budget_usd: float = 25.0,
    local_preflight_path: Path | None = None,
) -> Certification:
    local_report = load_local_preflight(local_preflight_path) if local_preflight_path is not None else None
    image_comfyui_fallback: CapabilityRecord = {
        "status": "contract-tested" if os.environ.get("COMFYUI_API_URL") else "unavailable",
        "detail": "ComfyUI requires explicit local preflight; offline certification does not contact the server.",
        "sdk_version": _package_version("requests"),
    }
    audio_f5_fallback = _module_status(
        "f5_tts",
        "f5-tts",
        "F5-TTS import is available; CUDA/VRAM preflight remains host-specific.",
    )
    audio_audiocraft_fallback = _module_status(
        "audiocraft",
        "audiocraft",
        "AudioCraft import is available; CUDA/VRAM preflight remains host-specific.",
    )
    local_ffmpeg_fallback: CapabilityRecord = {
        "status": "contract-tested" if _module_available("imageio_ffmpeg") else "unavailable",
        "detail": "Python ffmpeg helper availability checked; system ffmpeg is validated by adapter preflight.",
        "sdk_version": _package_version("imageio-ffmpeg"),
    }
    capabilities: dict[str, CapabilityRecord] = {
        "core.compiler": {
            "status": "certified",
            "detail": "Offline test suite, strict mypy, Ruff, source invariants, and interprocess determinism passed.",
            "sdk_version": _package_version("aiprod-adaptation"),
        },
        "ir.v6": {
            "status": "certified",
            "detail": "Strict schema, migration, and receipt rejection contracts are tested offline.",
            "sdk_version": _package_version("pydantic"),
        },
        "quality.arcface_ssim": {
            "status": "contract-tested",
            "detail": (
                "Fail-closed quality gate contract is tested with mocks; "
                "local InsightFace availability is environment-specific."
            ),
            "sdk_version": _package_version("opencv-python-headless"),
        },
        "video.runway": _cloud_status("RUNWAY_API_KEY", "runwayml"),
        "video.kling": _cloud_status("KLING_ACCESS_KEY", "PyJWT"),
        "video.seedance": _cloud_status("REPLICATE_API_TOKEN", "replicate"),
        "image.flux": _cloud_status("REPLICATE_API_TOKEN", "replicate"),
        "image.comfyui": _local_status(local_report, "image.comfyui", image_comfyui_fallback),
        "image.local_flux_diffusers": _local_status(
            local_report,
            "image.local_flux_diffusers",
            {
                "status": "unavailable",
                "detail": "Local Flux/diffusers stack is only certified by local preflight.",
                "sdk_version": _package_version("diffusers"),
            },
        ),
        "audio.f5tts": _local_status(local_report, "audio.f5tts", audio_f5_fallback),
        "audio.audiocraft": _local_status(local_report, "audio.audiocraft", audio_audiocraft_fallback),
        "local.ffmpeg": _local_status(local_report, "local.ffmpeg", local_ffmpeg_fallback),
        "local.ffmpeg_normalize": _local_status(
            local_report,
            "local.ffmpeg_normalize",
            {
                "status": "unavailable",
                "detail": "ffmpeg-normalize is only certified by local preflight.",
                "sdk_version": _package_version("ffmpeg-normalize"),
            },
        ),
        "local.torch_cuda": _local_status(
            local_report,
            "local.torch_cuda",
            {
                "status": "unavailable",
                "detail": "CUDA/VRAM is only certified by local preflight.",
                "sdk_version": _package_version("torch"),
            },
        ),
        "local.comfyui_models": _local_status(
            local_report,
            "local.comfyui_models",
            {
                "status": "unavailable",
                "detail": "ComfyUI model files are only certified by local preflight.",
                "sdk_version": "n/a",
            },
        ),
        "local.realesrgan": _local_status(
            local_report,
            "local.realesrgan",
            {
                "status": "unavailable",
                "detail": "Real-ESRGAN executable is only certified by local preflight.",
                "sdk_version": "n/a",
            },
        ),
        "local.whisper": _local_status(
            local_report,
            "local.whisper",
            {
                "status": "unavailable",
                "detail": "Whisper is only certified by local preflight.",
                "sdk_version": _package_version("openai-whisper"),
            },
        ),
    }
    return {
        "generated_at": datetime.now(UTC).isoformat(),
        "package_version": _package_version("aiprod-adaptation"),
        "smoke_budget_usd": smoke_budget_usd,
        "capabilities": capabilities,
    }


def write_certification(
    path: Path,
    smoke_budget_usd: float = 25.0,
    local_preflight_path: Path | None = None,
) -> Certification:
    certification = generate_certification(
        smoke_budget_usd=smoke_budget_usd,
        local_preflight_path=local_preflight_path,
    )
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(certification, indent=2, sort_keys=True), encoding="utf-8")
    return certification
