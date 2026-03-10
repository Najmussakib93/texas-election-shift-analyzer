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

.map-legend{
  display:flex; gap:18px; align-items:center;
  padding:8px 12px;
  background:rgba(255,255,255,0.05);
  border-radius:8px;
  font-size:0.82rem;
  color:rgba(255,255,255,0.75);
  margin-top:-4px;
}
.legend-swatch{
  display:inline-block; width:14px; height:14px;
  border-radius:3px; margin-right:5px; vertical-align:middle;
}

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
    df16 = pd.read_csv(DATA_2016)
    df16 = df16[df16["state_abbr"] == "TX"].copy()
    df16["county_fips"] = df16["combined_fips"].apply(lambda x: f"{int(x):05d}")
    df16["state_name"] = "Texas"
    df16["year"] = 2016
    df16 = df16[
        ["state_name", "county_fips", "county_name", "votes_dem", "votes_gop",
         "total_votes", "per_dem", "per_gop", "per_point_diff", "year"]
    ]

    df20 = pd.read_csv(DATA_2020)
    df20 = df20[df20["state_name"] == "Texas"].copy()
    df20["county_fips"] = df20["county_fips"].apply(lambda x: f"{int(x):05d}")
    df20["year"] = 2020
    df20 = df20[
        ["state_name", "county_fips", "county_name", "votes_dem", "votes_gop",
         "total_votes", "per_dem", "per_gop", "per_point_diff", "year"]
    ]

    df24 = pd.read_csv(DATA_2024)
    df24 = df24[df24["state_name"] == "Texas"].copy()
    df24["county_fips"] = df24["county_fips"].apply(lambda x: f"{int(x):05d}")
    df24["year"] = 2024
    df24 = df24[
        ["state_name", "county_fips", "county_name", "votes_dem", "votes_gop",
         "total_votes", "per_dem", "per_gop", "per_point_diff", "year"]
    ]

    df = pd.concat([df16, df20, df24], ignore_index=True)
    for c in ["votes_dem", "votes_gop", "total_votes", "per_dem", "per_gop", "per_point_diff"]:
        df[c] = pd.to_numeric(df[c], errors="coerce")
    df["county_fips"] = df["county_fips"].astype(str).str.zfill(5)
    return df


@st.cache_data(show_spinner=False)
def load_tx_geojson(path: str) -> Dict[str, Any]:
    with open(path, "r", encoding="utf-8") as f:
        geo = json.load(f)
    for feat in geo.get("features", []):
        if "properties" not in feat or feat["properties"] is None:
            feat["properties"] = {}
        geoid = feat["properties"].get("geoid") or feat.get("id")
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
# Map color helpers
# ----------------------------
def winner_rgba(per_dem: float, per_gop: float, alpha: int = 170):
    return [42, 113, 174, alpha] if float(per_dem) > float(per_gop) else [184, 45, 53, alpha]


def margin_rgba(margin: float, alpha: int = 200) -> list:
    """
    per_point_diff = GOP% - DEM%.  Positive = GOP leads, negative = DEM leads.
    Gradient: deep red (strong GOP) → light pink → light blue → deep blue (strong DEM).
    """
    t = max(-1.0, min(1.0, float(margin) / 50.0))
    if t >= 0:
        # neutral light pink [240, 200, 200] → deep red [184, 45, 53]
        r = int(240 + t * (184 - 240))
        g = int(200 + t * (45 - 200))
        b = int(200 + t * (53 - 200))
    else:
        at = -t
        # neutral light blue [200, 220, 240] → deep blue [42, 113, 174]
        r = int(200 + at * (42 - 200))
        g = int(220 + at * (113 - 220))
        b = int(240 + at * (174 - 240))
    return [r, g, b, alpha]


def turnout_rgba(total_votes: float, max_votes: float, alpha: int = 210) -> list:
    """Light gray [220, 220, 235] → deep purple [75, 0, 130]."""
    t = max(0.0, min(1.0, float(total_votes) / float(max_votes))) if max_votes else 0.0
    r = int(220 + t * (75 - 220))
    g = int(220 + t * (0 - 220))
    b = int(235 + t * (130 - 235))
    return [r, g, b, alpha]


