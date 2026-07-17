import mimetypes
import os
import time
import warnings
from pathlib import Path

import requests
import urllib3
from dotenv import load_dotenv

from src.logging_utils import get_logger

load_dotenv()

logger = get_logger("manus_client")

MANUS_API_URL = "https://api.manus.ai/v2"


def _ssl_verify() -> bool | str:
    """Return the requests `verify=` value from env.

    SSL_CA_BUNDLE=/path/to/corp-ca.crt  – use a custom CA bundle (recommended)
    SSL_VERIFY=false                     – disable verification entirely (last resort)
    """
    bundle = os.getenv("SSL_CA_BUNDLE", "").strip()
    if bundle:
        logger.debug("Using custom SSL CA bundle: %s", bundle)
        return bundle
    if os.getenv("SSL_VERIFY", "true").lower() in ("false", "0", "no"):
        logger.warning("SSL verification is disabled (SSL_VERIFY=false).")
        warnings.warn(
            "SSL verification is disabled (SSL_VERIFY=false). "
            "Only use this in trusted corporate networks.",
            stacklevel=2,
        )
        urllib3.disable_warnings(urllib3.exceptions.InsecureRequestWarning)
        return False
    return True


def _headers() -> dict:
    # Never log the API key itself.
    api_key = os.getenv("MANUS_API_KEY")
    if not api_key:
        logger.error("MANUS_API_KEY is not set.")
        raise EnvironmentError("MANUS_API_KEY is not set.")
    return {"x-manus-api-key": api_key, "Content-Type": "application/json"}


def upload_file_to_manus(file_path: str, file_name: str) -> str:
    logger.info("upload_file_to_manus: starte Upload fuer %s", file_name)
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
    logger.debug("file.upload response status=%s fuer %s", res.status_code, safe_name)
    if not res.ok:
        logger.error(
            "file.upload fehlgeschlagen (%s) fuer %s: %s",
            res.status_code,
            safe_name,
            res.text,
        )
        raise RuntimeError(
            f"file.upload fehlgeschlagen ({res.status_code}): {res.text}"
        )
    data = res.json()
    upload_url = data.get("upload_url")
    if not upload_url:
        logger.error(
            "file.upload lieferte keine upload_url fuer %s: %s", safe_name, data
        )
        raise RuntimeError(f"file.upload lieferte keine upload_url: {data}")
    mime_type, _ = mimetypes.guess_type(safe_name)
    mime_type = mime_type or "application/octet-stream"
    file_size = Path(file_path).stat().st_size
    logger.debug(
        "PUT-Upload fuer %s: mime_type=%s size=%d bytes",
        safe_name,
        mime_type,
        file_size,
    )
    with open(file_path, "rb") as f:
        put_res = requests.put(
            upload_url,
            data=f,
            headers={"Content-Type": mime_type},
            timeout=120,
            verify=_ssl_verify(),
        )
        if not put_res.ok:
            logger.error(
                "PUT upload fehlgeschlagen (%s) fuer %s: %s",
                put_res.status_code,
                safe_name,
                put_res.text,
            )
            raise RuntimeError(
                f"PUT upload fehlgeschlagen ({put_res.status_code}): {put_res.text}"
            )
    file_id = data["file"]["id"]
    logger.info(
        "upload_file_to_manus: %s erfolgreich hochgeladen, file_id=%s",
        safe_name,
        file_id,
    )
    return file_id


