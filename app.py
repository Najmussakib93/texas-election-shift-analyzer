# app.py
import json
import os
from typing import Dict, Any, Tuple

import pandas as pd
import streamlit as st
import plotly.graph_objects as go
import pydeck as pdk

from ai_insights import (
    build_county_summary,
    cached_gpt_quick_insight_json,
    cached_gpt_statewide_summary_json,
)

DATA_2016 = "data/2016.csv"
DATA_2020 = "data/2020.csv"
DATA_2024 = "data/2024.csv"
TX_GEOJSON_PATH = "data/texas_counties.geojson"


# ----------------------------
# UI polish
# ----------------------------
def inject_css():
    st.markdown(
        """
<style>
.block-container { padding-top: 0.8rem; padding-bottom: 1.2rem; }
div[data-testid="stVerticalBlock"] { gap: 0.75rem; }

/* Dark hero header */
.tt-card{
  background: linear-gradient(180deg, #0f172a 0%, #020617 100%);
  border: 1px solid rgba(255,255,255,0.08);
  border-radius: 14px;
  padding: 18px 20px;
  margin-bottom: 6px;
}
.tt-card::before{
  content: "";
  display: block;
  height: 3px;
  background: linear-gradient(90deg, #2A71AE, #B82D35);
  border-radius: 10px;
  margin-bottom: 10px;
}
.tt-title{
  font-size: 1.6rem;
  font-weight: 800;
  color: white;
  margin: 0;
}
.tt-sub{
  color: rgba(255,255,255,0.65);
  margin-top: 4px;
  font-size: 0.95rem;
}

.tt-dark{
  background:#0f1115;
  border:1px solid rgba(255,255,255,0.08);
  border-radius:14px;
  padding:14px 14px 6px 14px;
}
.tt-dark h3, .tt-dark p, .tt-dark li { color: #fff; }

/* Make the Streamlit header area match dark UI */
header[data-testid="stHeader"] { background: rgba(2,6,23,0.0); }
section[data-testid="stSidebar"] { background: #0b1220; }
</style>
""",
        unsafe_allow_html=True,
    )


def _dark_panel_open():
    st.markdown("<div class='tt-dark'>", unsafe_allow_html=True)


def _dark_panel_close():
    st.markdown("</div>", unsafe_allow_html=True)


# ----------------------------
# Data loading + standardization
# ----------------------------
@st.cache_data(show_spinner=False)
def load_and_standardize_tx() -> pd.DataFrame:
    # 2016
    df16 = pd.read_csv(DATA_2016)
    df16 = df16[df16["state_abbr"] == "TX"].copy()
    df16["county_fips"] = df16["combined_fips"].apply(lambda x: f"{int(x):05d}")
    df16["state_name"] = "Texas"
    df16["year"] = 2016
    df16 = df16[
        [
            "state_name",
            "county_fips",
            "county_name",
            "votes_dem",
            "votes_gop",
            "total_votes",
            "per_dem",
            "per_gop",
            "per_point_diff",
            "year",
        ]
    ]

    # 2020
    df20 = pd.read_csv(DATA_2020)
    df20 = df20[df20["state_name"] == "Texas"].copy()
    df20["county_fips"] = df20["county_fips"].apply(lambda x: f"{int(x):05d}")
    df20["year"] = 2020
    df20 = df20[
        [
            "state_name",
            "county_fips",
            "county_name",
            "votes_dem",
            "votes_gop",
            "total_votes",
            "per_dem",
            "per_gop",
            "per_point_diff",
            "year",
        ]
    ]

    # 2024
    df24 = pd.read_csv(DATA_2024)
    df24 = df24[df24["state_name"] == "Texas"].copy()
    df24["county_fips"] = df24["county_fips"].apply(lambda x: f"{int(x):05d}")
    df24["year"] = 2024
    df24 = df24[
        [
            "state_name",
            "county_fips",
            "county_name",
            "votes_dem",
            "votes_gop",
            "total_votes",
            "per_dem",
            "per_gop",
            "per_point_diff",
            "year",
        ]
    ]

    df = pd.concat([df16, df20, df24], ignore_index=True)

    for c in ["votes_dem", "votes_gop", "total_votes", "per_dem", "per_gop", "per_point_diff"]:
        df[c] = pd.to_numeric(df[c], errors="coerce")

    df["county_fips"] = df["county_fips"].astype(str).str.zfill(5)
    return df


