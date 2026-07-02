# -*- coding: utf-8 -*-
"""Hosted Postgres (Supabase) connection pooling + schema bootstrap.

Why Postgres/Supabase and not SQLite or a local file: this app is deployed on
Streamlit Community Cloud, where local files and in-memory state do not
survive container restarts/redeploys. A hosted DB is required for any data to
persist across sessions.

Why a connection pool and not a single cached connection: a single
`st.cache_resource`-cached psycopg connection would go stale across Streamlit
reruns and idle periods (Postgres/Supabase will close idle connections), and
the next rerun would crash trying to use a dead connection. `ConnectionPool`
transparently reconnects/replaces broken connections instead.

This module also provides the CRUD helpers (save_analysis/load_history/etc.)
used for best-effort persistence. The app has no login/accounts; persistence
is keyed to a single implicit "local" user (see get_default_user_id()) so the
`analyses.user_id` foreign key still has a valid row to reference.
"""
import datetime
import logging

import streamlit as st
from psycopg.rows import dict_row
from psycopg.types.json import Json
from psycopg_pool import ConnectionPool

from dermatica.groq_client import get_secret

logger = logging.getLogger(__name__)

# Full schema, applied idempotently by init_schema(). Column names/shapes here
# are relied upon elsewhere (the `users` table backs the single sentinel
# "local" user from get_default_user_id(); persistence's JSONB columns on
# `analyses`/`chat_messages`) — do not rename without updating those call
# sites too.
SCHEMA_SQL = """
CREATE TABLE IF NOT EXISTS users (
    id            SERIAL PRIMARY KEY,
    username      TEXT UNIQUE NOT NULL,
    password_hash TEXT NOT NULL,
    created_at    TIMESTAMPTZ NOT NULL DEFAULT now()
);

CREATE TABLE IF NOT EXISTS analyses (
    id                      SERIAL PRIMARY KEY,
    user_id                 INTEGER REFERENCES users(id) ON DELETE CASCADE,
    created_at              TIMESTAMPTZ NOT NULL DEFAULT now(),
    filename                TEXT,
    image_thumbnail_b64     TEXT,
    severity_score          REAL,
    severity_level          TEXT,
    visual_description      TEXT,
    conditions_json         JSONB,
    risk_factors_json       JSONB,
    recommended_action      TEXT,
    action_detail           TEXT,
    when_to_see_doctor_json JSONB,
    self_care_tips_json     JSONB,
    raw_text                TEXT,
    symptom_intake_json     JSONB
);

CREATE TABLE IF NOT EXISTS chat_messages (
    id          SERIAL PRIMARY KEY,
    analysis_id INTEGER NOT NULL REFERENCES analyses(id) ON DELETE CASCADE,
    role        TEXT NOT NULL,
    content     TEXT NOT NULL,
    created_at  TIMESTAMPTZ NOT NULL DEFAULT now()
);

CREATE INDEX IF NOT EXISTS idx_analyses_user_id ON analyses(user_id);
CREATE INDEX IF NOT EXISTS idx_chat_messages_analysis_id ON chat_messages(analysis_id);
"""
# Note on `image_thumbnail_b64`: a future caller (persistence wiring) should
# populate this with a small, downscaled JPEG thumbnail base64 string — not
# the full-resolution analyzed image — to keep row size and DB egress sane.
# Nothing writes to this column yet; it's just provisioned by the schema now.


class DatabaseNotConfiguredError(RuntimeError):
    """Raised when DATABASE_URL is missing/empty when a pool is requested."""


def is_configured() -> bool:
    """True when a DATABASE_URL secret is present, i.e. DB-backed persistence
    can be attempted.

    Callers use this to *skip* DB work entirely when it isn't configured
    (the common local-dev / no-DB case), rather than calling into the DB
    helpers and catching DatabaseNotConfiguredError on every single rerun —
    which floods the logs with full tracebacks for a perfectly expected
    "no database" state. When this returns False, treat DB persistence as
    simply absent and continue with in-session state only.
    """
    return bool(get_secret("DATABASE_URL"))


