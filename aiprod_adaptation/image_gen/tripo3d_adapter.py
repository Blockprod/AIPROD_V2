"""
aiprod_adaptation/image_gen/tripo3d_adapter.py
===============================================
Adaptateur Tripo3D API — génération de mesh 3D GLB depuis images multi-vues.

API : https://platform.tripo3d.ai
Endpoint : https://api.tripo3d.ai/v2/openapi

Workflow V4 (vues cohérentes via Tripo3D) :
  1. upload_image(front_path)             → image_token
  2. generate_multiview_image(front_path) → mv_task_id
  3. poll_multiview_image_task(mv_task_id) → mv_task_id confirmé
  4. multiview_to_model(mv_task_id)       → model_task_id
  5. poll_model_task(model_task_id)       → {model_url}
  6. download_glb(model_url, out_path)

Coût : ~$0.30 par modèle (5 personnages = ~$1.50)

Usage direct :
    adapter = Tripo3DAdapter()
    mv_id   = adapter.generate_multiview_image(Path("nara/angle_00_front.png"))
    adapter.poll_multiview_image_task(mv_id)
    mdl_id  = adapter.multiview_to_model(mv_id)
    result  = adapter.poll_model_task(mdl_id)
    adapter.download_glb(result["model_url"], Path("production/assets_3d/nara.glb"))
"""
from __future__ import annotations

import os
import time
from pathlib import Path
from typing import Any

import requests

_BASE_URL = "https://api.tripo3d.ai/v2/openapi"
_POLL_INTERVAL_S = 5
_POLL_TIMEOUT_S = 600  # 10 minutes max


class Tripo3DError(RuntimeError):
    """Erreur renvoyée par l'API Tripo3D."""


