"""
ReferenceQualityGate — deterministic quality validation for reference images.

Evaluates an image file against five structural criteria and produces a
ReferenceQualityReport with a composite score and hard-rejection flags.

Composite score formula (weights sum to 1.0):
    score = 0.30 * S_clarity
          + 0.25 * S_lighting
          + 0.20 * S_subject
          + 0.15 * S_depth
          + 0.10 * S_composition

Hard-rejection rules (score ignored if triggered):
    RESOLUTION_TOO_LOW    — image shorter than MIN_DIMENSION on either axis
    TOO_BLURRY            — normalised Laplacian variance < BLUR_THRESHOLD
    OVEREXPOSED           — more than MAX_EXPOSURE_PCT pixels with L* > 95
    UNDEREXPOSED          — more than MAX_EXPOSURE_PCT pixels with L* < 5
    LOW_INFORMATION       — global Shannon entropy < MIN_ENTROPY_BITS
    MONOCHROMATIC_INPUT   — inter-channel RGB variance < MIN_CHANNEL_VARIANCE
    LOAD_ERROR            — image cannot be opened or decoded

Pass threshold: composite_score >= DEFAULT_PASS_THRESHOLD (0.65)
Warning band:   composite_score in [WARNING_THRESHOLD, DEFAULT_PASS_THRESHOLD) → PASS with warnings
Reject:         composite_score < WARNING_THRESHOLD (0.50) OR any hard rejection

All computation is deterministic: identical input → identical output.
No model inference, no randomness, no external network calls.

Dependencies: Pillow (PIL), numpy
OpenCV (cv2) is used when available; Pillow-only fallback is provided.
"""

from __future__ import annotations

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
    QualityComponentScores,
    ReferenceQualityReport,
    RejectionReason,
)

# ---------------------------------------------------------------------------
# Thresholds (all configurable at instantiation time)
# ---------------------------------------------------------------------------

MIN_DIMENSION: int        = 512           # px — minimum on both axes
BLUR_THRESHOLD: float     = 0.01          # normalised Laplacian variance
MAX_EXPOSURE_PCT: float   = 40.0          # % of pixels allowed in clipped zones
MIN_ENTROPY_BITS: float   = 3.0           # global Shannon entropy lower bound
MIN_CHANNEL_VARIANCE: float = 100.0       # inter-channel RGB variance lower bound
DEFAULT_PASS_THRESHOLD: float  = 0.65
WARNING_THRESHOLD: float       = 0.50

# Composite score weights (must sum to 1.0)
W_CLARITY:     float = 0.30
W_LIGHTING:    float = 0.25
W_SUBJECT:     float = 0.20
W_DEPTH:       float = 0.15
W_COMPOSITION: float = 0.10


# ---------------------------------------------------------------------------
# Internal pixel helpers (Pillow + numpy, no cv2 required)
# ---------------------------------------------------------------------------

def _to_grey_array(img_rgb: np.ndarray) -> np.ndarray:
    """Convert RGB uint8 array to greyscale float32 via BT.601 luma."""
    return (
        0.299 * img_rgb[:, :, 0].astype("float32")
        + 0.587 * img_rgb[:, :, 1].astype("float32")
        + 0.114 * img_rgb[:, :, 2].astype("float32")
    )


def _laplacian_variance(grey: np.ndarray) -> float:
    """
    Compute the variance of the discrete Laplacian.
    Standard blur-detection estimator (Pech-Pacheco et al., 2000).
    Pure numpy 2D convolution with 3×3 Laplacian kernel.
    """
    kernel = np.array([
        [0,  1, 0],
        [1, -4, 1],
        [0,  1, 0],
    ], dtype="float32")
    # Manual 2D convolution via sliding window (no scipy dependency)
    # Using numpy stride tricks for performance
    h, w = grey.shape
    padded = np.pad(grey, 1, mode="reflect")
    lap = np.zeros((h, w), dtype="float32")
    for dy in range(3):
        for dx in range(3):
            lap += kernel[dy, dx] * padded[dy:dy + h, dx:dx + w]
    return float(np.var(lap))


