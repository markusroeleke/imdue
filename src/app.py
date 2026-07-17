import asyncio
import json
import shutil
import sys
import time
import uuid
from contextlib import suppress
from datetime import datetime
from pathlib import Path

# Ensure the project root is on sys.path when Chainlit loads this file directly
sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

import chainlit as cl
import requests
from dotenv import load_dotenv
from pypdf import PdfReader

from src.logging_utils import (
    bind_session_log,
    close_session_log,
    configure_logging,
    get_logger,
    run_sync,
)
from src.manus_client import (
    SKILL_STEPS,
    create_analysis_task,
    list_task_messages,
    match_skill,
    poll_for_result,
    send_followup_message,
    upload_file_to_manus,
)
from src.pdf_generator import generate_markdown, save_report
from src.schema import DUE_DILIGENCE_SCHEMA

load_dotenv()

configure_logging()
logger = get_logger("app")

# Generic, backend-agnostic messages shown to the user. Real exception details
# (which may reveal the backend provider, internal URLs, API responses, etc.)
# are only ever written to the server-side log, never sent to the chat.
GENERIC_ERROR_MESSAGE = "❌ Es ist ein Fehler aufgetreten. Bitte versuche es erneut."
GENERIC_UPLOAD_ERROR_MESSAGE = "❌ Upload fehlgeschlagen. Bitte versuche es erneut."
REPORT_DOWNLOAD_ENABLED = (
    True  # TODO: make this configurable (env var) if needed later.
)

# Global cap on follow-up/Ergänzung turns per analysis, to bound the extra
# Manus turns (cost/runtime) a single chat session can trigger after the
# initial analysis. TODO: make this configurable (env var) if needed later.
MAX_FOLLOWUP_QUESTIONS = 3

# Uploaded documents must be PDFs only, capped in number and length. Also
# enforced client-side via [features.spontaneous_file_upload] in
# .chainlit/config.toml (accept/max_files), but re-checked here server-side
# since that config can be bypassed (e.g. direct API calls, edited requests).
MAX_PDF_COUNT = 3
MAX_PDF_PAGES = 20

# Daily cap on new analyses (task.create calls) per client, to bound
# Manus API cost/usage. There is no login/auth system (MVP spec: "anonyme
# Sessions ohne Login"), so the client's IP address is used as a
# best-effort identity. Persisted to RATE_LIMIT_FILE so the cap survives
# app restarts and is shared across chat sessions/tabs from the same IP.
MAX_ANALYSES_PER_DAY = 2


def _log_error(context: str, exc: BaseException) -> None:
    """Log full exception details server-side only; never shown to the user."""
    logger.exception("%s: %s", context, exc)


def _format_elapsed(seconds: float) -> str:
    """Format a duration in seconds as a short human-readable string (e.g. '2m 5s')."""
    total = int(round(seconds))
    minutes, secs = divmod(total, 60)
    if minutes:
        return f"{minutes}m {secs}s"
    return f"{secs}s"


BASE_DIR = Path(__file__).parent.parent
SESSIONS_DIR = BASE_DIR / "sessions"
SESSIONS_DIR.mkdir(exist_ok=True)

RATE_LIMIT_FILE = SESSIONS_DIR / "rate_limits.json"
_rate_limit_lock = asyncio.Lock()

TRIGGER_WORDS = {
    "analyse",
    "analysieren",
    "analysiere",
    "bericht",
    "start",
    "auswerten",
}


def _new_session_dir() -> Path:
    """Create a fresh, uniquely named folder for one chat session.

    Holds everything produced during that session - uploaded documents, the
    generated report, and the raw JSON result from Manus - together in one
    place.
    """
    session_id = f"{datetime.now():%Y%m%d_%H%M%S}_{uuid.uuid4().hex[:8]}"
    session_dir = SESSIONS_DIR / session_id
    session_dir.mkdir(parents=True, exist_ok=True)
    logger.debug("_new_session_dir: erstellt %s", session_dir)
    return session_dir


