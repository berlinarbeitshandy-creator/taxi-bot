"""Telethon-Anbindung: Account-Login, Client-Pool, Gruppen- und
Beitrittsanfragen-Funktionen."""
from __future__ import annotations

import asyncio
import secrets
from dataclasses import dataclass, field
from typing import Any

from telethon import TelegramClient, errors, functions, types
from telethon.sessions import StringSession

from . import db
from .config import API_DELAY, CONNECT_TIMEOUT
from .crypto import decrypt, encrypt
from .devices import get_device


class TelegramError(Exception):
    """Fehler, der als Klartext ans Panel gehen darf."""


def build_proxy(proxy: dict[str, Any] | None) -> tuple | None:
    """Uebersetzt die Proxy-Konfiguration aus dem Panel in Telethons Format."""
    if not proxy or not proxy.get("host"):
        return None

    kind = (proxy.get("type") or "socks5").lower()
    host = proxy["host"]
    port = int(proxy["port"])
    user = proxy.get("username") or None
    password = proxy.get("password") or None

    if kind == "mtproto":
        secret = proxy.get("secret") or ""
        if not secret:
            raise TelegramError("MTProto-Proxy braucht ein Secret.")
        return (host, port, secret)

    if kind not in {"socks5", "socks4", "http"}:
        raise TelegramError(f"Unbekannter Proxy-Typ: {kind}")

    if user:
        return (kind, host, port, True, user, password)
    return (kind, host, port)


def _client_kwargs(proxy: dict[str, Any] | None) -> dict[str, Any]:
    kwargs: dict[str, Any] = {}
    resolved = build_proxy(proxy)
    if resolved is None:
        return kwargs
    kwargs["proxy"] = resolved
    if (proxy or {}).get("type") == "mtproto":
        from telethon.network import ConnectionTcpMTProxyRandomizedIntermediate

        kwargs["connection"] = ConnectionTcpMTProxyRandomizedIntermediate
    return kwargs


def make_client(
    session: str | None,
    api_id: int,
    api_hash: str,
    device_id: str | None,
    proxy: dict[str, Any] | None,
) -> TelegramClient:
    device = get_device(device_id)
    return TelegramClient(
        StringSession(session or None),
        api_id,
        api_hash,
        device_model=device["device_model"],
        system_version=device["system_version"],
        app_version=device["app_version"],
        lang_code="de",
        system_lang_code="de",
        timeout=int(CONNECT_TIMEOUT),
        connection_retries=2,
        retry_delay=1,
        request_retries=2,
        **_client_kwargs(proxy),
    )


async def connect_with_timeout(client: TelegramClient) -> None:
    """Verbindet und bricht ab, statt bei blockiertem Netz haengen zu bleiben."""
    try:
        await asyncio.wait_for(client.connect(), timeout=CONNECT_TIMEOUT)
    except asyncio.TimeoutError as exc:
        raise TelegramError(
            "Telegram ist nicht erreichbar - Netzwerk oder Proxy pruefen."
        ) from exc


# --------------------------------------------------------------------------
# Login-Flow
# --------------------------------------------------------------------------

@dataclass
class PendingLogin:
    client: TelegramClient
    phone: str
    api_id: int
    api_hash: str
    device_id: str
    proxy: dict[str, Any] | None
    label: str
    phone_code_hash: str = ""
    extra: dict[str, Any] = field(default_factory=dict)


_pending: dict[str, PendingLogin] = {}


async def start_login(
    *,
    phone: str,
    api_id: int,
    api_hash: str,
    device_id: str,
    proxy: dict[str, Any] | None,
    label: str,
) -> dict[str, Any]:
    """Schritt 1: Verbindung aufbauen und Login-Code anfordern."""
    if db.query_one("SELECT id FROM accounts WHERE phone = ?", (phone,)):
        raise TelegramError(f"{phone} ist bereits gebunden.")

    client = make_client(None, api_id, api_hash, device_id, proxy)
    try:
        await connect_with_timeout(client)
    except TelegramError:
        await _safe_disconnect(client)
        raise
    except Exception as exc:  # Netzwerk-/Proxyfehler
        await _safe_disconnect(client)
        raise TelegramError(f"Verbindung fehlgeschlagen: {exc}") from exc

    try:
        sent = await asyncio.wait_for(
            client.send_code_request(phone), timeout=CONNECT_TIMEOUT
        )
    except errors.PhoneNumberInvalidError as exc:
        await _safe_disconnect(client)
        raise TelegramError("Telefonnummer ungueltig.") from exc
    except errors.ApiIdInvalidError as exc:
        await _safe_disconnect(client)
        raise TelegramError("API-ID und API-Hash passen nicht zusammen.") from exc
    except errors.FloodWaitError as exc:
        await _safe_disconnect(client)
        raise TelegramError(f"Flood-Limit: bitte {exc.seconds}s warten.") from exc
    except asyncio.TimeoutError as exc:
        await _safe_disconnect(client)
        raise TelegramError("Zeitueberschreitung beim Anfordern des Codes.") from exc
    except Exception as exc:
        await _safe_disconnect(client)
        raise TelegramError(str(exc)) from exc

    login_id = secrets.token_urlsafe(16)
    _pending[login_id] = PendingLogin(
        client=client,
        phone=phone,
        api_id=api_id,
        api_hash=api_hash,
        device_id=device_id,
        proxy=proxy,
        label=label,
        phone_code_hash=sent.phone_code_hash,
    )
    return {"login_id": login_id, "step": "code"}


