# -*- coding: utf-8 -*-
# Last updated June 2026
import os
import re
import base64
import datetime
import io
import streamlit as st
import streamlit.components.v1 as components
from PIL import Image
from groq import Groq
from dotenv import load_dotenv

load_dotenv()

# ──────────────────────────────────────────────
# PAGE CONFIG
# ──────────────────────────────────────────────
st.set_page_config(
    page_title="Dermatica Pro | Advanced Skin Analysis",
    page_icon=None,
    layout="wide",
    initial_sidebar_state="expanded",
)

# ──────────────────────────────────────────────
# CONSTANTS
# ──────────────────────────────────────────────
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

# ──────────────────────────────────────────────
# GROQ CLIENT
# ──────────────────────────────────────────────
@st.cache_resource
def get_client():
    key = os.getenv("GROQ_API_KEY")
    if not key:
        st.error("GROQ_API_KEY not found. Add it to your .env file.")
        st.stop()
    return Groq(api_key=key)

client = get_client()

# ──────────────────────────────────────────────
# HELPERS
# ──────────────────────────────────────────────
def image_to_base64(img: Image.Image) -> str:
    buf = io.BytesIO()
    img.save(buf, format="JPEG", quality=90)
    return base64.b64encode(buf.getvalue()).decode()

def parse_analysis(text: str) -> dict:
    out = {
        "severity_score": 5.0,
        "severity_level": "MODERATE",
        "visual_description": "",
        "conditions": [],
        "risk_factors": [],
        "recommended_action": "SEE_DOCTOR",
        "action_detail": "",
        "when_to_see_doctor": [],
        "self_care_tips": [],
        "raw": text,
    }

    def grab(pattern, flags=re.DOTALL):
        m = re.search(pattern, text, flags)
        return m.group(1).strip() if m else ""

    s = grab(r"SEVERITY_SCORE:\s*([0-9]+(?:\.[0-9]+)?)", 0)
    if s:
        out["severity_score"] = min(10.0, max(1.0, float(s)))

    lvl = grab(r"SEVERITY_LEVEL:\s*(\w+)", 0)
    if lvl:
        out["severity_level"] = lvl.upper()

    vd = grab(r"VISUAL_DESCRIPTION:\s*\n(.*?)(?=\n[A-Z_]{3,}:|\Z)")
    if vd:
        out["visual_description"] = vd

    cblock = grab(r"CONDITIONS:\s*\n(.*?)(?=\n[A-Z_]{3,}:|\Z)")
    for line in cblock.split("\n"):
        line = line.strip().lstrip("-*+ ").strip()
        if "|" in line:
            parts = [p.strip() for p in line.split("|")]
            out["conditions"].append({
                "name":        parts[0] if parts else "Unknown",
                "level":       parts[1].upper() if len(parts) > 1 else "MEDIUM",
                "description": parts[2] if len(parts) > 2 else "",
            })

    rf = grab(r"RISK_FACTORS:\s*\n?(.*?)(?=\n[A-Z_]{3,}:|\Z)")
    if rf:
        out["risk_factors"] = [r.strip() for r in re.split(r"[,\n]", rf) if r.strip()]

    ra = grab(r"RECOMMENDED_ACTION:\s*(\w+(?:_\w+)?)", 0)
    if ra:
        out["recommended_action"] = ra.upper()

    ad = grab(r"ACTION_DETAIL:\s*\n(.*?)(?=\n[A-Z_]{3,}:|\Z)")
    if ad:
        out["action_detail"] = ad

    for line in grab(r"WHEN_TO_SEE_DOCTOR:\s*\n(.*?)(?=\n[A-Z_]{3,}:|\Z)").split("\n"):
        line = line.strip().lstrip("-*+ ").strip()
        if line:
            out["when_to_see_doctor"].append(line)

    for line in grab(r"SELF_CARE_TIPS:\s*\n(.*?)(?=\n[A-Z_]{3,}:|\Z)").split("\n"):
        line = line.strip().lstrip("-*+ ").strip()
        if line:
            out["self_care_tips"].append(line)

    return out

def analyze_image(img: Image.Image) -> dict:
    b64 = image_to_base64(img)
    prompt = (
        "You are a professional dermatology AI assistant. Analyze this skin image carefully.\n\n"
        "Return your response in EXACTLY this format -- keep ALL labels exactly as shown:\n\n"
        "SEVERITY_SCORE: [number 1-10]\n"
        "SEVERITY_LEVEL: [MINIMAL/LOW/MODERATE/HIGH/CRITICAL]\n\n"
        "VISUAL_DESCRIPTION:\n"
        "[2-3 sentences on color, texture, pattern, distribution, size]\n\n"
        "CONDITIONS:\n"
        "- [Most likely] | [HIGH/MEDIUM/LOW] | [1-sentence description]\n"
        "- [Second]      | [HIGH/MEDIUM/LOW] | [1-sentence description]\n"
        "- [Third]       | [HIGH/MEDIUM/LOW] | [1-sentence description]\n\n"
        "RISK_FACTORS:\n"
        "[comma-separated list of observed risk factors]\n\n"
        "RECOMMENDED_ACTION: [URGENT_CARE/SEE_DOCTOR/MONITOR_AT_HOME]\n"
        "ACTION_DETAIL:\n"
        "[2-3 sentences on recommended action and timeline]\n\n"
        "WHEN_TO_SEE_DOCTOR:\n"
        "- [warning sign 1]\n"
        "- [warning sign 2]\n"
        "- [warning sign 3]\n\n"
        "SELF_CARE_TIPS:\n"
        "- [tip 1]\n"
        "- [tip 2]\n"
        "- [tip 3]\n\n"
        "IMPORTANT: This is NOT a medical diagnosis. Always consult a licensed dermatologist."
    )
    resp = client.chat.completions.create(
        model="meta-llama/llama-4-scout-17b-16e-instruct",
        messages=[{"role": "user", "content": [
            {"type": "text", "text": prompt},
            {"type": "image_url", "image_url": {"url": f"data:image/jpeg;base64,{b64}"}},
        ]}],
        max_tokens=1500,
        temperature=0.2,
    )
    return parse_analysis(resp.choices[0].message.content)

