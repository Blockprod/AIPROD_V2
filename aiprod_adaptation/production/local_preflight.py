from __future__ import annotations

import importlib.metadata
import importlib.util
import json
import os
import platform
import shutil
import sys
import urllib.error
import urllib.request
from datetime import UTC, datetime
from pathlib import Path
from typing import Literal, TypedDict, cast

CapabilityStatus = Literal["certified", "contract-tested", "unavailable"]
EvidenceValue = str | int | float | bool | None | list[str]


class LocalCapability(TypedDict):
    status: CapabilityStatus
    detail: str
    evidence: dict[str, EvidenceValue]


class LocalPreflightReport(TypedDict):
    generated_at: str
    ready: bool
    platform: dict[str, str]
    capabilities: dict[str, LocalCapability]


_PIPELINE_COMFYUI_NODE_CLASSES: tuple[str, ...] = (
    "CheckpointLoaderSimple",
    "CLIPTextEncode",
    "LoadImage",
    "ControlNetLoader",
    "ControlNetApplyAdvanced",
    "CLIPVisionLoader",
    "IPAdapterModelLoader",
    "IPAdapter",
    "EmptyLatentImage",
    "KSampler",
    "VAEDecode",
    "SaveImage",
)
_FLUX_COMFYUI_NODE_CLASSES: tuple[str, ...] = (
    "UNETLoader",
    "DualCLIPLoader",
    "VAELoader",
    "CLIPTextEncode",
    "LoadImageFromURL",
    "FluxIPAdapterLoader",
    "IPAdapterFlux",
    "KSampler",
    "EmptySD3LatentImage",
    "SaveImage",
    "VAEDecode",
)
_COMFYUI_MODEL_FILES: tuple[str, ...] = (
    "models/checkpoints/v1-5-pruned-emaonly.safetensors",
    "models/controlnet/control_v11p_sd15_normalbae.safetensors",
    "models/ipadapter/ip-adapter-plus_sd15.safetensors",
    "models/clip_vision/CLIP-ViT-H-14-laion2B-s32B-b79K.safetensors",
    "models/diffusion_models/flux1-dev.safetensors",
    "models/clip/clip_l.safetensors",
    "models/clip/t5xxl_fp8_e4m3fn.safetensors",
    "models/vae/ae.safetensors",
    "models/ipadapter/flux-ip-adapter.safetensors",
)
_REQUIRED_READY_CAPABILITIES: tuple[str, ...] = (
    "local.python",
    "local.ffmpeg",
    "local.torch_cuda",
    "image.comfyui",
    "local.comfyui_models",
    "image.local_flux_diffusers",
    "audio.f5tts",
    "audio.audiocraft",
    "local.realesrgan",
    "local.whisper",
    "local.ffmpeg_normalize",
)


def generate_local_preflight(
    *,
    comfyui_url: str | None = None,
    comfyui_root: Path | None = None,
    min_vram_gib: float = 12.0,
    timeout_sec: float = 2.0,
    skip_comfyui: bool = False,
) -> LocalPreflightReport:
    url = (comfyui_url or os.environ.get("COMFYUI_API_URL") or "http://localhost:8188").rstrip("/")
    capabilities: dict[str, LocalCapability] = {
        "local.python": _python_capability(),
        "local.ffmpeg": _command_capability("ffmpeg"),
        "local.ffmpeg_normalize": _command_capability("ffmpeg-normalize"),
        "local.realesrgan": _any_command_capability(
            ("realesrgan-ncnn-vulkan", "realesrgan-ncnn-vulkan.exe", "realesrgan")
        ),
        "local.whisper": _any_module_capability(
            (
                ("whisper", "openai-whisper"),
                ("faster_whisper", "faster-whisper"),
            )
        ),
        "local.torch_cuda": _torch_cuda_capability(min_vram_gib=min_vram_gib),
        "image.comfyui": (
            _skipped_capability("ComfyUI HTTP check skipped by caller.")
            if skip_comfyui
            else _comfyui_capability(url, timeout_sec=timeout_sec)
        ),
        "local.comfyui_models": _comfyui_model_capability(comfyui_root),
        "image.local_flux_diffusers": _all_modules_capability(
            (
                ("torch", "torch"),
                ("diffusers", "diffusers"),
                ("transformers", "transformers"),
                ("accelerate", "accelerate"),
            )
        ),
        "audio.f5tts": _all_modules_capability(
            (
                ("f5_tts", "f5-tts"),
                ("soundfile", "soundfile"),
            )
        ),
        "audio.audiocraft": _all_modules_capability(
            (
                ("audiocraft", "audiocraft"),
                ("torchaudio", "torchaudio"),
            )
        ),
    }
    ready = all(capabilities[name]["status"] == "certified" for name in _REQUIRED_READY_CAPABILITIES)
    return {
        "generated_at": datetime.now(UTC).isoformat(),
        "ready": ready,
        "platform": {
            "python": sys.version.split()[0],
            "system": platform.system(),
            "release": platform.release(),
            "machine": platform.machine(),
        },
        "capabilities": capabilities,
    }


