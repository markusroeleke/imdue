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
    # API spec only accepts "filename" — no mime_type, no project_id
    res = requests.post(
        f"{MANUS_API_URL}/file.upload",
        headers=_headers(),
        json={"filename": safe_name},
        timeout=30,
        verify=_ssl_verify(),
    )
    if not res.ok:
        raise RuntimeError(
            f"file.upload fehlgeschlagen ({res.status_code}): {res.text}"
        )
    data = res.json()
    upload_url = data.get("upload_url")
    if not upload_url:
        raise RuntimeError(f"file.upload lieferte keine upload_url: {data}")
    mime_type, _ = mimetypes.guess_type(safe_name)
    mime_type = mime_type or "application/octet-stream"
    with open(file_path, "rb") as f:
        put_res = requests.put(
            upload_url,
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
        "Du bist ein hochspezialisierter Immobilien-Due-Diligence-Experte für den deutschsprachigen Markt.\n"
        "Führe folgende Analyseschritte für alle angehängten Maklerunterlagen durch:\n"
        "Phase 0 (immer zuerst): Dokument-Inventarisierung - Dokumente klassifizieren, "
        "Vollständigkeit prüfen, fehlende Kern- und Empfehlungsdokumente sowie Datenpunkte auflisten.\n"
        "Phase 1 (direkt danach - so viele Schritte wie möglich gleichzeitig/parallel bearbeiten, "
        "nicht nacheinander): "
        "(a) Grundbuch- & Eigentumsanalyse: Eigentümerstruktur, Lasten, Grundschulden, Nießbrauch, "
        "Wegerechte, Auflassungsvormerkungen; "
        "(b) Mietvertrags- & Mieteranalyse: Mietverträge/Mieterliste, Mietniveau, Laufzeiten, "
        "Index-/Staffelmietklauseln, Sonderkündigungsrechte, Leerstandsrisiko, Ist- vs. Sollmiete; "
        "(c) Wirtschaftliche Kennzahlen: Kaufpreisfaktor, Brutto-/Nettomietrendite, Cashflow vor/nach "
        "Finanzierung, Bewirtschaftungskostenquote, Break-Even-Vermietungsquote, Sensitivitätsszenarien, "
        "Marktvergleich per Websuche; "
        "(d) Technische & bauliche Prüfung: Mängel, Instandhaltungsrückstau, Energieausweis/"
        "Effizienzklasse, GEG-Pflichten, Investitionskosten kurz-/mittel-/langfristig; "
        "(e) WEG-Analyse (nur falls WEG-Unterlagen vorhanden): Hausgeld, Rücklagenangemessenheit, "
        "geplante Sonderumlagen, Rechtsstreitigkeiten, Verwalterqualität; "
        "(f) Standort- & Marktanalyse per Websuche: Makro-/Mikrolage, ÖPNV, Schulen, Kaufpreis/Miete "
        "pro qm, Leerstandsquote, Hochwasserrisiko (ZÜRS-Zone), Milieuschutz, Standort-Score 1-5 - "
        "diesen Schritt immer ausführen, unabhängig von Dokumentlage; "
        "(g) Rechtliche Risikoprüfung: Kaufvertragsentwurf, mietrechtliche Klauseln "
        "(Schönheitsreparaturen, Mietpreisbremse, Eigenbedarf), Baugenehmigungen, "
        "Zweckentfremdungsverbot, Steuerhinweise (AfA, Denkmalschutz), Gewährleistungsausschlüsse.\n"
        "Überspringe einen Teilschritt aus Phase 1 nur, wenn die dafür nötigen Unterlagen vollständig "
        "fehlen (außer Standortanalyse (f), die immer läuft), und vermerke dies als offenen Punkt statt "
        "Informationen zu erfinden.\n"
        "Phase 2 (erst nach Abschluss aller Phase-1-Schritte): Risikobewertung - alle Teilergebnisse zu "
        "einem Investment-Score (0-100, mit Aufschlüsselung je Kategorie), einer sortierten "
        "Red-Flag-Liste, Stärken/Schwächen und einer Kauf-Empfehlung "
        "(Kaufen/Nachverhandeln/Abstand nehmen) aggregieren.\n"
        "Arbeite so schnell wie möglich: bearbeite alle unabhängigen Analyseschritte aus Phase 1 "
        "parallel statt sequenziell, um die Gesamtlaufzeit zu minimieren.\n"
        "Wenn Informationen fehlen, erfinde nichts und liste sie als offene Punkte.\n"
        "Gib ausschließlich das strukturierte JSON-Ergebnis exakt im vorgegebenen Schema zurück. "
        "Erzeuge dabei kein PDF und keine sonstige Berichtsdatei und sende keine zusätzliche "
        "Chat-Nachricht, Zusammenfassung oder Erklärung an den Nutzer - liefere ausschließlich das "
        "JSON-Schema-Ergebnis."
    )
    # Per API spec: files are ContentPart objects in the content array,
    # not a separate "attachments" field.
    content_parts: list = [{"type": "text", "text": prompt}]
    for fid in file_ids:
        content_parts.append({"type": "file", "file_id": fid})
    message: dict = {"content": content_parts}
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