def ask_followup(question: str, analysis: dict, img: Image.Image) -> str:
    b64 = image_to_base64(img)
    system = (
        "You are a helpful dermatology AI assistant. "
        f"Previous analysis:\n{analysis.get('raw','')[:1200]}\n\n"
        "Answer concisely. Always advise consulting a licensed dermatologist."
    )
    msgs = [{"role": "system", "content": system}]
    for m in st.session_state.chat_messages:
        msgs.append({"role": m["role"], "content": m["content"]})
    msgs.append({"role": "user", "content": [
        {"type": "text", "text": question},
        {"type": "image_url", "image_url": {"url": f"data:image/jpeg;base64,{b64}"}},
    ]})
    resp = client.chat.completions.create(
        model="meta-llama/llama-4-scout-17b-16e-instruct",
        messages=msgs,
        max_tokens=600,
        temperature=0.4,
    )
    return resp.choices[0].message.content

def build_report(analysis: dict, filename: str) -> str:
    now   = datetime.datetime.now().strftime("%B %d, %Y at %H:%M")
    conds = "\n".join(
        f"  [{c['level']:6}] {c['name']}\n          {c.get('description','')}"
        for c in analysis.get("conditions", [])
    )
    rfs  = "\n".join(f"  - {r}" for r in analysis.get("risk_factors", []))
    wtsd = "\n".join(f"  - {s}" for s in analysis.get("when_to_see_doctor", []))
    sct  = "\n".join(f"  - {t}" for t in analysis.get("self_care_tips", []))
    return f"""
DERMAI PRO -- SKIN ANALYSIS REPORT
=====================================

Generated : {now}
File      : {filename}

-------------------------------------
SEVERITY ASSESSMENT
  Level : {analysis.get('severity_level','N/A')}
  Score : {analysis.get('severity_score','N/A')}/10

-------------------------------------
VISUAL OBSERVATIONS
{analysis.get('visual_description','N/A')}

-------------------------------------
POSSIBLE CONDITIONS
{conds or '  N/A'}

-------------------------------------
RISK FACTORS
{rfs or '  N/A'}

-------------------------------------
RECOMMENDED ACTION : {analysis.get('recommended_action','N/A').replace('_',' ')}
{analysis.get('action_detail','')}

-------------------------------------
WHEN TO SEEK MEDICAL ATTENTION
{wtsd or '  N/A'}

-------------------------------------
SELF-CARE RECOMMENDATIONS
{sct or '  N/A'}

-------------------------------------
MEDICAL DISCLAIMER
This report is AI-generated for informational purposes only.
It does NOT constitute a medical diagnosis or treatment advice.
Always consult a licensed dermatologist or healthcare provider.

-------------------------------------
Dermatica Pro | Powered by Groq & Llama AI
"""

# ──────────────────────────────────────────────
# SESSION STATE
# ──────────────────────────────────────────────
for k, v in {
    "analysis_history": [],
    "chat_messages":    [],
    "current_analysis": None,
    "current_image":    None,
}.items():
    if k not in st.session_state:
        st.session_state[k] = v

