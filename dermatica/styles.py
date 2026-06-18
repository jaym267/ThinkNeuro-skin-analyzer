# -*- coding: utf-8 -*-
"""Style/color constants shared by the UI layer."""

SEVERITY_STYLES = {
    "MINIMAL":  {"color": "#2E7D53", "bg": "rgba(46,125,83,0.08)",   "border": "rgba(46,125,83,0.22)"},
    "LOW":      {"color": "#2B5C8A", "bg": "rgba(43,92,138,0.08)",   "border": "rgba(43,92,138,0.22)"},
    "MODERATE": {"color": "#A06B00", "bg": "rgba(160,107,0,0.08)",   "border": "rgba(160,107,0,0.22)"},
    "HIGH":     {"color": "#8B2A2A", "bg": "rgba(139,42,42,0.08)",   "border": "rgba(139,42,42,0.22)"},
    "CRITICAL": {"color": "#5C0F1E", "bg": "rgba(92,15,30,0.08)",    "border": "rgba(92,15,30,0.22)"},
}

ACTION_CONFIGS = {
    "URGENT_CARE":     {"title": "Seek Urgent Medical Care",           "color": "#8B2A2A", "bg": "rgba(139,42,42,0.05)",  "border": "rgba(139,42,42,0.18)"},
    "SEE_DOCTOR":      {"title": "Schedule a Doctor's Appointment",    "color": "#A06B00", "bg": "rgba(160,107,0,0.05)",  "border": "rgba(160,107,0,0.18)"},
    "MONITOR_AT_HOME": {"title": "Monitor at Home",                    "color": "#2E7D53", "bg": "rgba(46,125,83,0.05)",  "border": "rgba(46,125,83,0.18)"},
}

PROB_STYLES = {
    "HIGH":   {"bar": "#8B2A2A", "badge_bg": "rgba(139,42,42,0.08)",  "badge_color": "#8B2A2A", "badge_border": "rgba(139,42,42,0.25)", "pct": 88},
    "MEDIUM": {"bar": "#A06B00", "badge_bg": "rgba(160,107,0,0.08)",  "badge_color": "#A06B00", "badge_border": "rgba(160,107,0,0.25)", "pct": 52},
    "LOW":    {"bar": "#2B5C8A", "badge_bg": "rgba(43,92,138,0.08)",  "badge_color": "#2B5C8A", "badge_border": "rgba(43,92,138,0.25)", "pct": 20},
}

# Shared brand/semantic hex values, used by ui/sidebar.py and ui/components.py
# to replace ad-hoc inline hex literals that recur across the sidebar markup
# and the risk-factor / when-to-see-doctor / self-care cards.
BRAND = {"navy": "#1B3252", "gold": "#B8882A"}
SEMANTIC = {"danger": "#8B2A2A", "success": "#2E7D53"}

# ──────────────────────────────────────────────
# THEME (Phase 5: dark mode)
# ──────────────────────────────────────────────
# These two dicts mirror the CSS custom properties defined in the `:root`
# block of static/styles.css exactly (same keys, same meaning). load_css()
# in ui/components.py picks one dict based on the `dark` flag and renders it
# as the ACTIVE `:root { ... }` block — static/styles.css itself no longer
# hardcodes :root values, it only *consumes* var(--xxx) throughout the rest
# of its rules. Keep these keys in sync with any new var(--xxx) usage added
# to the stylesheet.
LIGHT_THEME = {
    "cream":    "#F7F4EF",
    "cream2":   "#EFEBe4",
    "white":    "#FFFFFF",
    "navy":     "#1B3252",
    "navy-mid": "#2A4A72",
    "gold":     "#B8882A",
    "txt0":     "#1A1918",
    "txt1":     "#4A4845",
    "txt2":     "#8A8785",
    "txt3":     "#B8B5B0",
    "border":   "#E4E0D8",
    "border2":  "#CCC8BF",
    "sd0": "0 1px 3px rgba(27,50,82,0.06), 0 4px 16px rgba(27,50,82,0.07)",
    "sd1": "0 2px 8px rgba(27,50,82,0.08), 0 8px 28px rgba(27,50,82,0.10)",
    "sd2": "0 4px 16px rgba(27,50,82,0.12), 0 16px 40px rgba(27,50,82,0.12)",
}

DARK_THEME = {
    "cream":    "#1A1D23",   # page background (was light cream)
    "cream2":   "#23272F",   # secondary surface (track backgrounds etc.)
    "white":    "#2A2E37",   # "card" surface (was pure white)
    "navy":     "#7FA8D9",   # primary accent — lightened navy for contrast on dark bg
    "navy-mid": "#9BBBE6",   # hover/secondary accent, lighter still
    "gold":     "#D9A94A",   # brand gold, brightened for dark-bg legibility
    "txt0":     "#EDEBE6",   # primary text (was near-black, now near-white)
    "txt1":     "#C7C3BC",   # secondary text
    "txt2":     "#9B978F",   # tertiary/muted text
    "txt3":     "#76726B",   # faintest text (timestamps, labels)
    "border":   "#3A3F49",   # hairline borders
    "border2":  "#4C525E",   # stronger borders/dividers
    "sd0": "0 1px 3px rgba(0,0,0,0.35), 0 4px 16px rgba(0,0,0,0.30)",
    "sd1": "0 2px 8px rgba(0,0,0,0.40), 0 8px 28px rgba(0,0,0,0.35)",
    "sd2": "0 4px 16px rgba(0,0,0,0.45), 0 16px 40px rgba(0,0,0,0.40)",
}
