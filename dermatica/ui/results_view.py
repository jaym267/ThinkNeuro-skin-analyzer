# -*- coding: utf-8 -*-
"""Results view: 3-tab layout (Analysis Results / Follow-up Questions /
Download Report)."""
import datetime
import html as html_lib
import logging
import time

import plotly.express as px
import streamlit as st

from .. import config, db, styles
from ..rate_limit import acquire_request_slot
from ..report import build_pdf_report, build_report
from ..vision import ask_followup_stream
from .components import render_condition_card, render_list_card

logger = logging.getLogger("dermatica")


def _persist_chat_message(analysis_id, role: str, content: str) -> None:
    """Write-through a chat turn to the DB, linked to the current analysis's
    row id (set on result["id"] by upload_view.py's analyze handler when
    db.save_analysis() succeeded). Soft-fail, matching the rest of the app's
    DB philosophy: if analysis_id is missing (DB was unavailable at analyze
    time) or the DB call itself errors, skip persistence silently rather
    than breaking the chat UI that already works without it.
    """
    if not analysis_id:
        return
    try:
        db.save_chat_message(analysis_id, role, content)
    except Exception:
        logger.warning("Failed to persist chat message to DB.", exc_info=True)


def render_severity_trend(history: list[dict]) -> None:
    """Renders a severity-over-time scatter/line chart from past analyses in
    st.session_state.analysis_history. Each entry is the parsed analysis dict
    (see parsing.parse_analysis) plus "timestamp" (HH:MM display string),
    "timestamp_dt" (a real datetime, added in upload_view.py's analyze-button
    handler), and "filename". Needs at least 2 points to plot a meaningful
    trend; otherwise shows a low-key "come back later" message instead of an
    error/empty chart."""
    st.markdown('<div class="sec-lbl" style="margin-top:2rem;">Severity Trend</div>', unsafe_allow_html=True)

    if len(history) < 2:
        st.markdown("""
        <div class="g-card fade">
          <div style="font-size:.85rem;color:#8A8785;font-style:italic;text-align:center;padding:.5rem 0;">
            Come back after a few scans to see your severity trend over time.
          </div>
        </div>
        """, unsafe_allow_html=True)
        return

    rows = []
    for h in history:
        conds = h.get("conditions", [])
        top_condition = conds[0]["name"] if conds else "Unknown"
        rows.append({
            "timestamp":      h.get("timestamp_dt") or h.get("timestamp", ""),
            "severity_score": h.get("severity_score", 5.0),
            "severity_level": h.get("severity_level", "MODERATE"),
            "top_condition":  top_condition,
        })

    color_map = {lvl: sty["color"] for lvl, sty in styles.SEVERITY_STYLES.items()}

    fig = px.scatter(
        rows,
        x="timestamp",
        y="severity_score",
        color="severity_level",
        color_discrete_map=color_map,
        category_orders={"severity_level": list(styles.SEVERITY_STYLES.keys())},
        hover_data={"top_condition": True, "timestamp": True, "severity_level": True, "severity_score": True},
        labels={
            "timestamp": "Scan Time",
            "severity_score": "Severity Score",
            "severity_level": "Severity Level",
            "top_condition": "Top Condition",
        },
    )
    fig.update_traces(mode="markers+lines", line=dict(color="#B8B5B0", width=1.5))
    fig.update_layout(
        margin=dict(l=10, r=10, t=10, b=10),
        height=320,
        plot_bgcolor="#FFFFFF",
        paper_bgcolor="#FFFFFF",
        legend_title_text="Severity Level",
        yaxis=dict(range=[0, 10.5], title="Severity Score"),
        xaxis=dict(title="Scan Time"),
    )

    st.plotly_chart(fig, use_container_width=True)


