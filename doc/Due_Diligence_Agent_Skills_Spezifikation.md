# Agent Skills Spezifikation: Immobilien Due Diligence

**Autor:** Manus AI  
**Version:** 2.0  
**Datum:** 30. Juni 2026

---

## Inhaltsverzeichnis

1. [Einleitung](#1-einleitung)
2. [Das Projekt- und Skill-Konzept der Manus API](#2-das-projekt--und-skill-konzept-der-manus-api)
3. [Die Due-Diligence-Persona (Projekt-Instruktion)](#3-die-due-diligence-persona-projekt-instruktion)
4. [Gesamt-Workflow-Übersicht](#4-gesamt-workflow-übersicht)
5. [Skill 1: Dokument-Inventarisierung und Vollständigkeitsprüfung](#5-skill-1-dokument-inventarisierung-und-vollständigkeitsprüfung)
6. [Skill 2: Grundbuch- und Eigentumsanalyse](#6-skill-2-grundbuch--und-eigentumsanalyse)
7. [Skill 3: Mietvertrags- und Mieteranalyse](#7-skill-3-mietvertrags--und-mieteranalyse)
8. [Skill 4: Wirtschaftliche Kennzahlenberechnung](#8-skill-4-wirtschaftliche-kennzahlenberechnung)
9. [Skill 5: Technische und bauliche Prüfung](#9-skill-5-technische-und-bauliche-prüfung)
10. [Skill 6: WEG-Analyse und Eigentümergemeinschaft](#10-skill-6-weg-analyse-und-eigentümergemeinschaft)
11. [Skill 7: Standort- und Marktanalyse](#11-skill-7-standort--und-marktanalyse)
12. [Skill 8: Rechtliche Risikoprüfung](#12-skill-8-rechtliche-risikoprüfung)
13. [Skill 9: Risikobewertung und Investment-Score](#13-skill-9-risikobewertung-und-investment-score)
14. [Skill 10: Gesamt-Workflow-Orchestrierung](#14-skill-10-gesamt-workflow-orchestrierung)
15. [Gesamt-Structured-Output-Schema](#15-gesamt-structured-output-schema)
16. [Multi-Turn-Interaktion (Chat-Nachfragen)](#16-multi-turn-interaktion-chat-nachfragen)
17. [Implementierungshinweise für den Python-Client](#17-implementierungshinweise-für-den-python-client)
18. [Referenzen](#18-referenzen)

---

## 1. Einleitung

Dieses Dokument spezifiziert die vollständige Orchestrierung der KI-Intelligenz für die Immobilien-Due-Diligence-WebApp über die **Manus API**. Es definiert den **mehrstufigen Analyse-Workflow** mit dedizierten Skills für jeden Teilschritt sowie einen übergeordneten **Gesamt-Workflow-Skill (Skill 10)**, der alle Teilschritte koordiniert.

Die Architektur folgt dem Prinzip der **Skill-Komposition**: Jeder Teilschritt (Skill 1–9) ist ein eigenständiger, abgeschlossener Manus-Task mit spezifischen Force Skills und einem eigenen Structured Output Schema. Der Gesamt-Workflow-Skill (Skill 10) aggregiert alle Teilergebnisse und erzeugt das finale, berichtsreife Ergebnisobjekt.

### Kernprinzipien

| Prinzip | Beschreibung |
| :--- | :--- |
| **Separation of Concerns** | Jeder Skill hat genau eine Verantwortung und liefert ein klar definiertes Teilergebnis. |
| **Fail-Fast** | Skill 1 (Vollständigkeitsprüfung) erkennt sofort fehlende Kerndokumente, bevor teure Folge-Tasks gestartet werden. |
| **Parallelisierbarkeit** | Skills 2–8 sind voneinander unabhängig und können parallel ausgeführt werden (sofern das Rate-Limit dies erlaubt). |
| **Schema-Validierung** | Jeder Skill liefert validiertes JSON mit `additionalProperties: false`. |
| **Kosten-Kontrolle** | Skills werden nur für vorhandene Dokumententypen gestartet (bedingte Ausführung durch Skill 1 gesteuert). |

---

## 2. Das Projekt- und Skill-Konzept der Manus API

Die Manus API bietet drei wesentliche Mechanismen zur Steuerung der KI:

1. **Projects (`project_id`):** Über `POST /v2/project.create` wird ein Projekt mit einer dauerhaften `instruction` angelegt. Alle Tasks, die in diesem Projekt erstellt werden, erben diese Basis-Instruktion automatisch [2]. Dies ist ideal für die Definition der "Due-Diligence-Persona".
2. **Force Skills (`message.force_skills`):** Spezifische Fähigkeiten der KI können erzwungen werden, um sicherzustellen, dass bestimmte Werkzeuge (z.B. komplexe Dokumentenextraktion oder Websuche nach Vergleichsmieten) genutzt werden [3].
3. **Structured Output (`structured_output_schema`):** Ein "Arm once, fire once"-Mechanismus, der nach Abschluss des Tasks garantiert ein maschinenlesbares JSON gemäß einem strikten Schema liefert [4].

---

## 3. Die Due-Diligence-Persona (Projekt-Instruktion)

Um API-Kosten zu sparen und den Code sauber zu halten, wird beim initialen Setup ein Manus-Projekt angelegt. Alle nachfolgenden Tasks (Skills 1–10) erben diese Persona automatisch.

**API Call:** `POST /v2/project.create`

**Payload:**
```json
{
  "name": "Immobilien Due Diligence Analyse",
  "instruction": "Du bist ein hochqualifizierter Senior Real Estate Analyst und Due-Diligence-Experte für den deutschsprachigen Immobilienmarkt. Deine Aufgabe ist es, komplexe Maklerunterlagen (Exposés, Grundbuchauszüge, Mietverträge, Teilungserklärungen, Gutachten) präzise zu analysieren. Du arbeitest extrem akkurat, übersiehst keine rechtlichen Fallstricke (z.B. Dienstbarkeiten, Wegerechte, Indexmietklauseln) und bewertest wirtschaftliche Risiken (z.B. Leerstand, Instandhaltungsrückstau) objektiv. Wenn Informationen fehlen, erfindest du nichts, sondern listest diese als 'Offene Fragen' auf. Du denkst wie ein konservativer Investor, markierst Widersprüche und lieferst klare, handlungsweisende Einschätzungen."
}
```

**Antwort:** enthält `project_id` (z.B. `proj_abc123`), die in `.env` als `MANUS_PROJECT_ID` gespeichert wird.

---

## 4. Gesamt-Workflow-Übersicht

```
┌─────────────────────────────────────────────────────────────────────┐
│  NUTZER: Dokumente hochladen (Exposé, Grundbuch, Mietverträge, …)  │
└──────────────────────────┬──────────────────────────────────────────┘
                           │  file_ids[]
                           ▼
┌─────────────────────────────────────────────────────────────────────┐
│  SKILL 1: Dokument-Inventarisierung & Vollständigkeitsprüfung      │
│  → Welche Dokumente liegen vor? Was fehlt?                         │
│  → Ausgabe: doc_inventory (steuert bedingte Ausführung)            │
└──────────────────────────┬──────────────────────────────────────────┘
                           │  doc_inventory
          ┌────────────────┼─────────────────────────────┐
          ▼                ▼                             ▼
┌──────────────┐  ┌─────────────────┐  ┌───────────────────────────┐
│  SKILL 2    │  │    SKILL 3      │  │         SKILL 4           │
│  Grundbuch- │  │ Mietvertrags-   │  │  Wirtschaftliche KPIs     │
│  Eigentums- │  │ u. Mieter-      │  │  u. Cashflow-Berechnung   │
│  analyse    │  │ analyse         │  │                           │
└──────┬───────┘  └────────┬────────┘  └─────────────┬─────────────┘
       │                  │                          │
       │   ┌──────────────┼──────────────────────┐  │
       │   ▼              ▼                      ▼  │
       │ ┌──────────┐  ┌──────────┐  ┌──────────────┐│
       │ │ SKILL 5  │  │ SKILL 6  │  │   SKILL 7   ││
       │ │Technisch │  │  WEG-    │  │  Standort-  ││
       │ │ & Bau    │  │Analyse   │  │  & Markt-   ││
       │ └────┬─────┘  └────┬─────┘  │  analyse    ││
       │      │             │        └──────┬───────┘│
       │      │   ┌─────────┘               │        │
       │      ▼   ▼                         │        │
       │   ┌──────────┐                     │        │
       │   │ SKILL 8  │                     │        │
       │   │Rechtliche│                     │        │
       │   │Risikopr. │                     │        │
       │   └────┬─────┘                     │        │
       └────────┼───────────────────────────┘        │
                └────────────────────────────────────┘
                           │  alle Teilergebnisse
                           ▼
┌─────────────────────────────────────────────────────────────────────┐
│  SKILL 9: Risikobewertung & Investment-Score                       │
│  → Aggregiert alle Teilergebnisse → Gesamtrisiko, Score 0–100     │
└──────────────────────────┬──────────────────────────────────────────┘
                           │
                           ▼
┌─────────────────────────────────────────────────────────────────────┐
│  SKILL 10: Gesamt-Workflow-Orchestrierung                          │
│  → Fasst alle Skill-Ergebnisse zusammen → finales JSON für PDF    │
└──────────────────────────┬──────────────────────────────────────────┘
                           │  DUE_DILIGENCE_SCHEMA (vollständig)
                           ▼
                    PDF-Bericht (WeasyPrint)
```

### Ausführungsreihenfolge

| Phase | Skills | Ausführung | Bedingung |
| :--- | :--- | :--- | :--- |
| **Phase 0** | Skill 1 | Sequenziell (immer) | — |
| **Phase 1** | Skills 2, 3, 4, 5, 6, 7, 8 | Parallel (sofern Dokumente vorhanden) | Gesteuert durch Skill-1-Output |
| **Phase 2** | Skill 9 | Sequenziell (nach Phase 1) | Immer |
| **Phase 3** | Skill 10 | Sequenziell (nach Phase 2) | Immer |

---

## 5. Skill 1: Dokument-Inventarisierung und Vollständigkeitsprüfung

### Zweck

Erster Pflicht-Teilschritt. Klassifiziert alle hochgeladenen Dokumente nach Typ, prüft ob Kerndokumente fehlen und gibt eine priorisierte Liste fehlender Unterlagen aus. Steuert die bedingte Ausführung aller Folge-Skills.

### Skill-Steckbrief

| Attribut | Wert |
| :--- | :--- |
| **Skill-Bezeichner** | `dd_skill_01_document_inventory` |
| **Erforderliche Force Skills** | `advanced_document_extraction`, `file_classification` |
| **Input** | Alle hochgeladenen `file_ids` |
| **Output-Schema** | `SCHEMA_SKILL_01_INVENTORY` (siehe unten) |
| **Parallele Ausführung** | Nein (Voraussetzung für alle Folge-Skills) |
| **Geschätzte Dauer** | 3–8 Minuten |
| **Credits-Verbrauch** | ~35–110 Credits |

### Prompt

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

### Structured Output Schema

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
          "notes":          { "type": "string" }
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

---

## 6. Skill 2: Grundbuch- und Eigentumsanalyse

### Zweck

Analysiert Grundbuchauszüge auf Eigentümerstruktur, eingetragene Lasten, Beschränkungen, Grundschulden, Nießbrauch-, Wege- und Leitungsrechte. Identifiziert eigentumsrechtliche Risiken.

### Skill-Steckbrief

| Attribut | Wert |
| :--- | :--- |
| **Skill-Bezeichner** | `dd_skill_02_grundbuch` |
| **Erforderliche Force Skills** | `advanced_document_extraction`, `ocr_handwriting`, `legal_text_analysis` |
| **Input** | `file_ids` aller Grundbuchauszüge, Flurkarten, Teilungserklärungen |
| **Output-Schema** | `SCHEMA_SKILL_02_GRUNDBUCH` |
| **Parallele Ausführung** | Ja (parallel zu Skills 3–8) |
| **Geschätzte Dauer** | 5–15 Minuten |
| **Credits-Verbrauch** | ~55–210 Credits |
| **Ausführungsbedingung** | `skill_execution_flags.run_grundbuch_analysis == true` |

### Prompt

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

### Structured Output Schema

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
          "type":       { "type": "string",
                          "enum": ["Grundschuld", "Hypothek", "Rentenschuld"] },
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
    "grundbuch_notes":           { "type": "string" }
  },
  "required": ["ownership", "encumbrances", "mortgages", "total_mortgage_burden_eur",
               "land_area_sqm", "priority_risks", "grundbuch_risk_level",
               "grundbuch_notes"],
  "additionalProperties": false
}
```

---

## 7. Skill 3: Mietvertrags- und Mieteranalyse

### Zweck

Extrahiert und analysiert alle Mietverträge und Mieterlisten. Prüft Miethöhen, Laufzeiten, Indexierungsklauseln, Sonderkündigungsrechte und Mietausfallrisiken. Berechnet aktuelle und potenzielle Jahresmieteinnahmen.

### Skill-Steckbrief

| Attribut | Wert |
| :--- | :--- |
| **Skill-Bezeichner** | `dd_skill_03_mietanalyse` |
| **Erforderliche Force Skills** | `advanced_document_extraction`, `financial_data_processing`, `legal_text_analysis` |
| **Input** | `file_ids` aller Mietverträge, Mieterlisten, Nachträge |
| **Output-Schema** | `SCHEMA_SKILL_03_MIETE` |
| **Parallele Ausführung** | Ja |
| **Geschätzte Dauer** | 8–20 Minuten |
| **Credits-Verbrauch** | ~88–280 Credits |
| **Ausführungsbedingung** | `skill_execution_flags.run_mietvertrag_analysis == true` |

### Prompt

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

### Structured Output Schema

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
          "unit_notes":            { "type": "string" }
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

---

## 8. Skill 4: Wirtschaftliche Kennzahlenberechnung

### Zweck

Berechnet alle wirtschaftlichen KPIs auf Basis von Exposé-Daten, Mieterliste und Marktrecherche. Führt eine Sensitivitätsanalyse und Cashflow-Modellierung durch.

### Skill-Steckbrief

| Attribut | Wert |
| :--- | :--- |
| **Skill-Bezeichner** | `dd_skill_04_finanzkennzahlen` |
| **Erforderliche Force Skills** | `financial_data_processing`, `web_search`, `advanced_document_extraction` |
| **Input** | `file_ids` (Exposé, Mieterliste), Skill-3-Output (Mieteinnahmen) |
| **Output-Schema** | `SCHEMA_SKILL_04_FINANZEN` |
| **Parallele Ausführung** | Ja |
| **Geschätzte Dauer** | 6–15 Minuten |
| **Credits-Verbrauch** | ~66–210 Credits |
| **Ausführungsbedingung** | `skill_execution_flags.run_financial_analysis == true` |

### Prompt

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

### Structured Output Schema

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

---

## 9. Skill 5: Technische und bauliche Prüfung

### Zweck

Analysiert technische Gutachten, Energieausweis und Grundrisse auf Baumängel, Instandhaltungsrückstau, Energiezustand und notwendige Sanierungsmaßnahmen. Schätzt Kostenrahmen für Maßnahmen.

### Skill-Steckbrief

| Attribut | Wert |
| :--- | :--- |
| **Skill-Bezeichner** | `dd_skill_05_technisch` |
| **Erforderliche Force Skills** | `advanced_document_extraction`, `image_analysis`, `web_search` |
| **Input** | `file_ids` aller technischen Gutachten, Energieausweise, Grundrisse, Baupläne |
| **Output-Schema** | `SCHEMA_SKILL_05_TECHNIK` |
| **Parallele Ausführung** | Ja |
| **Geschätzte Dauer** | 5–12 Minuten |
| **Credits-Verbrauch** | ~55–168 Credits |
| **Ausführungsbedingung** | `skill_execution_flags.run_technical_analysis == true` |

### Prompt

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

### Structured Output Schema

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
          "severity":          {
            "type": "string", "enum": ["kritisch", "hoch", "mittel", "gering"]
          },
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
    "technical_notes":           { "type": "string" }
  },
  "required": ["building_year", "last_major_renovation", "energy_certificate",
               "defects", "investment_needs", "maintenance_backlog_notes",
               "upside_potential_notes", "technical_risk_level", "technical_notes"],
  "additionalProperties": false
}
```

---

## 10. Skill 6: WEG-Analyse und Eigentümergemeinschaft

### Zweck

Analysiert WEG-Protokolle und Jahresabrechnungen auf Hausgeld, Instandhaltungsrücklage, beschlossene Sonderumlagen, Rechtsstreitigkeiten innerhalb der WEG und geplante Großmaßnahmen.

### Skill-Steckbrief

| Attribut | Wert |
| :--- | :--- |
| **Skill-Bezeichner** | `dd_skill_06_weg` |
| **Erforderliche Force Skills** | `advanced_document_extraction`, `financial_data_processing`, `legal_text_analysis` |
| **Input** | `file_ids` aller WEG-Protokolle, Jahresabrechnungen, Wirtschaftspläne, Teilungserklärungen |
| **Output-Schema** | `SCHEMA_SKILL_06_WEG` |
| **Parallele Ausführung** | Ja |
| **Geschätzte Dauer** | 5–12 Minuten |
| **Credits-Verbrauch** | ~55–168 Credits |
| **Ausführungsbedingung** | `skill_execution_flags.run_weg_analysis == true` |

### Prompt

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

### Structured Output Schema

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
    "property_manager":      { "type": ["string", "null"] },
    "manager_contract_end":  { "type": ["string", "null"] },
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

---

## 11. Skill 7: Standort- und Marktanalyse

### Zweck

Recherchiert Standortfaktoren, Infrastruktur, Bevölkerungsentwicklung, Leerstandsquoten und Mietpreisentwicklung am Standort via Websuche. Bewertet Makro- und Mikrolage.

### Skill-Steckbrief

| Attribut | Wert |
| :--- | :--- |
| **Skill-Bezeichner** | `dd_skill_07_standort` |
| **Erforderliche Force Skills** | `web_search`, `data_analysis` |
| **Input** | Adresse/Standort (aus Skill-1-Output), ggf. `file_ids` mit Lagebeschreibung aus Exposé |
| **Output-Schema** | `SCHEMA_SKILL_07_STANDORT` |
| **Parallele Ausführung** | Ja |
| **Geschätzte Dauer** | 8–20 Minuten |
| **Credits-Verbrauch** | ~88–280 Credits |
| **Ausführungsbedingung** | Immer |

### Prompt

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

### Structured Output Schema

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
    "unemployment_rate_pct":   { "type": ["number", "null"] },
    "public_transport_minutes":{ "type": ["integer", "null"] },
    "infrastructure_notes":    { "type": "string" },
    "market_rent_per_sqm_eur": { "type": ["number", "null"] },
    "market_price_per_sqm_eur":{ "type": ["number", "null"] },
    "rent_trend_3y_pct":       { "type": ["number", "null"] },
    "vacancy_rate_market_pct": { "type": ["number", "null"] },
    "flood_risk_zone":         { "type": ["string", "null"] },
    "contamination_risk":      {
      "type": "string", "enum": ["niedrig", "mittel", "hoch", "unbekannt"]
    },
    "milieuschutz":            { "type": "boolean" },
    "risk_factors":            { "type": "array", "items": { "type": "string" } },
    "location_strengths":      { "type": "array", "items": { "type": "string" } },
    "location_risk_level":     {
      "type": "string", "enum": ["Low", "Medium", "High", "Critical"]
    },
    "location_notes":          { "type": "string" },
    "data_sources":            { "type": "array", "items": { "type": "string" } }
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

---

## 12. Skill 8: Rechtliche Risikoprüfung

### Zweck

Übergreifende rechtliche Analyse aller Dokumente: Kaufvertragsentwurf, Mietrechtsklauseln, Grundbucheintragungen und WEG-Beschlüsse auf rechtliche Fallstricke, Gewährleistungsausschlüsse und Haftungsrisiken.

### Skill-Steckbrief

| Attribut | Wert |
| :--- | :--- |
| **Skill-Bezeichner** | `dd_skill_08_rechtlich` |
| **Erforderliche Force Skills** | `legal_text_analysis`, `advanced_document_extraction` |
| **Input** | `file_ids` (Kaufvertragsentwurf, Mietverträge, Grundbuch) |
| **Output-Schema** | `SCHEMA_SKILL_08_RECHT` |
| **Parallele Ausführung** | Ja |
| **Geschätzte Dauer** | 6–15 Minuten |
| **Credits-Verbrauch** | ~66–210 Credits |
| **Ausführungsbedingung** | `skill_execution_flags.run_legal_analysis == true` |

### Prompt

```
Führe eine vollständige rechtliche Risikoprüfung aller angehängten Dokumente durch.

KAUFVERTRAGSENTWURF (falls vorhanden):
- Kaufpreis und Zahlungsmodalitäten: Plausibel? Treuhänderische Abwicklung?
- Gewährleistungsausschlüsse: Wie weit? Sind bekannte Mängel offengelegt?
- Übergabetermin: Auflösende Bedingungen, Finanzierungsvorbehalt?
- § 577 BGB: Ist die Käuferrechtsbelehrung bei Mieterwohnungen vorgesehen?
- Vorkaufsrechte: Alle Berechtigten korrekt benachrichtigt?
- Auflassungsvormerkung: Beantragt?

MIETRECHTLICHE RISIKEN:
- Schönheitsreparaturklauseln: Nach BGH-Rechtsprechung (2015) wirksam?
- Eigenbedarfskündigung: Für vorhandene Mieter zeitnah möglich?
- Sozialklausel / Härtefalleinwände bei älteren oder kranken Mietern?
- Mietpreisbremse: Gilt sie am Standort? Werden Obergrenzen eingehalten?
- Indexmiete: Entspricht die Anpassungsklausel § 557b BGB?

STEUERLICHE HINWEISE (keine steuerliche Beratung):
- Abschreibungspotenzial: Anteil Gebäude vs. Grund für § 7 EStG-AfA
- Denkmalschutz-AfA: Ist das Objekt unter Denkmalschutz?

COMPLIANCE UND ÖFFENTLICHES RECHT:
- Baugenehmigungen: Ist die aktuelle Nutzung vollständig genehmigt?
- Zweckentfremdungsverbot: Gilt es? Gibt es eine Ausnahmegenehmigung?
- Altlastenverdacht im Baulastenverzeichnis?

Gib für jedes Risiko an: Rechtsgrundlage, Schweregrad, Handlungsempfehlung.
```

### Structured Output Schema

```json
{
  "type": "object",
  "properties": {
    "purchase_contract_risks": {
      "type": "array",
      "items": {
        "type": "object",
        "properties": {
          "clause":         { "type": "string" },
          "description":    { "type": "string" },
          "legal_basis":    { "type": "string" },
          "severity":       { "type": "string",
                              "enum": ["Critical", "High", "Medium", "Low"] },
          "recommendation": { "type": "string" }
        },
        "required": ["clause", "description", "legal_basis", "severity",
                     "recommendation"],
        "additionalProperties": false
      }
    },
    "tenancy_law_risks": {
      "type": "array",
      "items": {
        "type": "object",
        "properties": {
          "type":           { "type": "string" },
          "description":    { "type": "string" },
          "severity":       { "type": "string",
                              "enum": ["Critical", "High", "Medium", "Low"] },
          "recommendation": { "type": "string" }
        },
        "required": ["type", "description", "severity", "recommendation"],
        "additionalProperties": false
      }
    },
    "public_law_issues":             { "type": "array", "items": { "type": "string" } },
    "tax_notes":                     { "type": "string" },
    "warranty_exclusion_assessment": { "type": "string" },
    "all_legal_risks":               { "type": "array", "items": { "type": "string" } },
    "legal_risk_level":              {
      "type": "string", "enum": ["Low", "Medium", "High", "Critical"]
    },
    "legal_notes":                   { "type": "string" }
  },
  "required": ["purchase_contract_risks", "tenancy_law_risks", "public_law_issues",
               "tax_notes", "warranty_exclusion_assessment", "all_legal_risks",
               "legal_risk_level", "legal_notes"],
  "additionalProperties": false
}
```

---

## 13. Skill 9: Risikobewertung und Investment-Score

### Zweck

Aggregiert alle Teilergebnisse der Skills 2–8 zu einer ganzheitlichen Risikobewertung. Berechnet den Investment-Score (0–100), leitet Stärken und Schwächen ab und formuliert die abschließende Investitionsempfehlung.

### Skill-Steckbrief

| Attribut | Wert |
| :--- | :--- |
| **Skill-Bezeichner** | `dd_skill_09_risikoscore` |
| **Erforderliche Force Skills** | `financial_data_processing`, `data_analysis` |
| **Input** | JSON-Outputs der Skills 1–8 als Kontext im Prompt |
| **Output-Schema** | `SCHEMA_SKILL_09_SCORE` |
| **Parallele Ausführung** | Nein (benötigt alle vorigen Outputs) |
| **Geschätzte Dauer** | 5–10 Minuten |
| **Credits-Verbrauch** | ~55–140 Credits |
| **Ausführungsbedingung** | Immer |

### Prompt-Template

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

### Structured Output Schema

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
          "severity":        {
            "type": "string", "enum": ["Critical", "High", "Medium", "Low"]
          },
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

---

## 14. Skill 10: Gesamt-Workflow-Orchestrierung

### Zweck

Der übergeordnete Orchestrierungs-Skill. Führt alle vorgelagerten Skills aus, aggregiert deren Outputs und erzeugt das finale, vollständige `DUE_DILIGENCE_SCHEMA`-konforme JSON für den PDF-Bericht.

### Skill-Steckbrief

| Attribut | Wert |
| :--- | :--- |
| **Skill-Bezeichner** | `dd_skill_10_orchestrator` |
| **Erforderliche Force Skills** | Alle (Skills 1–9 werden sub-orchestriert) |
| **Input** | Alle `file_ids`, alle Skill-1-9-Outputs |
| **Output-Schema** | `DUE_DILIGENCE_SCHEMA` (vollständiges finales Schema) |
| **Parallele Ausführung** | Nein (letzter Task) |
| **Geschätzte Dauer** | 3–8 Minuten (reine Aggregation) |
| **Credits-Verbrauch** | ~33–110 Credits |
| **Ausführungsbedingung** | Immer |

### Orchestrierungs-Logik (Python-Backend)

```python
async def run_full_workflow(file_ids: list[str], project_id: str) -> dict:
    """Führt den vollständigen Due-Diligence-Workflow in 3 Phasen aus."""
    results = {}

    # ─── Phase 0: Pflicht — Inventarisierung ────────────────────────────────
    results["skill_01"] = await run_skill(
        project_id=project_id,
        file_ids=file_ids,
        skill_id="dd_skill_01_document_inventory",
        schema=SCHEMA_SKILL_01_INVENTORY
    )
    flags = results["skill_01"]["skill_execution_flags"]

    # ─── Phase 1: Parallele Fachanalysen (bedingt) ──────────────────────────
    phase1_coros = []

    if flags["run_grundbuch_analysis"]:
        phase1_coros.append(run_skill(
            "dd_skill_02_grundbuch", SCHEMA_SKILL_02_GRUNDBUCH,
            file_ids=filter_by_type(file_ids, results["skill_01"],
                                    ["Grundbuchauszug", "Flurkarte", "Teilungserklärung"])
        ))
    if flags["run_mietvertrag_analysis"]:
        phase1_coros.append(run_skill(
            "dd_skill_03_mietanalyse", SCHEMA_SKILL_03_MIETE,
            file_ids=filter_by_type(file_ids, results["skill_01"],
                                    ["Mietvertrag", "Mieterliste"])
        ))
    if flags["run_financial_analysis"]:
        phase1_coros.append(run_skill(
            "dd_skill_04_finanzkennzahlen", SCHEMA_SKILL_04_FINANZEN,
            file_ids=file_ids
        ))
    if flags["run_technical_analysis"]:
        phase1_coros.append(run_skill(
            "dd_skill_05_technisch", SCHEMA_SKILL_05_TECHNIK,
            file_ids=filter_by_type(file_ids, results["skill_01"],
                                    ["Energieausweis", "Technisches Gutachten", "Bauplan"])
        ))
    if flags["run_weg_analysis"]:
        phase1_coros.append(run_skill(
            "dd_skill_06_weg", SCHEMA_SKILL_06_WEG,
            file_ids=filter_by_type(file_ids, results["skill_01"],
                                    ["WEG-Protokoll", "WEG-Jahresabrechnung"])
        ))
    # Standort läuft immer
    phase1_coros.append(run_skill(
        "dd_skill_07_standort", SCHEMA_SKILL_07_STANDORT,
        file_ids=file_ids,
        extra_context={"address": results["skill_01"]["property_address"]}
    ))
    if flags["run_legal_analysis"]:
        phase1_coros.append(run_skill(
            "dd_skill_08_rechtlich", SCHEMA_SKILL_08_RECHT,
            file_ids=file_ids
        ))

    # Parallel ausführen (Rate-Limit beachten: max. 10 task.create/Min.)
    phase1_results = await asyncio.gather(*phase1_coros, return_exceptions=True)
    for i, r in enumerate(phase1_results):
        key = f"skill_{str(i + 2).zfill(2)}"
        results[key] = r if not isinstance(r, Exception) else None

    # ─── Phase 2: Risikobewertung & Score ───────────────────────────────────
    results["skill_09"] = await run_skill(
        skill_id="dd_skill_09_risikoscore",
        schema=SCHEMA_SKILL_09_SCORE,
        extra_context=results
    )

    # ─── Phase 3: Finale Aggregation → DUE_DILIGENCE_SCHEMA ─────────────────
    return await run_skill(
        skill_id="dd_skill_10_orchestrator",
        schema=DUE_DILIGENCE_SCHEMA,
        extra_context=results
    )
```

### Prompt (Aggregations-Schritt)

```
Du hast alle Teilergebnisse der Due-Diligence-Analyse vorliegen.
Fasse sie zu einem vollständigen, kohärenten Abschlussbericht zusammen.

INVENTAR (Skill 1): {skill_01}
GRUNDBUCH (Skill 2): {skill_02}
MIETANALYSE (Skill 3): {skill_03}
FINANZKENNZAHLEN (Skill 4): {skill_04}
TECHNIK (Skill 5): {skill_05}
WEG (Skill 6): {skill_06}
STANDORT (Skill 7): {skill_07}
RECHT (Skill 8): {skill_08}
RISIKOBEWERTUNG & SCORE (Skill 9): {skill_09}

Erstelle das finale JSON-Objekt:
1. executive_summary: 2–3 präzise Sätze zu den wichtigsten 3–4 Erkenntnissen.
2. completeness_check: Aus Skill 1.
3. red_flags: Aus Skill 9, sortiert nach Schweregrad (Critical zuerst).
4. risk_assessment: Aus Skill 9.
5. financial_summary: Zusammenführung Skill 3 + Skill 4.
6. kpis: Direkt aus Skill 4.
7. legal_risks: Aggregiert aus Skills 2, 3 und 8.
8. strengths / weaknesses: Aus Skill 9.
9. open_questions: Aggregiert aus Skills 1–8 (alle offenen Fragen).
10. investment_score: Aus Skill 9.
11. recommendation: Aus Skill 9.
12. overall_risk_level: Aus Skill 9.
13. document_types_analyzed: Aus Skill 1.
14. property_address: Aus Skill 1.

Wenn ein Teilschritt nicht ausgeführt wurde, vermerke dies im betreffenden Feld.
Fehlende Zahlenwerte als null, fehlende Texte als "Keine Daten vorhanden".
Erfinde keine Informationen.
```

---

## 15. Gesamt-Structured-Output-Schema

Das finale `DUE_DILIGENCE_SCHEMA` ist identisch mit dem in `src/schema.py` definierten Schema und das einzige Schema, das für den PDF-Bericht-Generator relevant ist.

```json
{
  "type": "object",
  "properties": {
    "property_address":        { "type": ["string", "null"] },
    "document_types_analyzed": { "type": "array", "items": { "type": "string" } },
    "overall_risk_level":      {
      "type": "string", "enum": ["Low", "Medium", "High", "Critical"]
    },
    "executive_summary":       { "type": "string" },
    "completeness_check": {
      "type": "object",
      "properties": {
        "missing_documents":   { "type": "array", "items": { "type": "string" } },
        "missing_data_points": { "type": "array", "items": { "type": "string" } }
      },
      "required": ["missing_documents", "missing_data_points"],
      "additionalProperties": false
    },
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
          "severity":        {
            "type": "string", "enum": ["Critical", "High", "Medium", "Low"]
          },
          "source_document": { "type": "string" }
        },
        "required": ["category", "description", "severity", "source_document"],
        "additionalProperties": false
      }
    },
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
    "financial_summary": {
      "type": "object",
      "properties": {
        "current_rent_annual_eur":          { "type": ["number", "null"] },
        "estimated_market_rent_annual_eur": { "type": ["number", "null"] },
        "vacancy_risk_assessment":          { "type": "string" },
        "maintenance_backlog_notes":        { "type": "string" }
      },
      "required": ["current_rent_annual_eur", "estimated_market_rent_annual_eur",
                   "vacancy_risk_assessment", "maintenance_backlog_notes"],
      "additionalProperties": false
    },
    "kpis": {
      "type": "object",
      "properties": {
        "price_per_sqm_eur":            { "type": ["number", "null"] },
        "rent_multiplier":              { "type": ["number", "null"] },
        "gross_yield_percent":          { "type": ["number", "null"] },
        "net_yield_percent":            { "type": ["number", "null"] },
        "cashflow_pre_financing_eur":   { "type": ["number", "null"] },
        "cashflow_post_financing_eur":  { "type": ["number", "null"] },
        "operating_cost_ratio_percent": { "type": ["number", "null"] },
        "reserve_need_notes":           { "type": "string" },
        "sensitivity_analysis_notes":   { "type": "string" }
      },
      "required": ["price_per_sqm_eur", "rent_multiplier", "gross_yield_percent",
                   "net_yield_percent", "cashflow_pre_financing_eur",
                   "cashflow_post_financing_eur", "operating_cost_ratio_percent",
                   "reserve_need_notes", "sensitivity_analysis_notes"],
      "additionalProperties": false
    },
    "legal_risks":    { "type": "array", "items": { "type": "string" } },
    "strengths":      { "type": "array", "items": { "type": "string" } },
    "weaknesses":     { "type": "array", "items": { "type": "string" } },
    "open_questions": { "type": "array", "items": { "type": "string" } },
    "investment_score": {
      "type": "object",
      "properties": {
        "score":             { "type": "number" },
        "score_explanation": { "type": "string" },
        "classification":    {
          "type": "string",
          "enum": ["Sehr starkes Investment", "Solides Investment", "Prueffall",
                   "Kritisch", "Nicht empfehlenswert"]
        }
      },
      "required": ["score", "score_explanation", "classification"],
      "additionalProperties": false
    },
    "recommendation": {
      "type": "string", "enum": ["Kaufen", "Nachverhandeln", "Abstand nehmen"]
    }
  },
  "required": ["property_address", "document_types_analyzed", "overall_risk_level",
               "executive_summary", "completeness_check", "red_flags",
               "risk_assessment", "financial_summary", "kpis", "legal_risks",
               "strengths", "weaknesses", "open_questions", "investment_score",
               "recommendation"],
  "additionalProperties": false
}
```

---

## 16. Multi-Turn-Interaktion (Chat-Nachfragen)

Wenn der Nutzer nach der generierten Analyse Nachfragen stellt (z.B. *"Erkläre mir das Wegerecht im Detail"*), wird der bestehende Workflow-Task fortgesetzt.

**API Call:** `POST /v2/task.sendMessage`

```json
{
  "task_id": "task_xyz_workflow",
  "message": {
    "content": "Erkläre mir das Wegerecht im Grundbuch im Detail."
  }
}
```

Für Chat-Nachfragen wird **kein** `structured_output_schema` mitgeschickt. Die Antwort kommt als Markdown-Text und wird direkt im Chainlit-Frontend angezeigt. Die Due-Diligence-Persona und der vollständige Analysekontext bleiben über die `project_id` aktiv.

### Empfohlene Follow-up-Themen

| Nutzerfrage | Relevanter Skill-Kontext |
| :--- | :--- |
| "Erkläre das Nießbrauchrecht im Grundbuch" | Skill 2 |
| "Welche Mieterhöhung ist realistisch?" | Skills 3, 7 |
| "Berechne die Rendite bei 10% Rabatt auf Kaufpreis" | Skill 4 |
| "Was müsste ich vor dem Kauf sanieren?" | Skills 5, 6 |
| "Ist die Sonderumlage verhandelbar?" | Skill 6 |
| "Welche Klauseln im Kaufvertrag sind gefährlich?" | Skill 8 |
| "Was bedeutet der Investment-Score von X?" | Skill 9 |

---

## 17. Implementierungshinweise für den Python-Client

### Rate-Limit-Management

Das Manus-API-Limit von **10 `task.create`-Requests pro Minute** muss bei paralleler Ausführung berücksichtigt werden.

```python
import asyncio

TASK_SEMAPHORE = asyncio.Semaphore(8)  # Sicherheitspuffer

async def run_skill_with_rate_limit(skill_id, schema, file_ids, **kwargs):
    async with TASK_SEMAPHORE:
        task_id = create_analysis_task(file_ids, schema, skill_ids=[skill_id], **kwargs)
        return await asyncio.get_event_loop().run_in_executor(
            None, poll_for_result, task_id, 600  # 10 Min. Timeout pro Skill
        )

async def run_skill_safe(skill_id, schema, file_ids, **kwargs) -> dict | None:
    """Gibt None zurück bei Fehler, damit der Workflow weiterläuft."""
    try:
        return await run_skill_with_rate_limit(skill_id, schema, file_ids, **kwargs)
    except Exception as e:
        logger.warning(f"Skill {skill_id} fehlgeschlagen: {e}")
        return None
```

### Kosten-Schätzung Gesamt-Workflow

| Szenario | Aktive Skills | Geschätzte Dauer | Credits |
| :--- | :--- | :--- | :--- |
| **Minimal** (2 Docs) | 4–5 Skills | 25–35 Min. | 350–500 |
| **Standard** (4–6 Docs) | 7–8 Skills | 40–60 Min. | 560–840 |
| **Vollständig** (8–12 Docs) | 10 Skills | 55–80 Min. | 770–1.120 |

### Umgebungsvariablen

```env
MANUS_API_KEY=dein_manus_api_key_hier
MANUS_PROJECT_ID=proj_abc123

# Skill-IDs (einmalig mit check_skills.py ermitteln)
MANUS_SKILL_DOC_EXTRACTION=skill_xxxxxxx
MANUS_SKILL_LEGAL_ANALYSIS=skill_xxxxxxx
MANUS_SKILL_FINANCIAL_PROCESSING=skill_xxxxxxx
MANUS_SKILL_WEB_SEARCH=skill_xxxxxxx
MANUS_SKILL_IMAGE_ANALYSIS=skill_xxxxxxx
MANUS_SKILL_DATA_ANALYSIS=skill_xxxxxxx
MANUS_SKILL_OCR_HANDWRITING=skill_xxxxxxx
MANUS_SKILL_FILE_CLASSIFICATION=skill_xxxxxxx
```

---

## 18. Referenzen

[1] "Manus API Integration Guide", `SKILL.md`, System Knowledge.  
[2] "project.create API Documentation", `project.create.mdx`, System Knowledge.  
[3] "task.create API Documentation", `task.create.mdx`, System Knowledge.  
[4] "Structured Output Documentation", `structured-output.mdx`, System Knowledge.  
[5] "skill.list API Documentation", `skill.list.mdx`, System Knowledge.  
[6] BGB § 557b (Indexmiete), § 555b (Modernisierung), § 577 (Vorkaufsrecht Mieter).  
[7] WEG § 10 Abs. 4 (Bindungswirkung von Beschlüssen).  
[8] GEG (Gebäudeenergiegesetz) — Anforderungen bis 2035/2045.  
[9] BGH-Rechtsprechung zu Schönheitsreparaturklauseln (u.a. BGH VIII ZR 185/14).

Um API-Kosten zu sparen und den Code sauber zu halten, wird beim initialen Setup (oder bei der Erstellung eines neuen Analyse-Vorgangs) ein Manus-Projekt angelegt. 

**API Call:** `POST /v2/project.create`

**Projekt-Instruktion (wird an alle Tasks vererbt):**
> "Du bist ein hochqualifizierter Senior Real Estate Analyst und Due-Diligence-Experte für den deutschsprachigen Immobilienmarkt. Deine Aufgabe ist es, komplexe Maklerunterlagen (Exposés, Grundbuchauszüge, Mietverträge, Teilungserklärungen, Gutachten) präzise zu analysieren. 
> 
> Du arbeitest extrem akkurat, übersiehst keine rechtlichen Fallstricke (z.B. Dienstbarkeiten, Wegerechte, Indexmietklauseln) und bewertest wirtschaftliche Risiken (z.B. Leerstand, Instandhaltungsrückstau) objektiv. Wenn Informationen fehlen, erfindest du nichts, sondern listest diese als 'Offene Fragen' auf. Du denkst wie ein konservativer Investor, markierst Widersprueche und lieferst eine klare Empfehlung (Kaufen / Nachverhandeln / Abstand nehmen) inklusive Investment-Score (0-100)."

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
    "content": "Führe die vollständige Due-Diligence-Analyse für die angehängten Maklerunterlagen durch. Strukturiere die Ergebnisse strikt nach dem vorgegebenen Schema.",
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
    "completeness_check": {
      "type": "object",
      "properties": {
        "missing_documents": { "type": "array", "items": { "type": "string" } },
        "missing_data_points": { "type": "array", "items": { "type": "string" } }
      },
      "required": ["missing_documents", "missing_data_points"],
      "additionalProperties": false
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
    "risk_assessment": {
      "type": "object",
      "properties": {
        "legal": { "type": "string", "enum": ["Low", "Medium", "High", "Critical"] },
        "financial": { "type": "string", "enum": ["Low", "Medium", "High", "Critical"] },
        "technical": { "type": "string", "enum": ["Low", "Medium", "High", "Critical"] },
        "location": { "type": "string", "enum": ["Low", "Medium", "High", "Critical"] },
        "tenant_default": { "type": "string", "enum": ["Low", "Medium", "High", "Critical"] }
      },
      "required": ["legal", "financial", "technical", "location", "tenant_default"],
      "additionalProperties": false
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
    "kpis": {
      "type": "object",
      "properties": {
        "price_per_sqm_eur": { "type": ["number", "null"] },
        "rent_multiplier": { "type": ["number", "null"] },
        "gross_yield_percent": { "type": ["number", "null"] },
        "net_yield_percent": { "type": ["number", "null"] },
        "cashflow_pre_financing_eur": { "type": ["number", "null"] },
        "cashflow_post_financing_eur": { "type": ["number", "null"] },
        "operating_cost_ratio_percent": { "type": ["number", "null"] },
        "reserve_need_notes": { "type": "string" },
        "sensitivity_analysis_notes": { "type": "string" }
      },
      "required": [
        "price_per_sqm_eur", "rent_multiplier", "gross_yield_percent",
        "net_yield_percent", "cashflow_pre_financing_eur",
        "cashflow_post_financing_eur", "operating_cost_ratio_percent",
        "reserve_need_notes", "sensitivity_analysis_notes"
      ],
      "additionalProperties": false
    },
    "legal_risks": {
      "type": "array",
      "items": { "type": "string" },
      "description": "Rechtliche Risiken und Befunde aus den Dokumenten."
    },
    "strengths": { "type": "array", "items": { "type": "string" } },
    "weaknesses": { "type": "array", "items": { "type": "string" } },
    "open_questions": {
      "type": "array",
      "items": { "type": "string" },
      "description": "Wichtige Due-Diligence-Punkte, die aus den vorliegenden Dokumenten NICHT beantwortet werden können."
    },
    "investment_score": {
      "type": "object",
      "properties": {
        "score": { "type": "number" },
        "score_explanation": { "type": "string" },
        "classification": {
          "type": "string",
          "enum": ["Sehr starkes Investment", "Solides Investment", "Prueffall", "Kritisch", "Nicht empfehlenswert"]
        }
      },
      "required": ["score", "score_explanation", "classification"],
      "additionalProperties": false
    },
    "recommendation": {
      "type": "string",
      "enum": ["Kaufen", "Nachverhandeln", "Abstand nehmen"]
    }
  },
  "required": [
    "property_address", 
    "document_types_analyzed", 
    "overall_risk_level", 
    "executive_summary", 
    "completeness_check",
    "red_flags", 
    "financial_summary", 
    "risk_assessment",
    "kpis",
    "legal_risks", 
    "strengths",
    "weaknesses",
    "open_questions",
    "investment_score",
    "recommendation"
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
