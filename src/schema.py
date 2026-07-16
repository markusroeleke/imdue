"""JSON Schema for the final Due-Diligence report (`structured_output_schema`).

Mirrors the aggregation performed by dd-skill-10-orchestrator (see
.github/skills/dd-skill-10-orchestrator/SKILL.md), which merges the outputs
of skills 1-9. In addition to the condensed, top-level summary fields
(executive_summary, kpis, investment_score, ...), this schema also requests
the full, detailed output of each individual skill - Dokumentinventar
(Skill 1), Grundbuch (Skill 2), Mietanalyse (Skill 3), erweiterte
Finanzkennzahlen (Skill 4), Technik (Skill 5), WEG (Skill 6), Standort
(Skill 7) und Recht (Skill 8) - so the generated report can be as
comprehensive as the underlying skill runs, not just a condensed summary.

Skills that were not executed for a given property (see
skill_execution_flags of Skill 1, e.g. no WEG analysis for a
Einfamilienhaus) should have their corresponding detail section returned as
`null`.
"""

RISK_LEVEL_ENUM = ["Low", "Medium", "High", "Critical"]


def _risk_level_field() -> dict:
    return {"type": "string", "enum": list(RISK_LEVEL_ENUM)}


# --- Skill 1: Dokument-Inventarisierung ------------------------------------

_document_entry_schema = {
    "type": "object",
    "properties": {
        "file_name": {"type": "string"},
        "document_type": {"type": "string"},
        "page_count": {"type": ["integer", "null"]},
        "issue_date": {"type": ["string", "null"]},
        "readability": {
            "type": "string",
            "enum": ["gut", "teilweise_unleserlich", "stark_beeintraechtigt"],
        },
        "notes": {"type": "string"},
    },
    "required": [
        "file_name",
        "document_type",
        "page_count",
        "issue_date",
        "readability",
        "notes",
    ],
    "additionalProperties": False,
}

DOCUMENT_INVENTORY_SCHEMA = {
    "type": ["object", "null"],
    "properties": {
        "documents": {"type": "array", "items": _document_entry_schema},
        "missing_core_documents": {"type": "array", "items": {"type": "string"}},
        "missing_recommended_documents": {
            "type": "array",
            "items": {"type": "string"},
        },
        "overall_document_quality": {
            "type": "string",
            "enum": ["vollstaendig", "ausreichend", "lueckenhaft", "unzureichend"],
        },
        "inventory_notes": {"type": "string"},
    },
    "required": [
        "documents",
        "missing_core_documents",
        "missing_recommended_documents",
        "overall_document_quality",
        "inventory_notes",
    ],
    "additionalProperties": False,
}

# --- Skill 2: Grundbuch- und Eigentumsanalyse ------------------------------

GRUNDBUCH_SCHEMA = {
    "type": ["object", "null"],
    "properties": {
        "ownership": {
            "type": "object",
            "properties": {
                "owner_name": {"type": ["string", "null"]},
                "owner_type": {
                    "type": "string",
                    "enum": [
                        "Einzelperson",
                        "GbR",
                        "GmbH",
                        "AG",
                        "Erbengemeinschaft",
                        "Sonstige",
                        "Unbekannt",
                    ],
                },
                "co_owners": {"type": "array", "items": {"type": "string"}},
                "recent_transfers": {"type": "array", "items": {"type": "string"}},
                "ownership_notes": {"type": "string"},
            },
            "required": [
                "owner_name",
                "owner_type",
                "co_owners",
                "recent_transfers",
                "ownership_notes",
            ],
            "additionalProperties": False,
        },
        "encumbrances": {
            "type": "array",
            "items": {
                "type": "object",
                "properties": {
                    "type": {"type": "string"},
                    "beneficiary": {"type": "string"},
                    "description": {"type": "string"},
                    "risk_level": _risk_level_field(),
                    "is_deletable": {"type": ["boolean", "null"]},
                },
                "required": [
                    "type",
                    "beneficiary",
                    "description",
                    "risk_level",
                    "is_deletable",
                ],
                "additionalProperties": False,
            },
        },
        "mortgages": {
            "type": "array",
            "items": {
                "type": "object",
                "properties": {
                    "creditor": {"type": "string"},
                    "amount_eur": {"type": ["number", "null"]},
                    "rank": {"type": "string"},
                    "type": {
                        "type": "string",
                        "enum": ["Grundschuld", "Hypothek", "Rentenschuld"],
                    },
                    "notes": {"type": "string"},
                },
                "required": ["creditor", "amount_eur", "rank", "type", "notes"],
                "additionalProperties": False,
            },
        },
        "total_mortgage_burden_eur": {"type": ["number", "null"]},
        "land_area_sqm": {"type": ["number", "null"]},
        "priority_risks": {"type": "array", "items": {"type": "string"}},
        "grundbuch_risk_level": _risk_level_field(),
        "grundbuch_notes": {"type": "string"},
    },
    "required": [
        "ownership",
        "encumbrances",
        "mortgages",
        "total_mortgage_burden_eur",
        "land_area_sqm",
        "priority_risks",
        "grundbuch_risk_level",
        "grundbuch_notes",
    ],
    "additionalProperties": False,
}