# ----------------------------
# Statewide summary stats
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
# Vote share bar (stacked horizontal)
# ----------------------------
def render_vote_share_bar(dem_votes: float, gop_votes: float, total_votes: float, title_html: str, key: str = "vsbar"):
    other_votes = max(0.0, total_votes - dem_votes - gop_votes)
    if not total_votes or total_votes <= 0:
        st.warning("No vote totals available.")
        return

    dem_pct = 100.0 * dem_votes / total_votes
    gop_pct = 100.0 * gop_votes / total_votes
    oth_pct = 100.0 * other_votes / total_votes

    fig = go.Figure()
    fig.add_trace(go.Bar(
        name="Democrats", x=[dem_pct], y=[""], orientation="h",
        marker_color="#2A71AE",
        text=[f"{dem_pct:.1f}%<br>{int(dem_votes):,} votes"],
        textposition="inside",
    ))
    fig.add_trace(go.Bar(
        name="Republicans", x=[gop_pct], y=[""], orientation="h",
        marker_color="#B82D35",
        text=[f"{gop_pct:.1f}%<br>{int(gop_votes):,} votes"],
        textposition="inside",
    ))
    if oth_pct >= 0.3:
        fig.add_trace(go.Bar(
            name="Others / Uncaptured", x=[oth_pct], y=[""], orientation="h",
            marker_color="#6B7280",
            text=[f"{oth_pct:.1f}%<br>{int(other_votes):,} votes"],
            textposition="inside",
        ))

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
    st.plotly_chart(fig, use_container_width=True, key=key)


def render_statewide_bars(df: pd.DataFrame, year: int):
    d = df[df["year"] == year]
    title = f"<b>Two Parties. Texas's Vote.</b><br><span style='font-size:14px'>Texas vote share — {year}</span>"
    render_vote_share_bar(
        float(d["votes_dem"].sum()), float(d["votes_gop"].sum()), float(d["total_votes"].sum()), title,
        key=f"sw_bar_{year}",
    )


def render_county_bars(df: pd.DataFrame, county_fips: str, year: int):
    d = df[(df["county_fips"] == county_fips) & (df["year"] == year)]
    if d.empty:
        st.warning("No data for this county/year.")
        return
    row = d.iloc[0]
    title = f"<b>{row['county_name']} — Vote share</b><br><span style='font-size:14px'>{year}</span>"
    render_vote_share_bar(
        float(row["votes_dem"]), float(row["votes_gop"]), float(row["total_votes"]), title,
        key=f"county_bar_{county_fips}_{year}",
    )


# ----------------------------
# Trend line chart (all years for one county)
# ----------------------------
def render_trend_line(df: pd.DataFrame, county_fips: str, key: str = "trend"):
    d = df[df["county_fips"] == county_fips].sort_values("year")
    if d.empty or len(d) < 2:
        return

    county_name = d.iloc[0]["county_name"]
    years = d["year"].tolist()
    dem_pct = (d["votes_dem"] / d["total_votes"] * 100).tolist()
    gop_pct = (d["votes_gop"] / d["total_votes"] * 100).tolist()

    fig = go.Figure()
    fig.add_trace(go.Scatter(
        x=years, y=dem_pct, name="Democrats",
        mode="lines+markers",
        line=dict(color="#2A71AE", width=3),
        marker=dict(size=9),
        hovertemplate="%{y:.1f}%<extra>Dem</extra>",
    ))
    fig.add_trace(go.Scatter(
        x=years, y=gop_pct, name="Republicans",
        mode="lines+markers",
        line=dict(color="#B82D35", width=3),
        marker=dict(size=9),
        hovertemplate="%{y:.1f}%<extra>GOP</extra>",
    ))
    fig.update_layout(
        title=dict(text=f"<b>{county_name} — Vote share trend (2016–2024)</b>", x=0),
        height=260,
        margin=dict(l=0, r=0, t=50, b=0),
        paper_bgcolor="rgba(0,0,0,0)",
        plot_bgcolor="rgba(0,0,0,0)",
        xaxis=dict(
            tickvals=years, ticktext=[str(y) for y in years],
            color="white", gridcolor="rgba(255,255,255,0.08)",
        ),
        yaxis=dict(
            color="white", gridcolor="rgba(255,255,255,0.08)",
            range=[0, 100], ticksuffix="%",
        ),
        legend=dict(orientation="h", yanchor="top", y=-0.15, xanchor="left", x=0, font=dict(color="white")),
        font=dict(color="white"),
    )
    st.plotly_chart(fig, use_container_width=True, key=key)


