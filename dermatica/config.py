# -*- coding: utf-8 -*-
"""Centralized constants: model name, token limits, image/input limits."""

# ──────────────────────────────────────────────
# MODEL
# ──────────────────────────────────────────────
MODEL_NAME = "meta-llama/llama-4-scout-17b-16e-instruct"

# ──────────────────────────────────────────────
# TOKEN LIMITS
# ──────────────────────────────────────────────
ANALYZE_MAX_TOKENS = 1500   # app.py structured analysis call
FOLLOWUP_MAX_TOKENS = 600   # app.py follow-up chat stream
CLI_MAX_TOKENS = 1024       # analyze.py simple CLI call (separate, simpler path)

# ──────────────────────────────────────────────
# INPUT LIMITS
# ──────────────────────────────────────────────
MAX_UPLOAD_MB = 10              # reject image files larger than this
MAX_IMAGE_PIXELS = 25_000_000   # ~25 MP guard against decompression bombs
MAX_IMAGE_DIM = 2000            # downscale longest side before sending to the model
MAX_QUESTION_CHARS = 500        # cap on a follow-up question's length
MAX_HISTORY_ANALYSES = 20       # cap retained analyses per session
MAX_CHAT_MESSAGES = 20          # cap retained chat turns (also bounds tokens re-sent)

# ──────────────────────────────────────────────
# PHOTO-QUALITY PRE-FLIGHT THRESHOLDS (heuristic starting points; advisory only)
# ──────────────────────────────────────────────
# Mean grayscale luminance (0-255) below this is flagged as too dark. A clear,
# evenly-lit indoor photo of skin typically sits well above 80; 60 gives some
# margin before warning so we don't nag on merely dim-but-usable shots.
BRIGHTNESS_DARK_THRESHOLD = 60
# Mean grayscale luminance above this is flagged as washed-out/overexposed
# (e.g. direct flash on pale skin blowing out detail).
BRIGHTNESS_BRIGHT_THRESHOLD = 200
# Variance of a FIND_EDGES-filtered grayscale image, used as a cheap blur
# proxy (sharp images have strong, high-contrast edges -> high variance;
# blurred images smear edges toward a flat mid-gray -> low variance). This
# is not a true Laplacian, so the scale differs from typical OpenCV
# Laplacian-variance blur thresholds (often ~100-500); calibrated empirically
# against a real in-repo test photo (03DermatitisArm.jpg) plus a
# GaussianBlur(10)-degraded copy of it.
BLUR_VARIANCE_THRESHOLD = 100
