import asyncio
import functools
import logging
import re
import shutil
import sys
import uuid
from contextlib import suppress
from pathlib import Path

# Ensure the project root is on sys.path when Chainlit loads this file directly
sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

import chainlit as cl
from dotenv import load_dotenv

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

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger("imdue")

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


BASE_DIR = Path(__file__).parent.parent
REPORTS_DIR = BASE_DIR / "reports"
REPORTS_DIR.mkdir(exist_ok=True)
UPLOAD_DIR = BASE_DIR / "uploads"
UPLOAD_DIR.mkdir(exist_ok=True)

TRIGGER_WORDS = {
    "analyse",
    "analysieren",
    "analysiere",
    "bericht",
    "start",
    "auswerten",
}


def _persist_upload(temp_path: str, original_name: str | None) -> dict:
    """Store user upload on disk until Manus analysis starts."""
    source = Path(temp_path)
    display_name = original_name or source.name
    safe_name = Path(display_name).name
    dest = UPLOAD_DIR / f"{uuid.uuid4().hex}_{safe_name}"
    shutil.copy2(source, dest)
    return {"name": safe_name, "path": str(dest)}


def _cleanup_pending_files(pending_files: list[dict]) -> None:
    for info in pending_files:
        path = Path(info.get("path", ""))
        with suppress(OSError):
            if path.exists():
                path.unlink()


async def stream_status_updates(task_id: str, status_msg: cl.Message) -> None:
    spinner = ["⏳", "🔄", "🛠️", "⚙️"]
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

    try:
        while True:
            events = await loop.run_in_executor(
                None, functools.partial(list_task_messages, task_id, 30, verbose=True)
            )
            for event in reversed(events):
                event_id = event.get("id")
                if not event_id or event_id in seen_ids:
                    continue
                seen_ids.add(event_id)
                update_skill_status(event)
                if event.get("type") == "status_update":
                    steps.append(format_status(event))
            idx = (idx + 1) % len(spinner)
            base = f"{spinner[idx]} analysiere Dokumente …"
            checklist = render_skill_checklist()
            if steps:
                recent = "\n".join(f"- {line}" for line in steps[-5:])
                status_msg.content = (
                    f"{base}\n\n**Skill-Fortschritt:**\n{checklist}\n\n"
                    f"**Letzte Updates:**\n{recent}"
                )
            else:
                status_msg.content = f"{base}\n\n**Skill-Fortschritt:**\n{checklist}"
            await status_msg.update()
            await asyncio.sleep(4)
    except asyncio.CancelledError:
        pass


@cl.on_chat_start
async def start() -> None:
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


@cl.on_message
async def main(message: cl.Message) -> None:
    pending_files: list = cl.user_session.get("pending_files", [])
    task_id: str | None = cl.user_session.get("task_id")

    # --- Datei-Upload ---
    if message.elements:
        for el in message.elements:
            if hasattr(el, "path") and el.path:
                msg = await cl.Message(content=f"Lade `{el.name}` hoch …").send()
                try:
                    record = _persist_upload(el.path, getattr(el, "name", None))
                    pending_files.append(record)
                    cl.user_session.set("pending_files", pending_files)
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
            await cl.Message(content="Bitte zuerst Dokumente hochladen.").send()
            return

        msg = await cl.Message(
            content=f"Starte Analyse für {len(pending_files)} Dokument(e) …"
        ).send()
        try:
            loop = asyncio.get_running_loop()
            file_ids: list[str] = []
            total = len(pending_files)
            for idx, info in enumerate(pending_files, start=1):
                msg.content = f"⬆️ Lade Dokument {idx}/{total} zur Analyse …"
                await msg.update()
                fid = await loop.run_in_executor(
                    None, upload_file_to_manus, info["path"], info["name"]
                )
                file_ids.append(fid)

            msg.content = "🔍 Analysiere Dokumente …"
            await msg.update()

            new_task_id = await loop.run_in_executor(
                None, create_analysis_task, file_ids, DUE_DILIGENCE_SCHEMA
            )
            cl.user_session.set("task_id", new_task_id)

            status_task = asyncio.create_task(stream_status_updates(new_task_id, msg))

            try:
                result: dict = await loop.run_in_executor(
                    None, poll_for_result, new_task_id
                )
            finally:
                status_task.cancel()
                with suppress(asyncio.CancelledError):
                    await status_task

            msg.content = "📄 Erstelle Bericht …"
            await msg.update()

            report_md = generate_markdown(result)
            md_path = str(REPORTS_DIR / f"report_{uuid.uuid4().hex[:8]}.md")
            save_report(report_md, md_path)

            flags = result.get("red_flags", [])
            high = [f for f in flags if f["severity"] in ["High", "Critical"]]
            score_obj = result.get("investment_score", {})

            await cl.Message(
                content=(
                    "## ✅ Analyse abgeschlossen\n\n"
                    f"**Objekt:** {result.get('property_address') or '–'}\n"
                    f"**Gesamtrisiko:** {result.get('overall_risk_level', '–')}\n"
                    f"**Investment-Score:** {score_obj.get('score', '–')} — "
                    f"{score_obj.get('classification', '–')}\n"
                    f"**Empfehlung:** {result.get('recommendation', '–')}\n"
                    f"**Red Flags:** {len(flags)} ({len(high)} kritisch)\n\n"
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
            await cl.Message(content=GENERIC_ERROR_MESSAGE).send()
        else:
            _cleanup_pending_files(pending_files)
            cl.user_session.set("pending_files", [])
        return

    # --- Nachfragen nach abgeschlossener Analyse ---
    if task_id:
        try:
            loop = asyncio.get_running_loop()
            await loop.run_in_executor(
                None, send_followup_message, task_id, message.content
            )
            reply = await loop.run_in_executor(None, poll_for_followup_reply, task_id)
            reply = _sanitize_backend_text(reply) if reply else reply
            await cl.Message(content=reply or "(Keine Antwort erhalten)").send()
        except Exception as exc:
            _log_error("followup failed", exc)
            await cl.Message(content=GENERIC_ERROR_MESSAGE).send()
        return

    await cl.Message(
        content="Lade Dokumente hoch und tippe `analyse` für den Bericht."
    ).send()