async def submit_code(login_id: str, code: str) -> dict[str, Any]:
    """Schritt 2: Login-Code pruefen."""
    pending = _pending.get(login_id)
    if not pending:
        raise TelegramError("Login-Sitzung abgelaufen. Bitte neu starten.")

    try:
        await pending.client.sign_in(
            phone=pending.phone,
            code=code,
            phone_code_hash=pending.phone_code_hash,
        )
    except errors.SessionPasswordNeededError:
        return {"login_id": login_id, "step": "password"}
    except errors.PhoneCodeInvalidError as exc:
        raise TelegramError("Code ist falsch.") from exc
    except errors.PhoneCodeExpiredError as exc:
        await _drop_pending(login_id)
        raise TelegramError("Code ist abgelaufen. Bitte neu starten.") from exc
    except Exception as exc:
        raise TelegramError(str(exc)) from exc

    return await _finish_login(login_id)


async def submit_password(login_id: str, password: str) -> dict[str, Any]:
    """Schritt 3: Zwei-Faktor-Passwort (Cloud-Passwort)."""
    pending = _pending.get(login_id)
    if not pending:
        raise TelegramError("Login-Sitzung abgelaufen. Bitte neu starten.")

    try:
        await pending.client.sign_in(password=password)
    except errors.PasswordHashInvalidError as exc:
        raise TelegramError("Passwort ist falsch.") from exc
    except Exception as exc:
        raise TelegramError(str(exc)) from exc

    return await _finish_login(login_id)


async def _finish_login(login_id: str) -> dict[str, Any]:
    pending = _pending.pop(login_id)
    client = pending.client
    try:
        me = await client.get_me()
        session_string = client.session.save()
    finally:
        await _safe_disconnect(client)

    account_id = db.execute(
        """
        INSERT INTO accounts
            (label, phone, api_id, api_hash_enc, session_enc, proxy, device_id,
             status, tg_user_id, username, first_name, is_premium, last_check, created_at)
        VALUES (?,?,?,?,?,?,?,?,?,?,?,?,?,?)
        """,
        (
            pending.label or (me.first_name or pending.phone),
            pending.phone,
            pending.api_id,
            encrypt(pending.api_hash),
            encrypt(session_string),
            db.dumps(pending.proxy or {}),
            pending.device_id,
            "online",
            me.id,
            me.username,
            me.first_name,
            1 if getattr(me, "premium", False) else 0,
            db.now(),
            db.now(),
        ),
    )
    return {"step": "done", "account_id": account_id}


async def cancel_login(login_id: str) -> None:
    await _drop_pending(login_id)


async def _drop_pending(login_id: str) -> None:
    pending = _pending.pop(login_id, None)
    if pending:
        await _safe_disconnect(pending.client)


async def _safe_disconnect(client: TelegramClient) -> None:
    try:
        result = client.disconnect()
        if asyncio.iscoroutine(result):
            await result
    except Exception:
        pass


# --------------------------------------------------------------------------
# Client fuer gebundene Accounts
# --------------------------------------------------------------------------

class AccountClient:
    """Async-Contextmanager, der einen verbundenen Client liefert."""

    def __init__(self, account: dict[str, Any]):
        self.account = account
        self.client: TelegramClient | None = None

    async def __aenter__(self) -> TelegramClient:
        account = self.account
        api_hash = decrypt(account["api_hash_enc"])
        session = decrypt(account["session_enc"])
        if not api_hash or not session:
            raise TelegramError(
                "Session konnte nicht entschluesselt werden - "
                "wurde PANEL_SECRET_KEY geaendert?"
            )

        client = make_client(
            session,
            account["api_id"],
            api_hash,
            account["device_id"],
            db.loads(account["proxy"], None),
        )
        try:
            await connect_with_timeout(client)
        except Exception as exc:
            await _safe_disconnect(client)
            message = str(exc) if isinstance(exc, TelegramError) else f"Verbindung fehlgeschlagen: {exc}"
            _mark_error(account["id"], message)
            raise TelegramError(message) from exc

        if not await client.is_user_authorized():
            await _safe_disconnect(client)
            _mark_error(account["id"], "Session ungueltig - Account neu binden.")
            raise TelegramError("Session ungueltig - Account neu binden.")

        self.client = client
        return client

    async def __aexit__(self, *_exc) -> None:
        if self.client:
            await _safe_disconnect(self.client)