# --- Skill 3: Mietvertrags- und Mieteranalyse ------------------------------

MIETANALYSE_SCHEMA = {
    "type": ["object", "null"],
    "properties": {
        "rental_units": {
            "type": "array",
            "items": {
                "type": "object",
                "properties": {
                    "unit_id": {"type": "string"},
                    "tenant_name": {"type": ["string", "null"]},
                    "tenant_type": {
                        "type": "string",
                        "enum": [
                            "Privat",
                            "Gewerbe",
                            "Sozialeinrichtung",
                            "Leer",
                            "Unbekannt",
                        ],
                    },
                    "area_sqm": {"type": ["number", "null"]},
                    "contract_start": {"type": ["string", "null"]},
                    "contract_end": {"type": ["string", "null"]},
                    "is_indefinite": {"type": "boolean"},
                    "net_rent_monthly_eur": {"type": ["number", "null"]},
                    "ancillary_costs_eur": {"type": ["number", "null"]},
                    "last_rent_increase": {"type": ["string", "null"]},
                    "index_rent_clause": {"type": "boolean"},
                    "graduated_rent_clause": {"type": "boolean"},
                    "next_rent_adjustment": {"type": ["string", "null"]},
                    "special_clauses": {"type": "array", "items": {"type": "string"}},
                    "problematic_clauses": {
                        "type": "array",
                        "items": {"type": "string"},
                    },
                    "tenant_default_risk": _risk_level_field(),
                    "unit_notes": {"type": "string"},
                },
                "required": [
                    "unit_id",
                    "tenant_name",
                    "tenant_type",
                    "area_sqm",
                    "contract_start",
                    "contract_end",
                    "is_indefinite",
                    "net_rent_monthly_eur",
                    "ancillary_costs_eur",
                    "last_rent_increase",
                    "index_rent_clause",
                    "graduated_rent_clause",
                    "next_rent_adjustment",
                    "special_clauses",
                    "problematic_clauses",
                    "tenant_default_risk",
                    "unit_notes",
                ],
                "additionalProperties": False,
            },
        },
        "total_units": {"type": ["integer", "null"]},
        "occupied_units": {"type": ["integer", "null"]},
        "vacancy_count": {"type": ["integer", "null"]},
        "vacancy_rate_percent": {"type": ["number", "null"]},
        "current_rent_annual_eur": {"type": ["number", "null"]},
        "estimated_market_rent_annual_eur": {"type": ["number", "null"]},
        "rent_potential_delta_eur": {"type": ["number", "null"]},
        "overall_lease_risk": _risk_level_field(),
        "key_findings": {"type": "array", "items": {"type": "string"}},
        "mietanalyse_notes": {"type": "string"},
    },
    "required": [
        "rental_units",
        "total_units",
        "occupied_units",
        "vacancy_count",
        "vacancy_rate_percent",
        "current_rent_annual_eur",
        "estimated_market_rent_annual_eur",
        "rent_potential_delta_eur",
        "overall_lease_risk",
        "key_findings",
        "mietanalyse_notes",
    ],
    "additionalProperties": False,
}

# --- Skill 5: Technische und bauliche Pruefung -----------------------------

