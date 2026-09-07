"""Hintergrund-Jobs: Pool pruefen, Mitglieder aufnehmen, Beitrittsanfragen
genehmigen."""
from __future__ import annotations

import asyncio
import time
from typing import Any

from telethon import errors

from . import db, telegram_manager as tg
from .config import ADD_DELAY, API_DELAY

_tasks: dict[int, asyncio.Task] = {}


# --------------------------------------------------------------------------
# Job-Buchhaltung
# --------------------------------------------------------------------------

def create_job(kind: str, account_id: int | None, target: str) -> int:
    return db.execute(
        "INSERT INTO jobs (kind, account_id, target, status, stats, log, created_at)"
        " VALUES (?,?,?,?,?,?,?)",
        (kind, account_id, target, "running", "{}", "[]", db.now()),
    )


def _append_log(job_id: int, level: str, message: str) -> None:
    row = db.query_one("SELECT log FROM jobs WHERE id = ?", (job_id,))
    entries = db.loads(row["log"] if row else None, [])
    entries.append({"t": time.time(), "level": level, "msg": message})
    db.execute("UPDATE jobs SET log = ? WHERE id = ?", (db.dumps(entries[-500:]), job_id))


def _set_stats(job_id: int, stats: dict[str, Any]) -> None:
    db.execute("UPDATE jobs SET stats = ? WHERE id = ?", (db.dumps(stats), job_id))


def _finish(job_id: int, status: str) -> None:
    db.execute(
        "UPDATE jobs SET status = ?, finished_at = ? WHERE id = ?",
        (status, db.now(), job_id),
    )


def get_job(job_id: int) -> dict[str, Any] | None:
    job = db.query_one("SELECT * FROM jobs WHERE id = ?", (job_id,))
    if not job:
        return None
    job["stats"] = db.loads(job["stats"], {})
    job["log"] = db.loads(job["log"], [])
    return job


def list_jobs(limit: int = 30) -> list[dict[str, Any]]:
    rows = db.query(
        "SELECT id, kind, account_id, target, status, stats, created_at, finished_at"
        " FROM jobs ORDER BY created_at DESC LIMIT ?",
        (limit,),
    )
    for row in rows:
        row["stats"] = db.loads(row["stats"], {})
    return rows


def cancel_job(job_id: int) -> bool:
    task = _tasks.get(job_id)
    if task and not task.done():
        task.cancel()
        return True
    return False


def _spawn(job_id: int, coro) -> None:
    """Startet den Job im laufenden Event-Loop.

    Die aufrufenden Endpunkte sind async, damit hier ein Loop existiert -
    laeuft der Aufruf trotzdem ausserhalb, wird der Job als Fehler markiert
    statt fuer immer auf "running" stehen zu bleiben.
    """
    try:
        task = asyncio.create_task(coro)
    except RuntimeError as exc:
        coro.close()
        _append_log(job_id, "error", f"Job konnte nicht gestartet werden: {exc}")
        _finish(job_id, "error")
        raise
    _tasks[job_id] = task
    task.add_done_callback(lambda _t: _tasks.pop(job_id, None))


# --------------------------------------------------------------------------
# Job 1: Pool-Eintraege aufloesen
# --------------------------------------------------------------------------

def start_pool_check(account_id: int, only_new: bool = True) -> int:
    job_id = create_job("pool_check", account_id, "pool")
    _spawn(job_id, _run_pool_check(job_id, account_id, only_new))
    return job_id


async def _run_pool_check(job_id: int, account_id: int, only_new: bool) -> None:
    sql = "SELECT * FROM pool"
    if only_new:
        sql += " WHERE status IN ('new', 'error')"
    sql += " ORDER BY id"
    entries = db.query(sql)

    stats = {"total": len(entries), "done": 0, "ok": 0, "dead": 0, "failed": 0}
    _set_stats(job_id, stats)
    _append_log(job_id, "info", f"{len(entries)} Pool-Einträge werden geprüft.")

    try:
        account = tg.get_account(account_id)
        async with tg.AccountClient(account) as client:
            for entry in entries:
                username = entry["username"]
                try:
                    user = await client.get_entity(username)
                    display = " ".join(
                        p for p in [getattr(user, "first_name", None),
                                    getattr(user, "last_name", None)] if p
                    ).strip()
                    db.execute(
                        "UPDATE pool SET status = 'valid', reason = '', tg_user_id = ?,"
                        " display = ?, is_premium = ?, checked_at = ? WHERE id = ?",
                        (
                            user.id,
                            display or username,
                            1 if getattr(user, "premium", False) else 0,
                            db.now(),
                            entry["id"],
                        ),
                    )
                    stats["ok"] += 1
                except (ValueError, errors.UsernameInvalidError, errors.UsernameNotOccupiedError):
                    db.execute(
                        "UPDATE pool SET status = 'dead', reason = ?, checked_at = ?"
                        " WHERE id = ?",
                        ("existiert nicht", db.now(), entry["id"]),
                    )
                    stats["dead"] += 1
                    _append_log(job_id, "warn", f"{username}: nicht gefunden")
                except errors.FloodWaitError as exc:
                    _append_log(job_id, "warn", f"Flood-Limit: warte {exc.seconds}s")
                    await asyncio.sleep(exc.seconds + 1)
                    continue
                except Exception as exc:
                    db.execute(
                        "UPDATE pool SET status = 'error', checked_at = ? WHERE id = ?",
                        (db.now(), entry["id"]),
                    )
                    stats["failed"] += 1
                    _append_log(job_id, "error", f"{username}: {exc}")

                stats["done"] += 1
                _set_stats(job_id, stats)
                await asyncio.sleep(API_DELAY)

        _append_log(job_id, "info", "Pool-Prüfung abgeschlossen.")
        _finish(job_id, "done")
    except asyncio.CancelledError:
        _append_log(job_id, "warn", "Abgebrochen.")
        _finish(job_id, "cancelled")
        raise
    except tg.TelegramError as exc:
        _append_log(job_id, "error", str(exc))
        _finish(job_id, "error")
    except Exception as exc:
        _append_log(job_id, "error", f"Unerwarteter Fehler: {exc}")
        _finish(job_id, "error")