def _rgb_to_lab_l(img_rgb: np.ndarray) -> np.ndarray:
    """
    Convert RGB uint8 image to CIE L* channel (float32, range [0, 100]).
    Uses sRGB → linear → XYZ → L* conversion (deterministic, no cv2 needed).
    """
    # sRGB linearisation (IEC 61966-2-1)
    rgb_f = img_rgb.astype("float32") / 255.0
    mask = rgb_f > 0.04045
    linear = np.where(mask, ((rgb_f + 0.055) / 1.055) ** 2.4, rgb_f / 12.92)
    # sRGB → XYZ D65 (ITU-R BT.709 primaries)
    r, g, b = linear[:, :, 0], linear[:, :, 1], linear[:, :, 2]
    y = 0.2126 * r + 0.7152 * g + 0.0722 * b   # Y/Yn
    # D65 illuminant Yn = 1.0 → Y directly usable
    # L* from Y
    epsilon = 0.008856
    l_star = np.where(y > epsilon, 116.0 * np.cbrt(y) - 16.0, 903.3 * y)
    return l_star.astype("float32")


def _shannon_entropy(hist: np.ndarray) -> float:
    """Shannon entropy in bits from a normalised histogram array."""
    p = hist[hist > 0]
    return float(-np.sum(p * np.log2(p)))


def _image_entropy(grey: np.ndarray) -> float:
    """Global Shannon entropy of a greyscale image [0, 255]."""
    hist, _ = np.histogram(grey.ravel(), bins=256, range=(0, 256))
    total = hist.sum()
    if total == 0:
        return 0.0
    p = hist / total
    return _shannon_entropy(p)


def _sobel_magnitude(grey: np.ndarray) -> np.ndarray:
    """
    Compute Sobel gradient magnitude using numpy convolutions.
    Returns float32 array of same shape as grey.
    """
    h, w = grey.shape
    padded = np.pad(grey, 1, mode="reflect")
    # Sobel kernels
    kx = np.array([[-1, 0, 1], [-2, 0, 2], [-1, 0, 1]], dtype="float32")
    ky = np.array([[-1, -2, -1], [0, 0, 0], [1, 2, 1]], dtype="float32")
    gx = np.zeros((h, w), dtype="float32")
    gy = np.zeros((h, w), dtype="float32")
    for dy in range(3):
        for dx in range(3):
            gx += kx[dy, dx] * padded[dy:dy + h, dx:dx + w]
            gy += ky[dy, dx] * padded[dy:dy + h, dx:dx + w]
    result: np.ndarray = np.sqrt(gx ** 2 + gy ** 2)
    return result


def _otsu_threshold(grey: np.ndarray) -> int:
    """
    Compute Otsu binarisation threshold (deterministic, numpy-only implementation).
    Returns threshold value in [0, 255].
    """
    hist, _ = np.histogram(grey.ravel(), bins=256, range=(0, 256))
    total = float(hist.sum())
    if total == 0:
        return 128

    sum_all = float(np.dot(np.arange(256, dtype="float64"), hist))
    sum_b = 0.0
    w_b = 0.0
    max_var = 0.0
    threshold = 0

    for t in range(256):
        w_b += hist[t]
        if w_b == 0:
            continue
        w_f = total - w_b
        if w_f == 0:
            break
        sum_b += t * hist[t]
        mu_b = sum_b / w_b
        mu_f = (sum_all - sum_b) / w_f
        var = w_b * w_f * (mu_b - mu_f) ** 2
        if var > max_var:
            max_var = var
            threshold = t

    return threshold


