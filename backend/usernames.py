"""Erkennung von @usernames in eingefuegtem Text.

Telegram-Regeln: 5 bis 32 Zeichen, nur Buchstaben, Ziffern und Unterstrich,
und das erste Zeichen muss ein Buchstabe sein.

Wichtiger als die Regeln ist aber, *was* ueberhaupt als Kandidat gilt. Wer
eine Tabelle einfuegt, hat dort auch Spaltentexte stehen - die duerfen nicht
im Pool landen. Deshalb:

* Steht irgendwo ein @, gelten nur die @-Namen. Alles andere ist Beiwerk.
* Steht nirgends ein @, wird zeilen- und kommaweise gelesen, und ein Eintrag
  zaehlt nur, wenn er fuer sich allein steht. Eine Zeile mit mehreren
  Woertern ist dann eine Tabellenzeile und kein Name.
"""
from __future__ import annotations

import re

# t.me/name und Konsorten auf @name eindampfen.
_LINK = re.compile(r"(?:https?://)?(?:www\.)?(?:t|telegram)\.me/(?:s/)?", re.IGNORECASE)

_AT_NAME = re.compile(r"@([A-Za-z0-9_]+)")
_BARE = re.compile(r"^[A-Za-z0-9_]+$")
_VALID = re.compile(r"^[A-Za-z][A-Za-z0-9_]{4,31}$")


def is_valid(name: str) -> bool:
    return bool(_VALID.match(name.strip().lstrip("@")))


def extract(text: str) -> tuple[list[str], list[str]]:
    """Zerlegt eingefuegten Text in gueltige und verworfene Namen.

    Verworfen werden nur echte Kandidaten - ein @5516 also, nicht jedes
    Wort im Text. Sonst waere die Zahl daneben wertlos.
    """
    text = _LINK.sub("@", text)

    if "@" in text:
        kandidaten = _AT_NAME.findall(text)
    else:
        kandidaten = []
        for stueck in re.split(r"[\n\r,;]+", text):
            stueck = stueck.strip()
            # Nur was allein auf seiner Zeile steht. Mehrere Woerter
            # nebeneinander sind eine Tabellenzeile, kein Name.
            if stueck and _BARE.match(stueck):
                kandidaten.append(stueck)

    valid: list[str] = []
    invalid: list[str] = []
    for name in kandidaten:
        (valid if _VALID.match(name) else invalid).append(name)
    return valid, invalid