# ──────────────────────────────────────────────
# STYLES
# ──────────────────────────────────────────────
st.markdown("""
<style>

/* ── PALETTE ── */
:root {
  --cream:      #F7F4EF;
  --cream2:     #EFEBe4;
  --white:      #FFFFFF;
  --navy:       #1B3252;
  --navy-mid:   #2A4A72;
  --gold:       #B8882A;
  --txt0:       #1A1918;
  --txt1:       #4A4845;
  --txt2:       #8A8785;
  --txt3:       #B8B5B0;
  --border:     #E4E0D8;
  --border2:    #CCC8BF;
  --sd0: 0 1px 3px rgba(27,50,82,0.06), 0 4px 16px rgba(27,50,82,0.07);
  --sd1: 0 2px 8px rgba(27,50,82,0.08), 0 8px 28px rgba(27,50,82,0.10);
  --sd2: 0 4px 16px rgba(27,50,82,0.12), 0 16px 40px rgba(27,50,82,0.12);
}

/* ── RESET ── */
*, *::before, *::after { box-sizing: border-box; }

html, body, .main, [data-testid="stAppViewContainer"] {
  background: var(--cream) !important;
  color: var(--txt0) !important;
  font-family: 'Times New Roman', Times, Georgia, serif !important;
}

#MainMenu, footer, header { visibility: hidden; }
.stDeployButton { display: none !important; }
.block-container { padding: 0 2.5rem 4rem !important; max-width: 1380px !important; }

/* ── SCROLLBAR ── */
::-webkit-scrollbar { width: 6px; }
::-webkit-scrollbar-track { background: var(--cream2); }
::-webkit-scrollbar-thumb { background: var(--border2); border-radius: 100px; }
::-webkit-scrollbar-thumb:hover { background: var(--navy-mid); }

/* ── GLOBAL TYPE ── */
h1, h2, h3, h4, h5, h6, p, span, div, label, input, button, a, li, td, th {
  font-family: 'Times New Roman', Times, Georgia, serif !important;
}

/* ── HERO ── */
.hero {
  background: var(--white);
  border-bottom: 1px solid var(--border);
  padding: 3rem 3.5rem 2.5rem;
  margin: 0 -2.5rem 2.5rem;
  position: relative;
  overflow: hidden;
}
.hero::after {
  content: '';
  position: absolute;
  bottom: 0; left: 3.5rem; right: 3.5rem;
  height: 2px;
  background: linear-gradient(90deg, var(--navy), var(--gold), transparent);
  border-radius: 100px;
}
.hero-eyebrow {
  font-size: .7rem;
  letter-spacing: 3.5px;
  text-transform: uppercase;
  color: var(--gold);
  margin-bottom: 1rem;
  font-weight: 400;
}
.hero-title {
  font-size: 3.2rem;
  font-weight: 700;
  line-height: 1.05;
  color: var(--navy);
  letter-spacing: -.5px;
  margin-bottom: .6rem;
}
.hero-sub {
  font-size: 1.05rem;
  color: var(--txt1);
  font-style: italic;
  line-height: 1.6;
  max-width: 620px;
}
.status-bar {
  display: flex;
  gap: 2rem;
  margin-top: 1.8rem;
  flex-wrap: wrap;
}
.s-pill {
  display: flex;
  align-items: center;
  gap: 8px;
  font-size: .73rem;
  color: var(--txt2);
  letter-spacing: .8px;
  text-transform: uppercase;
}
.s-dot {
  width: 6px; height: 6px;
  background: #2E7D53;
  border-radius: 50%;
  flex-shrink: 0;
  box-shadow: 0 0 0 3px rgba(46,125,83,0.18);
  animation: pulse-dot 2.8s ease-in-out infinite;
}
@keyframes pulse-dot {
  0%, 100% { box-shadow: 0 0 0 3px rgba(46,125,83,0.18); }
  50%       { box-shadow: 0 0 0 5px rgba(46,125,83,0.08); }
}

/* ── DISCLAIMER ── */
.disclaimer {
  background: var(--white);
  border: 1px solid var(--border);
  border-left: 3px solid var(--gold);
  border-radius: 10px;
  padding: 1rem 1.4rem;
  margin-bottom: 2rem;
  font-size: .83rem;
  color: var(--txt1);
  line-height: 1.7;
  box-shadow: var(--sd0);
}

/* ── CARD ── */
.g-card {
  background: var(--white);
  border: 1px solid var(--border);
  border-radius: 14px;
  padding: 1.5rem 1.6rem;
  margin-bottom: 1.1rem;
  box-shadow: var(--sd0);
  transition: box-shadow .25s ease, transform .25s ease;
}
.g-card:hover {
  box-shadow: var(--sd1);
  transform: translateY(-1px);
}
.g-card-header {
  display: flex;
  align-items: flex-start;
  gap: 12px;
  padding-bottom: 1rem;
  margin-bottom: 1.1rem;
  border-bottom: 1px solid var(--border);
}
.g-accent {
  width: 3px;
  min-height: 38px;
  border-radius: 100px;
  background: var(--navy);
  flex-shrink: 0;
  margin-top: 2px;
}
.g-title {
  font-size: 1rem;
  font-weight: 700;
  color: var(--txt0);
  margin-bottom: 2px;
  letter-spacing: .1px;
}
.g-sub {
  font-size: .74rem;
  color: var(--txt2);
  font-style: italic;
}

/* ── SECTION LABEL ── */
.sec-lbl {
  display: flex;
  align-items: center;
  gap: 10px;
  font-size: .68rem;
  color: var(--txt3);
  text-transform: uppercase;
  letter-spacing: 2.5px;
  margin: 1.75rem 0 1rem;
}
.sec-lbl::after {
  content: '';
  flex: 1;
  height: 1px;
  background: linear-gradient(90deg, var(--border), transparent);
}

/* ── SEVERITY BAR ── */
.sev-wrap {
  background: var(--cream2);
  border-radius: 100px;
  height: 8px;
  overflow: hidden;
  border: 1px solid var(--border);
}
.sev-fill {
  height: 100%;
  border-radius: 100px;
  transition: width 1.1s cubic-bezier(0.4,0,0.2,1);
  position: relative;
}
.sev-fill::after {
  content: '';
  position: absolute; inset: 0;
  background: linear-gradient(90deg, transparent 30%, rgba(255,255,255,.35), transparent 70%);
  animation: sheen 2.5s ease-in-out infinite;
}
@keyframes sheen { 0%{transform:translateX(-100%)} 100%{transform:translateX(100%)} }
.sev-labels { display:flex; justify-content:space-between; margin-top:.45rem; }
.sev-label  { font-size:.65rem; color:var(--txt3); font-style:italic; }

/* ── CONDITION CARD ── */
.cond-card {
  background: var(--cream);
  border: 1px solid var(--border);
  border-radius: 10px;
  padding: .95rem 1.1rem;
  margin-bottom: .65rem;
  transition: border-color .2s ease, box-shadow .2s ease, transform .2s ease;
}
.cond-card:hover {
  border-color: var(--border2);
  box-shadow: var(--sd0);
  transform: translateX(3px);
}
.cond-name { font-size: .93rem; font-weight: 700; color: var(--txt0); margin-bottom: .5rem; }
.cond-bar  {
  background: var(--cream2);
  border-radius: 100px;
  height: 5px;
  overflow: hidden;
  border: 1px solid var(--border);
}
.cond-fill { height: 100%; border-radius: 100px; }
.prob-badge {
  font-size: .65rem;
  font-weight: 700;
  padding: 3px 10px;
  border-radius: 100px;
  text-transform: uppercase;
  letter-spacing: .8px;
  border: 1px solid;
}

/* ── ACTION CARD ── */
.act-card {
  border-radius: 12px;
  padding: 1.3rem 1.5rem;
  margin-bottom: 1rem;
  border: 1px solid;
  transition: box-shadow .2s ease;
}
.act-card:hover { box-shadow: var(--sd1); }
.act-title { font-size: 1rem; font-weight: 700; margin-bottom: .4rem; }
.act-desc  { font-size: .84rem; color: var(--txt1); line-height: 1.7; font-style: italic; }

/* ── RISK TAGS ── */
.risk-tags { display: flex; flex-wrap: wrap; gap: .45rem; margin-top: .7rem; }
.risk-tag {
  background: rgba(139,42,42,0.06);
  border: 1px solid rgba(139,42,42,0.2);
  color: #8B2A2A;
  font-size: .71rem;
  font-weight: 500;
  padding: 4px 11px;
  border-radius: 100px;
}

/* ── CHAT ── */
.chat-box {
  background: var(--cream);
  border: 1px solid var(--border);
  border-radius: 14px;
  padding: 1.25rem;
  max-height: 440px;
  overflow-y: auto;
  margin-bottom: 1rem;
  display: flex;
  flex-direction: column;
  gap: 1rem;
}
.chat-user { display: flex; justify-content: flex-end; }
.bubble-user {
  background: var(--navy);
  color: #FFFFFF;
  border-radius: 18px 18px 4px 18px;
  padding: .7rem 1.1rem;
  max-width: 78%;
  font-size: .88rem;
  line-height: 1.6;
  box-shadow: 0 2px 8px rgba(27,50,82,0.25);
}
.chat-ai { display: flex; gap: 10px; align-items: flex-start; }
.ai-label {
  width: 30px; height: 30px;
  background: linear-gradient(135deg, var(--navy), var(--navy-mid));
  color: #FFFFFF;
  border-radius: 50%;
  display: flex; align-items: center; justify-content: center;
  font-size: .58rem; font-weight: 700;
  letter-spacing: .5px;
  flex-shrink: 0;
  box-shadow: 0 2px 6px rgba(27,50,82,0.2);
}
.bubble-ai {
  background: var(--white);
  border: 1px solid var(--border);
  color: var(--txt0);
  border-radius: 18px 18px 18px 4px;
  padding: .7rem 1.1rem;
  max-width: 78%;
  font-size: .88rem;
  line-height: 1.6;
  box-shadow: var(--sd0);
}

/* ── BUTTONS ── */
.stButton > button {
  background: var(--navy) !important;
  color: #FFFFFF !important;
  border: none !important;
  border-radius: 8px !important;
  padding: .7rem 1.6rem !important;
  font-family: 'Times New Roman', Times, Georgia, serif !important;
  font-weight: 700 !important;
  font-size: .88rem !important;
  letter-spacing: .6px !important;
  text-transform: uppercase !important;
  transition: background .2s ease, transform .15s ease, box-shadow .2s ease !important;
  box-shadow: 0 2px 8px rgba(27,50,82,0.22) !important;
  width: 100% !important;
}
.stButton > button:hover {
  background: var(--navy-mid) !important;
  transform: translateY(-1px) !important;
  box-shadow: 0 4px 16px rgba(27,50,82,0.30) !important;
}
.stButton > button:active {
  transform: translateY(0) !important;
}

/* ── INPUTS ── */
.stTextInput > div > div > input {
  background: var(--white) !important;
  border: 1px solid var(--border) !important;
  border-radius: 8px !important;
  color: var(--txt0) !important;
  font-family: 'Times New Roman', Times, Georgia, serif !important;
  font-size: .9rem !important;
  padding: .65rem 1rem !important;
  box-shadow: var(--sd0) !important;
  transition: border-color .2s, box-shadow .2s !important;
}
.stTextInput > div > div > input:focus {
  border-color: var(--navy-mid) !important;
  box-shadow: 0 0 0 3px rgba(27,50,82,0.12) !important;
  outline: none !important;
}

/* ── FILE UPLOADER ── */
[data-testid="stFileUploader"],
[data-testid="stFileUploaderDropzone"] {
  background: #FFFFFF !important;
  border: 2px dashed #CCCCCC !important;
  border-radius: 14px !important;
  transition: border-color .2s !important;
}
[data-testid="stFileUploader"]:hover {
  border-color: #999999 !important;
}
/* all text inside the upload box */
[data-testid="stFileUploaderDropzoneInstructions"],
[data-testid="stFileUploaderDropzoneInstructions"] *,
[data-testid="stFileUploaderDropzone"] p,
[data-testid="stFileUploaderDropzone"] span,
[data-testid="stFileUploaderDropzone"] small,
[data-testid="stFileUploaderDropzone"] div {
  color: #111111 !important;
  font-family: 'Times New Roman', Times, Georgia, serif !important;
}
[data-testid="stFileUploader"] svg {
  fill: #555555 !important;
}
/* browse files button */
[data-testid="stFileUploaderDropzoneButton"],
[data-testid="stFileUploaderDropzoneButton"] button {
  background: #FFFFFF !important;
  background-color: #FFFFFF !important;
  background-image: none !important;
  color: #111111 !important;
  border: 1.5px solid #AAAAAA !important;
  border-radius: 8px !important;
  padding: .45rem 1.1rem !important;
  font-family: 'Times New Roman', Times, Georgia, serif !important;
  font-size: .85rem !important;
  font-weight: 600 !important;
  cursor: pointer !important;
  white-space: nowrap !important;
  overflow: hidden !important;
  box-shadow: none !important;
}
[data-testid="stFileUploaderDropzoneButton"]:hover,
[data-testid="stFileUploaderDropzoneButton"] button:hover {
  background: #F0F0F0 !important;
  background-color: #F0F0F0 !important;
}

/* ── SIDEBAR ── */
[data-testid="stSidebar"] {
  background: var(--white) !important;
  border-right: 1px solid var(--border) !important;
  box-shadow: 2px 0 12px rgba(27,50,82,0.05) !important;
}
[data-testid="stSidebar"] > div { padding-top: 0 !important; }

.sb-logo {
  padding: 2rem 1.25rem 1.25rem;
  border-bottom: 1px solid var(--border);
  margin-bottom: 1rem;
}
.sb-section {
  background: var(--cream);
  border: 1px solid var(--border);
  border-radius: 12px;
  padding: 1rem 1.1rem;
  margin: 0 .75rem .85rem;
  transition: box-shadow .2s;
}
.sb-section:hover { box-shadow: var(--sd0); }
.sb-title {
  font-size: .65rem;
  text-transform: uppercase;
  letter-spacing: 2px;
  color: var(--txt3);
  margin-bottom: .65rem;
  font-weight: 400;
  padding-bottom: .4rem;
  border-bottom: 1px solid var(--border);
}
.hist-item {
  display: flex;
  gap: 10px;
  align-items: flex-start;
  padding: .55rem 0;
  border-bottom: 1px solid var(--border);
}
.hist-item:last-child { border-bottom: none; }
.hist-dot {
  width: 8px; height: 8px;
  border-radius: 50%;
  background: var(--navy);
  margin-top: 5px;
  flex-shrink: 0;
}
.hist-cond { font-size: .8rem; font-weight: 700; color: var(--txt0); line-height: 1.3; }
.hist-time { font-size: .67rem; color: var(--txt3); margin-top: 2px; font-style: italic; }

.status-dot {
  display: inline-block;
  width: 7px; height: 7px;
  border-radius: 50%;
  background: #2E7D53;
  margin-right: 7px;
  vertical-align: middle;
  box-shadow: 0 0 0 2px rgba(46,125,83,0.2);
}

/* ── TIP CARD ── */
.tip-card {
  background: var(--white);
  border: 1px solid var(--border);
  border-radius: 10px;
  padding: .85rem 1rem;
  margin-bottom: .6rem;
  transition: box-shadow .2s;
}
.tip-card:hover { box-shadow: var(--sd0); }
.tip-rule {
  width: 24px; height: 2px;
  background: var(--gold);
  border-radius: 100px;
  margin-bottom: .45rem;
}
.tip-ttl { font-size: .82rem; font-weight: 700; color: var(--navy); margin-bottom: .25rem; }
.tip-txt  { font-size: .78rem; color: var(--txt1); line-height: 1.6; font-style: italic; }

/* ── EMPTY STATE ── */
.empty-state {
  text-align: center;
  padding: 3rem 2rem;
  background: var(--white);
  border: 1px solid var(--border);
  border-radius: 14px;
  box-shadow: var(--sd0);
}
.empty-monogram {
  font-size: 2.8rem;
  font-weight: 700;
  color: var(--border2);
  letter-spacing: -2px;
  margin-bottom: .75rem;
  font-style: italic;
}

/* ── FEATURE CARDS ── */
.feat-card {
  background: var(--white);
  border: 1px solid var(--border);
  border-radius: 14px;
  padding: 1.75rem 1.25rem 1.5rem;
  text-align: center;
  box-shadow: var(--sd0);
  transition: box-shadow .25s ease, transform .25s ease;
  height: 100%;
}
.feat-card:hover {
  box-shadow: var(--sd2);
  transform: translateY(-3px);
}
.feat-num {
  font-size: 2rem;
  font-weight: 700;
  color: var(--navy);
  opacity: .12;
  margin-bottom: .65rem;
  font-style: italic;
  line-height: 1;
}
.feat-rule {
  width: 28px; height: 2px;
  background: linear-gradient(90deg, var(--navy), var(--gold));
  border-radius: 100px;
  margin: 0 auto .7rem;
}
.feat-title { font-size: .96rem; font-weight: 700; color: var(--txt0); margin-bottom: .5rem; }
.feat-desc  { font-size: .79rem; color: var(--txt2); line-height: 1.65; font-style: italic; }

/* ── TABS ── */
.stTabs [data-baseweb="tab-list"] {
  background: var(--white) !important;
  border-bottom: 1px solid var(--border) !important;
  padding: 0 .25rem !important;
  border-radius: 0 !important;
}
.stTabs [data-baseweb="tab"] {
  background: transparent !important;
  border: none !important;
  color: var(--txt2) !important;
  font-family: 'Times New Roman', Times, Georgia, serif !important;
  font-size: .88rem !important;
  font-weight: 400 !important;
  padding: .7rem 1.5rem !important;
  border-radius: 0 !important;
  letter-spacing: .3px !important;
  transition: color .2s !important;
}
.stTabs [aria-selected="true"] {
  color: var(--navy) !important;
  font-weight: 700 !important;
  border-bottom: 2px solid var(--navy) !important;
}

/* ── INFO CHIPS ── */
.info-chip {
  font-size: .71rem;
  color: var(--txt2);
  background: var(--white);
  padding: 4px 10px;
  border: 1px solid var(--border);
  border-radius: 100px;
  display: inline-block;
  margin-right: 5px;
  margin-top: 5px;
  font-style: italic;
}

/* ── LIST ROWS ── */
.list-row {
  font-size: .84rem;
  color: var(--txt1);
  padding: .55rem 0;
  border-bottom: 1px solid var(--border);
  line-height: 1.65;
  display: flex;
  gap: 8px;
  align-items: flex-start;
}
.list-row:last-child { border-bottom: none; }
.list-dot {
  width: 5px; height: 5px;
  border-radius: 50%;
  background: var(--border2);
  flex-shrink: 0;
  margin-top: 7px;
}

/* ── FOOTER ── */
.app-footer {
  text-align: center;
  padding: 2rem 1rem;
  color: var(--txt3);
  font-size: .74rem;
  border-top: 1px solid var(--border);
  margin-top: 4rem;
  line-height: 2;
  font-style: italic;
}
.footer-rule {
  width: 40px; height: 1px;
  background: var(--border2);
  margin: .75rem auto;
  border-radius: 100px;
}

/* ── FADE ── */
.fade { animation: fadeUp .45s cubic-bezier(0.4,0,0.2,1); }
@keyframes fadeUp {
  from { opacity: 0; transform: translateY(14px); }
  to   { opacity: 1; transform: translateY(0); }
}

/* ── STREAMLIT OVERRIDES ── */
[data-testid="stImage"] img {
  border-radius: 10px !important;
  box-shadow: var(--sd1) !important;
}
.stAlert, .stInfo, .stSuccess, .stWarning, .stError {
  border-radius: 10px !important;
}
.stSpinner > div { border-color: var(--navy) transparent transparent !important; }

</style>
""", unsafe_allow_html=True)

