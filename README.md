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
  nicht existierende Namen als **tot**
- Filtern, suchen, als CSV exportieren

**Vorgang — Mitglieder aufnehmen**
- Nimmt die Pool-Einträge nacheinander in die Zielgruppe auf
- Pause und Höchstzahl pro Durchlauf einstellbar, mit Dauer-Schätzung
- Wer sich nicht aufnehmen lässt — Privatsphäre-Blockade, gelöschter Account,
  zu viele Gruppen — wird **tot** markiert und fällt aus allen weiteren
  Durchläufen raus. Der Grund steht daneben im Pool.
- Pausiert bei PeerFlood, statt den Account weiter zu verbrennen — und
  wartet auf dein **Go**, bevor es weitergeht

**Mehrere Accounts**
- Im Vorgang mehrere Accounts ankreuzen — jeder bekommt einen eigenen Job
- Der Pool wird fest aufgeteilt: jeder Account bekommt seinen eigenen Block
  zugewiesen, zwei greifen nie nach demselben Namen
- **Nacheinander** (Vorgabe) oder **gleichzeitig** — siehe unten
- Die Aufteilung und die Dauer stehen in der Vorschau, bevor du startest

### Nacheinander oder gleichzeitig?

**Nacheinander** ist die Vorgabe, und in den meisten Fällen die bessere Wahl:

- Telegram korreliert über die IP. Zwei Accounts, die aus derselben Leitung
  gleichzeitig dieselbe Gruppe befüllen, sind ein auffälliges Muster — es sei
  denn, jeder Account hat seinen eigenen Proxy.
- Auch die Gruppe selbst hat ein Tempo-Limit, nicht nur die Accounts.
  Gleichzeitig verdoppelt die Beitritte pro Minute in dieselbe Gruppe.
- Der erste Account ist der Kanarienvogel: hält er wegen PeerFlood an, wird
  die Kette gestoppt und die übrigen Accounts bleiben außen vor, statt in
  dieselbe Sperre zu laufen.

**Gleichzeitig** ist doppelt so schnell und vertretbar, wenn jeder Account
über einen eigenen Proxy läuft. Der Preis: eine Sperre erwischt beide, bevor
du davon erfährst.

**Kontingent je Account — mit Aufwärmen**
- Jeder Account hat seinen eigenen Regler (5–100). 40 ist die Faustregel für
  einen eingelaufenen Account, nicht mehr ein fester Wert
- **Frisch gebundene Accounts starten bei 10.** Ein neuer Account fällt
  Telegram schneller auf als einer, der seit Wochen unauffällig läuft
- Das Panel zählt mit, wie viel ein Account insgesamt geschafft hat, und
  empfiehlt daraufhin den nächsten Schritt — mit einem Knopf zum Übernehmen:

  | bisher aufgenommen | Empfehlung |
  | --- | --- |
  | unter 30 | 10 — erst warmlaufen lassen |
  | ab 30 | 20 — läuft an |
  | ab 100 | 30 — gut eingelaufen |
  | ab 250 | 40 — die Faustregel passt |

- Wer den Regler während einer Pause hochzieht, hat sofort wieder Luft
- Jeder Account darf so viele Aufnahme-Versuche machen, wie sein Regler sagt,
  dann pausiert er
- Die Pause endet nach 10 Stunden von selbst — oder sofort, wenn du den
  Account unter *Accounts* freigibst
- Der Stand steht am Account, bei laufender Pause mit Countdown
- Ein Durchlauf plant nie mehr ein, als der Account noch darf, und ein Job
  startet gar nicht erst, solange der Account pausiert

**Vorgang — Einladungslink (Alternative)**
- Einladungslink für die Zielgruppe erzeugen — mit Beitrittsanfrage
- Auto-Approve-Job: offene Beitrittsanfragen werden gegen den Pool geprüft
  und genehmigt; wahlweise einmalig oder über einen Zeitraum beobachtend

**Protokoll**
- Fortschritt, Zähler und Live-Log für jeden Job

---

## Pool-Status

| Status | Bedeutung |
| --- | --- |
| ungeprüft | Neu eingefügt, noch nicht gegen Telegram geprüft |
| gültig | Aufgelöst, bereit für die Aufnahme |
| aufgenommen | In der Zielgruppe — oder war schon drin |
| beigetreten | Über eine genehmigte Beitrittsanfrage reingekommen |
| **tot** | Aufnahme unmöglich. Grund steht daneben: *existiert nicht*, *Privatsphäre-Einstellung*, *kein gegenseitiger Kontakt*, *in zu vielen Gruppen*, *Account gelöscht*, *Gruppe voll* |

Der Pool ist dauerhaft — er liegt in der SQLite-Datei unter `data/`. Du
kannst jederzeit neue Namen nachlegen, auch Wochen später: Panel starten,
Namen einfügen, prüfen, weitermachen. Schon aufgenommene Einträge werden
bei jedem weiteren Durchlauf übersprungen.

Läuft gerade ein Vorgang, sind die Einträge dieses Durchlaufs dem jeweiligen
Account **zugewiesen** und für andere Accounts gesperrt. Die Zuweisung wird
freigegeben, sobald der Job endet — auch wenn er abbricht.

