# Video Tutorial Script: RC Insights Demo

**Format:** Screen recording with voiceover  
**Length:** ~2 minutes  
**Tools:** Terminal + Streamlit dashboard + code editor

---

## [0:00 - 0:15] Hook

**SCREEN:** Split view — RevenueCat Charts dashboard on left, terminal on right.

**VOICEOVER:**
"You've got RevenueCat tracking your subscription metrics. But are you actually *using* that data? RC Insights is an open-source tool that connects to the Charts API and uses AI to tell you what matters — and what to fix."

---

## [0:15 - 0:40] Install & Configure

**SCREEN:** Terminal, typing commands.

**VOICEOVER:**
"Getting started takes about 60 seconds. Install from GitHub with pip..."

**TYPE:**
```
pip install rc-insights
```

"...set your API key and project ID..."

**TYPE:**
```
export RC_API_KEY=sk_your_key_here
export RC_PROJECT_ID=proj_your_id
```

"...and optionally add an OpenAI key for AI-powered analysis."

**TYPE:**
```
export OPENAI_API_KEY=sk-your-key
```

---

## [0:40 - 1:05] CLI Demo

**SCREEN:** Terminal, running commands.

**VOICEOVER:**
"Let's start with the CLI. Running `rc-insights overview` gives you a quick snapshot of your key metrics."

**TYPE:**
```
rc-insights overview
```

**SHOW:** Rich table output with metrics.

"Now the real power — generate a full health report."

**TYPE:**
```
rc-insights report --days 30
```

**SHOW:** Health score panel appears (72/100 — Mixed ⚠️), insights table, file save confirmations.

**VOICEOVER:**
"In one command, you get a health score, AI-generated insights, and a downloadable report. The AI caught a trial conversion issue and a churn spike — things I might have missed staring at charts."

---

## [1:05 - 1:35] Web Dashboard

**SCREEN:** Switch to browser, Streamlit app.

**VOICEOVER:**
"If you prefer a visual experience, there's a Streamlit dashboard."

**TYPE (in terminal):**
```
streamlit run app.py
```

**SHOW:** Browser opens. Enter credentials in sidebar. Click "Generate Report."

**VOICEOVER:**
"Enter your credentials, hit Generate, and you get an interactive dashboard. Health score at the top, key metrics cards, AI insights with severity levels..."

**SCROLL:** Show insights section.

"...and interactive Plotly charts for every metric. You can zoom, hover for details, and switch between chart types."

**SHOW:** Click through chart tabs, hover on data points.

**VOICEOVER:**
"And everything is exportable — Markdown for Slack and Notion, or HTML for sharing with your team."

**SHOW:** Click download buttons.

---

## [1:35 - 1:55] Code / Library

**SCREEN:** Code editor with Python file.

**VOICEOVER:**
"For developers who want to build on top of this, it's also a Python library."

**SHOW:**
```python
from rc_insights import ChartsClient

with ChartsClient(api_key="sk_...", project_id="proj...") as client:
    overview = client.get_overview()
    print(f"MRR: ${overview.mrr:,.2f}")
    
    churn = client.get_chart("churn", start_date="2025-01-01")
    for ts, val in churn.data_points:
        print(f"  {ts.date()}: {val:.1f}%")
```

**VOICEOVER:**
"Three lines to pull your MRR. Typed responses, automatic retries, and all 9 confirmed chart types from RevenueCat's Charts API."

---

## [1:55 - 2:10] CTA

**SCREEN:** GitHub repo page.

**VOICEOVER:**
"RC Insights is open source and free. Install it, star the repo, or contribute. Link in the description."

**SHOW:** GitHub star button animation, link overlay.

**TEXT ON SCREEN:**
```
github.com/arimetabot/rc-insights
pip install rc-insights
Built on RevenueCat Charts API v2
```

---

## Production Notes

- **Recording:** Use OBS or ScreenFlow. 1920x1080, 30fps.
- **Terminal theme:** Dark (match the Streamlit dark theme for consistency)
- **Font size:** Bump terminal font to 16pt for readability
- **Music:** Subtle lo-fi background, fade under voiceover
- **Voiceover:** Record separately for clean audio. Alternatively, use ElevenLabs for synthesized VO.
- **Editing:** Cut pauses, speed up install/loading sequences (2-4x)
- **Thumbnail:** Health score "72/100" with gradient background