# ──────────────────────────────────────────────
# SIDEBAR
# ──────────────────────────────────────────────
with st.sidebar:
    st.markdown("""
    <div class="sb-logo">
      <div style="font-size:.65rem;letter-spacing:3px;text-transform:uppercase;
                  color:#B8882A;margin-bottom:.5rem;">Advanced Skin Analysis</div>
      <div style="font-size:1.45rem;font-weight:700;color:#1B3252;letter-spacing:-.3px;">Dermatica Pro</div>
    </div>
    """, unsafe_allow_html=True)

    st.markdown("""
    <div class="sb-section">
      <div class="sb-title">System Status</div>
      <div style="font-size:.81rem;color:#4A4845;line-height:2.3;">
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
        <div style="text-align:center;padding:.85rem .5rem;background:#FFFFFF;
                    border:1px solid #E4E0D8;border-radius:10px;">
          <div style="font-size:1.7rem;font-weight:700;color:#1B3252;line-height:1;">{n_scans}</div>
          <div style="font-size:.6rem;color:#B8B5B0;text-transform:uppercase;
                      letter-spacing:1.5px;margin-top:.25rem;">Scans</div>
        </div>
        <div style="text-align:center;padding:.85rem .5rem;background:#FFFFFF;
                    border:1px solid #E4E0D8;border-radius:10px;">
          <div style="font-size:1.7rem;font-weight:700;color:#1B3252;line-height:1;">{n_chats}</div>
          <div style="font-size:.6rem;color:#B8B5B0;text-transform:uppercase;
                      letter-spacing:1.5px;margin-top:.25rem;">Q&amp;A</div>
        </div>
      </div>
    </div>
    """, unsafe_allow_html=True)

    if st.session_state.analysis_history:
        hist_html = '<div class="sb-section"><div class="sb-title">Recent Analyses</div>'
        for h in reversed(st.session_state.analysis_history[-5:]):
            lvl   = h.get("severity_level", "MODERATE")
            style = SEVERITY_STYLES.get(lvl, SEVERITY_STYLES["MODERATE"])
            conds = h.get("conditions", [])
            top   = conds[0]["name"] if conds else "Unknown"
            ts    = h.get("timestamp", "")
            hist_html += f"""
            <div class="hist-item">
              <div class="hist-dot" style="background:{style['color']};
                   box-shadow:0 0 0 3px {style['bg']};"></div>
              <div style="flex:1;min-width:0;">
                <div class="hist-cond">{top}</div>
                <div style="display:flex;align-items:center;gap:6px;margin-top:3px;">
                  <span style="font-size:.62rem;padding:2px 8px;border-radius:100px;
                               background:{style['bg']};color:{style['color']};
                               border:1px solid {style['border']};font-weight:700;
                               letter-spacing:.5px;">{lvl}</span>
                  <span class="hist-time">{ts}</span>
                </div>
              </div>
            </div>"""
        hist_html += "</div>"
        st.markdown(hist_html, unsafe_allow_html=True)

    st.markdown("""
    <div class="sb-section">
      <div class="sb-title">Skin Health Guidelines</div>
      <div class="tip-card">
        <div class="tip-rule"></div>
        <div class="tip-ttl">Sun Protection</div>
        <div class="tip-txt">Apply SPF 30+ sunscreen daily. UV exposure is the leading cause of premature skin damage and elevated carcinoma risk.</div>
      </div>
      <div class="tip-card">
        <div class="tip-rule"></div>
        <div class="tip-ttl">Hydration</div>
        <div class="tip-txt">Maintain adequate water intake and moisturise twice daily to preserve the skin's protective barrier function.</div>
      </div>
      <div class="tip-card">
        <div class="tip-rule"></div>
        <div class="tip-ttl">Gentle Cleansing</div>
        <div class="tip-txt">Use fragrance-free, pH-balanced cleansers. Excessive washing disrupts the skin's natural protective lipid layer.</div>
      </div>
    </div>
    """, unsafe_allow_html=True)

