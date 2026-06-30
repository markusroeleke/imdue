"""One-time helper script: list all available Manus skills and their IDs.

Run from the project root:
    python check_skills.py

Copy the relevant IDs into your .env file as MANUS_FORCE_SKILL_IDS.
"""

from src.manus_client import get_available_skills

if __name__ == "__main__":
    skills = get_available_skills()
    if not skills:
        print("No skills returned. Check your MANUS_API_KEY.")
    for skill in skills:
        print(f"ID: {skill.get('id'):<40} Name: {skill.get('name')}")
