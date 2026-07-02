# -*- coding: utf-8 -*-
"""Vision model calls: structured analysis, streamed follow-up chat, and the
simple CLI analysis path."""
import base64

import streamlit as st
from PIL import Image

from . import config
from .groq_client import get_client
from .image_utils import image_to_base64
from .parsing import parse_analysis

ANALYSIS_PROMPT_TEMPLATE = (
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

CLI_PROMPT = """You are a medical image analysis assistant
                        specializing in dermatology and parasitology.
                        Analyze the uploaded skin image and provide:

                        1. DESCRIPTION: What you visually observe on the skin
                        2. POSSIBLE CONDITIONS: Potential skin or parasitic
                           infections matching the symptoms, with likelihood
                           (high / medium / low)
                        3. RISK FACTORS: Severity indicators and warning signs
                        4. RECOMMENDED ACTION: Whether the person should seek
                           urgent care, routine care, or monitor at home

                        End every response with:
                        ⚠️ This is NOT a medical diagnosis. Please consult a
                        licensed dermatologist or healthcare professional."""


def _build_symptom_context_block(symptom_context: dict) -> str:
    """Renders the optional patient-reported symptom dict as a clearly
    separated prepend block, kept distinct from ANALYSIS_PROMPT_TEMPLATE so
    that template remains the single source of truth for output format."""
    itch = symptom_context.get("itch_severity", "Not reported")
    duration = symptom_context.get("duration", "Not reported")
    spreading = symptom_context.get("spreading", "Not reported")
    prior_treatment = symptom_context.get("prior_treatment") or "None reported"
    return (
        "PATIENT-REPORTED CONTEXT:\n"
        f"- Itch severity: {itch}/10\n"
        f"- Duration: {duration}\n"
        f"- Spreading pattern: {spreading}\n"
        f"- Prior treatment: {prior_treatment}\n\n"
    )

def analyze_image(img: Image.Image, symptom_context: dict | None = None) -> dict:
    client = get_client()
    b64 = image_to_base64(img)
    if symptom_context:
        prompt = _build_symptom_context_block(symptom_context) + ANALYSIS_PROMPT_TEMPLATE
    else:
        prompt = ANALYSIS_PROMPT_TEMPLATE
    resp = client.chat.completions.create(
        model=config.MODEL_NAME,
        messages=[{"role": "user", "content": [
            {"type": "text", "text": prompt},
            {"type": "image_url", "image_url": {"url": f"data:image/jpeg;base64,{b64}"}},
        ]}],
        max_tokens=config.ANALYZE_MAX_TOKENS,
        temperature=0.2,
    )
    # content can be None if the model returns an empty message; parse_analysis
    # runs regexes over it, so coerce to a string to avoid a TypeError.
    content = resp.choices[0].message.content or ""
    return parse_analysis(content)

def ask_followup_stream(analysis: dict, img: Image.Image):
    """Yield the assistant reply in chunks so it can be typed out live.

    Reads st.session_state.chat_messages, whose final entry is the pending
    user question; the image is attached to that last turn for vision context.
    """
    client = get_client()
    b64 = st.session_state.get("current_image_b64") or image_to_base64(img)
    system = (
        "You are a helpful dermatology AI assistant. "
        f"Previous analysis:\n{analysis.get('raw','')[:1200]}\n\n"
        "Answer concisely. Always advise consulting a licensed dermatologist."
    )
    msgs = [{"role": "system", "content": system}]
    history = st.session_state.chat_messages
    last = len(history) - 1
    for i, m in enumerate(history):
        if m["role"] == "user" and i == last:
            msgs.append({"role": "user", "content": [
                {"type": "text", "text": m["content"]},
                {"type": "image_url", "image_url": {"url": f"data:image/jpeg;base64,{b64}"}},
            ]})
        else:
            msgs.append({"role": m["role"], "content": m["content"]})
    stream = client.chat.completions.create(
        model=config.MODEL_NAME,
        messages=msgs,
        max_tokens=config.FOLLOWUP_MAX_TOKENS,
        temperature=0.4,
        stream=True,
    )
    for chunk in stream:
        # The final streamed chunk (and some usage/keepalive chunks) can carry
        # an empty `choices` list; guard against IndexError so a normal reply
        # isn't cut short by an exception on the terminal chunk.
        if not chunk.choices:
            continue
        delta = chunk.choices[0].delta.content
        if delta:
            yield delta

def analyze_image_cli(image_path: str) -> str:
    """Simple, unstructured CLI analysis path (distinct from analyze_image()):
    base64-encodes the image from a filesystem path, sends the simpler CLI
    prompt, and returns the raw response text."""
    client = get_client()
    extension = image_path.split(".")[-1].lower()
    media_types = {
        "jpg": "image/jpeg",
        "jpeg": "image/jpeg",
        "png": "image/png",
        "webp": "image/webp",
    }
    media_type = media_types.get(extension, "image/jpeg")

    with open(image_path, "rb") as f:
        image_data = base64.b64encode(f.read()).decode("utf-8")

    response = client.chat.completions.create(
        model=config.MODEL_NAME,
        messages=[
            {
                "role": "user",
                "content": [
                    {
                        "type": "image_url",
                        "image_url": {"url": f"data:{media_type};base64,{image_data}"},
                    },
                    {"type": "text", "text": CLI_PROMPT},
                ],
            }
        ],
        max_tokens=config.CLI_MAX_TOKENS,
    )

    return response.choices[0].message.content