TECHNICAL_SCHEMA = {
    "type": ["object", "null"],
    "properties": {
        "building_year": {"type": ["integer", "null"]},
        "last_major_renovation": {"type": ["string", "null"]},
        "energy_certificate": {
            "type": "object",
            "properties": {
                "efficiency_class": {"type": ["string", "null"]},
                "primary_energy_kwh": {"type": ["number", "null"]},
                "energy_carrier": {"type": ["string", "null"]},
                "heating_system_year": {"type": ["integer", "null"]},
                "mandatory_upgrades": {"type": "array", "items": {"type": "string"}},
                "geg_compliance_notes": {"type": "string"},
            },
            "required": [
                "efficiency_class",
                "primary_energy_kwh",
                "energy_carrier",
                "heating_system_year",
                "mandatory_upgrades",
                "geg_compliance_notes",
            ],
            "additionalProperties": False,
        },
        "defects": {
            "type": "array",
            "items": {
                "type": "object",
                "properties": {
                    "component": {"type": "string"},
                    "description": {"type": "string"},
                    "severity": {
                        "type": "string",
                        "enum": ["kritisch", "hoch", "mittel", "gering"],
                    },
                    "cost_estimate_eur": {"type": ["number", "null"]},
                },
                "required": [
                    "component",
                    "description",
                    "severity",
                    "cost_estimate_eur",
                ],
                "additionalProperties": False,
            },
        },
        "investment_needs": {
            "type": "object",
            "properties": {
                "short_term_eur_min": {"type": ["number", "null"]},
                "short_term_eur_max": {"type": ["number", "null"]},
                "mid_term_eur_min": {"type": ["number", "null"]},
                "mid_term_eur_max": {"type": ["number", "null"]},
                "long_term_eur_min": {"type": ["number", "null"]},
                "long_term_eur_max": {"type": ["number", "null"]},
                "total_min_eur": {"type": ["number", "null"]},
                "total_max_eur": {"type": ["number", "null"]},
            },
            "required": [
                "short_term_eur_min",
                "short_term_eur_max",
                "mid_term_eur_min",
                "mid_term_eur_max",
                "long_term_eur_min",
                "long_term_eur_max",
                "total_min_eur",
                "total_max_eur",
            ],
            "additionalProperties": False,
        },
        "maintenance_backlog_notes": {"type": "string"},
        "upside_potential_notes": {"type": "string"},
        "technical_risk_level": _risk_level_field(),
        "technical_notes": {"type": "string"},
    },
    "required": [
        "building_year",
        "last_major_renovation",
        "energy_certificate",
        "defects",
        "investment_needs",
        "maintenance_backlog_notes",
        "upside_potential_notes",
        "technical_risk_level",
        "technical_notes",
    ],
    "additionalProperties": False,
}

# --- Skill 6: WEG-Analyse ---------------------------------------------------

WEG_SCHEMA = {
    "type": ["object", "null"],
    "properties": {
        "monthly_hausgeld_eur": {"type": ["number", "null"]},
        "maintenance_reserve_total_eur": {"type": ["number", "null"]},
        "reserve_per_sqm_eur": {"type": ["number", "null"]},
        "reserve_adequacy": {
            "type": "string",
            "enum": [
                "ausreichend",
                "grenzwertig",
                "unzureichend",
                "kritisch",
                "unbekannt",
            ],
        },
        "property_manager": {"type": ["string", "null"]},
        "manager_contract_end": {"type": ["string", "null"]},
        "planned_measures": {
            "type": "array",
            "items": {
                "type": "object",
                "properties": {
                    "description": {"type": "string"},
                    "decision_date": {"type": ["string", "null"]},
                    "estimated_cost_eur": {"type": ["number", "null"]},
                    "buyer_impact": {"type": "string"},
                    "status": {
                        "type": "string",
                        "enum": [
                            "beschlossen",
                            "geplant",
                            "diskutiert",
                            "abgeschlossen",
                        ],
                    },
                },
                "required": [
                    "description",
                    "decision_date",
                    "estimated_cost_eur",
                    "buyer_impact",
                    "status",
                ],
                "additionalProperties": False,
            },
        },
        "special_levies": {
            "type": "array",
            "items": {
                "type": "object",
                "properties": {
                    "description": {"type": "string"},
                    "amount_total_eur": {"type": ["number", "null"]},
                    "amount_unit_eur": {"type": ["number", "null"]},
                    "due_date": {"type": ["string", "null"]},
                    "status": {
                        "type": "string",
                        "enum": ["beschlossen", "drohend", "bezahlt"],
                    },
                },
                "required": [
                    "description",
                    "amount_total_eur",
                    "amount_unit_eur",
                    "due_date",
                    "status",
                ],
                "additionalProperties": False,
            },
        },
        "legal_disputes": {"type": "array", "items": {"type": "string"}},
        "arrears_situation": {"type": "string"},
        "weg_risk_level": _risk_level_field(),
        "weg_notes": {"type": "string"},
    },
    "required": [
        "monthly_hausgeld_eur",
        "maintenance_reserve_total_eur",
        "reserve_per_sqm_eur",
        "reserve_adequacy",
        "property_manager",
        "manager_contract_end",
        "planned_measures",
        "special_levies",
        "legal_disputes",
        "arrears_situation",
        "weg_risk_level",
        "weg_notes",
    ],
    "additionalProperties": False,
}

