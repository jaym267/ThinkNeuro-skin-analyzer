# -*- coding: utf-8 -*-
"""Purely educational, stateless content: the ABCDE mole self-exam checklist.

No backend or prompt impact -- this never feeds into the analysis call."""
import streamlit as st

_ABCDE_ITEMS = [
    ("A", "Asymmetry", "One half of the mole or spot doesn't match the other half in shape, size, or color."),
    ("B", "Border", "Edges are irregular, ragged, notched, or blurred rather than smooth and even."),
    ("C", "Color", "Color is uneven -- shades of brown, black, tan, white, red, or blue within the same spot."),
    ("D", "Diameter", "Larger than about 6mm (roughly the size of a pencil eraser), though some can be smaller."),
    ("E", "Evolving", "Any change over time in size, shape, color, elevation, or new symptoms like itching or bleeding."),
]


def render_abcde_checklist() -> None:
    """Renders a styled, collapsible ABCDE self-exam reference card. Purely
    educational -- does not read or write any session state."""
    st.markdown("""
    <div class="g-card fade">
      <div class="g-card-header">
        <div class="g-accent"></div>
        <div>
          <div class="g-title">ABCDE Self-Exam Checklist</div>
          <div class="g-sub">A quick dermatology reference for what to look for in a mole or skin spot.</div>
        </div>
      </div>
    </div>
    """, unsafe_allow_html=True)

    with st.expander("What does ABCDE stand for?", expanded=False):
        for letter, title, desc in _ABCDE_ITEMS:
            st.markdown(
                f'<div class="list-row"><span class="list-dot"></span>'
                f'<strong>{letter} &mdash; {title}:</strong>&nbsp;{desc}</div>',
                unsafe_allow_html=True,
            )
        st.markdown(
            '<div class="upload-hint" style="margin-top:1rem;">'
            "This checklist is educational only and is not a substitute for "
            "professional evaluation. If a spot meets any of these criteria, "
            "consider having it examined by a licensed dermatologist."
            "</div>",
            unsafe_allow_html=True,
        )
