---
name: dd-skill-06-weg
description: 'Immobilien Due Diligence: WEG-Analyse (Wohnungseigentümergemeinschaft). Use to analyze WEG meeting minutes and annual accounts for Hausgeld, maintenance reserve adequacy, planned special levies (Sonderumlagen), legal disputes within the WEG, planned major works, and property manager quality. Run in parallel after skill 1 sets run_weg_analysis=true.'
argument-hint: 'file_ids[] of WEG-Protokolle, Jahresabrechnungen, Wirtschaftspläne, Teilungserklärungen'
---

# Skill 6: WEG-Analyse und Eigentümergemeinschaft

## Zweck
Analysiert WEG-Protokolle und Jahresabrechnungen auf Hausgeld, Instandhaltungsrücklage, beschlossene Sonderumlagen, Rechtsstreitigkeiten innerhalb der WEG und geplante Großmaßnahmen. Bewertet ob beschlossene Maßnahmen den Käufer binden (§ 10 Abs. 4 WEG).

## Skill-Steckbrief
- **Skill-Bezeichner:** `dd_skill_06_weg`
- **Erforderliche Force Skills:** `advanced_document_extraction`, `financial_data_processing`, `legal_text_analysis`
- **Input:** `file_ids` aller WEG-Protokolle, Jahresabrechnungen, Wirtschaftspläne, Teilungserklärungen
- **Parallele Ausführung:** Ja
- **Geschätzte Dauer:** 5–12 Minuten
- **Credits-Verbrauch:** ~55–168 Credits
- **Ausführungsbedingung:** `skill_execution_flags.run_weg_analysis == true`

## Verwendung
Diesen Skill aufrufen wenn:
- WEG-Protokolle oder Jahresabrechnungen vorliegen
- Hausgeld und Instandhaltungsrücklage bewertet werden sollen
- Drohende Sonderumlagen identifiziert werden sollen
- WEG-Verwaltungsqualität eingeschätzt werden soll

## Procedure

1. Prüfe `skill_execution_flags.run_weg_analysis` aus Skill-1-Output
2. Filtere `file_ids` auf Typen: `WEG-Protokoll`, `WEG-Jahresabrechnung`, `Wirtschaftsplan`
3. Manus Task anlegen mit `force_skills: ["advanced_document_extraction", "financial_data_processing", "legal_text_analysis"]`
4. Prompt (siehe unten) senden
5. `structured_output_schema: SCHEMA_SKILL_06_WEG` anhängen
6. Task-Status pollen bis `completed`
7. `weg_risk_level` und `special_levies` an Skills 9+10 weitergeben

## Manus API Prompt

```
Analysiere alle WEG-Protokolle, Jahresabrechnungen und Wirtschaftspläne
für eine Immobilien-Due-Diligence.

WEG-PROTOKOLLE (analysiere alle vorliegenden, priorisiere letzte 3 Jahre):
- Datum und Teilnehmerquote jeder Eigentümerversammlung
- Alle gefassten Beschlüsse inkl. Abstimmungsergebnisse
- Geplante oder beschlossene Sanierungsmaßnahmen (Kosten, Zeitplan)
- Beschlossene oder drohende Sonderumlagen (Betrag pro MEA und absolut)
- Rechtsstreitigkeiten der WEG (laufende Klagen, Verfahren)
- Probleme mit einzelnen Eigentümern (Zahlungsausfälle, Beschlussmängelklagen)
- Hausverwalter: Name, seit wann, Vertragsende, Qualitätsbewertung aus Protokoll

WEG-JAHRESABRECHNUNG / WIRTSCHAFTSPLAN:
- Monatliches Hausgeld gesamt in EUR (für die betrachtete Einheit)
- Aufschlüsselung: Betriebskosten vs. Instandhaltungsrücklage
- Aktuelle Instandhaltungsrücklage der WEG gesamt in EUR
- Instandhaltungsrücklage pro m² Gesamtfläche
  (Richtwert: mind. 0,5–1% des Gebäudewerts/Jahr)
- Ist die Rücklage ausreichend für Baualter und Zustand?
- Rückstandsquote bei Hausgeld
- Nachzahlungen oder Gutschriften der letzten 3 Jahre?

RISIKOBEWERTUNG:
- Beschlossene Maßnahmen: bereits bezahlt oder noch ausstehend?
- Gibt es Beschlüsse, die für den Käufer bindend wären (§ 10 Abs. 4 WEG)?
- Drohen Sonderumlagen in den nächsten 2 Jahren?
```

## Structured Output Schema (`SCHEMA_SKILL_06_WEG`)

```json
{
  "type": "object",
  "properties": {
    "monthly_hausgeld_eur":          { "type": ["number", "null"] },
    "maintenance_reserve_total_eur": { "type": ["number", "null"] },
    "reserve_per_sqm_eur":           { "type": ["number", "null"] },
    "reserve_adequacy":              {
      "type": "string",
      "enum": ["ausreichend", "grenzwertig", "unzureichend", "kritisch", "unbekannt"]
    },
    "property_manager":     { "type": ["string", "null"] },
    "manager_contract_end": { "type": ["string", "null"] },
    "planned_measures": {
      "type": "array",
      "items": {
        "type": "object",
        "properties": {
          "description":        { "type": "string" },
          "decision_date":      { "type": ["string", "null"] },
          "estimated_cost_eur": { "type": ["number", "null"] },
          "buyer_impact":       { "type": "string" },
          "status":             {
            "type": "string",
            "enum": ["beschlossen", "geplant", "diskutiert", "abgeschlossen"]
          }
        },
        "required": ["description", "decision_date", "estimated_cost_eur",
                     "buyer_impact", "status"],
        "additionalProperties": false
      }
    },
    "special_levies": {
      "type": "array",
      "items": {
        "type": "object",
        "properties": {
          "description":      { "type": "string" },
          "amount_total_eur": { "type": ["number", "null"] },
          "amount_unit_eur":  { "type": ["number", "null"] },
          "due_date":         { "type": ["string", "null"] },
          "status":           {
            "type": "string",
            "enum": ["beschlossen", "drohend", "bezahlt"]
          }
        },
        "required": ["description", "amount_total_eur", "amount_unit_eur",
                     "due_date", "status"],
        "additionalProperties": false
      }
    },
    "legal_disputes":    { "type": "array", "items": { "type": "string" } },
    "arrears_situation": { "type": "string" },
    "weg_risk_level":    { "type": "string", "enum": ["Low", "Medium", "High", "Critical"] },
    "weg_notes":         { "type": "string" }
  },
  "required": ["monthly_hausgeld_eur", "maintenance_reserve_total_eur",
               "reserve_per_sqm_eur", "reserve_adequacy", "property_manager",
               "manager_contract_end", "planned_measures", "special_levies",
               "legal_disputes", "arrears_situation", "weg_risk_level", "weg_notes"],
  "additionalProperties": false
}
```
