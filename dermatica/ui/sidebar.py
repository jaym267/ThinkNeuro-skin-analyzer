# -*- coding: utf-8 -*-
"""Sidebar: status/stats/history/skin-tips panel plus the JS-injected
show/hide toggle handle."""
import html as html_lib
import logging
import time

import streamlit as st
import streamlit.components.v1 as components

from .. import db, styles

logger = logging.getLogger("dermatica")

# Plain-language skin tips (sourced from the American Academy of Dermatology).
# The sidebar shows three at a time and rotates to the next three every 10 min.
SKIN_TIPS = [
    ("Sunscreen Every Day",        "Put on sunscreen rated SPF 30 or higher every morning before you head out — even on cloudy days."),
    ("Wash Your Face Twice a Day", "Clean your face when you wake up, before bed, and after sweating to clear off oil, dirt, and germs."),
    ("Go Easy — Don't Scrub", "Wash with warm water and your fingertips in gentle circles; hard scrubbing irritates skin and can worsen breakouts."),
    ("Moisturize While Damp",      "Smooth on moisturizer within a few minutes of washing, while your skin is still a little wet, to lock in moisture."),
    ("Keep Showers Short",         "Keep baths and showers to about 5–10 minutes with warm — not hot — water so your skin doesn't dry out."),
    ("Pat Dry, Don't Rub",         "After washing, gently pat your skin dry with a towel instead of rubbing, then moisturize right away."),
    ("Add Moisture to the Air",    "Run a humidifier in dry rooms or during winter to help your skin hold on to water."),
    ("Skip Tanning Beds",          "Tanning beds and harsh sun cause wrinkles, dark spots, and skin cancer; use a self-tanner if you want color."),
    ("Check Your Skin Monthly",    "Once a month, look for new spots or moles that itch, bleed, or change — caught early, skin cancer is very treatable."),
    ("Don't Smoke",                "Smoking speeds up wrinkles and slows healing, so quitting helps your skin look and feel healthier."),
    ("Match Products to Your Skin","Choose cleansers and creams made for your skin type — oily, dry, or sensitive — not just any product."),
    ("Fragrance-Free if Sensitive","If your skin gets irritated easily, pick fragrance-free products and avoid harsh, alcohol-based ones."),
    ("Keep Stress in Check",       "Stress can set off acne, eczema, and rosacea, so make time to relax and unwind."),
    ("Protect Your Hands",         "Wear gloves while washing dishes or cleaning so soap and water don't dry out and crack your skin."),
    ("Wear Soft, Loose Cotton",    "Pick soft, loose cotton clothing; tight or scratchy fabrics like wool can irritate sensitive skin."),
    ("Keep It Simple",             "Using too many products at once can irritate your skin — add new ones one at a time."),
    ("Shave After a Warm Shower",  "Shave once warm water has softened your skin, use a sharp blade, and moisturize right afterward."),
    ("Get Enough Sleep",           "Your skin repairs itself overnight, so aim for 7–9 hours to help keep it healthy."),
]


