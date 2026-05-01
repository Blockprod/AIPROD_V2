"""
CharacterMask — removes background from a character portrait using rembg,
producing an RGBA PNG with the character opaque and the background transparent.

This RGBA "edit base" is used by OpenAIImageAdapter.generate_edit() to call
images.edit — OpenAI fills the transparent region with the scene prompt while
preserving the character's exact appearance.

Dependency: rembg (lazy import — only required when this module is actually used).
    pip install rembg  (or include in pyproject.toml [image] optional-dependencies)
"""

from __future__ import annotations

import io


def remove_background(image_bytes: bytes) -> bytes:
    """Return RGBA PNG bytes with background removed (alpha=0).

    Uses rembg with the u2net model (default). First call downloads the model
    weights (~170 MB) and caches them in ~/.u2net/.

    Args:
        image_bytes: Raw bytes of the source image (PNG, JPEG, etc.)

    Returns:
        RGBA PNG bytes where the subject is opaque and the background is
        fully transparent (alpha=0), ready for use with images.edit masking.

    Raises:
        ImportError: if rembg is not installed.
        RuntimeError: if background removal fails unexpectedly.
    """
    try:
        from rembg import remove as rembg_remove
    except ImportError as exc:
        raise ImportError(
            "rembg is required for character mask generation. "
            "Install it with: pip install rembg"
        ) from exc

    try:
        result_bytes: bytes = rembg_remove(image_bytes)
    except Exception as exc:
        raise RuntimeError(f"Background removal failed: {exc}") from exc

    return result_bytes


def build_edit_mask(rgba_bytes: bytes) -> bytes:
    """Convert an RGBA character image into an images.edit mask.

    OpenAI images.edit convention:
      - Mask alpha=0   (transparent) → region to REGENERATE (fill with scene)
      - Mask alpha=255 (opaque)      → region to PRESERVE (keep character pixels)

    rembg convention (rgba_bytes):
      - Alpha=0   → background (should be regenerated)
      - Alpha=255 → character  (should be preserved)

    The RGBA image from rembg is therefore directly usable as both the `image`
    and the `mask` for images.edit without any inversion:
      - The character pixels (alpha=255) are preserved.
      - The transparent background (alpha=0) is regenerated from the prompt.

    This function is a no-op pass-through kept for clarity and future extension
    (e.g. feathering edges, resizing, format conversion).

    Args:
        rgba_bytes: RGBA PNG bytes from remove_background().

    Returns:
        RGBA PNG bytes ready to pass as both image= and mask= to images.edit.
    """
    try:
        from PIL import Image
    except ImportError as exc:
        raise ImportError(
            "Pillow is required for mask building. "
            "Install it with: pip install Pillow"
        ) from exc

    img = Image.open(io.BytesIO(rgba_bytes)).convert("RGBA")
    buf = io.BytesIO()
    img.save(buf, format="PNG")
    return buf.getvalue()