# ----------------------------
# Statewide grouped bar trend (all 3 years)
# ----------------------------
def render_statewide_trend(df: pd.DataFrame):
    years = [2016, 2020, 2024]
    dem_pcts, gop_pcts, oth_pcts = [], [], []
    for y in years:
        d = df[df["year"] == y]
        dem = float(d["votes_dem"].sum())
        gop = float(d["votes_gop"].sum())
        total = float(d["total_votes"].sum())
        other = max(0.0, total - dem - gop)
        dem_pcts.append(round(dem / total * 100, 2) if total else 0)
        gop_pcts.append(round(gop / total * 100, 2) if total else 0)
        oth_pcts.append(round(other / total * 100, 2) if total else 0)

    fig = go.Figure()
    fig.add_trace(go.Bar(
        name="Democrats", x=[str(y) for y in years], y=dem_pcts,
        marker_color="#2A71AE",
        text=[f"{p:.1f}%" for p in dem_pcts],
        textposition="outside", textfont=dict(color="white"),
    ))
    fig.add_trace(go.Bar(
        name="Republicans", x=[str(y) for y in years], y=gop_pcts,
        marker_color="#B82D35",
        text=[f"{p:.1f}%" for p in gop_pcts],
        textposition="outside", textfont=dict(color="white"),
    ))
    if any(p >= 0.3 for p in oth_pcts):
        fig.add_trace(go.Bar(
            name="Other", x=[str(y) for y in years], y=oth_pcts,
            marker_color="#6B7280",
            text=[f"{p:.1f}%" for p in oth_pcts],
            textposition="outside", textfont=dict(color="white"),
        ))

    fig.update_layout(
        barmode="group",
        title=dict(text="<b>Texas statewide vote share by election year</b>", x=0),
        height=300,
        margin=dict(l=0, r=0, t=50, b=0),
        paper_bgcolor="rgba(0,0,0,0)",
        plot_bgcolor="rgba(0,0,0,0)",
        xaxis=dict(color="white"),
        yaxis=dict(color="white", gridcolor="rgba(255,255,255,0.08)", ticksuffix="%", range=[0, 75]),
        legend=dict(orientation="h", yanchor="top", y=-0.15, xanchor="left", x=0, font=dict(color="white")),
        font=dict(color="white"),
    )
    st.plotly_chart(fig, use_container_width=True, key="sw_trend")


