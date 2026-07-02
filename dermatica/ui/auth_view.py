# -*- coding: utf-8 -*-
"""The login / create-account gate shown when accounts are enabled (a DB is
configured) and no one is signed in. app.py renders this and st.stop()s the
rest of the app until the visitor authenticates."""
import html as html_lib

import streamlit as st

from .. import auth

# Segment colours by strength score (0-4). Semantic, readable in both themes.
_STRENGTH_COLORS = {
    0: "#8B2A2A", 1: "#8B2A2A", 2: "#A06B00", 3: "#2B5C8A", 4: "#2E7D53",
}


def _render_strength_meter(password: str) -> None:
    """Render a 4-segment password-strength bar + label/hint beneath the
    signup password field. Advisory only; the real minimum-length rule is
    enforced in auth.signup()."""
    if not password:
        return
    result = auth.password_strength(password)
    score = result["score"]
    color = _STRENGTH_COLORS.get(score, "#8B2A2A")
    filled = max(1, score)   # show at least one lit segment once typing starts

    segments = "".join(
        f'<div style="flex:1;height:5px;border-radius:100px;'
        f'background:{color if i < filled else "var(--border)"};"></div>'
        for i in range(4)
    )
    hint = ("Strong password." if score >= 4
            else "Tip: " + ", ".join(result["hints"]) if result["hints"] else "")
    st.markdown(
        f'<div style="margin:-.4rem 0 .5rem;">'
        f'  <div style="display:flex;gap:5px;margin-bottom:.35rem;">{segments}</div>'
        f'  <div style="font-size:.72rem;color:{color};font-weight:700;">'
        f'    {html_lib.escape(result["label"])}'
        f'    <span style="color:var(--txt2);font-weight:400;font-style:italic;">'
        f'&nbsp;&mdash;&nbsp;{html_lib.escape(hint)}</span>'
        f'  </div>'
        f'</div>',
        unsafe_allow_html=True,
    )


def render_auth_gate() -> None:
    st.markdown(
        """
        <div class="hero">
          <div class="hero-eyebrow">AI-Powered Dermatology Assistant</div>
          <h1 class="hero-title">Dermatica</h1>
          <p class="hero-sub">Sign in to your account to analyze skin images and keep your
          history saved securely across visits.</p>
        </div>
        """,
        unsafe_allow_html=True,
    )

    _, mid, _ = st.columns([1, 1.4, 1])
    with mid:
        tab_login, tab_signup = st.tabs(["Sign In", "Create Account"])

        with tab_login:
            with st.form("login_form", clear_on_submit=False):
                st.markdown(
                    '<div class="g-title" style="margin-bottom:.6rem;">Welcome back</div>',
                    unsafe_allow_html=True,
                )
                username = st.text_input("Username", key="login_username")
                password = st.text_input("Password", type="password", key="login_password")
                submitted = st.form_submit_button("Sign In", use_container_width=True)
                if submitted:
                    ok, msg = auth.login(username, password)
                    if ok:
                        st.rerun()
                    else:
                        st.error(msg)

        with tab_signup:
            # Deliberately NOT wrapped in st.form: a form only commits its
            # widget values on submit, so the password field couldn't drive a
            # live strength meter. Plain widgets rerun when the field commits
            # (Enter / focus change), letting the meter update as you go.
            st.markdown(
                '<div class="g-title" style="margin-bottom:.6rem;">Create your account</div>',
                unsafe_allow_html=True,
            )
            new_username = st.text_input(
                "Choose a username", key="signup_username",
                help="3-32 characters: letters, numbers, and . _ -",
            )
            new_password = st.text_input(
                "Choose a password", type="password", key="signup_password",
                help="At least 8 characters.",
            )
            _render_strength_meter(new_password)
            confirm = st.text_input(
                "Confirm password", type="password", key="signup_confirm",
            )
            if st.button("Create Account", key="signup_submit", use_container_width=True):
                ok, msg = auth.signup(new_username, new_password, confirm)
                if ok:
                    st.rerun()
                else:
                    st.error(msg)

        st.markdown(
            '<div class="upload-hint" style="margin-top:1.2rem;">'
            "Your password is stored only as a securely hashed value, never in plain text. "
            "This tool provides educational information only and is not a medical diagnosis."
            "</div>",
            unsafe_allow_html=True,
        )
