# pipeline — locked hybrid production method v2
# FLUX.2 Pro (master plate) + Flux Fill Pro v5 (face inpainting)
# Score ArcFace record : 0.9378 | Coût : $0.08/shot
from .shot_pipeline import run_shot, LOCKED_NARA_CANONICAL, LOCKED_PARAMS

__all__ = ["run_shot", "LOCKED_NARA_CANONICAL", "LOCKED_PARAMS"]