def poll_for_followup_reply(task_id: str, retries: int = 6, delay: int = 5) -> str:
    """Return the latest assistant_message text for a follow-up turn."""
    for _ in range(retries):
        for event in list_task_messages(task_id, limit=10):
            if event.get("type") == "assistant_message":
                # content is nested: event.assistant_message.content
                return event.get("assistant_message", {}).get("content", "")
        time.sleep(delay)
    return ""


# The Due-Diligence steps executed by the backend within the single
# consolidated analysis task (see the phase breakdown in the prompt built by
# create_analysis_task: Phase 0 = doc inventory, Phase 1 (a)-(g) = the
# parallel sub-analyses, Phase 2 = final risk score/recommendation
# aggregation). Used to detect which processing step is currently active
# from the free-text status/plan/tool events the backend reports, since
# there is no dedicated "skill status" event. Keywords are kept in sync
# with the wording used in that prompt so Manus's own plan/status text -
# which tends to mirror the given instructions - matches reliably. Shared
# between the per-step polling timeout below and the app's skill-progress
# checklist shown to the user. Corresponds to skills 1-9 documented in
# .github/skills/dd-skill-01 … dd-skill-09; skill 10 (orchestrator) is not
# tracked separately since this task no longer runs a distinct
# aggregation/report-generation call - the single task returns the final
# JSON directly (see create_analysis_task's "JSON only, no PDF" instruction).
SKILL_STEPS: list[tuple[str, str, tuple[str, ...]]] = [
    (
        "dd-skill-01-document-inventory",
        "Dokument-Inventarisierung",
        ("dokument-inventar", "vollständigkeit", "phase 0", "skill-01"),
    ),
    (
        "dd-skill-02-grundbuch",
        "Grundbuch- & Eigentumsanalyse",
        ("grundbuch", "eigentümerstruktur", "grundschuld", "nießbrauch", "skill-02"),
    ),
    (
        "dd-skill-03-mietanalyse",
        "Mietvertrags- & Mieteranalyse",
        ("mietvertr", "mieteranalyse", "mietanalyse", "leerstandsrisiko", "skill-03"),
    ),
    (
        "dd-skill-04-finanzkennzahlen",
        "Wirtschaftliche Kennzahlen",
        ("kaufpreisfaktor", "mietrendite", "cashflow", "finanzkennzahl", "skill-04"),
    ),
    (
        "dd-skill-05-technisch",
        "Technische & bauliche Prüfung",
        ("technische", "instandhaltungsrückstau", "energieausweis", "skill-05"),
    ),
    (
        "dd-skill-06-weg",
        "WEG-Analyse",
        (
            "weg-analyse",
            "hausgeld",
            "wohnungseigentümergemeinschaft",
            "sonderumlage",
            "skill-06",
        ),
    ),
    (
        "dd-skill-07-standort",
        "Standort- & Marktanalyse",
        ("standort", "makrolage", "mikrolage", "milieuschutz", "skill-07"),
    ),
    (
        "dd-skill-08-rechtlich",
        "Rechtliche Risikoprüfung",
        (
            "rechtliche risikoprüfung",
            "kaufvertragsentwurf",
            "mietpreisbremse",
            "skill-08",
        ),
    ),
    (
        "dd-skill-09-risikoscore",
        "Risikobewertung, Investment-Score & Empfehlung",
        (
            "risikoscore",
            "investment-score",
            "red-flag",
            "red flag",
            "phase 2",
            "skill-09",
        ),
    ),
]


