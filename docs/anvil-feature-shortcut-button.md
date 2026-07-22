# Feature-Spec: Shortcut-/Verknüpfungs-Button im Game-Panel (#24)
**Status:** Geplant — Eckpfeiler entschieden (2026-06-29)
**Datum:** 2026-06-28 (verifiziert gegen Code)

## 0. Entscheidungen (2026-06-29, mit Marc)
- **Verhalten global einstellbar** (NICHT pro Verknüpfung, NICHT pro Instanz): ein
  globaler Schalter in **Einstellungen → Allgemein → Sonstiges**, gespeichert in
  `QSettings` (z. B. `QSettings("AnvilOrganizer","Anvil")`, Key `shortcut/launch_game`).
- **Live-Ansatz:** Die `.desktop` ruft IMMER `--launch-instance "<Spiel>"`. Beim Start
  liest Anvil den Schalter und entscheidet zur Laufzeit:
  - „das Spiel" → deployen + Spiel starten (Phase 4),
  - „nur Anvil" → nur mit vorgewählter Instanz öffnen (Phase 3).
  → Ein Schalter steuert alle Verknüpfungen, jederzeit umstellbar, kein Neu-Erstellen.
- **Default: „das Spiel starten".**
- **Beide Verhalten werden gebaut** (Phase 3 + 4), der Schalter wählt zur Laufzeit.
- **Zielordner:** `~/.local/share/applications/` (App-Menü). Desktop optional später.
- **Profil:** aktives Profil (erste Stufe).
- **Neue Datei zusätzlich:** `anvil/widgets/settings_dialog.py` (Schalter ergänzen);
  neuer i18n-Key für die Beschriftung (siehe Abschnitt 7).

## 1. Problem / Ziel
Im Game-Panel (oben rechts über dem Game-Banner) existiert ein kleiner Verknüpfungs-Button
(`objectName "linkButton"`). Er ist optisch vorhanden, aber sein Klick ist auf den Platzhalter
`_todo("Verknüpfung")` verdrahtet — also funktionslos.

Issue #24 (Originaltext, OPEN, Labels: `disabled-feature`, `enhancement`):
> The shortcut button in the game panel is disabled.
> - Button creates desktop shortcut for the current game
> - Shortcut launches the game directly through Anvil (with mod deployment)
> - Optional: link shortcut to a specific profile
> Status: Button present in game panel but disabled — no functionality implemented.

Ziel:
- Klick erzeugt eine `.desktop`-Verknüpfung für das aktuell gewählte Spiel.
- Die Verknüpfung startet das Spiel über Anvil (inkl. Mod-Deployment).
- Optional: Verknüpfung an ein bestimmtes Profil binden (erste Stufe: aktives Profil).

## 2. WICHTIGE Erkenntnis — vorhandene Infrastruktur wiederverwenden
Es existiert bereits eine vollständige, XDG-konforme `.desktop`-Erzeugung im Code, die für die
nxm://-Protokoll-Registrierung benutzt wird. Diese ist die **Vorlage und Basis** — NICHT neu
erfinden:

| Vorhandenes Bauteil | Datei:Zeile | Was es liefert |
|---|---|---|
| `register_nxm_handler()` | `anvil/core/nxm_handler.py:111-153` | Schreibt eine `.desktop` nach `~/.local/share/applications/`, Felder `Type/Name/Exec/Icon/Terminal/Categories`, dann `xdg-mime` |
| `_build_exec_command()` | `anvil/core/nxm_handler.py:156-194` | Liefert den korrekten Anvil-Aufruf für `Exec=` — erkennt **Flatpak** (`flatpak run $FLATPAK_ID`), **AppImage** (`$APPIMAGE`), **PyInstaller** (`sys.frozen`) und **Dev** (`.venv/bin/python main.py`). Genau das verhindert hardcoded Pfade. |
| CLI-Arg-Parsing-Muster | `anvil/core/nxm_handler.py:98` (`get_nxm_arg(argv)`) | Bestehendes Muster, wie ein Argument aus `sys.argv` gelesen wird |
| Single-Instance-IPC | `anvil/core/single_instance.py:56` (`send_message`), `:20` (`message_received`) | Bestehendes Muster, wie ein Argument an eine laufende Instanz weitergereicht wird (siehe `anvil/main.py:79-93,108`) |

