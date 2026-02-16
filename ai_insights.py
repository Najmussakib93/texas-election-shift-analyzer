import json
import os
import streamlit as st
from openai import OpenAI
from typing import Optional


@st.cache_data(show_spinner=False)
def build_county_summary(d) -> dict:
    """
    Create a compact, model-friendly summary across years for one county.
    Expects columns: year, per_dem, per_gop, per_point_diff, total_votes
    """
    d = d.sort_values("year")
    return {
        "years": d["year"].tolist(),
        "per_dem": [round(float(x), 2) for x in d["per_dem"].tolist()],
        "per_gop": [round(float(x), 2) for x in d["per_gop"].tolist()],
        "margin_pts": [round(float(x), 2) for x in d["per_point_diff"].tolist()],
        "total_votes": [int(x) for x in d["total_votes"].tolist()],
    }


def _get_client() -> Optional[OpenAI]:
    api_key = os.getenv("OPENAI_API_KEY") or st.secrets.get("OPENAI_API_KEY", None)
    if not api_key:
        return None
    return OpenAI(api_key=api_key)


def _safe_json_load(s: str) -> dict:
    return json.loads(s)


@st.cache_data(show_spinner=False, ttl=60 * 60)
def cached_gpt_quick_insight_json(county_name: str, summary_json: str) -> str:
    """
    Cached for 1 hour. summary_json is a stable string key.
    """
    client = _get_client()
    if client is None:
        return "⚠️ Add `OPENAI_API_KEY` to Streamlit Secrets to enable AI insights."

    summary = _safe_json_load(summary_json)

    prompt = f"""
You are helping a newsroom build an elections tool.

Write a concise, factual “Quick insight” for {county_name} using ONLY the numbers provided.

Data (2016, 2020, 2024):
- Dem vote %: {summary["per_dem"]}
- GOP vote %: {summary["per_gop"]}
- Margin (percentage points, GOP minus Dem): {summary["margin_pts"]}
- Total votes: {summary["total_votes"]}

Rules:
- 2–4 sentences max, then 2 bullet points titled "What to watch".
- Plain language for general readers.
- Do not speculate about causes, demographics, or turnout drivers.
- If describing a shift, quantify it.
"""

    resp = client.chat.completions.create(
        model="gpt-4o-mini",
        messages=[
            {"role": "system", "content": "You are a careful data-journalism assistant who never invents facts."},
            {"role": "user", "content": prompt.strip()},
        ],
        temperature=0.2,
    )
    return resp.choices[0].message.content.strip()


@st.cache_data(show_spinner=False, ttl=60 * 60)
def cached_gpt_statewide_summary_json(statewide_stats_json: str) -> str:
    client = _get_client()
    if client is None:
        return "⚠️ Add `OPENAI_API_KEY` to Streamlit Secrets to enable AI insights."

    stats = _safe_json_load(statewide_stats_json)

    prompt = f"""
You are helping a newsroom build an elections tool.

Write a short statewide summary for Texas using ONLY these totals:
{json.dumps(stats, indent=2)}

Rules:
- 3–6 sentences max, then 2 bullet points titled "What to watch".
- Do not speculate about causes.
- If describing change across years, quantify it.
"""

    resp = client.chat.completions.create(
        model="gpt-4o-mini",
        messages=[
            {"role": "system", "content": "You are a careful data-journalism assistant who never invents facts."},
            {"role": "user", "content": prompt.strip()},
        ],
        temperature=0.2,
    )
    return resp.choices[0].message.content.strip()
