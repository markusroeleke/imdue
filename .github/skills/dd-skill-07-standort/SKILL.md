---
name: dd-skill-07-standort
description: 'Immobilien Due Diligence: Standort- und Marktanalyse. Use to research location factors via web search: macro location (population trend, unemployment, purchasing power), micro location (public transport, schools, noise risks), real estate market data (Kaufpreis/m², Miete/m², vacancy rate), flood risk (ZÜRS zone), Milieuschutz, and location score 1-5. Always runs regardless of document completeness.'
argument-hint: 'property_address from skill_01_output, optional file_ids with Exposé'
---

# Skill 7: Standort- und Marktanalyse

## Zweck
Recherchiert Standortfaktoren, Infrastruktur, Bevölkerungsentwicklung, Leerstandsquoten und Mietpreisentwicklung am Standort via Websuche. Bewertet Makro- und Mikrolage (Score 1–5). Liefert Marktvergleichsdaten für Skill 4 (Finanzkennzahlen) und den Investment-Score in Skill 9.

## Skill-Steckbrief
- **Skill-Bezeichner:** `dd_skill_07_standort`
- **Erforderliche Force Skills:** `web_search`, `data_analysis`
- **Input:** Adresse/Standort (aus Skill-1-Output `property_address`), ggf. `file_ids` mit Lagebeschreibung aus Exposé
- **Parallele Ausführung:** Ja
- **Geschätzte Dauer:** 8–20 Minuten
- **Credits-Verbrauch:** ~88–280 Credits
- **Ausführungsbedingung:** Immer (kein Flag erforderlich)

## Verwendung
Diesen Skill immer aufrufen wenn:
- Eine neue Due-Diligence-Analyse gestartet wird
- Standortbewertung und Marktvergleich benötigt werden
- Hochwasserrisiko, Milieuschutz oder Altlastenrisiko geprüft werden sollen
- Bevölkerungstrend und Wirtschaftsdaten des Standorts benötigt werden

## Procedure

1. `property_address` aus Skill-1-Output extrahieren
2. Manus Task anlegen mit `force_skills: ["web_search", "data_analysis"]`
3. Prompt (siehe unten) senden, Adresse als primären Input übergeben
4. `structured_output_schema: SCHEMA_SKILL_07_STANDORT` anhängen
5. Task-Status pollen bis `completed`
6. `macro_location_score`, `micro_location_score` und `location_risk_level` an Skill 9 weitergeben
7. `market_price_per_sqm_eur` und `market_rent_per_sqm_eur` an Skill 4 weitergeben (falls Skill 4 noch läuft)

## Manus API Prompt

```
Führe eine umfassende Standort- und Marktanalyse für die Immobilie durch.
Nutze aktuelle Websuche für alle Daten. Gib Quellen und Recherche-Datum an.

MAKROLAGE (Stadt / Region):
- Bundesland, Stadtgröße (Einwohner)
- Bevölkerungsentwicklung der letzten 5 Jahre und Prognose
- Arbeitslosenquote (aktuell, Trend)
- BIP-Entwicklung und größte Arbeitgeber
- Kaufkraftindex
- IW-Wohnungsmarktatlas oder ähnliche Ratings

MIKROLAGE (Stadtteil / Adresse):
- Stadtteil-Charakteristik (Wohngebiet, Mischgebiet, Gewerbe, aufwertend/abwertend)
- Öffentlicher Nahverkehr: Nächste U-/S-Bahn/Bus (Fußweg in Minuten)
- Schulen, Kitas, Supermärkte in der Nähe
- Bekannte Problemzonen (Lärmbelastung, Kriminalität, Industrienähe)
- Bebauungsplan: Störende Neubauten oder Gewerbeansiedlungen geplant?

IMMOBILIENMARKT AM STANDORT:
- Aktueller durchschnittlicher Kaufpreis pro m² vergleichbarer Objekte
- Mietpreis pro m² für vergleichbare Einheiten
- Mietpreisentwicklung der letzten 3 Jahre in %
- Leerstandsquote am Standort
- Markteinordnung des Objekts: über- oder unterbewertet?

RISIKOFAKTOREN:
- Hochwasserrisiko (ZÜRS-Zone)
- Altlasten-Risiko (bekannte Industriestandorte in der Umgebung)
- Milieuschutzgebiet / Mietendeckel-Diskussionen

Bewerte Makrolage (1–5) und Mikrolage (1–5) mit Begründung.
```

## Structured Output Schema (`SCHEMA_SKILL_07_STANDORT`)

```json
{
  "type": "object",
  "properties": {
    "city":                    { "type": ["string", "null"] },
    "district":                { "type": ["string", "null"] },
    "macro_location_score":    { "type": ["integer", "null"] },
    "micro_location_score":    { "type": ["integer", "null"] },
    "population_trend":        {
      "type": "string",
      "enum": ["stark_wachsend", "wachsend", "stabil", "leicht_ruecklaeufig",
               "ruecklaeufig", "unbekannt"]
    },
    "unemployment_rate_pct":    { "type": ["number", "null"] },
    "public_transport_minutes": { "type": ["integer", "null"] },
    "infrastructure_notes":     { "type": "string" },
    "market_rent_per_sqm_eur":  { "type": ["number", "null"] },
    "market_price_per_sqm_eur": { "type": ["number", "null"] },
    "rent_trend_3y_pct":        { "type": ["number", "null"] },
    "vacancy_rate_market_pct":  { "type": ["number", "null"] },
    "flood_risk_zone":          { "type": ["string", "null"] },
    "contamination_risk":       {
      "type": "string", "enum": ["niedrig", "mittel", "hoch", "unbekannt"]
    },
    "milieuschutz":        { "type": "boolean" },
    "risk_factors":        { "type": "array", "items": { "type": "string" } },
    "location_strengths":  { "type": "array", "items": { "type": "string" } },
    "location_risk_level": {
      "type": "string", "enum": ["Low", "Medium", "High", "Critical"]
    },
    "location_notes": { "type": "string" },
    "data_sources":   { "type": "array", "items": { "type": "string" } }
  },
  "required": ["city", "district", "macro_location_score", "micro_location_score",
               "population_trend", "unemployment_rate_pct", "public_transport_minutes",
               "infrastructure_notes", "market_rent_per_sqm_eur",
               "market_price_per_sqm_eur", "rent_trend_3y_pct",
               "vacancy_rate_market_pct", "flood_risk_zone", "contamination_risk",
               "milieuschutz", "risk_factors", "location_strengths",
               "location_risk_level", "location_notes", "data_sources"],
  "additionalProperties": false
}
```
