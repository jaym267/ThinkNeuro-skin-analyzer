# -*- coding: utf-8 -*-
"""Groq client construction + a generic secrets-lookup helper.

The env-or-st.secrets pattern in get_secret() is intentionally generic (not
Groq-specific) so other modules — e.g. a future db.py needing DATABASE_URL —
can reuse it without re-inventing the same fallback logic.
"""
import os

import streamlit as st
from groq import Groq


def get_secret(key: str, default=None):
    """Look up a secret by name: local .env / real env var first, then
    Streamlit Cloud's st.secrets, else `default`.

    Generic on purpose — used today for GROQ_API_KEY, intended for reuse by
    other modules (e.g. a DATABASE_URL secret) later.
    """
    value = os.getenv(key)
    if value:
        return value
    try:
        return st.secrets[key]
    except (KeyError, FileNotFoundError, AttributeError):
        return default


@st.cache_resource
def get_client():
    # Local runs read the key from .env; Streamlit Community Cloud provides it
    # through the app's Secrets manager (exposed via st.secrets).
    key = get_secret("GROQ_API_KEY")
    if not key:
        st.error(
            "GROQ_API_KEY not found. Add it to your local .env file, or — when "
            "deployed on Streamlit Cloud — add it under the app's Secrets."
        )
        st.stop()
    return Groq(api_key=key)
