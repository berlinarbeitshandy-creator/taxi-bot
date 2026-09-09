"""HTTP-Endpunkte des Panels."""
from __future__ import annotations

import re
from typing import Any

from fastapi import APIRouter, HTTPException

from . import db, jobs, quota, schemas
from . import telegram_manager as tg
from .devices import DEVICE_PROFILES

router = APIRouter(prefix="/api")

USERNAME_RE = re.compile(r"[A-Za-z0-9_]{4,32}")


def _fail(exc: Exception) -> HTTPException:
    return HTTPException(status_code=400, detail=str(exc))


# --------------------------------------------------------------------------
# Stammdaten
# --------------------------------------------------------------------------

@router.get("/devices")
def devices() -> list[dict[str, str]]:
    return DEVICE_PROFILES


@router.get("/stats")
def stats() -> dict[str, Any]:
    accounts = db.query("SELECT status, is_premium FROM accounts")
    pool = db.query("SELECT status FROM pool")
    running = db.query_one("SELECT COUNT(*) AS c FROM jobs WHERE status = 'running'")
    return {
        "accounts": len(accounts),
        "accounts_online": sum(1 for a in accounts if a["status"] == "online"),
        "accounts_premium": sum(1 for a in accounts if a["is_premium"]),
        "pool": len(pool),
        "pool_valid": sum(1 for p in pool if p["status"] == "valid"),
        "pool_dead": sum(1 for p in pool if p["status"] == "dead"),
        # Noch keinem Account zugewiesen - das ist es, was ein Start verteilen kann.
        "pool_free_valid": jobs.available_count(True),
        "pool_free_open": jobs.available_count(False),
        # In der Gruppe angekommen - direkt aufgenommen oder ueber eine
        # genehmigte Beitrittsanfrage.
        "pool_joined": sum(1 for p in pool if p["status"] in ("added", "joined")),
        "jobs_running": running["c"] if running else 0,
    }


# --------------------------------------------------------------------------
# Accounts
# --------------------------------------------------------------------------

def _public_account(row: dict[str, Any]) -> dict[str, Any]:
    proxy = db.loads(row["proxy"], {}) or {}
    return {
        "id": row["id"],
        "label": row["label"],
        "phone": row["phone"],
        "api_id": row["api_id"],
        "device_id": row["device_id"],
        "status": row["status"],
        "username": row["username"],
        "first_name": row["first_name"],
        "is_premium": bool(row["is_premium"]),
        "last_error": row["last_error"],
        "last_check": row["last_check"],
        "created_at": row["created_at"],
        "quota": quota.state(row),
        "proxy": {
            "type": proxy.get("type"),
            "host": proxy.get("host"),
            "port": proxy.get("port"),
            "has_auth": bool(proxy.get("username")),
        }
        if proxy.get("host")
        else None,
    }


@router.get("/accounts")
def list_accounts() -> list[dict[str, Any]]:
    rows = db.query("SELECT * FROM accounts ORDER BY created_at DESC")
    return [_public_account(row) for row in rows]


@router.post("/accounts/login/start")
async def login_start(payload: schemas.LoginStart) -> dict[str, Any]:
    proxy = payload.proxy.model_dump() if payload.proxy else None
    if proxy and not proxy.get("host"):
        proxy = None
    if proxy and not proxy.get("port"):
        raise HTTPException(status_code=400, detail="Proxy-Port fehlt.")
    try:
        return await tg.start_login(
            phone=payload.phone.strip(),
            api_id=payload.api_id,
            api_hash=payload.api_hash.strip(),
            device_id=payload.device_id,
            proxy=proxy,
            label=payload.label.strip(),
        )
    except tg.TelegramError as exc:
        raise _fail(exc) from exc


@router.post("/accounts/login/code")
async def login_code(payload: schemas.LoginCode) -> dict[str, Any]:
    try:
        return await tg.submit_code(payload.login_id, payload.code.strip())
    except tg.TelegramError as exc:
        raise _fail(exc) from exc


@router.post("/accounts/login/password")
async def login_password(payload: schemas.LoginPassword) -> dict[str, Any]:
    try:
        return await tg.submit_password(payload.login_id, payload.password)
    except tg.TelegramError as exc:
        raise _fail(exc) from exc


@router.post("/accounts/login/cancel/{login_id}")
async def login_cancel(login_id: str) -> dict[str, bool]:
    await tg.cancel_login(login_id)
    return {"ok": True}


@router.post("/accounts/{account_id}/refresh")
async def refresh(account_id: int) -> dict[str, Any]:
    try:
        return _public_account(await tg.refresh_account(account_id))
    except tg.TelegramError as exc:
        raise _fail(exc) from exc


@router.delete("/accounts/{account_id}")
async def delete_account(account_id: int, logout: bool = True) -> dict[str, bool]:
    if logout:
        try:
            await tg.logout_account(account_id)
        except tg.TelegramError:
            pass
    db.execute("DELETE FROM accounts WHERE id = ?", (account_id,))
    return {"ok": True}


