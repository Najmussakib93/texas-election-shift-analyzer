# Texas Election Shift Analyzer

> An interactive data journalism tool that helps Texans understand how their county voted — and how it shifted — across the 2016, 2020, and 2024 presidential elections.

[![Python](https://img.shields.io/badge/Python-3.9%2B-3776AB?logo=python&logoColor=white)](https://python.org)
[![Streamlit](https://img.shields.io/badge/Streamlit-App-FF4B4B?logo=streamlit&logoColor=white)](https://texas-election-shift-analyzer-cu6rxpaqgqcrteosuzvl7h.streamlit.app/)
[![Django](https://img.shields.io/badge/Django-REST_API-092E20?logo=django&logoColor=white)](./django_api)
[![D3.js](https://img.shields.io/badge/D3.js-v7-F9A03C?logo=d3.js&logoColor=white)](https://d3js.org)
[![OpenAI](https://img.shields.io/badge/GPT--4o--mini-AI_Insights-412991?logo=openai&logoColor=white)](https://openai.com)

**[→ Live App](https://texas-election-shift-analyzer-cu6rxpaqgqcrteosuzvl7h.streamlit.app/)**

---

## Overview

Texas has 254 counties. Understanding how each one voted — and whether it shifted toward Democrats or Republicans over three elections — is a story buried in thousands of rows of data.

This tool surfaces that story. It combines a geospatial county map, year-over-year trend analysis, a partisan shifts ranking, and GPT-powered plain-language insights into a single interface designed for Texans to explore on their own.

The project is built in two layers:
- **Streamlit front-end** — interactive visualization and AI insights for public audiences
- **Django REST API** — a production-style data backend modeled after how newsroom election tools serve live results

---

## Features

### Interactive County Map

Built with **Pydeck's GeoJsonLayer** for fast rendering of all 254 Texas counties without page lag. Three color modes are selectable inline above the map:

| Mode | What it shows |
|---|---|
| **Winner** | Flat red/blue — which party carried each county |
| **Margin Intensity** | Gradient from deep blue (strong Dem) → white (competitive) → deep red (strong GOP) |
| **Turnout** | Gradient from light gray (low votes) → deep purple (high votes), relative to the highest-turnout county in the selected year |

Hover tooltip shows county name, winner, Dem %, GOP %, margin, and total votes. Major cities (Houston, Dallas, Austin, San Antonio, etc.) are overlaid as labeled reference markers.

---

### Snapshot Stats Bar

Four metrics that update dynamically when the year selector changes:

- **Dem counties** — how many of 254 counties voted Democratic
- **GOP counties** — how many voted Republican
- **Closest margin** — the county with the smallest vote gap and its margin in points
- **Highest turnout** — the county with the most votes cast

All four reflect the selected election year, not hardcoded values.

---

### County Analysis Panel

Select any of the 254 counties to see:

- **Animated D3 v7 vote share bar** — stacked bar showing Dem/GOP/Other percentages and raw vote counts, with a left-to-right animation on each county change
- **Trend line chart (Plotly)** — Democratic and Republican vote percentages plotted across 2016, 2020, and 2024 to show the direction of shift
- **AI insight (GPT-4o-mini)** — 2–4 sentence factual summary of the county's trajectory plus two "What to watch" bullets. Falls back to a static shift statement when AI is disabled.

---

### Top Political Shifts Table

Ranks all 254 counties by the size of their partisan swing between any two elections. Users choose a "from" and "to" year; the table returns the 15 largest movers with:

- Starting and ending Democratic vote share
- Point shift (signed)
- Direction (Toward Dem / Toward GOP)

This is the most newsworthy view — the Rio Grande Valley reversal, the suburban shift around Houston and Dallas, and the competitive counties in between all surface immediately.

---

### Statewide Charts & AI Summary

- **Grouped bar chart** — Texas-wide Dem/GOP/Other share across all three election years side by side
- **County comparison** — select any two counties to view their vote share bars and trend lines side by side
- **Statewide AI summary** — GPT-4o-mini analysis of Texas election trends across all three years at once

---

## Architecture

The project is structured in two independent layers:

```
texas-election-shift-analyzer/
│
├── app.py                        # Streamlit app — map, charts, AI, UI
├── ai_insights.py                # GPT-4o-mini integration (county + statewide)
├── create_texas_geojson.py       # Filters US GeoJSON to Texas counties only
│
├── data/
│   ├── 2016.csv                  # County-level presidential results
│   ├── 2020.csv
│   ├── 2024.csv
│   └── texas_counties.geojson   # 254 county polygons (Census TIGER/Line)
│
├── django_api/                   # Production-style REST API
│   ├── manage.py
│   ├── requirements.txt
│   ├── config/                   # Django project settings + URL routing
│   └── elections/
│       ├── models.py             # County + ElectionResult ORM models
│       ├── serializers.py        # DRF serializers (summary + detail)
│       ├── views.py              # APIView classes for all three endpoints
│       ├── urls.py
│       └── management/commands/
│           └── import_election_data.py   # CSV → SQLite importer
│
├── requirements.txt
└── README.md
```

### Production Pipeline

In a live newsroom environment, the Django layer would connect to a live data feed instead of CSVs:

```
AP Election Feed / State SOS API
         ↓
  import_election_data (management command, scheduled via cron)
         ↓
  PostgreSQL (ElectionResult model, indexed by county + year)
         ↓
  Django REST Framework API
       ↓         ↓
React/D3       Streamlit
front-end    analysis tool
```

The `import_election_data` command and ORM models are structured so that swapping the CSV reader for a live API call requires changes in one place only.

---

## Tech Stack

| Layer | Technology | Purpose |
|---|---|---|
| Map | Pydeck (GeoJsonLayer) | Fast geospatial rendering of 254 county polygons |
| Charts | D3.js v7 + Plotly | Animated vote share (D3), trend lines and grouped bars (Plotly) |
| App framework | Streamlit | Interactive UI, session state, caching |
| REST API | Django + DRF | Production-style election data backend |
| Data processing | Pandas | CSV normalization, FIPS standardization, shift calculations |
| AI insights | OpenAI GPT-4o-mini | County and statewide plain-language summaries |
| Geospatial | GeoJSON + Census TIGER/Line | County boundary polygons |
| Deployment | Streamlit Cloud | Public live app |

---

## Setup

### Streamlit App

```bash
git clone https://github.com/Najmussakib93/texas-election-shift-analyzer.git
cd texas-election-shift-analyzer
pip install -r requirements.txt
streamlit run app.py
```

To enable AI insights, set your OpenAI API key:

```bash
# Option 1 — environment variable
export OPENAI_API_KEY=your_key_here

# Option 2 — Streamlit secrets (for deployment)
# Add to .streamlit/secrets.toml:
# OPENAI_API_KEY = "your_key_here"
```

The app runs without an API key — AI insight buttons will show a warning instead of generating text.

---

### Django REST API

```bash
cd django_api
pip install -r requirements.txt

python manage.py migrate
python manage.py import_election_data    # imports all three CSVs into SQLite

python manage.py runserver
```

The Django REST Framework browsable API is enabled in development. Open any endpoint in a browser to explore the JSON interactively:

| Endpoint | Example |
|---|---|
| `GET /api/counties/` | All 254 counties with 2024 summary |
| `GET /api/counties/48201/` | Harris County (Houston) — full 2016–2024 history |
| `GET /api/shifts/?from_year=2016&to_year=2024` | Top 15 partisan swings |

---

## Data Notes

- **Sources:** County-level presidential election results for 2016, 2020, and 2024. GeoJSON boundaries derived from US Census TIGER/Line shapefiles.
- **FIPS codes:** Zero-padded to 5 digits. Texas state prefix is `48`. Example: Harris County = `48201`.
- **Vote percentages:** Stored as decimals (0–1), not percentages (0–100). The margin gradient map normalizes against a 50-point (0.5 decimal) threshold.
- **2016 data difference:** The 2016 CSV uses different column names (`state_abbr`, `combined_fips`) compared to the 2020/2024 format. The data pipeline handles this transparently.

---

## Author

**Najmus Sakib** — Data Analyst · Data Engineer

- GitHub: [github.com/Najmussakib93](https://github.com/Najmussakib93)
- Live app: [texas-election-shift-analyzer.streamlit.app](https://texas-election-shift-analyzer-cu6rxpaqgqcrteosuzvl7h.streamlit.app/)