def _mark_error(account_id: int, message: str) -> None:
    db.execute(
        "UPDATE accounts SET status = 'error', last_error = ?, last_check = ? WHERE id = ?",
        (message, db.now(), account_id),
    )


def get_account(account_id: int) -> dict[str, Any]:
    account = db.query_one("SELECT * FROM accounts WHERE id = ?", (account_id,))
    if not account:
        raise TelegramError("Account nicht gefunden.")
    return account


async def refresh_account(account_id: int) -> dict[str, Any]:
    """Verbindet kurz und aktualisiert Status, Name und Premium-Flag."""
    account = get_account(account_id)
    async with AccountClient(account) as client:
        me = await client.get_me()
        db.execute(
            """
            UPDATE accounts
               SET status = 'online', last_error = NULL, last_check = ?,
                   tg_user_id = ?, username = ?, first_name = ?, is_premium = ?
             WHERE id = ?
            """,
            (
                db.now(),
                me.id,
                me.username,
                me.first_name,
                1 if getattr(me, "premium", False) else 0,
                account_id,
            ),
        )
    return get_account(account_id)


async def logout_account(account_id: int) -> None:
    """Meldet die Session bei Telegram ab, damit sie nicht offen bleibt."""
    account = get_account(account_id)
    try:
        async with AccountClient(account) as client:
            await client.log_out()
    except TelegramError:
        pass  # Session war ohnehin schon tot.


# --------------------------------------------------------------------------
# Gruppen / Zielgruppe
# --------------------------------------------------------------------------

async def list_groups(account_id: int) -> list[dict[str, Any]]:
    """Gruppen und Kanaele, in denen der Account Mitglied ist."""
    account = get_account(account_id)
    groups: list[dict[str, Any]] = []
    async with AccountClient(account) as client:
        async for dialog in client.iter_dialogs():
            if not (dialog.is_group or dialog.is_channel):
                continue
            entity = dialog.entity
            groups.append(
                {
                    "id": dialog.id,
                    "title": dialog.name,
                    "username": getattr(entity, "username", None),
                    "is_channel": bool(getattr(entity, "broadcast", False)),
                    "is_admin": bool(getattr(entity, "creator", False))
                    or getattr(entity, "admin_rights", None) is not None,
                    "can_invite": bool(
                        getattr(entity, "creator", False)
                        or getattr(getattr(entity, "admin_rights", None), "invite_users", False)
                    ),
                    "participants": getattr(entity, "participants_count", None),
                }
            )
    groups.sort(key=lambda g: (not g["can_invite"], (g["title"] or "").lower()))
    return groups


async def create_invite_link(
    account_id: int,
    target: str | int,
    *,
    title: str = "",
    request_needed: bool = True,
    usage_limit: int | None = None,
) -> dict[str, Any]:
    """Erzeugt einen Einladungslink fuer die Zielgruppe.

    Mit request_needed=True muss jeder Beitritt bestaetigt werden - genau
    darauf setzt der Auto-Approve-Job auf.
    """
    account = get_account(account_id)
    async with AccountClient(account) as client:
        peer = await _resolve_target(client, target)
        try:
            result = await client(
                functions.messages.ExportChatInviteRequest(
                    peer=peer,
                    title=title or "Panel-Einladung",
                    request_needed=request_needed,
                    usage_limit=None if request_needed else usage_limit,
                )
            )
        except errors.ChatAdminRequiredError as exc:
            raise TelegramError(
                "Der Account braucht Admin-Rechte mit 'Nutzer einladen' in dieser Gruppe."
            ) from exc
        except Exception as exc:
            raise TelegramError(str(exc)) from exc

    link = getattr(result, "link", None) or getattr(
        getattr(result, "invite", None), "link", None
    )
    return {"link": link, "request_needed": request_needed}


async def _resolve_target(client: TelegramClient, target: str | int):
    if isinstance(target, int):
        return await client.get_entity(target)
    value = str(target).strip()
    if value.lstrip("-").isdigit():
        return await client.get_entity(int(value))
    if value.startswith("https://t.me/") or value.startswith("t.me/"):
        value = value.split("t.me/", 1)[1].strip("/")
        if value.startswith("+") or value.startswith("joinchat/"):
            raise TelegramError(
                "Bitte die Zielgruppe waehlen, in der der Account bereits Mitglied ist."
            )
    return await client.get_entity(value.lstrip("@"))