def _client_ip() -> str:
    """Best-effort client identity for MAX_ANALYSES_PER_DAY (no auth exists).

    Chainlit's underlying python-socketio/engineio ASGI adapter always
    reports environ['REMOTE_ADDR'] as a hardcoded '127.0.0.1' (see
    engineio/async_drivers/asgi.py) rather than the real client address, so
    the real IP must be read from the raw ASGI scope instead. Falls back to
    'X-Forwarded-For' first in case of a reverse proxy in front of the app,
    then to 'unknown' (all such clients then share one bucket, the safe/
    conservative side to fail on) if neither is available.
    """
    environ = getattr(cl.context.session, "environ", None) or {}
    forwarded_for = environ.get("HTTP_X_FORWARDED_FOR")
    if forwarded_for:
        return forwarded_for.split(",")[0].strip()
    client = (environ.get("asgi.scope") or {}).get("client")
    if client:
        return client[0]
    return "unknown"


async def _check_daily_rate_limit(client_ip: str) -> bool:
    """Atomically check and, if allowed, register one analysis for today.

    Returns True (and registers the attempt) if `client_ip` is still under
    MAX_ANALYSES_PER_DAY for today (UTC date); returns False without
    registering anything if the daily cap is already reached.
    """
    today = datetime.now().strftime("%Y-%m-%d")
    async with _rate_limit_lock:
        state: dict = {}
        if RATE_LIMIT_FILE.exists():
            try:
                state = json.loads(RATE_LIMIT_FILE.read_text(encoding="utf-8"))
            except (json.JSONDecodeError, OSError) as exc:
                logger.warning(
                    "_check_daily_rate_limit: konnte %s nicht lesen: %s",
                    RATE_LIMIT_FILE,
                    exc,
                )
        entry = state.get(client_ip)
        count = entry["count"] if entry and entry.get("date") == today else 0
        if count >= MAX_ANALYSES_PER_DAY:
            logger.info(
                "_check_daily_rate_limit: Tageslimit erreicht fuer %s (%d/%d)",
                client_ip,
                count,
                MAX_ANALYSES_PER_DAY,
            )
            return False
        state[client_ip] = {"date": today, "count": count + 1}
        try:
            RATE_LIMIT_FILE.write_text(
                json.dumps(state, ensure_ascii=False, indent=2), encoding="utf-8"
            )
        except OSError as exc:
            logger.warning(
                "_check_daily_rate_limit: konnte %s nicht schreiben: %s",
                RATE_LIMIT_FILE,
                exc,
            )
        logger.info(
            "_check_daily_rate_limit: Analyse %d/%d heute fuer %s registriert",
            count + 1,
            MAX_ANALYSES_PER_DAY,
            client_ip,
        )
        return True


def _persist_upload(
    temp_path: str, original_name: str | None, session_dir: Path
) -> dict:
    """Store user upload in the current chat session's folder."""
    source = Path(temp_path)
    display_name = original_name or source.name
    safe_name = Path(display_name).name
    dest = session_dir / f"{uuid.uuid4().hex[:8]}_{safe_name}"
    shutil.copy2(source, dest)
    logger.debug("_persist_upload: %s -> %s", display_name, dest)
    return {"name": safe_name, "path": str(dest)}


def _validate_pdf_upload(temp_path: str, display_name: str) -> str | None:
    """Check that an uploaded file is a real PDF within the page limit.

    Returns an error message (to show the user) if the file is rejected,
    or `None` if it passes validation.
    """
    if Path(display_name).suffix.lower() != ".pdf":
        return f"❌ `{display_name}` ist keine PDF-Datei. Es werden ausschließlich PDF-Dokumente akzeptiert."
    try:
        num_pages = len(PdfReader(temp_path).pages)
    except (
        Exception
    ) as exc:  # noqa: BLE001 - any parse failure -> reject as invalid PDF
        logger.warning(
            "_validate_pdf_upload: %s konnte nicht als PDF gelesen werden: %s",
            display_name,
            exc,
        )
        return f"❌ `{display_name}` konnte nicht als gültige PDF-Datei gelesen werden."
    if num_pages > MAX_PDF_PAGES:
        return (
            f"❌ `{display_name}` hat {num_pages} Seiten. Maximal {MAX_PDF_PAGES} "
            "Seiten pro PDF sind erlaubt."
        )
    return None


