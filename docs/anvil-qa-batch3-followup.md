# QA Report — BUG 6 Follow-Up: NXM-Download "URL can't contain control characters"

Datum: 2026-03-04

## Fehlermeldung

```
URL can't contain control characters. '/cdn/1151/4042/Legendary ...
```

## Root Cause

**Die ursprüngliche Vermutung (Control Characters durch IPC/QLocalSocket) ist FALSCH.**

Die **Nexus Mods API** liefert im JSON-Feld `URI` CDN-Download-URLs mit **unescapten Leerzeichen** im Dateinamen zurück, z.B.:

```
https://cf-files.nexusmods.com/cdn/1151/4042/Legendary Endings-1151-3-0-1718390474.zip
```

Seit Python 3.7.2 lehnt `http.client` (intern von `urllib.request` verwendet) URLs mit Leerzeichen ab und meldet dies als "URL can't contain control characters". Das ist ein bekanntes Python-Verhalten — Leerzeichen werden als ungültige Zeichen klassifiziert.

## Datenfluss des Bugs

```
Nexus API Response
    │ URI: "https://...cdn/1151/4042/Legendary Endings-1151-3-0.zip"
    │                                ↑ LEERZEICHEN ↑
    ▼
mainwindow.py:3131     url = data[0].get("URI", "")
    │                  ← keine Bereinigung
    ▼
mainwindow.py:3146-47  dm.enqueue(url=url, ...)
    │                  ← keine Bereinigung
    ▼
download_manager.py:43 req = urllib.request.Request(self._url, ...)
download_manager.py:47 urllib.request.urlopen(req, timeout=60)
    │                  ← CRASH: InvalidURL("URL can't contain control characters")
    ▼
                       ❌ Download schlägt fehl
```

## Findings

### [CRITICAL] CDN-URL mit Leerzeichen wird unbereinigt an urllib übergeben

- **Datei:** `anvil/core/download_manager.py:43-47`
- **Problem:** `self._url` wird direkt an `urllib.request.Request()` übergeben. Nexus CDN-URLs können Leerzeichen im Dateinamen enthalten (z.B. "Legendary Endings-..."). Python's `http.client` lehnt diese ab.
- **Fix:** URL-Path vor dem Request URL-encoden:

```python
# download_manager.py — _DownloadWorker.run()
from urllib.parse import urlparse, quote, urlunparse

parsed = urlparse(self._url)
safe_path = quote(parsed.path, safe="/:@!$&'()*+,;=-._~")
clean_url = urlunparse(parsed._replace(path=safe_path))
req = urllib.request.Request(clean_url, headers={...})
```

### [HIGH] Keine Bereinigung im IPC-Flow (Defense-in-Depth)

Obwohl nicht die Hauptursache, fehlt an mehreren Stellen `.strip()`:

- **Datei:** `anvil/core/single_instance.py:60` — `send_message()`: kein `.strip()` vor Senden
- **Datei:** `anvil/core/single_instance.py:75` — `_on_new_connection()`: `data.decode()` ohne `.strip()`, `QByteArray.data()` kann trailing Null-Bytes enthalten
- **Datei:** `anvil/core/nxm_handler.py:33` — `parse_nxm_url()`: kein `.strip()` auf Input-URL

**Fix (3 Einzeiler):**
```python
# single_instance.py:60 — send_message()
socket.write(message.strip().encode("utf-8"))

# single_instance.py:75 — _on_new_connection()
message = data.decode("utf-8", errors="replace").strip("\x00").strip()

# nxm_handler.py:41 — parse_nxm_url()
url = url.strip()  # als erste Zeile in der Funktion
```

## Zusammenfassung

| # | Severity | Ort | Problem | Fix |
|---|----------|-----|---------|-----|
| 1 | CRITICAL | download_manager.py:43-47 | CDN-URL mit Leerzeichen → urllib crash | URL-Path quoten |
| 2 | HIGH | single_instance.py:60,75 | Kein .strip() bei IPC send/receive | .strip() hinzufügen |
| 3 | HIGH | nxm_handler.py:33 | Kein .strip() auf URL-Input | .strip() hinzufügen |

## Empfohlene Reihenfolge

1. **download_manager.py** — URL-Encoding im `_DownloadWorker.run()` (behebt den Bug)
2. **single_instance.py** — `.strip()` in send + receive (Defense-in-Depth)
3. **nxm_handler.py** — `.strip()` in `parse_nxm_url()` (Defense-in-Depth)

## Ergebnis

**NEEDS FIXES** — 1 CRITICAL, 2 HIGH

## Sub-Agent Reports

- [Agent 1 — single_instance.py](workflow/qa-nxm-agent1.md)
- [Agent 2 — nxm_handler.py](workflow/qa-nxm-agent2.md)
- [Agent 3 — IPC-Flow E2E](workflow/qa-nxm-agent3.md)
- [Agent 4 — handle_nxm_url](workflow/qa-nxm-agent4.md)