Konsequenz: Der neue `.desktop`-Generator soll `_build_exec_command()` aufrufen und sich an
`register_nxm_handler()` orientieren. Damit entfällt die im Erstentwurf vorgesehene eigene
Exec-Pfad-Erkennung komplett.

## 3. Ist-Zustand im Code (verifizierte Anker)
| Stelle | Datei:Zeile | Befund (verifiziert) |
|---|---|---|
| Button-Erstellung | `anvil/widgets/game_panel.py:126-138` | `link_btn = QPushButton()`, `setObjectName("linkButton")`, Icon `styles/icons/executables.svg`, `setIconSize(QSize(20,20))`, `setToolTip(tr("tooltip.link"))`, `setFixedWidth(32)`; eingehängt via `link_btn_row` → `top_layout` |
| Platzhalter-Connect | `anvil/widgets/game_panel.py:134` | `link_btn.clicked.connect(_todo("Verknüpfung"))` |
| Platzhalter-Funktion | `anvil/core/__init__.py:4-8` | `_todo(name)` gibt eine `_handler`-Closure zurück, die nur `print(f"TODO: {name}")` ausgibt |
| Import des Platzhalters | `anvil/widgets/game_panel.py:54` | `from anvil.core import _todo` |
| Start-Logik (Vorbild) | `anvil/widgets/game_panel.py:181` | `self._start_btn.clicked.connect(self._on_start_clicked)` |
| Start-Handler | `anvil/widgets/game_panel.py:1075-1108` | `_on_start_clicked()` — wählt Executable, prüft Steam/Proton, REDmod-Deploy-Zweig, ruft `_do_launch()` |
| Tatsächlicher Launch | `anvil/widgets/game_panel.py:1110-1142` | `_do_launch()` — Steam/Proton/Direkt-Start; emittiert `start_requested`/`game_started` |
| Aktive Instanz/Profil | `anvil/widgets/game_panel.py:359-360` | `self._instance_path: Path | None`, `self._current_profile_name = "Default"` |
| Panel-Update | `anvil/widgets/game_panel.py:416-437` | `update_game(game_name, game_path, game_plugin, icon_manager, game_short_name)` setzt `_current_game_path`, `_current_plugin`, `_icon_manager`, `_current_short_name` |
| Instanz-API | `anvil/core/instance_manager.py:270,287,326,348` | `load_instance(name)`, `save_instance(name,data)`, `current_instance()`, `set_current_instance(name)` |
| Einstiegspunkt | `anvil/main.py:54-121` (`main()`); Wrapper `main.py:1-6`, `anvil/__main__.py:1-6` | `app = QApplication(sys.argv)`; Single-Instance-Check vor `MainWindow()` |

Der Button ist angelegt, aber funktionslos. Eine **spiel-spezifische** `.desktop`-Erzeugung
existiert noch nicht; die **generische** `.desktop`-Mechanik (nxm) existiert bereits (Abschnitt 2).

### Falsche Annahmen des Erstentwurfs (korrigiert)
- Erstentwurf nannte `game_panel.py:126-137` / `:181` als grobe Bereiche — real exakt
  `126-138` bzw. `181` (jetzt präzisiert).
- Erstentwurf wollte `Exec=`-Pfad selbst zusammenbauen und XDG-Ziel selbst ermitteln — beides
  ist in `nxm_handler.py` bereits gelöst und wird wiederverwendet (Abschnitt 2).
- Erstentwurf erwähnte einen Anker `anvil/__main__.py` als Ort fürs Arg-Parsing — der reale
  Einstieg ist `anvil/main.py:main()`; `__main__.py`/`main.py` sind nur Wrapper.
- Kein erfundenes Format gefunden; `.desktop` ist real die richtige Form (Beleg
  `nxm_handler.py:126-136`).

