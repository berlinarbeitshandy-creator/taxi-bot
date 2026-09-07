"""Geraeteprofile fuer die Telethon-Verbindung.

Telethon meldet dem Server Geraet, System- und App-Version. Wer denselben
Account spaeter im echten Client weiterbenutzt, sollte hier das Profil
waehlen, das zum tatsaechlichen Geraet passt - sonst sieht die Sitzungs-
liste im Telegram-Client unstimmig aus.
"""
from __future__ import annotations

DEVICE_PROFILES: list[dict[str, str]] = [
    {
        "id": "desktop_windows",
        "name": "Telegram Desktop (Windows 11)",
        "platform": "Desktop",
        "device_model": "Desktop",
        "system_version": "Windows 11",
        "app_version": "5.10.0 x64",
    },
    {
        "id": "desktop_macos",
        "name": "Telegram Desktop (macOS 15)",
        "platform": "Desktop",
        "device_model": "MacBook Pro",
        "system_version": "macOS 15.3",
        "app_version": "5.10.0",
    },
    {
        "id": "desktop_linux",
        "name": "Telegram Desktop (Linux)",
        "platform": "Desktop",
        "device_model": "PC 64bit",
        "system_version": "Linux 6.8",
        "app_version": "5.10.0",
    },
    {
        "id": "iphone_15",
        "name": "iPhone 15 Pro (iOS 18)",
        "platform": "iOS",
        "device_model": "iPhone 15 Pro",
        "system_version": "18.3",
        "app_version": "11.5",
    },
    {
        "id": "iphone_13",
        "name": "iPhone 13 (iOS 17)",
        "platform": "iOS",
        "device_model": "iPhone 13",
        "system_version": "17.6.1",
        "app_version": "11.2",
    },
    {
        "id": "ipad",
        "name": "iPad Air (iPadOS 18)",
        "platform": "iOS",
        "device_model": "iPad Air",
        "system_version": "18.2",
        "app_version": "11.5",
    },
    {
        "id": "android_pixel",
        "name": "Google Pixel 8 (Android 15)",
        "platform": "Android",
        "device_model": "Pixel 8",
        "system_version": "SDK 35",
        "app_version": "11.6.2",
    },
    {
        "id": "android_samsung",
        "name": "Samsung Galaxy S24 (Android 14)",
        "platform": "Android",
        "device_model": "SM-S921B",
        "system_version": "SDK 34",
        "app_version": "11.6.2",
    },
    {
        "id": "android_xiaomi",
        "name": "Xiaomi Redmi Note 13 (Android 14)",
        "platform": "Android",
        "device_model": "23129RAA4G",
        "system_version": "SDK 34",
        "app_version": "11.4.1",
    },
    {
        "id": "web",
        "name": "Telegram Web (Chrome)",
        "platform": "Web",
        "device_model": "Chrome 133",
        "system_version": "Windows",
        "app_version": "2.4.0 Z",
    },
]

DEFAULT_DEVICE = DEVICE_PROFILES[0]["id"]

_BY_ID = {profile["id"]: profile for profile in DEVICE_PROFILES}


def get_device(device_id: str | None) -> dict[str, str]:
    return _BY_ID.get(device_id or "", _BY_ID[DEFAULT_DEVICE])
