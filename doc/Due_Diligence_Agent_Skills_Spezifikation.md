# Agent Skills Spezifikation: Immobilien Due Diligence

**Autor:** Manus AI
**Version:** 1.0
**Datum:** 30. Juni 2026

---

## 1. Einleitung

Dieses Dokument spezifiziert die Orchestrierung der KI-Intelligenz für die Immobilien-Due-Diligence-WebApp über die **Manus API**. Es definiert, wie "Agent Skills" und Projekt-Instruktionen kombiniert werden, um hochgeladene Immobiliendokumente (z.B. Grundbücher, Mietverträge, Gutachten) vollautomatisch zu analysieren.

Anstatt für jede Aufgabe den kompletten System-Prompt neu zu übergeben, nutzt die Architektur die Manus API-Funktion `project.create` für dauerhafte Instruktionen (Personas) und `task.create` in Kombination mit `force_skills` und `structured_output_schema` für die exakte Ausführung [1].

---

## 2. Das Projekt- und Skill-Konzept der Manus API

Die Manus API bietet drei wesentliche Mechanismen zur Steuerung der KI:

1. **Projects (`project_id`):** Über `POST /v2/project.create` wird ein Projekt mit einer dauerhaften `instruction` angelegt. Alle Tasks, die in diesem Projekt erstellt werden, erben diese Basis-Instruktion automatisch [2]. Dies ist ideal für die Definition der "Due-Diligence-Persona".
2. **Force Skills (`message.force_skills`):** Spezifische Fähigkeiten der KI können erzwungen werden, um sicherzustellen, dass bestimmte Werkzeuge (z.B. komplexe Dokumentenextraktion oder Websuche nach Vergleichsmieten) genutzt werden [3].
3. **Structured Output (`structured_output_schema`):** Ein "Arm once, fire once"-Mechanismus, der nach Abschluss des Tasks garantiert ein maschinenlesbares JSON gemäß einem strikten Schema liefert [4].

---

## 3. Die Due-Diligence-Persona (Projekt-Instruktion)

Um API-Kosten zu sparen und den Code sauber zu halten, wird beim initialen Setup (oder bei der Erstellung eines neuen Analyse-Vorgangs) ein Manus-Projekt angelegt. 

**API Call:** `POST /v2/project.create`

**Projekt-Instruktion (wird an alle Tasks vererbt):**
> "Du bist ein hochqualifizierter Senior Real Estate Analyst und Due-Diligence-Experte für den deutschen Immobilienmarkt. Deine Aufgabe ist es, komplexe Immobiliendokumente (Grundbuchauszüge, Mietverträge, Teilungserklärungen, Gutachten) präzise zu analysieren. 
> 
> Du arbeitest extrem akkurat, übersiehst keine rechtlichen Fallstricke (z.B. Dienstbarkeiten, Wegerechte, Indexmietklauseln) und bewertest wirtschaftliche Risiken (z.B. Leerstand, Instandhaltungsrückstau) objektiv. Deine Analysen müssen bundesweit für alle deutschen Bundesländer gültig und anwendbar sein. Wenn Informationen in den bereitgestellten Dokumenten fehlen, erfindest du nichts, sondern listest diese als 'Offene Fragen' auf. Du bist direkt, professionell und fokussierst dich ausschließlich auf Fakten und messbare Risiken."

---

## 4. Benötigte Agent Skills (Force Skills)

Um die Due-Diligence-Analyse erfolgreich durchzuführen, muss das Backend beim Aufruf von `task.create` spezifische Skills erzwingen. Die genauen Skill-IDs müssen über `GET /v2/skill.list` in der eigenen Manus-Instanz abgerufen werden [5]. 

Folgende Skill-Kategorien sind für das MVP zwingend erforderlich und müssen in `message.force_skills` übergeben werden:

| Skill-Kategorie | Beschreibung | Warum zwingend erforderlich? |
| :--- | :--- | :--- |
| **Advanced Document Extraction** | Liest und versteht PDFs, Scans und Bilder (OCR) mit komplexem Layout (Tabellen in Mietlisten, Stempel im Grundbuch). | Immobiliendokumente sind oft alte Scans oder komplexe Tabellen. Standard-Text-Extraktion reicht hier nicht aus. |
| **Legal Text Analysis** | Spezialisiert auf das Verstehen von juristischem Fachjargon, Vertragsrecht und Grundbuchrecht. | Erkennt den Unterschied zwischen einer harmlosen Grundschuld und einem wertmindernden Nießbrauchrecht. |
| **Financial Data Processing** | Extrahiert Zahlen, Währungen und Flächenangaben und kann einfache Berechnungen (z.B. Jahresnettokaltmiete) durchführen. | Notwendig, um aus einer 20-seitigen Mietliste die exakten aktuellen und potenziellen Mieteinnahmen zu aggregieren. |

