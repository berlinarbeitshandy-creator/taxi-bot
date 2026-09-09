#!/usr/bin/env python3
"""Startet das Panel."""
from __future__ import annotations

import os
from pathlib import Path

# .env einlesen, bevor die Konfiguration importiert wird.
_env = Path(__file__).resolve().parent / ".env"
if _env.exists():
    for line in _env.read_text().splitlines():
        line = line.strip()
        if not line or line.startswith("#") or "=" not in line:
            continue
        key, _, value = line.partition("=")
        os.environ.setdefault(key.strip(), value.strip())

import threading  # noqa: E402
import webbrowser  # noqa: E402

import uvicorn  # noqa: E402

from backend.config import PANEL_HOST, PANEL_PORT  # noqa: E402


def _open_browser(url: str) -> None:
    """Oeffnet das Panel, sobald der Server steht."""
    threading.Timer(1.5, lambda: webbrowser.open(url)).start()


if __name__ == "__main__":
    host = "127.0.0.1" if PANEL_HOST in ("0.0.0.0", "") else PANEL_HOST
    url = f"http://{host}:{PANEL_PORT}"

    lines = [f"Telegram Panel läuft auf  {url}", "Zum Beenden: Strg+C"]
    width = max(len(line) for line in lines) + 4
    print()
    print("  ┌" + "─" * width + "┐")
    for line in lines:
        print(f"  │  {line.ljust(width - 4)}  │")
    print("  └" + "─" * width + "┘")
    print()

    if os.getenv("PANEL_NO_BROWSER", "").strip() not in ("1", "true", "yes"):
        _open_browser(url)

    uvicorn.run(
        "backend.main:app",
        host=PANEL_HOST,
        port=PANEL_PORT,
        reload=False,
        log_level="warning",
    )
