---
name: dd-skill-10-orchestrator
description: 'Immobilien Due Diligence: Gesamt-Workflow-Orchestrierung. Use to run the complete end-to-end due diligence workflow: orchestrates all 10 skills in the correct sequence (Phase 0: skill 1 → Phase 1: skills 2-8 parallel → Phase 2: skill 9 → Phase 3: final aggregation), then produces the complete DUE_DILIGENCE_SCHEMA JSON for PDF report generation. Entry point for the full analysis pipeline.'
argument-hint: 'file_ids[] of all uploaded documents, project_id'
---

# Skill 10: Gesamt-Workflow-Orchestrierung

## Zweck
Der übergeordnete Orchestrierungs-Skill. Führt alle vorgelagerten Skills (1–9) aus, aggregiert deren Outputs und erzeugt das finale, vollständige `DUE_DILIGENCE_SCHEMA`-konforme JSON für den PDF-Bericht (WeasyPrint). Einstiegspunkt für die gesamte Analyse-Pipeline.

## Skill-Steckbrief
- **Skill-Bezeichner:** `dd_skill_10_orchestrator`
- **Erforderliche Force Skills:** Alle (Skills 1–9 werden orchestriert)
- **Input:** Alle `file_ids`, alle Skill-1-9-Outputs
- **Parallele Ausführung:** Nein (letzter Task)
- **Geschätzte Dauer:** 3–8 Minuten (reine Aggregation) + Phase-1-Zeit
- **Credits-Verbrauch:** ~33–110 Credits (Aggregationsschritt) + alle Phase-1-Credits
- **Ausführungsbedingung:** Immer

## Verwendung
Diesen Skill aufrufen wenn:
- Eine vollständige Due-Diligence-Analyse durchgeführt werden soll
- Alle Teilschritte automatisch orchestriert werden sollen
- Das finale JSON für den PDF-Bericht generiert werden soll

## Ausführungsphasen

| Phase | Skills | Ausführung | Bedingung |
|-------|--------|-----------|-----------|
| **Phase 0** | Skill 1 | Sequenziell (immer) | — |
| **Phase 1** | Skills 2, 3, 4, 5, 6, 7, 8 | Parallel (bedingt) | Gesteuert durch Skill-1-Flags |
| **Phase 2** | Skill 9 | Sequenziell | Nach Phase 1 |
| **Phase 3** | Skill 10 (Aggregation) | Sequenziell | Nach Phase 2 |

## Procedure

1. `MANUS_PROJECT_ID` aus Umgebungsvariable laden
2. **Phase 0:** Skill 1 ausführen → `skill_execution_flags` auswerten
3. **Phase 1:** Bedingte parallele Skills starten (Rate-Limit: max. 10 task.create/Min.):
   - `run_grundbuch_analysis` → Skill 2
   - `run_mietvertrag_analysis` → Skill 3
   - `run_financial_analysis` → Skill 4
   - `run_technical_analysis` → Skill 5
   - `run_weg_analysis` → Skill 6
   - Immer → Skill 7 (Standort)
   - `run_legal_analysis` → Skill 8
4. `asyncio.gather()` auf alle Phase-1-Coroutines warten
5. Fehlgeschlagene Skills als `null` in results markieren (kein Abbruch)
6. **Phase 2:** Skill 9 mit allen Phase-1-Outputs als Kontext ausführen
7. **Phase 3:** Aggregations-Task (Skill 10) ausführen mit allen Outputs
8. `DUE_DILIGENCE_SCHEMA`-konformes JSON zurückgeben
9. JSON an `pdf_generator.py` übergeben

## Python Orchestrierungs-Logik

```python
async def run_full_workflow(file_ids: list[str], project_id: str) -> dict:
    results = {}

    # Phase 0
    results["skill_01"] = await run_skill(
        project_id=project_id, file_ids=file_ids,
        skill_id="dd_skill_01_document_inventory",
        schema=SCHEMA_SKILL_01_INVENTORY
    )
    flags = results["skill_01"]["skill_execution_flags"]

    # Phase 1 (parallel, bedingt)
    phase1_coros = []
    if flags["run_grundbuch_analysis"]:
        phase1_coros.append(run_skill("dd_skill_02_grundbuch", ...))
    if flags["run_mietvertrag_analysis"]:
        phase1_coros.append(run_skill("dd_skill_03_mietanalyse", ...))
    if flags["run_financial_analysis"]:
        phase1_coros.append(run_skill("dd_skill_04_finanzkennzahlen", ...))
    if flags["run_technical_analysis"]:
        phase1_coros.append(run_skill("dd_skill_05_technisch", ...))
    if flags["run_weg_analysis"]:
        phase1_coros.append(run_skill("dd_skill_06_weg", ...))
    phase1_coros.append(run_skill("dd_skill_07_standort", ...))  # immer
    if flags["run_legal_analysis"]:
        phase1_coros.append(run_skill("dd_skill_08_rechtlich", ...))

    phase1_results = await asyncio.gather(*phase1_coros, return_exceptions=True)

    # Phase 2
    results["skill_09"] = await run_skill(
        skill_id="dd_skill_09_risikoscore",
        schema=SCHEMA_SKILL_09_SCORE,
        extra_context=results
    )

    # Phase 3
    return await run_skill(
        skill_id="dd_skill_10_orchestrator",
        schema=DUE_DILIGENCE_SCHEMA,
        extra_context=results
    )
```

See [../../src/manus_client.py](../../src/manus_client.py) for full implementation.

## Aggregations-Prompt (Phase 3)

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

## Finales Output-Schema (`DUE_DILIGENCE_SCHEMA`)

Das vollständige Schema ist in [../../src/schema.py](../../src/schema.py) definiert. Es enthält:
- `property_address`, `document_types_analyzed`, `overall_risk_level`
- `executive_summary`, `completeness_check`, `red_flags`
- `risk_assessment` (legal, financial, technical, location, tenant_default)
- `financial_summary` (current_rent, market_rent, vacancy_risk, maintenance_backlog)
- `kpis` (price_per_sqm, rent_multiplier, gross/net yield, cashflow, operating_cost_ratio)
- `legal_risks`, `strengths`, `weaknesses`, `open_questions`
- `investment_score` (score 0–100, classification, explanation)
- `recommendation` (Kaufen/Nachverhandeln/Abstand nehmen)

All fields with `additionalProperties: false` and strict enum/null typing.