@st.cache_resource
def get_pool() -> ConnectionPool:
    """Return a process-wide, cached connection pool to the Supabase/Postgres
    database.

    Mirrors the missing-secret UX in groq_client.get_client(): a missing
    DATABASE_URL surfaces as a clear st.error() + st.stop() rather than a raw
    psycopg connection error.
    """
    database_url = get_secret("DATABASE_URL")
    if not database_url:
        st.error(
            "DATABASE_URL not found. Add it to your local .env file, or — when "
            "deployed on Streamlit Cloud — add it under the app's Secrets."
        )
        st.stop()
        raise DatabaseNotConfiguredError("DATABASE_URL not found")  # pragma: no cover

    # open=True (default) would block here trying to connect immediately;
    # min_size=0 lets the pool start lazily so app startup doesn't hang if the
    # DB is briefly unreachable, while still warming connections as used.
    return ConnectionPool(conninfo=database_url, min_size=0, max_size=5)


DEFAULT_USERNAME = "local"
DEFAULT_PASSWORD_HASH_PLACEHOLDER = "unused"


def get_default_user_id() -> int:
    """Return the id of the single implicit "local" user, creating that row
    on first call if it doesn't exist yet.

    This app has no login/accounts — every analysis is attributed to one
    fixed sentinel row in `users` so the existing `analyses.user_id` foreign
    key (kept as-is rather than migrated away) still has something valid to
    reference. `users.password_hash` is NOT NULL but meaningless here since
    there's no real password; DEFAULT_PASSWORD_HASH_PLACEHOLDER is inserted
    as a throwaway value (no bcrypt import needed for this one-off literal).

    Idempotent under concurrent reruns: INSERT ... ON CONFLICT (username) DO
    NOTHING means a second/concurrent call that races the first never errors
    or inserts a duplicate row, then the SELECT fetches whichever row exists
    (the one this call inserted, or the one another call/process already
    did).

    Like init_schema(), this checks DATABASE_URL itself and raises
    DatabaseNotConfiguredError rather than calling get_pool() directly when
    it's absent. get_pool() does st.error() + st.stop() on a missing secret,
    and st.stop() raises StopException (a BaseException, deliberately not
    catchable by `except Exception:`) — callers of this function (app.py's
    history seed, upload_view.py's save_analysis path) wrap it in a soft-fail
    `except Exception:` so a missing DB doesn't break the core analyze flow;
    letting StopException slip through that guard would defeat the point.
    """
    if not get_secret("DATABASE_URL"):
        raise DatabaseNotConfiguredError(
            "DATABASE_URL not configured; cannot resolve default user."
        )

    pool = get_pool()
    with pool.connection() as conn:
        with conn.cursor() as cur:
            cur.execute(
                "INSERT INTO users (username, password_hash) VALUES (%s, %s) "
                "ON CONFLICT (username) DO NOTHING",
                (DEFAULT_USERNAME, DEFAULT_PASSWORD_HASH_PLACEHOLDER),
            )
            cur.execute(
                "SELECT id FROM users WHERE username = %s",
                (DEFAULT_USERNAME,),
            )
            user_id = cur.fetchone()[0]
        conn.commit()
    return user_id


def init_schema() -> None:
    """Create the users/analyses/chat_messages tables and indexes if they
    don't already exist. Safe to call on every app startup.

    Unlike get_pool(), this does NOT st.stop() the app when DATABASE_URL is
    absent — it raises DatabaseNotConfiguredError instead. The app has no
    hard runtime dependency on the DB (there's no login requirement, and
    persistence is best-effort), so the caller (app.py) is expected to catch
    this and continue running without DB-backed features rather than halting
    the whole app. A caller that *does* want the hard-stop, user-facing error
    UX should call get_pool() directly instead.
    """
    if not get_secret("DATABASE_URL"):
        raise DatabaseNotConfiguredError(
            "DATABASE_URL not configured; skipping schema bootstrap."
        )

    pool = get_pool()
    with pool.connection() as conn:
        with conn.cursor() as cur:
            cur.execute(SCHEMA_SQL)
        conn.commit()


