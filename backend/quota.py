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
from .config import ADD_QUOTA, COOLDOWN_HOURS, QUOTA_MAX, QUOTA_MIN, WARMUP_QUOTA

# Aufwaermleiter: was ein Account je nach Vorleistung tragen sollte.
# Ein frisch gebundener Account faellt Telegram schneller auf als einer,
# der schon Wochen unauffaellig laeuft.
WARMUP_STEPS = [
    (0, WARMUP_QUOTA, "Frisch gebunden — erst warmlaufen lassen."),
    (30, 20, "Läuft an — du kannst etwas hochgehen."),
    (100, 30, "Gut eingelaufen."),
    (250, ADD_QUOTA, "Eingelaufen — die Faustregel passt."),
]


def recommended_limit(adds_total: int) -> tuple[int, str]:
    """Empfohlenes Kontingent und die Begruendung dazu."""
    limit, reason = WARMUP_STEPS[0][1], WARMUP_STEPS[0][2]
    for threshold, value, text in WARMUP_STEPS:
        if adds_total >= threshold:
            limit, reason = value, text
    return limit, reason


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
    total = account.get("adds_total") or 0
    limit = account.get("quota_limit") or ADD_QUOTA
    until = account.get("cooldown_until")
    seconds_left = max(0.0, until - db.now()) if until else 0.0
    advice, reason = recommended_limit(total)
    return {
        "used": used,
        "limit": limit,
        "remaining": max(0, limit - used),
        "blocked": bool(until),
        "cooldown_until": until,
        "seconds_left": seconds_left,
        "cooldown_text": format_left(seconds_left) if until else "",
        # Aufwaermen
        "total": total,
        "recommended": advice,
        "advice": reason,
        "min": QUOTA_MIN,
        "max": QUOTA_MAX,
    }


def set_limit(account_id: int, limit: int) -> dict[str, Any]:
    """Setzt das Kontingent eines Accounts, begrenzt auf die Reglergrenzen."""
    limit = max(QUOTA_MIN, min(QUOTA_MAX, int(limit)))
    db.execute(
        "UPDATE accounts SET quota_limit = ? WHERE id = ?", (limit, account_id)
    )
    account = db.query_one("SELECT * FROM accounts WHERE id = ?", (account_id,))

    # Wer das Limit hochzieht, waehrend der Account pausiert, will weiter -
    # die Pause endet dann, sobald wieder Luft ist.
    if account and account["cooldown_until"] and (account["adds_used"] or 0) < limit:
        db.execute(
            "UPDATE accounts SET cooldown_until = NULL WHERE id = ?", (account_id,)
        )
        account = db.query_one("SELECT * FROM accounts WHERE id = ?", (account_id,))
    return state(account or {"id": account_id})


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
    """Zaehlt einen Versuch und startet bei Erreichen des Limits die Pause.

    adds_used wird bei jeder Freigabe zurueckgesetzt, adds_total nie - daran
    haengt die Aufwaerm-Empfehlung.
    """
    db.execute(
        "UPDATE accounts SET adds_used = adds_used + 1, adds_total = adds_total + 1"
        " WHERE id = ?",
        (account_id,),
    )
    account = db.query_one("SELECT * FROM accounts WHERE id = ?", (account_id,))
    if not account:
        return {"used": 0, "limit": ADD_QUOTA, "remaining": ADD_QUOTA, "blocked": False}

    limit = account["quota_limit"] or ADD_QUOTA
    if (account["adds_used"] or 0) >= limit and not account["cooldown_until"]:
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