# --------------------------------------------------------------------------
# Job 2: Beitrittsanfragen gegen den Pool genehmigen
# --------------------------------------------------------------------------

def start_approve(
    account_id: int,
    target: str,
    *,
    pool_only: bool = True,
    watch_minutes: int = 0,
) -> int:
    job_id = create_job("approve", account_id, target)
    _spawn(job_id, _run_approve(job_id, account_id, target, pool_only, watch_minutes))
    return job_id


def _pool_lookup() -> tuple[set[str], set[int]]:
    rows = db.query("SELECT username, tg_user_id FROM pool")
    names = {r["username"].lower().lstrip("@") for r in rows}
    ids = {r["tg_user_id"] for r in rows if r["tg_user_id"]}
    return names, ids


async def _run_approve(
    job_id: int,
    account_id: int,
    target: str,
    pool_only: bool,
    watch_minutes: int,
) -> None:
    stats = {"approved": 0, "skipped": 0, "failed": 0, "seen": 0, "rounds": 0}
    _set_stats(job_id, stats)
    mode = "nur Pool-Mitglieder" if pool_only else "alle Anfragen"
    _append_log(job_id, "info", f"Ziel: {target} — Modus: {mode}")

    deadline = time.time() + watch_minutes * 60 if watch_minutes else 0

    try:
        account = tg.get_account(account_id)
        async with tg.AccountClient(account) as client:
            peer = await tg._resolve_target(client, target)

            while True:
                stats["rounds"] += 1
                names, ids = _pool_lookup()
                requests = await tg.pending_join_requests(account_id, target)
                stats["seen"] = len(requests)
                _set_stats(job_id, stats)

                if not requests:
                    _append_log(job_id, "info", "Keine offenen Beitrittsanfragen.")

                for req in requests:
                    username = (req.get("username") or "").lower()
                    in_pool = (username and username in names) or req["user_id"] in ids

                    if pool_only and not in_pool:
                        stats["skipped"] += 1
                        continue

                    label = f"@{username}" if username else str(req["user_id"])
                    try:
                        await tg.approve_join_request(client, peer, req["user_id"])
                        stats["approved"] += 1
                        _append_log(job_id, "info", f"{label} genehmigt")
                        if username:
                            db.execute(
                                "UPDATE pool SET status = 'joined' WHERE lower(username) = ?",
                                (username,),
                            )
                        elif req["user_id"]:
                            db.execute(
                                "UPDATE pool SET status = 'joined' WHERE tg_user_id = ?",
                                (req["user_id"],),
                            )
                    except errors.FloodWaitError as exc:
                        _append_log(job_id, "warn", f"Flood-Limit: warte {exc.seconds}s")
                        await asyncio.sleep(exc.seconds + 1)
                    except errors.UserChannelsTooMuchError:
                        stats["failed"] += 1
                        _append_log(job_id, "warn", f"{label}: hat zu viele Gruppen")
                    except Exception as exc:
                        stats["failed"] += 1
                        _append_log(job_id, "error", f"{label}: {exc}")

                    _set_stats(job_id, stats)
                    await asyncio.sleep(API_DELAY)

                if not deadline or time.time() >= deadline:
                    break
                await asyncio.sleep(30)

        _append_log(job_id, "info", f"Fertig — {stats['approved']} genehmigt.")
        _finish(job_id, "done")
    except asyncio.CancelledError:
        _append_log(job_id, "warn", "Abgebrochen.")
        _finish(job_id, "cancelled")
        raise
    except tg.TelegramError as exc:
        _append_log(job_id, "error", str(exc))
        _finish(job_id, "error")
    except Exception as exc:
        _append_log(job_id, "error", f"Unerwarteter Fehler: {exc}")
        _finish(job_id, "error")


