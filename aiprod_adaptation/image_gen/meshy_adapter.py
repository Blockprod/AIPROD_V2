"""
aiprod_adaptation/image_gen/meshy_adapter.py
============================================
Adaptateur Meshy API — génération de mesh 3D GLB depuis une image.

API : https://www.meshy.ai
Endpoint : https://api.meshy.ai/openapi/v1

Opérations :
  - image_to_model : image source → GLB (décors)
  - poll_task      : attend la complétion du task
  - download_glb   : télécharge le GLB dans output_path

Coût : ~$0.20 par modèle (10 décors = ~$2.00)

Usage direct :
    adapter = MeshyAdapter()
    task_id = adapter.image_to_model(image_path=Path("ref.png"), seed=42)
    result  = adapter.poll_task(task_id)
    adapter.download_glb(result["model_url"], Path("production/assets_3d/corridor.glb"))

Note : MESHY_API_TOKEN doit être défini dans .env (subscription requise).
"""
from __future__ import annotations

import os
import time
from pathlib import Path
from typing import Any

import requests

_BASE_URL = "https://api.meshy.ai/openapi/v1"
_POLL_INTERVAL_S = 5
_POLL_TIMEOUT_S = 600  # 10 minutes max


class MeshyError(RuntimeError):
    """Erreur renvoyée par l'API Meshy."""


class MeshyAdapter:
    """Wrapper minimal autour de l'API Meshy."""

    def __init__(self, api_token: str | None = None) -> None:
        token = api_token or os.environ.get("MESHY_API_TOKEN", "")
        if not token:
            raise MeshyError(
                "MESHY_API_TOKEN manquant. Définir dans .env ou passer api_token=. "
                "(Subscription Meshy requise : https://www.meshy.ai)"
            )
        self._headers = {
            "Authorization": f"Bearer {token}",
            "Content-Type": "application/json",
        }

    # ------------------------------------------------------------------
    # Public API
    # ------------------------------------------------------------------

    def image_to_model(
        self,
        image_url: str | None = None,
        image_path: Path | None = None,
        seed: int = 42,
        topology: str = "quad",
        target_polycount: int = 30000,
    ) -> str:
        """Soumet un task image-to-3D.

        Fournir soit image_url (URL HTTPS) soit image_path (fichier local).

        Args:
            image_url:       URL HTTPS de l'image source.
            image_path:      Chemin local — sera uploadé en base64.
            seed:            Graine reproductible.
            topology:        "quad" (recommandé pour Blender) ou "triangle".
            target_polycount: Nombre de polygones cible.

        Returns:
            task_id (str) — utiliser avec poll_task().

        Raises:
            MeshyError: si l'API retourne une erreur.
        """
        if image_url is None and image_path is None:
            raise MeshyError("Fournir image_url ou image_path.")

        if image_url is None and image_path is not None:
            import base64
            suffix = image_path.suffix.lower().lstrip(".")
            mime = "image/jpeg" if suffix in ("jpg", "jpeg") else f"image/{suffix}"
            encoded = base64.b64encode(image_path.read_bytes()).decode()
            image_url = f"data:{mime};base64,{encoded}"

        payload: dict[str, Any] = {
            "image_url": image_url,
            "enable_pbr": False,
            "topology": topology,
            "target_polycount": target_polycount,
            "seed": seed,
        }
        response = requests.post(
            f"{_BASE_URL}/image-to-3d",
            headers=self._headers,
            json=payload,
            timeout=30,
        )
        self._raise_for_status(response)
        data = response.json()
        task_id: str = data["result"]
        return task_id

    def poll_task(self, task_id: str) -> dict[str, Any]:
        """Attend la complétion du task et retourne le résultat.

        Lève MeshyError si le task échoue ou expire.

        Returns:
            dict avec au minimum {"model_url": str, "status": "SUCCEEDED"}.
        """
        deadline = time.monotonic() + _POLL_TIMEOUT_S
        while time.monotonic() < deadline:
            response = requests.get(
                f"{_BASE_URL}/image-to-3d/{task_id}",
                headers=self._headers,
                timeout=30,
            )
            self._raise_for_status(response)
            data = response.json()
            status: str = data["status"]

            if status == "SUCCEEDED":
                model_url: str = data["model_urls"]["glb"]
                return {"status": "SUCCEEDED", "task_id": task_id, "model_url": model_url}

            if status in ("FAILED", "EXPIRED"):
                raise MeshyError(
                    f"Task {task_id} terminé avec statut '{status}': "
                    f"{data.get('task_error', {}).get('message', '')}"
                )

            # En attente — "PENDING" ou "IN_PROGRESS"
            time.sleep(_POLL_INTERVAL_S)

        raise MeshyError(f"Task {task_id} n'a pas terminé en {_POLL_TIMEOUT_S}s.")

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
        """Lève MeshyError avec le message API si le statut HTTP n'est pas 2xx."""
        if not response.ok:
            try:
                detail = response.json().get("message", response.text)
            except Exception:
                detail = response.text
            raise MeshyError(f"Meshy API {response.status_code}: {detail}")
