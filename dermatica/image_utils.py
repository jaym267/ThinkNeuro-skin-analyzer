# -*- coding: utf-8 -*-
"""Image encoding + upload validation/decoding helpers."""
import base64
import io

from PIL import Image, ImageFilter, ImageStat

from . import config

# Refuse to even decode absurdly large images (Pillow decompression-bomb guard).
Image.MAX_IMAGE_PIXELS = config.MAX_IMAGE_PIXELS


def image_to_base64(img: Image.Image) -> str:
    buf = io.BytesIO()
    img.save(buf, format="JPEG", quality=90)
    return base64.b64encode(buf.getvalue()).decode()

def image_to_thumbnail_base64(img: Image.Image, max_dim: int = 160, quality: int = 60) -> str:
    """Downscale to a small JPEG thumbnail and base64-encode it -- for DB
    storage in analyses.image_thumbnail_b64 (Phase 7's persistence wiring).
    Deliberately much smaller than image_to_base64()'s full-resolution
    output: storing a full-res image per analysis row would bloat row size
    and DB egress, which Phase 2's schema bootstrap comment calls out as an
    explicit constraint to avoid. Operates on a copy so the caller's
    full-resolution image (still needed for display/vision calls) is
    untouched."""
    thumb = img.copy()
    thumb.thumbnail((max_dim, max_dim))
    buf = io.BytesIO()
    thumb.save(buf, format="JPEG", quality=quality)
    return base64.b64encode(buf.getvalue()).decode()

def load_validated_image(uploaded_file):
    """Validate and safely decode an uploaded image.
    Returns (PIL.Image or None, error_message). Rejects oversized, malformed,
    or decompression-bomb files and downscales very large images."""
    size = getattr(uploaded_file, "size", None)
    if size is not None and size > config.MAX_UPLOAD_MB * 1024 * 1024:
        return None, f"That image is too large ({size/1_000_000:.1f} MB). Please upload one under {config.MAX_UPLOAD_MB} MB."

    data = uploaded_file.getvalue()
    if not data:
        return None, "That file is empty. Please upload a valid image."

    # First pass: verify the bytes really are a parseable image.
    try:
        with Image.open(io.BytesIO(data)) as probe:
            probe.verify()
    except Exception:
        return None, "That file doesn't look like a valid image. Please upload a JPG, PNG, or WebP photo."

    # Second pass: actually decode it (verify() leaves the image unusable).
    try:
        img = Image.open(io.BytesIO(data))
        img.load()
    except Image.DecompressionBombError:
        return None, "That image has too many pixels to process safely. Please use a smaller photo."
    except Exception:
        return None, "That image could not be read. Please try another photo."

    if img.mode != "RGB":
        img = img.convert("RGB")
    if max(img.size) > config.MAX_IMAGE_DIM:        # keep the payload to the model reasonable
        img.thumbnail((config.MAX_IMAGE_DIM, config.MAX_IMAGE_DIM))
    return img, ""

def assess_photo_quality(img: Image.Image) -> dict:
    """Advisory-only photo-quality pre-flight check (brightness + blur proxy).

    Pillow-only heuristics; never blocks analysis -- callers should render
    `warnings` via st.warning() but still allow the user to proceed. This is
    a separate layer from load_validated_image(), which only does structural
    validation (size/decompression-bomb/decode)."""
    gray = img.convert("L")
    brightness = ImageStat.Stat(gray).mean[0]
    is_too_dark = brightness < config.BRIGHTNESS_DARK_THRESHOLD
    is_too_bright = brightness > config.BRIGHTNESS_BRIGHT_THRESHOLD

    edges = gray.filter(ImageFilter.FIND_EDGES)
    sharpness = ImageStat.Stat(edges).var[0]
    is_blurry = sharpness < config.BLUR_VARIANCE_THRESHOLD

    warnings = []
    if is_too_dark:
        warnings.append("This photo looks quite dark — try retaking it in brighter, even lighting for a more reliable analysis.")
    if is_too_bright:
        warnings.append("This photo looks washed out or overexposed — try reducing glare or direct flash for a clearer shot.")
    if is_blurry:
        warnings.append("This photo looks a bit blurry — try holding the camera steady and refocusing for a sharper image.")

    return {
        "brightness": brightness,
        "is_too_dark": is_too_dark,
        "is_too_bright": is_too_bright,
        "sharpness": sharpness,
        "is_blurry": is_blurry,
        "warnings": warnings,
    }
