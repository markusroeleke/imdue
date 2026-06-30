import asyncio
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
    create_analysis_task,
    list_task_messages,
    poll_for_followup_reply,
    poll_for_result,
    send_followup_message,
    upload_file_to_manus,
)
from src.pdf_generator import generate_markdown, save_report
from src.schema import DUE_DILIGENCE_SCHEMA

load_dotenv()

BASE_DIR = Path(__file__).parent.parent
REPORTS_DIR = BASE_DIR / "reports"
REPORTS_DIR.mkdir(exist_ok=True)
UPLOAD_DIR = BASE_DIR / "uploads"
UPLOAD_DIR.mkdir(exist_ok=True)

TRIGGER_WORDS = {"analyse", "analysieren", "bericht", "start", "auswerten"}


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
    loop = asyncio.get_running_loop()

    def format_status(event: dict) -> str:
        # API spec fields: agent_status, brief, description
        status_info = event.get("status_update", {}) or {}
        brief = status_info.get("brief") or status_info.get("description", "")
        agent_status = status_info.get("agent_status", "")
        parts: list[str] = []
        if brief:
            parts.append(brief)
        elif agent_status:
            parts.append(agent_status.capitalize())
        return parts[0] if parts else "Status-Update"

    try:
        while True:
            events = await loop.run_in_executor(None, list_task_messages, task_id, 20)
            for event in reversed(events):
                event_id = event.get("id")
                if not event_id or event_id in seen_ids:
                    continue
                seen_ids.add(event_id)
                if event.get("type") == "status_update":
                    steps.append(format_status(event))
            idx = (idx + 1) % len(spinner)
            base = f"{spinner[idx]} KI analysiert Dokumente …"
            if steps:
                recent = "\n".join(f"- {line}" for line in steps[-5:])
                status_msg.content = f"{base}\n{recent}"
            else:
                status_msg.content = f"{base}\n- KI arbeitet weiter …"
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
            "2. Tippe `analyse` für den vollständigen Bericht\n"
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
                    msg.content = f"❌ Upload fehlgeschlagen: {exc}"
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
                msg.content = f"⬆️ Lade Dokument {idx}/{total} zu Manus …"
                await msg.update()
                fid = await loop.run_in_executor(
                    None, upload_file_to_manus, info["path"], info["name"]
                )
                file_ids.append(fid)

            msg.content = "🔍 KI analysiert Dokumente …"
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
                    )
                ],
            ).send()

        except Exception as exc:
            await cl.Message(content=f"❌ Fehler bei der Analyse: {exc}").send()
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
            await cl.Message(content=reply or "(Keine Antwort erhalten)").send()
        except Exception as exc:
            await cl.Message(content=f"❌ Fehler: {exc}").send()
        return

    await cl.Message(
        content="Lade Dokumente hoch und tippe `analyse` für den Bericht."
    ).send()