def create_analysis_task(file_ids: list, schema: dict) -> str:
    logger.info("create_analysis_task: erstelle Task fuer %d Datei(en)", len(file_ids))
    skill_ids = [s for s in os.getenv("MANUS_FORCE_SKILL_IDS", "").split(",") if s]
    project_id = os.getenv("MANUS_PROJECT_ID")
    logger.debug(
        "create_analysis_task: skill_ids=%s project_id=%s", skill_ids, project_id
    )
    prompt = (
        "Du bist ein hochspezialisierter Immobilien-Due-Diligence-Experte für den deutschsprachigen Markt.\n"
        "Erstelle zu Beginn eine Aufgabenliste (Plan) mit genau folgenden 10 Punkten in dieser "
        "Reihenfolge und aktualisiere deren Status (offen/in Bearbeitung/erledigt) fortlaufend "
        "während der Bearbeitung:\n"
        "1. dd-skill-01-document-inventory: Dokument-Inventarisierung & Vollständigkeitsprüfung\n"
        "2. dd-skill-02-grundbuch: Grundbuch- & Eigentumsanalyse\n"
        "3. dd-skill-03-mietanalyse: Mietvertrags- & Mieteranalyse\n"
        "4. dd-skill-04-finanzkennzahlen: Wirtschaftliche Kennzahlenberechnung\n"
        "5. dd-skill-05-technisch: Technische & bauliche Prüfung\n"
        "6. dd-skill-06-weg: WEG-Analyse\n"
        "7. dd-skill-07-standort: Standort- & Marktanalyse\n"
        "8. dd-skill-08-rechtlich: Rechtliche Risikoprüfung\n"
        "9. dd-skill-09-risikoscore: Risikobewertung & Investment-Score\n"
        "10. dd-skill-10-orchestrator: Finale Aggregation zum Gesamt-JSON\n"
        "Führe anschließend folgende Analysephasen für alle angehängten Maklerunterlagen durch:\n"
        "Phase 0 (Skill dd-skill-01-document-inventory, immer zuerst): Dokumente exakt nach Typ "
        "klassifizieren (Grundbuchauszug, Mietvertrag/Mieterliste, Exposé, Energieausweis, "
        "Teilungserklärung, WEG-Protokoll, WEG-Jahresabrechnung, Bauplan/Grundriss, Technisches "
        "Gutachten, Kaufvertragsentwurf, Flurkarte, Altlastenauskunft, Sonstiges), Objektadresse "
        "ermitteln, prüfen welche Kerndokumente (Grundbuchauszug, Mietvertrag/Mieterliste, Exposé, "
        "Energieausweis, Kaufvertragsentwurf) und empfohlenen Dokumente (WEG-Protokolle der letzten "
        "3 Jahre, WEG-Jahresabrechnung, Technisches Gutachten, Flurkarte/Lageplan, Altlastenauskunft) "
        "fehlen, und für jeden Folgeschritt (a)-(g) festlegen, ob ausreichend Unterlagen für eine "
        "sinnvolle Analyse vorliegen.\n"
        "Phase 1 (Skills dd-skill-02 bis dd-skill-08, direkt danach - so viele Schritte wie möglich "
        "gleichzeitig/parallel bearbeiten, nicht nacheinander):\n"
        "(a) dd-skill-02-grundbuch: Eigentümerstruktur (Abt. I), Lasten und Beschränkungen (Abt. II: "
        "Auflassungsvormerkungen, Wegerechte, Nießbrauch, Vorkaufsrechte, Erbbaurechte), "
        "Grundpfandrechte (Abt. III: Grundschulden, Hypotheken, Rang);\n"
        "(b) dd-skill-03-mietanalyse: Mietverträge/Mieterliste je Einheit, Mietniveau, "
        "Vertragslaufzeiten, Index-/Staffelmietklauseln, Sonderkündigungsrechte, "
        "Schönheitsreparaturklauseln, Leerstandsrisiko, Ist- vs. Sollmiete;\n"
        "(c) dd-skill-04-finanzkennzahlen: Kaufpreisfaktor, Brutto-/Nettomietrendite, Cashflow vor/"
        "nach Finanzierung, Bewirtschaftungskostenquote, Break-Even-Vermietungsquote, "
        "Sensitivitätsszenarien (Basis/positiv/negativ), Marktvergleich per Websuche;\n"
        "(d) dd-skill-05-technisch: Energieausweis/Effizienzklasse, GEG-Pflichten, Baumängel, "
        "Instandhaltungsrückstau, Investitionskosten kurz-/mittel-/langfristig;\n"
        "(e) dd-skill-06-weg (nur falls WEG-Unterlagen vorhanden): Hausgeld, "
        "Rücklagenangemessenheit, geplante/beschlossene Sonderumlagen, Rechtsstreitigkeiten der WEG, "
        "Verwalterqualität;\n"
        "(f) dd-skill-07-standort per Websuche: Makro-/Mikrolage, ÖPNV, Schulen, Kaufpreis/Miete "
        "pro qm, Leerstandsquote, Hochwasserrisiko (ZÜRS-Zone), Milieuschutz, Standort-Score 1-5 - "
        "diesen Schritt immer ausführen, unabhängig von Dokumentlage;\n"
        "(g) dd-skill-08-rechtlich: Kaufvertragsentwurf, mietrechtliche Klauseln "
        "(Schönheitsreparaturen, Mietpreisbremse, Eigenbedarf, § 577 BGB), Baugenehmigungen, "
        "Zweckentfremdungsverbot, Steuerhinweise (AfA, Denkmalschutz), Gewährleistungsausschlüsse.\n"
        "Überspringe einen Teilschritt aus Phase 1 nur, wenn die dafür nötigen Unterlagen vollständig "
        "fehlen (außer Standortanalyse (f), die immer läuft), und vermerke dies als offenen Punkt statt "
        "Informationen zu erfinden.\n"
        "Phase 2 (Skill dd-skill-09-risikoscore, erst nach Abschluss aller Phase-1-Schritte): "
        "Risikobewertung je Kategorie (Rechtlich, Wirtschaftlich, Technisch, Standort, Mietausfall) "
        "mit Low/Medium/High/Critical; Investment-Score 0-100 nach Gewichtung Standort 20 / "
        "Wirtschaftlichkeit 25 / Technik 20 / Rechtssicherheit 20 / WEG 10 / "
        "Dokumentenvollständigkeit 5 Punkte; sortierte Red-Flag-Liste (Critical zuerst); Stärken/"
        "Schwächen; Empfehlung Kaufen (Score ≥70, kein Critical-Risiko, KPIs marktgerecht) / "
        "Nachverhandeln (Score 45-69 oder behebbare Risiken) / Abstand nehmen (Score <45, "
        "Critical-Risiko oder fundamentale Datenlücken).\n"
        "Phase 3 (Skill dd-skill-10-orchestrator, letzter Schritt): Alle Teilergebnisse aus den "
        "Schritten 1-9 zu einem einzigen, in sich konsistenten Ergebnis im vorgegebenen Schema "
        "zusammenführen.\n"
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
    logger.debug("task.create response status=%s", res.status_code)
    res.raise_for_status()
    data = res.json()
    task = data.get("task") or data.get("data", {}).get("task")
    if isinstance(task, dict) and "id" in task:
        logger.info("create_analysis_task: Task erstellt, task_id=%s", task["id"])
        return task["id"]
    if "task_id" in data:
        logger.info("create_analysis_task: Task erstellt, task_id=%s", data["task_id"])
        return data["task_id"]
    logger.error("task.create Antwort enthaelt keine task_id: %s", data)
    raise RuntimeError(f"task.create Antwort enthaelt keine task_id: {data}")


def send_followup_message(task_id: str, content: str) -> None:
    """Continue an existing task with a follow-up question (no structured output)."""
    logger.info("send_followup_message: Task %s, %d Zeichen", task_id, len(content))
    res = requests.post(
        f"{MANUS_API_URL}/task.sendMessage",
        headers=_headers(),
        json={"task_id": task_id, "message": {"content": content}},
        timeout=30,
        verify=_ssl_verify(),
    )
    logger.debug("task.sendMessage response status=%s", res.status_code)
    res.raise_for_status()


def poll_for_followup_reply(task_id: str, retries: int = 6, delay: int = 5) -> str:
    """Return the latest assistant_message text for a follow-up turn."""
    logger.info(
        "poll_for_followup_reply: Task %s, retries=%d delay=%d", task_id, retries, delay
    )
    for attempt in range(retries):
        for event in list_task_messages(task_id, limit=10):
            if event.get("type") == "assistant_message":
                # content is nested: event.assistant_message.content
                logger.info(
                    "poll_for_followup_reply: Antwort erhalten (Versuch %d)",
                    attempt + 1,
                )
                return event.get("assistant_message", {}).get("content", "")
        logger.debug(
            "poll_for_followup_reply: keine Antwort im Versuch %d, warte %ds",
            attempt + 1,
            delay,
        )
        time.sleep(delay)
    logger.warning("poll_for_followup_reply: keine Antwort nach %d Versuchen", retries)
    return ""


# The Due-Diligence steps executed by the backend within the single
# consolidated analysis task (see the phase breakdown in the prompt built by
# create_analysis_task: Phase 0 = doc inventory, Phase 1 (a)-(g) = the
# parallel sub-analyses, Phase 2 = risk score/recommendation aggregation,
# Phase 3 = final JSON assembly). Used to detect which processing step is
# currently active from the free-text status/plan/tool events the backend
# reports, since there is no dedicated "skill status" event. Keywords are
# kept in sync with the wording used in that prompt so Manus's own
# plan/status text - which tends to mirror the given instructions - matches
# reliably. Shared between the per-step polling timeout below and the app's
# skill-progress checklist shown to the user. Corresponds to all 10 skills
# documented in .github/skills/dd-skill-01 … dd-skill-10. The prompt built
# by create_analysis_task explicitly asks Manus to create an upfront
# todo/plan list naming all 10 skills (by their dd-skill-XX id), so
# plan_update events reliably carry these ids even though this is a single
# consolidated task rather than 10 separate task.create calls.
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
    (
        "dd-skill-10-orchestrator",
        "Finale Aggregation zum Gesamt-JSON",
        (
            "orchestrator",
            "finale aggregation",
            "gesamt-json",
            "phase 3",
            "skill-10",
        ),
    ),
]


