---
name: imdue-setup
description: 'Set up the Immobilien Due Diligence project from scratch. Use when: initializing a new environment, onboarding a developer, configuring .env, installing dependencies, or verifying the local dev setup is working.'
argument-hint: 'Optional: platform (windows|linux|mac) or "docker" for container setup'
---

# Immobilien Due Diligence — Project Setup

## When to Use
- First-time local setup on a new machine
- Onboarding a new developer
- Resetting a broken environment
- Setting up the Docker deployment

## Prerequisites

Verify these are available before starting:

| Tool | Min Version | Check |
| :--- | :--- | :--- |
| Python | 3.11+ | `python --version` |
| pip | current | `pip --version` |
| Docker (optional) | 24+ | `docker --version` |

### WeasyPrint system dependencies (PDF rendering)

**Linux/Debian:**
```bash
sudo apt-get install libpango-1.0-0 libpangoft2-1.0-0 libpangocairo-1.0-0 libcairo2 libgdk-pixbuf-2.0-0 libffi-dev
```
**macOS:** `brew install pango cairo gdk-pixbuf libffi`

**Windows:** Install [GTK3 Runtime](https://github.com/tschoonj/GTK-for-Windows-Runtime-Environment-Installer/releases).

---

## Procedure

### Step 1 — Clone and enter the repo
```bash
git clone https://github.com/dein-user/imdue.git
cd imdue
```

### Step 2 — Create and activate virtual environment
```bash
python -m venv venv

# Windows PowerShell
venv\Scripts\Activate.ps1
# macOS / Linux
source venv/bin/activate
```

### Step 3 — Install Python dependencies
```bash
pip install -r requirements.txt
```

### Step 4 — Create .env from template
```bash
cp .env.example .env
```

Open `.env` and fill in:
- `MANUS_API_KEY` — from [manus.ai](https://manus.ai) dashboard
- `MANUS_FORCE_SKILL_IDS` — discover these in Step 5
- `MANUS_PROJECT_ID` — create this in Step 6 (optional but recommended)

### Step 5 — Discover available Manus skills
```bash
python check_skills.py
```
Find the IDs for **Advanced Document Extraction**, **Legal Text Analysis**, and **Financial Data Processing**. Set them as a comma-separated list in `MANUS_FORCE_SKILL_IDS`.

### Step 6 — Bootstrap Manus project (optional, recommended)
Run the `imdue-manus-bootstrap` skill to create a persistent Manus project with the Due-Diligence persona and store the `project_id` in `.env`.

### Step 7 — Start the app
```bash
chainlit run src/app.py -w
# App available at http://localhost:8000
```

### Step 7 (Docker alternative)
```bash
docker compose up -d
# App available at http://localhost:8000
```

---

## Verification Checklist

- [ ] `python check_skills.py` returns a list of skills without errors
- [ ] `MANUS_API_KEY`, `MANUS_FORCE_SKILL_IDS` are set in `.env`
- [ ] `chainlit run src/app.py -w` starts without errors
- [ ] Uploading a test PDF and typing `analyse` triggers the Manus task
- [ ] A PDF is returned in the chat

---

## Key Files

| File | Purpose |
| :--- | :--- |
| [src/app.py](../../src/app.py) | Chainlit entry point |
| [src/manus_client.py](../../src/manus_client.py) | API upload, task creation, polling |
| [src/schema.py](../../src/schema.py) | Structured output schema |
| [src/pdf_generator.py](../../src/pdf_generator.py) | PDF rendering |
| [src/templates/report.html](../../src/templates/report.html) | PDF Jinja2 template |
| [.env.example](../../.env.example) | Environment variable template |
| [requirements.txt](../../requirements.txt) | Python dependencies |