async def _deliver_result(
    result: dict,
    *,
    session_dir: Path,
    task_id: str,
    start_time: float,
    started_at: datetime,
    document_count: int,
) -> None:
    """Persist a structured result and send the rendered report to the chat.

    Shared by the initial analysis and any later follow-up/Ergänzung that
    re-triggers a fresh structured_output_result, so both paths end up with
    the same saved session artifacts (result.json/report.md/timing.json)
    and the same chat response - never a raw JSON/text dump.
    """
    json_path = session_dir / "result.json"
    json_path.write_text(
        json.dumps(result, ensure_ascii=False, indent=2), encoding="utf-8"
    )
    logger.debug("_deliver_result: JSON-Ergebnis gespeichert unter %s", json_path)

    elapsed_seconds = time.monotonic() - start_time
    finished_at = datetime.now()
    elapsed_display = _format_elapsed(elapsed_seconds)

    report_md = generate_markdown(result, elapsed_display=elapsed_display)
    md_path = str(session_dir / "report.md")
    save_report(report_md, md_path)
    logger.info("_deliver_result: Bericht gespeichert unter %s", md_path)

    flags = result.get("red_flags", [])
    high = [f for f in flags if f["severity"] in ["High", "Critical"]]
    score_obj = result.get("investment_score", {})

    timing_path = session_dir / "timing.json"
    timing_path.write_text(
        json.dumps(
            {
                "task_id": task_id,
                "document_count": document_count,
                "started_at": started_at.isoformat(),
                "finished_at": finished_at.isoformat(),
                "elapsed_seconds": round(elapsed_seconds, 2),
            },
            ensure_ascii=False,
            indent=2,
        ),
        encoding="utf-8",
    )
    logger.info(
        "_deliver_result: Analyse-Dauer fuer Task %s: %.2fs (gespeichert unter %s)",
        task_id,
        elapsed_seconds,
        timing_path,
    )

    await cl.Message(
        content=(
            "## ✅ Analyse abgeschlossen\n\n"
            f"**Objekt:** {result.get('property_address') or '–'}\n"
            f"**Gesamtrisiko:** {result.get('overall_risk_level', '–')}\n"
            f"**Investment-Score:** {score_obj.get('score', '–')} — "
            f"{score_obj.get('classification', '–')}\n"
            f"**Empfehlung:** {result.get('recommendation', '–')}\n"
            f"**Red Flags:** {len(flags)} ({len(high)} kritisch)\n"
            f"**Analysedauer:** {elapsed_display}\n\n"
            "Vollständiger Bericht:↓"
        ),
    ).send()
    await cl.Message(content=report_md).send()
    if REPORT_DOWNLOAD_ENABLED:
        await cl.Message(
            content="Bericht als Datei:",
            elements=[
                cl.File(
                    name="Due_Diligence_Bericht.md",
                    path=md_path,
                    mime="text/markdown",
                )
            ],
        ).send()