def match_skill(text: str, log: bool = True) -> str | None:
    """Return the skill id whose name/keywords occur in `text`, if any.

    `log=False` suppresses the debug line for events that have already been
    logged on a previous poll (Manus re-sends the same plan_update event on
    every poll while mutating its steps in place, so without this flag the
    same match would be logged repeatedly every few seconds).
    """
    text_lower = text.lower()
    for skill_id, _, keywords in SKILL_STEPS:
        if skill_id.lower() in text_lower or any(kw in text_lower for kw in keywords):
            if log:
                logger.debug("match_skill: %r -> %s", text, skill_id)
            return skill_id
    return None


def _detect_step_progress(event: dict, log: bool = True) -> tuple[str | None, bool]:
    """Return (skill_id, is_done) an event can be attributed to, if any.

    `log=False` suppresses debug logging for this call (see `match_skill`).
    """
    etype = event.get("type")
    if etype == "plan_update":
        for step in (event.get("plan_update", {}) or {}).get("steps", []) or []:
            skill_id = match_skill(step.get("title", ""), log=log)
            if skill_id:
                done = step.get("status") == "done"
                if log:
                    logger.debug(
                        "_detect_step_progress: plan_update step=%r skill_id=%s done=%s",
                        step.get("title"),
                        skill_id,
                        done,
                    )
                return skill_id, done
        return None, False
    if etype == "tool_used":
        tool_info = event.get("tool_used", {}) or {}
        text = f"{tool_info.get('brief', '')} {tool_info.get('description', '')}"
        return match_skill(text, log=log), False
    if etype == "status_update":
        status_info = event.get("status_update", {}) or {}
        text = f"{status_info.get('brief', '')} {status_info.get('description', '')}"
        return match_skill(text, log=log), False
    return None, False


