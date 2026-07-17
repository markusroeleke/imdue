"""Central stdlib logging configuration for the whole app.

Configures a single "imdue" logger hierarchy shared by src.app,
src.manus_client, src.pdf_generator, etc. In addition to a console handler
(useful for local dev / container logs), every log record is routed to a
per-chat-session log file (``session.log`` inside that session's folder
under ``sessions/<id>/``).

Routing to the correct session file is done via a ``contextvars.ContextVar``
holding the currently active session directory rather than a single global
file, so the same worker process logs correctly even if it ever handles
multiple chat sessions concurrently. The context must be bound once at the
top of each Chainlit event handler (see `bind_session_log`) and propagated
into any blocking helper run in a thread pool via `run_sync` (plain
`loop.run_in_executor` does NOT copy contextvars into the worker thread).
"""

from __future__ import annotations

import contextvars
import functools
import logging
from pathlib import Path
from typing import Callable, TypeVar

_LOGGER_ROOT_NAME = "imdue"

# Holds the session directory (as str) currently active for the running
# asyncio task / thread. Set via `bind_session_log`; read by
# `_SessionFileHandler.emit` to route the log record to the right file.
_current_session_dir: contextvars.ContextVar[str | None] = contextvars.ContextVar(
    "current_session_dir", default=None
)


class _SessionFileHandler(logging.Handler):
    """Routes each log record to session.log inside the active session dir.

    Caches one logging.FileHandler per session directory (opened lazily on
    first use) so repeated log calls don't reopen the file every time.
    Records emitted with no session bound in the current context (e.g. a
    standalone script like check_skills.py) are silently dropped by this
    handler - they still reach the console handler configured alongside it.
    """

    def __init__(self) -> None:
        super().__init__()
        self._file_handlers: dict[str, logging.FileHandler] = {}

    def _get_file_handler(self, session_dir: str) -> logging.FileHandler:
        handler = self._file_handlers.get(session_dir)
        if handler is None:
            log_path = Path(session_dir) / "session.log"
            handler = logging.FileHandler(log_path, encoding="utf-8")
            handler.setFormatter(
                logging.Formatter("%(asctime)s %(levelname)-8s %(name)s: %(message)s")
            )
            self._file_handlers[session_dir] = handler
        return handler

    def emit(self, record: logging.LogRecord) -> None:
        session_dir = _current_session_dir.get()
        if not session_dir:
            return
        try:
            self._get_file_handler(session_dir).emit(record)
        except Exception:
            self.handleError(record)

    def close_session(self, session_dir: str) -> None:
        handler = self._file_handlers.pop(session_dir, None)
        if handler is not None:
            handler.close()


_session_file_handler = _SessionFileHandler()
_configured = False


def configure_logging(level: int = logging.DEBUG) -> None:
    """Configure the shared "imdue" logger hierarchy. Call once at startup.

    Idempotent - safe to call multiple times (e.g. once per imported module).
    """
    global _configured
    root = logging.getLogger(_LOGGER_ROOT_NAME)
    root.setLevel(level)
    if _configured:
        return
    console_handler = logging.StreamHandler()
    console_handler.setFormatter(
        logging.Formatter("%(asctime)s %(levelname)-8s %(name)s: %(message)s")
    )
    root.addHandler(console_handler)
    root.addHandler(_session_file_handler)
    _configured = True


def get_logger(name: str) -> logging.Logger:
    """Return a logger under the shared "imdue" hierarchy."""
    return logging.getLogger(
        f"{_LOGGER_ROOT_NAME}.{name}" if name else _LOGGER_ROOT_NAME
    )


def bind_session_log(session_dir: str | Path) -> None:
    """Bind the current asyncio task/thread context to a session's log file.

    Every log record emitted from this task - and from child tasks/threads
    that inherit this context (asyncio.create_task, or `run_sync` below) -
    is appended to ``<session_dir>/session.log`` until a different session
    dir is bound in that context.
    """
    _current_session_dir.set(str(session_dir))


def close_session_log(session_dir: str | Path) -> None:
    """Close and drop the cached file handle for a finished session."""
    _session_file_handler.close_session(str(session_dir))


_T = TypeVar("_T")


async def run_sync(loop, func: Callable[..., _T], *args, **kwargs) -> _T:
    """Run a blocking function in the default executor, preserving context.

    Plain `loop.run_in_executor` does NOT copy the calling contextvars
    context into the worker thread, so a session dir bound via
    `bind_session_log` in the calling coroutine would otherwise be invisible
    to blocking helpers (e.g. src.manus_client functions) executed this way -
    their log records would silently be dropped by `_SessionFileHandler`
    (no active context => no file to write to). Wrapping the call with
    `contextvars.copy_context().run(...)` propagates it correctly.
    """
    ctx = contextvars.copy_context()
    return await loop.run_in_executor(
        None, functools.partial(ctx.run, functools.partial(func, *args, **kwargs))
    )
