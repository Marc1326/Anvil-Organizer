# QA Report: BA2-Packer Wine-Umstellung

**Datum:** 2026-02-28
**Geprüfte Dateien:** `anvil/core/ba2_packer.py`, `anvil/widgets/game_panel.py`
**Methode:** 4 parallele QA-Agents

---

## Gesamtergebnis: READY FOR COMMIT

Keine CRITICAL oder HIGH Bugs. Alle 4 Agents bestätigen die korrekte Implementierung.

---

## Agent 1: Code-Review (Compile, Imports, Typos)

| Prüfpunkt | Ergebnis |
|-----------|----------|
| Alle Imports vorhanden | OK |
| Syntax-Fehler | Keine (`py_compile` OK) |
| Signaturen konsistent (`wine_bin: str`) | OK — `_run_bsarch()`, `pack_mod()`, `pack_all_mods()` |
| Verwaiste Proton-Referenzen | Keine (2 korrekte: Docstring Zeile 4, `protonPrefix()` Zeile 162) |
| `_to_wine_path()` Implementierung | OK |
| `_get_wine_env()` Return-Typ | OK (`tuple[str, dict] | None`) |
| Docstrings aktualisiert | OK (alle 9 Stellen) |

---

## Agent 2: Logik-Review (Pfadkonvertierung)

| Prüfpunkt | Ergebnis |
|-----------|----------|
| Alle 3 Pfade konvertiert (bsarch, source_dir, output_ba2) | OK |
| Leerzeichen in Pfaden ("Fallout 4") | OK — `subprocess.run()` mit Liste |
| Umlaute | OK — `text=True` = UTF-8 |
| `/mnt/` Mount-Points | OK — `Z:` mappt Linux-Root `/` |
| `env` mit WINEPREFIX durchgereicht | OK — gesamte Aufrufkette |
| `protonPrefix()` None-Behandlung | OK — sauber abgefangen |
| WINEPREFIX-Pfad endet auf `/pfx` | OK — korrekt für Wine |

**[MEDIUM]** Fehlermeldung unterscheidet nicht Wine-fehlt vs. Prefix-fehlt (Zeile 401)
**[LOW]** Kein Fallback für GOG-Spiele (BA2-Packing nur mit Steam)

---

## Agent 3: Integration-Review (Aufrufer)

| Datei | Änderung nötig? | Status |
|-------|----------------|--------|
| `game_panel.py` | Log-Meldung "Proton" → "Wine" | Erledigt (Zeile 584) |
| `mod_deployer.py` | Nein (nur Kommentar) | OK |
| Öffentliche API | Unverändert | OK |

`pack_mod()` Signatur geändert, aber **kein externer Aufrufer** — nur intern von `pack_all_mods()`.

---

## Agent 4: Regressions-Check

| Prüfpunkt | Ergebnis |
|-----------|----------|
| Nur Fallout 4 hat `NeedsBa2Packing = True` | OK |
| Nicht-Bethesda-Spiele betroffen? | NEIN — dreifach abgesichert |
| `findProtonRun()` noch verwendet? | JA — `game_panel.py:817` für Game-Launch |
| `shutil.which("wine")` = None | Sauber → `is_available()` = False |
| `protonPrefix()` = None | Sauber → `is_available()` = False |
| Verbleibende "Proton"-Referenzen korrekt? | JA — alle beschreiben tatsächlichen Proton-Kontext |

---

## Alle Findings

| # | Severity | Beschreibung | Datei:Zeile |
|---|----------|-------------|-------------|
| 1 | MEDIUM | Fehlermeldung unterscheidet nicht Wine-fehlt vs. Prefix-fehlt | `ba2_packer.py:401` |
| 2 | LOW | Kein Fallback für GOG-Spiele | `base_game.py:229` |
| 3 | LOW | Z:-Drive-Existenz wird nicht verifiziert (nur Fallback-Pfad) | `ba2_packer.py:190` |
| 4 | LOW | Relative Pfade im Fallback (theoretisch, alle Pfade sind absolut) | `ba2_packer.py:190` |
| 5 | LOW | Docstring "Proton prefix" könnte verwirren | `ba2_packer.py:4` |

Keine Findings blockieren den Commit.

---

## Live-Test

App gestartet mit `_dev/restart.sh`. Ergebnis:
- Wine korrekt gefunden: `/usr/bin/wine`
- Pfade korrekt konvertiert: `Z:\home\mob\...`, `Z:\mnt\gamingS\...`
- **7 BA2-Archive erstellt** (6 Mods gepackt, 1 mit Textures)
- INI-Backup und Update funktioniert
- Keine Tracebacks, keine ImportError, keine NameError
