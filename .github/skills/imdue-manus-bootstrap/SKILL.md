---
name: imdue-manus-bootstrap
description: 'Bootstrap the Manus API project for the Immobilien Due Diligence app. Use when: setting up the persistent project persona for the first time, rotating the project_id, updating the Due-Diligence persona instruction, or discovering and configuring force skill IDs.'
argument-hint: 'Optional: "update-persona" to only refresh the instruction, "skills-only" to only re-discover skill IDs'
---

# Immobilien Due Diligence — Manus API Bootstrap

## When to Use
- First-time setup: creating the Manus project with the Due-Diligence persona
- Updating the persona instruction in the Manus project
- Re-discovering available skills after a Manus plan change
- Rotating or resetting the `MANUS_PROJECT_ID`

---

## Background

The Manus API supports **persistent projects** (`/v2/project.create`). All tasks created inside a project inherit its `instruction` automatically, saving tokens and keeping prompts consistent.

The Due-Diligence persona instruction is defined in [doc/Due_Diligence_Agent_Skills_Spezifikation.md](../../doc/Due_Diligence_Agent_Skills_Spezifikation.md), section 3.

---

## Procedure

### Step 1 — Verify `.env` has a valid API key

```bash
python check_skills.py
```
If this fails with an auth error, fix `MANUS_API_KEY` in `.env` first.

### Step 2 — Discover and configure skill IDs

```bash
python check_skills.py
```

Look for the three required skill categories and copy their IDs:

| Category | Purpose |
| :--- | :--- |
| Advanced Document Extraction / OCR | Reads scans, complex table layouts |
| Legal Text Analysis | Understands Grundbuch, Vertragsrecht |
| Financial Data Processing | Extracts numbers, calculates KPIs |

Set them in `.env`:
```env
MANUS_FORCE_SKILL_IDS=skill_id_ocr,skill_id_legal,skill_id_financial
```

### Step 3 — Create the Manus project (one-time)

Call `POST /v2/project.create` with the persona instruction. Use the Python snippet below or run it directly via the Manus dashboard.

```python
import os, requests
from dotenv import load_dotenv
load_dotenv()

INSTRUCTION = """Du bist ein hochqualifizierter Senior Real Estate Analyst und \
Due-Diligence-Experte fuer den deutschsprachigen Immobilienmarkt. Deine Aufgabe \
ist es, komplexe Maklerunterlagen (Exposés, Grundbuchauszüge, Mietverträge, \
Teilungserklärungen, Gutachten) präzise zu analysieren. Du arbeitest extrem akkurat, \
übersiehst keine rechtlichen Fallstricke (z.B. Dienstbarkeiten, Wegerechte, \
Indexmietklauseln) und bewertest wirtschaftliche Risiken (z.B. Leerstand, \
Instandhaltungsrückstau) objektiv. Wenn Informationen fehlen, erfindest du nichts, \
sondern listest diese als 'Offene Fragen' auf. Du denkst wie ein konservativer Investor, \
markierst Widersprueche und lieferst eine klare Empfehlung \
(Kaufen / Nachverhandeln / Abstand nehmen) inklusive Investment-Score (0-100)."""

res = requests.post(
    "https://api.manus.ai/v2/project.create",
    headers={"x-manus-api-key": os.getenv("MANUS_API_KEY"), "Content-Type": "application/json"},
    json={"instruction": INSTRUCTION},
    timeout=30,
)
res.raise_for_status()
project_id = res.json()["project"]["id"]
print(f"MANUS_PROJECT_ID={project_id}")
```

### Step 4 — Save the project ID

Copy the printed `MANUS_PROJECT_ID` value into `.env`:
```env
MANUS_PROJECT_ID=proj_abc123
```

### Step 5 — Verify the project is used

Start the app and trigger a test analysis:
```bash
chainlit run src/app.py -w
```

In [src/manus_client.py](../../src/manus_client.py), the `create_analysis_task` function reads `MANUS_PROJECT_ID` and includes it in the `task.create` payload. Confirm the task completes successfully.

---

## Updating the Persona (existing project)

Manus does not expose a `project.update` endpoint in v2. To change the persona:
1. Create a new project with the updated instruction (Step 3 above).
2. Update `MANUS_PROJECT_ID` in `.env`.
3. Old tasks under the previous project_id are unaffected.

---

## Rate Limits Reference

| Endpoint | Limit |
| :--- | :--- |
| `task.create` | 10 req / min |
| `task.listMessages` (polling) | 100 req / min |
| `file.upload` | 40 req / min |

If `HTTP 429` appears, wait and retry. For high-volume use, implement exponential backoff in [src/manus_client.py](../../src/manus_client.py).

---

## Checklist

- [ ] `python check_skills.py` returns skills without error
- [ ] `MANUS_FORCE_SKILL_IDS` set with 3 skill IDs
- [ ] Manus project created with persona instruction
- [ ] `MANUS_PROJECT_ID` saved in `.env`
- [ ] Test analysis completes via `chainlit run src/app.py -w`
