import json
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
/* Reduce padding */
.block-container { padding-top: 0.8rem; padding-bottom: 1.2rem; }

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

/* Dark panel for bar + insight */
.tt-dark{
  background:#0f1115;
  border:1px solid rgba(255,255,255,0.08);
  border-radius:14px;
  padding:14px 14px 6px 14px;
}
.tt-dark h3, .tt-dark p, .tt-dark li, .tt-dark span { color: #fff; }

/* Make Streamlit top chrome feel consistent */
header[data-testid="stHeader"] {
  background: #020617;
}
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
def load_tx_geojson(path: str) -> dict:
    """Normalize GeoJSON ids so feature['id'] is 5-digit TX county FIPS."""
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

        # Keep a clean display name if present
        if "name" not in feat["properties"]:
            # some sources store NAME
            if "NAME" in feat["properties"]:
                feat["properties"]["name"] = feat["properties"]["NAME"]

    return geo


@st.cache_data(show_spinner=False)
def geojson_to_df(geo: dict) -> pd.DataFrame:
    """Turn GeoJSON features into a DF for Pydeck GeoJsonLayer."""
    rows = []
    for feat in geo.get("features", []):
        props = feat.get("properties", {}) or {}
        fips = str(feat.get("id") or props.get("geoid") or "").zfill(5)
        rows.append(
            {
                "county_fips": fips,
                "geojson": feat,  # each row is a feature
                "county_name_geo": props.get("name", ""),
            }
        )
    return pd.DataFrame(rows)


@st.cache_data(show_spinner=False)
def year_slice(df: pd.DataFrame, year: int) -> pd.DataFrame:
    d = df[df["year"] == year].copy()
    d["county_fips"] = d["county_fips"].astype(str).str.zfill(5)
    return d


# ----------------------------
# Color helpers (Pydeck uses RGBA arrays)
# ----------------------------
def clamp01(x: float) -> float:
    return max(0.0, min(1.0, x))


def lerp(a: float, b: float, t: float) -> float:
    return a + (b - a) * t


def lerp_rgb(c1, c2, t: float):
    return [int(lerp(c1[i], c2[i], t)) for i in range(3)]


# Tribune-ish palette
BLUE = [42, 113, 174]
RED = [184, 45, 53]
WHITE = [247, 247, 247]


def margin_to_rgba(margin: float, alpha: int = 180) -> list[int]:
    """
    margin = GOP - DEM (positive => red, negative => blue)
    Map margins roughly into [-30, +30] then interpolate.
    """
    if margin is None or pd.isna(margin):
        return [120, 120, 120, 80]

    # normalize with soft clamp
    m = float(margin)
    m = max(-30.0, min(30.0, m))
    if m < 0:
        t = clamp01(abs(m) / 30.0)
        rgb = lerp_rgb(WHITE, BLUE, t)
    else:
        t = clamp01(m / 30.0)
        rgb = lerp_rgb(WHITE, RED, t)
    return [rgb[0], rgb[1], rgb[2], alpha]


def votes_to_rgba(votes: float, vmin: float, vmax: float, alpha: int = 180) -> list[int]:
    """
    Sequential scale: light -> dark.
    """
    if votes is None or pd.isna(votes):
        return [120, 120, 120, 80]

    if vmax <= vmin:
        t = 0.5
    else:
        t = clamp01((float(votes) - vmin) / (vmax - vmin))

    # light gray to near-white-blue-ish (keeps dark UI legible)
    low = [220, 230, 240]
    high = [40, 70, 100]
    rgb = lerp_rgb(low, high, t)
    return [rgb[0], rgb[1], rgb[2], alpha]


# ----------------------------
# Statewide summary stats for AI
# ----------------------------
def make_statewide_stats(df: pd.DataFrame) -> dict:
    out = {}
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
# Tribune-style stacked bars (Plotly)
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
# Build Pydeck map dataframe
# ----------------------------
@st.cache_data(show_spinner=False)
def build_map_df(geo_df: pd.DataFrame, d_year: pd.DataFrame) -> pd.DataFrame:
    keep = d_year[
        ["county_fips", "county_name", "per_dem", "per_gop", "per_point_diff", "total_votes", "votes_dem", "votes_gop"]
    ].copy()

    out = geo_df.merge(keep, on="county_fips", how="left")

    # fill missing names from election file if needed
    out["county_name"] = out["county_name"].fillna(out["county_name_geo"])

    # ensure numeric for tooltip
    for c in ["per_dem", "per_gop", "per_point_diff", "total_votes", "votes_dem", "votes_gop"]:
        out[c] = pd.to_numeric(out[c], errors="coerce")

    return out


def make_fill_colors(map_df: pd.DataFrame, style: str) -> pd.Series:
    if style == "Winner (Red/Blue)":
        winner = (map_df["per_dem"] > map_df["per_gop"])
        return winner.apply(lambda x: [BLUE[0], BLUE[1], BLUE[2], 180] if bool(x) else [RED[0], RED[1], RED[2], 180])

    if style == "Margin (Red↔Blue)":
        return map_df["per_point_diff"].apply(lambda m: margin_to_rgba(m, 190))

    # Total votes
    vmin = float(map_df["total_votes"].min(skipna=True)) if map_df["total_votes"].notna().any() else 0.0
    vmax = float(map_df["total_votes"].max(skipna=True)) if map_df["total_votes"].notna().any() else 1.0
    return map_df["total_votes"].apply(lambda v: votes_to_rgba(v, vmin, vmax, 190))


# ----------------------------
# Main App
# ----------------------------
st.set_page_config(page_title="Texas Election Map + Insights", layout="wide")
inject_css()

st.markdown(
    """
<div class="tt-card">
  <div class="tt-title">Texas Election Shift Analyzer</div>
  <div class="tt-sub">Fast map (Pydeck) + vote-share bars (Plotly) + optional GPT insight.</div>
</div>
""",
    unsafe_allow_html=True,
)

df = load_and_standardize_tx()

if "selected_fips" not in st.session_state:
    st.session_state.selected_fips = None

# Sidebar
st.sidebar.markdown("## Controls")
year = st.sidebar.selectbox("Year", [2016, 2020, 2024], index=2)

map_style = st.sidebar.selectbox(
    "Map style",
    ["Winner (Red/Blue)", "Margin (Red↔Blue)", "Total votes (Turnout)"],
    index=0,
)

use_ai = st.sidebar.checkbox("Enable AI insights", value=True)

if st.sidebar.button("Clear selected county"):
    st.session_state.selected_fips = None

texas_snapshot_cards(df)

# Load geojson
try:
    tx_geo = load_tx_geojson(TX_GEOJSON_PATH)
except FileNotFoundError:
    st.error(
        "Missing `data/texas_counties.geojson`.\n\n"
        "Run `create_texas_geojson.py` to generate it."
    )
    st.stop()

geo_df = geojson_to_df(tx_geo)
d_year = year_slice(df, year)
map_df = build_map_df(geo_df, d_year)

# County search + select (locks the panel)
st.sidebar.markdown("---")
st.sidebar.markdown("### Find your county")
search = st.sidebar.text_input("Type a county name", value="")
counties = sorted([c for c in map_df["county_name"].dropna().unique()])

filtered = [c for c in counties if search.lower() in c.lower()] if search else counties
picked = st.sidebar.selectbox("Select county (locks bar + insight)", ["(None)"] + filtered)

if picked != "(None)":
    picked_fips = map_df.loc[map_df["county_name"] == picked, "county_fips"].iloc[0]
    st.session_state.selected_fips = picked_fips

# Scoreboard row
selected_name = "None"
if st.session_state.selected_fips:
    rr = map_df[map_df["county_fips"] == st.session_state.selected_fips]
    if not rr.empty:
        selected_name = rr.iloc[0]["county_name"]

dem_wins = int((d_year["per_dem"] > d_year["per_gop"]).sum())
gop_wins = int((d_year["per_gop"] >= d_year["per_dem"]).sum())

c1, c2, c3 = st.columns([1, 1, 2])
c1.metric("🟦 DEM counties", dem_wins)
c2.metric("🟥 GOP counties", gop_wins)
c3.metric("Selected county", selected_name)

# ----------------------------
# Pydeck Map
# ----------------------------
# Add fill color column (fast)
map_df = map_df.copy()
map_df["fill_rgba"] = make_fill_colors(map_df, map_style)

tooltip = {
    "html": """
<b>{county_name}</b><br/>
FIPS: {county_fips}<br/><br/>
Dem %: {per_dem}<br/>
GOP %: {per_gop}<br/>
Margin (GOP − DEM): {per_point_diff}<br/>
Total votes: {total_votes}
""",
    "style": {"backgroundColor": "rgba(0,0,0,0.9)", "color": "white"},
}

layer = pdk.Layer(
    "GeoJsonLayer",
    data=map_df,
    get_geojson="geojson",
    pickable=True,
    auto_highlight=True,
    get_fill_color="fill_rgba",
    get_line_color=[255, 255, 255, 70],
    line_width_min_pixels=0.6,
)

# Texas view
view_state = pdk.ViewState(latitude=31.0, longitude=-99.0, zoom=5.2)

deck = pdk.Deck(
    layers=[layer],
    initial_view_state=view_state,
    tooltip=tooltip,
    map_style=None,  # no basemap (clean Tribune-style)
)

st.pydeck_chart(deck, use_container_width=True)

# ----------------------------
# Bars + Insight region
# ----------------------------
st.markdown("")
_dark_panel_open()

if st.session_state.selected_fips:
    render_county_bars(df, st.session_state.selected_fips, year)
else:
    render_statewide_bars(df, year)

st.markdown("<h3 style='margin:6px 0 0 0;'>Quick insight</h3>", unsafe_allow_html=True)

if st.session_state.selected_fips:
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
else:
    if use_ai:
        if st.button("Generate AI statewide summary", key=f"ai_state_{year}"):
            stats_json = json.dumps(make_statewide_stats(df), sort_keys=True)
            st.markdown(cached_gpt_statewide_summary_json(stats_json))
        else:
            st.caption("AI is enabled. Click “Generate AI statewide summary” to run GPT.")
    else:
        st.markdown("Select a county to see a county-specific insight. (AI disabled.)")

_dark_panel_close()

st.caption("Tip: Hover counties for stats. Use the sidebar county search to lock the selection for bars + insight.")