# ──────────────────────────────────────────────
# HERO
# ──────────────────────────────────────────────
st.markdown("""
<div class="hero">
  <div class="hero-eyebrow">AI-Powered Dermatology Assistant</div>
  <h1 class="hero-title">Dermatica Pro</h1>
  <p class="hero-sub">Advanced skin condition analysis powered by multimodal AI. Upload a photograph for structured clinical insights in seconds.</p>
  <div class="status-bar">
    <div class="s-pill"><span class="s-dot"></span>Real-time Analysis</div>
    <div class="s-pill"><span class="s-dot"></span>Llama Vision Model</div>
    <div class="s-pill"><span class="s-dot"></span>Secure &amp; Private</div>
    <div class="s-pill"><span class="s-dot"></span>Medical-Grade Prompting</div>
  </div>
</div>
""", unsafe_allow_html=True)

# ──────────────────────────────────────────────
# DISCLAIMER
# ──────────────────────────────────────────────
st.markdown("""
<div class="disclaimer">
  <strong style="color:#1B3252;">Medical Disclaimer &mdash;</strong>
  Dermatica Pro provides AI-generated insights for <em>educational and informational purposes only</em>.
  This tool does not constitute a medical diagnosis or replace professional medical advice.
  Always consult a licensed dermatologist or qualified healthcare professional for accurate
  diagnosis and appropriate treatment.
</div>
""", unsafe_allow_html=True)