@st.cache_data(show_spinner=False)
def load_tx_geojson(path: str) -> Dict[str, Any]:
    """
    Ensures:
      - feature["id"] as 5-digit string FIPS
      - feature["properties"]["geoid"] as 5-digit string FIPS
    """
    with open(path, "r", encoding="utf-8") as f:
        geo = json.load(f)

    for feat in geo.get("features", []):
        if "properties" not in feat or feat["properties"] is None:
            feat["properties"] = {}

        geoid = feat["properties"].get("geoid")
        if not geoid:
            geoid = feat.get("id")

        if geoid is not None:
            geoid = str(geoid).zfill(5)

        feat["id"] = geoid
        feat["properties"]["geoid"] = geoid

    return geo


@st.cache_data(show_spinner=False)
def year_slice_and_lookup(df: pd.DataFrame, year: int) -> Tuple[pd.DataFrame, Dict[str, Dict[str, Any]]]:
    d = df[df["year"] == year].copy()
    d["county_fips"] = d["county_fips"].astype(str).str.zfill(5)

    lookup = (
        d.set_index("county_fips")[
            ["per_dem", "per_gop", "per_point_diff", "total_votes", "county_name", "votes_dem", "votes_gop"]
        ]
        .to_dict("index")
    )
    return d, lookup


# ----------------------------
# Statewide summary stats for AI
# ----------------------------
def make_statewide_stats(df: pd.DataFrame) -> Dict[str, Any]:
    out: Dict[str, Any] = {}
    for y in [2016, 2020, 2024]:
        d = df[df["year"] == y]
        dem = float(d["votes_dem"].sum())
        gop = float(d["votes_gop"].sum())
        total = float(d["total_votes"].sum())
        other = max(0.0, total - dem - gop)
        out[str(y)] = {
            "votes_dem": int(dem),
            "votes_gop": int(gop),
            "votes_other": int(other),
            "total_votes": int(total),
            "per_dem": round((dem / total) * 100.0, 2) if total else None,
            "per_gop": round((gop / total) * 100.0, 2) if total else None,
            "per_other": round((other / total) * 100.0, 2) if total else None,
        }
    return out


# ----------------------------
# Tribune-style stacked bars
# ----------------------------
def render_vote_share_bar(dem_votes: float, gop_votes: float, total_votes: float, title_html: str):
    other_votes = max(0.0, total_votes - dem_votes - gop_votes)
    if not total_votes or total_votes <= 0:
        st.warning("No vote totals available.")
        return

    dem_pct = 100.0 * dem_votes / total_votes
    gop_pct = 100.0 * gop_votes / total_votes
    oth_pct = 100.0 * other_votes / total_votes

    fig = go.Figure()

    fig.add_trace(
        go.Bar(
            name="Democrats",
            x=[dem_pct],
            y=[""],
            orientation="h",
            marker_color="#2A71AE",
            text=[f"{dem_pct:.1f}%<br>{int(dem_votes):,} votes"],
            textposition="inside",
        )
    )
    fig.add_trace(
        go.Bar(
            name="Republicans",
            x=[gop_pct],
            y=[""],
            orientation="h",
            marker_color="#B82D35",
            text=[f"{gop_pct:.1f}%<br>{int(gop_votes):,} votes"],
            textposition="inside",
        )
    )
    if oth_pct >= 0.3:
        fig.add_trace(
            go.Bar(
                name="Others / Uncaptured",
                x=[oth_pct],
                y=[""],
                orientation="h",
                marker_color="#6B7280",
                text=[f"{oth_pct:.1f}%<br>{int(other_votes):,} votes"],
                textposition="inside",
            )
        )

    fig.update_layout(
        barmode="stack",
        height=250,
        margin=dict(l=0, r=0, t=55, b=0),
        title=dict(text=title_html, x=0),
        showlegend=True,
        legend=dict(orientation="h", yanchor="top", y=-0.2, xanchor="left", x=0),
        paper_bgcolor="rgba(0,0,0,0)",
        plot_bgcolor="rgba(0,0,0,0)",
        xaxis=dict(visible=False, range=[0, 100]),
        yaxis=dict(visible=False),
        font=dict(size=18, color="white"),
    )

    st.plotly_chart(fig, use_container_width=True)


def render_statewide_bars(df: pd.DataFrame, year: int):
    d = df[df["year"] == year]
    dem_votes = float(d["votes_dem"].sum())
    gop_votes = float(d["votes_gop"].sum())
    total_votes = float(d["total_votes"].sum())

    title = f"<b>Two Parties. Texas’s Vote.</b><br><span style='font-size:14px'>Texas vote share — {year}</span>"
    render_vote_share_bar(dem_votes, gop_votes, total_votes, title)