# --- Skill 7: Standort- und Marktanalyse -----------------------------------

STANDORT_SCHEMA = {
    "type": ["object", "null"],
    "properties": {
        "city": {"type": ["string", "null"]},
        "district": {"type": ["string", "null"]},
        "macro_location_score": {"type": ["integer", "null"]},
        "micro_location_score": {"type": ["integer", "null"]},
        "population_trend": {
            "type": "string",
            "enum": [
                "stark_wachsend",
                "wachsend",
                "stabil",
                "leicht_ruecklaeufig",
                "ruecklaeufig",
                "unbekannt",
            ],
        },
        "unemployment_rate_pct": {"type": ["number", "null"]},
        "public_transport_minutes": {"type": ["integer", "null"]},
        "infrastructure_notes": {"type": "string"},
        "market_rent_per_sqm_eur": {"type": ["number", "null"]},
        "market_price_per_sqm_eur": {"type": ["number", "null"]},
        "rent_trend_3y_pct": {"type": ["number", "null"]},
        "vacancy_rate_market_pct": {"type": ["number", "null"]},
        "flood_risk_zone": {"type": ["string", "null"]},
        "contamination_risk": {
            "type": "string",
            "enum": ["niedrig", "mittel", "hoch", "unbekannt"],
        },
        "milieuschutz": {"type": "boolean"},
        "risk_factors": {"type": "array", "items": {"type": "string"}},
        "location_strengths": {"type": "array", "items": {"type": "string"}},
        "location_risk_level": _risk_level_field(),
        "location_notes": {"type": "string"},
        "data_sources": {"type": "array", "items": {"type": "string"}},
    },
    "required": [
        "city",
        "district",
        "macro_location_score",
        "micro_location_score",
        "population_trend",
        "unemployment_rate_pct",
        "public_transport_minutes",
        "infrastructure_notes",
        "market_rent_per_sqm_eur",
        "market_price_per_sqm_eur",
        "rent_trend_3y_pct",
        "vacancy_rate_market_pct",
        "flood_risk_zone",
        "contamination_risk",
        "milieuschutz",
        "risk_factors",
        "location_strengths",
        "location_risk_level",
        "location_notes",
        "data_sources",
    ],
    "additionalProperties": False,
}

# --- Skill 8: Rechtliche Risikopruefung -------------------------------------

