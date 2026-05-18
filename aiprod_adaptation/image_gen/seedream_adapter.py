"""
aiprod_adaptation/image_gen/seedream_adapter.py
================================================
Adapter Seedream 4.5 (ByteDance) via Replicate API.

Usage principal : générer les planches multi-angles de personnages et de décors
pour le pipeline V4 (source → Tripo3D / Meshy).

Modèle : bytedance/seedream-4.5
Coût   : ~$0.04/image (Replicate, mai 2026)

API publique :
    adapter = SeedreamAdapter()
    result  = adapter.generate(request)         # shot standard
    png     = adapter.generate_reference(       # planche turnaround
                  prompt, seed, aspect_ratio
              )  -> bytes PNG

Raises:
    SeedreamError(RuntimeError) si REPLICATE_API_TOKEN absent ou si l'appel échoue.
"""
from __future__ import annotations

import os
import time
import urllib.request
from typing import Any

from aiprod_adaptation.image_gen.image_adapter import ImageAdapter
from aiprod_adaptation.image_gen.image_request import ImageRequest, ImageResult

MODEL = "bytedance/seedream-4.5"
COST_PER_IMAGE_USD = 0.04

# Tailles supportées par Seedream 4.5
_VALID_SIZES = {"1K", "2K", "4K"}
_VALID_ASPECT_RATIOS = {
    "1:1", "4:3", "3:4", "16:9", "9:16", "2:3", "3:2", "21:9",
}


class SeedreamError(RuntimeError):
    """Erreur levée par SeedreamAdapter."""


class SeedreamAdapter(ImageAdapter):
    """Adapter Seedream 4.5 via Replicate.

    Args:
        size:           Resolution de sortie ("1K", "2K", "4K").
        default_aspect: Ratio par defaut pour les shots storyboard ("16:9").
        ref_aspect:     Ratio par defaut pour les planches de reference ("2:3").
        sequential:     "disabled" = images independantes (defaut, reproductible).
    """

    MODEL_NAME = MODEL

    def __init__(
        self,
        size: str = "2K",
        default_aspect: str = "16:9",
        ref_aspect: str = "2:3",
        sequential: str = "disabled",
    ) -> None:
        token = os.environ.get("REPLICATE_API_TOKEN", "")
        if not token:
            raise SeedreamError("REPLICATE_API_TOKEN manquant dans .env")
        if size not in _VALID_SIZES:
            raise ValueError(f"size invalide : '{size}'. Valides : {_VALID_SIZES}")
        if default_aspect not in _VALID_ASPECT_RATIOS:
            raise ValueError(f"aspect_ratio invalide : '{default_aspect}'")
        self._size = size
        self._default_aspect = default_aspect
        self._ref_aspect = ref_aspect
        self._sequential = sequential

    # ------------------------------------------------------------------
    # ImageAdapter interface
    # ------------------------------------------------------------------

    def generate(self, request: ImageRequest) -> ImageResult:
        """Genere une image de storyboard (format 16:9 par defaut).

        Args:
            request: ImageRequest avec prompt, seed, shot_id.

        Returns:
            ImageResult avec image_url et cost_usd renseignes.

        Raises:
            SeedreamError si l'appel Replicate echoue.
        """
        t0 = time.monotonic()
        url = self._run_replicate(
            prompt=request.prompt,
            seed=request.seed,
            aspect_ratio=self._default_aspect,
        )
        latency_ms = int((time.monotonic() - t0) * 1000)
        return ImageResult(
            shot_id=request.shot_id,
            image_url=url,
            model_used=MODEL,
            latency_ms=latency_ms,
            cost_usd=COST_PER_IMAGE_USD,
        )

    # ------------------------------------------------------------------
    # API specifique V4 — planches de reference
    # ------------------------------------------------------------------

    def generate_reference(
        self,
        prompt: str,
        seed: int | None = None,
        aspect_ratio: str | None = None,
        size: str | None = None,
    ) -> bytes:
        """Genere une image de reference turnaround et retourne les bytes PNG.

        Usage typique : planches multi-angles personnages / decors pour Tripo3D / Meshy.

        Args:
            prompt:       Prompt complet (canonical + framing + studio_suffix).
            seed:         Graine reproductible.
            aspect_ratio: Ratio image ("2:3" pour portrait plein corps).
            size:         Resolution ("1K", "2K", "4K"). Defaut : self._size.

        Returns:
            bytes PNG de l'image generee.
        """
        ar = aspect_ratio or self._ref_aspect
        sz = size or self._size
        url = self._run_replicate(prompt=prompt, seed=seed, aspect_ratio=ar, size=sz)
        return _download_png(url)

    def generate_reference_to_file(
        self,
        prompt: str,
        out_path: str | os.PathLike[str],
        seed: int | None = None,
        aspect_ratio: str | None = None,
        size: str | None = None,
    ) -> str:
        """Genere et sauvegarde une image de reference.

        Returns:
            Chemin absolu du fichier PNG sauvegarde.
        """
        from pathlib import Path
        out = Path(out_path)
        out.parent.mkdir(parents=True, exist_ok=True)
        png_bytes = self.generate_reference(
            prompt=prompt,
            seed=seed,
            aspect_ratio=aspect_ratio,
            size=size,
        )
        out.write_bytes(png_bytes)
        return str(out.resolve())

    # ------------------------------------------------------------------
    # Interne
    # ------------------------------------------------------------------

    def _run_replicate(
        self,
        prompt: str,
        seed: int | None,
        aspect_ratio: str,
        size: str | None = None,
    ) -> str:
        """Appelle Replicate et retourne l'URL de l'image generee."""
        try:
            import replicate
        except ImportError as exc:
            raise SeedreamError(
                "Package 'replicate' non installe. Lancer : pip install replicate"
            ) from exc

        if aspect_ratio not in _VALID_ASPECT_RATIOS:
            raise ValueError(f"aspect_ratio invalide : '{aspect_ratio}'")

        input_data: dict[str, Any] = {
            "prompt": prompt,
            "size": size or self._size,
            "aspect_ratio": aspect_ratio,
            "sequential_image_generation": self._sequential,
        }
        # Seedream 4.5 ne supporte pas le champ 'seed' (validation Replicate)

        try:
            output = replicate.run(MODEL, input=input_data)
        except Exception as exc:
            raise SeedreamError(f"Replicate Seedream 4.5 a echoue : {exc}") from exc

        url = str(output[0]) if isinstance(output, list) else str(output)
        if not url.startswith("http"):
            raise SeedreamError(f"URL inattendue de Replicate : {url!r}")
        return url


# ------------------------------------------------------------------
# Helper
# ------------------------------------------------------------------

def _download_png(url: str, timeout: int = 120) -> bytes:
    with urllib.request.urlopen(url, timeout=timeout) as resp:
        return resp.read()
