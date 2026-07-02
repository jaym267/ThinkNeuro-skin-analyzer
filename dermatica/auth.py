# -*- coding: utf-8 -*-
"""Username/password accounts + persistent sessions.

Design notes
------------
* Passwords are hashed with bcrypt (never stored or logged in plaintext).
* "Stay logged in" is a stateless, HMAC-signed cookie carrying `user_id.exp`.
  Verifying only needs the server secret, so there's no server-side session
  table to keep in sync; tampering fails the signature check and an expired
  `exp` is rejected. The signing key comes from an AUTH_SECRET secret when
  set (so sessions survive redeploys); otherwise a per-process random key is
  used as a safe fallback (sessions just won't outlive a restart).
* Accounts require a database. When DATABASE_URL isn't configured the whole
  auth layer disables itself (is_enabled() -> False) and the app runs in its
  original open, no-login mode — so a missing DB never breaks the live site.
"""
import hashlib
import hmac
import logging
import re
import secrets
import time

import bcrypt
import streamlit as st

from . import db
from .groq_client import get_secret

logger = logging.getLogger("dermatica")

COOKIE_NAME = "dermatica_auth"
SESSION_TTL_DAYS = 30
SESSION_TTL_SECONDS = SESSION_TTL_DAYS * 86400

MIN_USERNAME_LEN = 3
MAX_USERNAME_LEN = 32
MIN_PASSWORD_LEN = 8
# bcrypt only uses the first 72 bytes of a password; cap input so a longer
# password isn't silently truncated in a way that surprises the user.
MAX_PASSWORD_LEN = 72
_USERNAME_RE = re.compile(r"^[A-Za-z0-9_.-]+$")


# ── enablement / state ────────────────────────────────────────────────────
def is_enabled() -> bool:
    """Accounts are only available when a database is configured."""
    return db.is_configured()


def is_logged_in() -> bool:
    return bool(st.session_state.get("user_id"))


def current_username() -> str:
    return st.session_state.get("username", "")


def current_user_id() -> int:
    """The active account's id when logged in, else the no-auth sentinel
    user (only reached in open/no-DB mode, where callers already guard on
    db.is_configured())."""
    uid = st.session_state.get("user_id")
    if uid:
        return uid
    return db.get_default_user_id()


# ── password hashing ──────────────────────────────────────────────────────
def hash_password(password: str) -> str:
    return bcrypt.hashpw(password.encode("utf-8"), bcrypt.gensalt()).decode("utf-8")


def verify_password(password: str, hashed: str) -> bool:
    try:
        return bcrypt.checkpw(password.encode("utf-8"), hashed.encode("utf-8"))
    except Exception:
        # Malformed/legacy hash, etc. — treat as a failed login, never raise.
        return False


# ── session cookie (stateless, HMAC-signed) ───────────────────────────────
@st.cache_resource
def _fallback_secret() -> bytes:
    """Process-wide random signing key used when AUTH_SECRET isn't set.
    Cached so it's stable within a running process (all sessions share it),
    but it changes on restart — which just means users re-log-in after a
    redeploy. Set AUTH_SECRET in secrets to make sessions durable."""
    return secrets.token_bytes(32)


def _signing_key() -> bytes:
    configured = get_secret("AUTH_SECRET")
    if configured:
        return configured.encode("utf-8")
    return _fallback_secret()


def _make_token(user_id: int, exp: int) -> str:
    payload = f"{user_id}.{exp}"
    sig = hmac.new(_signing_key(), payload.encode(), hashlib.sha256).hexdigest()
    return f"{payload}.{sig}"


def _verify_token(token: str) -> int | None:
    """Return the user_id from a valid, unexpired, correctly-signed token,
    else None."""
    try:
        user_id, exp, sig = token.rsplit(".", 2)
        expected = hmac.new(
            _signing_key(), f"{user_id}.{exp}".encode(), hashlib.sha256
        ).hexdigest()
        if not hmac.compare_digest(sig, expected):
            return None
        if int(exp) < int(time.time()):
            return None
        return int(user_id)
    except Exception:
        return None


def _controller():
    """A single CookieController per session. Instantiating more than one in
    a run collides on the component key, so memoize it in session_state."""
    ctrl = st.session_state.get("_cookie_ctrl")
    if ctrl is None:
        # Imported lazily so a missing component build never breaks import of
        # this module (e.g. during headless AppTest of the no-DB fallback).
        from streamlit_cookies_controller import CookieController

        ctrl = CookieController()
        st.session_state["_cookie_ctrl"] = ctrl
    return ctrl


