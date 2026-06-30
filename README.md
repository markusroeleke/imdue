# Immobilien Due Diligence KI

KI-gestützte Due-Diligence-Analyse für Immobilien-Kaufobjekte. Maklerunterlagen hochladen → vollständiger PDF-Bericht mit Risikobewertung, Kennzahlen und Investment-Score.

---

## Voraussetzungen

| Anforderung | Version |
| :--- | :--- |
| Python | 3.11+ |
| pip | aktuell |
| Manus API Key | [manus.ai](https://manus.ai) |

---

## Setup

### 1. Repository klonen

```bash
git clone https://github.com/markusroeleke/imdue.git
cd imdue
```

### 2. Virtuelle Umgebung erstellen und aktivieren

```bash
python -m venv venv

# Windows
venv\Scripts\Activate.ps1

# macOS / Linux
source venv/bin/activate
```

### 3. Abhängigkeiten installieren

```bash
pip install -r requirements.txt
```

### 4. Umgebungsvariablen konfigurieren

```bash
cp .env.example .env
```

Öffne `.env` und trage deine Werte ein:

```env
MANUS_API_KEY=dein_manus_api_key_hier
MANUS_FORCE_SKILL_IDS=skill_id_1,skill_id_2
MANUS_PROJECT_ID=proj_abc123          # optional
SECRET_KEY=langer_zufaelliger_string  # Phase 2
```

### 5. Verfügbare Manus Skills abrufen (einmalig)

```bash
python check_skills.py
```

Trage die relevanten Skill-IDs (Advanced Document Extraction, Legal Text Analysis, Financial Data Processing) als komma-separierte Liste in `MANUS_FORCE_SKILL_IDS` in deiner `.env` ein.

---

## Starten

### Lokal (Entwicklung)

```bash
chainlit run src/app.py -w
```

Die App ist unter **http://localhost:8000** erreichbar.

### Docker

```bash
docker compose up -d
```

Beim ersten Start wird das Image gebaut. Die App ist danach unter **http://localhost:8000** erreichbar.

> **Hinweis:** Stelle sicher, dass `.env` befüllt ist, bevor du Docker startest. Die Datei wird vom Container über `env_file` eingelesen.

---

## Nutzung

1. **Dokumente hochladen** – Ziehe Maklerunterlagen (Exposé, Grundbuch, Mietverträge, Gutachten …) in das Chat-Fenster.
2. **Analyse starten** – Tippe `analyse` (oder `bericht`, `start`, `auswerten`).
3. **Bericht lesen** – Der vollständige Bericht erscheint direkt im Chat als Markdown.
4. **Bericht herunterladen** – Die `.md`-Datei steht als Dateidownload bereit.
4. **Rückfragen stellen** – Nach der Analyse kannst du Folgefragen stellen (z. B. *„Erkläre das Wegerecht im Detail"*).

---

## Projektstruktur

```
imdue/
├── src/
│   ├── app.py              # Chainlit Frontend + Chat-Logik
│   ├── manus_client.py     # Manus API: Upload, Task, Polling
│   ├── schema.py           # Structured Output Schema
│   ├── pdf_generator.py    # WeasyPrint PDF-Renderer
│   └── templates/
│       └── report.html     # Jinja2 PDF-Template
├── reports/                # Generierte PDFs (lokal)
├── check_skills.py         # Einmaliger Skill-Discovery-Helper
├── .env.example            # Vorlage für Umgebungsvariablen
├── requirements.txt
├── Dockerfile
└── docker-compose.yml
```

---

## Unterstützte Dokumententypen

Exposé · Grundbuchauszug · Mietvertrag / Mieterliste · Energieausweis · Baupläne · WEG-Jahresabrechnung · WEG-Protokoll · Technisches Gutachten · Kaufvertragsentwurf · Flurkarte · Altlastenauskunft

**Formate:** PDF, DOCX, JPG, PNG · **Max.:** 512 MB pro Datei

---

## Häufige Fehler

| Fehler | Ursache | Lösung |
| :--- | :--- | :--- |
| `EnvironmentError: MANUS_API_KEY is not set` | `.env` fehlt oder nicht geladen | `.env.example` kopieren und befüllen |
| `TimeoutError` beim Polling | Task dauert >10 Min. | `timeout`-Parameter in `poll_for_result` erhöhen |
| `HTTP 429` von Manus API | Rate Limit überschritten | Kurz warten; Exponential Backoff erwägen |
| Port 8000 belegt | Anderer Prozess läuft | `chainlit run src/app.py --port 8001` |

---

## Lizenz

MIT