def poll_for_result(
    task_id: str, timeout: int = 1200, extraction_timeout: int = 300
) -> dict:
    """Poll task.listMessages until a structured_output_result event appears.

    Follows the documented task lifecycle (see
    https://open.manus.ai/docs/v2/task-lifecycle): the authoritative signal
    is each `status_update` event's `agent_status` field, not skill/plan
    heuristics:
      - "running": the agent is working, keep polling.
      - "stopped": the task itself finished; the structured_output_result is
        produced by a separate, asynchronous extraction pass shortly
        afterwards (see the Structured Output guide), so polling continues
        with its own `extraction_timeout` budget instead of the general
        inactivity `timeout`.
      - "waiting": the agent needs input. If it is asking a question
        (`waiting_for_event_type == "messageAskUser"`) it is nudged once to
        continue autonomously, since this pipeline has no interactive user
        in the loop; other waiting types are logged and bounded by the
        regular inactivity `timeout`.
      - "error": raises immediately with the reported error details.

    Previously, progress was tracked per DD skill (see SKILL_STEPS) and a
    skill with no matching event for `timeout` seconds was considered
    stalled. That heuristic could raise a false-positive TimeoutError (e.g.
    when a skill's plan step never matched our "done" keyword detection)
    and abort polling *before* the task actually stopped and Manus produced
    a structured result on its side - matching the reported symptom of "the
    structured output was created on Manus's side but never retrieved".
    Skill/plan progress is now only used for debug logging, never to decide
    when to give up.
    """
    overall_last_activity = time.time()
    stopped_at: float | None = None
    nudged_waiting = False
    seen_event_ids: set[str] = set()
    logger.info(
        "poll_for_result: starte Polling fuer Task %s (timeout=%ds, extraction_timeout=%ds)",
        task_id,
        timeout,
        extraction_timeout,
    )
    poll_count = 0
    while True:
        poll_count += 1
        events = list_task_messages(task_id, limit=50, verbose=True)
        logger.debug(
            "poll_for_result: Poll #%d, %d Event(s) erhalten", poll_count, len(events)
        )
        if events:
            overall_last_activity = time.time()
        # Process oldest -> newest so the final agent_status/stopped_at
        # reflect the *latest* known state (list_task_messages defaults to
        # newest-first order).
        for e in reversed(events):
            result = _extract_structured_output(e)
            if result is not None:
                logger.info(
                    "poll_for_result: strukturiertes Ergebnis erhalten fuer Task %s",
                    task_id,
                )
                return result

            # Only log for events not already seen on a previous poll: Manus
            # re-sends the same plan_update/status_update event id on every
            # poll while mutating it in place, so events must still be
            # re-processed every time but should only be logged once.
            event_id = e.get("id")
            is_new_event = bool(event_id) and event_id not in seen_event_ids
            if event_id:
                seen_event_ids.add(event_id)
            # Kept only for debug visibility into which skill is currently
            # active; must never influence the timeout/stop decisions below.
            step_id, _ = _detect_step_progress(e, log=is_new_event)
            if step_id and is_new_event:
                logger.debug("poll_for_result: Aktivitaet fuer Schritt '%s'", step_id)

            if e.get("type") != "status_update":
                continue
            status_info = e.get("status_update", {}) or {}
            agent_status = status_info.get("agent_status")

            if agent_status == "error":
                err_detail = status_info.get("description", "")
                logger.error(
                    "poll_for_result: Task %s fehlgeschlagen: %s", task_id, err_detail
                )
                raise RuntimeError(f"Manus Task fehlgeschlagen: {err_detail}")

            if agent_status == "stopped":
                if stopped_at is None:
                    stopped_at = time.time()
                    logger.info(
                        "poll_for_result: Task %s gestoppt, warte auf strukturiertes "
                        "Ergebnis (max. %ds)",
                        task_id,
                        extraction_timeout,
                    )
                continue

            if agent_status == "waiting":
                detail = status_info.get("status_detail", {}) or {}
                waiting_for = detail.get("waiting_for_event_type")
                description = detail.get("waiting_description") or status_info.get(
                    "description", ""
                )
                if waiting_for == "messageAskUser":
                    if is_new_event and not nudged_waiting:
                        logger.warning(
                            "poll_for_result: Task %s wartet auf Nutzerantwort (%s), "
                            "fordere eigenstaendige Fortsetzung an",
                            task_id,
                            description,
                        )
                        send_followup_message(
                            task_id,
                            "Bitte triff eine plausible Annahme und setze die Analyse "
                            "eigenständig fort, ohne auf eine Nutzerantwort zu warten. "
                            "Vermerke offene Fragen stattdessen als offenen Punkt im "
                            "Ergebnis.",
                        )
                        nudged_waiting = True
                elif is_new_event:
                    logger.warning(
                        "poll_for_result: Task %s wartet auf Bestaetigung (%s): %s",
                        task_id,
                        waiting_for,
                        description,
                    )
                continue

            # agent_status == "running" (or an unrecognized value): the task
            # is active again, so any earlier "stopped" sighting no longer
            # applies (extraction can only start after the *latest* stop).
            stopped_at = None
            nudged_waiting = False

        now = time.time()
        if stopped_at is not None and now - stopped_at >= extraction_timeout:
            logger.error(
                "poll_for_result: Task %s gestoppt, aber kein strukturiertes Ergebnis "
                "nach %ds erhalten",
                task_id,
                extraction_timeout,
            )
            raise TimeoutError(
                f"Task {task_id}: gestoppt, aber kein strukturiertes Ergebnis nach "
                f"{extraction_timeout}s erhalten."
            )
        if stopped_at is None and now - overall_last_activity >= timeout:
            logger.error(
                "poll_for_result: Task %s Timeout nach %ds ohne Aktivitaet",
                task_id,
                timeout,
            )
            raise TimeoutError(
                f"Task {task_id} Timeout nach {timeout}s ohne Aktivität."
            )
        time.sleep(5)