async def stream_status_updates(
    task_id: str, status_msg: cl.Message, start_time: float
) -> None:
    """Periodically refresh `status_msg` with the analysis' progress.

    Only our own, curated German wording is ever shown to the user - never
    the backend's raw `brief`/`description`/tool-name text. That text is
    free-form and can reveal implementation details (which provider is used,
    internal tool names, etc.), so instead this derives a purely internal
    view of progress: which of the 10 DD skills (see SKILL_STEPS) is
    pending/running/done, plus a couple of curated milestones (started/
    finished a step, wrapping up the report). This still gives the user a
    meaningful, live glimpse into what is happening without ever leaking
    which backend/provider performs the analysis.
    """
    spinner = ["⣾", "⣽", "⣻", "⢿", "⡿", "⣟", "⣯", "⣷"]
    idx = 0
    seen_ids: set[str] = set()
    skill_ids = [sid for sid, _, _ in SKILL_STEPS]
    skill_status: dict[str, str] = {sid: "pending" for sid, _, _ in SKILL_STEPS}
    skill_label = {sid: label for sid, label, _ in SKILL_STEPS}
    milestones: list[str] = []
    loop = asyncio.get_running_loop()

    def note(text: str) -> None:
        """Append a curated (never backend-derived) milestone line, deduped."""
        if not milestones or milestones[-1] != text:
            milestones.append(text)

    def mark_done(skill_id: str) -> None:
        if skill_status[skill_id] != "done":
            skill_status[skill_id] = "done"
            note(f"✅ Abgeschlossen: {skill_label[skill_id]}")
        # Skill 9 (risk score) only starts once all prior skills (1-8) have
        # actually finished on the backend (see the orchestration prompt in
        # manus_client.create_analysis_task), so its start is a reliable
        # signal that every preceding step is done - even if we missed/
        # mismatched some of their individual "done" plan_update events.
        if skill_id == "dd-skill-09-risikoscore":
            for prev_id in skill_ids[: skill_ids.index(skill_id)]:
                mark_done(prev_id)

    def mark_running(skill_id: str) -> None:
        if skill_status[skill_id] == "pending":
            skill_status[skill_id] = "running"
            note(f"🔄 Gestartet: {skill_label[skill_id]}")
        if skill_id == "dd-skill-09-risikoscore":
            for prev_id in skill_ids[: skill_ids.index(skill_id)]:
                mark_done(prev_id)

    def apply_event(event: dict, log: bool = True) -> None:
        """Update skill_status/milestones from one backend event.

        Only ever reads which skill an event maps to (via `match_skill`) and
        the plan step's own status/`agent_status` enum value - never any
        free-form text is stored or displayed.
        """
        etype = event.get("type")
        if etype == "plan_update":
            for step in (event.get("plan_update", {}) or {}).get("steps", []) or []:
                skill_id = match_skill(step.get("title", ""), log=log)
                if not skill_id:
                    continue
                step_status = step.get("status")
                if step_status == "done":
                    mark_done(skill_id)
                elif step_status == "doing":
                    mark_running(skill_id)
        elif etype == "tool_used":
            tool_info = event.get("tool_used", {}) or {}
            text = f"{tool_info.get('brief', '')} {tool_info.get('description', '')}"
            skill_id = match_skill(text, log=log)
            if skill_id:
                mark_running(skill_id)
        elif etype == "status_update":
            status_info = event.get("status_update", {}) or {}
            text = (
                f"{status_info.get('brief', '')} {status_info.get('description', '')}"
            )
            skill_id = match_skill(text, log=log)
            if skill_id:
                mark_running(skill_id)
            agent_status = status_info.get("agent_status")
            if agent_status == "stopped":
                note("🧮 Ergebnisse werden zusammengeführt …")
            elif agent_status == "waiting":
                note("⏳ Ergänze fehlende Informationen …")

    def render_skill_checklist() -> str:
        icons = {"pending": "⬜", "running": "🔄", "done": "✅"}
        lines = [
            f"{icons[skill_status[sid]]} {i}. {label}"
            for i, (sid, label, _) in enumerate(SKILL_STEPS, start=1)
        ]
        return "\n".join(lines)

    logger.info(
        "stream_status_updates: starte Fortschrittsanzeige fuer Task %s", task_id
    )
    poll_count = 0
    try:
        while True:
            poll_count += 1
            try:
                events = await run_sync(
                    loop, list_task_messages, task_id, 30, "desc", True
                )
            except requests.exceptions.RequestException as exc:
                # A transient network blip here must not kill this
                # fire-and-forget progress display (the actual analysis
                # keeps polling independently via poll_for_result); just
                # skip this refresh and try again on the next iteration.
                logger.warning(
                    "stream_status_updates: Netzwerkfehler fuer Task %s (Poll #%d): %s",
                    task_id,
                    poll_count,
                    exc,
                )
                await asyncio.sleep(4)
                continue
            logger.debug(
                "stream_status_updates: Poll #%d fuer Task %s, %d Event(s)",
                poll_count,
                task_id,
                len(events),
            )
            for event in reversed(events):
                # Always re-apply status from every event the API currently
                # returns, even if its id was already seen: the backend
                # reuses the same event id for a plan_update while mutating
                # its `steps` statuses in place (a live snapshot, not a
                # one-off delta), so skipping already-seen ids would freeze
                # the checklist at whatever state it had when first seen.
                # Logging is still deduped: only genuinely new event ids are
                # logged, to avoid repeating the same debug line every poll.
                event_id = event.get("id")
                is_new_event = bool(event_id) and event_id not in seen_ids
                apply_event(event, log=is_new_event)
                if event_id:
                    seen_ids.add(event_id)
            idx = (idx + 1) % len(spinner)
            elapsed_display = _format_elapsed(time.monotonic() - start_time)
            base = f"{spinner[idx]} analysiere Dokumente … (⏱️ {elapsed_display})"
            checklist = render_skill_checklist()
            if milestones:
                recent = "\n".join(f"- {line}" for line in milestones[-5:])
                status_msg.content = (
                    f"{base}\n\n**Analyse-Fortschritt:**\n{checklist}\n\n"
                    f"**Letzte Updates:**\n{recent}"
                )
            else:
                status_msg.content = f"{base}\n\n**Analyse-Fortschritt:**\n{checklist}"
            await status_msg.update()
            await asyncio.sleep(4)
    except asyncio.CancelledError:
        logger.info(
            "stream_status_updates: Fortschrittsanzeige fuer Task %s beendet", task_id
        )
        raise


