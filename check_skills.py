"""Helper script: list available Manus skills and identify project-relevant ones.

Run from the project root:
    python check_skills.py

This project requires three skill categories (see doc/Due_Diligence_Agent_Skills_Spezifikation.md §4):
  1. Advanced Document Extraction / OCR
  2. Legal Text Analysis
  3. Financial Data Processing

Skills whose name matches one of these categories are highlighted with ★.
Copy the IDs of the best matches into .env as MANUS_FORCE_SKILL_IDS.
"""

import os
from dotenv import load_dotenv
from src.manus_client import get_available_skills

# Keywords that indicate a skill is relevant for this project
RELEVANT_KEYWORDS: dict[str, list[str]] = {
    "Document Extraction / OCR": [
        "ocr",
        "document",
        "extraction",
        "pdf",
        "scan",
        "image",
        "vision",
    ],
    "Legal Text Analysis": [
        "legal",
        "law",
        "contract",
        "juristic",
        "clause",
        "grundbuch",
        "recht",
    ],
    "Financial Data Processing": [
        "financial",
        "finance",
        "math",
        "calculat",
        "number",
        "accounting",
        "kpi",
    ],
}


def _matches(skill_name: str) -> list[str]:
    name_lower = skill_name.lower()
    return [
        category
        for category, keywords in RELEVANT_KEYWORDS.items()
        if any(kw in name_lower for kw in keywords)
    ]


if __name__ == "__main__":
    load_dotenv()

    # Show current .env configuration
    current_ids = os.getenv("MANUS_FORCE_SKILL_IDS", "")
    current_project = os.getenv("MANUS_PROJECT_ID", "")
    print("─" * 70)
    print("Current .env configuration")
    print(f"  MANUS_FORCE_SKILL_IDS : {current_ids or '(not set)'}")
    print(f"  MANUS_PROJECT_ID      : {current_project or '(not set)'}")
    print("─" * 70)

    skills = get_available_skills()
    if not skills:
        print("No skills returned. Check your MANUS_API_KEY.")
    else:
        print(f"{'ID':<42} {'NAME':<40} RELEVANT FOR")
        print("─" * 70)
        for skill in skills:
            sid = skill.get("id", "")
            name = skill.get("name", "")
            matches = _matches(name)
            marker = "★ " if matches else "  "
            categories = ", ".join(matches) if matches else ""
            print(f"{marker}{sid:<40} {name:<40} {categories}")

        print("─" * 70)
        print("\nProject requires skills for:")
        for cat in RELEVANT_KEYWORDS:
            print(f"  • {cat}")
        print("\nSet the ★ skill IDs in .env:")
        print("  MANUS_FORCE_SKILL_IDS=skill_id_1,skill_id_2,skill_id_3")
