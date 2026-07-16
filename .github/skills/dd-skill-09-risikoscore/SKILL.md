---
name: dd-skill-09-risikoscore
description: 'Immobilien Due Diligence: Risikobewertung und Investment-Score. Use to aggregate all partial results from skills 1-8 into a holistic risk assessment, calculate investment score (0-100) with breakdown by category (location 20pts, financial 25pts, technical 20pts, legal 20pts, WEG 10pts, completeness 5pts), generate red flags list, strengths/weaknesses, and final recommendation (Kaufen/Nachverhandeln/Abstand nehmen). Runs after all phase-1 skills complete.'
argument-hint: 'JSON outputs from skills 01-08 as context'
---

# Skill 9: Risikobewertung und Investment-Score

## Zweck
Aggregiert alle Teilergebnisse der Skills 2–8 zu einer ganzheitlichen Risikobewertung. Berechnet den Investment-Score (0–100) nach gewichtetem Schema, leitet Stärken und Schwächen ab und formuliert die abschließende Investitionsempfehlung. Letzter Schritt vor der finalen Aggregation durch Skill 10.

## Skill-Steckbrief
- **Skill-Bezeichner:** `dd_skill_09_risikoscore`
- **Erforderliche Force Skills:** `financial_data_processing`, `data_analysis`
- **Input:** JSON-Outputs der Skills 1–8 als Kontext im Prompt
- **Parallele Ausführung:** Nein (benötigt alle vorigen Outputs)
- **Geschätzte Dauer:** 5–10 Minuten
- **Credits-Verbrauch:** ~55–140 Credits
- **Ausführungsbedingung:** Immer (Phase 2, nach Phase 1)

## Verwendung
Diesen Skill aufrufen wenn:
- Alle Phase-1-Skills (2–8) abgeschlossen sind
- Ein zusammenfassender Investment-Score berechnet werden soll
- Red Flags priorisiert aufgelistet werden sollen
- Eine finale Kaufempfehlung generiert werden soll

## Gewichtungsschema Investment-Score (0–100)

| Kategorie | Punkte | Quelle |
|-----------|--------|--------|
| Lage/Standort | 20 | Skill 7 |
| Wirtschaftlichkeit/KPIs | 25 | Skills 3, 4 |
| Substanz/Technik | 20 | Skill 5 |
| Rechtssicherheit | 20 | Skills 2, 8 |
| WEG/Verwaltung | 10 | Skill 6 |
| Dokumentenvollständigkeit | 5 | Skill 1 |

## Score-Klassifikation

| Score | Klassifikation |
|-------|---------------|
| 80–100 | Sehr starkes Investment |
| 60–79 | Solides Investment |
| 40–59 | Prueffall |
| 20–39 | Kritisch |
| 0–19 | Nicht empfehlenswert |

## Empfehlungslogik

- **Kaufen:** Score ≥ 70, kein Critical-Risiko, KPIs marktgerecht
- **Nachverhandeln:** Score 45–69 oder behebbare Risiken
- **Abstand nehmen:** Score < 45, Critical-Risiko oder fundamentale Datenlücken

## Procedure

1. Alle Phase-1-Outputs (Skills 1–8) als JSON-Strings im Prompt einbetten
2. Manus Task anlegen mit `force_skills: ["financial_data_processing", "data_analysis"]`
3. Prompt-Template (siehe unten) mit Skill-Outputs befüllen
4. `structured_output_schema: SCHEMA_SKILL_09_SCORE` anhängen
5. Task-Status pollen bis `completed`
6. Gesamtes Output-Objekt an Skill 10 weitergeben

## Manus API Prompt-Template