# ----------------------------
# Top political shifts table
# ----------------------------
def render_top_shifts(df: pd.DataFrame):
    col1, col2 = st.columns(2)
    with col1:
        year_from = st.selectbox("From year", [2016, 2020], index=0, key="shift_from")
    with col2:
        to_opts = [y for y in [2016, 2020, 2024] if y > year_from]
        year_to = st.selectbox("To year", to_opts, index=len(to_opts) - 1, key="shift_to")

    d_from = df[df["year"] == year_from][["county_fips", "county_name", "votes_dem", "total_votes"]].copy()
    d_to   = df[df["year"] == year_to][["county_fips", "votes_dem", "total_votes"]].copy()

    d_from["dem_pct"] = d_from["votes_dem"] / d_from["total_votes"] * 100
    d_to["dem_pct"]   = d_to["votes_dem"]   / d_to["total_votes"]   * 100

    merged = d_from[["county_fips", "county_name", "dem_pct"]].merge(
        d_to[["county_fips", "dem_pct"]], on="county_fips", suffixes=("_from", "_to")
    )
    merged["shift"] = merged["dem_pct_to"] - merged["dem_pct_from"]
    merged["direction"] = merged["shift"].apply(lambda x: "Toward Dem" if x > 0 else "Toward GOP")
    merged = merged.reindex(merged["shift"].abs().sort_values(ascending=False).index).head(15)

    display = merged[["county_name", "dem_pct_from", "dem_pct_to", "shift", "direction"]].copy()
    display.columns = ["County", f"Dem% {year_from}", f"Dem% {year_to}", "Shift (pts)", "Direction"]
    display[f"Dem% {year_from}"] = display[f"Dem% {year_from}"].apply(lambda x: f"{x:.1f}%")
    display[f"Dem% {year_to}"]   = display[f"Dem% {year_to}"].apply(lambda x: f"{x:.1f}%")
    display["Shift (pts)"] = display["Shift (pts)"].apply(lambda x: f"{x:+.1f}")

    st.dataframe(display, use_container_width=True, hide_index=True)


# ----------------------------
# County comparison
# ----------------------------
def render_county_comparison(df: pd.DataFrame, year: int):
    counties = sorted(df["county_name"].unique().tolist())
    default_a = counties.index("Harris") if "Harris" in counties else 0
    default_b = counties.index("Dallas") if "Dallas" in counties else min(1, len(counties) - 1)

    c1, c2 = st.columns(2)
    with c1:
        county_a = st.selectbox("County A", counties, index=default_a, key="comp_a")
    with c2:
        county_b = st.selectbox("County B", counties, index=default_b, key="comp_b")

    col1, col2 = st.columns(2)
    for county_name, col in [(county_a, col1), (county_b, col2)]:
        with col:
            _dark_panel_open()
            d = df[(df["county_name"] == county_name) & (df["year"] == year)]
            if d.empty:
                st.warning(f"No data for {county_name} ({year})")
                _dark_panel_close()
                continue
            row = d.iloc[0]
            title = f"<b>{county_name}</b><br><span style='font-size:13px'>{year}</span>"
            render_vote_share_bar(
                float(row["votes_dem"]), float(row["votes_gop"]), float(row["total_votes"]), title,
                key=f"comp_bar_{county_name}_{year}",
            )
            render_trend_line(df, str(row["county_fips"]).zfill(5), key=f"comp_trend_{county_name}")
            _dark_panel_close()


# ----------------------------
# Snapshot cards
# ----------------------------
def texas_snapshot_cards(df: pd.DataFrame):
    d24 = df[df["year"] == 2024].copy()
    if d24.empty:
        return
    dem_counties = int((d24["per_dem"] > d24["per_gop"]).sum())
    gop_counties = int((d24["per_gop"] >= d24["per_dem"]).sum())
    closest  = d24.loc[d24["per_point_diff"].abs().idxmin()]
    top_votes = d24.loc[d24["total_votes"].idxmax()]

    c1, c2, c3, c4 = st.columns(4)
    c1.metric("🟦 Dem counties (2024)", dem_counties)
    c2.metric("🟥 GOP counties (2024)", gop_counties)
    c3.metric("Closest margin", closest["county_name"], f"{closest['per_point_diff']:+.1f} pts")
    c4.metric("Highest turnout", top_votes["county_name"], f"{int(top_votes['total_votes']):,} votes")