@cl.on_chat_start
async def start() -> None:
    session_dir = _new_session_dir()
    bind_session_log(session_dir)
    logger.info("start: neue Chat-Session gestartet, session_dir=%s", session_dir)
    cl.user_session.set("session_dir", str(session_dir))
    cl.user_session.set("pending_files", [])
    cl.user_session.set("task_id", None)
    cl.user_session.set("followup_count", 0)
    await cl.Message(
        content=(
            "## Willkommen bei der Immobilien Due Diligence KI\n\n"
            "1. Lade deine Maklerunterlagen als PDF hoch (Exposé, Grundbuch, Mietverträge, Gutachten …)\n"
            "2. Tippe `analysiere` im chat für den vollständigen Bericht\n"
            "3. Nach der Analyse kannst du Rückfragen stellen\n"
            "4. Du erhältst einen Bericht zum Download"
        )
    ).send()


@cl.on_chat_end
async def end() -> None:
    session_dir = cl.user_session.get("session_dir")
    if not session_dir:
        return
    bind_session_log(session_dir)
    logger.info("end: Chat-Session beendet, session_dir=%s", session_dir)
    close_session_log(session_dir)


@cl.on_message
async def main(message: cl.Message) -> None:
    pending_files: list = cl.user_session.get("pending_files", [])
    task_id: str | None = cl.user_session.get("task_id")
    session_dir = Path(cl.user_session.get("session_dir"))
    bind_session_log(session_dir)
    logger.debug(
        "main: Nachricht erhalten (%d Zeichen, %d Anhang/-haenge)",
        len(message.content),
        len(message.elements or []),
    )

    # --- Datei-Upload ---
    if message.elements:
        for el in message.elements:
            if hasattr(el, "path") and el.path:
                display_name = getattr(el, "name", None) or Path(el.path).name
                if len(pending_files) >= MAX_PDF_COUNT:
                    logger.info(
                        "main: Upload von %s abgelehnt, PDF-Limit erreicht (%d/%d)",
                        display_name,
                        len(pending_files),
                        MAX_PDF_COUNT,
                    )
                    await cl.Message(
                        content=(
                            f"❌ Maximal {MAX_PDF_COUNT} PDF-Dokumente pro Analyse sind "
                            f"erlaubt. `{display_name}` wurde nicht übernommen."
                        )
                    ).send()
                    continue
                msg = await cl.Message(content=f"Lade `{display_name}` hoch …").send()
                validation_error = _validate_pdf_upload(el.path, display_name)
                if validation_error:
                    logger.info(
                        "main: Upload von %s abgelehnt: %s",
                        display_name,
                        validation_error,
                    )
                    msg.content = validation_error
                    await msg.update()
                    continue
                try:
                    record = _persist_upload(el.path, display_name, session_dir)
                    pending_files.append(record)
                    cl.user_session.set("pending_files", pending_files)
                    logger.info(
                        "main: Datei gespeichert: %s (%d gesamt)",
                        record["name"],
                        len(pending_files),
                    )
                    msg.content = f"✅ `{record['name']}` gespeichert ({len(pending_files)} Dokument(e) gesamt)."
                    await msg.update()
                except Exception as exc:
                    _log_error("upload failed", exc)
                    msg.content = GENERIC_UPLOAD_ERROR_MESSAGE
                    await msg.update()
        return

    # --- Nachfragen/Ergänzungen zu einer bereits laufenden/abgeschlossenen
    # Analyse: ein Task wird immer weiterverwendet (egal ob es eine reine
    # Rückfrage ist oder ob dabei zusätzliche Dokumente hochgeladen wurden).
    # Ein neuer Manus-Task entsteht ausschließlich im ersten Zweig unten,
    # wenn diese Chat-Session noch gar keinen task_id hat (= neuer Chat).
    if task_id:
        followup_count: int = cl.user_session.get("followup_count", 0)
        if followup_count >= MAX_FOLLOWUP_QUESTIONS:
            logger.info(
                "main: Nachfrage-Limit erreicht fuer Task %s (%d/%d)",
                task_id,
                followup_count,
                MAX_FOLLOWUP_QUESTIONS,
            )
            await cl.Message(
                content=(
                    f"ℹ️ Maximal {MAX_FOLLOWUP_QUESTIONS} Rückfragen/Ergänzungen pro "
                    "Analyse sind aktuell möglich. Starte für weitere Fragen bitte "
                    "eine neue Analyse."
                )
            ).send()
            return
        cl.user_session.set("followup_count", followup_count + 1)
        logger.info(
            "main: Nachfrage/Ergaenzung zu Task %s (%d/%d, %d neue Datei(en))",
            task_id,
            followup_count + 1,
            MAX_FOLLOWUP_QUESTIONS,
            len(pending_files),
        )
        followup_start = time.monotonic()
        status_msg = await cl.Message(content="🔄 Verarbeite Ergänzung …").send()
        status_task = asyncio.create_task(
            stream_status_updates(task_id, status_msg, followup_start)
        )
        try:
            loop = asyncio.get_running_loop()
            file_ids: list[str] = []
            if pending_files:
                total = len(pending_files)
                for idx, info in enumerate(pending_files, start=1):
                    status_msg.content = (
                        f"⬆️ Lade zusätzliches Dokument {idx}/{total} hoch …"
                    )
                    await status_msg.update()
                    fid = await run_sync(
                        loop, upload_file_to_manus, info["path"], info["name"]
                    )
                    file_ids.append(fid)
                logger.info(
                    "main: %d zusaetzliche Datei(en) zu Manus hochgeladen fuer Task %s: %s",
                    len(file_ids),
                    task_id,
                    file_ids,
                )
                status_msg.content = "🔄 Verarbeite Ergänzung …"
                await status_msg.update()

            followup_text = message.content.strip() or (
                "Bitte berücksichtige die neu hochgeladenen Dokumente und "
                "aktualisiere die Analyse entsprechend."
            )
            # Re-arm the schema so this follow-up turn produces a fresh
            # structured_output_result instead of a plain text reply (a
            # schema is only consumed once per task.sendMessage/task.create,
            # see the Structured Output guide).
            await run_sync(
                loop,
                send_followup_message,
                task_id,
                followup_text,
                DUE_DILIGENCE_SCHEMA,
                file_ids or None,
            )
            try:
                result: dict = await run_sync(loop, poll_for_result, task_id)
            finally:
                status_task.cancel()
                with suppress(asyncio.CancelledError):
                    await status_task
            logger.info("main: aktualisiertes Ergebnis fuer Task %s erhalten", task_id)

            status_msg.content = "📄 Aktualisiere Bericht …"
            await status_msg.update()

            document_count = cl.user_session.get("document_count", 0) + len(file_ids)
            cl.user_session.set("document_count", document_count)

            await _deliver_result(
                result,
                session_dir=session_dir,
                task_id=task_id,
                start_time=followup_start,
                started_at=datetime.now(),
                document_count=document_count,
            )
        except Exception as exc:
            _log_error("followup failed", exc)
            await cl.Message(content=GENERIC_ERROR_MESSAGE).send()
        else:
            if pending_files:
                cl.user_session.set("pending_files", [])
        return

    # --- Analyse starten (erster Task dieser Chat-Session) ---
    if message.content.lower().strip() in TRIGGER_WORDS:
        if not pending_files:
            logger.info("main: Analyse angefordert, aber keine Dokumente hochgeladen")
            await cl.Message(content="Bitte zuerst Dokumente hochladen.").send()
            return

        client_ip = _client_ip()
        if not await _check_daily_rate_limit(client_ip):
            await cl.Message(
                content=(
                    f"❌ Du hast das Tageslimit von {MAX_ANALYSES_PER_DAY} Analysen "
                    "erreicht. Bitte versuche es morgen erneut."
                )
            ).send()
            return

        logger.info("main: starte Analyse fuer %d Dokument(e)", len(pending_files))
        msg = await cl.Message(
            content=f"Starte Analyse für {len(pending_files)} Dokument(e) …"
        ).send()
        analysis_started_at = datetime.now()
        start_time = time.monotonic()
        try:
            loop = asyncio.get_running_loop()
            file_ids: list[str] = []
            total = len(pending_files)
            for idx, info in enumerate(pending_files, start=1):
                elapsed_display = _format_elapsed(time.monotonic() - start_time)
                msg.content = (
                    f"⬆️ Lade Dokument {idx}/{total} zur Analyse … "
                    f"(⏱️ {elapsed_display})"
                )
                await msg.update()
                fid = await run_sync(
                    loop, upload_file_to_manus, info["path"], info["name"]
                )
                file_ids.append(fid)
            logger.info(
                "main: %d Datei(en) zu Manus hochgeladen: %s", len(file_ids), file_ids
            )

            msg.content = (
                f"🔍 Analysiere Dokumente … "
                f"(⏱️ {_format_elapsed(time.monotonic() - start_time)})"
            )
            await msg.update()

            new_task_id = await run_sync(
                loop, create_analysis_task, file_ids, DUE_DILIGENCE_SCHEMA
            )
            logger.info("main: Analyse-Task erstellt: %s", new_task_id)
            cl.user_session.set("task_id", new_task_id)
            cl.user_session.set("document_count", len(pending_files))

            status_task = asyncio.create_task(
                stream_status_updates(new_task_id, msg, start_time)
            )

            try:
                result: dict = await run_sync(loop, poll_for_result, new_task_id)
            finally:
                status_task.cancel()
                with suppress(asyncio.CancelledError):
                    await status_task
            logger.info("main: Analyse-Ergebnis fuer Task %s erhalten", new_task_id)

            msg.content = "📄 Erstelle Bericht …"
            await msg.update()

            await _deliver_result(
                result,
                session_dir=session_dir,
                task_id=new_task_id,
                start_time=start_time,
                started_at=analysis_started_at,
                document_count=len(pending_files),
            )

        except Exception as exc:
            _log_error("analysis failed", exc)
            elapsed_seconds = time.monotonic() - start_time
            timing_path = session_dir / "timing.json"
            timing_path.write_text(
                json.dumps(
                    {
                        "task_id": cl.user_session.get("task_id"),
                        "document_count": len(pending_files),
                        "started_at": analysis_started_at.isoformat(),
                        "finished_at": datetime.now().isoformat(),
                        "elapsed_seconds": round(elapsed_seconds, 2),
                        "error": str(exc.__class__.__name__),
                    },
                    ensure_ascii=False,
                    indent=2,
                ),
                encoding="utf-8",
            )
            await cl.Message(content=GENERIC_ERROR_MESSAGE).send()
        else:
            cl.user_session.set("pending_files", [])
        return

    await cl.Message(
        content="Lade Dokumente hoch und tippe `analyse` für den Bericht."
    ).send()
