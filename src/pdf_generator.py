from datetime import datetime
from pathlib import Path


def _badge(level: str) -> str:
    icons = {"Low": "🟢", "Medium": "🟡", "High": "🔴", "Critical": "⛔"}
    return f"{icons.get(level, '⚪')} {level}"


def generate_markdown(json_data: dict) -> str:
    d = json_data
    created_at = datetime.now().strftime("%d.%m.%Y %H:%M Uhr")
    address = d.get("property_address") or "–"
    lines: list[str] = []

    lines += [
        f"# 🏠 Due Diligence Bericht",
        f"**Objekt:** {address}  ",
        f"**Erstellt:** {created_at}  ",
        f"**Gesamtrisiko:** {_badge(d.get('overall_risk_level', '–'))}",
        "",
        "---",
        "",
    ]

    # Executive Summary
    lines += ["## 📋 Executive Summary", "", d.get("executive_summary", "–"), ""]

    # Vollständigkeit
    cc = d.get("completeness_check", {})
    missing_docs = cc.get("missing_documents", [])
    missing_pts = cc.get("missing_data_points", [])
    lines += ["## ✅ Vollständigkeitsprüfung", ""]
    if missing_docs:
        lines += ["**Fehlende Dokumente:**"]
        lines += [f"- {m}" for m in missing_docs]
        lines += [""]
    if missing_pts:
        lines += ["**Fehlende Datenpunkte:**"]
        lines += [f"- {m}" for m in missing_pts]
        lines += [""]
    if not missing_docs and not missing_pts:
        lines += ["Alle relevanten Dokumente vorhanden.", ""]

    # KPIs
    kpis = d.get("kpis", {})

    def fmt(val, suffix=""):
        return f"{val:,.2f}{suffix}" if val is not None else "–"

    lines += [
        "## 📊 Kennzahlen",
        "",
        "| Kennzahl | Wert |",
        "| :--- | ---: |",
        f"| Kaufpreis pro m² | {fmt(kpis.get('price_per_sqm_eur'), ' €')} |",
        f"| Kaufpreisfaktor | {fmt(kpis.get('rent_multiplier'), 'x')} |",
        f"| Bruttomietrendite | {fmt(kpis.get('gross_yield_percent'), ' %')} |",
        f"| Nettomietrendite | {fmt(kpis.get('net_yield_percent'), ' %')} |",
        f"| Cashflow vor Finanzierung | {fmt(kpis.get('cashflow_pre_financing_eur'), ' €/J')} |",
        f"| Cashflow nach Finanzierung | {fmt(kpis.get('cashflow_post_financing_eur'), ' €/J')} |",
        f"| Betriebskostenquote | {fmt(kpis.get('operating_cost_ratio_percent'), ' %')} |",
        "",
    ]
    if kpis.get("reserve_need_notes"):
        lines += [f"**Rücklage:** {kpis['reserve_need_notes']}", ""]
    if kpis.get("sensitivity_analysis_notes"):
        lines += [f"**Sensitivität:** {kpis['sensitivity_analysis_notes']}", ""]

    # Risikoanalyse
    ra = d.get("risk_assessment", {})
    lines += [
        "## ⚠️ Risikoanalyse",
        "",
        "| Kategorie | Bewertung |",
        "| :--- | :--- |",
        f"| Rechtlich | {_badge(ra.get('legal', '–'))} |",
        f"| Wirtschaftlich | {_badge(ra.get('financial', '–'))} |",
        f"| Technisch | {_badge(ra.get('technical', '–'))} |",
        f"| Standort | {_badge(ra.get('location', '–'))} |",
        f"| Mietausfall | {_badge(ra.get('tenant_default', '–'))} |",
        "",
    ]

    # Red Flags
    red_flags = d.get("red_flags", [])
    if red_flags:
        lines += ["## 🚩 Red Flags", ""]
        for f in sorted(
            red_flags,
            key=lambda x: ["Critical", "High", "Medium", "Low"].index(
                x.get("severity", "Low")
            ),
        ):
            lines += [
                f"**[{f.get('severity')}] {f.get('category')}** — {f.get('description')}  ",
                f"*Quelle: {f.get('source_document', '–')}*",
                "",
            ]

    # Rechtliche Risiken
    legal_risks = d.get("legal_risks", [])
    if legal_risks:
        lines += ["## ⚖️ Rechtliche Risiken", ""]
        lines += [f"- {r}" for r in legal_risks]
        lines += [""]

    # Stärken / Schwächen
    strengths = d.get("strengths", [])
    weaknesses = d.get("weaknesses", [])
    if strengths or weaknesses:
        lines += ["## 💪 Stärken / Schwächen", ""]
        if strengths:
            lines += ["**Stärken:**"]
            lines += [f"- {s}" for s in strengths]
            lines += [""]
        if weaknesses:
            lines += ["**Schwächen:**"]
            lines += [f"- {w}" for w in weaknesses]
            lines += [""]

    # Investment-Score
    sc = d.get("investment_score", {})
    score_val = sc.get("score", "–")
    classification = sc.get("classification", "–")
    lines += [
        f"## 🎯 Investment-Score: {score_val}/100",
        f"**{classification}**",
        "",
        sc.get("score_explanation", ""),
        "",
    ]

    # Offene Punkte
    open_q = d.get("open_questions", [])
    if open_q:
        lines += ["## ❓ Offene Punkte", ""]
        lines += [f"- {q}" for q in open_q]
        lines += [""]

    # Empfehlung
    rec = d.get("recommendation", "–")
    rec_icon = {"Kaufen": "✅", "Nachverhandeln": "⚠️", "Abstand nehmen": "❌"}.get(
        rec, "📌"
    )
    lines += ["## 📌 Empfehlung", "", f"### {rec_icon} {rec}", ""]

    # Analysierte Dokumente
    doc_types = d.get("document_types_analyzed", [])
    if doc_types:
        lines += ["---", "", "**Analysierte Dokumente:** " + " · ".join(doc_types), ""]

    return "\n".join(lines)


def save_report(markdown: str, output_path: str) -> str:
    Path(output_path).parent.mkdir(parents=True, exist_ok=True)
    Path(output_path).write_text(markdown, encoding="utf-8")
    return output_path
