# Bugfix-Plan: Absturz bei fehlendem Spiel-/Downloads-Pfad

**Status:** Geplant (verifiziert am 2026-06-29)
**Auslöser:** CachyOS-Neuinstallation — 6 von 7 Spielen nicht mehr installiert,
Instanz-Pfade zeigen auf das nicht mehr existierende Laufwerk `/mnt/gamingS`.

## Problem (real reproduziert)

Beim Wechsel auf eine Instanz, deren Spiel-/Downloads-Pfad auf einem fehlenden
Laufwerk liegt, **stürzt Anvil komplett ab**. Da `.current` schon vor dem Laden
geschrieben wird, **startet die App danach gar nicht mehr** (lädt beim Start die
kaputte Instanz → erneuter Absturz).

## Bug A — Crash bei fehlendem/unzugänglichem Pfad

### Ursache (verifiziert)
- `mainwindow.py:1203` `self._game_panel.download_manager().set_downloads_dir(downloads_dir)`
- → `download_manager.py:156` `path.mkdir(parents=True, exist_ok=True)` **ohne** try/except.
- Liegt `downloads_dir` auf einem fehlenden Laufwerk (z. B. `/mnt/gamingS/Mods-test/Skyrim SE`),
  läuft `mkdir` bis `/mnt` hoch (gehört root) → `PermissionError` → **ungefangen** →
  propagiert durch `_apply_instance` → `switch_instance` → App-Crash.
- Der Downloads-Pfad ist hier ein **absoluter** Pfad (nicht `%INSTANCE_DIR%`), liegt also
  außerhalb des sicheren Instanz-Ordners.

### Fix-Ansatz (3 Ebenen)
1. **`download_manager.set_downloads_dir` (download_manager.py:153):** `mkdir` in
   `try/except OSError`. Bei Fehler: `_downloads_dir` trotzdem merken, **nicht** crashen,
   Warnung loggen. Downloads funktionieren erst wieder, wenn der Pfad gültig ist.
2. **`_apply_instance` (mainwindow.py:1119):** Vor dem Deploy prüfen, ob `game_path`
   existiert. Fehlt er → Warn-Toast (`tr("toast.game_path_missing", …)`), **Deploy
   überspringen**, aber Instanz **trotzdem laden** (Mod-Liste kommt aus dem Instanz-Ordner
   auf `/home` → gültig). So bleibt die Instanz offen und der User kann in den
   **Einstellungen** den Pfad ändern (`settings_dialog.py:394/1120` — bereits vorhanden).
3. **Startup-Schutz (mainwindow.py:1003-1005):** `switch_instance(current)` in
   `try/except` kapseln. Schlägt der Start-Load fehl → Warnung + leerer „Kein Spiel"-Zustand
   (Muster existiert bereits in `_apply_instance` bei `if not data:` Zeile 1130-1145),
   damit die App **immer** hochkommt.

## Bug B — `.current` wird vor erfolgreichem Laden geschrieben

### Ursache (verifiziert)
- `mainwindow.py:1115-1117`:
  ```
  self._teardown_current_instance()
  self.instance_manager.set_current_instance(instance_name)   # 1116 — VOR dem Laden
  self._apply_instance(instance_name)                         # 1117 — kann crashen
  ```
- Crasht `_apply_instance`, bleibt `.current` auf der kaputten Instanz stehen → nächster
  Start lädt sie wieder → Dauer-Crash / App gesperrt.

### Fix-Ansatz
- **Reihenfolge umdrehen:** erst `_apply_instance`, **dann** `set_current_instance` (nur bei
  Erfolg). Verifiziert sicher: `_apply_instance` ruft selbst **kein** `current_instance()` auf
  (nutzt `self._current_*`-Member). Grep: kein `current_instance()` innerhalb 1119–1300.

## Betroffene Dateien
| Datei | Änderung |
|---|---|
| `anvil/core/download_manager.py` | `set_downloads_dir`: `mkdir` in try/except |
| `anvil/mainwindow.py` | `switch_instance`: Reihenfolge (1115-1117); Startup-Guard (1003-1005); `game_path`-Check + Warn-Toast in `_apply_instance` |
| `anvil/locales/{de,en,es,fr,it,pt,ru}.json` | neue tr-Keys für Warnungen (7 Locales) |

## Impact / zu prüfen
- Reihenfolge-Umstellung: kein Code im Lade-/Deploy-Pfad liest `current_instance()` (geprüft).
- Andere Reload-Pfade (`mainwindow.py:776-777`, `:3675`, `:3714`) konsistent mit absichern.
- Nach `_teardown_current_instance()` + Fehler: sauberer „Kein Spiel"-Zustand (Muster 1130-1145).
- tr()-Keys in **allen 7** Locales (de, en, es, fr, it, pt, ru).

## Akzeptanzkriterien
- [ ] Wechsel auf Instanz mit fehlendem Laufwerk → **Warnung statt Crash**, App bedienbar.
- [ ] App **startet** auch wenn `.current` auf eine kaputte Instanz zeigt (Warnung, kein Crash).
- [ ] Spielpfad in den Einstellungen änderbar → danach lädt die Instanz normal.
- [ ] `.current` wird **erst nach** erfolgreichem Laden geschrieben.
- [ ] `./restart.sh` startet fehlerfrei.
- [ ] Neue tr-Keys in allen 7 Locales, kein Roh-Key sichtbar.
- [ ] Kein `setStyleSheet()` in neuen Widgets; keine hardcoded Pfade.

## Nicht im Scope
- Basisverzeichnis änderbar machen → eigener Plan `anvil-feature-base-directory.md`.
- 6 tote Instanzen: **behalten** (Mod-Daten/Profile bleiben für späteren Reinstall).
