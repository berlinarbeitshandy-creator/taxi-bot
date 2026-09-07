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

import uvicorn  # noqa: E402

from backend.config import PANEL_HOST, PANEL_PORT  # noqa: E402

if __name__ == "__main__":
    uvicorn.run("backend.main:app", host=PANEL_HOST, port=PANEL_PORT, reload=False)
