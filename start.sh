#!/usr/bin/env bash
# Startet das Telegram Panel unter macOS und Linux.
set -e
cd "$(dirname "$0")"

if ! command -v python3 >/dev/null 2>&1; then
  echo
  echo "  Python 3 wurde nicht gefunden."
  echo "  macOS:  brew install python"
  echo "  Linux:  sudo apt install python3 python3-venv"
  echo
  exit 1
fi

if [ ! -d .venv ]; then
  echo "  Richte die Umgebung ein, das dauert einmalig ein bis zwei Minuten..."
  python3 -m venv .venv
fi

# shellcheck disable=SC1091
source .venv/bin/activate

# Neu installieren, wenn Pakete fehlen ODER sich die Liste seit dem letzten
# Mal geaendert hat - sonst faehrt ein Update mit alten Paketen los.
if ! python -c "import fastapi, telethon" >/dev/null 2>&1 \
   || ! cmp -s requirements.txt .venv/.requirements-stand; then
  echo "  Lade die benoetigten Pakete..."
  python -m pip install --quiet --upgrade pip
  python -m pip install --quiet -r requirements.txt
  cp requirements.txt .venv/.requirements-stand
fi

[ -f .env ] || cp .env.example .env

echo
echo "  Panel startet. Zum Beenden Strg+C."
echo
exec python run.py
