---
name: dd-skill-08-rechtlich
description: 'Immobilien Due Diligence: Rechtliche Risikoprüfung. Use to analyze purchase contract (Kaufvertragsentwurf), tenancy law clauses (Schönheitsreparaturen, Mietpreisbremse, Eigenbedarfskündigung), building permits, Zweckentfremdungsverbot, tax notes (AfA, Denkmalschutz), and warranty exclusions. Run in parallel after skill 1 sets run_legal_analysis=true.'
argument-hint: 'file_ids[] of Kaufvertragsentwurf, Mietverträge, Grundbuchauszüge'
---

# Skill 8: Rechtliche Risikoprüfung

## Zweck
Übergreifende rechtliche Analyse aller Dokumente: Kaufvertragsentwurf, Mietrechtsklauseln, Grundbucheintragungen und WEG-Beschlüsse auf rechtliche Fallstricke, Gewährleistungsausschlüsse und Haftungsrisiken. Bewertet jeden Risikopunkt mit Rechtsgrundlage und Handlungsempfehlung.

## Skill-Steckbrief
- **Skill-Bezeichner:** `dd_skill_08_rechtlich`
- **Erforderliche Force Skills:** `legal_text_analysis`, `advanced_document_extraction`
- **Input:** `file_ids` (Kaufvertragsentwurf, Mietverträge, Grundbuch)
- **Parallele Ausführung:** Ja
- **Geschätzte Dauer:** 6–15 Minuten
- **Credits-Verbrauch:** ~66–210 Credits
- **Ausführungsbedingung:** `skill_execution_flags.run_legal_analysis == true`

## Verwendung
Diesen Skill aufrufen wenn:
- Rechtliche Fallstricke in Kauf- oder Mietverträgen identifiziert werden sollen
- Gewährleistungsausschlüsse und § 577 BGB-Belehrungen geprüft werden sollen
- Mietpreisbremse, Eigenbedarfs- und Sozialklausel-Risiken bewertet werden sollen
- Baugenehmigungen und Zweckentfremdungsverbote geprüft werden sollen

## Procedure

1. Prüfe `skill_execution_flags.run_legal_analysis` aus Skill-1-Output
2. Alle `file_ids` übergeben (Kaufvertrag, Mietverträge, Grundbuch)
3. Manus Task anlegen mit `force_skills: ["legal_text_analysis", "advanced_document_extraction"]`
4. Prompt (siehe unten) senden
5. `structured_output_schema: SCHEMA_SKILL_08_RECHT` anhängen
6. Task-Status pollen bis `completed`
7. `legal_risk_level` und `all_legal_risks` an Skills 9+10 weitergeben

## Manus API Prompt

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

## Structured Output Schema (`SCHEMA_SKILL_08_RECHT`)

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
          "severity":       { "type": "string", "enum": ["Critical", "High", "Medium", "Low"] },
          "recommendation": { "type": "string" }
        },
        "required": ["clause", "description", "legal_basis", "severity", "recommendation"],
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
          "severity":       { "type": "string", "enum": ["Critical", "High", "Medium", "Low"] },
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
    "legal_notes": { "type": "string" }
  },
  "required": ["purchase_contract_risks", "tenancy_law_risks", "public_law_issues",
               "tax_notes", "warranty_exclusion_assessment", "all_legal_risks",
               "legal_risk_level", "legal_notes"],
  "additionalProperties": false
}
```