async def pending_join_requests(account_id: int, target: str | int) -> list[dict[str, Any]]:
    """Offene Beitrittsanfragen der Zielgruppe."""
    account = get_account(account_id)
    out: list[dict[str, Any]] = []
    async with AccountClient(account) as client:
        peer = await _resolve_target(client, target)
        offset_user: types.TypeInputUser = types.InputUserEmpty()
        offset_date = None
        while True:
            try:
                res = await client(
                    functions.messages.GetChatInviteImportersRequest(
                        peer=peer,
                        requested=True,
                        offset_date=offset_date,
                        offset_user=offset_user,
                        limit=100,
                        q="",
                    )
                )
            except errors.ChatAdminRequiredError as exc:
                raise TelegramError(
                    "Der Account braucht Admin-Rechte mit 'Nutzer einladen' in dieser Gruppe."
                ) from exc

            users = {u.id: u for u in res.users}
            if not res.importers:
                break
            for importer in res.importers:
                user = users.get(importer.user_id)
                out.append(
                    {
                        "user_id": importer.user_id,
                        "username": getattr(user, "username", None),
                        "name": " ".join(
                            p for p in [getattr(user, "first_name", None),
                                        getattr(user, "last_name", None)] if p
                        ).strip(),
                        "is_premium": bool(getattr(user, "premium", False)),
                        "requested_at": importer.date.timestamp() if importer.date else None,
                    }
                )
            if len(res.importers) < 100:
                break
            last = res.importers[-1]
            offset_date = last.date
            offset_user = await client.get_input_entity(last.user_id)
            await asyncio.sleep(API_DELAY)
    return out


async def approve_join_request(
    client: TelegramClient, peer, user_id: int, approved: bool = True
) -> None:
    await client(
        functions.messages.HideChatJoinRequestRequest(
            peer=peer,
            user_id=user_id,
            approved=approved,
        )
    )


# --------------------------------------------------------------------------
# Mitglieder hinzufuegen
# --------------------------------------------------------------------------

ADDED = "added"
ALREADY = "already"
PRIVACY = "privacy"
FAILED = "failed"


async def add_user_to_group(client: TelegramClient, peer, target_user) -> tuple[str, str]:
    """Fuegt einen Nutzer der Gruppe hinzu.

    Liefert (ergebnis, meldung). Fehler, die nur diesen einen Nutzer
    betreffen, werden hier zu einem Ergebnis - alles, was den Account als
    Ganzes betrifft (PeerFlood, FloodWait), fliegt nach oben durch.
    """
    try:
        input_user = await client.get_input_entity(target_user)
    except (ValueError, TypeError) as exc:
        return FAILED, f"nicht aufloesbar: {exc}"

    try:
        if isinstance(peer, types.Chat) or isinstance(peer, types.InputPeerChat):
            chat_id = getattr(peer, "chat_id", None) or peer.id
            await client(
                functions.messages.AddChatUserRequest(
                    chat_id=chat_id, user_id=input_user, fwd_limit=0
                )
            )
        else:
            result = await client(
                functions.channels.InviteToChannelRequest(
                    channel=peer, users=[input_user]
                )
            )
            # Neuere Layer melden hier still, wen sie nicht aufnehmen konnten.
            missing = getattr(result, "missing_invitees", None)
            if missing:
                return PRIVACY, "von Telegram abgelehnt (Privatsphaere-Einstellung)"
    except errors.UserAlreadyParticipantError:
        return ALREADY, "war schon in der Gruppe"
    except errors.UserPrivacyRestrictedError:
        return PRIVACY, "Privatsphaere-Einstellung verbietet das Hinzufuegen"
    except errors.UserNotMutualContactError:
        return PRIVACY, "muss den hinzufuegenden Account als Kontakt haben"
    except errors.UserChannelsTooMuchError:
        return FAILED, "ist in zu vielen Gruppen"
    except errors.UserBannedInChannelError:
        return FAILED, "ist in dieser Gruppe gesperrt"
    except errors.InputUserDeactivatedError:
        return FAILED, "Account ist geloescht"
    except errors.UserKickedError:
        return FAILED, "wurde aus der Gruppe entfernt"
    except errors.UsersTooMuchError:
        return FAILED, "Gruppe hat ihr Mitgliederlimit erreicht"
    except errors.ChatAdminRequiredError:
        raise TelegramError(
            "Der Account braucht Admin-Rechte mit 'Nutzer einladen' in dieser Gruppe."
        )
    return ADDED, "hinzugefuegt"


async def resolve_peer(client: TelegramClient, target: str | int):
    """Oeffentlicher Zugang zur Ziel-Aufloesung."""
    return await _resolve_target(client, target)
