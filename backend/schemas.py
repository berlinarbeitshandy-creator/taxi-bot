"""Pydantic-Modelle fuer die API."""
from __future__ import annotations

from pydantic import BaseModel, Field


class ProxyIn(BaseModel):
    type: str = "socks5"
    host: str = ""
    port: int | None = None
    username: str = ""
    password: str = ""
    secret: str = ""


class LoginStart(BaseModel):
    label: str = ""
    phone: str
    api_id: int
    api_hash: str
    device_id: str = "desktop_windows"
    proxy: ProxyIn | None = None


class LoginCode(BaseModel):
    login_id: str
    code: str


class LoginPassword(BaseModel):
    login_id: str
    password: str


class PoolAdd(BaseModel):
    usernames: str = Field(description="Freitext, ein Name pro Zeile oder komma-getrennt")
    note: str = ""


class PoolPatch(BaseModel):
    note: str | None = None
    status: str | None = None


class InviteIn(BaseModel):
    account_id: int
    target: str
    title: str = ""
    request_needed: bool = True
    usage_limit: int | None = None


class ApproveIn(BaseModel):
    account_id: int
    target: str
    pool_only: bool = True
    watch_minutes: int = 0


class PoolCheckIn(BaseModel):
    account_id: int
    only_new: bool = True


class AddIn(BaseModel):
    account_id: int
    target: str
    delay: float = Field(default=45, ge=3, le=600)
    limit: int = Field(default=0, ge=0)
    only_valid: bool = True