Tote Einträge werden bei den nächsten Durchläufen übersprungen — sie kosten
sonst nur Aufnahme-Versuche, die ohnehin gegen das Tageslimit zählen. Über
den Filter *Tot* siehst du sie gesammelt, **Tote löschen** wirft sie aus dem
Pool.

Bei *Privatsphäre-Einstellung* lohnt ein zweiter Blick: das ist am Account
änderbar. Danach den Eintrag neu einfügen oder den Pool ohne den Haken
„nur ungeprüfte" erneut prüfen.

---

## Die zwei Wege in die Gruppe

**Direkt aufnehmen** ist der kurze Weg und funktioniert für Accounts, die du
selbst kontrollierst. Grenzen setzt Telegram, nicht das Panel:

- Das Aufnehmen ist deutlich strenger begrenzt als Lesezugriffe. Bewährt sind
  45 Sekunden oder mehr Pause. Ist das Kontingent des Accounts erreicht,
  pausiert er 10 Stunden — das Kontingent stellst du je Account am Regler ein,
  frisch gebundene starten bei 10.
- Gezählt wird **jeder** Versuch, der Telegram erreicht hat, auch ein
  abgelehnter: Telegram zählt Anfragen, nicht Erfolge, und gerade die
  abgelehnten lösen die Sperre aus.
- Bei `FloodWaitError` wartet das Panel die geforderte Zeit ab und macht weiter.
- Bei `PeerFloodError` hat Telegram den Account als auffällig eingestuft. Der
  Vorgang **pausiert** dann sofort — weiterzumachen kostet den Account, nicht
  nur den Job. Er bleibt stehen, bis du im Protokoll **Go** drückst, und macht
  dann genau bei dem Eintrag weiter, an dem er aufgehört hat. Die restlichen
  Einträge bleiben so lange für diesen Account reserviert, auch über einen
  Neustart des Panels hinweg. Vor dem Go ein paar Stunden warten — sonst steht
  die Sperre sofort wieder da.
- Steht die Privatsphäre-Einstellung „Wer kann mich zu Gruppen hinzufügen“ auf
  *Meine Kontakte*, scheitert die Aufnahme. Abhilfe: die Einstellung im
  betroffenen Account ändern oder die Accounts gegenseitig als Kontakt
  hinterlegen.

**Über den Einladungslink** geht immer, auch an Privatsphäre-Einstellungen
vorbei, und zählt nicht gegen die Aufnahme-Limits: Link mit Beitrittsanfrage
erzeugen, verteilen, und das Panel genehmigt eingehende Anfragen automatisch —
wahlweise nur die, deren Absender im Pool steht.

---

## Installation

**Der einfache Weg** — Python 3.11+ muss installiert sein
(<https://www.python.org/downloads/>, unter Windows beim Installieren
„Add Python to PATH" ankreuzen):

| System | Datei |
| --- | --- |
| Windows | Doppelklick auf `start.bat` |
| macOS / Linux | `./start.sh` im Terminal |

Beim ersten Start richtet das Skript alles ein — das dauert ein bis zwei
Minuten. Danach geht es sofort los, und der Browser öffnet sich von selbst
auf <http://127.0.0.1:8000>.

**Von Hand**, wenn du lieber selbst tippst:

```bash
python3 -m venv .venv
source .venv/bin/activate        # Windows: .venv\Scripts\activate
pip install -r requirements.txt
cp .env.example .env             # Windows: copy .env.example .env
python run.py
```

Das Fenster muss offen bleiben, solange das Panel läuft — dort steckt der
Server. Beenden mit `Strg+C`.

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
| `PANEL_ADD_DELAY` | Vorgabe für die Pause zwischen zwei Aufnahmen | `45` |
| `PANEL_ADD_QUOTA` | Faustregel für einen eingelaufenen Account | `40` |
| `PANEL_WARMUP_QUOTA` | Womit ein frisch gebundener Account startet | `10` |
| `PANEL_QUOTA_MIN` / `PANEL_QUOTA_MAX` | Grenzen des Reglers | `5` / `100` |
| `PANEL_COOLDOWN_HOURS` | Dauer der Pause, wenn nicht von Hand freigegeben | `10` |
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
  telegram_manager.py   Telethon: Login, Client-Pool, Gruppen, Aufnahme
  jobs.py               Hintergrund-Jobs (Prüfung, Aufnahme, Auto-Approve)
  quota.py              Aufnahme-Kontingent, Pause und Freigabe je Account
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
- Ein Durchlauf mit 25 Einträgen und 45 Sekunden Pause läuft rund 18 Minuten.
  Das Panel muss dabei laufen.
- Zum Aufnehmen, Erzeugen von Einladungslinks und Genehmigen von Anfragen
  braucht der Account Admin-Rechte mit „Nutzer einladen“ in der Zielgruppe.
- Die Job-Ausführung läuft im Prozess des Panels. Wird das Panel beendet,
  werden laufende Jobs als *unterbrochen* markiert und müssen neu gestartet
  werden.