LEGAL_DETAIL_SCHEMA = {
    "type": ["object", "null"],
    "properties": {
        "purchase_contract_risks": {
            "type": "array",
            "items": {
                "type": "object",
                "properties": {
                    "clause": {"type": "string"},
                    "description": {"type": "string"},
                    "legal_basis": {"type": "string"},
                    "severity": {
                        "type": "string",
                        "enum": ["Critical", "High", "Medium", "Low"],
                    },
                    "recommendation": {"type": "string"},
                },
                "required": [
                    "clause",
                    "description",
                    "legal_basis",
                    "severity",
                    "recommendation",
                ],
                "additionalProperties": False,
            },
        },
        "tenancy_law_risks": {
            "type": "array",
            "items": {
                "type": "object",
                "properties": {
                    "type": {"type": "string"},
                    "description": {"type": "string"},
                    "severity": {
                        "type": "string",
                        "enum": ["Critical", "High", "Medium", "Low"],
                    },
                    "recommendation": {"type": "string"},
                },
                "required": ["type", "description", "severity", "recommendation"],
                "additionalProperties": False,
            },
        },
        "public_law_issues": {"type": "array", "items": {"type": "string"}},
        "tax_notes": {"type": "string"},
        "warranty_exclusion_assessment": {"type": "string"},
        "all_legal_risks": {"type": "array", "items": {"type": "string"}},
        "legal_risk_level": _risk_level_field(),
        "legal_notes": {"type": "string"},
    },
    "required": [
        "purchase_contract_risks",
        "tenancy_law_risks",
        "public_law_issues",
        "tax_notes",
        "warranty_exclusion_assessment",
        "all_legal_risks",
        "legal_risk_level",
        "legal_notes",
    ],
    "additionalProperties": False,
}

# --- Final aggregated report ------------------------------------------------

