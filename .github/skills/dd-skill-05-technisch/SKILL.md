---
name: dd-skill-05-technisch
description: 'Immobilien Due Diligence: Technische und bauliche Prüfung. Use to analyze technical reports, energy certificates (Energieausweis), and floor plans for building defects, maintenance backlog (Instandhaltungsrückstau), energy efficiency class, GEG compliance requirements, and investment cost estimates (short/mid/long term). Run in parallel after skill 1 sets run_technical_analysis=true.'
argument-hint: 'file_ids[] of Gutachten, Energieausweis, Grundrisse, Baupläne'
---

# Skill 5: Technische und bauliche Prüfung

## Zweck
Analysiert technische Gutachten, Energieausweis und Grundrisse auf Baumängel, Instandhaltungsrückstau, Energiezustand und notwendige Sanierungsmaßnahmen gemäß GEG. Schätzt Kostenrahmen für Sofort-, Mittel- und Langfristmaßnahmen.

## Skill-Steckbrief
- **Skill-Bezeichner:** `dd_skill_05_technisch`
- **Erforderliche Force Skills:** `advanced_document_extraction`, `image_analysis`, `web_search`
- **Input:** `file_ids` aller technischen Gutachten, Energieausweise, Grundrisse, Baupläne
- **Parallele Ausführung:** Ja
- **Geschätzte Dauer:** 5–12 Minuten
- **Credits-Verbrauch:** ~55–168 Credits
- **Ausführungsbedingung:** `skill_execution_flags.run_technical_analysis == true`

## Verwendung
Diesen Skill aufrufen wenn:
- Technische Gutachten oder Energieausweis vorliegen
- Sanierungsbedarf und Investitionskosten ermittelt werden sollen
- GEG-Konformität und Energieeffizienzklasse bewertet werden sollen
- Baumängel und Instandhaltungsrückstau quantifiziert werden sollen

## Procedure

1. Prüfe `skill_execution_flags.run_technical_analysis` aus Skill-1-Output
2. Filtere `file_ids` auf Typen: `Energieausweis`, `Technisches Gutachten`, `Bauplan/Grundriss`
3. Manus Task anlegen mit `force_skills: ["advanced_document_extraction", "image_analysis", "web_search"]`
4. Prompt (siehe unten) senden
5. `structured_output_schema: SCHEMA_SKILL_05_TECHNIK` anhängen
6. Task-Status pollen bis `completed`
7. `technical_risk_level` und `investment_needs.total_max_eur` an Skills 9+10 weitergeben

## Manus API Prompt

```
Analysiere alle technischen Unterlagen (Gutachten, Energieausweis, Grundrisse,
Baupläne) für eine Immobilien-Due-Diligence.

ENERGIEAUSWEIS:
- Energieeffizienzklasse (A+ bis H)
- Primärenergiebedarf / Endenergiebedarf in kWh/(m²·a)
- Energieträger (Gas, Öl, Fernwärme, Wärmepumpe, ...)
- Baujahr der Heizungsanlage
- Empfohlene Modernisierungsmaßnahmen gemäß Energieausweis
- GEG-Konformität: Welche Maßnahmen sind bis 2035/2045 vorgeschrieben?

TECHNISCHES GUTACHTEN / BAUZUSTAND:
- Baujahr des Gebäudes, letzte Sanierungen
- Baumängel: Liste jeden Mangel mit Schweregrad (kritisch/hoch/mittel/gering)
- Instandhaltungsrückstau: geschätzter Gesamtbetrag in EUR
- Dach: Zustand, Alter, Sanierungsbedarf
- Fassade: Zustand, Wärmedämmung, Sanierungsbedarf
- Fenster: Zustand, Verglasung, Sanierungsbedarf
- Heizung: System, Alter, Zustand
- Elektrik: Zustand, Alter der Hauptleitungen
- Sanitär/Rohrleitungen: Material (Kupfer/Blei/Kunststoff), Zustand
- Keller/Fundament: Feuchtigkeitsschäden, Schimmel
- Aufzug (falls vorhanden): Alter, TÜV-Status

GRUNDRISSE:
- Wohnflächen nach WoFlV plausibel?
- Nutzungsänderungspotenzial (Dachausbau, Kellererweiterung)
- Barrierefreiheit

KOSTENSCHÄTZUNG:
- Kurzfristig notwendige Maßnahmen (0–2 Jahre): min./max. EUR
- Mittelfristige Maßnahmen (2–5 Jahre): min./max. EUR
- Langfristige Maßnahmen (5–15 Jahre): min./max. EUR
- Gesamtinvestitionsbedarf: min. / max. in EUR
```

## Structured Output Schema (`SCHEMA_SKILL_05_TECHNIK`)

```json
{
  "type": "object",
  "properties": {
    "building_year":         { "type": ["integer", "null"] },
    "last_major_renovation": { "type": ["string", "null"] },
    "energy_certificate": {
      "type": "object",
      "properties": {
        "efficiency_class":     { "type": ["string", "null"] },
        "primary_energy_kwh":   { "type": ["number", "null"] },
        "energy_carrier":       { "type": ["string", "null"] },
        "heating_system_year":  { "type": ["integer", "null"] },
        "mandatory_upgrades":   { "type": "array", "items": { "type": "string" } },
        "geg_compliance_notes": { "type": "string" }
      },
      "required": ["efficiency_class", "primary_energy_kwh", "energy_carrier",
                   "heating_system_year", "mandatory_upgrades", "geg_compliance_notes"],
      "additionalProperties": false
    },
    "defects": {
      "type": "array",
      "items": {
        "type": "object",
        "properties": {
          "component":         { "type": "string" },
          "description":       { "type": "string" },
          "severity":          { "type": "string", "enum": ["kritisch", "hoch", "mittel", "gering"] },
          "cost_estimate_eur": { "type": ["number", "null"] }
        },
        "required": ["component", "description", "severity", "cost_estimate_eur"],
        "additionalProperties": false
      }
    },
    "investment_needs": {
      "type": "object",
      "properties": {
        "short_term_eur_min": { "type": ["number", "null"] },
        "short_term_eur_max": { "type": ["number", "null"] },
        "mid_term_eur_min":   { "type": ["number", "null"] },
        "mid_term_eur_max":   { "type": ["number", "null"] },
        "long_term_eur_min":  { "type": ["number", "null"] },
        "long_term_eur_max":  { "type": ["number", "null"] },
        "total_min_eur":      { "type": ["number", "null"] },
        "total_max_eur":      { "type": ["number", "null"] }
      },
      "required": ["short_term_eur_min", "short_term_eur_max", "mid_term_eur_min",
                   "mid_term_eur_max", "long_term_eur_min", "long_term_eur_max",
                   "total_min_eur", "total_max_eur"],
      "additionalProperties": false
    },
    "maintenance_backlog_notes": { "type": "string" },
    "upside_potential_notes":    { "type": "string" },
    "technical_risk_level":      {
      "type": "string", "enum": ["Low", "Medium", "High", "Critical"]
    },
    "technical_notes": { "type": "string" }
  },
  "required": ["building_year", "last_major_renovation", "energy_certificate",
               "defects", "investment_needs", "maintenance_backlog_notes",
               "upside_potential_notes", "technical_risk_level", "technical_notes"],
  "additionalProperties": false
}
```
