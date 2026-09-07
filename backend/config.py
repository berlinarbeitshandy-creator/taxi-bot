"""Zentrale Pfade und Einstellungen des Panels."""
from __future__ import annotations

import os
from pathlib import Path

BASE_DIR = Path(__file__).resolve().parent.parent
DATA_DIR = Path(os.getenv("PANEL_DATA_DIR", BASE_DIR / "data"))
FRONTEND_DIR = BASE_DIR / "frontend"

DB_PATH = DATA_DIR / "panel.db"
SECRET_PATH = DATA_DIR / ".secret"

PANEL_USER = os.getenv("PANEL_USER", "admin")
PANEL_PASSWORD = os.getenv("PANEL_PASSWORD", "")
PANEL_HOST = os.getenv("PANEL_HOST", "127.0.0.1")
PANEL_PORT = int(os.getenv("PANEL_PORT", "8000"))

# Wartezeit zwischen einzelnen Telegram-Aufrufen in Sekunden.
API_DELAY = float(os.getenv("PANEL_API_DELAY", "1.5"))

# Standardpause zwischen zwei Hinzufuege-Aktionen in Sekunden. Telegram
# begrenzt diese Aktion deutlich strenger als reine Lesezugriffe.
ADD_DELAY = float(os.getenv("PANEL_ADD_DELAY", "45"))

# Wie viele Aufnahme-Versuche ein Account machen darf, bevor er pausiert.
ADD_QUOTA = int(os.getenv("PANEL_ADD_QUOTA", "40"))

# Wie lange die Pause dauert, wenn sie nicht vorher freigegeben wird.
COOLDOWN_HOURS = float(os.getenv("PANEL_COOLDOWN_HOURS", "10"))

# Abbruch, wenn Telegram nicht erreichbar ist (Firewall, toter Proxy).
CONNECT_TIMEOUT = float(os.getenv("PANEL_CONNECT_TIMEOUT", "25"))

DATA_DIR.mkdir(parents=True, exist_ok=True)
