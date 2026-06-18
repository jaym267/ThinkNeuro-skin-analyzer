# -*- coding: utf-8 -*-
"""Dual rate limiting: protects the shared Groq API key on a public
deployment via a global cap across all visitors (guards your quota and stays
under Groq's own per-minute limit) plus a per-session cap (stops one visitor
hammering or double-clicking). Tune RATE_LIMITS to taste."""
import threading
import time
from collections import deque

import streamlit as st

RATE_LIMITS = {
    "global_per_min": 20,    # total model calls/minute across everyone
    "global_per_day": 800,   # total model calls/day across everyone
    "session_per_min": 8,    # model calls/minute from a single visitor
}

@st.cache_resource
def _global_rate_state():
    # Shared across all sessions in the server process (one per deployment).
    return {"events": deque(), "lock": threading.Lock()}

def acquire_request_slot():
    """Reserve one model-call slot. Returns (ok, message). Only records the
    call when both the per-session and global limits allow it."""
    now = time.time()

    # per-session window (this visitor)
    sdq = st.session_state.setdefault("_req_times", deque())
    while sdq and now - sdq[0] > 60:
        sdq.popleft()
    if len(sdq) >= RATE_LIMITS["session_per_min"]:
        # sdq may be empty if the limit is configured at 0; fall back safely.
        oldest = sdq[0] if sdq else now
        wait = max(1, int(60 - (now - oldest)) + 1)
        return False, f"You're going a bit fast — please wait about {wait} seconds and try again."

    # global window (everyone), committed atomically
    state = _global_rate_state()
    with state["lock"]:
        gdq = state["events"]
        while gdq and now - gdq[0] > 86400:
            gdq.popleft()
        per_min = sum(1 for t in gdq if now - t <= 60)
        if per_min >= RATE_LIMITS["global_per_min"]:
            return False, "The analyzer is handling a lot of requests right now. Please wait a moment and try again."
        if len(gdq) >= RATE_LIMITS["global_per_day"]:
            return False, "The analyzer has reached today's usage limit. Please check back tomorrow."
        gdq.append(now)
    sdq.append(now)
    return True, ""
