# Session-Zusammenfassung: BG3 Bugs & User-Problem

## 1. BG3 DnD Duplikations-Bug (GEFIXT, committed `1170cfb`)
- **Problem:** Mods wurden beim Drag-and-Drop kopiert statt verschoben. Ghost-Einträge (Data-Override-Dateinamen) landeten in `bg3_modstate.json`.
- **Fix:** `_on_mods_reordered()` filtert jetzt uuid_order gegen echte BG3-UUIDs. Manuelle Bereinigung von 7 Ghost-Einträgen in bg3_modstate.json.
- **Dateien:** `mainwindow.py` (Zeile 1234-1250)

## 2. BG3 Separatoren nicht sichtbar (GEFIXT, committed `54a989d`)
- **Problem:** Trenner wurden erstellt (Duplikat-Erkennung funktionierte), aber nicht in der Mod-Liste angezeigt. Ursache: Standard-Pfad erstellt Ordner in `.mods/` + Eintrag in `modlist.txt`, aber BG3 nutzt `bg3_separators.json`.
- **Fix:** BG3-Weiche in `_ctx_create_separator()` — Separator wird direkt ins Model eingefügt + in `bg3_separators.json` gespeichert.
- **Dateien:** `mainwindow.py` (Zeile 2477-2520)

## 3. BG3 Separator springt (OFFEN)
- **Problem:** Separator springt an falsche Position nach Verschieben + Schließen/Öffnen.
- **Schritte zum Reproduzieren (Video-Beweis vorhanden):**
  1. Separator "Aussehen" per DnD verschieben
  2. Separator schließen oder öffnen (Collapse/Expand)
  3. Separator springt an eine andere Position
- **Ursache:** Noch nicht abschließend identifiziert. Der Separator nutzt die Standard-Funktionalität (gleicher Code wie Cyberpunk). Bei Standard-Games (Cyberpunk) funktioniert es, weil Separatoren direkt in `modlist.txt` eingebettet sind und Reloads überleben. Bei BG3 werden Separatoren separat in `bg3_separators.json` gespeichert. `_bg3_reload_mod_list()` baut die gesamte Mod-Liste bei bestimmten Aktionen komplett neu auf und fügt Separatoren per Anchor-UUID wieder ein — dabei geht die Position verloren.
- **Betroffene Stellen:**
  - `mainwindow.py`: `_bg3_reload_mod_list()` (Zeile 4972) — kompletter Rebuild
  - `mainwindow.py`: `_on_mod_toggled()` (Zeile 1208) — ruft Rebuild bei Checkbox-Toggle auf
  - `mainwindow.py`: `_bg3_save_separators()` (Zeile 4923) — Anchor-basierte Speicherung
- **Video:** `~/Videos/Videos - Claude Code/Bildschirmaufnahme_20260331_172813.webm`

## 4. User kann AppImage nicht starten (BEANTWORTET)
- **User:** PikaOS (Ubuntu-basiert), KDE
- **Fehler:** `ImportError: /lib/x86_64-linux-gnu/libc.so.6: version GLIBC_2.43 not found`
- **Ursache:** AppImage wurde mit GLIBC 2.43 gebaut (GitHub Actions ubuntu-latest), PikaOS hat nur GLIBC 2.39.
- **Workaround:** Quellcode-Installation (git clone + venv + pip install + python main.py)
- **Antwort an User:** `docs/antwort-user-appimage.txt` (Deutsch, nur Quellcode-Option)
- **Langfristiger Fix nötig:** CI auf älterer Ubuntu-Version bauen (z.B. ubuntu-22.04) damit AppImage mit älteren GLIBC-Versionen kompatibel ist.

## 5. BG3 Charakter-Erstellung Augen laden nicht (OFFEN)
- **Problem:** Von Marc gemeldet, noch nicht untersucht.
- **Status:** Wartet auf Analyse.
