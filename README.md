# Telegram Panel

Web-Panel auf Basis von **Python + Telethon**, um Telegram-Accounts zu binden,
einen `@username`-Pool zu pflegen und Pool-Mitglieder über bestätigte
Einladungen in eine Zielgruppe zu holen.

![Stack](https://img.shields.io/badge/Python-3.11%2B-3b9dff) ![Stack](https://img.shields.io/badge/Telethon-1.38-6d5cff)

---

## Funktionen

**Account binden**
- Telefonnummer, API-ID, API-Hash
- Login mit Code und, falls gesetzt, Zwei-Faktor-Passwort
- Proxy optional: SOCKS5, SOCKS4, HTTP oder MTProto
- Geräteprofil wählbar (Desktop, iOS, Android, Web) — bestimmt, wie die
  Sitzung in der Telegram-Geräteliste erscheint
- Premium-Erkennung, Statusprüfung, Abmelden

**@username Pool**
- Namen als Liste, Komma-Text oder `t.me/`-Links einfügen — die Erkennung
  läuft automatisch, Duplikate werden übersprungen
- Prüf-Job löst jeden Namen über einen gebundenen Account auf und markiert
  tote Namen als ungültig
- Filtern, suchen, als CSV exportieren

**Vorgang**
- Einladungslink für die Zielgruppe erzeugen — mit Beitrittsanfrage
- Auto-Approve-Job: offene Beitrittsanfragen werden gegen den Pool geprüft
  und genehmigt; wahlweise einmalig oder über einen Zeitraum beobachtend
- Protokoll mit Fortschritt, Zählern und Live-Log

---

## Wie Beitritte ablaufen

Das Panel fügt **niemanden ungefragt** in eine Gruppe ein. Der Weg ist:

1. Einladungslink mit aktivierter Beitrittsanfrage erzeugen.
2. Link an die Leute aus deinem Pool verteilen.
3. Wer beitreten will, stellt eine Anfrage.
4. Der Vorgang genehmigt automatisch alle Anfragen, deren Absender im Pool steht.

Das hat zwei Gründe. Zum einen ist das Massen-Hinzufügen fremder Nutzer in
Telegrams Nutzungsbedingungen untersagt und führt zuverlässig zu Sperren —
auch bei Premium-Accounts. Zum anderen entscheiden die Leute selbst, ob sie
in der Gruppe landen wollen.

---

## Installation

```bash
git clone <repo>
cd taxi-bot

python3 -m venv .venv
source .venv/bin/activate        # Windows: .venv\Scripts\activate
pip install -r requirements.txt

cp .env.example .env
python run.py
```

Panel öffnen: <http://127.0.0.1:8000>

### API-Zugang besorgen

API-ID und API-Hash gibt es unter <https://my.telegram.org> →
*API development tools*. Beide gehören zu deinem Telegram-Konto, nicht zum
Panel — jeder Account kann dieselben Werte verwenden.

---

## Konfiguration

Alles über `.env` (siehe `.env.example`):

| Variable | Bedeutung | Standard |
| --- | --- | --- |
| `PANEL_SECRET_KEY` | Schlüssel für die Session-Verschlüsselung. Leer → wird einmalig unter `data/.secret` erzeugt. | – |
| `PANEL_USER` / `PANEL_PASSWORD` | Basic-Auth für das Panel. Passwort leer → kein Login. | `admin` / – |
| `PANEL_HOST` / `PANEL_PORT` | Bind-Adresse | `127.0.0.1:8000` |
| `PANEL_API_DELAY` | Pause zwischen einzelnen Telegram-Aufrufen in Sekunden | `1.5` |
| `PANEL_CONNECT_TIMEOUT` | Abbruch, wenn Telegram nicht erreichbar ist | `25` |

> **Wichtig:** Änderst du `PANEL_SECRET_KEY` nachträglich, lassen sich
> bestehende Sessions nicht mehr entschlüsseln und die Accounts müssen neu
> gebunden werden.

---

## Sicherheit

- Telethon-Sessions und API-Hashes liegen **Fernet-verschlüsselt** in der
  SQLite-Datenbank, nie im Klartext.
- Eine Session ist Vollzugriff auf den Account. `data/` gehört nicht ins
  Repository und ist in `.gitignore` ausgeschlossen.
- Standard-Bind ist `127.0.0.1`. Wer das Panel nach außen öffnet, sollte
  `PANEL_PASSWORD` setzen und einen HTTPS-Reverse-Proxy davorstellen.
- Beim Lösen eines Accounts meldet das Panel die Session bei Telegram ab.

---

## Projektstruktur

```
backend/
  config.py             Pfade und Einstellungen
  crypto.py             Fernet-Verschlüsselung für Sessions
  db.py                 SQLite-Zugriff und Schema
  devices.py            Geräteprofile
  telegram_manager.py   Telethon: Login, Client-Pool, Gruppen, Anfragen
  jobs.py               Hintergrund-Jobs (Pool-Prüfung, Auto-Approve)
  schemas.py            Pydantic-Modelle
  api.py                HTTP-Endpunkte
  main.py               FastAPI-App, Basic-Auth, statisches Frontend
frontend/
  index.html            Panel-Oberfläche
  css/app.css           Design-System
  js/app.js             Views, Login-Flow, Jobs
run.py                  Startskript (liest .env)
```

---

## Grenzen

- Telegram begrenzt, wie viele Anfragen ein Account in kurzer Zeit stellen
  darf. Bei `FloodWaitError` wartet das Panel die geforderte Zeit ab und
  macht weiter — bei großen Pools dauert eine Prüfung entsprechend.
- Zum Erzeugen von Einladungslinks und Genehmigen von Anfragen braucht der
  Account Admin-Rechte mit „Nutzer einladen“ in der Zielgruppe.
- Die Job-Ausführung läuft im Prozess des Panels. Wird das Panel beendet,
  werden laufende Jobs als *unterbrochen* markiert und müssen neu gestartet
  werden.
