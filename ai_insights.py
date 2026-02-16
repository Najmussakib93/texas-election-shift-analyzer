import os
import json
import streamlit as st
import pandas as pd
from openai import OpenAI
from dotenv import load_dotenv

load_dotenv()


@st.cache_data(show_spinner=False)
def build_county_summary(d: pd.DataFrame) -> dict:
    d = d.sort_values("year")
    return {
        "years": d["year"].tolist(),
        "per_dem": [round(float(x), 2) for x in d["per_dem"].tolist()],
        "per_gop": [round(float(x), 2) for x in d["per_gop"].tolist()],
        "margin_pts": [round(float(x), 2) for x in d["per_point_diff"].tolist()],
        "total_votes": [int(x) for x in d["total_votes"].tolist()],
    }


def _get_openai_key():
    key = os.getenv("OPENAI_API_KEY")
    if key:
        return key
    try:
        return st.secrets["OPENAI_API_KEY"]
    except Exception:
        return None


def _client():
    api_key = _get_openai_key()
    if not api_key:
        return None
    return OpenAI(api_key=api_key)


def gpt_quick_insight(county: str, summary: dict) -> str:
    client = _client()
    if not client:
        return "⚠️ AI insight disabled. Set OPENAI_API_KEY in your .env (local) or Streamlit secrets (deploy)."

    prompt = f"""
You are helping a newsroom build an election results tool.
Write a concise, factual "Quick insight" for {county}, Texas using ONLY the numbers provided.

Data (2016, 2020, 2024):
- Dem vote %: {summary["per_dem"]}
- GOP vote %: {summary["per_gop"]}
- Margin (percentage points, GOP minus Dem): {summary["margin_pts"]}
- Total votes: {summary["total_votes"]}

Rules:
- 2–4 sentences max, then 2 bullet points titled "What to watch".
- Use plain language for general readers.
- Do not speculate about causes, demographics, or turnout drivers.
- Do not mention the model or missing data.
- Quantify shifts since 2016 when possible.
"""

    resp = client.chat.completions.create(
        model="gpt-4o-mini",
        messages=[
            {"role": "system", "content": "You are a careful data-journalism assistant who never invents facts."},
            {"role": "user", "content": prompt},
        ],
        temperature=0.2,
    )
    return resp.choices[0].message.content.strip()


def gpt_statewide_summary(state_stats: dict) -> str:
    client = _client()
    if not client:
        return "⚠️ AI insight disabled. Set OPENAI_API_KEY in your .env (local) or Streamlit secrets (deploy)."

    prompt = f"""
You are helping a newsroom summarize statewide election trends for Texas.
Use ONLY the totals and percentages provided. Keep it factual and concise.

Statewide stats:
{json.dumps(state_stats, indent=2)}

Rules:
- 4–6 sentences max.
- Then add 3 bullet points titled "Key takeaways".
- Do not speculate about causes or demographics.
- Use plain language for general readers.
"""

    resp = client.chat.completions.create(
        model="gpt-4o-mini",
        messages=[
            {"role": "system", "content": "You are a careful data-journalism assistant who never invents facts."},
            {"role": "user", "content": prompt},
        ],
        temperature=0.2,
    )
    return resp.choices[0].message.content.strip()


@st.cache_data(show_spinner=False)
def cached_gpt_quick_insight_json(county: str, summary_json: str) -> str:
    return gpt_quick_insight(county, json.loads(summary_json))


@st.cache_data(show_spinner=False)
def cached_gpt_statewide_summary_json(stats_json: str) -> str:
    return gpt_statewide_summary(json.loads(stats_json))