def write_local_preflight(
    path: Path,
    *,
    comfyui_url: str | None = None,
    comfyui_root: Path | None = None,
    min_vram_gib: float = 12.0,
    timeout_sec: float = 2.0,
    skip_comfyui: bool = False,
) -> LocalPreflightReport:
    report = generate_local_preflight(
        comfyui_url=comfyui_url,
        comfyui_root=comfyui_root,
        min_vram_gib=min_vram_gib,
        timeout_sec=timeout_sec,
        skip_comfyui=skip_comfyui,
    )
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(report, indent=2, sort_keys=True), encoding="utf-8")
    return report


def load_local_preflight(path: Path) -> LocalPreflightReport:
    payload = json.loads(path.read_text(encoding="utf-8"))
    if not isinstance(payload, dict):
        raise ValueError("Local preflight report must be a JSON object.")
    if not isinstance(payload.get("capabilities"), dict):
        raise ValueError("Local preflight report has no capabilities object.")
    return cast(LocalPreflightReport, payload)


def _python_capability() -> LocalCapability:
    version = sys.version_info
    certified = version.major == 3 and version.minor >= 11
    return {
        "status": "certified" if certified else "unavailable",
        "detail": "Python runtime is compatible." if certified else "Python 3.11+ is required.",
        "evidence": {"version": sys.version.split()[0]},
    }


def _package_version(package_name: str) -> str:
    try:
        return importlib.metadata.version(package_name)
    except importlib.metadata.PackageNotFoundError:
        return "uninstalled"


def _module_available(module_name: str) -> bool:
    return importlib.util.find_spec(module_name) is not None


def _module_capability(module_name: str, package_name: str) -> LocalCapability:
    available = _module_available(module_name)
    version = _package_version(package_name)
    return {
        "status": "certified" if available else "unavailable",
        "detail": f"{module_name} is importable." if available else f"{module_name} is not importable.",
        "evidence": {"module": module_name, "package": package_name, "version": version},
    }


def _all_modules_capability(modules: tuple[tuple[str, str], ...]) -> LocalCapability:
    missing = [module_name for module_name, _ in modules if not _module_available(module_name)]
    versions = [f"{package_name}={_package_version(package_name)}" for _, package_name in modules]
    return {
        "status": "certified" if not missing else "unavailable",
        "detail": "All required Python modules are importable." if not missing else f"Missing modules: {missing}",
        "evidence": {"modules": [module_name for module_name, _ in modules], "versions": versions},
    }


def _any_module_capability(modules: tuple[tuple[str, str], ...]) -> LocalCapability:
    for module_name, package_name in modules:
        capability = _module_capability(module_name, package_name)
        if capability["status"] == "certified":
            return capability
    return {
        "status": "unavailable",
        "detail": f"None of these modules are importable: {[module_name for module_name, _ in modules]}",
        "evidence": {"modules": [module_name for module_name, _ in modules]},
    }


def _command_capability(command: str) -> LocalCapability:
    resolved = shutil.which(command)
    return {
        "status": "certified" if resolved else "unavailable",
        "detail": f"{command} is available on PATH." if resolved else f"{command} is not available on PATH.",
        "evidence": {"command": command, "path": resolved},
    }