def render_county_bars(df: pd.DataFrame, county_fips: str, year: int):
    d = df[(df["county_fips"] == county_fips) & (df["year"] == year)]
    if d.empty:
        st.warning("No data for this county/year.")
        return
    row = d.iloc[0]
    title = f"<b>{row['county_name']} — Vote share</b><br><span style='font-size:14px'>{year}</span>"
    render_vote_share_bar(float(row["votes_dem"]), float(row["votes_gop"]), float(row["total_votes"]), title)


# ----------------------------
# Snapshot cards
# ----------------------------
def texas_snapshot_cards(df: pd.DataFrame):
    d24 = df[df["year"] == 2024].copy()
    if d24.empty:
        return
    dem_counties = int((d24["per_dem"] > d24["per_gop"]).sum())
    gop_counties = int((d24["per_gop"] >= d24["per_dem"]).sum())
    closest = d24.loc[d24["per_point_diff"].abs().idxmin()]
    top_votes = d24.loc[d24["total_votes"].idxmax()]

    c1, c2, c3, c4 = st.columns(4)
    c1.metric("🟦 DEM counties (2024)", dem_counties)
    c2.metric("🟥 GOP counties (2024)", gop_counties)
    c3.metric("Closest county (margin pts)", f"{closest['county_name']} ({closest['per_point_diff']:+.1f})")
    c4.metric("Highest votes cast", f"{top_votes['county_name']} ({int(top_votes['total_votes']):,})")


# ----------------------------
# Main App
# ----------------------------
st.set_page_config(page_title="Texas Election Map + Insights", layout="wide")
inject_css()

st.markdown(
    """
<div class="tt-card">
  <div class="tt-title">Texas Election Shift Analyzer</div>
  <div class="tt-sub">Texas counties colored by winner. Hover for county stats. (Pydeck map for speed.)</div>
</div>
""",
    unsafe_allow_html=True,
)

df = load_and_standardize_tx()

# Session state
if "selected_fips" not in st.session_state:
    st.session_state.selected_fips = None

# Sidebar
st.sidebar.markdown("## Controls")
year = st.sidebar.selectbox("Year", [2016, 2020, 2024], index=2)
use_ai = st.sidebar.checkbox("Enable AI insights", value=True)

if st.sidebar.button("Clear selected county"):
    st.session_state.selected_fips = None

texas_snapshot_cards(df)

# Load geojson
try:
    geo = load_tx_geojson(TX_GEOJSON_PATH)
except FileNotFoundError:
    st.error("Missing `data/texas_counties.geojson`. Run `create_texas_geojson.py` to generate it.")
    st.stop()

# Year slice + lookup
d_year, lookup = year_slice_and_lookup(df, year)

# ----------------------------
# Pydeck map (Texas-only, CARTO light basemap) — Winner colors
# NOTE: Streamlit pydeck cannot reliably capture click-to-select.
# We'll provide selection via dropdown below (fast + reliable).
# ----------------------------
# Embed stats in GeoJSON features for fast tooltip
tx_features = []
for feat in geo.get("features", []):
    fips = str(feat.get("id") or feat.get("properties", {}).get("geoid", "")).zfill(5)
    row = lookup.get(fips)
    if not row:
        continue

    winner_is_dem = float(row["per_dem"]) > float(row["per_gop"])
    fill = [42, 113, 174, 170] if winner_is_dem else [184, 45, 53, 170]  # blue/red

    tx_features.append(
        {
            "type": "Feature",
            "geometry": feat["geometry"],
            "properties": {
                "county_fips": fips,
                "county_name": row["county_name"],
                "per_dem": f"{float(row['per_dem']):.1f}",
                "per_gop": f"{float(row['per_gop']):.1f}",
                "per_point_diff": f"{float(row['per_point_diff']):+.1f}",
                "total_votes": f"{int(row['total_votes']):,}",
                "winner": "Democratic" if winner_is_dem else "Republican",
                "fill_rgba": fill,
            },
        }
    )

tx_geo = {"type": "FeatureCollection", "features": tx_features}

counties_layer = pdk.Layer(
    "GeoJsonLayer",
    data=tx_geo,
    pickable=True,
    auto_highlight=True,
    get_fill_color="properties.fill_rgba",
    get_line_color=[0, 0, 0, 60],
    line_width_min_pixels=0.6,
)

cities = [
    {"name": "El Paso", "lat": 31.7619, "lon": -106.4850},
    {"name": "Fort Worth", "lat": 32.7555, "lon": -97.3308},
    {"name": "Dallas", "lat": 32.7767, "lon": -96.7970},
    {"name": "Austin", "lat": 30.2672, "lon": -97.7431},
    {"name": "San Antonio", "lat": 29.4241, "lon": -98.4936},
    {"name": "Houston", "lat": 29.7604, "lon": -95.3698},
    {"name": "Corpus Christi", "lat": 27.8006, "lon": -97.3964},
]

