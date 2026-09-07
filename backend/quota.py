"""Aufnahme-Kontingent je Account.

Ein Account darf eine begrenzte Zahl Aufnahme-Versuche machen, danach
pausiert er. Die Pause endet entweder, wenn sie von Hand freigegeben wird,
oder nach Ablauf des Timers.

Gezaehlt wird jeder Versuch, der Telegram tatsaechlich erreicht hat - auch
ein abgelehnter. Telegram zaehlt Anfragen, nicht Erfolge, und genau die
abgelehnten sind es, die eine Sperre ausloesen.
"""
from __future__ import annotations

from typing import Any

from . import db
from .config import ADD_QUOTA, COOLDOWN_HOURS


class QuotaBlocked(Exception):
    """Der Account pausiert gerade."""

    def __init__(self, seconds_left: float):
        self.seconds_left = seconds_left
        # format_left endet bereits mit einem Abkuerzungspunkt.
        super().__init__(f"Account pausiert noch {format_left(seconds_left)}")


def format_left(seconds: float) -> str:
    seconds = max(0, int(seconds))
    hours, rest = divmod(seconds, 3600)
    minutes = rest // 60
    if hours and minutes:
        return f"{hours} Std. {minutes} Min."
    if hours:
        return f"{hours} Std."
    return f"{max(1, minutes)} Min."


def _expire_if_due(account: dict[str, Any]) -> dict[str, Any]:
    """Laeuft der Timer ab, ist der Account wieder frei."""
    until = account.get("cooldown_until")
    if until and until <= db.now():
        db.execute(
            "UPDATE accounts SET adds_used = 0, cooldown_until = NULL WHERE id = ?",
            (account["id"],),
        )
        account = dict(account)
        account["adds_used"] = 0
        account["cooldown_until"] = None
    return account


def state(account: dict[str, Any]) -> dict[str, Any]:
    """Kontingentstand fuer die Anzeige."""
    account = _expire_if_due(account)
    used = account.get("adds_used") or 0
    until = account.get("cooldown_until")
    seconds_left = max(0.0, until - db.now()) if until else 0.0
    return {
        "used": used,
        "limit": ADD_QUOTA,
        "remaining": max(0, ADD_QUOTA - used),
        "blocked": bool(until),
        "cooldown_until": until,
        "seconds_left": seconds_left,
        "cooldown_text": format_left(seconds_left) if until else "",
    }


def require_free(account_id: int) -> dict[str, Any]:
    """Wirft QuotaBlocked, wenn der Account gerade pausiert."""
    account = db.query_one("SELECT * FROM accounts WHERE id = ?", (account_id,))
    if not account:
        return state({"id": account_id, "adds_used": 0, "cooldown_until": None})
    current = state(account)
    if current["blocked"]:
        raise QuotaBlocked(current["seconds_left"])
    return current


def record_attempt(account_id: int) -> dict[str, Any]:
    """Zaehlt einen Versuch und startet bei Erreichen des Limits die Pause."""
    db.execute(
        "UPDATE accounts SET adds_used = adds_used + 1 WHERE id = ?", (account_id,)
    )
    account = db.query_one("SELECT * FROM accounts WHERE id = ?", (account_id,))
    if not account:
        return {"used": 0, "limit": ADD_QUOTA, "remaining": ADD_QUOTA, "blocked": False}

    if (account["adds_used"] or 0) >= ADD_QUOTA and not account["cooldown_until"]:
        db.execute(
            "UPDATE accounts SET cooldown_until = ? WHERE id = ?",
            (db.now() + COOLDOWN_HOURS * 3600, account_id),
        )
        account = db.query_one("SELECT * FROM accounts WHERE id = ?", (account_id,))
    return state(account)


def release(account_id: int) -> dict[str, Any]:
    """Gibt den Account von Hand wieder frei."""
    db.execute(
        "UPDATE accounts SET adds_used = 0, cooldown_until = NULL WHERE id = ?",
        (account_id,),
    )
    account = db.query_one("SELECT * FROM accounts WHERE id = ?", (account_id,))
    return state(account or {"id": account_id, "adds_used": 0, "cooldown_until": None})
