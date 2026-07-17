from datetime import datetime
from pathlib import Path

from src.logging_utils import get_logger

logger = get_logger("pdf_generator")


def _badge(level: str) -> str:
    icons = {"Low": "🟢", "Medium": "🟡", "High": "🔴", "Critical": "⛔"}
    return f"{icons.get(level, '⚪')} {level}"


def _fmt(val, suffix: str = "") -> str:
    if val is None:
        return "–"
    if isinstance(val, (int, float)):
        return f"{val:,.2f}{suffix}"
    return str(val)


def _first(source: dict, *keys):
    """Return the first present, non-None value among candidate keys.

    Tolerates schema drift where the backend occasionally returns a
    slightly different field name for the same value (e.g. 'gross_yield_pct'
    instead of 'gross_yield_percent').
    """
    for key in keys:
        val = source.get(key)
        if val is not None:
            return val
    return None


def _fmt_rent_value(value) -> str:
    """Render a rent/income value that may be a plain number, a free-text
    description, or a nested dict ({monthly_eur, annual_eur, per_sqm_eur, notes})."""
    if value is None:
        return "–"
    if isinstance(value, (int, float)):
        return _fmt(value, " €/Jahr")
    if isinstance(value, str):
        return value
    if isinstance(value, dict):
        parts = []
        if value.get("annual_eur") is not None:
            parts.append(_fmt(value["annual_eur"], " €/Jahr"))
        if value.get("monthly_eur") is not None:
            parts.append(_fmt(value["monthly_eur"], " €/Monat"))
        if value.get("per_sqm_eur") is not None:
            parts.append(f"{_fmt(value['per_sqm_eur'], ' €/m²')}")
        text = ", ".join(parts) if parts else "–"
        if value.get("notes"):
            text += f" – {value['notes']}"
        return text
    return str(value)