# --------------------------------------------------------------------------
# Job 3: Pool-Mitglieder direkt in die Zielgruppe aufnehmen
# --------------------------------------------------------------------------

# Wer nicht aufgenommen werden kann, wird tot markiert und faellt aus den
# folgenden Durchlaeufen raus. Der Grund steht in der Spalte daneben, damit
# man Blockaden von wirklich toten Accounts unterscheiden kann.
_STATUS_FOR_OUTCOME = {
    tg.ADDED: "added",
    tg.ALREADY: "added",
    tg.PRIVACY: "dead",
    tg.FAILED: "dead",
}


def start_add(
    account_id: int,
    target: str,
    *,
    delay: float = ADD_DELAY,
    limit: int = 0,
    only_valid: bool = True,
) -> int:
    job_id = create_job("add", account_id, target)
    _spawn(job_id, _run_add(job_id, account_id, target, delay, limit, only_valid))
    return job_id


def _add_candidates(only_valid: bool, limit: int) -> list[dict[str, Any]]:
    if only_valid:
        sql = "SELECT * FROM pool WHERE status = 'valid' ORDER BY id"
    else:
        # Tote und bereits aufgenommene Eintraege kosten sonst nur Versuche.
        sql = "SELECT * FROM pool WHERE status NOT IN ('added', 'dead') ORDER BY id"
    entries = db.query(sql)
    return entries[:limit] if limit else entries


async def _run_add(
    job_id: int,
    account_id: int,
    target: str,
    delay: float,
    limit: int,
    only_valid: bool,
) -> None:
    entries = _add_candidates(only_valid, limit)
    stats = {
        "total": len(entries),
        "done": 0,
        "added": 0,
        "already": 0,
        "privacy": 0,
        "failed": 0,
    }
    _set_stats(job_id, stats)
    _append_log(
        job_id,
        "info",
        f"{len(entries)} Einträge, Pause {delay:.0f}s zwischen den Aufnahmen.",
    )

    if not entries:
        _append_log(
            job_id, "warn", "Nichts zu tun — Pool leer oder alles schon aufgenommen."
        )
        _finish(job_id, "done")
        return

    try:
        account = tg.get_account(account_id)
        async with tg.AccountClient(account) as client:
            peer = await tg.resolve_peer(client, target)

            for index, entry in enumerate(entries):
                username = entry["username"]
                identifier = entry["tg_user_id"] or username

                while True:  # wiederholt nur nach einem abgewarteten Flood-Limit
                    try:
                        outcome, message = await tg.add_user_to_group(
                            client, peer, identifier
                        )
                    except errors.FloodWaitError as exc:
                        _append_log(job_id, "warn", f"Flood-Limit: warte {exc.seconds}s")
                        await asyncio.sleep(exc.seconds + 1)
                        continue
                    except errors.PeerFloodError:
                        # Telegram hat den Account als auffaellig eingestuft.
                        # Weitermachen kostet hier den Account, nicht nur den Job.
                        _append_log(
                            job_id,
                            "error",
                            "Telegram hat den Account vorläufig für diese Aktion "
                            "gesperrt (PeerFlood). Job gestoppt — später mit "
                            "größerer Pause erneut versuchen.",
                        )
                        _finish(job_id, "error")
                        return
                    break

                stats[outcome] += 1
                db.execute(
                    "UPDATE pool SET status = ?, reason = ? WHERE id = ?",
                    (
                        _STATUS_FOR_OUTCOME[outcome],
                        "" if outcome in (tg.ADDED, tg.ALREADY) else message,
                        entry["id"],
                    ),
                )

                level = "info" if outcome in (tg.ADDED, tg.ALREADY) else "warn"
                _append_log(job_id, level, f"@{username}: {message}")

                stats["done"] += 1
                _set_stats(job_id, stats)

                if index < len(entries) - 1:
                    await asyncio.sleep(delay)

        _append_log(
            job_id,
            "info",
            f"Fertig — {stats['added']} aufgenommen, {stats['already']} schon drin, "
            f"{stats['privacy'] + stats['failed']} als tot markiert "
            f"({stats['privacy']} Privatsphäre, {stats['failed']} sonstiges).",
        )
        _finish(job_id, "done")
    except asyncio.CancelledError:
        _append_log(job_id, "warn", "Abgebrochen.")
        _finish(job_id, "cancelled")
        raise
    except tg.TelegramError as exc:
        _append_log(job_id, "error", str(exc))
        _finish(job_id, "error")
    except Exception as exc:
        _append_log(job_id, "error", f"Unerwarteter Fehler: {exc}")
        _finish(job_id, "error")