@router.post("/accounts/{account_id}/release")
def release_quota(account_id: int) -> dict[str, Any]:
    """Hebt die Aufnahme-Pause sofort auf und setzt den Zähler zurück."""
    if not db.query_one("SELECT id FROM accounts WHERE id = ?", (account_id,)):
        raise HTTPException(status_code=404, detail="Account nicht gefunden.")
    return quota.release(account_id)


@router.get("/accounts/{account_id}/groups")
async def account_groups(account_id: int) -> list[dict[str, Any]]:
    try:
        return await tg.list_groups(account_id)
    except tg.TelegramError as exc:
        raise _fail(exc) from exc


# --------------------------------------------------------------------------
# Pool
# --------------------------------------------------------------------------

@router.get("/pool")
def list_pool(status: str | None = None, q: str | None = None) -> list[dict[str, Any]]:
    sql = "SELECT * FROM pool"
    params: list[Any] = []
    where = []
    if status and status != "all":
        where.append("status = ?")
        params.append(status)
    if q:
        where.append("(username LIKE ? OR display LIKE ?)")
        params += [f"%{q}%", f"%{q}%"]
    if where:
        sql += " WHERE " + " AND ".join(where)
    sql += " ORDER BY created_at DESC"
    return db.query(sql, tuple(params))


@router.post("/pool")
def add_pool(payload: schemas.PoolAdd) -> dict[str, Any]:
    found = USERNAME_RE.findall(payload.usernames.replace("t.me/", " "))
    added, skipped = 0, 0
    for raw in found:
        username = raw.lower()
        existing = db.query_one("SELECT id FROM pool WHERE lower(username) = ?", (username,))
        if existing:
            skipped += 1
            continue
        db.execute(
            "INSERT INTO pool (username, note, status, created_at) VALUES (?,?,?,?)",
            (raw, payload.note, "new", db.now()),
        )
        added += 1
    return {"added": added, "skipped": skipped, "parsed": len(found)}


@router.patch("/pool/{entry_id}")
def patch_pool(entry_id: int, payload: schemas.PoolPatch) -> dict[str, bool]:
    if payload.note is not None:
        db.execute("UPDATE pool SET note = ? WHERE id = ?", (payload.note, entry_id))
    if payload.status is not None:
        db.execute("UPDATE pool SET status = ? WHERE id = ?", (payload.status, entry_id))
    return {"ok": True}


@router.delete("/pool/{entry_id}")
def delete_pool(entry_id: int) -> dict[str, bool]:
    db.execute("DELETE FROM pool WHERE id = ?", (entry_id,))
    return {"ok": True}


@router.delete("/pool")
def clear_pool(status: str | None = None) -> dict[str, bool]:
    if status and status != "all":
        db.execute("DELETE FROM pool WHERE status = ?", (status,))
    else:
        db.execute("DELETE FROM pool", ())
    return {"ok": True}


# --------------------------------------------------------------------------
# Vorgang / Jobs
# --------------------------------------------------------------------------

@router.post("/invite")
async def invite(payload: schemas.InviteIn) -> dict[str, Any]:
    try:
        return await tg.create_invite_link(
            payload.account_id,
            payload.target,
            title=payload.title,
            request_needed=payload.request_needed,
            usage_limit=payload.usage_limit,
        )
    except tg.TelegramError as exc:
        raise _fail(exc) from exc


@router.get("/join-requests")
async def join_requests(account_id: int, target: str) -> list[dict[str, Any]]:
    try:
        return await tg.pending_join_requests(account_id, target)
    except tg.TelegramError as exc:
        raise _fail(exc) from exc


@router.post("/jobs/pool-check")
async def job_pool_check(payload: schemas.PoolCheckIn) -> dict[str, int]:
    return {"job_id": jobs.start_pool_check(payload.account_id, payload.only_new)}


@router.post("/jobs/add")
async def job_add(payload: schemas.AddIn) -> dict[str, list[int]]:
    """Startet je Account einen eigenen Job. Sie laufen parallel und teilen
    sich den Pool, ohne sich dieselben Namen zu greifen."""
    for account_id in payload.account_ids:
        if not db.query_one("SELECT id FROM accounts WHERE id = ?", (account_id,)):
            raise HTTPException(
                status_code=404, detail=f"Account {account_id} nicht gefunden."
            )

    return {
        "job_ids": [
            jobs.start_add(
                account_id,
                payload.target,
                delay=payload.delay,
                limit=payload.limit,
                only_valid=payload.only_valid,
            )
            for account_id in payload.account_ids
        ]
    }


@router.post("/jobs/approve")
async def job_approve(payload: schemas.ApproveIn) -> dict[str, int]:
    return {
        "job_id": jobs.start_approve(
            payload.account_id,
            payload.target,
            pool_only=payload.pool_only,
            watch_minutes=payload.watch_minutes,
        )
    }


@router.get("/jobs")
def job_list() -> list[dict[str, Any]]:
    return jobs.list_jobs()


@router.get("/jobs/{job_id}")
def job_detail(job_id: int) -> dict[str, Any]:
    job = jobs.get_job(job_id)
    if not job:
        raise HTTPException(status_code=404, detail="Job nicht gefunden.")
    return job


@router.post("/jobs/{job_id}/cancel")
def job_cancel(job_id: int) -> dict[str, bool]:
    return {"ok": jobs.cancel_job(job_id)}
