# -*- coding: utf-8 -*-
# Last updated June 2026
import logging

import streamlit as st
from dotenv import load_dotenv

from dermatica import db
from dermatica.ui.components import load_css
from dermatica.ui.results_view import render_results_view
from dermatica.ui.sidebar import render_sidebar
from dermatica.ui.upload_view import render_upload_view

load_dotenv()
logger = logging.getLogger(__name__)

# ──────────────────────────────────────────────
# DATABASE SCHEMA BOOTSTRAP
# ──────────────────────────────────────────────
# Self-provisions a fresh Supabase project's schema on first run. The app has
# no login requirement and DB persistence is best-effort only, so a missing/
# unreachable DATABASE_URL must NOT break the core analyze flow — soft-fail
# with a log entry instead of st.stop()'ing the whole app.
try:
    db.init_schema()
except Exception:
    logger.warning(
        "Database schema bootstrap skipped (DATABASE_URL not configured or "
        "unreachable). Continuing without DB-backed features.",
        exc_info=True,
    )

# ──────────────────────────────────────────────
# PAGE CONFIG
# ──────────────────────────────────────────────
st.set_page_config(
    page_title="Dermatica | Advanced Skin Analysis",
    page_icon=None,
    layout="wide",
    initial_sidebar_state="expanded",
)

# ──────────────────────────────────────────────
# SESSION STATE
# ──────────────────────────────────────────────
for k, v in {
    "analysis_history": [],
    "chat_messages":    [],
    "current_analysis": None,
    "current_image":    None,
    "current_image_b64": None,
    "pending_q":        None,
    "symptom_intake":   None,
    "dark_mode":        False,
    "history_seeded":   False,
}.items():
    if k not in st.session_state:
        st.session_state[k] = v

# ──────────────────────────────────────────────
# STYLES
# ──────────────────────────────────────────────
load_css("static/styles.css", dark=st.session_state.get("dark_mode", False))

# ──────────────────────────────────────────────
# SEED HISTORY FROM DB (once per fresh session)
# ──────────────────────────────────────────────
# No login event exists in this no-auth app, so the seed runs once per fresh
# session at startup instead of after a successful login. Session state is
# the live read/write path during an active session; the DB is a
# write-through log plus a one-time seed at startup, not re-queried every
# rerun. The "history_seeded" sentinel ensures this runs exactly once per
# fresh session rather than on every rerun, which would otherwise be
# harmless-but-wasteful at best (load_history() already returns a fresh,
# correctly-ordered list each time) — the explicit guard is still kept so a
# later change to this block can't accidentally start duplicating entries.
if not st.session_state.get("history_seeded") and not st.session_state.analysis_history:
    try:
        st.session_state.analysis_history = db.load_history(db.get_default_user_id())
    except Exception:
        logger.warning(
            "Failed to seed analysis history from DB; continuing with an "
            "empty in-session history.",
            exc_info=True,
        )
    st.session_state.history_seeded = True

# ──────────────────────────────────────────────
# SIDEBAR
# ──────────────────────────────────────────────
render_sidebar()

# ──────────────────────────────────────────────
# HERO
# ──────────────────────────────────────────────
st.markdown("""
<div class="hero">
  <div class="hero-eyebrow">AI-Powered Dermatology Assistant</div>
  <h1 class="hero-title">Dermatica</h1>
  <p class="hero-sub">Advanced skin condition analysis powered by multimodal AI. Upload a photograph for structured clinical insights in seconds.</p>
  <div class="status-bar">
    <div class="s-pill"><span class="s-dot"></span>Real-time Analysis</div>
    <div class="s-pill"><span class="s-dot"></span>Llama Vision Model</div>
    <div class="s-pill"><span class="s-dot"></span>Secure &amp; Private</div>
    <div class="s-pill"><span class="s-dot"></span>Medical-Grade Prompting</div>
  </div>
</div>
""", unsafe_allow_html=True)

# ──────────────────────────────────────────────
# DISCLAIMER
# ──────────────────────────────────────────────
st.markdown("""
<div class="disclaimer">
  <strong style="color:#1B3252;">Medical Disclaimer &mdash;</strong>
  Dermatica provides AI-generated insights for <em>educational and informational purposes only</em>.
  This tool does not constitute a medical diagnosis or replace professional medical advice.
  Always consult a licensed dermatologist or qualified healthcare professional for accurate
  diagnosis and appropriate treatment.
</div>
""", unsafe_allow_html=True)

# ──────────────────────────────────────────────
# MAIN
# ──────────────────────────────────────────────
if st.session_state.current_analysis is None:
    render_upload_view()
else:
    render_results_view()

# ──────────────────────────────────────────────
# FOOTER
# ──────────────────────────────────────────────
st.markdown("""
<div class="app-footer">
  <div class="footer-rule"></div>
  Dermatica &nbsp;&mdash;&nbsp; Powered by Groq &amp; Llama AI &nbsp;&mdash;&nbsp; For Educational Use Only
  <br>Always consult a licensed dermatologist for professional medical advice.
</div>
""", unsafe_allow_html=True)
