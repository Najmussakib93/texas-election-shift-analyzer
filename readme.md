# Texas Election Shift Analyzer

Interactive election analytics tool for exploring how Texas counties voted and shifted across the 2016, 2020, and 2024 U.S. Presidential Elections.

**Live app:** [texas-election-shift-analyzer.streamlit.app](https://texas-election-shift-analyzer-cu6rxpaqgqcrteosuzvl7h.streamlit.app/)

Built by [Najmus Sakib](https://github.com/Najmussakib93)

---

## What It Does

- Renders a county-level Texas map with three color modes: winner (red/blue), margin intensity (gradient), and voter turnout
- Lets users select any of the 254 Texas counties via dropdown to see a vote share breakdown and 2016–2024 trend line
- Shows top political shifts ranked by the largest Democratic/Republican swings between any two election years
- Compares any two counties side by side
- Generates AI-powered insights per county using GPT-4o-mini (optional, requires OpenAI API key)
- Displays a statewide GPT summary of Texas election trends across all three years

---

## Key Features

### Interactive County Map (Pydeck)
- Powered by Pydeck's GeoJsonLayer for fast rendering across all 254 counties
- Three color modes selectable directly above the map: Winner, Margin Intensity, Turnout
- Hover tooltip shows county name, winner, Dem %, GOP %, margin, and total votes
- City reference points (Houston, Dallas, Austin, etc.) overlaid as labeled markers

### Snapshot Stats Bar
- Four real-time metrics that update with the selected year: Democratic counties, Republican counties, closest-margin county, and highest-turnout county
- All stats reflect the currently selected election year (2016, 2020, or 2024)

### County Analysis Panel
- Horizontal stacked bar chart showing Dem/GOP/Other vote share for the selected county and year
- Trend line chart tracking Democratic and Republican vote percentages across all three elections

### Top Political Shifts Table
- Ranks all 254 counties by the size of their partisan swing between any two selected years
- Shows starting Dem%, ending Dem%, point shift, and direction (toward Dem / toward GOP)

### AI Insights (GPT-4o-mini)
- Per-county insight: summarizes the county's political trajectory and flags what to watch
- Statewide summary: GPT analysis of Texas-wide trends across 2016, 2020, and 2024
- Both are cached (1-hour TTL) to avoid redundant API calls
- Falls back to a static shift summary when AI is disabled

---

## Tech Stack

| Layer | Technology |
|---|---|
| App framework | Streamlit |
| Map | Pydeck (GeoJsonLayer) |
| Charts | Plotly (bar, stacked bar, line) |
| Data processing | Pandas |
| AI insights | OpenAI GPT-4o-mini |
| Geospatial data | GeoJSON (Texas county boundaries) |
| Deployment | Streamlit Cloud |

---

## Project Structure

```
texas-election-shift-analyzer/
├── app.py                    # Main Streamlit app
├── ai_insights.py            # GPT integration and county/statewide summaries
├── create_texas_geojson.py   # Filters US GeoJSON to Texas-only features
├── data/
│   ├── 2016.csv
│   ├── 2020.csv
│   ├── 2024.csv
│   └── texas_counties.geojson
├── requirements.txt
└── README.md
```

---

## Setup

```bash
git clone https://github.com/Najmussakib93/texas-election-shift-analyzer.git
cd texas-election-shift-analyzer
pip install -r requirements.txt
```

For AI insights, set your OpenAI API key:

```bash
export OPENAI_API_KEY=your_key_here
# or add it to .streamlit/secrets.toml as OPENAI_API_KEY = "your_key"
```

Run locally:

```bash
streamlit run app.py
```

---

## Data Sources

- County-level presidential election results: 2016, 2020, 2024
- Texas county GeoJSON boundaries derived from US Census TIGER/Line shapefiles
- FIPS codes zero-padded to 5 digits; Texas state prefix is `48`

---

## Author

**Najmus Sakib** — Data Analyst | Data Engineer

- GitHub: [github.com/Najmussakib93](https://github.com/Najmussakib93)
