"""
aiprod_adaptation/post_prod/audiocraft_adapter.py
==================================================
Adaptateur audio local via Meta AudioCraft (MusicGen + AudioGen).

MusicGen  : génération musicale guidée par prompt texte (score/ambiance).
AudioGen  : génération d'effets sonores (SFX) guidée par prompt texte.

Les deux modèles sont gratuits, locaux, et fonctionnent sur RTX 5080 32GB.

Installation :
  pip install audiocraft
  # ou : pip install git+https://github.com/facebookresearch/audiocraft.git

Modèles disponibles (MusicGen) :
  "facebook/musicgen-small"  — 300M params, ~2s génération
  "facebook/musicgen-medium" — 1.5B params, qualité broadcast, ~10s
  "facebook/musicgen-large"  — 3.3B params, meilleure qualité, ~30s (recommandé RTX 5080)
  "facebook/musicgen-stereo-large" — large + stereo (recommandé production)

Modèles disponibles (AudioGen) :
  "facebook/audiogen-medium" — SFX haute qualité, 16kHz
"""
from __future__ import annotations

import io
import time
from pathlib import Path
from typing import Any, Literal

from aiprod_adaptation.post_prod.audio_adapter import AudioAdapter
from aiprod_adaptation.post_prod.audio_request import AudioRequest, AudioResult

# Modèles par défaut — changer selon VRAM disponible
_DEFAULT_MUSIC_MODEL = "facebook/musicgen-stereo-large"
_DEFAULT_SFX_MODEL = "facebook/audiogen-medium"
_DEFAULT_SAMPLE_RATE_MUSIC = 32000   # MusicGen large stereo
_DEFAULT_SAMPLE_RATE_SFX = 16000     # AudioGen medium


class MusicGenAdapter(AudioAdapter):
    """Génération musicale locale via Meta MusicGen (score + ambiance).

    Args:
        model:       Variante MusicGen (voir ci-dessus).
        duration:    Durée de génération en secondes (max 30s en pratique).
        device:      "cuda" (recommandé) ou "cpu".
        temperature: Température d'échantillonnage (1.0 = défaut, 0.8 = plus cohérent).
        top_k:       Top-k sampling (250 = défaut MusicGen).
        cfg_coef:    Coefficient de guidance (3.0 = défaut, augmenter pour plus de prompt-following).
    """

    MODEL_NAME = "musicgen-local"

    def __init__(
        self,
        model: str = _DEFAULT_MUSIC_MODEL,
        duration: float = 10.0,
        device: str | None = None,
        temperature: float = 1.0,
        top_k: int = 250,
        cfg_coef: float = 3.0,
    ) -> None:
        self._model_id = model
        self._duration = duration
        self._device = device or ("cuda" if _cuda_available() else "cpu")
        self._temperature = temperature
        self._top_k = top_k
        self._cfg_coef = cfg_coef
        self._model: Any | None = None

    # ------------------------------------------------------------------
    # AudioAdapter interface
    # ------------------------------------------------------------------

    def generate(self, request: AudioRequest) -> AudioResult:
        t0 = time.monotonic()
        model = self._get_model()

        duration = float(request.duration_hint_sec)
        wav_bytes = self._generate_music(model, request.text, duration)

        latency_ms = int((time.monotonic() - t0) * 1000)
        import base64
        audio_b64 = base64.b64encode(wav_bytes).decode("ascii")

        return AudioResult(
            shot_id=request.shot_id,
            audio_url=f"local://musicgen/{request.shot_id}.wav",
            audio_b64=audio_b64,
            duration_sec=request.duration_hint_sec,
            model_used=self.MODEL_NAME,
            latency_ms=latency_ms,
            cost_usd=0.0,
        )

    def generate_to_file(self, request: AudioRequest, out_path: Path) -> Path:
        """Génère le score et l'écrit dans un fichier WAV."""
        t0 = time.monotonic()
        model = self._get_model()
        duration = float(request.duration_hint_sec)
        wav_bytes = self._generate_music(model, request.text, duration)
        out_path.parent.mkdir(parents=True, exist_ok=True)
        out_path.write_bytes(wav_bytes)
        elapsed = (time.monotonic() - t0) * 1000
        print(f"[MusicGen] {request.shot_id} → {out_path.name} ({elapsed:.0f}ms, $0.00)")
        return out_path

    # ------------------------------------------------------------------
    # Helpers internes
    # ------------------------------------------------------------------

    def _get_model(self) -> Any:
        if self._model is not None:
            return self._model
        try:
            from audiocraft.models import MusicGen  # type: ignore[import-untyped]
        except ImportError as exc:
            raise ImportError(
                "audiocraft manquant. Installer : pip install audiocraft\n"
                "Ou : pip install git+https://github.com/facebookresearch/audiocraft.git"
            ) from exc
        m = MusicGen.get_pretrained(self._model_id, device=self._device)
        m.set_generation_params(
            duration=self._duration,
            temperature=self._temperature,
            top_k=self._top_k,
            cfg_coef=self._cfg_coef,
        )
        self._model = m
        return m

    def _generate_music(self, model: Any, prompt: str, duration: float) -> bytes:
        import torchaudio  # type: ignore[import-untyped]
        import torch

        model.set_generation_params(duration=duration)
        with torch.inference_mode():
            wav = model.generate([prompt])

        # wav shape : [batch, channels, samples]
        wav_cpu = wav[0].cpu()
        sample_rate = model.sample_rate

        buf = io.BytesIO()
        torchaudio.save(buf, wav_cpu, sample_rate, format="wav")
        buf.seek(0)
        return buf.read()