city_points = pdk.Layer(
    "ScatterplotLayer",
    data=cities,
    get_position="[lon, lat]",
    get_radius=9000,
    get_fill_color=[15, 23, 42, 220],
    pickable=False,
)

city_labels = pdk.Layer(
    "TextLayer",
    data=cities,
    get_position="[lon, lat]",
    get_text="name",
    get_size=14,
    get_color=[15, 23, 42, 230],
    get_text_anchor="'start'",
    get_alignment_baseline="'center'",
    pickable=False,
)

view_state = pdk.ViewState(
    latitude=31.0,
    longitude=-99.0,
    zoom=5.6,
    pitch=0,
    bearing=0,
)

tooltip = {
    "html": """
    <div style="font-family: ui-sans-serif, system-ui; font-size: 13px;">
      <div style="font-weight: 800; font-size: 14px; margin-bottom: 6px;">
        {properties.county_name}
      </div>

      <div style="margin-bottom: 8px;">
        <span style="font-weight: 700;">Winner:</span> {properties.winner}<br/>
        <span style="font-weight: 700;">FIPS:</span> {properties.county_fips}
      </div>

      <div style="display:grid; grid-template-columns: 1fr 1fr; gap: 6px 14px;">
        <div><span style="font-weight:700;">Dem %:</span> {properties.per_dem}</div>
        <div><span style="font-weight:700;">GOP %:</span> {properties.per_gop}</div>
        <div style="grid-column: 1 / -1;">
          <span style="font-weight:700;">Margin (GOP − DEM):</span> {properties.per_point_diff}
        </div>
        <div style="grid-column: 1 / -1;">
          <span style="font-weight:700;">Total votes:</span> {properties.total_votes}
        </div>
      </div>
    </div>
    """,
    "style": {
        "backgroundColor": "rgba(255,255,255,0.98)",
        "color": "#0f172a",
        "padding": "10px 12px",
        "borderRadius": "10px",
        "boxShadow": "0 8px 20px rgba(0,0,0,0.15)",
    },
}


deck = pdk.Deck(
    layers=[counties_layer, city_points, city_labels],
    initial_view_state=view_state,
    tooltip=tooltip,
    map_provider="carto",
    map_style="light",
)

st.pydeck_chart(deck, use_container_width=True)

# ----------------------------
# Reliable selection (dropdown) + bars + insight
# ----------------------------
st.markdown("")

counties = sorted(d_year["county_name"].unique().tolist())
default_idx = 0
if st.session_state.selected_fips and st.session_state.selected_fips in lookup:
    default_name = lookup[st.session_state.selected_fips]["county_name"]
    if default_name in counties:
        default_idx = counties.index(default_name)

sel_name = st.selectbox("Select a county (updates bar chart + insight)", counties, index=default_idx)

# Update selected_fips from name
sel_row = d_year[d_year["county_name"] == sel_name].iloc[0]
st.session_state.selected_fips = str(sel_row["county_fips"]).zfill(5)

# ----------------------------
# Bars + Insight region
# ----------------------------
_dark_panel_open()

render_county_bars(df, st.session_state.selected_fips, year)

st.markdown("<h3 style='margin:6px 0 0 0;'>Quick insight</h3>", unsafe_allow_html=True)

county_fips = st.session_state.selected_fips
county_all_years = df[df["county_fips"] == county_fips].sort_values("year")
county_name = county_all_years.iloc[0]["county_name"]

if use_ai:
    if st.button("Generate AI insight", key=f"ai_{county_fips}_{year}"):
        summary = build_county_summary(county_all_years)
        summary_json = json.dumps(summary, sort_keys=True)
        st.markdown(cached_gpt_quick_insight_json(county_name, summary_json))
    else:
        st.caption("AI is enabled. Click “Generate AI insight” to run GPT.")
else:
    d16 = county_all_years[county_all_years["year"] == 2016].iloc[0]
    d24 = county_all_years[county_all_years["year"] == 2024].iloc[0]
    shift = float(d24["per_dem"] - d16["per_dem"])
    direction = "more Democratic" if shift > 0 else "more Republican"
    st.markdown(f"From 2016 to 2024, **{county_name} shifted {abs(shift):.1f} points {direction}**.")

_dark_panel_close()

st.caption("Hover to view county stats. Use the dropdown to update the bar + insight (fast + stable on Streamlit).")