# ──────────────────────────────────────────────
# MAIN
# ──────────────────────────────────────────────
if st.session_state.current_analysis is None:

    _, mid, _ = st.columns([1, 2, 1])
    with mid:
        st.markdown("""
        <div class="g-card">
          <div class="g-card-header">
            <div class="g-accent"></div>
            <div>
              <div class="g-title">Upload Skin Image</div>
              <div class="g-sub">High-resolution, well-lit photographs produce the most accurate analysis.</div>
            </div>
          </div>
        </div>
        """, unsafe_allow_html=True)

        uploaded_file = st.file_uploader(
            "Select an image file",
            type=["jpg", "jpeg", "png", "webp"],
            label_visibility="collapsed",
        )

        components.html("""
<script>
(function() {
  function fix() {
    try {
      var doc = window.parent.document;
      var btn = doc.querySelector('[data-testid="stFileUploaderDropzoneButton"]');
      if (!btn) return;
      var leaves = [];
      btn.querySelectorAll('*').forEach(function(el) {
        if (el.children.length === 0 && el.textContent.trim()) {
          leaves.push(el);
        }
      });
      if (leaves.length > 1) {
        for (var i = 0; i < leaves.length - 1; i++) {
          leaves[i].style.setProperty('display', 'none', 'important');
          leaves[i].style.setProperty('visibility', 'hidden', 'important');
          leaves[i].style.setProperty('font-size', '0', 'important');
          leaves[i].style.setProperty('width', '0', 'important');
          leaves[i].style.setProperty('height', '0', 'important');
          leaves[i].style.setProperty('position', 'absolute', 'important');
        }
      }
    } catch(e) {}
  }
  fix();
  [200, 500, 1000, 2000].forEach(function(t){ setTimeout(fix, t); });
  try {
    new MutationObserver(fix).observe(
      window.parent.document.body,
      { childList: true, subtree: true }
    );
  } catch(e) {}
})();
</script>
""", height=0, scrolling=False)

        if uploaded_file:
            img = Image.open(uploaded_file)
            if img.mode != "RGB":
                img = img.convert("RGB")
            w, h  = img.size
            fsize = uploaded_file.size / 1024

            st.image(img, use_container_width=True)
            st.markdown(
                f'<div style="margin:.65rem 0;">'
                f'<span class="info-chip">{w} &times; {h} px</span>'
                f'<span class="info-chip">{fsize:.1f} KB</span>'
                f'<span class="info-chip">{img.mode}</span>'
                f'</div>',
                unsafe_allow_html=True,
            )

            if st.button("Analyze Skin Condition", use_container_width=True):
                with st.spinner("Analyzing image — please wait..."):
                    try:
                        result = analyze_image(img)
                        result["timestamp"] = datetime.datetime.now().strftime("%H:%M")
                        result["filename"]  = uploaded_file.name
                        st.session_state.current_analysis = result
                        st.session_state.current_image    = img
                        st.session_state.analysis_history.append(result)
                        st.session_state.chat_messages    = []
                        st.rerun()
                    except Exception as exc:
                        st.error(f"Analysis failed: {exc}")
        else:
            st.markdown("""
            <div class="empty-state">
              <div class="empty-monogram">Rx</div>
              <div style="font-size:.92rem;font-weight:700;color:#4A4845;margin-bottom:.35rem;">
                No Image Selected
              </div>
              <div style="font-size:.81rem;color:#8A8785;font-style:italic;line-height:1.65;">
                Accepted formats: JPG, PNG, WebP<br>
                For best results, use a clear close-up in natural lighting.
              </div>
            </div>
            """, unsafe_allow_html=True)

    st.markdown('<div class="sec-lbl" style="margin-top:3.5rem;">How It Works</div>', unsafe_allow_html=True)
    f_cols = st.columns(4)
    feats  = [
        ("I",   "Upload",           "Submit a clear photograph of the affected skin area for evaluation."),
        ("II",  "AI Analysis",      "Multimodal AI examines visual patterns, texture, colour, and distribution."),
        ("III", "Review Results",   "Receive a structured report with severity, ranked conditions, and risk factors."),
        ("IV",  "Consult Further",  "Ask follow-up questions to receive additional clinical context from the AI."),
    ]
    for col, (num, title, desc) in zip(f_cols, feats):
        with col:
            st.markdown(f"""
            <div class="feat-card">
              <div class="feat-num">{num}</div>
              <div class="feat-rule"></div>
              <div class="feat-title">{title}</div>
              <div class="feat-desc">{desc}</div>
            </div>
            """, unsafe_allow_html=True)