## 4. Phasen-Rückgrat (Bau-Reihenfolge nach steigendem Risiko)
| # | Phase | Inhalt | Risiko | Testbar nach Phase? |
|---|---|---|---|---|
| 1 | `.desktop`-Generator (Backend) | Neue Funktion `create_game_shortcut(...)` in neuem Modul, die sich an `register_nxm_handler()` orientiert und `_build_exec_command()` nutzt; schreibt `.desktop` nach `~/.local/share/applications/`. Noch ohne neues CLI-Arg (Exec zeigt zunächst auf reinen Anvil-Start). | Niedrig | Ja — Datei wird erzeugt; Inhalt (`Exec`, `Icon`, `Name`) prüfbar; `desktop-file-validate` |
| 2 | Button verdrahten + Feedback | `_todo("Verknüpfung")`-Connect durch `self._on_create_shortcut` ersetzen; aktuelle Instanz/Spielname/Icon aus Panel-State holen; Erfolg/Fehler + „kein Spiel“ über Statusbar/Toast melden (`tr`-Keys). | Niedrig | Ja — Klick erzeugt Datei, Meldung erscheint, Edge-Case „kein Spiel“ greift |
| 3 | CLI-Arg `--launch-instance` (+ optional `--profile`) | In `anvil/main.py` Argument aus `sys.argv` lesen (Muster `get_nxm_arg`); bei gesetzter Instanz: passende Instanz aktiv setzen (`set_current_instance`) und Anvil mit vorgewählter Instanz öffnen. | Mittel | Ja — `python main.py --launch-instance "<Name>"` öffnet Anvil mit gewählter Instanz |
| 4 | Direkt-Start des Spiels über die Verknüpfung | Auto-Start nach Init an die bestehende Start-Kette (`silent_deploy` + `_on_start_clicked`/`_do_launch`) anbinden; Steam/Proton/REDmod-Verzweigungen NICHT duplizieren. Exec der `.desktop` um das Arg ergänzen (in Phase 1/2 erzeugte Datei aktualisieren). | Hoch | Ja — Doppelklick auf Verknüpfung deployt Mods und startet das Spiel |

Begründung der Reihenfolge: Datei-Erzeugung ist isoliert und sofort prüfbar (1). UI-Verdrahtung
ist lokal (2). Erst danach der invasivere Eingriff in den Init-/Start-Flow (3→4), wo der größte
Abstimmungsbedarf mit Marc liegt (öffnet die Verknüpfung Anvil nur vorgewählt, oder startet sie
das Spiel direkt?).

## 5. Betroffene Dateien
| Datei | Änderung |
|---|---|
| `anvil/core/desktop_shortcut.py` | NEU: `create_game_shortcut(...)` — schreibt spiel-spezifische `.desktop` (nutzt `_build_exec_command()`) |
| `anvil/core/nxm_handler.py` | ggf. `_build_exec_command()` öffentlich machen/importieren (keine Logik ändern) |
| `anvil/widgets/game_panel.py` | `:134` `_todo("Verknüpfung")`-Connect → `self._on_create_shortcut`; neuen Handler ergänzen; Import bei Bedarf |
| `anvil/main.py` | NEU: `--launch-instance` / `--profile` aus `sys.argv` lesen und an Start-/Init-Flow weiterreichen |
| `anvil/mainwindow.py` | ggf. Hilfsmethode für Auto-Start einer Instanz beim Programmstart (bindet an bestehende Deploy-/Start-Pfade an) |
| `anvil/locales/*.json` (7×) | neue Keys (siehe i18n) |