def render_results_view() -> None:
    analysis = st.session_state.current_analysis
    img      = st.session_state.current_image

    tab_res, tab_chat, tab_dl = st.tabs(
        ["Analysis Results", "Follow-up Questions", "Download Report"]
    )

    # ── TAB 1 ────────────────────────────────
    with tab_res:
        col_l, col_r = st.columns([1, 1.55])

        with col_l:
            st.markdown('<div class="sec-lbl">Analyzed Image</div>', unsafe_allow_html=True)
            st.image(img, use_container_width=True)

            sev_lvl   = analysis.get("severity_level", "MODERATE")
            sev_score = analysis.get("severity_score", 5.0)
            sev_style = styles.SEVERITY_STYLES.get(sev_lvl, styles.SEVERITY_STYLES["MODERATE"])
            sev_pct   = min(100, max(5, int(sev_score * 10)))

            st.markdown(f"""
            <div class="g-card fade" style="margin-top:.85rem;">
              <div class="g-card-header">
                <div class="g-accent" style="background:{sev_style['color']};"></div>
                <div>
                  <div class="g-title">Severity Assessment</div>
                  <div class="g-sub">Score: {sev_score:.1f} / 10</div>
                </div>
              </div>
              <div class="sev-wrap">
                <div class="sev-fill" style="width:{sev_pct}%;background:{sev_style['color']};"></div>
              </div>
              <div class="sev-labels">
                <span class="sev-label">Minimal</span>
                <span class="sev-label">Moderate</span>
                <span class="sev-label">Critical</span>
              </div>
              <div style="text-align:center;margin-top:1rem;">
                <span style="font-size:.78rem;font-weight:700;padding:5px 16px;
                             border-radius:100px;letter-spacing:1px;
                             background:{sev_style['bg']};color:{sev_style['color']};
                             border:1px solid {sev_style['border']};">
                  {sev_lvl} SEVERITY
                </span>
              </div>
            </div>
            """, unsafe_allow_html=True)

            rec    = analysis.get("recommended_action", "SEE_DOCTOR")
            acfg   = styles.ACTION_CONFIGS.get(rec, styles.ACTION_CONFIGS["SEE_DOCTOR"])
            detail = html_lib.escape(analysis.get("action_detail", "Please consult a medical professional."))
            st.markdown(f"""
            <div class="act-card fade"
                 style="background:{acfg['bg']};border-color:{acfg['border']};
                        border-left:4px solid {acfg['color']};">
              <div class="act-title" style="color:{acfg['color']};">{acfg['title']}</div>
              <div class="act-desc">{detail}</div>
            </div>
            """, unsafe_allow_html=True)

        with col_r:
            vd = html_lib.escape(analysis.get("visual_description", ""))
            if vd:
                st.markdown('<div class="sec-lbl">Clinical Observations</div>', unsafe_allow_html=True)
                st.markdown(f"""
                <div class="g-card fade">
                  <div class="g-card-header">
                    <div class="g-accent"></div>
                    <div class="g-title">What the AI Observed</div>
                  </div>
                  <div style="font-size:.89rem;line-height:1.82;color:#4A4845;
                              font-style:italic;">{vd}</div>
                </div>
                """, unsafe_allow_html=True)

            conds = analysis.get("conditions", [])
            if conds:
                st.markdown('<div class="sec-lbl">Differential Analysis</div>', unsafe_allow_html=True)
                cond_html = """
                <div class="g-card fade">
                  <div class="g-card-header">
                    <div class="g-accent"></div>
                    <div>
                      <div class="g-title">Possible Conditions</div>
                      <div class="g-sub">Ranked by clinical likelihood</div>
                    </div>
                  </div>"""
                for c in conds:
                    cond_html += render_condition_card(c)
                cond_html += "</div>"
                st.markdown(cond_html, unsafe_allow_html=True)

            render_list_card(
                "Identified Risk Factors",
                analysis.get("risk_factors", []),
                styles.SEMANTIC["danger"],
            )

            wtsd = analysis.get("when_to_see_doctor", [])
            sct  = analysis.get("self_care_tips", [])
            if wtsd or sct:
                c1, c2 = st.columns(2)
                if wtsd:
                    with c1:
                        render_list_card("When to Seek Medical Care", wtsd, styles.SEMANTIC["danger"])
                if sct:
                    with c2:
                        render_list_card("Self-Care Recommendations", sct, styles.SEMANTIC["success"])

        render_severity_trend(st.session_state.get("analysis_history", []))

        st.markdown("<div style='margin-top:2.5rem;'></div>", unsafe_allow_html=True)
        _, mid2, _ = st.columns([2, 1, 2])
        with mid2:
            if st.button("Analyze New Image", use_container_width=True):
                st.session_state.current_analysis = None
                st.session_state.current_image    = None
                st.session_state.chat_messages    = []
                st.session_state.pending_q        = None
                st.rerun()

    # ── TAB 2 ────────────────────────────────
    with tab_chat:
        st.markdown('<div class="sec-lbl">AI Consultation</div>', unsafe_allow_html=True)

        def _fmt(text):
            # escape so AI/user text can't break the bubble markup; keep line breaks
            return html_lib.escape(text).replace("\n", "<br>")

        def _bubbles(messages):
            out = ""
            for m in messages:
                if m["role"] == "user":
                    out += (f'<div class="chat-user">'
                            f'<div class="bubble-user">{_fmt(m["content"])}</div></div>')
                else:
                    out += (f'<div class="chat-ai"><div class="ai-label">AI</div>'
                            f'<div class="bubble-ai">{_fmt(m["content"])}</div></div>')
            return out

        pending   = st.session_state.get("pending_q")
        chat_slot = st.empty()

        if st.session_state.chat_messages:
            chat_slot.markdown(
                f'<div class="chat-box">{_bubbles(st.session_state.chat_messages)}</div>',
                unsafe_allow_html=True,
            )
        elif not pending:
            chat_slot.markdown("""
            <div style="text-align:center;padding:2rem;background:#FFFFFF;
                        border:1px solid #E4E0D8;border-radius:14px;
                        margin-bottom:1rem;box-shadow:0 1px 3px rgba(27,50,82,.06),
                        0 4px 16px rgba(27,50,82,.07);">
              <div style="font-size:.95rem;font-weight:700;color:#4A4845;margin-bottom:.4rem;">
                Ask About Your Results
              </div>
              <div style="font-size:.82rem;color:#8A8785;font-style:italic;">
                Submit a question below to receive additional clinical context from the AI.
              </div>
            </div>
            """, unsafe_allow_html=True)

        st.markdown(
            '<div style="font-size:.68rem;color:#B8B5B0;text-transform:uppercase;'
            'letter-spacing:2px;margin-bottom:.65rem;">Suggested Questions</div>',
            unsafe_allow_html=True
        )
        suggestions = [
            "What treatments are typically available for this condition?",
            "Is this condition contagious?",
            "What activities or substances should I avoid?",
            "What is the typical recovery timeline?",
        ]
        sq_cols = st.columns(2)
        for i, q in enumerate(suggestions):
            with sq_cols[i % 2]:
                if st.button(q, key=f"sq_{i}", use_container_width=True):
                    st.session_state.chat_messages.append({"role": "user", "content": q})
                    st.session_state.pending_q = q
                    _persist_chat_message(analysis.get("id"), "user", q)
                    st.rerun()

        with st.form("qform", clear_on_submit=True):
            user_q   = st.text_input("Question", placeholder="Enter your question here...", label_visibility="collapsed")
            send_btn = st.form_submit_button("Submit Question", use_container_width=True)
            if send_btn and user_q.strip():
                q = user_q.strip()[:config.MAX_QUESTION_CHARS]   # cap length before storing/sending
                st.session_state.chat_messages.append({"role": "user", "content": q})
                st.session_state.pending_q = q
                _persist_chat_message(analysis.get("id"), "user", q)
                st.rerun()

        # Answer a pending question: hold a brief "thinking" beat, then type the
        # reply out live, character by character, rather than dropping it in at once.
        if pending:
            base = _bubbles(st.session_state.chat_messages)

            ok, limit_msg = acquire_request_slot()
            if not ok:
                # Surface the limit transiently; do NOT store it as an assistant
                # turn (that would be replayed to the model as conversation history).
                st.session_state.pending_q = None
                st.warning(limit_msg)
                st.stop()

            thinking = ('<div class="chat-ai"><div class="ai-label">AI</div>'
                        '<div class="bubble-ai thinking"><span class="think-text">'
                        'Reviewing your question against the analysis&hellip;</span>'
                        '</div></div>')
            chat_slot.markdown(f'<div class="chat-box">{base}{thinking}</div>',
                               unsafe_allow_html=True)
            time.sleep(1.0)   # brief, intentional "thinking" beat

            full = ""
            try:
                # Renders incrementally as stream chunks arrive (typewriter effect)
                # without an artificial per-chunk delay.
                for delta in ask_followup_stream(analysis, img):
                    full += delta
                    typing = ('<div class="chat-ai"><div class="ai-label">AI</div>'
                              f'<div class="bubble-ai">{_fmt(full)}'
                              '<span class="type-caret"></span></div></div>')
                    chat_slot.markdown(f'<div class="chat-box">{base}{typing}</div>',
                                       unsafe_allow_html=True)
                if not full.strip():
                    full = "I could not generate a response. Please try again."
            except Exception:
                logger.exception("Follow-up chat failed")
                full = "Sorry, I couldn't complete that response. Please try again."

            st.session_state.chat_messages.append({"role": "assistant", "content": full})
            st.session_state.chat_messages = st.session_state.chat_messages[-config.MAX_CHAT_MESSAGES:]
            _persist_chat_message(analysis.get("id"), "assistant", full)
            st.session_state.pending_q = None
            st.rerun()

    # ── TAB 3 ────────────────────────────────
    with tab_dl:
        st.markdown('<div class="sec-lbl">Export Report</div>', unsafe_allow_html=True)
        fname  = analysis.get("filename", "skin_image")
        report = build_report(analysis, fname)

        st.markdown("""
        <div class="g-card">
          <div class="g-card-header">
            <div class="g-accent"></div>
            <div>
              <div class="g-title">Full Analysis Report</div>
              <div class="g-sub">Complete findings, differential diagnosis, risk factors, and recommendations.</div>
            </div>
          </div>
        </div>
        """, unsafe_allow_html=True)

        st.code(report, language=None)

        ts = datetime.datetime.now().strftime("%Y%m%d_%H%M")
        stem = fname.rsplit(".", 1)[0] if "." in fname else fname

        col_txt, col_pdf = st.columns(2)
        with col_txt:
            st.download_button(
                label="Download Report (.txt)",
                data=report,
                file_name=f"dermai_report_{ts}.txt",
                mime="text/plain",
                use_container_width=True,
            )
        with col_pdf:
            pdf_bytes = build_pdf_report(analysis, img, fname)
            st.download_button(
                label="Download Report (.pdf)",
                data=pdf_bytes,
                file_name=f"{stem}_report.pdf",
                mime="application/pdf",
                use_container_width=True,
            )
