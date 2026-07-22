# Code-Review — Features #24 (.desktop-Verknüpfung) & #25 (Eigene Programme) + 2 Fixes
Datum: 2026-07-02
Reviewer: QA-Prüfer (nur Lesen, kein Code geändert)

Geprüfte Commits: cecd840 (#24), 4582f97 (#25-Label), 7290182 (#25), 5718e51 (Fix switch_instance), 38ba7ba (Fix fehlender Pfad)

Vorbedingung erfüllt: ARCHITEKTUR.md gelesen. Die Änderungen berühren KEINE Mod-Verwaltung/Deploy/modlist.txt/Frameworks — die 7 Architektur-Schutzregeln sind nicht betroffen (kein MO2-Vergleich nötig, da reine Start-/UI-/Verknüpfungs-Logik).

---

## Findings

### 1. [MITTEL] Unvollständiges Escaping der .desktop Exec-Zeile
- Datei: anvil/core/desktop_shortcut.py:68-69
- Problem: `safe_instance = instance_name.replace('"', "")` entfernt nur Anführungszeichen. Die freedesktop-Spec verlangt, dass innerhalb doppelt-gequoteter Exec-Argumente auch `$`, Backtick und `\` mit Backslash escaped werden. Ein Instanz-/Ordnername mit `$`, Backtick oder `\` erzeugt eine spec-widrige Exec-Zeile → undefiniertes Verhalten beim Start.
- Positiv: Der eigentliche Hauptfall (Leerzeichen im Pfad "Anvil Organizer" bzw. im Instanznamen) ist korrekt gelöst, weil `_build_exec_command()` alle Pfade in doppelte Quotes wrappt und der Instanzname ebenfalls gequotet wird.
- Fix: Reserved chars (`"`, Backtick, `$`, `\`) escapen statt nur `"` zu entfernen, z. B. `re.sub(r'(["`$\\])', r'\\\1', instance_name)`.

### 2. [MITTEL] save_proton_tools ohne Fehlerbehandlung — mögliche Slot-Exception
- Datei: anvil/widgets/proton_tools_dialog.py:54-56 (save_proton_tools) und :302-305 (_on_ok)
- Problem: `fp.write_text(...)` ist NICHT in try/except gekapselt. Beim Klick auf OK kann ein OSError auftreten (Instanz-Laufwerk nicht gemountet, read-only, Platte voll). Eine unbehandelte Exception im Qt-Slot `_on_ok` kann (PySide6 6.5+) die App beenden. `load_proton_tools` ist demgegenüber sauber abgesichert.
- Fix: Schreibvorgang in `_on_ok` in try/except OSError kapseln und bei Fehler `QMessageBox.warning` zeigen, Dialog offen lassen.

### 3. [NIEDRIG] ExecutablesDialog-Platzhalter: setStyleSheet + hardcodierte Spielnamen
- Datei: anvil/widgets/executables_dialog.py:40 (setStyleSheet), :61-68 (hardcoded "Cyberpunk 2077", "REDprelauncher" …)
- Problem: Verstößt gegen die Regel "kein setStyleSheet() in Widgets" (QSS-Theme wird umgangen) und enthält hartkodierte Spielnamen/Beispieldaten ohne Funktion. Dieser Dialog gehört NICHT zu #25 (das echte #25-Feature ist ProtonToolsDialog). Er ist aber weiterhin über "Werkzeuge → Executables (Strg+E)" (mainwindow.py:779) und toolbar.py:108 erreichbar und koexistiert damit verwirrend mit dem neuen Editor "Eigene Programme verwalten".
- Hinweis: Von diesen Commits NICHT geändert (vorbestehend). Nur zur Kenntnis, da explizit zur Prüfung genannt.
- Fix: Platzhalter entfernen oder auf QSS umstellen; klären ob der doppelte Editor gewollt ist.

### 4. [NIEDRIG] Keine Bereinigung verwaister .desktop-Verknüpfungen
- Datei: anvil/core/desktop_shortcut.py (create_game_shortcut, gesamter Ablauf)
- Problem: Bei Instanz-Rename/-Delete bleiben alte `anvil-game-<slug>-<hash>.desktop` in ~/.local/share/applications liegen (Slug+SHA1 hängen am Instanznamen). Verwaiste, nicht mehr startbare Verknüpfungen häufen sich an.
- Fix: Beim Rename/Delete die zugehörige .desktop-Datei (via Slug+Digest) entfernen; optional auch das gecachte Icon.

### 5. [NIEDRIG] Nativer Custom-Tool-Start ohne stdout/stderr-Umleitung
- Datei: anvil/mainwindow.py — _on_custom_tool_start (nativer Zweig, host_popen([exe_path, *args], …))
- Problem: Anders als run_with_proton (nutzt DEVNULL) erbt der native Direktstart Anvils stdout/stderr; gesprächige Tools spammen die Anvil-Konsole. Popen wird zudem verworfen (kein poll/reap → potenzieller Zombie). Command-Injection besteht NICHT (Listen-Argumente, kein shell=True) — korrekt.
- Fix: stdout/stderr=subprocess.DEVNULL setzen wie in run_with_proton.

### 6. [NIEDRIG] Flatpak-Sandbox: Verknüpfung/Icon landen ggf. im Sandbox-Home
- Datei: anvil/core/desktop_shortcut.py:58-60 und anvil/widgets/game_panel.py (_save_shortcut_icon)
- Problem: Beide schreiben nach `Path.home()/.local/share/...`. Im Flatpak zeigt Path.home() ohne `--filesystem=home` auf `~/.var/app/<ID>/` → die Verknüpfung erscheint nicht im System-Menü. Selbes bekanntes Muster wie register_nxm_handler (bereits ausgeliefert), daher konsistent. AppImage-Fall ist korrekt: `$APPIMAGE` (persistenter Pfad) wird VOR dem PyInstaller-Zweig geprüft → Exec-Zeile stimmt.
- Fix: Optional Flatpak-Portal/`--filesystem` dokumentieren; kein Code-Bug.

### 7. [NIEDRIG] .desktop Name=/Comment= ungefiltert
- Datei: anvil/core/desktop_shortcut.py:74-76
- Problem: display_name/name gehen ungefiltert in die localestring-Zeilen. Ein Newline im Namen würde die Zeile brechen. Sehr unwahrscheinlich (Spiel-Labels).
- Fix: Newlines/Steuerzeichen aus dem Namen strippen.

### 8. [NIEDRIG] Auswahl-Rückfall nach Löschen eines Custom-Tools (nur UX)
- Datei: anvil/widgets/game_panel.py — _on_exe_menu_about_to_show
- Problem: Wird das zuvor gewählte Custom-Tool im Editor gelöscht, findet die Identity-Restore-Schleife keinen Treffer; die Auswahl fällt auf Index 0 (Spiel) zurück. Kein Crash (Bounds-Guard in _on_start_clicked:1190 und _on_exe_selected vorhanden). Reine UX-Notiz.

---

## Bewertung der beiden Fixes (Vollständigkeit)

### Fix 5718e51 (switch_instance-Guard) — VOLLSTÄNDIG
- Alle Aufrufer von `_apply_instance` laufen über `switch_instance` (Startup ruft jetzt ebenfalls nur `switch_instance`, der Alt-Guard im Startup wurde korrekt entfernt). Direkte, ungeschützte `_apply_instance`-Aufrufe existieren nicht (nur Zeile 1159 in switch_instance + 1172 im Reset-Pfad).
- Der Reset-Pfad ergänzt korrekt `_current_plugin`, `_current_game_path`, `_mod_index` (konsistent mit den __init__-/No-Game-Definitionen 1144/1146/1200/1201). `.current` wird erst nach erfolgreichem Laden persistiert → kaputte Instanz sperrt den Start nicht mehr.

### Fix 38ba7ba (fehlender Spiel-/Downloads-Pfad) — VOLLSTÄNDIG
- `set_downloads_dir` fängt OSError beim mkdir ab und merkt den Pfad trotzdem.
- Fehlender game_path (bei gesetztem game_path_str) → Toast `toast.game_path_missing` (Key liegt korrekt in der `toast`-Sektion aller 7 Locales, Code liest ihn passend aus).
- Geprüfte Folge-Codepfade mit gleichem Muster:
  - `profiles_dir.mkdir` (mainwindow.py:1327) und `(profiles_dir/"Default").mkdir` (1337): Können bei komplett fehlendem Instanz-Laufwerk werfen, sind aber jetzt vom switch_instance-try/except (5718e51) abgefangen → kein Crash, sauberer No-Game-Reset.
  - `refresh_downloads` (game_panel.py:2151): Guard `if not self._downloads_path or not is_dir(): return` vorhanden → kein Crash bei fehlendem Downloads-Ordner.
- Ergebnis: Kein weiterer ungeschützter Crash-Pfad im Instanz-Ladefluss gefunden.

---

## Zusätzlich geprüft (in Ordnung)

- tr()-Keys: ALLE verwendeten Keys (shortcut.*, settings.shortcut_launch_game, game_panel.custom_executables/edit_executables/start_with_name, proton_tools.* komplett, error.start_failed_*, toast.game_path_missing, tooltip.link) existieren in ALLEN 7 Locales (de/en/es/fr/it/pt/ru).
- Signal/Slot: `custom_start_requested = Signal(str, list, str, bool)` korrekt an `_on_custom_tool_start` verbunden; `single.message_received` → `handle_ipc_message` korrekt umgestellt.
- Lambda-Fallen: Alle `triggered.connect(lambda checked, i=idx: …)` binden idx per Default-Argument (kein Closure-Bug); `clicked.connect(lambda checked=False: …)` korrekt.
- Command-Injection: Proton- und Native-Start nutzen Listen-Argumente, kein shell=True → sicher.
- Hardcoded Pfade im Feature-Code: keine — Exec-Kommando kommt aus build_exec_command() (Flatpak/AppImage/PyInstaller/Dev-Erkennung).
- setStyleSheet in NEUEN Widgets (#24/#25): keine (ProtonToolsDialog nutzt objectName + QSS).
- Setting `Interface/shortcut_launch_game` wird gespeichert (settings_dialog) UND ausgelesen (launch_instance_shortcut) → funktional wirksam.
- Fehlende Imports: keine (Toast top-level importiert Z.49, clean_subprocess_env/host_popen Z.39, QMessageBox/Path in game_panel vorhanden).
- Direkt-Start via Verknüpfung: nach switch_instance wird das Executable-Menü in _rebuild_executables_menu (Z.463) neu aufgebaut, Index 0 = Spiel → start_selected startet korrekt.

---

## Ergebnis

Keine KRITISCHEN/crash-verursachenden Fehler in den geprüften Änderungen. Beide Fixes sind vollständig. Offen: 2×MITTEL (Exec-Escaping, save_proton_tools ohne try/except) + 6×NIEDRIG.

Empfehlung: Vor Freigabe die beiden MITTEL-Punkte beheben (#1, #2). NEEDS FIXES (MITTEL), ansonsten funktional tragfähig.
