# -*- coding: utf-8 -*-
"""Upload panel: file uploader, image preview, Analyze button, How It Works."""
import datetime
import logging

import streamlit as st

from .. import config, db
from ..image_utils import (
    assess_photo_quality,
    image_to_base64,
    image_to_thumbnail_base64,
    load_validated_image,
)
from ..rate_limit import acquire_request_slot
from ..vision import analyze_image
from .education import render_abcde_checklist

logger = logging.getLogger("dermatica")

_DURATION_OPTIONS = ["Less than a day", "A few days", "1-2 weeks", "Longer than 2 weeks"]
_SPREADING_OPTIONS = ["Not spreading", "Spreading slowly", "Spreading quickly"]


def render_symptom_intake_form() -> None:
    """Pre-scan symptom intake form. On submit, stores a plain JSON-serializable
    dict in st.session_state.symptom_intake for later use by analyze_image()
    (and, in a later phase, persistence to a symptom_intake_json DB column)."""
    st.markdown('<div class="sec-lbl">Tell Us About Your Symptoms (Optional)</div>', unsafe_allow_html=True)
    with st.form("symptom_intake_form"):
        itch_severity = st.slider("Itch severity", 1, 10, 1)
        duration = st.selectbox("Duration", _DURATION_OPTIONS)
        spreading = st.radio("Spreading pattern", _SPREADING_OPTIONS)
        prior_treatment = st.text_area("Any treatments tried so far? (optional)")
        submitted = st.form_submit_button("Save Symptom Info")
        if submitted:
            st.session_state.symptom_intake = {
                "itch_severity": int(itch_severity),
                "duration": duration,
                "spreading": spreading,
                "prior_treatment": prior_treatment,
            }
            st.success("Symptom information saved. It will be included with your analysis.")


def render_upload_view() -> None:
    render_abcde_checklist()

    _, mid, _ = st.columns([1, 2, 1])
    with mid:
        render_symptom_intake_form()

        st.markdown("""
        <div class="upload-panel fade">
          <div class="upload-head">
            <div class="g-accent"></div>
            <div>
              <div class="g-title">Upload Skin Image</div>
              <div class="g-sub">Drag a photograph into the area below, or browse your files to begin.</div>
            </div>
          </div>
        </div>
        """, unsafe_allow_html=True)

        uploaded_file = st.file_uploader(
            "Select an image file",
            type=["jpg", "jpeg", "png", "webp"],
            label_visibility="collapsed",
        )

        if uploaded_file:
            img, img_err = load_validated_image(uploaded_file)
            if img_err:
                st.error(img_err)
            else:
                w, h  = img.size
                fsize = uploaded_file.size / 1024

                st.markdown('<div class="sec-lbl">Selected Image</div>', unsafe_allow_html=True)
                st.image(img, use_container_width=True)
                st.markdown(
                    f'<div style="margin:.65rem 0;">'
                    f'<span class="info-chip">{w} &times; {h} px</span>'
                    f'<span class="info-chip">{fsize:.1f} KB</span>'
                    f'<span class="info-chip">{img.mode}</span>'
                    f'</div>',
                    unsafe_allow_html=True,
                )

                quality = assess_photo_quality(img)
                for warning in quality["warnings"]:
                    st.warning(warning)

                if st.button("Analyze Skin Condition", use_container_width=True):
                    ok, limit_msg = acquire_request_slot()
                    if not ok:
                        st.warning(limit_msg)
                        st.stop()
                    with st.spinner("Analyzing image — please wait..."):
                        try:
                            result = analyze_image(img, st.session_state.get("symptom_intake"))
                            result["timestamp"] = datetime.datetime.now().strftime("%H:%M")
                            result["timestamp_dt"] = datetime.datetime.now()
                            result["filename"]  = uploaded_file.name
                            st.session_state.current_analysis  = result
                            st.session_state.current_image     = img
                            st.session_state.current_image_b64 = image_to_base64(img)
                            st.session_state.analysis_history.append(result)
                            st.session_state.analysis_history = \
                                st.session_state.analysis_history[-config.MAX_HISTORY_ANALYSES:]
                            st.session_state.chat_messages    = []
                            st.session_state.pending_q        = None

                            # Persist to the DB so this analysis survives a
                            # browser refresh / redeploy. Skip entirely when no
                            # DATABASE_URL is configured (expected local/no-DB
                            # mode); only attempt — and soft-fail with a logged
                            # traceback — when a DB *is* configured but the
                            # write fails. A DB hiccup must not break the
                            # in-session analyze flow that already works without
                            # persistence. On success, stash the new row's id
                            # onto the result dict so later chat messages in
                            # results_view.py can link to it.
                            if db.is_configured():
                                try:
                                    thumbnail_b64 = image_to_thumbnail_base64(img)
                                    new_id = db.save_analysis(
                                        db.get_default_user_id(),
                                        result,
                                        uploaded_file.name,
                                        thumbnail_b64,
                                        st.session_state.get("symptom_intake"),
                                    )
                                    result["id"] = new_id
                                except Exception:
                                    logger.warning(
                                        "Failed to persist analysis to DB; "
                                        "continuing with in-session result only.",
                                        exc_info=True,
                                    )

                            st.rerun()
                        except Exception:
                            logger.exception("Analysis failed")
                            st.error("Analysis failed. Please try again in a moment.")
        else:
            st.markdown("""
            <div class="upload-hint">
              Accepted formats: JPG, PNG, WebP &nbsp;&mdash;&nbsp; maximum 10 MB.
              For the most accurate analysis, use a clear, close-up photograph taken in natural light.
            </div>
            """, unsafe_allow_html=True)

    st.markdown('<div class="sec-lbl" style="margin-top:3.5rem;">How It Works</div>', unsafe_allow_html=True)
    f_cols = st.columns(4)
    feats  = [
        ("I",   "Upload",           "Submit a clear photograph of the affected skin area for evaluation."),
        ("II",  "AI Analysis",      "Multimodal AI examines visual patterns, texture, colour, and distribution."),
        ("III", "Review Results",   "Receive a structured report with severity, ranked conditions, and risk factors."),
        ("IV",  "Consult Further",  "Ask follow-up questions to receive additional clinical context from the AI."),
    ]
    for col, (num, title, desc) in zip(f_cols, feats):
        with col:
            st.markdown(f"""
            <div class="feat-card">
              <div class="feat-num">{num}</div>
              <div class="feat-rule"></div>
              <div class="feat-title">{title}</div>
              <div class="feat-desc">{desc}</div>
            </div>
            """, unsafe_allow_html=True)