def get_available_skills(project_id: str | None = None) -> list:
    logger.info("get_available_skills: project_id=%s", project_id)
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
    skills = res.json().get("data", [])
    logger.debug("get_available_skills: %d Skill(s) erhalten", len(skills))
    return skills


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
            logger.debug(
                "list_task_messages: Task %s noch nicht indexiert (404), Versuch %d/%d",
                task_id,
                attempt + 1,
                retries,
            )
            time.sleep(delay)
            continue
        res.raise_for_status()
        # API returns key "messages", not "data"
        body = res.json()
        messages = body.get("messages") or body.get("data") or []
        logger.debug(
            "list_task_messages: Task %s -> %d Event(s) (limit=%d, verbose=%s)",
            task_id,
            len(messages),
            limit,
            verbose,
        )
        return messages
    logger.warning(
        "list_task_messages: Task %s nach %d Versuchen nicht erreichbar",
        task_id,
        retries,
    )
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
            logger.debug("_extract_structured_output: nicht-dict payload gefunden")
            return payload
        if payload.get("success") is False:
            logger.error(
                "_extract_structured_output: Schema-Fehler: %s", payload.get("error")
            )
            raise RuntimeError(f"Schema-Fehler: {payload.get('error')}")
        if "value" in payload:
            logger.debug("_extract_structured_output: Ergebnis unter 'value' gefunden")
            return payload["value"]
        if "result" in payload:
            logger.debug("_extract_structured_output: Ergebnis unter 'result' gefunden")
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