DUE_DILIGENCE_SCHEMA = {
    "type": "object",
    "properties": {
        "property_address": {"type": ["string", "null"]},
        "document_types_analyzed": {"type": "array", "items": {"type": "string"}},
        "overall_risk_level": _risk_level_field(),
        "executive_summary": {"type": "string"},
        "completeness_check": {
            "type": "object",
            "properties": {
                "missing_documents": {"type": "array", "items": {"type": "string"}},
                "missing_data_points": {"type": "array", "items": {"type": "string"}},
            },
            "required": ["missing_documents", "missing_data_points"],
            "additionalProperties": False,
        },
        "red_flags": {
            "type": "array",
            "items": {
                "type": "object",
                "properties": {
                    "category": {
                        "type": "string",
                        "enum": ["Rechtlich", "Wirtschaftlich", "Technisch", "Umwelt"],
                    },
                    "description": {"type": "string"},
                    "severity": {
                        "type": "string",
                        "enum": ["Critical", "High", "Medium", "Low"],
                    },
                    "source_document": {"type": "string"},
                },
                "required": ["category", "description", "severity", "source_document"],
                "additionalProperties": False,
            },
        },
        "risk_assessment": {
            "type": "object",
            "properties": {
                "legal": _risk_level_field(),
                "financial": _risk_level_field(),
                "technical": _risk_level_field(),
                "location": _risk_level_field(),
                "tenant_default": _risk_level_field(),
            },
            "required": [
                "legal",
                "financial",
                "technical",
                "location",
                "tenant_default",
            ],
            "additionalProperties": False,
        },
        "financial_summary": {
            "type": "object",
            "properties": {
                "current_rent_annual_eur": {"type": ["number", "null"]},
                "estimated_market_rent_annual_eur": {"type": ["number", "null"]},
                "vacancy_risk_assessment": {"type": "string"},
                "maintenance_backlog_notes": {"type": "string"},
            },
            "required": [
                "current_rent_annual_eur",
                "estimated_market_rent_annual_eur",
                "vacancy_risk_assessment",
                "maintenance_backlog_notes",
            ],
            "additionalProperties": False,
        },
        "kpis": {
            "type": "object",
            "properties": {
                "purchase_price_eur": {"type": ["number", "null"]},
                "total_area_sqm": {"type": ["number", "null"]},
                "price_per_sqm_eur": {"type": ["number", "null"]},
                "market_price_per_sqm_eur": {"type": ["number", "null"]},
                "price_vs_market_percent": {"type": ["number", "null"]},
                "rent_multiplier": {"type": ["number", "null"]},
                "gross_yield_percent": {"type": ["number", "null"]},
                "net_yield_percent": {"type": ["number", "null"]},
                "acquisition_costs_total_eur": {"type": ["number", "null"]},
                "operating_costs_annual_eur": {"type": ["number", "null"]},
                "maintenance_reserve_annual_eur": {"type": ["number", "null"]},
                "cashflow_pre_financing_eur": {"type": ["number", "null"]},
                "cashflow_post_financing_eur": {"type": ["number", "null"]},
                "operating_cost_ratio_percent": {"type": ["number", "null"]},
                "break_even_occupancy_percent": {"type": ["number", "null"]},
                "sensitivity_scenarios": {
                    "type": "object",
                    "properties": {
                        "base_case_cashflow_eur": {"type": ["number", "null"]},
                        "optimistic_cashflow_eur": {"type": ["number", "null"]},
                        "pessimistic_cashflow_eur": {"type": ["number", "null"]},
                        "sensitivity_notes": {"type": "string"},
                    },
                    "required": [
                        "base_case_cashflow_eur",
                        "optimistic_cashflow_eur",
                        "pessimistic_cashflow_eur",
                        "sensitivity_notes",
                    ],
                    "additionalProperties": False,
                },
                "reserve_need_notes": {"type": "string"},
                "assumptions_and_limitations": {"type": "string"},
                "sensitivity_analysis_notes": {"type": "string"},
            },
            "required": [
                "purchase_price_eur",
                "total_area_sqm",
                "price_per_sqm_eur",
                "market_price_per_sqm_eur",
                "price_vs_market_percent",
                "rent_multiplier",
                "gross_yield_percent",
                "net_yield_percent",
                "acquisition_costs_total_eur",
                "operating_costs_annual_eur",
                "maintenance_reserve_annual_eur",
                "cashflow_pre_financing_eur",
                "cashflow_post_financing_eur",
                "operating_cost_ratio_percent",
                "break_even_occupancy_percent",
                "sensitivity_scenarios",
                "reserve_need_notes",
                "assumptions_and_limitations",
                "sensitivity_analysis_notes",
            ],
            "additionalProperties": False,
        },
        # --- Detailed per-skill sections (see skill SKILL.md docs) ---------
        "document_inventory": DOCUMENT_INVENTORY_SCHEMA,
        "grundbuch": GRUNDBUCH_SCHEMA,
        "mietanalyse": MIETANALYSE_SCHEMA,
        "technical": TECHNICAL_SCHEMA,
        "weg": WEG_SCHEMA,
        "standort": STANDORT_SCHEMA,
        "legal": LEGAL_DETAIL_SCHEMA,
        "legal_risks": {"type": "array", "items": {"type": "string"}},
        "strengths": {"type": "array", "items": {"type": "string"}},
        "weaknesses": {"type": "array", "items": {"type": "string"}},
        "open_questions": {"type": "array", "items": {"type": "string"}},
        "investment_score": {
            "type": "object",
            "properties": {
                "score": {"type": "number"},
                "score_explanation": {"type": "string"},
                "classification": {
                    "type": "string",
                    "enum": [
                        "Sehr starkes Investment",
                        "Solides Investment",
                        "Prueffall",
                        "Kritisch",
                        "Nicht empfehlenswert",
                    ],
                },
                "score_breakdown": {
                    "type": "object",
                    "properties": {
                        "location_score": {"type": "number"},
                        "financial_score": {"type": "number"},
                        "technical_score": {"type": "number"},
                        "legal_score": {"type": "number"},
                        "weg_score": {"type": "number"},
                        "completeness_score": {"type": "number"},
                    },
                    "required": [
                        "location_score",
                        "financial_score",
                        "technical_score",
                        "legal_score",
                        "weg_score",
                        "completeness_score",
                    ],
                    "additionalProperties": False,
                },
            },
            "required": [
                "score",
                "score_explanation",
                "classification",
                "score_breakdown",
            ],
            "additionalProperties": False,
        },
        "recommendation": {
            "type": "string",
            "enum": ["Kaufen", "Nachverhandeln", "Abstand nehmen"],
        },
        "recommendation_reasoning": {"type": "string"},
    },
    "required": [
        "property_address",
        "document_types_analyzed",
        "overall_risk_level",
        "executive_summary",
        "completeness_check",
        "red_flags",
        "risk_assessment",
        "financial_summary",
        "kpis",
        "document_inventory",
        "grundbuch",
        "mietanalyse",
        "technical",
        "weg",
        "standort",
        "legal",
        "legal_risks",
        "strengths",
        "weaknesses",
        "open_questions",
        "investment_score",
        "recommendation",
        "recommendation_reasoning",
    ],
    "additionalProperties": False,
}
