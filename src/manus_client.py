import os
import time

import requests
from dotenv import load_dotenv

load_dotenv()

MANUS_API_URL = "https://api.manus.ai/v2"


def _headers() -> dict:
    api_key = os.getenv("MANUS_API_KEY")
    if not api_key:
        raise EnvironmentError("MANUS_API_KEY is not set.")
    return {"x-manus-api-key": api_key, "Content-Type": "application/json"}


def upload_file_to_manus(file_path: str, file_name: str) -> str:
    res = requests.post(
        f"{MANUS_API_URL}/file.upload",
        headers=_headers(),
        json={"file_name": file_name},
        timeout=30,
    )
    res.raise_for_status()
    data = res.json()
    with open(file_path, "rb") as f:
        requests.put(data["upload_url"], data=f, timeout=120).raise_for_status()
    return data["file"]["id"]


def create_analysis_task(file_ids: list, schema: dict) -> str:
    skill_ids = [s for s in os.getenv("MANUS_FORCE_SKILL_IDS", "").split(",") if s]
    project_id = os.getenv("MANUS_PROJECT_ID")
    prompt = (
        "Du bist ein hochspezialisierter Immobilien-Due-Diligence-Experte fuer den deutschsprachigen Markt.\n"
        "Analysiere alle angehaengten Maklerunterlagen auf rechtliche, wirtschaftliche und technische Risiken.\n"
        "Berechne Kennzahlen, bewerte Risiken je Kategorie, und vergib einen Investment-Score.\n"
        "Wenn Informationen fehlen, erfinde nichts und liste sie als offene Punkte.\n"
        "Liefere deine Analyse exakt im geforderten JSON-Format."
    )
    message: dict = {
        "content": prompt,
        "attachments": [{"file_id": fid} for fid in file_ids],
    }
    if skill_ids:
        message["force_skills"] = skill_ids
    payload: dict = {"message": message, "structured_output_schema": schema}
    if project_id:
        payload["project_id"] = project_id
    res = requests.post(
        f"{MANUS_API_URL}/task.create",
        headers=_headers(),
        json=payload,
        timeout=30,
    )
    res.raise_for_status()
    return res.json()["task"]["id"]


def send_followup_message(task_id: str, content: str) -> None:
    """Continue an existing task with a follow-up question (no structured output)."""
    res = requests.post(
        f"{MANUS_API_URL}/task.sendMessage",
        headers=_headers(),
        json={"task_id": task_id, "message": {"content": content}},
        timeout=30,
    )
    res.raise_for_status()


def poll_for_result(task_id: str, timeout: int = 600) -> dict:
    start = time.time()
    while time.time() - start < timeout:
        res = requests.get(
            f"{MANUS_API_URL}/task.listMessages",
            headers=_headers(),
            params={"task_id": task_id, "order": "desc", "limit": 20},
            timeout=30,
        )
        res.raise_for_status()
        events = res.json().get("data", [])
        for e in events:
            if e.get("type") == "structured_output_result":
                r = e["structured_output_result"]
                if r.get("success"):
                    return r["value"]
                raise RuntimeError(f"Schema-Fehler: {r.get('error')}")
            if (
                e.get("type") == "status_update"
                and e.get("status_update", {}).get("status") == "error"
            ):
                raise RuntimeError("Manus Task fehlgeschlagen.")
        time.sleep(5)
    raise TimeoutError(f"Task {task_id} Timeout nach {timeout}s.")


def get_available_skills() -> list:
    res = requests.get(f"{MANUS_API_URL}/skill.list", headers=_headers(), timeout=30)
    res.raise_for_status()
    return res.json().get("data", [])