# ──────────────────────────────────────────────────────────────────────────
# PERSISTENCE (Phase 7)
# ──────────────────────────────────────────────────────────────────────────
# Column <-> in-app dict key mapping for `analyses`. The in-session dict
# shape comes from parsing.parse_analysis() (+ "timestamp"/"timestamp_dt"/
# "filename" added by upload_view.py's analyze-button handler):
#
#   DB column                 <-> in-app dict key
#   ------------------------------------------------
#   severity_score             <-> severity_score
#   severity_level              <-> severity_level
#   visual_description           <-> visual_description
#   conditions_json (JSONB)     <-> conditions          (list[dict])
#   risk_factors_json (JSONB)   <-> risk_factors         (list[str])
#   recommended_action          <-> recommended_action
#   action_detail                <-> action_detail
#   when_to_see_doctor_json     <-> when_to_see_doctor   (list[str])
#   self_care_tips_json (JSONB) <-> self_care_tips       (list[str])
#   raw_text                     <-> raw
#   symptom_intake_json (JSONB) <-> (separate symptom_intake arg, not part
#                                     of the analysis dict itself)
#   filename                     <-> filename
#   image_thumbnail_b64         <-> (separate thumbnail arg)
#   id (row pk)                  <-> id (added on load/after save)
#   created_at                   <-> timestamp / timestamp_dt
#
# All queries below use parameterized `%s` placeholders with values passed
# separately in a tuple/list — never f-string/`.format()`/`%`-interpolated
# SQL. JSONB columns are always written through psycopg's `Json()` adapter
# (never `json.dumps()`), so reads come back as native Python dicts/lists
# rather than JSON-encoded strings.

def save_analysis(
    user_id: int,
    analysis: dict,
    filename: str,
    image_thumbnail_b64: str,
    symptom_intake: dict | None,
) -> int:
    """Insert one row into `analyses` for a completed analysis and return the
    new row's id (used to link later chat_messages rows to it).

    `analysis` is the dict produced by parsing.parse_analysis() (optionally
    with extra keys like "timestamp"/"timestamp_dt"/"filename" already mixed
    in by upload_view.py -- only the keys this function reads are used).
    """
    pool = get_pool()
    with pool.connection() as conn:
        with conn.cursor() as cur:
            cur.execute(
                """
                INSERT INTO analyses (
                    user_id, filename, image_thumbnail_b64,
                    severity_score, severity_level, visual_description,
                    conditions_json, risk_factors_json, recommended_action,
                    action_detail, when_to_see_doctor_json, self_care_tips_json,
                    raw_text, symptom_intake_json
                ) VALUES (
                    %s, %s, %s,
                    %s, %s, %s,
                    %s, %s, %s,
                    %s, %s, %s,
                    %s, %s
                ) RETURNING id
                """,
                (
                    user_id,
                    filename,
                    image_thumbnail_b64,
                    analysis.get("severity_score"),
                    analysis.get("severity_level"),
                    analysis.get("visual_description"),
                    Json(analysis.get("conditions", [])),
                    Json(analysis.get("risk_factors", [])),
                    analysis.get("recommended_action"),
                    analysis.get("action_detail"),
                    Json(analysis.get("when_to_see_doctor", [])),
                    Json(analysis.get("self_care_tips", [])),
                    analysis.get("raw", ""),
                    Json(symptom_intake) if symptom_intake is not None else None,
                ),
            )
            new_id = cur.fetchone()[0]
        conn.commit()
    return new_id


def save_chat_message(analysis_id: int, role: str, content: str) -> None:
    """Insert one chat turn linked to a prior analysis row."""
    pool = get_pool()
    with pool.connection() as conn:
        with conn.cursor() as cur:
            cur.execute(
                "INSERT INTO chat_messages (analysis_id, role, content) "
                "VALUES (%s, %s, %s)",
                (analysis_id, role, content),
            )
        conn.commit()


def load_history(user_id: int, limit: int = 20) -> list[dict]:
    """Load a user's past analyses, most recent first, reshaped to match the
    in-session dict shape used everywhere else in the app (same keys as
    parsing.parse_analysis()'s output plus "timestamp"/"timestamp_dt"/
    "filename"/"id"), so render_severity_trend() and the sidebar's recent-
    history list work identically whether data came from a fresh DB load or
    a live session.
    """
    pool = get_pool()
    with pool.connection() as conn:
        with conn.cursor(row_factory=dict_row) as cur:
            cur.execute(
                "SELECT * FROM analyses WHERE user_id = %s "
                "ORDER BY created_at DESC LIMIT %s",
                (user_id, limit),
            )
            rows = cur.fetchall()

    history = []
    for row in rows:
        created_at: datetime.datetime | None = row.get("created_at")
        history.append({
            "id":                  row.get("id"),
            "severity_score":      row.get("severity_score"),
            "severity_level":      row.get("severity_level"),
            "visual_description":  row.get("visual_description"),
            "conditions":          row.get("conditions_json") or [],
            "risk_factors":        row.get("risk_factors_json") or [],
            "recommended_action":  row.get("recommended_action"),
            "action_detail":       row.get("action_detail"),
            "when_to_see_doctor":  row.get("when_to_see_doctor_json") or [],
            "self_care_tips":      row.get("self_care_tips_json") or [],
            "raw":                 row.get("raw_text") or "",
            "filename":            row.get("filename"),
            "timestamp_dt":        created_at,
            "timestamp":           created_at.strftime("%H:%M") if created_at else "",
        })
    return history


