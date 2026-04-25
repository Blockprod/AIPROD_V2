"""
VisualInvariantsExtractor — deterministic extraction of visual invariants
from a reference image.

Produces a VisualInvariants object encoding the five priority tiers:
  P1. Subject identity (coverage, luminance fingerprint)
  P2. Lighting (key direction, colour temperature, contrast, exposure zones)
  P3. Camera / spatial coherence (height class, aspect ratio)
  P4. Depth layers (gradient magnitude by horizontal band)
  P5. Colour palette (k=5 LAB k-means, ranked by coverage)

All algorithms are deterministic:
  - k-means is run with fixed seed via a fully-deterministic Lloyd's algorithm
    on a spatially-sorted sample (no random init, no sklearn dependency).
  - Every floating-point operation is applied in the same order on identical input.
  - Luminance fingerprint uses MD5 of a fixed-size (32×32) L* raster.

Dependencies: Pillow (PIL), numpy
"""

from __future__ import annotations

import hashlib
from pathlib import Path

try:
    import numpy as np
    _HAS_NUMPY = True
except ImportError:
    _HAS_NUMPY = False

try:
    from PIL import Image
    _HAS_PILLOW = True
except ImportError:
    _HAS_PILLOW = False

from aiprod_adaptation.core.reference_image.models import (
    CameraHeightClass,
    ColorSwatch,
    DepthLayerEstimate,
    LightingAnalysis,
    LightingDirectionH,
    LightingDirectionV,
    VisualInvariants,
)
from aiprod_adaptation.core.reference_image.quality_gate import (
    _otsu_threshold,
    _rgb_to_lab_l,
    _sobel_magnitude,
    _to_grey_array,
)

# ---------------------------------------------------------------------------
# k-means configuration
# ---------------------------------------------------------------------------

_PALETTE_K: int    = 5
_KMEANS_ITERS: int = 20        # deterministic Lloyd iterations
_SAMPLE_SIZE: int  = 4096      # pixels sampled for palette (spatially regular grid)

# Variability classification thresholds
_INVARIANT_RANK_MAX:     int = 2   # ranks 1–2 → invariant
_SEMI_VARIABLE_RANK_MAX: int = 4   # ranks 3–4 → semi_variable


# ---------------------------------------------------------------------------
# Deterministic k-means (LAB space, fixed spatial sampling, no sklearn)
# ---------------------------------------------------------------------------

def _spatial_sample(pixels: np.ndarray, n: int) -> np.ndarray:
    """
    Draw n pixels from a (H*W, C) array using a spatially-regular grid stride.
    Deterministic: same input → same indices.
    """
    total = len(pixels)
    if total <= n:
        return pixels
    step = total // n
    indices = np.arange(0, total, step)[:n]
    return pixels[indices]


