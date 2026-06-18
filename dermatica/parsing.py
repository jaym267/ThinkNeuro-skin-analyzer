# -*- coding: utf-8 -*-
"""Regex-based parser for the structured analysis text returned by the model.

Tightly coupled to the prompt in vision.ANALYSIS_PROMPT_TEMPLATE: if the
prompt's section labels/format change, these regexes must change too, or
fields silently fall back to their defaults instead of raising an error.
"""
import re


def _strip_bullet_lines(block: str) -> list[str]:
    """Split a block of text into lines, strip bullet prefixes (-, *, +) and
    surrounding whitespace, and drop empty lines. Shared by every section
    that's just a plain bulleted list."""
    out = []
    for line in block.split("\n"):
        line = line.strip().lstrip("-*+ ").strip()
        if line:
            out.append(line)
    return out

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
    for line in _strip_bullet_lines(cblock):
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

    out["when_to_see_doctor"] = _strip_bullet_lines(
        grab(r"WHEN_TO_SEE_DOCTOR:\s*\n(.*?)(?=\n[A-Z_]{3,}:|\Z)")
    )

    out["self_care_tips"] = _strip_bullet_lines(
        grab(r"SELF_CARE_TIPS:\s*\n(.*?)(?=\n[A-Z_]{3,}:|\Z)")
    )

    return out
