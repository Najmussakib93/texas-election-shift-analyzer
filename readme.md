# Texas Election Shift Analyzer

Interactive AI-powered election analytics platform for Texas counties using geospatial visualization, multi-year election data, and GPT-generated insights.

Built by [Najmus Sakib](https://github.com/Najmussakib93)

---

## Live Overview

This project analyzes how voting patterns have shifted across Texas counties between the 2016, 2020, and 2024 U.S. Presidential Elections.

Users can:

• Explore an interactive county-level Texas map  
• See which counties voted Democratic or Republican  
• Compare vote share and turnout across election years  
• Click any county to view detailed vote breakdown  
• Generate AI-powered insights explaining political trends

This project combines data engineering, geospatial analytics, interactive visualization, and LLM-powered analysis.

---

## Key Features

### Interactive Texas County Map

• Fully interactive choropleth map using Plotly  
• Counties colored by:

- Winner (Red vs Blue)
- Margin (vote difference)
- Total votes (turnout)

• Hover to view:

- Democratic vote %
- Republican vote %
- Margin
- Total votes

• Click any county to update analysis dynamically

---

### County-Level Vote Analysis

When a county is selected:

• Vote share stacked bar chart  
• Total vote comparison  
• Multi-year trend analysis  
• Visual breakdown of Democratic vs Republican support

---

### AI-Generated Political Insights (GPT-Powered)

Uses OpenAI GPT to generate human-readable explanations such as:

• Which direction the county shifted politically  
• How strong the political trend is  
• Comparison between elections  
• Contextual explanation of voter behavior

Falls back to statistical insight if AI is disabled.

---

### Statewide Analytics

Provides statewide election summaries including:

• Number of Democratic counties  
• Number of Republican counties  
• Closest county by margin  
• Highest turnout county

---

## Tech Stack

### Core Technologies

• Python  
• Streamlit  
• Pandas  
• Plotly

### Data & Geospatial

• GeoJSON county boundaries  
• County-level election datasets (2016, 2020, 2024)

### AI Integration

• OpenAI GPT-4  
• JSON-based structured prompts  
• Cached AI insight generation

### Visualization

• Plotly Choropleth maps  
• Interactive stacked bar charts  
• Real-time UI updates

---

## Project Structure

texas-election-shift-analyzer/
│
├── app.py
├── ai_insights.py
├── create_texas_geojson.py
│
├── data/
│ ├── 2016.csv
│ ├── 2020.csv
│ ├── 2024.csv
│ ├── texas_counties.geojson
│
├── requirements.txt
├── README.md
├── .gitignore

---

## Installation

Clone the repository:

git clone https://github.com/Najmussakib93/texas-election-shift-analyzer.git

cd texas-election-shift-analyzer

Install dependencies:

pip install -r requirements.txt

Run the application:

streamlit run app.py

---

## How It Works

### Data Pipeline

1. Load election datasets for 2016, 2020, 2024
2. Standardize county FIPS codes
3. Merge datasets into unified structure
4. Connect election data with GeoJSON map

---

### Map Interaction Flow

User clicks county →  
Plotly event captures county FIPS →  
Streamlit session state updates →  
Bar chart updates →  
AI insight updates

---

### AI Insight Pipeline

County data →  
Structured JSON summary →  
GPT prompt generation →  
Human-readable explanation

---

## Example Use Cases

This platform can be used for:

• Political analysis  
• Election trend analysis  
• Data visualization portfolio projects  
• Geospatial analytics demonstrations  
• AI-powered analytics systems

---

## Skills Demonstrated

This project demonstrates real-world expertise in:

Data Engineering
• Data cleaning and transformation  
• Multi-source dataset integration

Data Analytics
• Election trend analysis  
• Statistical analysis

Geospatial Analytics
• GeoJSON processing  
• Choropleth mapping

Software Engineering
• Interactive dashboard design  
• Event-driven architecture

AI Integration
• GPT integration  
• Prompt engineering  
• Structured data → natural language

---

## Author

Najmus Sakib

Data Analyst | Data Engineer | AI Engineer

GitHub:  
https://github.com/Najmussakib93

LinkedIn:  
(Add your LinkedIn here)

---

## Future Improvements

• Nationwide election analysis  
• Historical election data (2000-2024)  
• Demographic overlays  
• Turnout prediction model  
• Advanced ML political shift modeling

---

## Why This Project Matters

This project demonstrates the ability to build a complete data analytics platform combining:

• Data engineering  
• Geospatial analytics  
• Interactive visualization  
• AI integration  
• Production-level dashboard design

This reflects real-world systems used by organizations such as:

• Texas Tribune  
• FiveThirtyEight  
• New York Times  
• Political analytics firms