def match_skill(text: str) -> str | None:
    """Return the skill id whose name/keywords occur in `text`, if any."""
    text_lower = text.lower()
    for skill_id, _, keywords in SKILL_STEPS:
        if skill_id.lower() in text_lower or any(kw in text_lower for kw in keywords):
            return skill_id
    return None


def _detect_step_progress(event: dict) -> tuple[str | None, bool]:
    """Return (skill_id, is_done) an event can be attributed to, if any."""
    etype = event.get("type")
    if etype == "plan_update":
        for step in (event.get("plan_update", {}) or {}).get("steps", []) or []:
            skill_id = match_skill(step.get("title", ""))
            if skill_id:
                return skill_id, step.get("status") == "done"
        return None, False
    if etype == "tool_used":
        tool_info = event.get("tool_used", {}) or {}
        text = f"{tool_info.get('brief', '')} {tool_info.get('description', '')}"
        return match_skill(text), False
    if etype == "status_update":
        status_info = event.get("status_update", {}) or {}
        text = f"{status_info.get('brief', '')} {status_info.get('description', '')}"
        return match_skill(text), False
    return None, False


def poll_for_result(task_id: str, timeout: int = 600) -> dict:
    """Poll task.listMessages until a structured result appears.

    `timeout` applies per processing step (skill), not to the task as a
    whole: whenever a backend event can be attributed to one of the DD
    skills (see SKILL_STEPS), that skill's own clock resets. A skill that
    hasn't finished and shows no further event for `timeout` seconds is
    considered stuck and raises TimeoutError. Since skills 2-8 run in
    parallel and each gets its own budget, a long-running analysis (>10 min)
    that keeps progressing through its skills is not cut off. Events that
    cannot be attributed to a specific skill (e.g. before the first skill
    starts) fall back to a plain inactivity timeout.
    """
    seen_ids: set[str] = set()
    skill_last_seen: dict[str, float] = {}
    skill_done: set[str] = set()
    overall_last_activity = time.time()
    while True:
        events = list_task_messages(task_id, limit=50, verbose=True)
        for e in events:
            event_id = e.get("id")
            if event_id:
                if event_id in seen_ids:
                    continue
                seen_ids.add(event_id)
            result = _extract_structured_output(e)
            if result is not None:
                return result
            if (
                e.get("type") == "status_update"
                and e.get("status_update", {}).get("agent_status") == "error"
            ):
                err_detail = e.get("status_update", {}).get("description", "")
                raise RuntimeError(f"Manus Task fehlgeschlagen: {err_detail}")
            step_id, step_done = _detect_step_progress(e)
            if step_id:
                skill_last_seen[step_id] = time.time()
                if step_done:
                    skill_done.add(step_id)
            else:
                overall_last_activity = time.time()

        now = time.time()
        stalled_step = next(
            (
                sid
                for sid, last_seen in skill_last_seen.items()
                if sid not in skill_done and now - last_seen >= timeout
            ),
            None,
        )
        if stalled_step:
            raise TimeoutError(
                f"Task {task_id}: Schritt '{stalled_step}' ohne Fortschritt seit {timeout}s."
            )
        if not skill_last_seen and now - overall_last_activity >= timeout:
            raise TimeoutError(
                f"Task {task_id} Timeout nach {timeout}s ohne Aktivität."
            )
        time.sleep(5)


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


def list_task_messages(
    task_id: str,
    limit: int = 20,
    order: str = "desc",
    verbose: bool = False,
) -> list:
    """Return latest Manus task events (status updates, results, etc.).

    Right after task.create, the task can briefly 404 on task.listMessages
    before it is fully indexed on the backend (eventual consistency). Retry a
    few times with a short backoff before giving up.

    `verbose=True` additionally includes tool_used/plan_update/new_plan_step/
    explanation events, useful for deriving fine-grained (e.g. per-skill)
    progress.
    """
    retries = 5
    delay = 2
    params: dict = {"task_id": task_id, "order": order, "limit": limit}
    if verbose:
        params["verbose"] = "true"
    for attempt in range(retries):
        res = requests.get(
            f"{MANUS_API_URL}/task.listMessages",
            headers=_headers(),
            params=params,
            timeout=30,
            verify=_ssl_verify(),
        )
        if res.status_code == 404 and attempt < retries - 1:
            time.sleep(delay)
            continue
        res.raise_for_status()
        # API returns key "messages", not "data"
        body = res.json()
        return body.get("messages") or body.get("data") or []
    return []


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
