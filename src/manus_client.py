import mimetypes
import os
import time
import warnings
from pathlib import Path

import requests
import urllib3
from dotenv import load_dotenv

load_dotenv()

MANUS_API_URL = "https://api.manus.ai/v2"


def _ssl_verify() -> bool | str:
    """Return the requests `verify=` value from env.

    SSL_CA_BUNDLE=/path/to/corp-ca.crt  – use a custom CA bundle (recommended)
    SSL_VERIFY=false                     – disable verification entirely (last resort)
    """
    bundle = os.getenv("SSL_CA_BUNDLE", "").strip()
    if bundle:
        return bundle
    if os.getenv("SSL_VERIFY", "true").lower() in ("false", "0", "no"):
        warnings.warn(
            "SSL verification is disabled (SSL_VERIFY=false). "
            "Only use this in trusted corporate networks.",
            stacklevel=2,
        )
        urllib3.disable_warnings(urllib3.exceptions.InsecureRequestWarning)
        return False
    return True


def _headers() -> dict:
    api_key = os.getenv("MANUS_API_KEY")
    if not api_key:
        raise EnvironmentError("MANUS_API_KEY is not set.")
    return {"x-manus-api-key": api_key, "Content-Type": "application/json"}


def upload_file_to_manus(file_path: str, file_name: str) -> str:
    # Use only the basename — no path separators that could cause a 400
    safe_name = Path(file_name).name or Path(file_path).name
    mime_type, _ = mimetypes.guess_type(safe_name)
    mime_type = mime_type or "application/octet-stream"
    project_id = os.getenv("MANUS_PROJECT_ID")

    payload: dict = {"filename": safe_name, "mime_type": mime_type}
    if project_id:
        payload["project_id"] = project_id

    res = requests.post(
        f"{MANUS_API_URL}/file.upload",
        headers=_headers(),
        json=payload,
        timeout=30,
        verify=_ssl_verify(),
    )
    if not res.ok:
        raise RuntimeError(
            f"file.upload fehlgeschlagen ({res.status_code}): {res.text}"
        )
    data = res.json()
    with open(file_path, "rb") as f:
        put_res = requests.put(
            data["upload_url"],
            data=f,
            headers={"Content-Type": mime_type},
            timeout=120,
            verify=_ssl_verify(),
        )
        if not put_res.ok:
            raise RuntimeError(
                f"PUT upload fehlgeschlagen ({put_res.status_code}): {put_res.text}"
            )
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
        verify=_ssl_verify(),
    )
    res.raise_for_status()
    data = res.json()
    task = data.get("task") or data.get("data", {}).get("task")
    if isinstance(task, dict) and "id" in task:
        return task["id"]
    if "task_id" in data:
        return data["task_id"]
    raise RuntimeError(f"task.create Antwort enthaelt keine task_id: {data}")


def send_followup_message(task_id: str, content: str) -> None:
    """Continue an existing task with a follow-up question (no structured output)."""
    res = requests.post(
        f"{MANUS_API_URL}/task.sendMessage",
        headers=_headers(),
        json={"task_id": task_id, "message": {"content": content}},
        timeout=30,
        verify=_ssl_verify(),
    )
    res.raise_for_status()


def poll_for_followup_reply(task_id: str) -> str:
    """Return the latest assistant_message text for a follow-up turn."""
    for event in list_task_messages(task_id, limit=5):
        if event.get("type") == "assistant_message":
            return event.get("content", "")
    return ""


def poll_for_result(task_id: str, timeout: int = 600) -> dict:
    start = time.time()
    while time.time() - start < timeout:
        events = list_task_messages(task_id, limit=50)
        for e in events:
            result = _extract_structured_output(e)
            if result is not None:
                return result
            if (
                e.get("type") == "status_update"
                and e.get("status_update", {}).get("status") == "error"
            ):
                raise RuntimeError("Manus Task fehlgeschlagen.")
        time.sleep(5)
    raise TimeoutError(f"Task {task_id} Timeout nach {timeout}s.")


def get_available_skills(project_id: str | None = None) -> list:
    params: dict = {}
    if project_id:
        params["project_id"] = project_id
    res = requests.get(
        f"{MANUS_API_URL}/skill.list",
        headers=_headers(),
        params=params or None,
        timeout=30,
        verify=_ssl_verify(),
    )
    res.raise_for_status()
    return res.json().get("data", [])


def list_task_messages(task_id: str, limit: int = 20, order: str = "desc") -> list:
    """Return latest Manus task events (status updates, results, etc.)."""
    res = requests.get(
        f"{MANUS_API_URL}/task.listMessages",
        headers=_headers(),
        params={"task_id": task_id, "order": order, "limit": limit},
        timeout=30,
        verify=_ssl_verify(),
    )
    res.raise_for_status()
    return res.json().get("data", [])


def _extract_structured_output(event: dict) -> dict | None:
    """Return schema value from any Manus structured output variant if present."""
    payload_candidates = []
    if event.get("type") == "structured_output_result":
        payload_candidates.append(event.get("structured_output_result"))
    payload_candidates.extend(
        filter(
            None,
            (
                event.get("structured_output_result"),
                event.get("structured_output"),
                (
                    (event.get("data") or {}).get("structured_output_result")
                    if isinstance(event.get("data"), dict)
                    else None
                ),
            ),
        )
    )

    for payload in payload_candidates:
        if payload is None:
            continue
        if not isinstance(payload, dict):
            return payload
        if payload.get("success") is False:
            raise RuntimeError(f"Schema-Fehler: {payload.get('error')}")
        if "value" in payload:
            return payload["value"]
        if "result" in payload:
            return payload["result"]
        data = payload.get("data")
        if isinstance(data, dict):
            if "value" in data:
                return data["value"]
            return data
        # Fallback: treat dict itself as result if it already looks like schema output
        keys = {k for k in payload.keys() if k not in {"success", "error", "schema_id"}}
        if keys:
            return {k: payload[k] for k in keys}
    return None
