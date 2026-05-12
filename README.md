# Mushroom Tracker

A local web application for tracking mushroom cultivation — substrate recipes, spawn details, environmental conditions, flush yields, and sales — with a built-in AI daily briefing powered by Claude.

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
pip install flask rich anthropic apscheduler
```

| Package | Purpose |
|---|---|
| `flask` | Web application framework |
| `rich` | Terminal output for the CLI tool |
| `anthropic` | Claude API SDK for the AI daily briefing |
| `apscheduler` | Runs the 06:00 daily briefing schedule automatically |

> **Optional:** Install `reportlab` if you want to regenerate the PDF guides:
> ```bash
> pip install reportlab
> ```

### 3. Set your Anthropic API key *(required for AI briefing only)*

The AI daily briefing requires an API key from [console.anthropic.com](https://console.anthropic.com).

**On Windows** — set it as a user environment variable:

1. Open **Start → Search → "Edit environment variables for your account"**
2. Click **New**
3. Variable name: `ANTHROPIC_API_KEY`
4. Variable value: your key (`sk-ant-...`)
5. Click OK, then restart your terminal

**On macOS / Linux** — add to your shell profile (`~/.zshrc`, `~/.bashrc`, etc.):

```bash
export ANTHROPIC_API_KEY="sk-ant-..."
```

Then reload: `source ~/.zshrc`

> The app and CLI read this variable automatically at startup. No config file is needed. If the key is not set, all features work normally except the AI briefing.

---

## Running the app

```bash
python mushroom_app.py
```

Then open **http://localhost:5000** in your browser.

Keep the terminal window open while using the app. To stop it, press **Ctrl+C**.

---

## First-time setup

On a fresh database the app redirects you to a one-time chamber setup page. Fill in your chamber name, location, type, and default temperature and humidity targets. After saving you land on the Dashboard — click **+ New Batch** to add your first batch.

The database file (`mushroom_data.db`) is created automatically in the same folder on first run.

---

## File overview

| File | Purpose |
|---|---|
| `mushroom_app.py` | Flask web application — run this to start the server |
| `mushroom_tracker.py` | Command-line interface (CLI) |
| `mushroom_agent.py` | AI briefing agent (also triggered by the web app) |
| `agent_config.py` | Species timelines, environment guardrails, flush targets |
| `seed_data.py` | Generates realistic test data for the sandbox database |
| `generate_guide.py` | Regenerates `mushroom_tracker_guide.pdf` |
| `generate_getting_started.py` | Regenerates `mushroom_tracker_getting_started.pdf` |

---

## CLI usage

The CLI provides the same core functions without a browser:

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

- `mushroom_tracker_guide.pdf` — full user guide
- `mushroom_tracker_getting_started.pdf` — step-by-step first session walkthrough

To regenerate them after making changes:

```bash
python generate_guide.py
python generate_getting_started.py
```
