import asyncio
import json
import re
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
from dotenv import load_dotenv

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
    poll_for_followup_reply,
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

# Patterns that could reveal which backend/provider is used; stripped from any
# text that originates from the backend before it is ever shown to the user.
_BACKEND_NAME_PATTERN = re.compile(r"manus", re.IGNORECASE)
_URL_PATTERN = re.compile(r"https?://\S+")


def _log_error(context: str, exc: BaseException) -> None:
    """Log full exception details server-side only; never shown to the user."""
    logger.exception("%s: %s", context, exc)


def _sanitize_backend_text(text: str) -> str:
    """Strip backend/provider names and URLs from text before showing it to the user."""
    text = _URL_PATTERN.sub("", text)
    text = _BACKEND_NAME_PATTERN.sub("Analyse-System", text)
    return text


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


async def stream_status_updates(task_id: str, status_msg: cl.Message) -> None:
    spinner = ["⣾", "⣽", "⣻", "⢿", "⡿", "⣟", "⣯", "⣷"]
    idx = 0
    seen_ids: set[str] = set()
    steps: list[str] = []
    skill_status: dict[str, str] = {sid: "pending" for sid, _, _ in SKILL_STEPS}
    loop = asyncio.get_running_loop()

    def format_status(event: dict) -> str:
        # API spec fields: agent_status, brief, description
        logger.debug("status event: %r", event)
        status_info = event.get("status_update", {}) or {}
        brief = status_info.get("brief") or status_info.get("description", "")
        agent_status = status_info.get("agent_status", "")
        parts: list[str] = []
        if brief:
            parts.append(brief)
        elif agent_status:
            parts.append(agent_status.capitalize())
        # never leak backend/provider names or URLs to the user
        parts = [_sanitize_backend_text(p) for p in parts]
        return parts[0] if parts else "Status-Update"

    def update_skill_status(event: dict) -> None:
        """Best-effort mapping of free-text backend events onto the 10 DD skills."""
        etype = event.get("type")
        if etype == "plan_update":
            for step in (event.get("plan_update", {}) or {}).get("steps", []) or []:
                skill_id = match_skill(step.get("title", ""))
                if not skill_id:
                    continue
                step_status = step.get("status")
                if step_status == "done":
                    skill_status[skill_id] = "done"
                elif step_status == "doing" and skill_status[skill_id] != "done":
                    skill_status[skill_id] = "running"
        elif etype == "tool_used":
            tool_info = event.get("tool_used", {}) or {}
            text = f"{tool_info.get('brief', '')} {tool_info.get('description', '')}"
            skill_id = match_skill(text)
            if skill_id and skill_status[skill_id] != "done":
                skill_status[skill_id] = "running"
        elif etype == "status_update":
            status_info = event.get("status_update", {}) or {}
            text = (
                f"{status_info.get('brief', '')} {status_info.get('description', '')}"
            )
            skill_id = match_skill(text)
            if skill_id and skill_status[skill_id] != "done":
                skill_status[skill_id] = "running"

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
            events = await run_sync(loop, list_task_messages, task_id, 30, "desc", True)
            logger.debug(
                "stream_status_updates: Poll #%d fuer Task %s, %d Event(s)",
                poll_count,
                task_id,
                len(events),
            )
            for event in reversed(events):
                # Always re-apply skill/plan status from every event the API
                # currently returns, even if its id was already seen: Manus
                # reuses the same event id for a plan_update while mutating
                # its `steps` statuses in place (a live snapshot, not a
                # one-off delta), so skipping already-seen ids would freeze
                # the checklist at whatever state it had when first seen.
                update_skill_status(event)
                event_id = event.get("id")
                if not event_id or event_id in seen_ids:
                    continue
                seen_ids.add(event_id)
                if event.get("type") == "status_update":
                    steps.append(format_status(event))
            idx = (idx + 1) % len(spinner)
            base = f"{spinner[idx]} analysiere Dokumente …"
            checklist = render_skill_checklist()
            if steps:
                recent = "\n".join(f"- {line}" for line in steps[-5:])
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
    await cl.Message(
        content=(
            "## Willkommen bei der Immobilien Due Diligence KI\n\n"
            "1. Lade deine Maklerunterlagen hoch (Exposé, Grundbuch, Mietverträge, Gutachten …)\n"
            "2. Tippe `analysiere` für den vollständigen Bericht\n"
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
                msg = await cl.Message(content=f"Lade `{el.name}` hoch …").send()
                try:
                    record = _persist_upload(
                        el.path, getattr(el, "name", None), session_dir
                    )
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

    # --- Analyse starten ---
    if message.content.lower().strip() in TRIGGER_WORDS:
        if not pending_files:
            logger.info("main: Analyse angefordert, aber keine Dokumente hochgeladen")
            await cl.Message(content="Bitte zuerst Dokumente hochladen.").send()
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
                msg.content = f"⬆️ Lade Dokument {idx}/{total} zur Analyse …"
                await msg.update()
                fid = await run_sync(
                    loop, upload_file_to_manus, info["path"], info["name"]
                )
                file_ids.append(fid)
            logger.info(
                "main: %d Datei(en) zu Manus hochgeladen: %s", len(file_ids), file_ids
            )

            msg.content = "🔍 Analysiere Dokumente …"
            await msg.update()

            new_task_id = await run_sync(
                loop, create_analysis_task, file_ids, DUE_DILIGENCE_SCHEMA
            )
            logger.info("main: Analyse-Task erstellt: %s", new_task_id)
            cl.user_session.set("task_id", new_task_id)

            status_task = asyncio.create_task(stream_status_updates(new_task_id, msg))

            try:
                result: dict = await run_sync(loop, poll_for_result, new_task_id)
            finally:
                status_task.cancel()
                with suppress(asyncio.CancelledError):
                    await status_task
            logger.info("main: Analyse-Ergebnis fuer Task %s erhalten", new_task_id)

            msg.content = "📄 Erstelle Bericht …"
            await msg.update()

            json_path = session_dir / "result.json"
            json_path.write_text(
                json.dumps(result, ensure_ascii=False, indent=2), encoding="utf-8"
            )
            logger.debug("main: JSON-Ergebnis gespeichert unter %s", json_path)

            # Compute elapsed time BEFORE generating the report so it can be
            # embedded in the report itself, not just mentioned in the chat.
            elapsed_seconds = time.monotonic() - start_time
            analysis_finished_at = datetime.now()
            elapsed_display = _format_elapsed(elapsed_seconds)

            report_md = generate_markdown(result, elapsed_display=elapsed_display)
            md_path = str(session_dir / "report.md")
            save_report(report_md, md_path)
            logger.info("main: Bericht gespeichert unter %s", md_path)

            flags = result.get("red_flags", [])
            high = [f for f in flags if f["severity"] in ["High", "Critical"]]
            score_obj = result.get("investment_score", {})

            timing_path = session_dir / "timing.json"
            timing_path.write_text(
                json.dumps(
                    {
                        "task_id": new_task_id,
                        "document_count": len(pending_files),
                        "started_at": analysis_started_at.isoformat(),
                        "finished_at": analysis_finished_at.isoformat(),
                        "elapsed_seconds": round(elapsed_seconds, 2),
                    },
                    ensure_ascii=False,
                    indent=2,
                ),
                encoding="utf-8",
            )
            logger.info(
                "main: Analyse-Dauer fuer Task %s: %.2fs (gespeichert unter %s)",
                new_task_id,
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

    # --- Nachfragen nach abgeschlossener Analyse ---
    if task_id:
        logger.info("main: Nachfrage zu Task %s", task_id)
        try:
            loop = asyncio.get_running_loop()
            await run_sync(loop, send_followup_message, task_id, message.content)
            reply = await run_sync(loop, poll_for_followup_reply, task_id)
            reply = _sanitize_backend_text(reply) if reply else reply
            logger.debug(
                "main: Nachfrage-Antwort erhalten (%d Zeichen)", len(reply or "")
            )
            await cl.Message(content=reply or "(Keine Antwort erhalten)").send()
        except Exception as exc:
            _log_error("followup failed", exc)
            await cl.Message(content=GENERIC_ERROR_MESSAGE).send()
        return

    await cl.Message(
        content="Lade Dokumente hoch und tippe `analyse` für den Bericht."
    ).send()