def _thirds_entropy(grey: np.ndarray) -> float:
    """
    Compute the mean Shannon entropy across the 9 cells of a rule-of-thirds grid.
    Higher values = more compositional information distributed across cells.
    """
    h, w = grey.shape
    h1, h2 = h // 3, 2 * (h // 3)
    w1, w2 = w // 3, 2 * (w // 3)

    row_bands = [(0, h1), (h1, h2), (h2, h)]
    col_bands = [(0, w1), (w1, w2), (w2, w)]

    entropies = []
    for r0, r1 in row_bands:
        for c0, c1 in col_bands:
            cell = grey[r0:r1, c0:c1]
            if cell.size == 0:
                continue
            hist, _ = np.histogram(cell.ravel(), bins=64, range=(0, 256))
            total = hist.sum()
            if total > 0:
                p = hist / total
                entropies.append(_shannon_entropy(p))
    return float(np.mean(entropies)) if entropies else 0.0


# ---------------------------------------------------------------------------
# Score computation
# ---------------------------------------------------------------------------

def _score_clarity(lap_var: float, max_lap: float = 2000.0) -> float:
    """Normalise Laplacian variance to [0, 1]. Soft-clamp at max_lap."""
    return min(1.0, lap_var / max_lap)


def _score_lighting(l_channel: np.ndarray) -> float:
    """
    Fraction of pixels in usable luminance zone [10, 90] L* mapped to [0, 1].
    Penalises blown highlights and crushed blacks.
    """
    total: int = int(l_channel.size)
    if total == 0:
        return 0.0
    usable = float(np.sum((l_channel >= 10) & (l_channel <= 90)))
    return usable / total


def _score_subject(grey: np.ndarray, otsu_thresh: int) -> float:
    """
    Otsu foreground ratio mapped to a bell-curve score peaked at 30–60% coverage.
    Too small a subject (< 5%) or too large (> 90%) both score lower.
    """
    total: int = int(grey.size)
    if total == 0:
        return 0.0
    fg_ratio = float(np.sum(grey <= otsu_thresh)) / total
    # Ideal coverage 20–70%, bell-curve via triangular approximation
    if fg_ratio < 0.05 or fg_ratio > 0.95:
        return 0.2
    if 0.20 <= fg_ratio <= 0.70:
        return 1.0
    if fg_ratio < 0.20:
        return 0.2 + (fg_ratio - 0.05) / (0.20 - 0.05) * 0.8
    # fg_ratio > 0.70
    return 1.0 - (fg_ratio - 0.70) / (0.95 - 0.70) * 0.8


def _score_depth(sobel_mag: np.ndarray) -> float:
    """
    Coefficient of variation (std/mean) of gradient magnitude — estimator for
    depth complexity. Normalised to [0, 1], soft-clamped at CV = 1.5.
    """
    mean_g = float(np.mean(sobel_mag))
    if mean_g < 1e-6:
        return 0.0
    cv = float(np.std(sobel_mag)) / mean_g
    return min(1.0, cv / 1.5)


def _score_composition(thirds_ent: float, max_ent: float = 6.0) -> float:
    """Normalised thirds-entropy score [0, 1]."""
    return min(1.0, thirds_ent / max_ent)


# ---------------------------------------------------------------------------
# ReferenceQualityGate
# ---------------------------------------------------------------------------