# ----------------------------
# Map legend
# ----------------------------
def render_map_legend(color_mode: str):
    if color_mode == "Winner":
        st.markdown(
            """<div class='map-legend'>
            <span><span class='legend-swatch' style='background:#2A71AE'></span>Democratic win</span>
            <span><span class='legend-swatch' style='background:#B82D35'></span>Republican win</span>
            </div>""",
            unsafe_allow_html=True,
        )
    elif color_mode == "Margin Intensity":
        st.markdown(
            """<div class='map-legend'>
            <span><span class='legend-swatch' style='background:#2A71AE'></span>Strong Dem (+50)</span>
            <span><span class='legend-swatch' style='background:#c8dcf0'></span>Lean Dem</span>
            <span><span class='legend-swatch' style='background:#f0c8c8'></span>Lean GOP</span>
            <span><span class='legend-swatch' style='background:#B82D35'></span>Strong GOP (+50)</span>
            </div>""",
            unsafe_allow_html=True,
        )
    elif color_mode == "Turnout":
        st.markdown(
            """<div class='map-legend'>
            <span><span class='legend-swatch' style='background:#dcdceb'></span>Low turnout</span>
            <span><span class='legend-swatch' style='background:#4b0082'></span>High turnout</span>
            </div>""",
            unsafe_allow_html=True,
        )


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
color_mode = st.sidebar.radio(
    "Map color mode",
    ["Winner", "Margin Intensity", "Turnout"],
    index=0,
    help="Winner: flat red/blue  |  Margin: gradient by vote gap  |  Turnout: shade by votes cast",
)
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

# Max turnout for normalization (used only in Turnout mode)
max_turnout = max((v["total_votes"] for v in lookup.values()), default=1)

# ----------------------------
# Build GeoJSON features with embedded stats + color
# ----------------------------
tx_features = []
for feat in geo.get("features", []):
    fips = str(feat.get("id") or feat.get("properties", {}).get("geoid", "")).zfill(5)
    row = lookup.get(fips)
    if not row:
        continue

    per_dem  = float(row["per_dem"])
    per_gop  = float(row["per_gop"])
    margin   = float(row["per_point_diff"])
    total    = float(row["total_votes"])

    if color_mode == "Winner":
        fill = winner_rgba(per_dem, per_gop)
    elif color_mode == "Margin Intensity":
        fill = margin_rgba(margin)
    else:  # Turnout
        fill = turnout_rgba(total, max_turnout)

    tx_features.append({
        "type": "Feature",
        "geometry": feat["geometry"],
        "properties": {
            "county_fips": fips,
            "county_name": row["county_name"],
            "per_dem": f"{per_dem:.1f}",
            "per_gop": f"{per_gop:.1f}",
            "per_point_diff": f"{margin:+.1f}",
            "total_votes": f"{int(total):,}",
            "winner": "Democratic" if per_dem > per_gop else "Republican",
            "fill_rgba": fill,
        },
    })

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
    {"name": "El Paso",       "lat": 31.7619, "lon": -106.4850},
    {"name": "Fort Worth",    "lat": 32.7555, "lon": -97.3308},
    {"name": "Dallas",        "lat": 32.7767, "lon": -96.7970},
    {"name": "Austin",        "lat": 30.2672, "lon": -97.7431},
    {"name": "San Antonio",   "lat": 29.4241, "lon": -98.4936},
    {"name": "Houston",       "lat": 29.7604, "lon": -95.3698},
    {"name": "Corpus Christi","lat": 27.8006, "lon": -97.3964},
]

city_points = pdk.Layer(
    "ScatterplotLayer", data=cities,
    get_position="[lon, lat]", get_radius=9000,
    get_fill_color=[15, 23, 42, 220], pickable=False,
)
city_labels = pdk.Layer(
    "TextLayer", data=cities,
    get_position="[lon, lat]", get_text="name",
    get_size=14, get_color=[15, 23, 42, 230],
    get_text_anchor="'start'", get_alignment_baseline="'center'",
    pickable=False,
)

view_state = pdk.ViewState(latitude=31.0, longitude=-99.0, zoom=5.6, pitch=0, bearing=0)