```
Du hast alle Teilergebnisse der Due-Diligence-Analyse vorliegen:

INVENTAR (Skill 1): {skill_01_output}
GRUNDBUCH (Skill 2): {skill_02_output}
MIETANALYSE (Skill 3): {skill_03_output}
FINANZKENNZAHLEN (Skill 4): {skill_04_output}
TECHNIK (Skill 5): {skill_05_output}
WEG (Skill 6): {skill_06_output}
STANDORT (Skill 7): {skill_07_output}
RECHT (Skill 8): {skill_08_output}

RISIKOBEWERTUNG — bewerte je Kategorie Low/Medium/High/Critical:
- Rechtlich (aus Skills 2, 8)
- Wirtschaftlich (aus Skills 3, 4)
- Technisch (aus Skill 5)
- Standort (aus Skill 7)
- Mietausfall (aus Skill 3)

Gesamtrisiko-Logik:
- Critical: mind. 1 Kategorie Critical
- High: mind. 2 Kategorien High ODER 1 High + 2 Medium
- Medium: mind. 1 Kategorie High
- Low: alle Kategorien Low oder Medium

INVESTMENT-SCORE (0–100) — Gewichtungsschema:
- Lage/Standort:             20 Punkte (Skill 7)
- Wirtschaftlichkeit/KPIs:   25 Punkte (Skills 3, 4)
- Substanz/Technik:          20 Punkte (Skill 5)
- Rechtssicherheit:          20 Punkte (Skills 2, 8)
- WEG/Verwaltung:            10 Punkte (Skill 6)
- Dokumentenvollständigkeit:  5 Punkte (Skill 1)

Klassifikation:
- 80–100: "Sehr starkes Investment"
- 60–79:  "Solides Investment"
- 40–59:  "Prueffall"
- 20–39:  "Kritisch"
-  0–19:  "Nicht empfehlenswert"

RED FLAGS: Liste alle kritischen Befunde, priorisiert nach Schweregrad.

STÄRKEN / SCHWÄCHEN: Je 3–7 konkrete Punkte.

EMPFEHLUNG:
- "Kaufen": Score ≥ 70, kein Critical-Risiko, KPIs marktgerecht
- "Nachverhandeln": Score 45–69 oder behebbare Risiken
- "Abstand nehmen": Score < 45, Critical-Risiko oder fundamentale Datenlücken

Begründe die Empfehlung in 3–5 Sätzen.
```

## Structured Output Schema (`SCHEMA_SKILL_09_SCORE`)

```json
{
  "type": "object",
  "properties": {
    "risk_assessment": {
      "type": "object",
      "properties": {
        "legal":          { "type": "string", "enum": ["Low", "Medium", "High", "Critical"] },
        "financial":      { "type": "string", "enum": ["Low", "Medium", "High", "Critical"] },
        "technical":      { "type": "string", "enum": ["Low", "Medium", "High", "Critical"] },
        "location":       { "type": "string", "enum": ["Low", "Medium", "High", "Critical"] },
        "tenant_default": { "type": "string", "enum": ["Low", "Medium", "High", "Critical"] }
      },
      "required": ["legal", "financial", "technical", "location", "tenant_default"],
      "additionalProperties": false
    },
    "overall_risk_level": { "type": "string", "enum": ["Low", "Medium", "High", "Critical"] },
    "red_flags": {
      "type": "array",
      "items": {
        "type": "object",
        "properties": {
          "category":        {
            "type": "string",
            "enum": ["Rechtlich", "Wirtschaftlich", "Technisch", "Umwelt"]
          },
          "description":     { "type": "string" },
          "severity":        { "type": "string", "enum": ["Critical", "High", "Medium", "Low"] },
          "source_document": { "type": "string" }
        },
        "required": ["category", "description", "severity", "source_document"],
        "additionalProperties": false
      }
    },
    "investment_score": {
      "type": "object",
      "properties": {
        "score":             { "type": "number" },
        "score_explanation": { "type": "string" },
        "classification":    {
          "type": "string",
          "enum": ["Sehr starkes Investment", "Solides Investment", "Prueffall",
                   "Kritisch", "Nicht empfehlenswert"]
        },
        "score_breakdown": {
          "type": "object",
          "properties": {
            "location_score":     { "type": "number" },
            "financial_score":    { "type": "number" },
            "technical_score":    { "type": "number" },
            "legal_score":        { "type": "number" },
            "weg_score":          { "type": "number" },
            "completeness_score": { "type": "number" }
          },
          "required": ["location_score", "financial_score", "technical_score",
                       "legal_score", "weg_score", "completeness_score"],
          "additionalProperties": false
        }
      },
      "required": ["score", "score_explanation", "classification", "score_breakdown"],
      "additionalProperties": false
    },
    "strengths":                { "type": "array", "items": { "type": "string" } },
    "weaknesses":               { "type": "array", "items": { "type": "string" } },
    "open_questions":           { "type": "array", "items": { "type": "string" } },
    "recommendation":           {
      "type": "string", "enum": ["Kaufen", "Nachverhandeln", "Abstand nehmen"]
    },
    "recommendation_reasoning": { "type": "string" }
  },
  "required": ["risk_assessment", "overall_risk_level", "red_flags", "investment_score",
               "strengths", "weaknesses", "open_questions", "recommendation",
               "recommendation_reasoning"],
  "additionalProperties": false
}
```