def _set_session_cookie(user_id: int) -> None:
    exp = int(time.time()) + SESSION_TTL_SECONDS
    try:
        _controller().set(
            COOKIE_NAME, _make_token(user_id, exp), max_age=SESSION_TTL_SECONDS
        )
    except Exception:
        # A cookie hiccup shouldn't block login; the user is still logged in
        # for this session via session_state, just not across a refresh.
        logger.warning("Could not set auth cookie.", exc_info=True)


def _clear_session_cookie() -> None:
    try:
        _controller().remove(COOKIE_NAME)
    except Exception:
        logger.warning("Could not clear auth cookie.", exc_info=True)


def restore_session() -> None:
    """On load, if not already logged in, try to restore the session from a
    valid auth cookie. Safe to call every run."""
    if not is_enabled() or is_logged_in():
        return
    try:
        token = _controller().get(COOKIE_NAME)
    except Exception:
        token = None
    if not token:
        return
    user_id = _verify_token(token)
    if not user_id:
        return
    try:
        user = db.get_user_by_id(user_id)
    except Exception:
        logger.warning("Session restore DB lookup failed.", exc_info=True)
        return
    if user:
        st.session_state.user_id = user["id"]
        st.session_state.username = user["username"]


# ── auth actions ──────────────────────────────────────────────────────────
def _validate_credentials(username: str, password: str) -> str:
    if not (MIN_USERNAME_LEN <= len(username) <= MAX_USERNAME_LEN):
        return f"Username must be {MIN_USERNAME_LEN}-{MAX_USERNAME_LEN} characters."
    if not _USERNAME_RE.match(username):
        return "Username can only use letters, numbers, and . _ - characters."
    if not (MIN_PASSWORD_LEN <= len(password) <= MAX_PASSWORD_LEN):
        return f"Password must be {MIN_PASSWORD_LEN}-{MAX_PASSWORD_LEN} characters."
    return ""


def signup(username: str, password: str, confirm: str) -> tuple[bool, str]:
    username = (username or "").strip()
    err = _validate_credentials(username, password or "")
    if err:
        return False, err
    if password != confirm:
        return False, "Passwords do not match."
    try:
        new_id = db.create_user(username, hash_password(password))
    except Exception:
        logger.exception("Signup failed")
        return False, "Could not create the account right now. Please try again."
    if new_id is None:
        return False, "That username is already taken. Please choose another."
    st.session_state.user_id = new_id
    st.session_state.username = username
    _set_session_cookie(new_id)
    return True, ""


def login(username: str, password: str) -> tuple[bool, str]:
    username = (username or "").strip()
    try:
        user = db.get_user_by_username(username)
    except Exception:
        logger.exception("Login DB lookup failed")
        return False, "Could not sign you in right now. Please try again."
    # Verify even when the user is missing to keep timing roughly uniform, and
    # give one generic message so we don't reveal which field was wrong.
    stored = user["password_hash"] if user else ""
    if not user or not verify_password(password or "", stored):
        return False, "Incorrect username or password."
    st.session_state.user_id = user["id"]
    st.session_state.username = user["username"]
    _set_session_cookie(user["id"])
    return True, ""


def _reset_session_state() -> None:
    """Wipe per-user session state on logout / delete so nothing leaks into
    the next (possibly different) account within the same browser tab."""
    for key in ("analysis_history", "chat_messages"):
        st.session_state[key] = []
    for key in (
        "user_id", "username", "current_analysis", "current_image",
        "current_image_b64", "pending_q", "symptom_intake",
    ):
        st.session_state[key] = None
    st.session_state.history_seeded = False


def logout() -> None:
    _clear_session_cookie()
    _reset_session_state()


def delete_account() -> tuple[bool, str]:
    """Permanently delete the logged-in account and all its data, then log
    out. Irreversible by design (backs the Settings 'delete my account'
    control, which gates this behind an explicit confirmation)."""
    uid = st.session_state.get("user_id")
    if not uid:
        return False, "You are not signed in."
    try:
        db.delete_user(uid)
    except Exception:
        logger.exception("Account deletion failed")
        return False, "Could not delete the account right now. Please try again."
    logout()
    return True, ""
