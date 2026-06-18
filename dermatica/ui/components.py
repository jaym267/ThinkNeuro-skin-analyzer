# -*- coding: utf-8 -*-
"""Reusable HTML-rendering helpers shared across views."""
import html as html_lib
from pathlib import Path

import streamlit as st

from .. import styles


def _theme_root_block(dark: bool) -> str:
    """Builds the `:root { --xxx: ...; }` custom-property block from
    styles.DARK_THEME / styles.LIGHT_THEME. This is the entire dark-mode
    mechanism: rather than relying on a `[data-theme="dark"]` attribute
    selector (which would need JS to attach to Streamlit's document root —
    unreliable across Streamlit versions/sandboxing), we just pick which
    dict's values populate the single active `:root` block and inject that
    as plain CSS text. No JS, no DOM attribute propagation required."""
    theme = styles.DARK_THEME if dark else styles.LIGHT_THEME
    decls = "\n".join(f"  --{name}: {value};" for name, value in theme.items())
    return f":root {{\n{decls}\n}}"


def load_css(path: str, dark: bool = False) -> None:
    """Injects the app's stylesheet, with the `:root` variable block
    generated for the active theme (light by default, dark when
    dark=True). See _theme_root_block() for why this is a Python-side
    pick-and-inject rather than a CSS attribute-selector cascade."""
    css = Path(path).read_text(encoding="utf-8")
    root_block = _theme_root_block(dark)
    st.markdown(f"<style>{root_block}\n{css}</style>", unsafe_allow_html=True)


def render_list_card(title: str, items: list, accent_hex: str) -> None:
    """Renders a g-card with a colored accent bar, a title, and one
    .list-row per item with a matching colored dot. Used for the
    Identified Risk Factors / When to Seek Medical Care / Self-Care
    Recommendations cards, which were previously three near-identical
    inline blocks."""
    if not items:
        return
    rows = "".join(
        f'<div class="list-row"><span class="list-dot" '
        f'style="background:{accent_hex};"></span>{html_lib.escape(item)}</div>'
        for item in items
    )
    st.markdown(f"""
    <div class="g-card fade">
      <div class="g-card-header">
        <div class="g-accent" style="background:{accent_hex};"></div>
        <div class="g-title">{html_lib.escape(title)}</div>
      </div>
      {rows}
    </div>""", unsafe_allow_html=True)


def render_condition_card(condition: dict) -> str:
    """Returns the HTML string for one condition's cond-card block (used
    inside a loop that concatenates several before a single st.markdown
    call)."""
    lvl  = condition.get("level", "MEDIUM")
    ps   = styles.PROB_STYLES.get(lvl, styles.PROB_STYLES["MEDIUM"])
    name = html_lib.escape(condition.get("name", "Unknown"))
    desc = html_lib.escape(condition.get("description", ""))
    return f"""
  <div class="cond-card">
    <div style="display:flex;justify-content:space-between;
                align-items:center;margin-bottom:.5rem;">
      <div class="cond-name">{name}</div>
      <span class="prob-badge"
            style="background:{ps['badge_bg']};color:{ps['badge_color']};
                   border-color:{ps['badge_border']};">{html_lib.escape(lvl)}</span>
    </div>
    <div class="cond-bar">
      <div class="cond-fill"
           style="width:{ps['pct']}%;background:{ps['bar']};"></div>
    </div>
    <div style="display:flex;justify-content:space-between;
                margin-top:.45rem;align-items:flex-start;">
      <div style="font-size:.79rem;color:#8A8785;line-height:1.5;
                  font-style:italic;flex:1;">{desc}</div>
      <div style="font-size:.7rem;color:#B8B5B0;flex-shrink:0;
                  margin-left:10px;">~{ps['pct']}%</div>
    </div>
  </div>"""
