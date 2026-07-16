---
name: dd-skill-04-finanzkennzahlen
description: 'Immobilien Due Diligence: Wirtschaftliche Kennzahlenberechnung (KPIs). Use to calculate all financial KPIs: Kaufpreisfaktor, Brutto-/Nettomietrendite, Cashflow pre/post financing, operating cost ratio, break-even occupancy, sensitivity scenarios, and web-based market comparison. Run in parallel after skill 1 sets run_financial_analysis=true.'
argument-hint: 'file_ids[] (Exposé, Mieterliste) and skill_03_output JSON'
---

# Skill 4: Wirtschaftliche Kennzahlenberechnung

## Zweck
Berechnet alle wirtschaftlichen KPIs auf Basis von Exposé-Daten, Mieterliste und Marktrecherche. Führt eine Sensitivitätsanalyse (Basis/Positiv/Negativ-Szenarien) und Cashflow-Modellierung durch. Liefert die Kernzahlen für den Investitions-Score in Skill 9.

## Skill-Steckbrief
- **Skill-Bezeichner:** `dd_skill_04_finanzkennzahlen`
- **Erforderliche Force Skills:** `financial_data_processing`, `web_search`, `advanced_document_extraction`
- **Input:** `file_ids` (Exposé, Mieterliste), Skill-3-Output (Mieteinnahmen)
- **Parallele Ausführung:** Ja
- **Geschätzte Dauer:** 6–15 Minuten
- **Credits-Verbrauch:** ~66–210 Credits
- **Ausführungsbedingung:** `skill_execution_flags.run_financial_analysis == true`

## Verwendung
Diesen Skill aufrufen wenn:
- Kaufpreis und Mietdaten vorliegen
- Renditekennzahlen berechnet werden sollen
- Marktvergleich (Preis/m² und Miete/m²) benötigt wird
- Cashflow-Szenarien modelliert werden sollen

## Procedure

1. Prüfe `skill_execution_flags.run_financial_analysis` aus Skill-1-Output
2. Skill-3-Output (`current_rent_annual_eur`) als Kontext einbinden
3. Manus Task anlegen mit `force_skills: ["financial_data_processing", "web_search", "advanced_document_extraction"]`
4. Prompt (siehe unten) senden mit allen `file_ids`
5. `structured_output_schema: SCHEMA_SKILL_04_FINANZEN` anhängen
6. Task-Status pollen bis `completed`
7. `financial_risk_level`, `net_yield_percent`, `cashflow_post_financing_eur` an Skill 9 weitergeben

## Manus API Prompt

```
Berechne alle wirtschaftlichen Kennzahlen für die Due-Diligence-Analyse.

DATENBASIS:
- Kaufpreis (aus Exposé oder Kaufvertragsentwurf)
- Wohnfläche / Nutzfläche in m²
- Aktuelle Jahreskaltmiete (aus Mieterliste/Mietverträgen)
- Nicht umlagefähige Bewirtschaftungskosten (Branchenstandard: ~20–25% der Kaltmiete,
  falls nicht angegeben)

BERECHNE:

BASISWERTE:
- Kaufpreis pro m² = Kaufpreis / Wohnfläche
- Kaufpreisfaktor = Kaufpreis / Jahresnettokaltmiete (IST)
- Bruttomietrendite = (Jahresnettokaltmiete / Kaufpreis) × 100
- Nettomietrendite = ((Jahresnettokaltmiete - Bewirtschaftungskosten)
  / (Kaufpreis + Nebenkosten)) × 100
  Nebenkosten-Schätzung: GrESt (je nach Bundesland 3,5–6,5%),
  Notar/Grundbuch (~2%), Makler (0–3,57%)

CASHFLOW-MODELLIERUNG:
- Cashflow vor Finanzierung = Jahresnettokaltmiete
  - Nicht-umlagefähige Kosten - Instandhaltungsrücklage
  (Instandhaltung: €10–15/m²/Jahr Altbau, €5–8/m²/Jahr Neubau)
- Cashflow nach Finanzierung
  (bei 70% Fremdfinanzierung, 3,5% Zinsen, 30 Jahre)
- Betriebskostenquote = Bewirtschaftungskosten / Jahresnettokaltmiete × 100
- Break-even-Vermietungsquote

SENSITIVITÄTSANALYSE:
- Szenario Basis: aktuelle Miete, aktuelle Kosten
- Szenario Positiv: +5% Miete, −10% Kosten
- Szenario Negativ: −10% Leerstand, +10% Kosten

MARKTVERGLEICH (via Webrecherche):
- Kaufpreis pro m² für vergleichbare Objekte am Standort
- Aktuelle Durchschnittsmiete pro m² am Standort
- Einordnung: Objekt über- oder unterbewertet?

Markiere klar, welche Werte exakt berechnet und welche geschätzt sind.
```

## Structured Output Schema (`SCHEMA_SKILL_04_FINANZEN`)

```json
{
  "type": "object",
  "properties": {
    "purchase_price_eur":             { "type": ["number", "null"] },
    "total_area_sqm":                 { "type": ["number", "null"] },
    "price_per_sqm_eur":              { "type": ["number", "null"] },
    "market_price_per_sqm_eur":       { "type": ["number", "null"] },
    "price_vs_market_percent":        { "type": ["number", "null"] },
    "current_rent_annual_eur":        { "type": ["number", "null"] },
    "potential_rent_annual_eur":      { "type": ["number", "null"] },
    "rent_multiplier":                { "type": ["number", "null"] },
    "gross_yield_percent":            { "type": ["number", "null"] },
    "net_yield_percent":              { "type": ["number", "null"] },
    "acquisition_costs_total_eur":    { "type": ["number", "null"] },
    "operating_costs_annual_eur":     { "type": ["number", "null"] },
    "maintenance_reserve_annual_eur": { "type": ["number", "null"] },
    "cashflow_pre_financing_eur":     { "type": ["number", "null"] },
    "cashflow_post_financing_eur":    { "type": ["number", "null"] },
    "operating_cost_ratio_percent":   { "type": ["number", "null"] },
    "break_even_occupancy_percent":   { "type": ["number", "null"] },
    "sensitivity_scenarios": {
      "type": "object",
      "properties": {
        "base_case_cashflow_eur":   { "type": ["number", "null"] },
        "optimistic_cashflow_eur":  { "type": ["number", "null"] },
        "pessimistic_cashflow_eur": { "type": ["number", "null"] },
        "sensitivity_notes":        { "type": "string" }
      },
      "required": ["base_case_cashflow_eur", "optimistic_cashflow_eur",
                   "pessimistic_cashflow_eur", "sensitivity_notes"],
      "additionalProperties": false
    },
    "reserve_need_notes":          { "type": "string" },
    "assumptions_and_limitations": { "type": "string" },
    "financial_risk_level":        {
      "type": "string", "enum": ["Low", "Medium", "High", "Critical"]
    }
  },
  "required": ["purchase_price_eur", "total_area_sqm", "price_per_sqm_eur",
               "market_price_per_sqm_eur", "price_vs_market_percent",
               "current_rent_annual_eur", "potential_rent_annual_eur",
               "rent_multiplier", "gross_yield_percent", "net_yield_percent",
               "acquisition_costs_total_eur", "operating_costs_annual_eur",
               "maintenance_reserve_annual_eur", "cashflow_pre_financing_eur",
               "cashflow_post_financing_eur", "operating_cost_ratio_percent",
               "break_even_occupancy_percent", "sensitivity_scenarios",
               "reserve_need_notes", "assumptions_and_limitations",
               "financial_risk_level"],
  "additionalProperties": false
}
```
