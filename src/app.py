import asyncio
import uuid
from pathlib import Path

import chainlit as cl
from dotenv import load_dotenv

from src.manus_client import (
    create_analysis_task,
    poll_for_result,
    send_followup_message,
    upload_file_to_manus,
)
from src.pdf_generator import generate_pdf
from src.schema import DUE_DILIGENCE_SCHEMA

load_dotenv()

REPORTS_DIR = Path(__file__).parent.parent / "reports"
REPORTS_DIR.mkdir(exist_ok=True)

TRIGGER_WORDS = {"analyse", "analysieren", "bericht", "start", "auswerten"}


@cl.on_chat_start
async def start() -> None:
    cl.user_session.set("file_ids", [])
    cl.user_session.set("file_names", [])
    cl.user_session.set("task_id", None)
    await cl.Message(
        content=(
            "## Willkommen bei der Immobilien Due Diligence KI\n\n"
            "1. Lade deine Maklerunterlagen hoch (Exposé, Grundbuch, Mietverträge, Gutachten …)\n"
            "2. Tippe `analyse` für den vollständigen Bericht\n"
            "3. Nach der Analyse kannst du Rückfragen stellen\n"
            "4. Du erhältst einen PDF-Bericht zum Download"
        )
    ).send()


@cl.on_message
async def main(message: cl.Message) -> None:
    file_ids: list = cl.user_session.get("file_ids", [])
    file_names: list = cl.user_session.get("file_names", [])
    task_id: str | None = cl.user_session.get("task_id")

    # --- File upload ---
    if message.elements:
        for el in message.elements:
            if hasattr(el, "path") and el.path:
                msg = await cl.Message(content=f"Lade `{el.name}` hoch …").send()
                try:
                    fid = upload_file_to_manus(el.path, el.name)
                    file_ids.append(fid)
                    file_names.append(el.name)
                    cl.user_session.set("file_ids", file_ids)
                    cl.user_session.set("file_names", file_names)
                    msg.content = f"✅ `{el.name}` hochgeladen ({len(file_ids)} Dokument(e) gesamt)."
                    await msg.update()
                except Exception as exc:
                    msg.content = f"❌ Upload fehlgeschlagen: {exc}"
                    await msg.update()
        return

    # --- Trigger analysis ---
    if message.content.lower().strip() in TRIGGER_WORDS:
        if not file_ids:
            await cl.Message(content="Bitte zuerst Dokumente hochladen.").send()
            return

        msg = await cl.Message(
            content=f"Starte Analyse für {len(file_ids)} Dokument(e) …"
        ).send()
        try:
            new_task_id = create_analysis_task(file_ids, DUE_DILIGENCE_SCHEMA)
            cl.user_session.set("task_id", new_task_id)
            msg.content = "🔍 KI analysiert Dokumente …"
            await msg.update()

            result: dict = await asyncio.get_event_loop().run_in_executor(
                None, poll_for_result, new_task_id
            )

            msg.content = "📄 Erstelle PDF-Bericht …"
            await msg.update()

            pdf_path = str(REPORTS_DIR / f"report_{uuid.uuid4().hex[:8]}.pdf")
            generate_pdf(result, pdf_path)

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
                    f"_{result.get('executive_summary', '')}_\n\n"
                    "Stelle gerne Rückfragen zu einzelnen Punkten."
                ),
                elements=[
                    cl.File(
                        name="Due_Diligence_Bericht.pdf",
                        path=pdf_path,
                        display="inline",
                    )
                ],
            ).send()

        except Exception as exc:
            await cl.Message(content=f"❌ Fehler bei der Analyse: {exc}").send()
        return

    # --- Follow-up questions after analysis ---
    if task_id:
        try:
            await asyncio.get_event_loop().run_in_executor(
                None, send_followup_message, task_id, message.content
            )
            # Poll for the plain-text reply (no structured output)
            events_res = await asyncio.get_event_loop().run_in_executor(
                None,
                lambda: __import__("requests").get(
                    "https://api.manus.ai/v2/task.listMessages",
                    headers=__import__(
                        "src.manus_client", fromlist=["_headers"]
                    )._headers(),
                    params={"task_id": task_id, "order": "desc", "limit": 5},
                    timeout=30,
                ),
            )
            events_res.raise_for_status()
            for e in events_res.json().get("data", []):
                if e.get("type") == "assistant_message":
                    await cl.Message(content=e.get("content", "")).send()
                    return
        except Exception as exc:
            await cl.Message(content=f"❌ Fehler: {exc}").send()
        return

    await cl.Message(
        content="Lade Dokumente hoch und tippe `analyse` für den Bericht."
    ).send()