**Beispielhafter API-Payload (`task.create`):**
```json
{
  "project_id": "proj_abc123",
  "message": {
    "content": "Führe die vollständige Due-Diligence-Analyse für die angehängten Dokumente durch. Strukturiere die Ergebnisse strikt nach dem vorgegebenen Schema.",
    "attachments": [{"file_id": "file_xyz789"}],
    "force_skills": [
      "skill_advanced_ocr",
      "skill_legal_analysis",
      "skill_financial_math"
    ]
  },
  "structured_output_schema": { ... }
}
```

---

## 5. Das Structured Output Schema

Das Herzstück der Orchestrierung ist das `structured_output_schema`. Es zwingt die Manus API, nach Abschluss der Analyse (wenn `stop_reason: finish` erreicht ist) die Ergebnisse aus dem Kontext zu extrahieren und als JSON zurückzugeben [4]. 

Das Schema muss strikte Regeln befolgen: `additionalProperties` muss auf `false` gesetzt sein und alle Eigenschaften müssen im `required`-Array gelistet sein [4]. Optionale Felder werden über nullable Types (z.B. `["string", "null"]`) abgebildet.

### Das vollständige Due-Diligence-Schema

```json
{
  "type": "object",
  "properties": {
    "property_address": {
      "type": ["string", "null"],
      "description": "Vollständige Adresse der Immobilie, falls in den Dokumenten auffindbar."
    },
    "document_types_analyzed": {
      "type": "array",
      "items": { "type": "string" },
      "description": "Liste der erkannten Dokumentenarten (z.B. 'Grundbuch', 'Mietvertrag')."
    },
    "overall_risk_level": {
      "type": "string",
      "enum": ["Low", "Medium", "High", "Critical"],
      "description": "Gesamteinschätzung des Risikos basierend auf allen Befunden."
    },
    "executive_summary": {
      "type": "string",
      "description": "Zusammenfassung der wichtigsten Erkenntnisse in 2-3 Sätzen."
    },
    "red_flags": {
      "type": "array",
      "items": {
        "type": "object",
        "properties": {
          "category": { "type": "string", "enum": ["Rechtlich", "Wirtschaftlich", "Technisch", "Umwelt"] },
          "description": { "type": "string" },
          "severity": { "type": "string", "enum": ["Critical", "High", "Medium", "Low"] },
          "source_document": { "type": "string" }
        },
        "required": ["category", "description", "severity", "source_document"],
        "additionalProperties": false
      },
      "description": "Kritische Risiken, priorisiert nach Schweregrad, mit Quelldokument."
    },
    "financial_summary": {
      "type": "object",
      "properties": {
        "current_rent_annual_eur": { "type": ["number", "null"] },
        "estimated_market_rent_annual_eur": { "type": ["number", "null"] },
        "vacancy_risk_assessment": { "type": "string" },
        "maintenance_backlog_notes": { "type": "string" }
      },
      "required": ["current_rent_annual_eur", "estimated_market_rent_annual_eur", "vacancy_risk_assessment", "maintenance_backlog_notes"],
      "additionalProperties": false
    },
    "legal_risks": {
      "type": "array",
      "items": { "type": "string" },
      "description": "Rechtliche Risiken und Befunde aus den Dokumenten."
    },
    "open_questions": {
      "type": "array",
      "items": { "type": "string" },
      "description": "Wichtige Due-Diligence-Punkte, die aus den vorliegenden Dokumenten NICHT beantwortet werden können."
    }
  },
  "required": [
    "property_address", 
    "document_types_analyzed", 
    "overall_risk_level", 
    "executive_summary", 
    "red_flags", 
    "financial_summary", 
    "legal_risks", 
    "open_questions"
  ],
  "additionalProperties": false
}
```

---

## 6. Multi-Turn-Interaktion (Chat)

Wenn der Nutzer nach der generierten Analyse Nachfragen stellt (z.B. *"Erkläre mir das Wegerecht im Detail"*), wird der bestehende Task fortgesetzt. 

Dazu wird `POST /v2/task.sendMessage` aufgerufen. Die `task_id` des initialen Analyse-Tasks wird übergeben. Da die `project_id` bereits mit dem Task verknüpft ist, bleibt die Due-Diligence-Persona aktiv. 

**Wichtig:** Für diese einfachen Chat-Nachfragen wird **kein** `structured_output_schema` mitgeschickt. Das System liefert dann eine normale Textantwort (als Markdown) zurück, die direkt im Chainlit-Frontend angezeigt werden kann [4].

---

## 7. Referenzen

[1] "Manus API Integration Guide", `SKILL.md`, System Knowledge.
[2] "project.create API Documentation", `project.create.mdx`, System Knowledge.
[3] "task.create API Documentation", `task.create.mdx`, System Knowledge.
[4] "Structured Output Documentation", `structured-output.mdx`, System Knowledge.
[5] "skill.list API Documentation", `skill.list.mdx`, System Knowledge.
