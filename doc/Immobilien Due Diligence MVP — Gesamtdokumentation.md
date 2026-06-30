# Immobilien Due Diligence MVP — Gesamtdokumentation

**Autor:** Manus AI
**Version:** 1.0
**Datum:** 30. Juni 2026

---

## Inhaltsverzeichnis

1. [Projektidee und Ziel](#1-projektidee-und-ziel)
2. [Architektur und Tech-Stack](#2-architektur-und-tech-stack)
3. [Systemarchitektur und Datenfluss](#3-systemarchitektur-und-datenfluss)
4. [Funktionsumfang des MVP](#4-funktionsumfang-des-mvp)
5. [Manus API Integration](#5-manus-api-integration)
6. [Structured Output Schema](#6-structured-output-schema)
7. [Datenmodell](#7-datenmodell)
8. [Sicherheitskonzept](#8-sicherheitskonzept)
9. [Kostenanalyse](#9-kostenanalyse)
10. [Implementierung: Schritt-für-Schritt](#10-implementierung-schritt-für-schritt)
11. [Deployment](#11-deployment)
12. [Skalierungsplan](#12-skalierungsplan)

---

## 1. Projektidee und Ziel

Das MVP ist eine webbasierte Anwendung, die Immobilieninvestoren bei der strukturierten Prüfung von Kaufobjekten unterstützt. Der Nutzer lädt relevante Maklerunterlagen (Exposé, Mieterliste, Grundbuch, Energieausweis etc.) über ein einfaches Chat-Interface hoch. Eine KI analysiert diese Dokumente automatisch und liefert einen vollständigen PDF-Bericht mit Risikobewertung, wirtschaftlichen Kennzahlen, Investment-Score (0–100) und einer Checkliste offener Punkte.

Der entscheidende Architekturansatz: Es wird **keine eigene KI-Infrastruktur** aufgebaut. Die gesamte Analyse-Intelligenz wird an die **Manus API** mit Agent Skills ausgelagert. Die WebApp ist ein schlanker Orchestrierungs-Layer, der in reinem Python implementiert ist.

---

## 2. Architektur und Tech-Stack

### Warum dieser Stack

Die Anwendung ist vollständig in Python implementiert, was die Entwicklungszeit auf wenige Tage reduziert und die Wartbarkeit maximiert. Es werden keine JavaScript-Kenntnisse benötigt. Die KI-Logik entfällt komplett im eigenen Code — kein LangChain, kein RAG, keine Vektordatenbank.

### Komponentenübersicht

| Schicht | Technologie | Aufgabe |
| :--- | :--- | :--- |
| **Frontend / UI** | Chainlit (Python) | Chat-Interface, Datei-Upload, Ergebnisdarstellung |
| **Backend / API** | FastAPI (Python, optional im MVP) | Geschäftslogik, Manus API Orchestrierung, Authentifizierung, PDF-Generierung |
| **Datenbank** | SQLite + SQLAlchemy (optional im MVP) | Nutzerdaten, Projekt-Metadaten, Task-Historie |
| **Authentifizierung** | FastAPI-Users (optional im MVP) | JWT-basiertes E-Mail-Login, bcrypt-Passwort-Hashing |
| **KI-Engine** | Manus API (v2) | Dokumentenverständnis, Entitätsextraktion, Risikoanalyse, Structured Output |
| **Berichts-Rendering** | WeasyPrint + Jinja2 | HTML-zu-PDF-Konvertierung auf Basis der Manus-Ergebnisse |
| **Deployment** | Docker Compose + nginx | Single-Server, TLS-Terminierung, Reverse Proxy |

### Projektstruktur (MVP minimal)

```
due-diligence-mvp/
├── app.py                  # Chainlit Frontend (Einstiegspunkt)
├── manus_client.py         # Manus API Kommunikation
├── schema.py               # Structured Output Schema
├── pdf_generator.py        # PDF-Rendering
├── templates/
│   └── report.html         # Jinja2 PDF-Template
├── reports/                # Generierte PDFs (lokal gespeichert)
├── .env                    # Umgebungsvariablen (NICHT in Git!)
├── requirements.txt        # Python-Abhängigkeiten
├── Dockerfile
└── docker-compose.yml

# Optional in Phase 2 (Auth + Persistenz)
# ├── models.py              # Datenbankmodelle (SQLAlchemy)
# ├── api.py                 # FastAPI App
# └── migrations/            # Alembic Migrations
```

---

## 3. Systemarchitektur und Datenfluss

### Deployment-Topologie

**MVP minimal (ein Prozess):**

```
Internet → nginx (TLS) → Chainlit (Port 8000)
                         ↓
                     Manus API (extern)
                         ↓
                     SQLite (optional, lokal)
```

**Phase 2 (separates Backend):**

```
Internet → nginx (TLS) → Chainlit (Port 8000) → FastAPI (intern, Port 8001)
                                            ↓
                                        Manus API (extern)
                                            ↓
                                        SQLite/PostgreSQL
```

### 5-Phasen-Datenfluss pro Analyse

**Phase 1 — Datei-Upload durch Nutzer**
Der Nutzer lädt ein oder mehrere Dokumente über das Chainlit-Frontend hoch. Der Server empfängt die Dateien temporär.

**Phase 2 — Upload zur Manus API**
Das Backend fordert über `POST /v2/file.upload` eine temporäre, signierte Upload-URL an (3 Minuten gültig). Die Datei wird via HTTP PUT übertragen. Die API liefert eine eindeutige `file_id` zurück. Dateien werden von Manus nach **48 Stunden automatisch gelöscht**.

**Phase 3 — Task-Erstellung mit Skills**
Mit der `file_id` wird über `POST /v2/task.create` ein Analyse-Task erstellt. Der Request enthält: einen präzisen System-Prompt, optional `force_skills` (spezifische Agent-Skill-IDs) und das `structured_output_schema`.

**Phase 4 — Polling und Ergebnisabruf**
Das Backend pollt `GET /v2/task.listMessages` alle 5 Sekunden. Sobald ein Event vom Typ `structured_output_result` erscheint, wird das garantierte, schema-konforme JSON extrahiert.

**Phase 5 — PDF-Rendering und Auslieferung**
Das JSON wird über ein Jinja2-Template in HTML gerendert und via WeasyPrint in ein PDF-Dokument konvertiert. Der Nutzer erhält den Bericht direkt im Chat zum Download.

---

## 4. Funktionsumfang des MVP

### Nutzerverwaltung

**MVP minimal:** anonyme Sessions ohne Login, ein Analyse-Vorgang pro Session.

**Phase 2:** E-Mail-basierte Registrierung und Login via JWT-Tokens. Passwörter werden als bcrypt-Hashes gespeichert. Jeder Nutzer kann beliebig viele **Projekte** anlegen, die jeweils eine zu prüfende Immobilie repräsentieren.

### Unterstützte Dokumententypen

| Dokumentenkategorie | Typische Formate | Analyseschwerpunkt |
| :--- | :--- | :--- |
| Exposé | PDF | Objekt- und Vermarktungsdaten, Verkäuferangaben |
| Grundbuchauszug | PDF, JPG/PNG (Scan) | Eigentümer, Lasten, Beschränkungen, Grundschulden |
| Mietvertrag / Mietliste | PDF, DOCX | Miethöhe, Laufzeit, Indexierung, Sonderklauseln |
| Energieausweis | PDF | Energieklasse, Sanierungsbedarf |
| Baupläne und Grundrisse | PDF, JPG/PNG | Flächenangaben, Raumaufteilung |
| WEG-Jahresabrechnung | PDF | Hausgeld, Instandhaltungsrücklage, Sonderumlagen |
| WEG-Protokoll | PDF | Beschlüsse, geplante Sanierungen, Rechtsstreitigkeiten |
| Technisches Gutachten | PDF | Baumängel, Instandhaltungsrückstau |
| Kaufvertragsentwurf | PDF | Kaufpreis, Bedingungen, Gewährleistungsausschlüsse |
| Flurkarte / Lageplan | PDF, JPG/PNG | Grundstücksgrenzen, Bebauung |
| Altlastenauskunft | PDF | Kontaminationen, Bodenbelastungen |

**Technische Limits:** Max. 512 MB pro Datei, 10 GB gesamt pro Account. Diese Limits müssen serverseitig vor dem Manus-Upload validiert werden (MIME-Typ + Größe).

### Berichtsstruktur (PDF-Output)

| Berichtsabschnitt | Inhalt |
| :--- | :--- |
| **Executive Summary** | Kurzzusammenfassung und Gesamtrisikobewertung (Low / Medium / High / Critical) |
| **Vollstaendigkeitscheck** | Fehlende Unterlagen und Datenluecken |
| **Kennzahlen** | KPIs wie Faktor, Renditen, Kaufpreis pro m2, Cashflow (falls Daten vorhanden) |
| **Risikoanalyse** | Rechtlich, wirtschaftlich, technisch, Standort, Mietausfall (jeweils Low/Medium/High/Critical) |
| **Staerken / Schwaechen** | Verdichtete Chancen und Problemfelder |
| **Investment-Score** | Score 0-100 inkl. Begruendung und Einordnung |
| **Offene Punkte** | Checkliste von Informationen, die noch geprueft werden muessen |
| **Empfehlung** | Klarer Vorschlag: Kaufen / Nachverhandeln / Abstand nehmen |

---

## 5. Manus API Integration

### Authentifizierung

Alle Requests verwenden den Header `x-manus-api-key`. Der Key wird ausschließlich als Umgebungsvariable konfiguriert.

### Wichtige Endpunkte

| Endpunkt | Methode | Verwendung |
| :--- | :--- | :--- |
| `/v2/file.upload` | POST | Upload-URL anfordern |
| `/v2/project.create` | POST | Projekt mit persistenter Instruktion anlegen (optional, empfohlen) |
| `/v2/task.create` | POST | Analyse-Task mit Schema erstellen |
| `/v2/task.listMessages` | GET | Polling auf Ergebnis |
| `/v2/skill.list` | GET | Verfügbare Skills abrufen |
| `/v2/usage.list` | GET | Credit-Verbrauch überwachen |

### Rate Limits (relevant für das MVP)

| Endpunkt | Limit |
| :--- | :--- |
| `task.create` | 10 Requests / Minute |
| `task.listMessages` | 100 Requests / Minute |
| `file.upload` | 40 Requests / Minute |

### Skills einbinden

Verfügbare Skills einmalig abrufen und relevante IDs in `.env` hinterlegen:

```bash
# Einmalig ausführen
python check_skills.py
```

```python
# check_skills.py
from manus_client import get_available_skills
for skill in get_available_skills():
    print(f"ID: {skill['id']} | Name: {skill['name']}")
```

Relevante Skill-IDs in `.env` eintragen:
```env
MANUS_FORCE_SKILL_IDS=skill_id_1,skill_id_2
MANUS_PROJECT_ID=proj_abc123   # optional, falls project.create genutzt wird
```

---

## 6. Structured Output Schema

Das Schema zwingt Manus, Ergebnisse maschinenlesbar zurückzugeben. Pflichtregeln: `"additionalProperties": false` und alle Felder in `"required"`. Felder, die in den Dokumenten fehlen können, werden als nullable Typen modelliert.

```python
DUE_DILIGENCE_SCHEMA = {
    "type": "object",
    "properties": {
        "property_address":        { "type": ["string", "null"] },
        "document_types_analyzed": { "type": "array", "items": { "type": "string" } },
        "overall_risk_level":      { "type": "string", "enum": ["Low", "Medium", "High", "Critical"] },
        "executive_summary":       { "type": "string" },
        "completeness_check": {
            "type": "object",
            "properties": {
                "missing_documents": { "type": "array", "items": { "type": "string" } },
                "missing_data_points": { "type": "array", "items": { "type": "string" } }
            },
            "required": ["missing_documents", "missing_data_points"],
            "additionalProperties": False
        },
        "red_flags": {
            "type": "array",
            "items": {
                "type": "object",
                "properties": {
                    "category":        { "type": "string", "enum": ["Rechtlich", "Wirtschaftlich", "Technisch", "Umwelt"] },
                    "description":     { "type": "string" },
                    "severity":        { "type": "string", "enum": ["Critical", "High", "Medium", "Low"] },
                    "source_document": { "type": "string" }
                },
                "required": ["category", "description", "severity", "source_document"],
                "additionalProperties": False
            }
        },
        "risk_assessment": {
            "type": "object",
            "properties": {
                "legal": { "type": "string", "enum": ["Low", "Medium", "High", "Critical"] },
                "financial": { "type": "string", "enum": ["Low", "Medium", "High", "Critical"] },
                "technical": { "type": "string", "enum": ["Low", "Medium", "High", "Critical"] },
                "location": { "type": "string", "enum": ["Low", "Medium", "High", "Critical"] },
                "tenant_default": { "type": "string", "enum": ["Low", "Medium", "High", "Critical"] }
            },
            "required": ["legal", "financial", "technical", "location", "tenant_default"],
            "additionalProperties": False
        },
        "financial_summary": {
            "type": "object",
            "properties": {
                "current_rent_annual_eur":           { "type": ["number", "null"] },
                "estimated_market_rent_annual_eur":  { "type": ["number", "null"] },
                "vacancy_risk_assessment":           { "type": "string" },
                "maintenance_backlog_notes":         { "type": "string" }
            },
            "required": ["current_rent_annual_eur", "estimated_market_rent_annual_eur",
                         "vacancy_risk_assessment", "maintenance_backlog_notes"],
            "additionalProperties": False
        },
        "kpis": {
            "type": "object",
            "properties": {
                "price_per_sqm_eur": { "type": ["number", "null"] },
                "rent_multiplier": { "type": ["number", "null"] },
                "gross_yield_percent": { "type": ["number", "null"] },
                "net_yield_percent": { "type": ["number", "null"] },
                "cashflow_pre_financing_eur": { "type": ["number", "null"] },
                "cashflow_post_financing_eur": { "type": ["number", "null"] },
                "operating_cost_ratio_percent": { "type": ["number", "null"] },
                "reserve_need_notes": { "type": "string" },
                "sensitivity_analysis_notes": { "type": "string" }
            },
            "required": [
                "price_per_sqm_eur", "rent_multiplier", "gross_yield_percent",
                "net_yield_percent", "cashflow_pre_financing_eur",
                "cashflow_post_financing_eur", "operating_cost_ratio_percent",
                "reserve_need_notes", "sensitivity_analysis_notes"
            ],
            "additionalProperties": False
        },
        "legal_risks":     { "type": "array", "items": { "type": "string" } },
        "strengths":        { "type": "array", "items": { "type": "string" } },
        "weaknesses":       { "type": "array", "items": { "type": "string" } },
        "open_questions":  { "type": "array", "items": { "type": "string" } },
        "investment_score": {
            "type": "object",
            "properties": {
                "score": { "type": "number" },
                "score_explanation": { "type": "string" },
                "classification": { "type": "string", "enum": [
                    "Sehr starkes Investment", "Solides Investment", "Prueffall", "Kritisch", "Nicht empfehlenswert"
                ] }
            },
            "required": ["score", "score_explanation", "classification"],
            "additionalProperties": False
        },
        "recommendation": { "type": "string", "enum": ["Kaufen", "Nachverhandeln", "Abstand nehmen"] }
    },
    "required": ["property_address", "document_types_analyzed", "overall_risk_level",
                 "executive_summary", "completeness_check", "red_flags",
                 "risk_assessment", "financial_summary", "kpis", "legal_risks",
                 "strengths", "weaknesses", "open_questions", "investment_score",
                 "recommendation"],
    "additionalProperties": False
}
```

---

## 7. Datenmodell

**Phase 2 (nach MVP):** Persistenz für Nutzer, Projekte, Dokumente und Berichte.

| Tabelle | Felder | Beschreibung |
| :--- | :--- | :--- |
| `users` | `id`, `email`, `hashed_password`, `is_active`, `created_at` | Nutzerverwaltung via FastAPI-Users |
| `projects` | `id`, `user_id`, `name`, `property_address`, `created_at` | Bündelt Dokumente und Berichte je Immobilie |
| `documents` | `id`, `project_id`, `file_name`, `manus_file_id`, `uploaded_at` | Metadaten der hochgeladenen Dokumente |
| `reports` | `id`, `project_id`, `pdf_path`, `json_result`, `created_at` | Generierte Berichte und Rohdaten |

---

## 8. Sicherheitskonzept

| Maßnahme | Umsetzung |
| :--- | :--- |
| Transportverschlüsselung | TLS via nginx für alle Client-Server-Verbindungen |
| Passwort-Sicherheit | bcrypt-Hashing mit Salt, kein Klartext-Speicher |
| Session-Verwaltung | JWT-Tokens mit konfigurierbarer Ablaufzeit (Phase 2) |
| Upload-Validierung | MIME-Typ-Prüfung und Größenlimit vor Weiterleitung |
| API-Key-Schutz | Ausschließlich als Umgebungsvariable, nie im Quellcode |
| Datenschutz | Manus löscht Dokumente nach 48h automatisch; PDFs nur für authentifizierten Nutzer zugänglich (Phase 2) |

---

## 9. Kostenanalyse

### Manus API Preismodell

Credits werden verbraucht basierend auf: LLM-Token-Verbrauch, Rechenzeit der virtuellen Maschine und Dauer des Tasks. Die Verbrauchsrate liegt bei ca. **11–14 Credits pro Minute** Taskdauer.

### Aktuelle Pläne (Stand: Juni 2026)

| Plan | Preis/Monat | Credits/Monat | Tägliche Refresh-Credits | Preis pro Credit |
| :--- | :--- | :--- | :--- | :--- |
| **Standard** | $20 | 4.000 | 300 (läuft nach 24h ab) | ~$0,005 |
| **Customizable** | $40 | 8.000 | 300 | ~$0,005 |
| **Extended** | $200 | 40.000 | 300 | ~$0,005 |
| **Team** | $20/Seat | 4.000/Seat (Pool) | 300 | ~$0,005 |

> **Wichtig:** Monatliche Plan-Credits verfallen am Ende des Abrechnungszeitraums. Nur gekaufte Add-on Credits verfallen nie.

### Kosten pro Due-Diligence-Analyse (Schätzung)

| Szenario | Dokumente | Geschätzte Dauer | Credits | Kosten |
| :--- | :--- | :--- | :--- | :--- |
| **Minimal** | 1–2 Docs (Grundbuch + Exposé) | 15–20 Min. | ~200–280 | ~$1,00–$1,40 |
| **Standard** | 3–6 Docs | 25–40 Min. | ~350–560 | ~$1,75–$2,80 |
| **Vollständig** | 7–12 Docs | 40–60 Min. | ~560–840 | ~$2,80–$4,20 |

### Gesamtbetriebskosten (TCO) pro Monat

| Volumen | Manus Credits | VPS-Server | Gesamt | Kosten/Analyse |
| :--- | :--- | :--- | :--- | :--- |
| 10 Analysen/Monat | ~$25–45 | ~$5 | **~$30–50** | ~$3,00–5,00 |
| 30 Analysen/Monat | ~$60–130 | ~$5 | **~$65–135** | ~$2,20–4,50 |
| 50 Analysen/Monat | ~$100–210 | ~$10 | **~$110–220** | ~$2,20–4,40 |

> **Empfehlung:** Vor der Preisfestlegung 5–10 Testanalysen durchführen und den tatsächlichen Verbrauch über `GET /v2/usage.list` messen. Bei einem Verkaufspreis von **€15–25 pro Analyse** ist die Marge sehr gesund.

---

## 10. Implementierung: Schritt-für-Schritt

### Schritt 1: Setup

```bash
mkdir due-diligence-mvp && cd due-diligence-mvp
python -m venv venv
# Windows
venv\Scripts\Activate.ps1
# macOS/Linux
# source venv/bin/activate
mkdir templates reports
pip install chainlit requests weasyprint jinja2 python-dotenv

# Optional für Phase 2 (Auth + Persistenz)
# pip install fastapi uvicorn fastapi-users[sqlalchemy] aiosqlite sqlalchemy \
#     python-multipart aiofiles
```

`.env` Datei:
```env
MANUS_API_KEY=dein_manus_api_key_hier
SECRET_KEY=ein_langer_zufaelliger_string_fuer_jwt
DATABASE_URL=sqlite+aiosqlite:///./due_diligence.db
MANUS_FORCE_SKILL_IDS=skill_id_1,skill_id_2
MANUS_PROJECT_ID=proj_abc123
```

### Schritt 2: Manus API Client (`manus_client.py`)

```python
import os, time, requests
from dotenv import load_dotenv
load_dotenv()

MANUS_API_URL = "https://api.manus.ai/v2"

def _headers():
    return {"x-manus-api-key": os.getenv("MANUS_API_KEY"), "Content-Type": "application/json"}

def upload_file_to_manus(file_path: str, file_name: str) -> str:
    res = requests.post(f"{MANUS_API_URL}/file.upload", headers=_headers(), json={"file_name": file_name})
    res.raise_for_status()
    data = res.json()
    with open(file_path, "rb") as f:
        requests.put(data["upload_url"], data=f).raise_for_status()
    return data["file"]["id"]

def create_analysis_task(file_ids: list, schema: dict) -> str:
    skill_ids = [s for s in os.getenv("MANUS_FORCE_SKILL_IDS", "").split(",") if s]
    project_id = os.getenv("MANUS_PROJECT_ID")
    prompt = """Du bist ein hochspezialisierter Immobilien-Due-Diligence-Experte fuer den deutschsprachigen Markt.
Analysiere alle angehaengten Maklerunterlagen auf rechtliche, wirtschaftliche und technische Risiken.
Berechne Kennzahlen, bewerte Risiken je Kategorie, und vergib einen Investment-Score.
Wenn Informationen fehlen, erfinde nichts und liste sie als offene Punkte.
Liefere deine Analyse exakt im geforderten JSON-Format."""
    message = {"content": prompt, "attachments": [{"file_id": fid} for fid in file_ids]}
    if skill_ids:
        message["force_skills"] = skill_ids
    payload = {"message": message, "structured_output_schema": schema}
    if project_id:
        payload["project_id"] = project_id
    res = requests.post(f"{MANUS_API_URL}/task.create", headers=_headers(), json=payload)
    res.raise_for_status()
    return res.json()["task"]["id"]

def poll_for_result(task_id: str, timeout: int = 300) -> dict:
    start = time.time()
    while time.time() - start < timeout:
        events = requests.get(
            f"{MANUS_API_URL}/task.listMessages?task_id={task_id}&order=desc&limit=20",
            headers=_headers()).json().get("data", [])
        for e in events:
            if e.get("type") == "structured_output_result":
                r = e["structured_output_result"]
                if r.get("success"): return r["value"]
                raise Exception(f"Schema-Fehler: {r.get('error')}")
            if e.get("type") == "status_update" and e.get("status_update", {}).get("status") == "error":
                raise Exception("Manus Task fehlgeschlagen.")
        time.sleep(5)
    raise TimeoutError(f"Task {task_id} Timeout nach {timeout}s.")
```

### Schritt 3: PDF-Generator (`pdf_generator.py`)

```python
import os
from datetime import datetime
from jinja2 import Environment, FileSystemLoader
from weasyprint import HTML

def generate_pdf(json_data: dict, output_path: str) -> str:
    os.makedirs(os.path.dirname(output_path) or ".", exist_ok=True)
    env = Environment(loader=FileSystemLoader("templates"))
    html = env.get_template("report.html").render(
        data=json_data, created_at=datetime.now().strftime("%d.%m.%Y %H:%M Uhr"))
    HTML(string=html).write_pdf(output_path)
    return output_path
```

### Schritt 4: Chainlit App (`app.py`)

```python
import os, uuid, asyncio
import chainlit as cl
from dotenv import load_dotenv
from manus_client import upload_file_to_manus, create_analysis_task, poll_for_result
from schema import DUE_DILIGENCE_SCHEMA
from pdf_generator import generate_pdf
load_dotenv()

@cl.on_chat_start
async def start():
    cl.user_session.set("file_ids", [])
    cl.user_session.set("file_names", [])
    await cl.Message(content=(
        "## Willkommen bei der Immobilien Due Diligence KI\n\n"
        "1. Lade deine Dokumente hoch (Grundbuch, Mietverträge, Gutachten…)\n"
        "2. Tippe `analyse` für den vollständigen Bericht\n"
        "3. Du erhältst einen PDF-Bericht zum Download"
    )).send()

@cl.on_message
async def main(message: cl.Message):
    file_ids = cl.user_session.get("file_ids", [])
    file_names = cl.user_session.get("file_names", [])

    if message.elements:
        for el in message.elements:
            if hasattr(el, 'path') and el.path:
                msg = cl.Message(content=f"Lade `{el.name}` hoch...")
                await msg.send()
                try:
                    fid = upload_file_to_manus(el.path, el.name)
                    file_ids.append(fid); file_names.append(el.name)
                    cl.user_session.set("file_ids", file_ids)
                    cl.user_session.set("file_names", file_names)
                    msg.content = f"✅ `{el.name}` hochgeladen."
                    await msg.update()
                except Exception as e:
                    msg.content = f"❌ Fehler: {e}"; await msg.update()
        return

    if message.content.lower().strip() in ["analyse", "analysieren", "bericht", "start"]:
        if not file_ids:
            await cl.Message(content="Bitte zuerst Dokumente hochladen.").send(); return
        msg = cl.Message(content=f"Starte Analyse für {len(file_ids)} Dokument(e)…")
        await msg.send()
        try:
            task_id = create_analysis_task(file_ids, DUE_DILIGENCE_SCHEMA)
            msg.content = "🔍 KI analysiert Dokumente…"; await msg.update()
            result = await asyncio.get_event_loop().run_in_executor(
                None, poll_for_result, task_id)
            msg.content = "📄 Erstelle PDF-Bericht…"; await msg.update()
            pdf = f"reports/report_{uuid.uuid4().hex[:8]}.pdf"
            generate_pdf(result, pdf)
            flags = result.get("red_flags", [])
            high = [f for f in flags if f["severity"] in ["High", "Critical"]]
            await cl.Message(
                content=(f"## ✅ Analyse abgeschlossen\n\n"
                         f"**Objekt:** {result.get('property_address', '–')}\n"
                         f"**Gesamtrisiko:** {result.get('overall_risk_level', '–')}\n"
                         f"**Investment-Score:** {result.get('investment_score', {}).get('score', '–')}\n"
                         f"**Red Flags:** {len(flags)} ({len(high)} kritisch)\n\n"
                         f"_{result.get('executive_summary', '')}_"),
                elements=[cl.File(name="Due_Diligence_Bericht.pdf", path=pdf, display="inline")]
            ).send()
        except Exception as e:
            await cl.Message(content=f"❌ Fehler: {e}").send()
        return

    await cl.Message(content="Lade Dokumente hoch und tippe `analyse` für den Bericht.").send()
```

### Schritt 5: Starten

```bash
chainlit run app.py -w
# Erreichbar unter: http://localhost:8000
```

---

## 11. Deployment

### Dockerfile

```dockerfile
FROM python:3.11-slim
RUN apt-get update && apt-get install -y \
    libpango-1.0-0 libpangoft2-1.0-0 libpangocairo-1.0-0 \
    libcairo2 libgdk-pixbuf2.0-0 libffi-dev \
    && rm -rf /var/lib/apt/lists/*
WORKDIR /app
COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt
COPY . .
RUN mkdir -p reports
EXPOSE 8000
CMD ["chainlit", "run", "app.py", "--host", "0.0.0.0", "--port", "8000"]
```

### docker-compose.yml

```yaml
version: '3.8'
services:
  app:
    build: .
    ports:
      - "8000:8000"
    volumes:
      - ./reports:/app/reports
      - ./due_diligence.db:/app/due_diligence.db
    env_file:
      - .env
    restart: unless-stopped
```

### Server starten

```bash
docker compose up -d
```

---

## 12. Skalierungsplan

Das MVP ist für ~50 Nutzer auf einem einzelnen Server ausgelegt. Für Wachstum auf 100–1.000 Nutzer sind folgende Schritte vorgesehen — ohne Umbau der Kernarchitektur:

| Stufe | Maßnahme | Auslöser |
| :--- | :--- | :--- |
| **Stufe 1** | SQLite → PostgreSQL | >50 gleichzeitige Nutzer |
| **Stufe 2** | Polling → Celery + Redis (async Task Queue) | >20 gleichzeitige Analysen |
| **Stufe 3** | Lokale PDF-Speicherung → S3 / MinIO | >500 Berichte / Monat |
| **Stufe 4** | Manus Standard → Extended Plan | >800 Credits/Tag Verbrauch |
| **Stufe 5** | Single Server → Load Balancer + mehrere Chainlit-Instanzen | >200 gleichzeitige Nutzer |

---

## Häufige Fehler und Lösungen

| Fehler | Ursache | Lösung |
| :--- | :--- | :--- |
| `QuotaExceededError` beim Upload | 10 GB Speicherlimit überschritten | Alte Tasks löschen, Add-on Credits kaufen |
| `TimeoutError` beim Polling | Task dauert >5 Min. | `timeout`-Parameter in `poll_for_result` erhöhen |
| Leeres `structured_output_result` | Schema-Validierungsfehler | Alle Felder in `required` listen, `additionalProperties: false` setzen |
| WeasyPrint-Fehler beim PDF | Fehlende Systemabhängigkeiten | `apt-get install libpango-1.0-0 libcairo2` |
| Chainlit startet nicht | Port 8000 belegt | `chainlit run app.py --port 8001` |
| HTTP 429 von Manus API | Rate Limit überschritten | Exponential Backoff implementieren, Webhooks statt Polling nutzen |

---

*Dieses Dokument fasst alle wesentlichen Architektur-, Implementierungs- und Kostendaten für das Immobilien Due Diligence MVP zusammen. Alle Kostenschätzungen basieren auf offiziellen Manus-Benchmarks (Stand: Juni 2026) und sollten durch eigene Testläufe validiert werden.*
