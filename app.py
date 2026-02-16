import json
import os
import pandas as pd
import streamlit as st
import plotly.express as px
import plotly.graph_objects as go

from streamlit_plotly_events import plotly_events

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
def load_tx_geojson(path: str):
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


# ----------------------------
# Cache year slice + lookup (performance)
# ----------------------------
@st.cache_data(show_spinner=False)
def year_slice_and_lookup(df: pd.DataFrame, year: int):
    d = df[df["year"] == year].copy()
    d["county_fips"] = d["county_fips"].astype(str).str.zfill(5)
    lookup = d.set_index("county_fips")[
        ["per_dem", "per_gop", "per_point_diff", "total_votes", "county_name", "votes_dem", "votes_gop"]
    ].to_dict("index")
    return d, lookup


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
  <div class="tt-sub">Hover for county stats. Click a county to lock selection and update the bar + insight.</div>
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

metric = st.sidebar.selectbox(
    "Map style",
    ["Winner (Red/Blue)", "Margin (Red↔Blue)", "Total votes (Turnout)"],
    index=0,
)

if st.sidebar.button("Clear selected county"):
    st.session_state.selected_fips = None

use_ai = st.sidebar.checkbox("Enable AI insights", value=True)

texas_snapshot_cards(df)

# Load geojson
try:
    geo = load_tx_geojson(TX_GEOJSON_PATH)
except FileNotFoundError:
    st.error(
        "Texas map disabled: missing `data/texas_counties.geojson`.\n\n"
        "Run `create_texas_geojson.py` to generate it."
    )
    st.stop()

# Cached year slice + lookup
d_year, lookup = year_slice_and_lookup(df, year)

# Selected county name
selected_name = "None"
if st.session_state.selected_fips and st.session_state.selected_fips in lookup:
    selected_name = lookup[st.session_state.selected_fips]["county_name"]

# Scoreboard
dem_wins = int((d_year["per_dem"] > d_year["per_gop"]).sum())
gop_wins = int((d_year["per_gop"] >= d_year["per_dem"]).sum())

c1, c2, c3 = st.columns([1, 1, 2])
c1.metric("🟦 DEM counties", dem_wins)
c2.metric("🟥 GOP counties", gop_wins)
c3.metric("Selected county", selected_name)

# ----------------------------
# Map section (Winner/Margin/Votes) + hover + click
# Winner mode has multiple traces, so we click using trace.locations[pn]
# ----------------------------
if metric == "Winner (Red/Blue)":
    d_year = d_year.copy()
    d_year["winner"] = (d_year["per_dem"] > d_year["per_gop"]).map({True: "Democratic", False: "Republican"})

    fig_map = px.choropleth(
        d_year,
        geojson=geo,
        locations="county_fips",
        featureidkey="id",
        color="winner",
        hover_name="county_name",
        color_discrete_map={"Democratic": "#2A71AE", "Republican": "#B82D35"},
        category_orders={"winner": ["Democratic", "Republican"]},
    )

elif metric == "Margin (Red↔Blue)":
    fig_map = px.choropleth(
        d_year,
        geojson=geo,
        locations="county_fips",
        featureidkey="id",
        color="per_point_diff",
        hover_name="county_name",
        color_continuous_scale=["#2A71AE", "#BFDCEB", "#F7F7F7", "#FACCB4", "#B82D35"],
    )
    fig_map.update_layout(coloraxis=dict(cmid=0))
    fig_map.update_layout(coloraxis_colorbar=dict(title="Margin (GOP − DEM)", len=0.75))

else:
    fig_map = px.choropleth(
        d_year,
        geojson=geo,
        locations="county_fips",
        featureidkey="id",
        color="total_votes",
        hover_name="county_name",
    )
    fig_map.update_layout(coloraxis_colorbar=dict(title="Votes", len=0.75))

# Per-trace hover + outline (fast enough; no AI calls here)
for trace in fig_map.data:
    if getattr(trace, "type", None) != "choropleth":
        continue

    if trace.locations is None:
        locs = []
    else:
        locs = [str(x).zfill(5) for x in list(trace.locations)]

    per_trace_customdata = []
    hovertext = []

    for f in locs:
        row = lookup.get(f)
        if row:
            per_trace_customdata.append(
                [row["per_dem"], row["per_gop"], row["per_point_diff"], row["total_votes"], f]
            )
            hovertext.append(row["county_name"])
        else:
            per_trace_customdata.append([None, None, None, None, f])
            hovertext.append("")

    trace.customdata = per_trace_customdata
    trace.hovertext = hovertext
    trace.hovertemplate = (
        "<b>%{hovertext}</b><br><br>"
        "County FIPS: %{customdata[4]}<br>"
        "Dem %: %{customdata[0]:.1f}<br>"
        "GOP %: %{customdata[1]:.1f}<br>"
        "Margin (GOP − DEM): %{customdata[2]:.1f}<br>"
        "Total votes: %{customdata[3]:,.0f}"
        "<extra></extra>"
    )

    selected_fips = st.session_state.selected_fips
    trace.marker.line.width = [2.2 if (selected_fips and f == selected_fips) else 0.35 for f in locs]
    trace.marker.line.color = "white"

fig_map.update_geos(fitbounds="locations", visible=False)
fig_map.update_layout(margin=dict(l=0, r=0, t=10, b=0), height=560)

clicked = plotly_events(
    fig_map,
    click_event=True,
    hover_event=False,
    select_event=False,
    key=f"tx_map_{metric}_{year}",
)

# Click selection (NO st.rerun)
if clicked:
    ev = clicked[-1]
    curve = ev.get("curveNumber", 0)
    pn = ev.get("pointNumber", None)

    if pn is not None and curve < len(fig_map.data):
        trace = fig_map.data[curve]
        if trace.locations is not None:
            locs = list(trace.locations)
            if 0 <= pn < len(locs):
                loc = str(locs[pn]).zfill(5)
                if loc in lookup and st.session_state.selected_fips != loc:
                    st.session_state.selected_fips = loc


# ----------------------------
# Bars + Insight region
# ----------------------------
st.markdown("")
_dark_panel_open()

# Bar chart changes based on selection
if st.session_state.selected_fips:
    render_county_bars(df, st.session_state.selected_fips, year)
else:
    render_statewide_bars(df, year)

st.markdown("<h3 style='margin:6px 0 0 0;'>Quick insight</h3>", unsafe_allow_html=True)

# Insight changes based on selection
if st.session_state.selected_fips:
    county_fips = st.session_state.selected_fips
    county_all_years = df[df["county_fips"] == county_fips].sort_values("year")
    county_name = county_all_years.iloc[0]["county_name"]

    if use_ai:
        # AI is now explicit to avoid blocking/hanging
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
        st.markdown("Click a county to see a county-specific insight. (AI disabled.)")

_dark_panel_close()

st.caption("Tip: Hover to view county stats. Click a county to lock selection and update the bar + insight.")
