"""
aiprod_adaptation/image_gen/triposg_adapter.py
===============================================
Adaptateur TripoSG local -- generation de mesh 3D GLB depuis une image.

Modele : VAST-AI/TripoSG (1.5B params, rectified flow transformer)
Source : https://github.com/VAST-AI-Research/TripoSG
Licence : MIT

PREREQUIS (a faire une seule fois) :
    git clone https://github.com/VAST-AI-Research/TripoSG.git third_party/triposg
    cd third_party/triposg
    pip install torch torchvision --index-url https://download.pytorch.org/whl/cu121
    pip install -r requirements.txt

Les poids (VAST-AI/TripoSG sur HuggingFace) se telechargent automatiquement
au premier lancement (~2 Go).

SYSTEME REQUIS :
    GPU CUDA avec 8 Go+ VRAM minimum (GTX 1070 8 Go : limite, RTX 5080 : optimal)

ENV :
    TRIPOSG_DIR   chemin vers le repo TripoSG clone
                  defaut : {workspace}/third_party/triposg

COUT : gratuit (inference locale)

Usage direct :
    adapter = TripoSGAdapter()
    glb_path = adapter.generate(
        image_path=Path("nara_front.png"),
        output_path=Path("nara_rodin.glb"),
    )
"""
from __future__ import annotations

import os
import subprocess
import sys
from pathlib import Path

import structlog

# Racine du workspace (remonte de image_gen/ -> aiprod_adaptation/ -> workspace/)
_WORKSPACE_ROOT = Path(__file__).resolve().parent.parent.parent

_DEFAULT_TRIPOSG_DIR = _WORKSPACE_ROOT / "third_party" / "triposg"
logger = structlog.get_logger(__name__)


class TripoSGError(RuntimeError):
    """Erreur TripoSG (installation manquante, inference echouee, etc.)."""


class TripoSGAdapter:
    """Wrapper autour de l'inference TripoSG locale (subprocess).

    L'inference est lancee dans le repertoire TripoSG via subprocess pour
    isoler ses dependances (torch, diffusers) du venv principal.
    """

    def __init__(self, triposg_dir: str | Path | None = None) -> None:
        raw = triposg_dir or os.environ.get("TRIPOSG_DIR", str(_DEFAULT_TRIPOSG_DIR))
        self.triposg_dir = Path(raw).resolve()
        self._check_installation()

    # ------------------------------------------------------------------
    # Public API
    # ------------------------------------------------------------------

    def generate(
        self,
        image_path: Path,
        output_path: Path,
        num_faces: int | None = None,
    ) -> Path:
        """Genere un GLB depuis une image via TripoSG.

        Args:
            image_path:  Image source (PNG/JPG). Vue frontale recommandee.
            output_path: Chemin de sortie du fichier GLB.
            num_faces:   Limite le nombre de faces (None = defaut TripoSG ~50k).

        Returns:
            Chemin vers le GLB genere (== output_path).

        Raises:
            TripoSGError si l'inference echoue.
        """
        output_path.parent.mkdir(parents=True, exist_ok=True)

        python_exe = self._find_python()
        cmd: list[str] = [
            python_exe,
            "-m", "scripts.inference_triposg",
            "--image-input", str(image_path.resolve()),
            "--output-path", str(output_path.resolve()),
        ]
        if num_faces is not None:
            cmd += ["--faces", str(num_faces)]

        logger.info(
            "triposg_inference_start",
            image=image_path.name,
            output=output_path.name,
            min_vram_gb=8,
            recommended_gpu="RTX 5080",
        )

        result = subprocess.run(
            cmd,
            cwd=str(self.triposg_dir),
            capture_output=False,
        )
        if result.returncode != 0:
            raise TripoSGError(
                f"TripoSG inference echouee (code {result.returncode}) "
                f"pour {image_path}"
            )

        if not output_path.exists():
            raise TripoSGError(
                f"TripoSG n'a pas produit de GLB a {output_path}. "
                f"Verifier les logs ci-dessus."
            )

        return output_path

    def is_available(self) -> bool:
        """Retourne True si TripoSG est installe et pret."""
        try:
            self._check_installation()
            return True
        except TripoSGError:
            return False

    # ------------------------------------------------------------------
    # Private helpers
    # ------------------------------------------------------------------

    def _check_installation(self) -> None:
        """Verifie que le repo TripoSG est clone et les scripts presents."""
        if not self.triposg_dir.exists():
            raise TripoSGError(
                f"TripoSG introuvable dans {self.triposg_dir}.\n"
                f"Installer avec :\n"
                f"  git clone https://github.com/VAST-AI-Research/TripoSG.git "
                f"{self.triposg_dir}\n"
                f"  cd {self.triposg_dir}\n"
                f"  pip install torch torchvision --index-url "
                f"https://download.pytorch.org/whl/cu121\n"
                f"  pip install -r requirements.txt"
            )
        inference_script = self.triposg_dir / "scripts" / "inference_triposg.py"
        if not inference_script.exists():
            raise TripoSGError(
                f"Script TripoSG introuvable : {inference_script}.\n"
                f"Le repo semble incomplet. Recloner depuis :\n"
                f"  https://github.com/VAST-AI-Research/TripoSG"
            )

    def _find_python(self) -> str:
        """Retourne le chemin Python a utiliser pour lancer TripoSG.

        Priorite :
          1. TRIPOSG_PYTHON env var (venv TripoSG dedie si necessaire)
          2. Python courant (sys.executable) -- si TripoSG installe dans le venv
        """
        custom = os.environ.get("TRIPOSG_PYTHON", "")
        if custom:
            return custom
        return sys.executable
