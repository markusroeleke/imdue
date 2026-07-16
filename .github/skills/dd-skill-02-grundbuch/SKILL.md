---
name: dd-skill-02-grundbuch
description: 'Immobilien Due Diligence: Grundbuch- und Eigentumsanalyse. Use to analyze Grundbuchauszüge for ownership structure, encumbrances (Lasten), mortgages (Grundschulden), Nießbrauch, Wegerechte, and Auflassungsvormerkungen. Run in parallel with skills 3-8 after skill 1 sets run_grundbuch_analysis=true.'
argument-hint: 'file_ids[] of Grundbuchauszüge, Flurkarten, Teilungserklärungen'
---

# Skill 2: Grundbuch- und Eigentumsanalyse

## Zweck
Analysiert Grundbuchauszüge auf Eigentümerstruktur (Abt. I), eingetragene Lasten und Beschränkungen (Abt. II) sowie Grundpfandrechte (Abt. III). Identifiziert eigentumsrechtliche Risiken wie Nießbrauch, aktive Grundschulden, fehlende Löschungsbewilligungen.

## Skill-Steckbrief
- **Skill-Bezeichner:** `dd_skill_02_grundbuch`
- **Erforderliche Force Skills:** `advanced_document_extraction`, `ocr_handwriting`, `legal_text_analysis`
- **Input:** `file_ids` aller Grundbuchauszüge, Flurkarten, Teilungserklärungen
- **Parallele Ausführung:** Ja (parallel zu Skills 3–8)
- **Geschätzte Dauer:** 5–15 Minuten
- **Credits-Verbrauch:** ~55–210 Credits
- **Ausführungsbedingung:** `skill_execution_flags.run_grundbuch_analysis == true`

## Verwendung
Diesen Skill aufrufen wenn:
- Grundbuchauszüge vorliegen (Flag gesetzt durch Skill 1)
- Eigentumsstruktur und Belastungen geprüft werden sollen
- Kaufpreis-Relevanz von Grundpfandrechten bewertet werden soll

## Procedure

1. Prüfe `skill_execution_flags.run_grundbuch_analysis` aus Skill-1-Output
2. Filtere `file_ids` auf Typen: `Grundbuchauszug`, `Flurkarte`, `Teilungserklärung`
3. Manus Task anlegen mit `force_skills: ["advanced_document_extraction", "ocr_handwriting", "legal_text_analysis"]`
4. Prompt (siehe unten) senden mit gefilterten `file_ids`
5. `structured_output_schema: SCHEMA_SKILL_02_GRUNDBUCH` anhängen
6. Task-Status pollen bis `completed`
7. `grundbuch_risk_level` und `priority_risks` in Phase-2-Aggregation einbringen

## Manus API Prompt

```
Analysiere alle angehängten Grundbuchauszüge, Flurkarten und Teilungserklärungen
für eine Immobilien-Due-Diligence.

ABTEILUNG I (Eigentümer):
- Wer ist aktueller Eigentümer? Einzelperson, GbR, GmbH, Erbengemeinschaft?
- Gibt es mehrere Miteigentümer? Welche Quoten?
- Gibt es Eigentümerwechsel in den letzten 5 Jahren? Erbfälle?

ABTEILUNG II (Lasten und Beschränkungen):
- Auflassungsvormerkungen: Liegt eine zugunsten des aktuellen Käufers vor?
- Wegerechte, Leitungsrechte, Überfahrtrechte: Wer ist Berechtigter?
- Nießbrauchrechte: Wer ist Berechtigter? Ist dieser noch am Leben?
  (kritisch wertmindernd)
- Vorkaufsrechte: Gemeindliches oder privatrechtliches Vorkaufsrecht?
- Denkmalschutz-Vermerke
- Sanierungsvermerke / städtebauliche Gebote
- Erbbaurechte: Laufzeit, Erbbauzins, Heimfallklauseln

ABTEILUNG III (Grundpfandrechte):
- Grundschulden: Gläubiger, Betrag, Rang
- Hypotheken: Gläubiger, Betrag, Zinssatz, Restschuld (falls erkennbar)
- Gesamtbelastung durch Grundpfandrechte in EUR

FLURKARTE / TEILUNGSERKLÄRUNG:
- Grundstücksgröße in m²
- Bebauungsgrad, Bebauungsplan-Verweise
- Bei WEG: Miteigentumsanteile, Sondereigentumsabgrenzung, Gemeinschaftseigentum

Hebe alle Einträge hervor, die wertmindernd oder rechtlich riskant sind.
Markiere explizit: Nießbrauch, aktive Grundschulden über Verkehrswert,
fehlende Löschungsbewilligung nach Eigentumsübergang.
```

## Structured Output Schema (`SCHEMA_SKILL_02_GRUNDBUCH`)

```json
{
  "type": "object",
  "properties": {
    "ownership": {
      "type": "object",
      "properties": {
        "owner_name":       { "type": ["string", "null"] },
        "owner_type":       {
          "type": "string",
          "enum": ["Einzelperson", "GbR", "GmbH", "AG", "Erbengemeinschaft",
                   "Sonstige", "Unbekannt"]
        },
        "co_owners":        { "type": "array", "items": { "type": "string" } },
        "recent_transfers": { "type": "array", "items": { "type": "string" } },
        "ownership_notes":  { "type": "string" }
      },
      "required": ["owner_name", "owner_type", "co_owners", "recent_transfers",
                   "ownership_notes"],
      "additionalProperties": false
    },
    "encumbrances": {
      "type": "array",
      "items": {
        "type": "object",
        "properties": {
          "type":         { "type": "string" },
          "beneficiary":  { "type": "string" },
          "description":  { "type": "string" },
          "risk_level":   { "type": "string", "enum": ["Low", "Medium", "High", "Critical"] },
          "is_deletable": { "type": ["boolean", "null"] }
        },
        "required": ["type", "beneficiary", "description", "risk_level", "is_deletable"],
        "additionalProperties": false
      }
    },
    "mortgages": {
      "type": "array",
      "items": {
        "type": "object",
        "properties": {
          "creditor":   { "type": "string" },
          "amount_eur": { "type": ["number", "null"] },
          "rank":       { "type": "string" },
          "type":       { "type": "string", "enum": ["Grundschuld", "Hypothek", "Rentenschuld"] },
          "notes":      { "type": "string" }
        },
        "required": ["creditor", "amount_eur", "rank", "type", "notes"],
        "additionalProperties": false
      }
    },
    "total_mortgage_burden_eur": { "type": ["number", "null"] },
    "land_area_sqm":             { "type": ["number", "null"] },
    "priority_risks":            { "type": "array", "items": { "type": "string" } },
    "grundbuch_risk_level":      {
      "type": "string", "enum": ["Low", "Medium", "High", "Critical"]
    },
    "grundbuch_notes": { "type": "string" }
  },
  "required": ["ownership", "encumbrances", "mortgages", "total_mortgage_burden_eur",
               "land_area_sqm", "priority_risks", "grundbuch_risk_level",
               "grundbuch_notes"],
  "additionalProperties": false
}
```

## Implementierung in `manus_client.py`

See [../../src/manus_client.py](../../src/manus_client.py). Use `filter_by_type()` helper to filter file_ids to relevant document types before calling this skill.