class Tripo3DAdapter:
    """Wrapper minimal autour de l'API Tripo3D."""

    def __init__(self, api_token: str | None = None) -> None:
        token = api_token or os.environ.get("TRIPO3D_API_TOKEN", "")
        if not token:
            raise Tripo3DError(
                "TRIPO3D_API_TOKEN manquant. Définir dans .env ou passer api_token=."
            )
        self._headers = {
            "Authorization": f"Bearer {token}",
            "Content-Type": "application/json",
        }

    # ------------------------------------------------------------------
    # Public API
    # ------------------------------------------------------------------

    def upload_image(self, image_path: Path) -> str:
        """Upload une image vers Tripo3D et retourne l'image_token.

        Endpoint : POST /upload/sts (multipart/form-data)

        Returns:
            image_token (str) à utiliser comme file_token dans les tasks.

        Raises:
            Tripo3DError si l'upload échoue.
        """
        headers_upload = {"Authorization": self._headers["Authorization"]}
        with open(image_path, "rb") as f:
            response = requests.post(
                f"{_BASE_URL}/upload/sts",
                headers=headers_upload,
                files={"file": (image_path.name, f, "image/png")},
                timeout=60,
            )
        self._raise_for_status(response)
        token: str = response.json()["data"]["image_token"]
        return token

    def generate_multiview_image(self, front_path: Path) -> str:
        """Soumet un task generate_multiview_image a partir d'une image front.

        Tripo3D genere lui-meme les 4 vues coherentes (front/left/back/right)
        ce qui garantit la coherence geometrique requise pour un GLB de qualite.

        Args:
            front_path: Image face du personnage (PNG, fond blanc, plein corps).

        Returns:
            task_id a passer a poll_multiview_image_task().

        Raises:
            Tripo3DError si l'upload ou la soumission echoue.
        """
        token = self.upload_image(front_path)
        payload: dict[str, Any] = {
            "type": "generate_multiview_image",
            "file": {"type": "png", "file_token": token},
        }
        response = requests.post(
            f"{_BASE_URL}/task",
            headers=self._headers,
            json=payload,
            timeout=30,
        )
        self._raise_for_status(response)
        task_id: str = response.json()["data"]["task_id"]
        return task_id

    def poll_multiview_image_task(self, task_id: str) -> str:
        """Attend la completion d'un task generate_multiview_image.

        Returns:
            task_id confirme (a utiliser comme original_task_id dans multiview_to_model).

        Raises:
            Tripo3DError si le task echoue ou expire.
        """
        deadline = time.monotonic() + _POLL_TIMEOUT_S
        while time.monotonic() < deadline:
            response = requests.get(
                f"{_BASE_URL}/task/{task_id}",
                headers=self._headers,
                timeout=30,
            )
            self._raise_for_status(response)
            data = response.json()["data"]
            status: str = data["status"]

            if status == "success":
                return task_id

            if status in ("failed", "cancelled", "banned", "expired"):
                raise Tripo3DError(
                    f"Task multiview {task_id} termine avec statut '{status}'"
                )

            time.sleep(_POLL_INTERVAL_S)

        raise Tripo3DError(f"Task multiview {task_id} n'a pas termine en {_POLL_TIMEOUT_S}s.")

    def multiview_to_model(
        self,
        original_task_id: str,
        model_seed: int | None = None,
    ) -> str:
        """Soumet un task multiview_to_model a partir d'un task generate_multiview_image.

        Args:
            original_task_id: task_id issu de generate_multiview_image (vues coherentes).
            model_seed: Graine reproductible pour la geometrie (optionnel).

        Returns:
            task_id a passer a poll_model_task().

        Raises:
            Tripo3DError si la soumission echoue.
        """
        payload: dict[str, Any] = {
            "type": "multiview_to_model",
            "original_task_id": original_task_id,
            "texture": True,
            "pbr": False,
        }
        if model_seed is not None:
            payload["model_seed"] = model_seed

        response = requests.post(
            f"{_BASE_URL}/task",
            headers=self._headers,
            json=payload,
            timeout=30,
        )
        self._raise_for_status(response)
        task_id: str = response.json()["data"]["task_id"]
        return task_id

    def poll_model_task(self, task_id: str) -> dict[str, Any]:
        """Attend la completion d'un task de generation de modele 3D.

        Returns:
            dict {"status": "success", "task_id": str, "model_url": str}.

        Raises:
            Tripo3DError si le task echoue ou expire.
        """
        deadline = time.monotonic() + _POLL_TIMEOUT_S
        while time.monotonic() < deadline:
            response = requests.get(
                f"{_BASE_URL}/task/{task_id}",
                headers=self._headers,
                timeout=30,
            )
            self._raise_for_status(response)
            data = response.json()["data"]
            status: str = data["status"]

            if status == "success":
                output = data.get("output") or data.get("result") or {}
                # L'API retourne output.model soit comme string URL, soit comme dict {url: ...}
                model_raw = output.get("model", "")
                if isinstance(model_raw, dict):
                    model_url: str = model_raw.get("url", "")
                else:
                    model_url = str(model_raw)
                if not model_url:
                    raise Tripo3DError(
                        f"Task {task_id} success mais model_url introuvable. output={output}"
                    )
                return {"status": "success", "task_id": task_id, "model_url": model_url}

            if status in ("failed", "cancelled", "banned", "expired"):
                raise Tripo3DError(
                    f"Task {task_id} termine avec statut '{status}'"
                )

            time.sleep(_POLL_INTERVAL_S)

        raise Tripo3DError(f"Task {task_id} n'a pas termine en {_POLL_TIMEOUT_S}s.")

    def download_glb(self, model_url: str, output_path: Path) -> None:
        """Télécharge le GLB depuis model_url vers output_path.

        Crée les répertoires parents si nécessaire.
        """
        output_path.parent.mkdir(parents=True, exist_ok=True)
        response = requests.get(model_url, timeout=120, stream=True)
        response.raise_for_status()
        with open(output_path, "wb") as f:
            for chunk in response.iter_content(chunk_size=65536):
                f.write(chunk)

    # ------------------------------------------------------------------
    # Internal helpers
    # ------------------------------------------------------------------

    def _raise_for_status(self, response: requests.Response) -> None:
        """Lève Tripo3DError avec le message API si le statut HTTP n'est pas 2xx."""
        if not response.ok:
            try:
                detail = response.json().get("message", response.text)
            except Exception:
                detail = response.text
            raise Tripo3DError(
                f"Tripo3D API {response.status_code}: {detail}"
            )