def _any_command_capability(commands: tuple[str, ...]) -> LocalCapability:
    for command in commands:
        resolved = shutil.which(command)
        if resolved:
            return {
                "status": "certified",
                "detail": f"{command} is available on PATH.",
                "evidence": {"command": command, "path": resolved},
            }
    return {
        "status": "unavailable",
        "detail": f"None of these commands are available on PATH: {list(commands)}",
        "evidence": {"commands": list(commands)},
    }


def _torch_cuda_capability(*, min_vram_gib: float) -> LocalCapability:
    if not _module_available("torch"):
        return {
            "status": "unavailable",
            "detail": "torch is not importable.",
            "evidence": {"min_vram_gib": min_vram_gib},
        }
    try:
        import torch
    except (ImportError, OSError, RuntimeError) as exc:
        return {
            "status": "unavailable",
            "detail": f"torch import failed: {exc}",
            "evidence": {"min_vram_gib": min_vram_gib},
        }
    if not torch.cuda.is_available():
        return {
            "status": "unavailable",
            "detail": "torch.cuda is unavailable.",
            "evidence": {"min_vram_gib": min_vram_gib, "cuda_available": False},
        }
    props = torch.cuda.get_device_properties(0)
    total_gib = float(props.total_memory) / float(1024**3)
    certified = total_gib >= min_vram_gib
    return {
        "status": "certified" if certified else "unavailable",
        "detail": (
            f"CUDA device has {total_gib:.1f} GiB VRAM."
            if certified
            else f"CUDA VRAM {total_gib:.1f} GiB is below required {min_vram_gib:.1f} GiB."
        ),
        "evidence": {
            "device": str(props.name),
            "vram_gib": round(total_gib, 2),
            "min_vram_gib": min_vram_gib,
            "cuda_version": str(getattr(getattr(torch, "version", None), "cuda", "")),
        },
    }


def _comfyui_capability(api_url: str, *, timeout_sec: float) -> LocalCapability:
    required_classes = sorted(set(_PIPELINE_COMFYUI_NODE_CLASSES).union(_FLUX_COMFYUI_NODE_CLASSES))
    try:
        with urllib.request.urlopen(f"{api_url}/object_info", timeout=timeout_sec) as response:
            payload = json.loads(response.read().decode("utf-8"))
    except (TimeoutError, OSError, urllib.error.URLError, json.JSONDecodeError) as exc:
        return {
            "status": "unavailable",
            "detail": f"ComfyUI object_info is unavailable at {api_url}: {exc}",
            "evidence": {"api_url": api_url, "required_classes": required_classes},
        }
    if not isinstance(payload, dict):
        return {
            "status": "unavailable",
            "detail": "ComfyUI object_info response is not a JSON object.",
            "evidence": {"api_url": api_url, "required_classes": required_classes},
        }
    missing = [class_name for class_name in required_classes if class_name not in payload]
    return {
        "status": "certified" if not missing else "unavailable",
        "detail": "ComfyUI has all required workflow node classes." if not missing else f"Missing nodes: {missing}",
        "evidence": {"api_url": api_url, "required_classes": required_classes, "missing_classes": missing},
    }


def _comfyui_model_capability(comfyui_root: Path | None) -> LocalCapability:
    if comfyui_root is None:
        return {
            "status": "unavailable",
            "detail": "ComfyUI model files were not checked. Pass --comfyui-root for production certification.",
            "evidence": {"required_files": list(_COMFYUI_MODEL_FILES)},
        }
    missing = [
        relative_path
        for relative_path in _COMFYUI_MODEL_FILES
        if not (comfyui_root / relative_path).is_file()
    ]
    return {
        "status": "certified" if not missing else "unavailable",
        "detail": "All required ComfyUI model files exist." if not missing else f"Missing model files: {missing}",
        "evidence": {
            "comfyui_root": str(comfyui_root),
            "required_files": list(_COMFYUI_MODEL_FILES),
            "missing_files": missing,
        },
    }


def _skipped_capability(detail: str) -> LocalCapability:
    return {
        "status": "contract-tested",
        "detail": detail,
        "evidence": {},
    }
