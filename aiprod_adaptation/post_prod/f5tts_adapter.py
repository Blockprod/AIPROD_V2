"""
aiprod_adaptation/post_prod/f5tts_adapter.py
=============================================
Adaptateur TTS local via F5-TTS (100% gratuit, zéro API cloud).

F5-TTS génère une voix naturelle de haute qualité en utilisant un modèle
de flow matching entraîné sur 100K+ heures audio.

Avantages vs ElevenLabs :
  - Gratuit (local)
  - Voix clonables à partir d'un sample de 3-10 secondes
  - Qualité broadcast (24kHz / 44.1kHz selon config)
  - Latence ~1-3s par phrase sur RTX 5080

Installation :
  pip install f5-tts
  # ou depuis source : pip install git+https://github.com/SWivid/F5-TTS.git

Utilisation :
  adapter = F5TTSAdapter(ref_audio="production/audio/voice_refs/nara_ref.wav")
  result = adapter.generate(AudioRequest(shot_id="SCN_001_SHOT_001", text="..."))
"""
from __future__ import annotations

import io
import os
import time
from pathlib import Path
from typing import Any

from aiprod_adaptation.post_prod.audio_adapter import AudioAdapter
from aiprod_adaptation.post_prod.audio_request import AudioRequest, AudioResult

_DEFAULT_SAMPLE_RATE = 24000
_DEFAULT_STEPS = 32          # 32 = bon équilibre qualité/vitesse sur RTX
_DEFAULT_NFE = 32            # nombre de function evaluations (même valeur)
_DEFAULT_SPEED = 1.0


class F5TTSAdapter(AudioAdapter):
    """TTS local via F5-TTS (flow-matching, zéro API cloud).

    Args:
        ref_audio: Chemin vers l'audio de référence pour le clonage vocal (3-10s, WAV/MP3).
        ref_text:  Transcription exacte du ref_audio (améliore la qualité).
        model:     Variante F5-TTS : "F5TTS_Base" (défaut) ou "E2TTS_Base".
        speed:     Vitesse de parole (1.0 = normal, 0.85 = légèrement plus lent, broadcast).
        nfe_steps: Nombre d'étapes d'inférence (32 = défaut, 64 = meilleure qualité).
        device:    "cuda" (recommandé RTX 5080) ou "cpu".
    """

    MODEL_NAME = "f5-tts-local"

    def __init__(
        self,
        ref_audio: str | Path | None = None,
        ref_text: str = "",
        model: str = "F5TTS_Base",
        speed: float = _DEFAULT_SPEED,
        nfe_steps: int = _DEFAULT_NFE,
        device: str | None = None,
    ) -> None:
        self._ref_audio = Path(ref_audio) if ref_audio else None
        self._ref_text = ref_text
        self._model_name = model
        self._speed = speed
        self._nfe_steps = nfe_steps
        self._device = device or ("cuda" if _cuda_available() else "cpu")
        self._pipeline: Any | None = None

    # ------------------------------------------------------------------
    # AudioAdapter interface
    # ------------------------------------------------------------------

    def generate(self, request: AudioRequest) -> AudioResult:
        """Génère l'audio TTS pour un shot.

        Returns:
            AudioResult avec audio_b64 contenant le WAV base64.
        """
        t0 = time.monotonic()
        pipe = self._get_pipeline()

        wav_bytes = self._synthesize(pipe, request.text)

        latency_ms = int((time.monotonic() - t0) * 1000)
        import base64
        audio_b64 = base64.b64encode(wav_bytes).decode("ascii")

        return AudioResult(
            shot_id=request.shot_id,
            audio_url=f"local://f5tts/{request.shot_id}.wav",
            audio_b64=audio_b64,
            duration_sec=request.duration_hint_sec,
            model_used=self.MODEL_NAME,
            latency_ms=latency_ms,
            cost_usd=0.0,
        )

    def generate_to_file(self, request: AudioRequest, out_path: Path) -> Path:
        """Génère l'audio et l'écrit directement dans un fichier WAV.

        Args:
            request:  Requête audio.
            out_path: Chemin du fichier WAV de sortie (créé si absent).

        Returns:
            Path vers le fichier généré.
        """
        t0 = time.monotonic()
        pipe = self._get_pipeline()
        wav_bytes = self._synthesize(pipe, request.text)
        out_path.parent.mkdir(parents=True, exist_ok=True)
        out_path.write_bytes(wav_bytes)
        elapsed = (time.monotonic() - t0) * 1000
        print(f"[F5TTS] {request.shot_id} → {out_path.name} ({elapsed:.0f}ms, $0.00)")
        return out_path

    # ------------------------------------------------------------------
    # Helpers internes
    # ------------------------------------------------------------------

    def _get_pipeline(self) -> Any:
        """Charge le pipeline F5-TTS (singleton, chargé une seule fois)."""
        if self._pipeline is not None:
            return self._pipeline

        try:
            from f5_tts.api import F5TTS  # type: ignore[import-untyped]
        except ImportError as exc:
            raise ImportError(
                "f5-tts manquant. Installer : pip install f5-tts\n"
                "Ou depuis source : pip install git+https://github.com/SWivid/F5-TTS.git"
            ) from exc

        self._pipeline = F5TTS(
            model_type=self._model_name,
            device=self._device,
        )
        return self._pipeline

    def _synthesize(self, pipe: Any, text: str) -> bytes:
        """Appelle F5-TTS et retourne les bytes WAV."""
        import soundfile as sf  # type: ignore[import-untyped]

        ref_audio_path = str(self._ref_audio) if self._ref_audio else None
        ref_text = self._ref_text if self._ref_audio else ""

        wav, sr = pipe.infer(
            ref_file=ref_audio_path,
            ref_text=ref_text,
            gen_text=text,
            nfe_step=self._nfe_steps,
            speed=self._speed,
        )

        buf = io.BytesIO()
        sf.write(buf, wav, sr, format="WAV")
        buf.seek(0)
        return buf.read()


def _cuda_available() -> bool:
    try:
        import torch
        return torch.cuda.is_available()
    except ImportError:
        return False