class ReferenceQualityGate:
    """
    Deterministic quality gate for reference images.

    Parameters
    ----------
    pass_threshold : float
        Minimum composite score for a PASS verdict (default 0.65).
    warning_threshold : float
        Score below pass_threshold but above this generates PASS with warnings
        (default 0.50). Below → hard FAIL.
    min_dimension : int
        Minimum pixel dimension on both axes (default 512).
    """

    def __init__(
        self,
        pass_threshold: float = DEFAULT_PASS_THRESHOLD,
        warning_threshold: float = WARNING_THRESHOLD,
        min_dimension: int = MIN_DIMENSION,
    ) -> None:
        if not _HAS_PILLOW or not _HAS_NUMPY:
            raise ImportError(
                "ReferenceQualityGate requires Pillow and numpy. "
                "Install them with: pip install Pillow numpy"
            )
        self.pass_threshold = pass_threshold
        self.warning_threshold = warning_threshold
        self.min_dimension = min_dimension

    def check(self, image_path: str | Path) -> ReferenceQualityReport:
        """
        Analyse a reference image and produce a quality report.

        Parameters
        ----------
        image_path : str or Path
            Absolute or relative path to the image file.

        Returns
        -------
        ReferenceQualityReport
            Full quality assessment. Check `.passed` and `.rejection_reasons`.
        """
        path_str = str(image_path)
        rejections: list[RejectionReason] = []
        warnings: list[str] = []

        # --- Load image ---
        try:
            pil_img = Image.open(image_path).convert("RGB")
        except Exception as exc:
            return self._reject_report(
                path_str,
                rejections=[RejectionReason.LOAD_ERROR],
                reason=f"Cannot open image: {exc}",
            )

        width, height = pil_img.size
        img_rgb = np.array(pil_img, dtype="uint8")

        # --- Hard check: resolution ---
        if width < self.min_dimension or height < self.min_dimension:
            rejections.append(RejectionReason.RESOLUTION_TOO_LOW)

        # --- Derive channels ---
        grey = _to_grey_array(img_rgb)                     # [0, 255] float32
        l_channel = _rgb_to_lab_l(img_rgb)                 # [0, 100] float32
        sobel_mag = _sobel_magnitude(grey)

        # --- Hard check: blur ---
        lap_var = _laplacian_variance(grey)
        # Normalise by image mean^2 for scale invariance
        mean_intensity = float(np.mean(grey))
        if mean_intensity < 1.0:
            mean_intensity = 1.0
        normalised_lap_var = lap_var / (mean_intensity ** 2)
        if normalised_lap_var < BLUR_THRESHOLD:
            rejections.append(RejectionReason.TOO_BLURRY)

        # --- Hard check: exposure ---
        total_px = float(l_channel.size)
        highlight_pct = float(np.sum(l_channel > 95)) / total_px * 100.0
        shadow_pct    = float(np.sum(l_channel < 5))  / total_px * 100.0
        if highlight_pct > MAX_EXPOSURE_PCT:
            rejections.append(RejectionReason.OVEREXPOSED)
        if shadow_pct > MAX_EXPOSURE_PCT:
            rejections.append(RejectionReason.UNDEREXPOSED)

        # --- Hard check: information entropy ---
        grey_uint8 = grey.astype("uint8")
        entropy = _image_entropy(grey_uint8)
        if entropy < MIN_ENTROPY_BITS:
            rejections.append(RejectionReason.LOW_INFORMATION)

        # --- Hard check: monochromatic input ---
        channel_means = [float(np.mean(img_rgb[:, :, c])) for c in range(3)]
        channel_var = float(np.var(channel_means))
        if channel_var < MIN_CHANNEL_VARIANCE:
            rejections.append(RejectionReason.MONOCHROMATIC_INPUT)

        # --- Component scores ---
        otsu_t = _otsu_threshold(grey_uint8)
        thirds_ent = _thirds_entropy(grey_uint8)

        s_clarity     = _score_clarity(lap_var)
        s_lighting    = _score_lighting(l_channel)
        s_subject     = _score_subject(grey_uint8, otsu_t)
        s_depth       = _score_depth(sobel_mag)
        s_composition = _score_composition(thirds_ent)

        composite = (
            W_CLARITY     * s_clarity
            + W_LIGHTING    * s_lighting
            + W_SUBJECT     * s_subject
            + W_DEPTH       * s_depth
            + W_COMPOSITION * s_composition
        )

        # --- Soft warnings ---
        if highlight_pct > 20.0:
            warnings.append(f"Significant highlights: {highlight_pct:.1f}% of pixels >L*95.")
        if shadow_pct > 20.0:
            warnings.append(f"Significant shadows: {shadow_pct:.1f}% of pixels <L*5.")
        if s_clarity < 0.4:
            warnings.append(
                f"Low sharpness score ({s_clarity:.2f}). "
                "Image may produce inconsistent prompt anchoring."
            )
        if channel_var < 500.0:
            warnings.append(
                f"Low inter-channel colour variance ({channel_var:.0f}). "
                "Palette extraction may yield limited diversity."
            )
        if composite >= self.pass_threshold and composite < self.pass_threshold + 0.10:
            warnings.append(
                f"Score ({composite:.3f}) is close to the pass threshold "
                f"({self.pass_threshold}). Consider a higher-quality reference."
            )

        # --- Verdict ---
        if rejections:
            passed = False
        elif composite < self.warning_threshold:
            passed = False
        else:
            passed = True

        # Emit warning for score in warning band
        if not rejections and self.warning_threshold <= composite < self.pass_threshold:
            passed = False  # below pass threshold → FAIL (not just warn)
            warnings.insert(
                0,
                f"Score {composite:.3f} below pass threshold {self.pass_threshold}. "
                f"Minimum acceptable is {self.warning_threshold} (warning band).",
            )

        recommendation = self._build_recommendation(passed, rejections, composite)

        return ReferenceQualityReport(
            source_path=path_str,
            passed=passed,
            composite_score=round(composite, 4),
            component_scores=QualityComponentScores(
                clarity=round(s_clarity, 4),
                lighting=round(s_lighting, 4),
                subject=round(s_subject, 4),
                depth=round(s_depth, 4),
                composition=round(s_composition, 4),
            ),
            rejection_reasons=rejections,
            warnings=warnings,
            threshold_used=self.pass_threshold,
            recommendation=recommendation,
        )

    # ------------------------------------------------------------------
    # Internal helpers
    # ------------------------------------------------------------------

    @staticmethod
    def _build_recommendation(
        passed: bool,
        rejections: list[RejectionReason],
        score: float,
    ) -> str:
        if passed:
            return "Reference image approved. Proceed with invariant extraction."
        if RejectionReason.RESOLUTION_TOO_LOW in rejections:
            return (
                f"Upscale image to at least {MIN_DIMENSION}×{MIN_DIMENSION} px "
                "or provide a higher-resolution source."
            )
        if RejectionReason.TOO_BLURRY in rejections:
            return (
                "Image is too blurry for reliable invariant extraction. "
                "Provide a sharper frame or keyframe."
            )
        if RejectionReason.OVEREXPOSED in rejections:
            return "Reduce exposure or use a differently-lit reference frame."
        if RejectionReason.UNDEREXPOSED in rejections:
            return "Increase exposure or use a better-lit reference frame."
        if RejectionReason.LOW_INFORMATION in rejections:
            return (
                "Image contains insufficient visual information (nearly blank/solid). "
                "Provide a content-rich reference frame."
            )
        if RejectionReason.MONOCHROMATIC_INPUT in rejections:
            return (
                "Image appears monochromatic. "
                "Provide a colour reference for palette extraction."
            )
        if RejectionReason.LOAD_ERROR in rejections:
            return "Check file path and ensure image is a valid JPEG, PNG, TIFF, or WebP."
        return (
            f"Composite score {score:.3f} below minimum {DEFAULT_PASS_THRESHOLD}. "
            "Use a higher-quality, well-lit, in-focus reference frame."
        )

    def _reject_report(
        self,
        path_str: str,
        rejections: list[RejectionReason],
        reason: str,
    ) -> ReferenceQualityReport:
        return ReferenceQualityReport(
            source_path=path_str,
            passed=False,
            composite_score=0.0,
            component_scores=QualityComponentScores(
                clarity=0.0, lighting=0.0, subject=0.0,
                depth=0.0, composition=0.0,
            ),
            rejection_reasons=rejections,
            warnings=[],
            threshold_used=self.pass_threshold,
            recommendation=reason,
        )
