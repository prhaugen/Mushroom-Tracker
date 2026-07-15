# Mushroom Tracker

A local web application for tracking mushroom cultivation — substrate recipes, spawn details, environmental conditions, flush yields, and sales — with Govee sensor auto-sync, smart light control, push/email alerts, an AI daily briefing, and a full culture-lineage chain from LC lot through grain spawn to fruiting block.

---

## Requirements

- Python 3.9 or later
- A modern web browser

---

## Installation

### 1. Clone the repository

```bash
git clone https://github.com/prhaugen/Mushroom-Tracker.git
cd Mushroom-Tracker
```

### 2. Install dependencies

```bash
pip install flask rich waitress anthropic apscheduler google-generativeai
```

| Package | Purpose |
|---|---|
| `flask` | Web application framework |
| `rich` | Terminal output for the CLI tool |
| `waitress` | Production WSGI server (multi-threaded, replaces Flask dev server) |
| `anthropic` | Claude API SDK for AI briefing, Q&A, and chamber recommendations |
| `apscheduler` | Runs scheduled jobs: daily briefing, Govee sensor poll, light schedules |
| `google-generativeai` | Gemini API SDK (alternative AI briefing model) |

> **Optional:** Install `reportlab` if you want to regenerate the PDF guides:
> ```bash
> pip install reportlab
> ```

### 3. Set environment variables

The app reads API keys and credentials from Windows user environment variables.

**How to set a variable on Windows:**
1. Open **Start → Search → "Edit environment variables for your account"**
2. Click **New**, enter the name and value, click OK
3. Restart the app after adding variables

| Variable | Required for | Where to get it |
|---|---|---|
| `ANTHROPIC_API_KEY` | AI briefing, Q&A assistant, chamber fit recommendation | [console.anthropic.com](https://console.anthropic.com) |
| `GEMINI_API_KEY` | Gemini-powered AI briefing (alternative to Claude) | [aistudio.google.com](https://aistudio.google.com) |
| `GOVEE_API_KEY` | Govee sensor auto-sync, light control | Govee Developer Platform |
| `GMAIL_APP_PASSWORD` | Email alerts | Google Account → Security → 2-Step Verification → App Passwords |

All features work without these keys except their respective functions. If a key is missing, the app disables that feature gracefully rather than crashing.

---

## Running the app

```bash
python mushroom_app.py
```

Then open **http://localhost:5000** in your browser. The app is served by **Waitress** — a multi-threaded WSGI server — so concurrent requests (multiple tabs, background briefings, sensor polls) are handled without queuing.

Keep the terminal window open while using the app. To stop it, press **Ctrl+C**.

A desktop shortcut (`Mushroom Tracker.lnk`) is also available for double-click launch.

---

## First-time setup

On a fresh database the app redirects you to a one-time chamber setup page. Fill in your chamber name, location, type, and default temperature and humidity targets. After saving you land on the Dashboard — click **+ New Batch** to add your first batch.

The database file (`mushroom_data.db`) is created automatically in the same folder on first run.

---

## Key features

| Feature | Where |
|---|---|
| Batch tracking — substrate, spawn, lifecycle, flush log, sales | Batches → Batch Detail |
| Culture lineage — LC lot → LC jar (with recipe) → grain jar → fruiting block | Supply → LC Lots / LC Jars / Grain Jars |
| Recipe calculator — agar and LC recipes scaled by volume, adjustable concentration | Supply → Recipes |
| Saved recipe presets — name and save custom recipes from the calculator | Supply → Saved Recipes |
| Slant / culture library — track agar slants by species, generation, and use history | Supply → Slants |
| Substrate batches — log and reuse prepared substrate batches across blocks | Supply → Substrate Batches |
| Vendor management — master vendor list linked to LC lots, expenses, and spawn | Supply → Vendors |
| Expense & labor logs — money out and time in, optionally linked to batches | Reports → Expenses / Labor |
| Sales tracking — log sales per batch with species, weight, and price | Sales (nav bar) |
| Checklists (SOPs) — step-by-step process checklists (substrate block prep, agar slants, more) | Supply → Checklists |
| Species reference library — 258 entries with grow parameters and out-grow.com guide links | Species (nav bar) |
| AI Q&A assistant — ask cultivation questions answered in context of your live data | Ask (nav bar) |
| Govee sensor auto-sync (H5179 / H5140) — polls every 10 min | Environment → Govee Auto-Sync |
| Multi-shelf sensor charts — separate line per shelf on batch charts | Batch Detail → Environment tab |
| Smart light & plug control (H6159 strip, H5083 plugs) | Lights (nav bar) |
| Daily light schedules — on/off times via APScheduler | Lights → Light Schedules |
| Environment alerts — push (ntfy) + email after 3 consecutive violations | Alerts (nav bar) |
| Harvest forecast — projects harvest dates from species timelines | Dashboard |
| AI daily briefing — Claude or Gemini analysis of all active batches | Briefing (nav bar) |
| Roadmap & phase gates — tracks progress toward cultivation milestones | Roadmap (nav bar) |

---

## File overview

| File | Purpose |
|---|---|
| `mushroom_app.py` | Flask web application — run this to start the server |
| `mushroom_tracker.py` | Database schema, migrations, and CLI tool |
| `mushroom_agent.py` | AI briefing agent (Claude + Gemini) and APScheduler setup |
| `agent_config.py` | Species timelines, environment guardrails, flush targets |
| `roadmap_gates.py` | Auto-evaluates roadmap phase gate milestones against live DB data |
| `populate_species_conditions.py` | One-time script: populates grow conditions for species_db via Claude |
| `add_grow_guide_urls.py` | One-time script: populates grow_guide_url for species_db from out-grow.com |
| `add_new_species_from_outgrow.py` | One-time script: adds species present on out-grow.com not yet in db |
| `govee_test.py` | Standalone script to list Govee devices and verify API key |
| `seed_data.py` | Generates realistic test data for the sandbox database |
| `generate_guide.py` | Regenerates `mushroom_tracker_guide.pdf` |
| `generate_getting_started.py` | Regenerates `mushroom_tracker_getting_started.pdf` |
| `mushroom.ico` | App icon used by the Windows desktop shortcut |

---

## CLI usage

The CLI provides core functions without a browser:

```bash
python mushroom_tracker.py status           # Dashboard summary
python mushroom_tracker.py batch add        # Add a new batch
python mushroom_tracker.py batch list       # List all batches
python mushroom_tracker.py batch update <id>  # Update batch status
python mushroom_tracker.py flush log <id>   # Log a harvest
python mushroom_tracker.py env log          # Log an environment reading
python mushroom_tracker.py report           # BE% performance report
```

---

## Sandbox mode

The app includes a sandbox database completely separate from your production data. Click the **PROD** pill in the top-right of the navbar to switch into sandbox mode. To seed it with six months of realistic test data:

```bash
python seed_data.py --sandbox
```

---

## PDF guides

Two PDF guides are included (and ignored by `.gitignore` since they are generated files):

- `mushroom_tracker_guide.pdf` — full user guide (23 sections)
- `mushroom_tracker_getting_started.pdf` — step-by-step first session walkthrough

To regenerate them after making changes:

```bash
python generate_guide.py
python generate_getting_started.py
```
