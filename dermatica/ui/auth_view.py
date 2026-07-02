# -*- coding: utf-8 -*-
"""The login / create-account gate shown when accounts are enabled (a DB is
configured) and no one is signed in. app.py renders this and st.stop()s the
rest of the app until the visitor authenticates."""
import streamlit as st

from .. import auth


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
            with st.form("signup_form", clear_on_submit=False):
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
                confirm = st.text_input(
                    "Confirm password", type="password", key="signup_confirm",
                )
                created = st.form_submit_button("Create Account", use_container_width=True)
                if created:
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