def _kmeans_lloyd(points: np.ndarray, k: int, n_iter: int) -> np.ndarray:
    """
    Deterministic Lloyd's algorithm.
    Initialises centroids by evenly-spaced indices in the sorted-by-L* sample.
    Returns (k, C) centroid array.
    """
    n, c = points.shape
    # Sort by first channel (L*) for deterministic init
    sorted_idx = np.argsort(points[:, 0])
    step = max(1, n // k)
    init_idx = [min(i * step, n - 1) for i in range(k)]
    centroids = points[sorted_idx[init_idx]].copy().astype("float32")

    for _ in range(n_iter):
        # Assign each point to nearest centroid
        diffs = points[:, np.newaxis, :] - centroids[np.newaxis, :, :]
        dists = np.sum(diffs ** 2, axis=2)
        labels = np.argmin(dists, axis=1)

        # Update centroids — use sorted order for determinism on empty clusters
        new_centroids = np.zeros_like(centroids)
        for ki in range(k):
            mask = labels == ki
            if np.any(mask):
                new_centroids[ki] = np.mean(points[mask], axis=0)
            else:
                # Empty cluster: retain previous centroid
                new_centroids[ki] = centroids[ki]
        centroids = new_centroids

    return centroids


def _rgb_to_lab_pixels(img_rgb: np.ndarray) -> np.ndarray:
    """
    Convert (H, W, 3) RGB uint8 image to (H*W, 3) LAB float32 pixels.
    Uses the same sRGB→XYZ→LAB pipeline as quality_gate._rgb_to_lab_l()
    but for all three channels.
    """
    rgb_f = img_rgb.astype("float32") / 255.0
    mask = rgb_f > 0.04045
    linear = np.where(mask, ((rgb_f + 0.055) / 1.055) ** 2.4, rgb_f / 12.92)

    r, g, b = linear[:, :, 0], linear[:, :, 1], linear[:, :, 2]

    # sRGB → XYZ D65
    x = 0.4124564 * r + 0.3575761 * g + 0.1804375 * b
    y = 0.2126729 * r + 0.7151522 * g + 0.0721750 * b
    z = 0.0193339 * r + 0.1191920 * g + 0.9503041 * b

    # Normalise by D65 white point
    xn, yn, zn = 0.95047, 1.00000, 1.08883
    xr, yr, zr = x / xn, y / yn, z / zn

    def _f(t: np.ndarray) -> np.ndarray:
        delta = 6.0 / 29.0
        return np.where(t > delta ** 3, np.cbrt(t), t / (3 * delta ** 2) + 4.0 / 29.0)

    fx, fy, fz = _f(xr), _f(yr), _f(zr)

    lab_l = 116.0 * fy - 16.0
    lab_a = 500.0 * (fx - fy)
    lab_b = 200.0 * (fy - fz)

    h, w = img_rgb.shape[:2]
    lab = np.stack([lab_l, lab_a, lab_b], axis=2).reshape(-1, 3).astype("float32")
    return lab


def _lab_to_hex(lab_centroid: np.ndarray) -> str:
    """Convert a [L, a, b] centroid back to sRGB hex string."""
    lab_l, lab_a, lab_b = float(lab_centroid[0]), float(lab_centroid[1]), float(lab_centroid[2])

    fy = (lab_l + 16.0) / 116.0
    fx = lab_a / 500.0 + fy
    fz = fy - lab_b / 200.0

    def _f_inv(t: float) -> float:
        delta = 6.0 / 29.0
        return t ** 3 if t > delta else 3 * delta ** 2 * (t - 4.0 / 29.0)

    xn, yn, zn = 0.95047, 1.00000, 1.08883
    x = _f_inv(fx) * xn
    y = _f_inv(fy) * yn
    z = _f_inv(fz) * zn

    # XYZ → linear sRGB (D65)
    r_lin =  3.2404542 * x - 1.5371385 * y - 0.4985314 * z
    g_lin = -0.9692660 * x + 1.8760108 * y + 0.0415560 * z
    b_lin =  0.0556434 * x - 0.2040259 * y + 1.0572252 * z

    def _gamma(c: float) -> int:
        c = max(0.0, min(1.0, c))
        if c <= 0.0031308:
            c = 12.92 * c
        else:
            c = 1.055 * (c ** (1.0 / 2.4)) - 0.055
        return int(round(c * 255.0))

    r8, g8, b8 = _gamma(r_lin), _gamma(g_lin), _gamma(b_lin)
    return f"#{r8:02x}{g8:02x}{b8:02x}"


# ---------------------------------------------------------------------------
# Lighting helpers
# ---------------------------------------------------------------------------

def _estimate_key_direction(l_channel: np.ndarray) -> tuple[LightingDirectionH, LightingDirectionV]:
    """
    Estimate the key-light direction by computing the centre of mass
    of the brightest 10% of pixels in L* channel.
    Returns (horizontal_class, vertical_class).
    """
    h, w = l_channel.shape
    threshold = float(np.percentile(l_channel, 90))
    bright_mask = l_channel >= threshold

    bright_coords = np.argwhere(bright_mask)  # (N, 2) — rows=y, cols=x
    if len(bright_coords) == 0:
        return LightingDirectionH.CENTER, LightingDirectionV.TOP

    mean_y = float(np.mean(bright_coords[:, 0]))  # row → vertical
    mean_x = float(np.mean(bright_coords[:, 1]))  # col → horizontal

    # Horizontal thirds
    if mean_x < w / 3.0:
        h_dir = LightingDirectionH.LEFT
    elif mean_x > 2.0 * w / 3.0:
        h_dir = LightingDirectionH.RIGHT
    else:
        h_dir = LightingDirectionH.CENTER

    # Vertical thirds (top = low row index)
    if mean_y < h / 3.0:
        v_dir = LightingDirectionV.TOP
    elif mean_y > 2.0 * h / 3.0:
        v_dir = LightingDirectionV.BOTTOM
    else:
        v_dir = LightingDirectionV.MIDDLE

    return h_dir, v_dir


def _estimate_color_temperature(img_rgb: np.ndarray, l_channel: np.ndarray) -> int:
    """
    Estimate approximate colour temperature (Kelvin) from the R/B ratio
    in the highlight zone (L* > 80).

    Warm (tungsten) ~ 2700–3200 K: R >> B (ratio > 2.0)
    Neutral daylight ~ 5500 K:     R ≈ B  (ratio ≈ 1.0)
    Cool (HMI/LED)  ~ 6500+ K:     B ≥ R  (ratio < 0.9)
    """
    highlight_mask = l_channel > 80
    if not np.any(highlight_mask):
        return 5500  # default: daylight

    r_vals = img_rgb[:, :, 0][highlight_mask].astype("float32")
    b_vals = img_rgb[:, :, 2][highlight_mask].astype("float32")

    mean_r = float(np.mean(r_vals))
    mean_b = float(np.mean(b_vals))

    if mean_b < 1.0:
        mean_b = 1.0

    rb_ratio = mean_r / mean_b

    # Piecewise linear mapping from R/B ratio to CCT (Kelvin)
    # Calibrated against tungsten/daylight/cool anchors
    if rb_ratio >= 2.0:
        cct = 2700
    elif rb_ratio >= 1.8:
        cct = int(2700 + (2.0 - rb_ratio) / (2.0 - 1.8) * 500)   # 2700–3200
    elif rb_ratio >= 1.2:
        cct = int(3200 + (1.8 - rb_ratio) / (1.8 - 1.2) * 2300)  # 3200–5500
    elif rb_ratio >= 0.9:
        cct = int(5500 + (1.2 - rb_ratio) / (1.2 - 0.9) * 1000)  # 5500–6500
    else:
        cct = 7000

    # Round to nearest 100 K for stable serialisation
    return int(round(cct / 100.0) * 100)


# ---------------------------------------------------------------------------
# Camera height estimation
# ---------------------------------------------------------------------------

def _estimate_camera_height(sobel_mag: np.ndarray) -> CameraHeightClass:
    """
    Estimate camera height class from the vertical distribution of gradient energy.

    Logic:
    - Eye-level:  gradient energy roughly uniform across rows.
    - Low angle:  higher gradient energy in the upper half (horizon is high).
    - High angle: higher gradient energy in the lower half (ground plane details).
    - Overhead:   extreme gradient energy in bottom 20% (looking straight down).

    Uses the ratio of upper-third to lower-third mean gradient magnitude.
    """
    h = sobel_mag.shape[0]
    h1, h2 = h // 3, 2 * (h // 3)

    top_mean    = float(np.mean(sobel_mag[:h1, :]))
    bottom_mean = float(np.mean(sobel_mag[h2:, :]))

    if top_mean < 1e-6 and bottom_mean < 1e-6:
        return CameraHeightClass.EYE_LEVEL

    ratio = top_mean / (bottom_mean + 1e-6)

    if ratio > 1.6:
        return CameraHeightClass.LOW_ANGLE      # high gradient in top → horizon high
    if ratio < 0.4:
        return CameraHeightClass.HIGH_ANGLE     # high gradient in bottom → looking down
    if ratio < 0.2:
        return CameraHeightClass.OVERHEAD
    return CameraHeightClass.EYE_LEVEL


# ---------------------------------------------------------------------------
# Depth layer estimation
# ---------------------------------------------------------------------------

def _estimate_depth_layers(sobel_mag: np.ndarray) -> DepthLayerEstimate:
    """
    Estimate depth complexity per horizontal band (foreground=bottom, background=top).
    The layer with highest mean gradient is the likely focal plane.
    """
    h = sobel_mag.shape[0]
    h1, h2 = h // 3, 2 * (h // 3)

    fg_mean = float(np.mean(sobel_mag[h2:, :]))    # bottom third
    mg_mean = float(np.mean(sobel_mag[h1:h2, :]))  # middle third
    bg_mean = float(np.mean(sobel_mag[:h1, :]))     # top third

    layer_means = {
        "foreground": fg_mean,
        "midground":  mg_mean,
        "background": bg_mean,
    }
    dominant = max(layer_means, key=lambda k: layer_means[k])

    return DepthLayerEstimate(
        gradient_mean_foreground=round(fg_mean, 2),
        gradient_mean_midground=round(mg_mean, 2),
        gradient_mean_background=round(bg_mean, 2),
        dominant_layer=dominant,
    )


# ---------------------------------------------------------------------------
# Aspect ratio helper
# ---------------------------------------------------------------------------

def _format_aspect_ratio(width: int, height: int) -> str:
    """Return a human-readable aspect ratio string, e.g. '16:9' or '2.39:1'."""
    # Check common standard ratios first (exact match)
    standard_ratios: list[tuple[float, str]] = [
        (16.0 / 9.0,    "16:9"),
        (4.0  / 3.0,    "4:3"),
        (2.39,          "2.39:1"),
        (2.35,          "2.35:1"),
        (1.85,          "1.85:1"),
        (1.78,          "16:9"),     # same as 16:9 numerically
        (1.33,          "4:3"),
        (1.0,           "1:1"),
        (9.0 / 16.0,    "9:16"),
    ]
    ratio = width / height
    for ref_ratio, label in standard_ratios:
        if abs(ratio - ref_ratio) < 0.02:
            return label
    # Fallback: reduced fraction
    def gcd(a: int, b: int) -> int:
        while b:
            a, b = b, a % b
        return a
    g = gcd(width, height)
    return f"{width // g}:{height // g}"


# ---------------------------------------------------------------------------
# Luminance fingerprint
# ---------------------------------------------------------------------------

def _luminance_fingerprint(l_channel: np.ndarray) -> str:
    """
    Compute an MD5 fingerprint of a 32×32 downsampled, quantised L* map.
    Deterministic: identical pixel content → identical hash.
    """
    from PIL import Image as _Image
    # Downscale to 32×32 using Lanczos (deterministic in Pillow ≥ 9)
    h, w = l_channel.shape
    # Round L* to 1 decimal place before hashing for fp stability
    l_uint8 = np.clip(l_channel, 0, 100).astype("uint8")
    pil_l = _Image.fromarray(l_uint8, mode="L").resize((32, 32), resample=_Image.Resampling.LANCZOS)
    raw = bytes(pil_l.tobytes())
    return hashlib.md5(raw).hexdigest()


# ---------------------------------------------------------------------------
# VisualInvariantsExtractor
# ---------------------------------------------------------------------------

class VisualInvariantsExtractor:
    """
    Extracts all deterministic visual invariants from a reference image.

    Prerequisites
    -------------
    The image must have passed ReferenceQualityGate.check() with `.passed == True`.
    Calling extract() on a rejected image is legal but may yield unreliable results.

    Parameters
    ----------
    palette_k : int
        Number of palette clusters (default 5, max 8).
    """

    def __init__(self, palette_k: int = _PALETTE_K) -> None:
        if not _HAS_PILLOW or not _HAS_NUMPY:
            raise ImportError(
                "VisualInvariantsExtractor requires Pillow and numpy. "
                "Install them with: pip install Pillow numpy"
            )
        if not (2 <= palette_k <= 8):
            raise ValueError(f"palette_k must be in [2, 8], got {palette_k}.")
        self.palette_k = palette_k

    def extract(self, image_path: str | Path) -> VisualInvariants:
        """
        Extract visual invariants from a reference image.

        Parameters
        ----------
        image_path : str or Path

        Returns
        -------
        VisualInvariants

        Raises
        ------
        ValueError  if the image cannot be loaded.
        """
        path_str = str(image_path)
        pil_img  = Image.open(image_path).convert("RGB")
        width, height = pil_img.size
        img_rgb  = np.array(pil_img, dtype="uint8")

        # --- Derived channels (reused across extractors) ---
        grey      = _to_grey_array(img_rgb)
        grey_u8   = grey.astype("uint8")
        l_channel = _rgb_to_lab_l(img_rgb)
        sobel_mag = _sobel_magnitude(grey)

        # --- P1: Subject identity ---
        otsu_t = _otsu_threshold(grey_u8)
        subject_coverage_pct = float(np.sum(grey_u8 <= otsu_t)) / grey_u8.size * 100.0
        fingerprint = _luminance_fingerprint(l_channel)

        # --- P2: Lighting ---
        h_dir, v_dir        = _estimate_key_direction(l_channel)
        color_temp_k        = _estimate_color_temperature(img_rgb, l_channel)
        intensity_l95       = float(np.percentile(l_channel, 95))
        contrast_std_l      = float(np.std(l_channel))
        total_px            = float(l_channel.size)
        highlight_pct       = float(np.sum(l_channel > 90)) / total_px * 100.0
        shadow_pct          = float(np.sum(l_channel < 10)) / total_px * 100.0

        lighting = LightingAnalysis(
            key_direction_h=h_dir,
            key_direction_v=v_dir,
            color_temperature_k=color_temp_k,
            intensity_l95=round(intensity_l95, 2),
            contrast_std_l=round(contrast_std_l, 2),
            highlight_pct=round(highlight_pct, 2),
            shadow_pct=round(shadow_pct, 2),
        )

        # --- P3: Camera / spatial coherence ---
        camera_height = _estimate_camera_height(sobel_mag)
        aspect_ratio  = _format_aspect_ratio(width, height)

        # --- P4: Depth layers ---
        depth_layers = _estimate_depth_layers(sobel_mag)

        # --- P5: Palette (deterministic k-means in LAB) ---
        palette = self._extract_palette(img_rgb)

        return VisualInvariants(
            source_path=path_str,
            width_px=width,
            height_px=height,
            aspect_ratio=aspect_ratio,
            subject_coverage_pct=round(subject_coverage_pct, 2),
            luminance_fingerprint=fingerprint,
            lighting=lighting,
            camera_height_class=camera_height,
            depth_layers=depth_layers,
            palette=palette,
        )

    # ------------------------------------------------------------------
    # Palette extraction
    # ------------------------------------------------------------------

    def _extract_palette(self, img_rgb: np.ndarray) -> list[ColorSwatch]:
        """
        Extract up to `palette_k` dominant colours via deterministic LAB k-means.

        Steps:
        1. Convert to LAB pixel array.
        2. Spatially-regular sample of _SAMPLE_SIZE pixels.
        3. Lloyd's k-means with fixed init (sorted by L*).
        4. Count cluster memberships for coverage estimation.
        5. Sort clusters by coverage (descending) → rank.
        6. Assign variability class by rank.
        """
        lab_pixels = _rgb_to_lab_pixels(img_rgb)             # (H*W, 3)
        sample     = _spatial_sample(lab_pixels, _SAMPLE_SIZE)
        centroids  = _kmeans_lloyd(sample, self.palette_k, _KMEANS_ITERS)

        # Assign all pixels to nearest centroid for coverage count
        diffs  = lab_pixels[:, np.newaxis, :] - centroids[np.newaxis, :, :]
        dists  = np.sum(diffs ** 2, axis=2)
        labels = np.argmin(dists, axis=1)

        total = len(lab_pixels)
        coverage = [float(np.sum(labels == ki)) / total * 100.0
                    for ki in range(self.palette_k)]

        # Sort by coverage descending (deterministic: ties broken by centroid L* ascending)
        order = sorted(
            range(self.palette_k),
            key=lambda ki: (-coverage[ki], float(centroids[ki][0])),
        )

        swatches: list[ColorSwatch] = []
        for rank_zero, ki in enumerate(order):
            rank      = rank_zero + 1
            hex_code  = _lab_to_hex(centroids[ki])
            lab_vals  = [round(float(centroids[ki][0]), 2),
                         round(float(centroids[ki][1]), 2),
                         round(float(centroids[ki][2]), 2)]
            if rank <= _INVARIANT_RANK_MAX:
                variability = "invariant"
            elif rank <= _SEMI_VARIABLE_RANK_MAX:
                variability = "semi_variable"
            else:
                variability = "variable"

            swatches.append(ColorSwatch(
                rank=rank,
                hex_code=hex_code,
                lab=lab_vals,
                coverage_pct=round(coverage[ki], 2),
                variability=variability,
            ))

        return swatches
