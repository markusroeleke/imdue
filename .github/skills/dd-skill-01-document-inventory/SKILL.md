---
name: dd-skill-01-document-inventory
description: 'Immobilien Due Diligence: Dokument-Inventarisierung und Vollständigkeitsprüfung. Use when starting a due diligence analysis to classify uploaded documents, identify missing core documents, and generate execution flags for follow-up skills. First mandatory step in the DD workflow.'
argument-hint: 'file_ids[] of all uploaded documents'
---

# Skill 1: Dokument-Inventarisierung und Vollständigkeitsprüfung

## Zweck
Erster Pflicht-Teilschritt der Immobilien-Due-Diligence. Klassifiziert alle hochgeladenen Dokumente nach Typ, prüft ob Kerndokumente fehlen und gibt eine priorisierte Liste fehlender Unterlagen aus. Steuert die bedingte Ausführung aller Folge-Skills (2–8).

## Skill-Steckbrief
- **Skill-Bezeichner:** `dd_skill_01_document_inventory`
- **Erforderliche Force Skills:** `advanced_document_extraction`, `file_classification`
- **Input:** Alle hochgeladenen `file_ids`
- **Parallele Ausführung:** Nein (Voraussetzung für alle Folge-Skills)
- **Geschätzte Dauer:** 3–8 Minuten
- **Credits-Verbrauch:** ~35–110 Credits

## Verwendung
Diesen Skill aufrufen wenn:
- Eine neue Due-Diligence-Analyse gestartet wird
- Neue Dokumente zu einer laufenden Analyse hochgeladen werden
- Geprüft werden soll, welche Dokumente noch fehlen

## Procedure

1. Manus Task anlegen mit `project_id` aus `MANUS_PROJECT_ID` Env-Variable
2. Alle `file_ids` der hochgeladenen Dokumente anhängen
3. `force_skills: ["advanced_document_extraction", "file_classification"]` setzen
4. Prompt (siehe unten) als `message.text` senden
5. `structured_output_schema: SCHEMA_SKILL_01_INVENTORY` anhängen
6. Task-Status pollen bis `completed`
7. Output-JSON für bedingte Ausführung von Skills 2–8 auswerten

## Manus API Prompt

```
Analysiere alle angehängten Dokumente und erstelle ein vollständiges Inventar.

Aufgaben:
1. Klassifiziere jedes Dokument exakt nach Typ (Grundbuchauszug, Mietvertrag, Exposé,
   Energieausweis, Teilungserklärung, WEG-Protokoll, WEG-Jahresabrechnung,
   Bauplan/Grundriss, Technisches Gutachten, Kaufvertragsentwurf, Flurkarte,
   Altlastenauskunft, Sonstiges).
2. Extrahiere pro Dokument: Dateiname, erkannter Typ, Seitenzahl, Sprache, Qualität
   (gut lesbar / teilweise unleserlich / stark beeinträchtigt), Ausstellungsdatum
   falls erkennbar.
3. Ermittle die Adresse/das Objekt, auf das sich die Dokumente beziehen.
4. Prüfe welche der folgenden Kerndokumente fehlen: Grundbuchauszug, Mietvertrag
   oder Mieterliste, Exposé, Energieausweis, aktueller Kaufvertragsentwurf.
5. Prüfe welche der folgenden empfohlenen Dokumente fehlen: WEG-Protokolle
   (letzte 3 Jahre), WEG-Jahresabrechnung, Technisches Gutachten,
   Flurkarte/Lageplan, Altlastenauskunft.
6. Bestimme für jeden der Folge-Skills (Grundbuch, Mietverträge, Wirtschaft,
   Technik, WEG, Standort, Recht), ob ausreichend Dokumente für eine sinnvolle
   Analyse vorliegen.

Erfinde keine Informationen. Wenn ein Dokument unleserlich ist, markiere es als solches.
```

## Structured Output Schema (`SCHEMA_SKILL_01_INVENTORY`)

```json
{
  "type": "object",
  "properties": {
    "property_address": { "type": ["string", "null"] },
    "documents": {
      "type": "array",
      "items": {
        "type": "object",
        "properties": {
          "file_id":        { "type": "string" },
          "file_name":      { "type": "string" },
          "document_type":  { "type": "string" },
          "page_count":     { "type": ["integer", "null"] },
          "issue_date":     { "type": ["string", "null"] },
          "readability":    {
            "type": "string",
            "enum": ["gut", "teilweise_unleserlich", "stark_beeintraechtigt"]
          },
          "notes": { "type": "string" }
        },
        "required": ["file_id", "file_name", "document_type", "page_count",
                     "issue_date", "readability", "notes"],
        "additionalProperties": false
      }
    },
    "missing_core_documents":        { "type": "array", "items": { "type": "string" } },
    "missing_recommended_documents": { "type": "array", "items": { "type": "string" } },
    "missing_data_points":           { "type": "array", "items": { "type": "string" } },
    "skill_execution_flags": {
      "type": "object",
      "properties": {
        "run_grundbuch_analysis":   { "type": "boolean" },
        "run_mietvertrag_analysis": { "type": "boolean" },
        "run_financial_analysis":   { "type": "boolean" },
        "run_technical_analysis":   { "type": "boolean" },
        "run_weg_analysis":         { "type": "boolean" },
        "run_standort_analysis":    { "type": "boolean" },
        "run_legal_analysis":       { "type": "boolean" }
      },
      "required": ["run_grundbuch_analysis", "run_mietvertrag_analysis",
                   "run_financial_analysis", "run_technical_analysis",
                   "run_weg_analysis", "run_standort_analysis", "run_legal_analysis"],
      "additionalProperties": false
    },
    "overall_document_quality": {
      "type": "string",
      "enum": ["vollstaendig", "ausreichend", "lueckenhaft", "unzureichend"]
    },
    "inventory_notes": { "type": "string" }
  },
  "required": ["property_address", "documents", "missing_core_documents",
               "missing_recommended_documents", "missing_data_points",
               "skill_execution_flags", "overall_document_quality", "inventory_notes"],
  "additionalProperties": false
}
```

## Implementierung in `manus_client.py`

See [../../src/manus_client.py](../../src/manus_client.py) for the `run_skill()` helper and polling logic.

The `skill_execution_flags` output of this skill controls conditional execution of Skills 2–8 in the parallel Phase 1.