@st.fragment(run_every=600)   # auto-reruns every 10 minutes
def render_skin_tips():
    # Show three tips, advancing to the next three every 10-minute window so the
    # panel keeps cycling through the full list on its own.
    per    = 3
    n      = len(SKIN_TIPS)
    start  = (int(time.time() // 600) * per) % n
    chosen = [SKIN_TIPS[(start + i) % n] for i in range(per)]
    cards  = "".join(
        f'<div class="tip-card"><div class="tip-rule"></div>'
        f'<div class="tip-ttl">{title}</div>'
        f'<div class="tip-txt">{text}</div></div>'
        for title, text in chosen
    )
    st.markdown(
        f'<div class="sb-section"><div class="sb-title">Skin Health Guidelines</div>'
        f'{cards}</div>',
        unsafe_allow_html=True,
    )


def _render_sidebar_toggle():
    """Injects a "Hide Panel" button into the sidebar (below the guidelines) and a
    floating "Show Panel" tab that appears when the sidebar is collapsed. The
    sidebar is slid out with a negative margin so the main content reflows to
    full width. State persists on the parent window across Streamlit reruns."""
    components.html("""
<script>
(function(){
  var pwin = window.parent, pdoc = pwin.document;
  // The panel starts hidden on every fresh load so it never blocks the screen.
  if (pwin.__dermHidden === undefined) pwin.__dermHidden = true;
  function sidebar(){ return pdoc.querySelector('[data-testid="stSidebar"]'); }

  function ensureStyles(){
    if (pdoc.getElementById('derm-toggle-style')) return;
    var s = pdoc.createElement('style');
    s.id = 'derm-toggle-style';
    s.textContent = `
      [data-testid="stSidebar"]{
        transition: margin-left .35s cubic-bezier(0.4,0,0.2,1) !important;
      }
      /* the single always-visible toggle handle (rides the edge of the panel) */
      #derm-handle{
        position:fixed; top:50%; left:0; transform:translateY(-50%);
        z-index:1000000; display:flex;
        flex-direction:column; align-items:center; justify-content:center; gap:1px;
        width:30px; height:70px; padding-left:3px;
        background:#1B3252; color:#FFFFFF; border:none;
        border-radius:0 36px 36px 0;
        cursor:pointer; user-select:none;
        box-shadow:3px 2px 16px rgba(27,50,82,.34);
        font-family:'Times New Roman',Times,Georgia,serif;
        transition:left .35s cubic-bezier(0.4,0,0.2,1), background .2s ease, box-shadow .2s ease;
      }
      #derm-handle:hover{ background:#2A4A72; box-shadow:4px 3px 22px rgba(27,50,82,.44); }
      /* a single chevron arrow that points the way the panel will move */
      #derm-handle .derm-arrow{
        width:11px; height:11px; margin-left:-3px;
        border-top:2.5px solid #FFFFFF;
        border-right:2.5px solid #FFFFFF;
        transform:rotate(45deg);            /* points right = show */
        transition:transform .3s ease, margin-left .3s ease;
      }
      /* when the panel is open, flip the arrow to point back at it = hide */
      #derm-handle.derm-open .derm-arrow{
        margin-left:3px;
        transform:rotate(-135deg);          /* points left = hide */
      }
    `;
    pdoc.head.appendChild(s);
  }

  var PANEL_W = 300;  // matches the fixed sidebar width forced in CSS

  function applyState(){
    var sb = sidebar(); if(!sb) return;
    var handle = pdoc.getElementById('derm-handle');
    var hidden = !!pwin.__dermHidden;
    var sbTarget = hidden ? (-(PANEL_W + 8) + 'px') : '0px';  // slide panel out / in
    var hTarget  = hidden ? '0px' : (PANEL_W + 'px');          // handle rides panel edge

    if (!pwin.__dermInit){
      // first paint after a load: snap into place instantly, no slide
      sb.style.setProperty('transition', 'none', 'important');
      sb.style.marginLeft = sbTarget;
      if (handle){ handle.style.transition = 'none'; handle.style.left = hTarget; }
      void sb.offsetWidth;                                // force reflow
      sb.style.removeProperty('transition');
      if (handle) handle.style.removeProperty('transition');
      pwin.__dermInit = true;
    } else {
      if (sb.style.marginLeft !== sbTarget) sb.style.marginLeft = sbTarget;
      if (handle && handle.style.left !== hTarget) handle.style.left = hTarget;
    }
    if (handle) handle.classList.toggle('derm-open', !hidden);
    pdoc.body.classList.toggle('derm-hidden', hidden);
  }

  function setHidden(v){ pwin.__dermHidden = v; applyState(); }

  function ensureHandle(){
    if (pdoc.getElementById('derm-handle')) return;
    var b = pdoc.createElement('div');
    b.id = 'derm-handle';
    b.setAttribute('role', 'button');
    b.setAttribute('tabindex', '0');
    b.setAttribute('aria-label', 'Show or hide the panel');
    b.setAttribute('title', 'Show or hide the panel');
    b.innerHTML = '<span class="derm-arrow"></span>';
    b.addEventListener('click', function(){ setHidden(!pwin.__dermHidden); });
    b.addEventListener('keydown', function(e){
      if (e.key === 'Enter' || e.key === ' '){ e.preventDefault(); setHidden(!pwin.__dermHidden); }
    });
    pdoc.body.appendChild(b);
  }

  function tick(){ ensureStyles(); ensureHandle(); applyState(); }

  tick();
  [120,300,600,1200].forEach(function(t){ setTimeout(tick, t); });

  if (!pwin.__dermObserver){
    var pending = false;
    pwin.__dermObserver = new MutationObserver(function(){
      if (pending) return; pending = true;
      requestAnimationFrame(function(){ pending = false; tick(); });
    });
    pwin.__dermObserver.observe(pdoc.body, { childList:true, subtree:true });
  }
})();
</script>
""", height=0, scrolling=False)


_TEXT_SIZE_OPTIONS = ["Small", "Default", "Large"]


def _clear_history() -> None:
    """Reset all per-session analysis/chat state and, when a DB is
    configured, delete the stored rows too (soft-fail so a persistence
    hiccup never blocks the in-app reset). history_seeded is left True so
    the just-cleared history isn't immediately re-seeded from the DB on the
    next run within this session."""
    for key in ("analysis_history", "chat_messages"):
        st.session_state[key] = []
    for key in ("current_analysis", "current_image", "current_image_b64", "pending_q"):
        st.session_state[key] = None
    st.session_state.history_seeded = True
    if db.is_configured():
        try:
            db.clear_history(db.get_default_user_id())
        except Exception:
            logger.warning("Failed to clear DB analysis history.", exc_info=True)
    st.toast("Analysis history cleared.")
    st.rerun()


def _render_settings_control():
    """Renders the sidebar Settings card: appearance controls (dark mode,
    reduce motion, text size) and a data control (clear history).

    Built with a real st.container(border=True) rather than a hand-written
    <div>: Streamlit renders each widget as its own DOM block, so opening a
    wrapper <div> in one st.markdown and closing it in another never
    actually contained the widgets — the card rendered empty and the toggle
    floated outside it. The container is styled to match the other sidebar
    cards in static/styles.css.

    The toggles/radio write straight to st.session_state via their keys and
    trigger a rerun on change, so app.py picks up the new dark_mode /
    reduce_motion / text_size values on the next run — no explicit rerun
    needed for those."""
    # key="settings_card" adds a stable `st-key-settings_card` class to the
    # container so static/styles.css can target this one card precisely
    # (every st.container shares the generic stVerticalBlock testid otherwise).
    with st.container(border=True, key="settings_card"):
        st.markdown('<div class="sb-title">Settings</div>', unsafe_allow_html=True)

        st.markdown('<div class="set-label">Appearance</div>', unsafe_allow_html=True)
        st.toggle("Dark Mode", key="dark_mode")
        st.toggle(
            "Reduce Motion",
            key="reduce_motion",
            help="Turn off background animations and movement.",
        )
        st.radio(
            "Text Size",
            _TEXT_SIZE_OPTIONS,
            key="text_size",
            horizontal=True,
        )

        st.markdown('<div class="set-label">Data</div>', unsafe_allow_html=True)
        if st.button(
            "Clear Analysis History",
            key="clear_history_btn",
            use_container_width=True,
            help="Remove all analyses and chats from this session"
                 " (and from the database, if one is configured).",
        ):
            _clear_history()


def render_sidebar():
    with st.sidebar:
        st.markdown("""
        <div class="sb-logo">
          <div style="font-size:.65rem;letter-spacing:3px;text-transform:uppercase;
                      color:var(--gold);margin-bottom:.5rem;">Advanced Skin Analysis</div>
          <div style="font-size:1.45rem;font-weight:700;color:var(--navy);letter-spacing:-.3px;">Dermatica</div>
        </div>
        """, unsafe_allow_html=True)

        st.markdown("""
        <div class="sb-section">
          <div class="sb-title">System Status</div>
          <div style="font-size:.81rem;color:var(--txt1);line-height:2.3;">
            <span class="status-dot"></span>AI Engine Online<br>
            <span class="status-dot"></span>Groq API Connected<br>
            <span class="status-dot"></span>Vision Model Active
          </div>
        </div>
        """, unsafe_allow_html=True)

        n_scans = len(st.session_state.analysis_history)
        n_chats = len(st.session_state.chat_messages)
        st.markdown(f"""
        <div class="sb-section">
          <div class="sb-title">Session Statistics</div>
          <div style="display:grid;grid-template-columns:1fr 1fr;gap:.6rem;margin-top:.1rem;">
            <div style="text-align:center;padding:.85rem .5rem;background:var(--white);
                        border:1px solid var(--border);border-radius:10px;">
              <div style="font-size:1.7rem;font-weight:700;color:var(--navy);line-height:1;">{n_scans}</div>
              <div style="font-size:.6rem;color:var(--txt3);text-transform:uppercase;
                          letter-spacing:1.5px;margin-top:.25rem;">Scans</div>
            </div>
            <div style="text-align:center;padding:.85rem .5rem;background:var(--white);
                        border:1px solid var(--border);border-radius:10px;">
              <div style="font-size:1.7rem;font-weight:700;color:var(--navy);line-height:1;">{n_chats}</div>
              <div style="font-size:.6rem;color:var(--txt3);text-transform:uppercase;
                          letter-spacing:1.5px;margin-top:.25rem;">Q&amp;A</div>
            </div>
          </div>
        </div>
        """, unsafe_allow_html=True)

        if st.session_state.analysis_history:
            hist_html = '<div class="sb-section"><div class="sb-title">Recent Analyses</div>'
            for h in reversed(st.session_state.analysis_history[-5:]):
                lvl   = h.get("severity_level", "MODERATE")
                style = styles.SEVERITY_STYLES.get(lvl, styles.SEVERITY_STYLES["MODERATE"])
                conds = h.get("conditions", [])
                top   = conds[0]["name"] if conds else "Unknown"
                ts    = h.get("timestamp", "")
                hist_html += f"""
                <div class="hist-item">
                  <div class="hist-dot" style="background:{style['color']};
                       box-shadow:0 0 0 3px {style['bg']};"></div>
                  <div style="flex:1;min-width:0;">
                    <div class="hist-cond">{html_lib.escape(top)}</div>
                    <div style="display:flex;align-items:center;gap:6px;margin-top:3px;">
                      <span style="font-size:.62rem;padding:2px 8px;border-radius:100px;
                                   background:{style['bg']};color:{style['color']};
                                   border:1px solid {style['border']};font-weight:700;
                                   letter-spacing:.5px;">{html_lib.escape(lvl)}</span>
                      <span class="hist-time">{ts}</span>
                    </div>
                  </div>
                </div>"""
            hist_html += "</div>"
            st.markdown(hist_html, unsafe_allow_html=True)

        render_skin_tips()

        _render_settings_control()

    _render_sidebar_toggle()