tooltip = {
    "html": """
    <div style="font-family: ui-sans-serif, system-ui; font-size: 13px;">
      <div style="font-weight: 800; font-size: 14px; margin-bottom: 6px;">{county_name}</div>
      <div style="margin-bottom: 8px;">
        <span style="font-weight: 700;">Winner:</span> {winner}<br/>
        <span style="font-weight: 700;">FIPS:</span> {county_fips}
      </div>
      <div style="display:grid; grid-template-columns: 1fr 1fr; gap: 6px 14px;">
        <div><span style="font-weight:700;">Dem %:</span> {per_dem}</div>
        <div><span style="font-weight:700;">GOP %:</span> {per_gop}</div>
        <div style="grid-column: 1 / -1;">
          <span style="font-weight:700;">Margin (GOP − DEM):</span> {per_point_diff}
        </div>
        <div style="grid-column: 1 / -1;">
          <span style="font-weight:700;">Total votes:</span> {total_votes}
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
render_map_legend(color_mode)

# ----------------------------
# County selection + analysis
# ----------------------------
st.markdown("")

counties = sorted(d_year["county_name"].unique().tolist())
default_idx = 0
if st.session_state.selected_fips and st.session_state.selected_fips in lookup:
    default_name = lookup[st.session_state.selected_fips]["county_name"]
    if default_name in counties:
        default_idx = counties.index(default_name)

sel_name = st.selectbox("Select a county (updates charts + insight)", counties, index=default_idx)

sel_row = d_year[d_year["county_name"] == sel_name].iloc[0]
st.session_state.selected_fips = str(sel_row["county_fips"]).zfill(5)

county_fips = st.session_state.selected_fips
county_all_years = df[df["county_fips"] == county_fips].sort_values("year")
county_name = county_all_years.iloc[0]["county_name"]

# County analysis panel
_dark_panel_open()

render_county_bars(df, county_fips, year)
render_trend_line(df, county_fips, key=f"main_trend_{county_fips}")

st.markdown("<h3 style='margin:6px 0 0 0;'>Quick insight</h3>", unsafe_allow_html=True)

if use_ai:
    if st.button("Generate AI insight", key=f"ai_{county_fips}_{year}"):
        summary = build_county_summary(county_all_years)
        summary_json = json.dumps(summary, sort_keys=True)
        st.markdown(cached_gpt_quick_insight_json(county_name, summary_json))
    else:
        st.caption("AI is enabled. Click \"Generate AI insight\" to run GPT.")
else:
    if len(county_all_years) >= 2:
        d16 = county_all_years[county_all_years["year"] == county_all_years["year"].min()].iloc[0]
        d24 = county_all_years[county_all_years["year"] == county_all_years["year"].max()].iloc[0]
        shift = float(d24["per_dem"] - d16["per_dem"])
        direction = "more Democratic" if shift > 0 else "more Republican"
        st.markdown(f"From 2016 to 2024, **{county_name} shifted {abs(shift):.1f} points {direction}**.")

_dark_panel_close()

# ----------------------------
# Statewide trend chart
# ----------------------------
with st.expander("Texas statewide vote share trend", expanded=True):
    _dark_panel_open()
    render_statewide_trend(df)
    _dark_panel_close()

# ----------------------------
# County comparison
# ----------------------------
with st.expander("County comparison", expanded=False):
    render_county_comparison(df, year)

# ----------------------------
# Top political shifts
# ----------------------------
with st.expander("Top political shifts by county", expanded=False):
    _dark_panel_open()
    render_top_shifts(df)
    _dark_panel_close()

# ----------------------------
# Statewide AI summary
# ----------------------------
with st.expander("Statewide AI summary", expanded=False):
    _dark_panel_open()
    st.markdown("<h3 style='margin:0 0 8px 0;'>Texas statewide summary</h3>", unsafe_allow_html=True)
    if use_ai:
        if st.button("Generate statewide AI summary", key="statewide_ai"):
            stats = make_statewide_stats(df)
            stats_json = json.dumps(stats, sort_keys=True)
            st.markdown(cached_gpt_statewide_summary_json(stats_json))
        else:
            st.caption("Click to generate a GPT-powered summary of Texas election trends across all three years.")
    else:
        st.caption("Enable AI insights in the sidebar to use this feature.")
    _dark_panel_close()

st.caption("Hover to view county stats. Use the dropdown to update charts and insight.")