class AudioGenAdapter(AudioAdapter):
    """Génération d'effets sonores locaux via Meta AudioGen.

    Utilisation type :
      adapter = AudioGenAdapter()
      request = AudioRequest(
          shot_id="SCN_002_SHOT_001",
          text="metallic valve hissing, pressurized steam, industrial background hum",
          duration_hint_sec=5,
      )
      result = adapter.generate(request)

    Args:
        model:    Variante AudioGen (voir ci-dessus).
        duration: Durée en secondes.
        device:   "cuda" ou "cpu".
    """

    MODEL_NAME = "audiogen-local"

    def __init__(
        self,
        model: str = _DEFAULT_SFX_MODEL,
        duration: float = 5.0,
        device: str | None = None,
    ) -> None:
        self._model_id = model
        self._duration = duration
        self._device = device or ("cuda" if _cuda_available() else "cpu")
        self._model: Any | None = None

    # ------------------------------------------------------------------
    # AudioAdapter interface
    # ------------------------------------------------------------------

    def generate(self, request: AudioRequest) -> AudioResult:
        t0 = time.monotonic()
        model = self._get_model()

        duration = float(request.duration_hint_sec)
        wav_bytes = self._generate_sfx(model, request.text, duration)

        latency_ms = int((time.monotonic() - t0) * 1000)
        import base64
        audio_b64 = base64.b64encode(wav_bytes).decode("ascii")

        return AudioResult(
            shot_id=request.shot_id,
            audio_url=f"local://audiogen/{request.shot_id}.wav",
            audio_b64=audio_b64,
            duration_sec=request.duration_hint_sec,
            model_used=self.MODEL_NAME,
            latency_ms=latency_ms,
            cost_usd=0.0,
        )

    def generate_to_file(self, request: AudioRequest, out_path: Path) -> Path:
        """Génère le SFX et l'écrit dans un fichier WAV."""
        t0 = time.monotonic()
        model = self._get_model()
        duration = float(request.duration_hint_sec)
        wav_bytes = self._generate_sfx(model, request.text, duration)
        out_path.parent.mkdir(parents=True, exist_ok=True)
        out_path.write_bytes(wav_bytes)
        elapsed = (time.monotonic() - t0) * 1000
        print(f"[AudioGen] {request.shot_id} → {out_path.name} ({elapsed:.0f}ms, $0.00)")
        return out_path

    # ------------------------------------------------------------------
    # Helpers internes
    # ------------------------------------------------------------------

    def _get_model(self) -> Any:
        if self._model is not None:
            return self._model
        try:
            from audiocraft.models import AudioGen  # type: ignore[import-untyped]
        except ImportError as exc:
            raise ImportError(
                "audiocraft manquant. Installer : pip install audiocraft\n"
                "Ou : pip install git+https://github.com/facebookresearch/audiocraft.git"
            ) from exc
        m = AudioGen.get_pretrained(self._model_id, device=self._device)
        m.set_generation_params(duration=self._duration)
        self._model = m
        return m

    def _generate_sfx(self, model: Any, prompt: str, duration: float) -> bytes:
        import torchaudio  # type: ignore[import-untyped]
        import torch

        model.set_generation_params(duration=duration)
        with torch.inference_mode():
            wav = model.generate([prompt])

        wav_cpu = wav[0].cpu()
        sample_rate = model.sample_rate

        buf = io.BytesIO()
        torchaudio.save(buf, wav_cpu, sample_rate, format="wav")
        buf.seek(0)
        return buf.read()


def _cuda_available() -> bool:
    try:
        import torch
        return torch.cuda.is_available()
    except ImportError:
        return False


# ---------------------------------------------------------------------------
# Helper : fabrique d'adapter selon le type
# ---------------------------------------------------------------------------

AudioAdapterType = Literal["musicgen", "audiogen"]


def make_local_audio_adapter(
    kind: AudioAdapterType,
    duration: float = 10.0,
    device: str | None = None,
) -> AudioAdapter:
    """Fabrique un adaptateur audio local selon le type demandé.

    Args:
        kind:     "musicgen" (score/ambiance) ou "audiogen" (SFX).
        duration: Durée de génération en secondes.
        device:   "cuda" ou "cpu" (auto-détecté si None).

    Returns:
        Instance prête à l'emploi implémentant AudioAdapter.
    """
    if kind == "musicgen":
        return MusicGenAdapter(duration=duration, device=device)
    if kind == "audiogen":
        return AudioGenAdapter(duration=duration, device=device)
    raise ValueError(f"kind inconnu : '{kind}'. Valides : musicgen, audiogen")