else:
    analysis = st.session_state.current_analysis
    img      = st.session_state.current_image

    tab_res, tab_chat, tab_dl = st.tabs(
        ["Analysis Results", "Follow-up Questions", "Download Report"]
    )

    # ── TAB 1 ────────────────────────────────
    with tab_res:
        col_l, col_r = st.columns([1, 1.55])

        with col_l:
            st.markdown('<div class="sec-lbl">Analyzed Image</div>', unsafe_allow_html=True)
            st.image(img, use_container_width=True)

            sev_lvl   = analysis.get("severity_level", "MODERATE")
            sev_score = analysis.get("severity_score", 5.0)
            sev_style = SEVERITY_STYLES.get(sev_lvl, SEVERITY_STYLES["MODERATE"])
            sev_pct   = min(100, max(5, int(sev_score * 10)))

            st.markdown(f"""
            <div class="g-card fade" style="margin-top:.85rem;">
              <div class="g-card-header">
                <div class="g-accent" style="background:{sev_style['color']};"></div>
                <div>
                  <div class="g-title">Severity Assessment</div>
                  <div class="g-sub">Score: {sev_score:.1f} / 10</div>
                </div>
              </div>
              <div class="sev-wrap">
                <div class="sev-fill" style="width:{sev_pct}%;background:{sev_style['color']};"></div>
              </div>
              <div class="sev-labels">
                <span class="sev-label">Minimal</span>
                <span class="sev-label">Moderate</span>
                <span class="sev-label">Critical</span>
              </div>
              <div style="text-align:center;margin-top:1rem;">
                <span style="font-size:.78rem;font-weight:700;padding:5px 16px;
                             border-radius:100px;letter-spacing:1px;
                             background:{sev_style['bg']};color:{sev_style['color']};
                             border:1px solid {sev_style['border']};">
                  {sev_lvl} SEVERITY
                </span>
              </div>
            </div>
            """, unsafe_allow_html=True)

            rec    = analysis.get("recommended_action", "SEE_DOCTOR")
            acfg   = ACTION_CONFIGS.get(rec, ACTION_CONFIGS["SEE_DOCTOR"])
            detail = analysis.get("action_detail", "Please consult a medical professional.")
            st.markdown(f"""
            <div class="act-card fade"
                 style="background:{acfg['bg']};border-color:{acfg['border']};
                        border-left:4px solid {acfg['color']};">
              <div class="act-title" style="color:{acfg['color']};">{acfg['title']}</div>
              <div class="act-desc">{detail}</div>
            </div>
            """, unsafe_allow_html=True)

        with col_r:
            vd = analysis.get("visual_description", "")
            if vd:
                st.markdown('<div class="sec-lbl">Clinical Observations</div>', unsafe_allow_html=True)
                st.markdown(f"""
                <div class="g-card fade">
                  <div class="g-card-header">
                    <div class="g-accent"></div>
                    <div class="g-title">What the AI Observed</div>
                  </div>
                  <div style="font-size:.89rem;line-height:1.82;color:#4A4845;
                              font-style:italic;">{vd}</div>
                </div>
                """, unsafe_allow_html=True)

            conds = analysis.get("conditions", [])
            if conds:
                st.markdown('<div class="sec-lbl">Differential Analysis</div>', unsafe_allow_html=True)
                cond_html = """
                <div class="g-card fade">
                  <div class="g-card-header">
                    <div class="g-accent"></div>
                    <div>
                      <div class="g-title">Possible Conditions</div>
                      <div class="g-sub">Ranked by clinical likelihood</div>
                    </div>
                  </div>"""
                for c in conds:
                    lvl  = c.get("level", "MEDIUM")
                    ps   = PROB_STYLES.get(lvl, PROB_STYLES["MEDIUM"])
                    name = c.get("name", "Unknown")
                    desc = c.get("description", "")
                    cond_html += f"""
                  <div class="cond-card">
                    <div style="display:flex;justify-content:space-between;
                                align-items:center;margin-bottom:.5rem;">
                      <div class="cond-name">{name}</div>
                      <span class="prob-badge"
                            style="background:{ps['badge_bg']};color:{ps['badge_color']};
                                   border-color:{ps['badge_border']};">{lvl}</span>
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
                cond_html += "</div>"
                st.markdown(cond_html, unsafe_allow_html=True)

            rfs = analysis.get("risk_factors", [])
            if rfs:
                rf_html = """
                <div class="g-card fade">
                  <div class="g-card-header">
                    <div class="g-accent" style="background:#8B2A2A;"></div>
                    <div class="g-title">Identified Risk Factors</div>
                  </div>
                  <div class="risk-tags">"""
                for r in rfs:
                    rf_html += f'<span class="risk-tag">{r}</span>'
                rf_html += "</div></div>"
                st.markdown(rf_html, unsafe_allow_html=True)

            wtsd = analysis.get("when_to_see_doctor", [])
            sct  = analysis.get("self_care_tips", [])
            if wtsd or sct:
                c1, c2 = st.columns(2)
                if wtsd:
                    with c1:
                        rows = "".join(
                            f'<div class="list-row"><span class="list-dot" '
                            f'style="background:#8B2A2A;"></span>{s}</div>'
                            for s in wtsd
                        )
                        st.markdown(f"""
                        <div class="g-card fade">
                          <div class="g-card-header">
                            <div class="g-accent" style="background:#8B2A2A;"></div>
                            <div class="g-title">When to Seek Medical Care</div>
                          </div>
                          {rows}
                        </div>""", unsafe_allow_html=True)
                if sct:
                    with c2:
                        rows = "".join(
                            f'<div class="list-row"><span class="list-dot" '
                            f'style="background:#2E7D53;"></span>{t}</div>'
                            for t in sct
                        )
                        st.markdown(f"""
                        <div class="g-card fade">
                          <div class="g-card-header">
                            <div class="g-accent" style="background:#2E7D53;"></div>
                            <div class="g-title">Self-Care Recommendations</div>
                          </div>
                          {rows}
                        </div>""", unsafe_allow_html=True)

        st.markdown("<div style='margin-top:2.5rem;'></div>", unsafe_allow_html=True)
        _, mid2, _ = st.columns([2, 1, 2])
        with mid2:
            if st.button("Analyze New Image", use_container_width=True):
                st.session_state.current_analysis = None
                st.session_state.current_image    = None
                st.session_state.chat_messages    = []
                st.rerun()

    # ── TAB 2 ────────────────────────────────
    with tab_chat:
        st.markdown('<div class="sec-lbl">AI Consultation</div>', unsafe_allow_html=True)

        if st.session_state.chat_messages:
            bubbles = ""
            for m in st.session_state.chat_messages:
                if m["role"] == "user":
                    bubbles += (
                        f'<div class="chat-user">'
                        f'<div class="bubble-user">{m["content"]}</div></div>'
                    )
                else:
                    bubbles += (
                        f'<div class="chat-ai">'
                        f'<div class="ai-label">AI</div>'
                        f'<div class="bubble-ai">{m["content"]}</div></div>'
                    )
            st.markdown(f'<div class="chat-box">{bubbles}</div>', unsafe_allow_html=True)
        else:
            st.markdown("""
            <div style="text-align:center;padding:2rem;background:#FFFFFF;
                        border:1px solid #E4E0D8;border-radius:14px;
                        margin-bottom:1rem;box-shadow:0 1px 3px rgba(27,50,82,.06),
                        0 4px 16px rgba(27,50,82,.07);">
              <div style="font-size:.95rem;font-weight:700;color:#4A4845;margin-bottom:.4rem;">
                Ask About Your Results
              </div>
              <div style="font-size:.82rem;color:#8A8785;font-style:italic;">
                Submit a question below to receive additional clinical context from the AI.
              </div>
            </div>
            """, unsafe_allow_html=True)

        st.markdown(
            '<div style="font-size:.68rem;color:#B8B5B0;text-transform:uppercase;'
            'letter-spacing:2px;margin-bottom:.65rem;">Suggested Questions</div>',
            unsafe_allow_html=True
        )
        suggestions = [
            "What treatments are typically available for this condition?",
            "Is this condition contagious?",
            "What activities or substances should I avoid?",
            "What is the typical recovery timeline?",
        ]
        sq_cols = st.columns(2)
        for i, q in enumerate(suggestions):
            with sq_cols[i % 2]:
                if st.button(q, key=f"sq_{i}", use_container_width=True):
                    st.session_state.chat_messages.append({"role": "user", "content": q})
                    with st.spinner("Processing..."):
                        try:
                            ans = ask_followup(q, analysis, img)
                            st.session_state.chat_messages.append({"role": "assistant", "content": ans})
                        except Exception as exc:
                            st.session_state.chat_messages.append({"role": "assistant", "content": f"Error: {exc}"})
                    st.rerun()

        with st.form("qform", clear_on_submit=True):
            user_q   = st.text_input("Question", placeholder="Enter your question here...", label_visibility="collapsed")
            send_btn = st.form_submit_button("Submit Question", use_container_width=True)
            if send_btn and user_q.strip():
                st.session_state.chat_messages.append({"role": "user", "content": user_q.strip()})
                with st.spinner("Processing..."):
                    try:
                        ans = ask_followup(user_q.strip(), analysis, img)
                        st.session_state.chat_messages.append({"role": "assistant", "content": ans})
                    except Exception as exc:
                        st.session_state.chat_messages.append({"role": "assistant", "content": f"Error: {exc}"})
                st.rerun()

    # ── TAB 3 ────────────────────────────────
    with tab_dl:
        st.markdown('<div class="sec-lbl">Export Report</div>', unsafe_allow_html=True)
        fname  = analysis.get("filename", "skin_image")
        report = build_report(analysis, fname)

        st.markdown("""
        <div class="g-card">
          <div class="g-card-header">
            <div class="g-accent"></div>
            <div>
              <div class="g-title">Full Analysis Report</div>
              <div class="g-sub">Complete findings, differential diagnosis, risk factors, and recommendations.</div>
            </div>
          </div>
        </div>
        """, unsafe_allow_html=True)

        st.code(report, language=None)

        _, mid3, _ = st.columns([1, 2, 1])
        with mid3:
            ts = datetime.datetime.now().strftime("%Y%m%d_%H%M")
            st.download_button(
                label="Download Report (.txt)",
                data=report,
                file_name=f"dermai_report_{ts}.txt",
                mime="text/plain",
                use_container_width=True,
            )

# ──────────────────────────────────────────────
# FOOTER
# ──────────────────────────────────────────────
st.markdown("""
<div class="app-footer">
  <div class="footer-rule"></div>
  Dermatica Pro &nbsp;&mdash;&nbsp; Powered by Groq &amp; Llama AI &nbsp;&mdash;&nbsp; For Educational Use Only
  <br>Always consult a licensed dermatologist for professional medical advice.
</div>
""", unsafe_allow_html=True)