## 6. Umsetzungsschritte (nach Phasen)
1. **Phase 1:** `desktop_shortcut.py` mit `create_game_shortcut(name, icon_path, exec_extra="", target_dir=None)`; `target_dir` default `~/.local/share/applications/` (wie nxm), optional `~/Desktop` (XDG, nicht hardcoden). `Exec=` via `_build_exec_command()` + optionalem Suffix.
2. **Phase 2:** In `game_panel.py` `_on_create_shortcut()` ergänzen: aktuellen Spielnamen (`self._game_label.text()` / `update_game`-State), Icon (über `self._icon_manager` / `_current_short_name`) und Instanz holen; Generator rufen; Ergebnis melden. `_todo`-Connect entfernen; `_todo`-Import nur entfernen, falls nicht mehr genutzt (Achtung: `profile_bar.py:284,287` und `mainwindow.py:84` nutzen `_todo` ebenfalls — nicht global entfernen).
3. **Phase 3:** In `anvil/main.py` Arg lesen (Muster `get_nxm_arg`); Instanz via `instance_manager.set_current_instance(name)` vorwählen; Anvil normal hochfahren.
4. **Phase 4:** Auto-Start an bestehende Kette anbinden (`silent_deploy` → `_on_start_clicked`), Steam/Proton/REDmod nicht duplizieren; `.desktop`-Exec um das Arg ergänzen.
5. i18n-Keys in allen 7 Locales ergänzen.
6. `./restart.sh`; Button drücken; `.desktop` prüfen (`Exec`, `Icon`, `Name`, `desktop-file-validate`); Verknüpfung anklicken → erwartetes Verhalten (Phase 3 bzw. 4).

## 7. i18n (tr-Keys, 7 Locales: de, en, es, fr, it, pt, ru)
Vorhanden und bestätigt in allen 7 Locales: `tooltip.link` — bleibt unverändert.
Neue Keys (in ALLEN 7 Dateien `anvil/locales/{de,en,es,fr,it,pt,ru}.json`):
- `shortcut.created` — Erfolg (DE: „Verknüpfung erstellt: {path}“)
- `shortcut.failed` — Fehler (DE: „Verknüpfung konnte nicht erstellt werden“)
- `shortcut.no_game` — kein Spiel gewählt (DE: „Kein Spiel ausgewählt“)

## 8. Akzeptanzkriterien
- [ ] Klick auf den `linkButton` erzeugt eine gültige `.desktop`-Datei (kein `print`-TODO mehr).
- [ ] `.desktop` enthält korrekten Spielnamen (`Name=`), Spiel-/App-Icon (`Icon=`) und ausführbaren `Exec=` aus `_build_exec_command()` (kein hardcoded Pfad).
- [ ] `_build_exec_command()` wird wiederverwendet — keine eigene Exec-Pfad-Erkennung dupliziert.
- [ ] Zielordner XDG-korrekt (`~/.local/share/applications/`), kein hardcoded Pfad.
- [ ] Edge-Case „kein Spiel ausgewählt“ → `shortcut.no_game`-Hinweis, keine kaputte Datei.
- [ ] Erfolg/Fehler wird gemeldet (Statusbar/Toast) über `shortcut.created` / `shortcut.failed`.
- [ ] CLI-Arg `--launch-instance` öffnet Anvil mit der richtigen Instanz; Verhalten (nur öffnen vs. direkt starten) mit Marc abgestimmt.
- [ ] Direkt-Start nutzt die bestehende Start-Kette (Steam/Proton/REDmod nicht dupliziert).
- [ ] Alle 7 Locale-Dateien enthalten `shortcut.created`, `shortcut.failed`, `shortcut.no_game`.
- [ ] `_todo` nur dort entfernt, wo nicht mehr genutzt (profile_bar/mainwindow nicht brechen).
- [ ] `./restart.sh` startet fehlerfrei (kein NameError/ImportError im `debug.log`).

## 9. Aufwand / Risiko
**Aufwand:** Mittel. Phasen 1+2 sind klein, weil `register_nxm_handler()`/`_build_exec_command()`
als Vorlage existieren. Der Aufwand steckt in Phasen 3+4 (CLI-Arg → Init → Auto-Start).

**Risiko:**
- Phasen 1+2: Niedrig — isolierte Datei-Erzeugung und lokale UI-Verdrahtung.
- Phase 3: Mittel — Eingriff in `main()`-Init-Flow; Single-Instance-Verhalten beachten (zweiter
  Start mit Arg landet evtl. im Forwarder, vgl. `anvil/main.py:79-93`).
- Phase 4: Hoch — Direkt-Start greift in die Start-Kette mit Steam/Proton/REDmod-Verzweigungen
  ein. ✅ GEKLÄRT (2026-06-29, Abschnitt 0): beide Verhalten werden gebaut, ein globaler
  Live-Schalter in den Einstellungen entscheidet zur Laufzeit (Default „das Spiel"). Keine
  BG3-Pfade anfassen.