def generate_markdown(json_data: dict, elapsed_display: str | None = None) -> str:
    d = json_data
    address = d.get("property_address") or "–"
    logger.info("generate_markdown: erstelle Bericht fuer %s", address)
    created_at = datetime.now().strftime("%d.%m.%Y %H:%M Uhr")
    lines: list[str] = []
    fmt = _fmt

    lines += [
        f"# 🏠 Due Diligence Bericht",
        f"**Objekt:** {address}  ",
        f"**Erstellt:** {created_at}  ",
    ]
    if elapsed_display:
        lines += [f"**Analysedauer:** {elapsed_display}  "]
    lines += [
        f"**Gesamtrisiko:** {_badge(d.get('overall_risk_level', '–'))}",
        "",
        "---",
        "",
    ]

    # Executive Summary
    lines += ["## 📋 Executive Summary", "", d.get("executive_summary", "–"), ""]

    # Vollständigkeit
    cc = d.get("completeness_check") or {}
    # Canonical schema fields (matching Skill 1's own field names).
    missing_docs = (cc.get("missing_core_documents") or []) + (
        cc.get("missing_recommended_documents") or []
    )
    if not missing_docs:
        # Legacy backend runs used a single flat 'missing_documents' field.
        missing_docs = cc.get("missing_documents") or []
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

    # Dokumenteninventar (Skill 1)
    inv = d.get("document_inventory")
    if not inv and cc.get("documents") is not None:
        # Some backend runs nest the Skill-1 inventory inside
        # completeness_check instead of the dedicated top-level field.
        inv = cc
    if inv:
        lines += ["## 🗂️ Dokumenteninventar", ""]
        if inv.get("overall_document_quality"):
            lines += [f"**Gesamtqualität:** {inv['overall_document_quality']}", ""]
        docs = inv.get("documents", [])
        if docs:
            lines += [
                "| Datei | Typ | Seiten | Datum | Lesbarkeit |",
                "| :--- | :--- | ---: | :--- | :--- |",
            ]
            for doc in docs:
                page_count = doc.get("page_count")
                lines += [
                    f"| {doc.get('file_name', '–')} | {doc.get('document_type', '–')} | "
                    f"{page_count if page_count is not None else '–'} | "
                    f"{doc.get('issue_date') or '–'} | {doc.get('readability', '–')} |"
                ]
            lines += [""]
        if inv.get("missing_core_documents"):
            lines += ["**Fehlende Kerndokumente:**"]
            lines += [f"- {m}" for m in inv["missing_core_documents"]]
            lines += [""]
        if inv.get("missing_recommended_documents"):
            lines += ["**Fehlende empfohlene Dokumente:**"]
            lines += [f"- {m}" for m in inv["missing_recommended_documents"]]
            lines += [""]
        if inv.get("inventory_notes"):
            lines += [f"*{inv['inventory_notes']}*", ""]

    # Wirtschaftliche Zusammenfassung
    fs = d.get("financial_summary")
    if fs:
        current_rent = _first(fs, "current_rent_annual_eur", "current_rent")
        market_rent = _first(fs, "estimated_market_rent_annual_eur", "market_rent")
        vacancy_rate = _first(fs, "vacancy_rate_percent")
        # Older backend runs returned a free-text assessment instead of a rate.
        vacancy_risk = _first(fs, "vacancy_risk_assessment", "vacancy_risk")
        maintenance_backlog = _first(
            fs, "maintenance_backlog_notes", "maintenance_backlog"
        )
        lines += [
            "## 💰 Wirtschaftliche Zusammenfassung",
            "",
            f"**Ist-Miete:** {_fmt_rent_value(current_rent)}  ",
            f"**Marktmiete:** {_fmt_rent_value(market_rent)}",
            "",
        ]
        if vacancy_rate is not None:
            lines += [f"**Leerstandsquote:** {fmt(vacancy_rate, ' %')}", ""]
        elif vacancy_risk:
            lines += [f"**Leerstandsrisiko:** {vacancy_risk}", ""]
        if maintenance_backlog:
            lines += [f"**Instandhaltungsrückstau:** {maintenance_backlog}", ""]

    # KPIs
    kpis = d.get("kpis", {})

    lines += [
        "## 📊 Kennzahlen",
        "",
        "| Kennzahl | Wert |",
        "| :--- | ---: |",
        f"| Kaufpreis | {fmt(_first(kpis, 'purchase_price_eur'), ' €')} |",
        f"| Wohn-/Nutzfläche | {fmt(_first(kpis, 'total_area_sqm'), ' m²')} |",
        f"| Kaufpreis pro m² | {fmt(_first(kpis, 'price_per_sqm_eur', 'price_per_sqm'), ' €')} |",
        f"| Marktpreis pro m² | {fmt(_first(kpis, 'market_price_per_sqm_eur'), ' €')} |",
        f"| Abweichung vom Marktpreis | {fmt(_first(kpis, 'price_vs_market_percent'), ' %')} |",
        f"| Potenzielle Jahresmiete | {fmt(_first(kpis, 'potential_rent_annual_eur'), ' €')} |",
        f"| Kaufpreisfaktor | {fmt(_first(kpis, 'rent_multiplier'), 'x')} |",
        f"| Bruttomietrendite | {fmt(_first(kpis, 'gross_yield_percent', 'gross_yield_pct'), ' %')} |",
        f"| Nettomietrendite | {fmt(_first(kpis, 'net_yield_percent', 'net_yield_pct'), ' %')} |",
        f"| Erwerbsnebenkosten | {fmt(_first(kpis, 'acquisition_costs_total_eur'), ' €')} |",
        f"| Betriebskosten p.a. | {fmt(_first(kpis, 'operating_costs_annual_eur'), ' €')} |",
        f"| Instandhaltungsrücklage p.a. | {fmt(_first(kpis, 'maintenance_reserve_annual_eur'), ' €')} |",
        f"| Cashflow vor Finanzierung | {fmt(_first(kpis, 'cashflow_pre_financing_eur', 'cashflow_before_financing_eur'), ' €/J')} |",
        f"| Cashflow nach Finanzierung | {fmt(_first(kpis, 'cashflow_post_financing_eur', 'cashflow_after_financing_eur'), ' €/J')} |",
        f"| Betriebskostenquote | {fmt(_first(kpis, 'operating_cost_ratio_percent', 'operating_cost_ratio_pct'), ' %')} |",
        f"| Break-Even-Vermietungsquote | {fmt(_first(kpis, 'break_even_occupancy_percent', 'break_even_occupancy_pct'), ' %')} |",
        "",
    ]
    scenarios = kpis.get("sensitivity_scenarios")
    if isinstance(scenarios, dict) and scenarios:
        known_scenario_keys = {
            "base_case_cashflow_eur",
            "optimistic_cashflow_eur",
            "pessimistic_cashflow_eur",
        }
        if known_scenario_keys & scenarios.keys():
            lines += [
                "**Sensitivitätsszenarien (Cashflow):**",
                "",
                "| Szenario | Cashflow |",
                "| :--- | ---: |",
                f"| Positiv | {fmt(scenarios.get('optimistic_cashflow_eur'), ' €/J')} |",
                f"| Basis | {fmt(scenarios.get('base_case_cashflow_eur'), ' €/J')} |",
                f"| Negativ | {fmt(scenarios.get('pessimistic_cashflow_eur'), ' €/J')} |",
                "",
            ]
            if scenarios.get("sensitivity_notes"):
                lines += [f"*{scenarios['sensitivity_notes']}*", ""]
        else:
            # Alternate shape: dict of freely named scenarios, each with its
            # own nested metrics (e.g. 'optimistisch_70pct_auslastung': {...}).
            lines += [
                "**Sensitivitätsszenarien:**",
                "",
                "| Szenario | Jahresmiete | Bruttorendite | Nettorendite | Cashflow vor Fin. | Cashflow nach Fin. |",
                "| :--- | ---: | ---: | ---: | ---: | ---: |",
            ]
            for name, metrics in scenarios.items():
                if not isinstance(metrics, dict):
                    continue
                label = name.replace("_", " ").capitalize()
                lines.append(
                    f"| {label} | "
                    f"{fmt(_first(metrics, 'jahresmiete_brutto_eur'), ' €')} | "
                    f"{fmt(_first(metrics, 'bruttomietrendite_pct'), ' %')} | "
                    f"{fmt(_first(metrics, 'nettomietrendite_pct'), ' %')} | "
                    f"{fmt(_first(metrics, 'cashflow_vor_finanzierung_eur'), ' €')} | "
                    f"{fmt(_first(metrics, 'cashflow_nach_finanzierung_eur'), ' €')} |"
                )
            lines += [""]
    if kpis.get("reserve_need_notes"):
        lines += [f"**Rücklage:** {kpis['reserve_need_notes']}", ""]
    if kpis.get("assumptions_and_limitations"):
        lines += [
            f"**Annahmen/Einschränkungen:** {kpis['assumptions_and_limitations']}",
            "",
        ]
    if kpis.get("sensitivity_analysis_notes"):
        # Legacy field name (removed from schema; kept as fallback for
        # older captured outputs that still used it).
        lines += [f"**Sensitivität:** {kpis['sensitivity_analysis_notes']}", ""]
    if kpis.get("kpi_notes"):
        lines += [f"**Hinweise:** {kpis['kpi_notes']}", ""]

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

    # Grundbuch- und Eigentumsanalyse (Skill 2)
    grundbuch = d.get("grundbuch")
    if grundbuch:
        lines += ["## 📜 Grundbuch- & Eigentumsanalyse", ""]
        own = grundbuch.get("ownership") or {}
        if own:
            lines += [
                f"**Eigentümer:** {own.get('owner_name') or '–'} ({own.get('owner_type', '–')})",
                "",
            ]
            if own.get("co_owners"):
                lines += ["**Miteigentümer:** " + ", ".join(own["co_owners"]), ""]
            if own.get("recent_transfers"):
                lines += ["**Jüngste Eigentumswechsel:**"]
                lines += [f"- {t}" for t in own["recent_transfers"]]
                lines += [""]
            if own.get("ownership_notes"):
                lines += [f"*{own['ownership_notes']}*", ""]
        encumbrances = grundbuch.get("encumbrances", [])
        if encumbrances:
            lines += [
                "**Lasten (Abteilung II):**",
                "",
                "| Art | Begünstigter | Beschreibung | Risiko | Löschbar |",
                "| :--- | :--- | :--- | :--- | :--- |",
            ]
            for e in encumbrances:
                deletable = {True: "Ja", False: "Nein"}.get(e.get("is_deletable"), "–")
                lines += [
                    f"| {e.get('type', '–')} | {e.get('beneficiary', '–')} | "
                    f"{e.get('description', '–')} | {_badge(e.get('risk_level', '–'))} | {deletable} |"
                ]
            lines += [""]
        mortgages = grundbuch.get("mortgages", [])
        if mortgages:
            lines += [
                "**Grundschulden/Hypotheken (Abteilung III):**",
                "",
                "| Gläubiger | Betrag | Rang | Typ | Anmerkung |",
                "| :--- | ---: | :--- | :--- | :--- |",
            ]
            for m in mortgages:
                lines += [
                    f"| {m.get('creditor', '–')} | {fmt(m.get('amount_eur'), ' €')} | "
                    f"{m.get('rank', '–')} | {m.get('type', '–')} | {m.get('notes', '–')} |"
                ]
            lines += [""]
        lines += [
            f"**Gesamtbelastung:** {fmt(grundbuch.get('total_mortgage_burden_eur'), ' €')}  ",
            f"**Grundstücksfläche:** {fmt(grundbuch.get('land_area_sqm'), ' m²')}",
            "",
        ]
        if grundbuch.get("priority_risks"):
            lines += ["**Prioritäre Risiken:**"]
            lines += [f"- {r}" for r in grundbuch["priority_risks"]]
            lines += [""]
        lines += [
            f"**Risikobewertung Grundbuch:** {_badge(grundbuch.get('grundbuch_risk_level', '–'))}",
            "",
        ]
        if grundbuch.get("grundbuch_notes"):
            lines += [f"*{grundbuch['grundbuch_notes']}*", ""]

    # Mietvertrags- und Mieteranalyse (Skill 3)
    miete = d.get("mietanalyse")
    if miete:
        lines += ["## 🏘️ Mietvertrags- & Mieteranalyse", ""]
        total_units = miete.get("total_units")
        occupied_units = miete.get("occupied_units")
        vacancy_count = miete.get("vacancy_count")
        lines += [
            "| Kennzahl | Wert |",
            "| :--- | ---: |",
            f"| Einheiten gesamt | {total_units if total_units is not None else '–'} |",
            f"| Vermietet | {occupied_units if occupied_units is not None else '–'} |",
            f"| Leerstand | {vacancy_count if vacancy_count is not None else '–'} |",
            f"| Leerstandsquote | {fmt(miete.get('vacancy_rate_percent'), ' %')} |",
            f"| Ist-Miete p.a. | {fmt(miete.get('current_rent_annual_eur'), ' €')} |",
            f"| Markt-Miete p.a. | {fmt(miete.get('estimated_market_rent_annual_eur'), ' €')} |",
            f"| Mietsteigerungspotenzial | {fmt(miete.get('rent_potential_delta_eur'), ' €')} |",
            "",
        ]
        units = miete.get("rental_units", [])
        if units:
            lines += [
                "**Mieteinheiten:**",
                "",
                "| Einheit | Mieter | Typ | Fläche | Kaltmiete | Indexmiete | Vertragsende | Risiko |",
                "| :--- | :--- | :--- | ---: | ---: | :--- | :--- | :--- |",
            ]
            for u in units:
                index_flag = "Ja" if u.get("index_rent_clause") else "Nein"
                end = u.get("contract_end") or (
                    "unbefristet" if u.get("is_indefinite") else "–"
                )
                lines += [
                    f"| {u.get('unit_id', '–')} | {u.get('tenant_name') or '–'} | {u.get('tenant_type', '–')} | "
                    f"{fmt(u.get('area_sqm'), ' m²')} | {fmt(u.get('net_rent_monthly_eur'), ' €')} | "
                    f"{index_flag} | {end} | {_badge(u.get('tenant_default_risk', '–'))} |"
                ]
            lines += [""]
            for u in units:
                if u.get("problematic_clauses"):
                    lines += [f"**Problematische Klauseln ({u.get('unit_id', '–')}):**"]
                    lines += [f"- {c}" for c in u["problematic_clauses"]]
                    lines += [""]
        if miete.get("key_findings"):
            lines += ["**Wesentliche Erkenntnisse:**"]
            lines += [f"- {k}" for k in miete["key_findings"]]
            lines += [""]
        lines += [
            f"**Risikobewertung Mietanalyse:** {_badge(miete.get('overall_lease_risk', '–'))}",
            "",
        ]
        if miete.get("mietanalyse_notes"):
            lines += [f"*{miete['mietanalyse_notes']}*", ""]

    # Technische und bauliche Prüfung (Skill 5)
    tech = d.get("technical")
    if tech:
        lines += ["## 🔧 Technische & bauliche Prüfung", ""]
        lines += [
            f"**Baujahr:** {tech.get('building_year') or '–'}  ",
            f"**Letzte Modernisierung:** {tech.get('last_major_renovation') or '–'}",
            "",
        ]
        ec = tech.get("energy_certificate") or {}
        if ec:
            lines += [
                "**Energieausweis:**",
                "",
                "| Merkmal | Wert |",
                "| :--- | ---: |",
                f"| Effizienzklasse | {ec.get('efficiency_class') or '–'} |",
                f"| Primärenergiebedarf | {fmt(ec.get('primary_energy_kwh'), ' kWh/m²a')} |",
                f"| Energieträger | {ec.get('energy_carrier') or '–'} |",
                f"| Baujahr Heizung | {ec.get('heating_system_year') or '–'} |",
                "",
            ]
            if ec.get("mandatory_upgrades"):
                lines += ["**Pflichtmaßnahmen (GEG):**"]
                lines += [f"- {u}" for u in ec["mandatory_upgrades"]]
                lines += [""]
            if ec.get("geg_compliance_notes"):
                lines += [f"*{ec['geg_compliance_notes']}*", ""]
        defects = tech.get("defects", [])
        if defects:
            lines += [
                "**Mängel:**",
                "",
                "| Bauteil | Beschreibung | Schwere | Kostenschätzung |",
                "| :--- | :--- | :--- | ---: |",
            ]
            for defect in defects:
                lines += [
                    f"| {defect.get('component', '–')} | {defect.get('description', '–')} | "
                    f"{defect.get('severity', '–')} | {fmt(defect.get('cost_estimate_eur'), ' €')} |"
                ]
            lines += [""]
        inv_needs = tech.get("investment_needs") or {}
        if inv_needs:
            lines += [
                "**Investitionsbedarf:**",
                "",
                "| Zeithorizont | Von | Bis |",
                "| :--- | ---: | ---: |",
                f"| Kurzfristig (0–2 J.) | {fmt(inv_needs.get('short_term_eur_min'), ' €')} | {fmt(inv_needs.get('short_term_eur_max'), ' €')} |",
                f"| Mittelfristig (2–5 J.) | {fmt(inv_needs.get('mid_term_eur_min'), ' €')} | {fmt(inv_needs.get('mid_term_eur_max'), ' €')} |",
                f"| Langfristig (5–15 J.) | {fmt(inv_needs.get('long_term_eur_min'), ' €')} | {fmt(inv_needs.get('long_term_eur_max'), ' €')} |",
                f"| **Gesamt** | **{fmt(inv_needs.get('total_min_eur'), ' €')}** | **{fmt(inv_needs.get('total_max_eur'), ' €')}** |",
                "",
            ]
        if tech.get("maintenance_backlog_notes"):
            lines += [
                f"**Instandhaltungsrückstau:** {tech['maintenance_backlog_notes']}",
                "",
            ]
        if tech.get("upside_potential_notes"):
            lines += [
                f"**Wertsteigerungspotenzial:** {tech['upside_potential_notes']}",
                "",
            ]
        lines += [
            f"**Risikobewertung Technik:** {_badge(tech.get('technical_risk_level', '–'))}",
            "",
        ]
        if tech.get("technical_notes"):
            lines += [f"*{tech['technical_notes']}*", ""]

    # WEG-Analyse (Skill 6)
    weg = d.get("weg")
    if weg:
        lines += ["## 🏢 WEG-Analyse", ""]
        lines += [
            "| Kennzahl | Wert |",
            "| :--- | ---: |",
            f"| Hausgeld monatlich | {fmt(weg.get('monthly_hausgeld_eur'), ' €')} |",
            f"| Instandhaltungsrücklage gesamt | {fmt(weg.get('maintenance_reserve_total_eur'), ' €')} |",
            f"| Rücklage pro m² | {fmt(weg.get('reserve_per_sqm_eur'), ' €')} |",
            "",
        ]
        manager_line = f"**Hausverwaltung:** {weg.get('property_manager') or '–'}"
        if weg.get("manager_contract_end"):
            manager_line += f" (Vertrag bis {weg['manager_contract_end']})"
        lines += [
            f"**Rücklagenbewertung:** {weg.get('reserve_adequacy', '–')}  ",
            manager_line,
            "",
        ]
        measures = weg.get("planned_measures", [])
        if measures:
            lines += [
                "**Geplante Maßnahmen:**",
                "",
                "| Beschreibung | Beschluss | Kosten | Auswirkung für Käufer | Status |",
                "| :--- | :--- | ---: | :--- | :--- |",
            ]
            for m in measures:
                lines += [
                    f"| {m.get('description', '–')} | {m.get('decision_date') or '–'} | "
                    f"{fmt(m.get('estimated_cost_eur'), ' €')} | {m.get('buyer_impact', '–')} | {m.get('status', '–')} |"
                ]
            lines += [""]
        levies = weg.get("special_levies", [])
        if levies:
            lines += [
                "**Sonderumlagen:**",
                "",
                "| Beschreibung | Gesamt | Pro Einheit | Fällig | Status |",
                "| :--- | ---: | ---: | :--- | :--- |",
            ]
            for lvy in levies:
                lines += [
                    f"| {lvy.get('description', '–')} | {fmt(lvy.get('amount_total_eur'), ' €')} | "
                    f"{fmt(lvy.get('amount_unit_eur'), ' €')} | {lvy.get('due_date') or '–'} | {lvy.get('status', '–')} |"
                ]
            lines += [""]
        if weg.get("legal_disputes"):
            lines += ["**Rechtsstreitigkeiten:**"]
            lines += [f"- {ld}" for ld in weg["legal_disputes"]]
            lines += [""]
        if weg.get("arrears_situation"):
            lines += [f"**Zahlungsrückstände:** {weg['arrears_situation']}", ""]
        lines += [
            f"**Risikobewertung WEG:** {_badge(weg.get('weg_risk_level', '–'))}",
            "",
        ]
        if weg.get("weg_notes"):
            lines += [f"*{weg['weg_notes']}*", ""]

    # Standort- und Marktanalyse (Skill 7)
    standort = d.get("standort")
    if standort:
        lines += ["## 📍 Standort- & Marktanalyse", ""]
        loc_line = (
            " / ".join(filter(None, [standort.get("city"), standort.get("district")]))
            or "–"
        )
        macro_score = standort.get("macro_location_score")
        micro_score = standort.get("micro_location_score")
        transport_min = standort.get("public_transport_minutes")
        lines += [
            f"**Lage:** {loc_line}",
            "",
            "| Kennzahl | Wert |",
            "| :--- | ---: |",
            f"| Makrolage-Score | {macro_score if macro_score is not None else '–'}/5 |",
            f"| Mikrolage-Score | {micro_score if micro_score is not None else '–'}/5 |",
            f"| Bevölkerungstrend | {standort.get('population_trend', '–')} |",
            f"| Arbeitslosenquote | {fmt(standort.get('unemployment_rate_pct'), ' %')} |",
            f"| ÖPNV-Anbindung | {f'{transport_min} Min.' if transport_min is not None else '–'} |",
            f"| Marktmiete pro m² | {fmt(standort.get('market_rent_per_sqm_eur'), ' €')} |",
            f"| Marktpreis pro m² | {fmt(standort.get('market_price_per_sqm_eur'), ' €')} |",
            f"| Mietentwicklung (3 Jahre) | {fmt(standort.get('rent_trend_3y_pct'), ' %')} |",
            f"| Leerstandsquote Markt | {fmt(standort.get('vacancy_rate_market_pct'), ' %')} |",
            f"| Hochwasserrisiko (ZÜRS) | {standort.get('flood_risk_zone') or '–'} |",
            f"| Altlastenrisiko | {standort.get('contamination_risk', '–')} |",
            f"| Milieuschutz | {'Ja' if standort.get('milieuschutz') else 'Nein'} |",
            "",
        ]
        if standort.get("infrastructure_notes"):
            lines += [f"**Infrastruktur:** {standort['infrastructure_notes']}", ""]
        if standort.get("location_strengths"):
            lines += ["**Standortstärken:**"]
            lines += [f"- {s}" for s in standort["location_strengths"]]
            lines += [""]
        if standort.get("risk_factors"):
            lines += ["**Standortrisiken:**"]
            lines += [f"- {r}" for r in standort["risk_factors"]]
            lines += [""]
        lines += [
            f"**Risikobewertung Standort:** {_badge(standort.get('location_risk_level', '–'))}",
            "",
        ]
        if standort.get("location_notes"):
            lines += [f"*{standort['location_notes']}*", ""]
        if standort.get("data_sources"):
            lines += ["*Quellen: " + " · ".join(standort["data_sources"]) + "*", ""]

    # Rechtliche Risikoprüfung - Detail (Skill 8)
    legal_detail = d.get("legal")
    legal_risks = d.get("legal_risks")
    if legal_detail is None and isinstance(legal_risks, dict):
        # Some backend runs place the full Skill-8 detail object under
        # 'legal_risks' instead of the dedicated 'legal' field.
        legal_detail = legal_risks
        legal_risks = legal_detail.get("all_legal_risks", [])
    if legal_detail:
        lines += ["## ⚖️ Rechtliche Risikoprüfung (Detail)", ""]
        pc_risks = legal_detail.get("purchase_contract_risks", [])
        if pc_risks:
            lines += [
                "**Kaufvertrag:**",
                "",
                "| Klausel | Beschreibung | Rechtsgrundlage | Schwere | Empfehlung |",
                "| :--- | :--- | :--- | :--- | :--- |",
            ]
            for r in pc_risks:
                lines += [
                    f"| {r.get('clause', '–')} | {r.get('description', '–')} | "
                    f"{r.get('legal_basis', '–')} | {r.get('severity', '–')} | {r.get('recommendation', '–')} |"
                ]
            lines += [""]
        tl_risks = legal_detail.get("tenancy_law_risks", [])
        if tl_risks:
            lines += [
                "**Mietrecht:**",
                "",
                "| Typ | Beschreibung | Schwere | Empfehlung |",
                "| :--- | :--- | :--- | :--- |",
            ]
            for r in tl_risks:
                lines += [
                    f"| {r.get('type', '–')} | {r.get('description', '–')} | "
                    f"{r.get('severity', '–')} | {r.get('recommendation', '–')} |"
                ]
            lines += [""]
        if legal_detail.get("public_law_issues"):
            lines += ["**Öffentlich-rechtliche Themen:**"]
            lines += [f"- {p}" for p in legal_detail["public_law_issues"]]
            lines += [""]
        if legal_detail.get("tax_notes"):
            lines += [f"**Steuerliche Hinweise:** {legal_detail['tax_notes']}", ""]
        if legal_detail.get("warranty_exclusion_assessment"):
            lines += [
                f"**Gewährleistungsausschluss:** {legal_detail['warranty_exclusion_assessment']}",
                "",
            ]
        lines += [
            f"**Risikobewertung Recht:** {_badge(legal_detail.get('legal_risk_level', '–'))}",
            "",
        ]
        if legal_detail.get("legal_notes"):
            lines += [f"*{legal_detail['legal_notes']}*", ""]

    # Zusammenfassung rechtlicher Risiken (aggregiert aus Skills 2, 3, 8)
    if legal_risks:
        lines += ["## ⚖️ Zusammenfassung rechtlicher Risiken", ""]
        for r in legal_risks:
            if isinstance(r, dict):
                severity = r.get("severity")
                label = r.get("category") or r.get("type") or r.get("clause")
                desc = r.get("description") or r.get("recommendation") or ""
                prefix = f"**[{severity}]** " if severity else ""
                label_part = f"{label}: " if label else ""
                lines.append(f"- {prefix}{label_part}{desc}")
            else:
                lines.append(f"- {r}")
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
    ]
    breakdown = sc.get("score_breakdown")
    if breakdown:
        lines += [
            "| Kategorie | Punkte |",
            "| :--- | ---: |",
            f"| Standort (max. 20) | {breakdown.get('location_score', '–')} |",
            f"| Wirtschaftlichkeit (max. 25) | {breakdown.get('financial_score', '–')} |",
            f"| Technik (max. 20) | {breakdown.get('technical_score', '–')} |",
            f"| Recht (max. 20) | {breakdown.get('legal_score', '–')} |",
            f"| WEG (max. 10) | {breakdown.get('weg_score', '–')} |",
            f"| Vollständigkeit (max. 5) | {breakdown.get('completeness_score', '–')} |",
            "",
        ]
    lines += [sc.get("score_explanation", ""), ""]

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
    if d.get("recommendation_reasoning"):
        lines += [d["recommendation_reasoning"], ""]

    # Analysierte Dokumente
    doc_types = d.get("document_types_analyzed", [])
    if doc_types:
        lines += ["---", "", "**Analysierte Dokumente:** " + " · ".join(doc_types), ""]

    markdown = "\n".join(lines)
    logger.debug(
        "generate_markdown: fertig, %d Zeichen / %d Zeilen", len(markdown), len(lines)
    )
    return markdown


def save_report(markdown: str, output_path: str) -> str:
    Path(output_path).parent.mkdir(parents=True, exist_ok=True)
    Path(output_path).write_text(markdown, encoding="utf-8")
    logger.info(
        "save_report: Bericht gespeichert unter %s (%d Zeichen)",
        output_path,
        len(markdown),
    )
    return output_path
