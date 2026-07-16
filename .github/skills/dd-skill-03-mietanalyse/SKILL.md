---
name: dd-skill-03-mietanalyse
description: 'Immobilien Due Diligence: Mietvertrags- und Mieteranalyse. Use to extract and analyze all rental contracts and tenant lists: rent levels, contract terms, index clauses, special termination rights, vacancy risk, and annual rental income (actual vs. market). Run in parallel after skill 1 sets run_mietvertrag_analysis=true.'
argument-hint: 'file_ids[] of Mietverträge, Mieterlisten, Nachträge'
---

# Skill 3: Mietvertrags- und Mieteranalyse

## Zweck
Extrahiert und analysiert alle Mietverträge und Mieterlisten. Prüft Miethöhen, Laufzeiten, Indexierungsklauseln, Sonderkündigungsrechte und Mietausfallrisiken. Berechnet aktuelle und potenzielle Jahresmieteinnahmen. Outputs werden von Skill 4 (Finanzkennzahlen) und Skill 9 (Risikoscore) weiterverwendet.

## Skill-Steckbrief
- **Skill-Bezeichner:** `dd_skill_03_mietanalyse`
- **Erforderliche Force Skills:** `advanced_document_extraction`, `financial_data_processing`, `legal_text_analysis`
- **Input:** `file_ids` aller Mietverträge, Mieterlisten, Nachträge
- **Parallele Ausführung:** Ja (parallel zu Skills 2, 4–8)
- **Geschätzte Dauer:** 8–20 Minuten
- **Credits-Verbrauch:** ~88–280 Credits
- **Ausführungsbedingung:** `skill_execution_flags.run_mietvertrag_analysis == true`

## Verwendung
Diesen Skill aufrufen wenn:
- Mietverträge oder Mieterlisten hochgeladen wurden
- Mietrendite und Leerstandsquote berechnet werden sollen
- Mietrechtliche Klauseln auf Gültigkeit geprüft werden sollen (BGH-Rechtsprechung)

## Procedure

1. Prüfe `skill_execution_flags.run_mietvertrag_analysis` aus Skill-1-Output
2. Filtere `file_ids` auf Typen: `Mietvertrag`, `Mieterliste`
3. Manus Task anlegen mit `force_skills: ["advanced_document_extraction", "financial_data_processing", "legal_text_analysis"]`
4. Prompt (siehe unten) senden
5. `structured_output_schema: SCHEMA_SKILL_03_MIETE` anhängen
6. Task-Status pollen bis `completed`
7. `current_rent_annual_eur` und `overall_lease_risk` an Skill 4 und Skill 9 weitergeben

## Manus API Prompt

```
Analysiere alle angehängten Mietverträge, Nachträge und Mieterlisten vollständig.

Für JEDEN Mietvertrag / jede Einheit extrahiere:

VERTRAGSPARTEIEN & OBJEKT:
- Mieter (Name, Typ: Privat/Gewerbe/Sozialeinrichtung)
- Gemietete Einheit (Wohnung Nr., Etage, Typ, Fläche m²)
- Vertragsbeginn und -ende (oder unbefristet)

MIETE & KOSTEN:
- Aktuelle monatliche Kaltmiete in EUR
- Monatliche Nebenkosten/Vorauszahlung in EUR
- Letzte Mieterhöhung: Datum und Betrag

KLAUSELN & BESONDERHEITEN:
- Indexmietklausel: Ja/Nein, verknüpfter Index (VPI), letzter Anpassungstermin
- Staffelmietklausel: Ja/Nein, nächste Stufe
- Sonderkündigungsrechte des Mieters
- Modernisierungsklauseln (§ 555b BGB)
- Konkurrenzschutzklauseln (Gewerbe)
- Schönheitsreparaturklauseln (prüfen ob wirksam nach aktueller BGH-Rechtsprechung)

RISIKOBEWERTUNG PRO MIETER:
- Mietausfall-Risiko (Low/Medium/High/Critical)
- Begründung: Mietdauer, Bonität (falls erkennbar), Leerstandsindikator

AGGREGATION:
- Gesamte Jahreskaltmiete (IST) in EUR
- Geschätzte marktübliche Jahreskaltmiete (SOLL) in EUR
- Leerstandsquote in % (falls erkennbar)
- Anzahl Einheiten gesamt / vermietet / leer
```

## Structured Output Schema (`SCHEMA_SKILL_03_MIETE`)

```json
{
  "type": "object",
  "properties": {
    "rental_units": {
      "type": "array",
      "items": {
        "type": "object",
        "properties": {
          "unit_id":               { "type": "string" },
          "tenant_name":           { "type": ["string", "null"] },
          "tenant_type":           {
            "type": "string",
            "enum": ["Privat", "Gewerbe", "Sozialeinrichtung", "Leer", "Unbekannt"]
          },
          "area_sqm":              { "type": ["number", "null"] },
          "contract_start":        { "type": ["string", "null"] },
          "contract_end":          { "type": ["string", "null"] },
          "is_indefinite":         { "type": "boolean" },
          "net_rent_monthly_eur":  { "type": ["number", "null"] },
          "ancillary_costs_eur":   { "type": ["number", "null"] },
          "last_rent_increase":    { "type": ["string", "null"] },
          "index_rent_clause":     { "type": "boolean" },
          "graduated_rent_clause": { "type": "boolean" },
          "next_rent_adjustment":  { "type": ["string", "null"] },
          "special_clauses":       { "type": "array", "items": { "type": "string" } },
          "problematic_clauses":   { "type": "array", "items": { "type": "string" } },
          "tenant_default_risk":   {
            "type": "string", "enum": ["Low", "Medium", "High", "Critical"]
          },
          "unit_notes": { "type": "string" }
        },
        "required": ["unit_id", "tenant_name", "tenant_type", "area_sqm",
                     "contract_start", "contract_end", "is_indefinite",
                     "net_rent_monthly_eur", "ancillary_costs_eur",
                     "last_rent_increase", "index_rent_clause",
                     "graduated_rent_clause", "next_rent_adjustment",
                     "special_clauses", "problematic_clauses",
                     "tenant_default_risk", "unit_notes"],
        "additionalProperties": false
      }
    },
    "total_units":                      { "type": "integer" },
    "occupied_units":                   { "type": "integer" },
    "vacancy_count":                    { "type": "integer" },
    "vacancy_rate_percent":             { "type": ["number", "null"] },
    "current_rent_annual_eur":          { "type": ["number", "null"] },
    "estimated_market_rent_annual_eur": { "type": ["number", "null"] },
    "rent_potential_delta_eur":         { "type": ["number", "null"] },
    "overall_lease_risk":               {
      "type": "string", "enum": ["Low", "Medium", "High", "Critical"]
    },
    "key_findings":      { "type": "array", "items": { "type": "string" } },
    "mietanalyse_notes": { "type": "string" }
  },
  "required": ["rental_units", "total_units", "occupied_units", "vacancy_count",
               "vacancy_rate_percent", "current_rent_annual_eur",
               "estimated_market_rent_annual_eur", "rent_potential_delta_eur",
               "overall_lease_risk", "key_findings", "mietanalyse_notes"],
  "additionalProperties": false
}
```