# ──────────────────────────────────────────────────────────────────────────
# ACCOUNTS
# ──────────────────────────────────────────────────────────────────────────
# Real username/password accounts (dermatica/auth.py owns the hashing +
# session logic; these are the thin, parameterized DB queries it builds on).
# The `users` table is the same one get_default_user_id() seeds for the no-auth
# fallback — accounts just add rows with a real bcrypt hash in password_hash.

def create_user(username: str, password_hash: str) -> int | None:
    """Insert a new account and return its id, or None if the username is
    already taken (ON CONFLICT DO NOTHING makes the insert a no-op, so
    fetchone() returns no row and we surface that as None for the caller to
    turn into a friendly 'username taken' message)."""
    pool = get_pool()
    with pool.connection() as conn:
        with conn.cursor() as cur:
            cur.execute(
                "INSERT INTO users (username, password_hash) VALUES (%s, %s) "
                "ON CONFLICT (username) DO NOTHING RETURNING id",
                (username, password_hash),
            )
            row = cur.fetchone()
        conn.commit()
    return row[0] if row else None


def get_user_by_username(username: str) -> dict | None:
    """Fetch id + password_hash for a login attempt (None if no such user)."""
    pool = get_pool()
    with pool.connection() as conn:
        with conn.cursor(row_factory=dict_row) as cur:
            cur.execute(
                "SELECT id, username, password_hash FROM users WHERE username = %s",
                (username,),
            )
            return cur.fetchone()


def get_user_by_id(user_id: int) -> dict | None:
    """Fetch id + username for restoring a session from a cookie token."""
    pool = get_pool()
    with pool.connection() as conn:
        with conn.cursor(row_factory=dict_row) as cur:
            cur.execute(
                "SELECT id, username FROM users WHERE id = %s", (user_id,)
            )
            return cur.fetchone()


def delete_user(user_id: int) -> None:
    """Permanently delete an account and everything owned by it. The
    analyses (and their chat_messages, via cascade) reference users(id) with
    ON DELETE CASCADE, so removing the user row removes all of their data in
    one statement — backs the Settings 'delete my account' control."""
    pool = get_pool()
    with pool.connection() as conn:
        with conn.cursor() as cur:
            cur.execute("DELETE FROM users WHERE id = %s", (user_id,))
        conn.commit()


def clear_history(user_id: int) -> None:
    """Delete all of a user's stored analyses. The chat_messages rows are
    removed automatically via their ON DELETE CASCADE foreign key, so this
    one DELETE clears both tables for the user. Backs the sidebar Settings
    "Clear Analysis History" control; callers guard with is_configured() and
    soft-fail so a DB hiccup never blocks the in-session reset.
    """
    pool = get_pool()
    with pool.connection() as conn:
        with conn.cursor() as cur:
            cur.execute("DELETE FROM analyses WHERE user_id = %s", (user_id,))
        conn.commit()


def load_chat_messages(analysis_id: int) -> list[dict]:
    """Load prior chat turns for an analysis, oldest first, shaped as
    {"role": ..., "content": ...} to match st.session_state.chat_messages'
    entry shape used by results_view.py's Follow-up Questions tab.
    """
    pool = get_pool()
    with pool.connection() as conn:
        with conn.cursor(row_factory=dict_row) as cur:
            cur.execute(
                "SELECT role, content FROM chat_messages "
                "WHERE analysis_id = %s ORDER BY created_at ASC",
                (analysis_id,),
            )
            rows = cur.fetchall()
    return [{"role": row["role"], "content": row["content"]} for row in rows]
