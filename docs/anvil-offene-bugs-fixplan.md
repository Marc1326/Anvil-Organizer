# Offene Bugs — Fixplan

Stand: 2026-07-03, Branch `v2/modern-gui`, verifiziert gegen Commit `e9d2f31`.
Quellen: QA-Reviews vom 2026-07-02 (`docs/anvil-review-20260702-*.md`), alle Fundstellen
am 2026-07-03 gegen den aktuellen Code nachgeprüft — Zeilennummern stimmen mit HEAD überein.

Dieses Dokument ist die Arbeitsgrundlage für die Umsetzung der Fixes. Jeder Bug hat:
Fundstelle, Problem, konkreten Lösungsweg, Testhinweis.

---

## Regeln für die Umsetzung (PFLICHT)

1. **EINEN Bug fixen → testen → committen**, dann erst den nächsten. Kleine Commits.
2. Nach jeder Änderung `./restart.sh` ausführen und Log auf Tracebacks prüfen
   (NameError, ImportError, AttributeError). QTabBar-"alignment"-Warnings sind bekannt und ok.
3. `python -m py_compile <datei>` vor jedem Commit.
4. **KEIN `setStyleSheet()`** in Widgets — QSS-Theme wird vererbt.
5. **KEINE hardcoded Pfade** — immer aus Instanz-Config lesen.
6. Neue `tr()`-Keys in **ALLEN 7 Locale-Dateien** (`anvil/locales/`: de, en, es, fr, it, pt, ru).
7. Commit-Messages kurz und natürlich, **KEINE** "Co-Authored-By"-Zeile.
8. Imports prüfen — fehlende Imports sind der häufigste Fehler.
9. Qt-Signal-Falle: `clicked` sendet `bool` → Lambdas mit `lambda checked=False: ...`.
10. Bei Unklarheiten → Marc fragen, nicht raten.

---

## Bereits erledigt — NICHT nochmal anfassen

Diese Punkte aus älteren Reports/Notizen sind inzwischen gefixt (am 2026-07-03 im Code verifiziert):

- **REDmod-Deploy im Flatpak**: Beide Popen-Stellen (`game_panel.py:1642` und `:1932`)
  nutzen jetzt `host_popen`. Erledigt.
- **Starfield `_find_install_root` Wildcard-Bug**: Funktion hat jetzt Strategie 1 mit
  `detect_installed` + `target` (`mod_installer.py:346ff`). Erledigt.
- **Framework-Heuristik "Nein = Mod weg"**: Nach abgelehntem `FrameworkDetectDialog`
  fällt der Code jetzt zum normalen Install durch (`mainwindow.py:2420`,
  Kommentar "User declined — install as normal mod"). `detect_possible_framework`
  läuft nur noch an EINER Stelle (`mainwindow.py:2377`). Erledigt.
- **Stummer Extract-Abbruch**: `extract_to_temp`-Fehler zeigt jetzt
  `error.extract_failed` in der Statusbar (`mainwindow.py:2326-2330`). Erledigt.

Hinweis für Marc (kein Code): Aus dem alten Starfield-Bug können noch Datei-Reste
unter `<game>/Data/SFSE/SFSE/` (doppelter Ordner) liegen — einmal manuell prüfen/löschen.

---

# PRIORITÄT 1 — MITTEL, echter Nutzer-Impact

## Bug 1: Einzel-Install / „Leeren Mod erstellen" schreiben in Legacy-modlist statt global

- **Dateien:** `anvil/mainwindow.py:4214` (Einzel-Archiv-Install via Kontextmenü)
  und `anvil/mainwindow.py:4254` (`_ctx_create_empty_mod`)
- **Problem:** Beide rufen `add_mod_to_modlist(self._current_profile_path, name, False)`
  auf — das schreibt in die **per-Profil**-Legacy-Datei `.profiles/Default/modlist.txt`,
  NICHT in die globale `.profiles/modlist.txt`. `scan_mods_directory` liest bei vorhandener
  globaler modlist nur die globale Reihenfolge → der neue Mod steht dort nicht, wird als
  "external" behandelt und **aktiviert** angehängt, obwohl `False` (deaktiviert) übergeben
  wurde. Außerdem wird eine tote Legacy-Datei wiederbelebt (Verstoß gegen Architektur-Regel 5).
- **Referenz für die korrekte Logik:** Der Batch-Installer macht es richtig, siehe
  `mainwindow.py:~2630-2656`: bei vorhandener globaler modlist → `read_global_modlist`,
  Name einfügen/anhängen, `write_global_modlist(profiles_dir, mod_names)`, und
  **NICHT** in `active_mods.json` eintragen (fehlender Eintrag = deaktiviert).
  Nur im Legacy-Fall (keine globale modlist) → `add_mod_to_modlist`.
- **Lösung:** Eine Hilfsmethode in `MainWindow` extrahieren, z. B.
  `_register_new_mod(self, name: str) -> None`, die genau diese global-vs-legacy-Verzweigung
  kapselt (Logik 1:1 vom Batch-Installer übernehmen, ohne insert_at-Teil). Dann an
  Zeile 4214 und 4254 `add_mod_to_modlist(...)` durch `self._register_new_mod(name)` ersetzen.
  Den Batch-Installer selbst NICHT umbauen (funktioniert), nur die Hilfsmethode dort
  optional mitnutzen, wenn es ohne Verhaltensänderung geht.
- **Test:** In einer Instanz mit globaler modlist per Kontextmenü ein Archiv einzeln
  installieren und einen leeren Mod erstellen → beide müssen **deaktiviert** in der Liste
  erscheinen, in `.profiles/modlist.txt` (global) stehen, und es darf KEINE
  `.profiles/<Profil>/modlist.txt` neu entstehen.

## Bug 2: UnicodeDecodeError beim Lesen von modlist.txt crasht die App

- **Datei:** `anvil/core/mod_list_io.py:49-50, 268-269, 346-347` (zusätzlich prüfen: `:212`
  liest `active_mods.json` mit demselben Muster)
- **Problem:** `read_text(encoding="utf-8")` ist nur mit `except OSError` abgesichert.
  `UnicodeDecodeError` ist ein `ValueError`, kein `OSError` → propagiert. Eine aus MO2/
  Altbestand stammende modlist.txt in Latin-1 (Umlaute in Mod-Namen) crasht
  `read_modlist` / `read_global_modlist` / `migrate_modlist_order` — im Zweifel schon
  beim App-Start.
- **Lösung (beides machen):**
  1. An allen genannten Stellen `read_text(encoding="utf-8", errors="replace")` —
     so bleibt die Liste nutzbar statt komplett verloren (eine kaputte Zeile wird zum
     „external"-Mod, Rest bleibt intakt).
  2. Zusätzlich als Gürtel+Hosenträger die `except OSError` zu
     `except (OSError, UnicodeDecodeError)` erweitern.
  Bei `:212` (JSON): `errors="replace"` reicht dort nicht allein — prüfen ob
  `json.JSONDecodeError` abgefangen wird; falls nicht, `except (OSError, ValueError)`.
- **Test:** Testdatei erzeugen:
  `printf '+M\xf6dchen\n' > .profiles/modlist.txt` (Latin-1-Byte) → App starten,
  darf nicht crashen, Log prüfen.

## Bug 3: `shutil.move` ohne Ziel-Prüfung → kaputte Mod-Struktur bei Namenskollision

- **Datei:** `anvil/core/mod_installer.py:188` (`install_from_archive`) und
  `:264` (`install_from_extracted`)
- **Problem:** Existiert der Zielordner `dest` bereits, verschiebt `shutil.move` den
  Temp-Ordner ALS UNTERORDNER hinein (`.mods/ModName/anvil_install_XXXX/...`) statt zu
  ersetzen → Mod-Struktur kaputt, Symlinks beim Deploy zeigen ins Leere.
- **Lösung:** Direkt vor beiden `shutil.move`-Aufrufen defensiv prüfen:
  ```python
  if dest.exists():
      dest = self._unique_dest(dest)   # oder Abbruch mit None + Log
  ```
  Im Installer nachsehen, ob es bereits eine Namens-Eindeutigkeits-Hilfe gibt
  (`suggest_name` o. ä.) und die wiederverwenden; sonst kleine Hilfsfunktion, die
  `Name`, `Name (2)`, `Name (3)` … probiert. WICHTIG: `dest` NICHT stillschweigend
  löschen — Datenverlust-Risiko.
- **Test:** Denselben Mod zweimal über einen Pfad installieren, der die
  Duplikat-Abfrage des Aufrufers umgeht (z. B. `install_from_extracted` direkt) →
  es darf kein verschachtelter `anvil_install_*`-Ordner in `.mods/<Name>/` entstehen.

## Bug 4: Kein atomares Schreiben kritischer Dateien (Datenverlust bei Absturz)

- **Dateien:** `anvil/core/mod_list_io.py:88, 237, 312, 379` (modlist.txt / active_mods.json),
  `anvil/core/mod_deployer.py:557-558` (`.deploy_manifest.json`)
- **Problem:** Direktes `write_text`. Wird der Prozess mitten im Schreiben beendet
  (Absturz, OOM-Kill, Stromausfall), bleibt eine abgeschnittene/leere Datei zurück →
  Mod-Reihenfolge/Aktiv-Status weg, bzw. Purge findet Symlinks nicht mehr
  (Orphans im Game-Verzeichnis).
- **Lösung:** Eine Hilfsfunktion in `mod_list_io.py` (Modul-Ebene):
  ```python
  def _atomic_write_text(path: Path, text: str) -> None:
      tmp = path.with_name(path.name + ".tmp")
      tmp.write_text(text, encoding="utf-8")
      tmp.replace(path)   # os.replace = atomar auf demselben Dateisystem
  ```
  Alle 4 Stellen in `mod_list_io.py` darauf umstellen. Im Deployer entweder die
  Funktion importieren oder das gleiche 3-Zeilen-Muster lokal verwenden
  (Manifest: `json.dumps` zuerst in String, dann atomar schreiben).
  Die bestehende Fehlerbehandlung (`except OSError`) drumherum beibehalten.
- **Test:** `./restart.sh`, Mods umsortieren, aktivieren/deaktivieren, deployen →
  alles funktioniert wie vorher; keine `.tmp`-Dateien bleiben liegen.

## Bug 5: Ungespeicherte Theme-Farb-Overrides gehen beim Theme-Wechsel im Dialog verloren

- **Datei:** `anvil/widgets/settings_dialog.py:1573-1581` (`_on_theme_changed`)
- **Problem:** Ändert der Nutzer Rollenfarben (nur im Speicher `self._color_overrides`),
  wechselt dann im Combo das Theme und wieder zurück, überschreibt `_on_theme_changed`
  die in-memory-Änderungen mit `load_overrides(...)` frisch aus QSettings. Die noch
  nicht mit OK bestätigten Änderungen sind unwiderruflich weg — stiller Datenverlust
  in der Bearbeitungssitzung.
- **Lösung:** Session-Cache pro Theme:
  1. In `__init__` neben `self._color_overrides` ein Dict anlegen:
     `self._session_overrides: dict[str, dict] = {}` und eine Variable
     `self._overrides_theme = <initial gewähltes Theme>`.
  2. In `_on_theme_changed`: ZUERST den aktuellen Stand sichern:
     `self._session_overrides[self._overrides_theme] = dict(self._color_overrides)`,
     DANN laden: `self._color_overrides = self._session_overrides.get(theme_name)
     or load_overrides(self._settings(), theme_name)`,
     danach `self._overrides_theme = theme_name`.
  3. Prüfen, ob der Modern-Design-Pfad (`_on_design_clicked` / `_selected_modern_theme`)
     dieselbe Falle hat — falls ja, gleiches Muster dort.
  4. Beim OK/Übernehmen speichern wie bisher (nur das aktuell gewählte Theme);
     `reject()` bleibt unverändert (verwirft bewusst).
- **Test:** Einstellungen → Farbe ändern (nicht OK) → Theme wechseln → zurückwechseln →
  die geänderte Farbe muss noch da sein. Danach OK → Farbe persistiert.

## Bug 6: Unvollständiges Escaping der .desktop Exec-Zeile

- **Datei:** `anvil/core/desktop_shortcut.py:68-69`
- **Problem:** `safe_instance = instance_name.replace('"', "")` entfernt nur
  Anführungszeichen. Die freedesktop-Spec verlangt, dass in doppelt-gequoteten
  Exec-Argumenten auch `$`, Backtick und `\` escaped werden. Ein Instanzname mit
  diesen Zeichen erzeugt eine spec-widrige Exec-Zeile → Start schlägt fehl oder
  verhält sich undefiniert.
- **Lösung:**
  ```python
  import re
  safe_instance = re.sub(r'([\\`$"])', r'\\\1', instance_name)
  ```
  (Backslash MUSS in der Zeichenklasse zuerst gedacht sein — `re.sub` mit Klasse
  erledigt das korrekt in einem Pass, keine Ketten-Ersetzung nötig.)
  Zusätzlich Bug 19 (Newlines in Name=/Comment=) gleich mit erledigen, selbe Datei.
- **Test:** Instanz mit Namen wie `Test$abc` anlegen, Verknüpfung erstellen,
  erzeugte `.desktop`-Datei ansehen: `Exec=... "Test\$abc"`. Start über die
  Verknüpfung muss funktionieren.

## Bug 7: `save_proton_tools` ohne Fehlerbehandlung — Exception im Qt-Slot

- **Datei:** `anvil/widgets/proton_tools_dialog.py:54-56` (`save_proton_tools`)
  und `:302` (`_on_ok`)
- **Problem:** `fp.write_text(...)` ist nicht in try/except gekapselt. Beim OK-Klick
  kann `OSError` fliegen (Laufwerk nicht gemountet, read-only, Platte voll) — eine
  unbehandelte Exception im Qt-Slot kann die App beenden. `load_proton_tools` ist
  im Gegensatz dazu sauber abgesichert.
- **Lösung:** In `_on_ok` den Speicheraufruf kapseln:
  ```python
  try:
      save_proton_tools(...)
  except OSError as exc:
      QMessageBox.warning(self, tr("error.start_failed_title"), str(exc))
      return   # Dialog offen lassen, damit nichts verloren geht
  self.accept()
  ```
  Falls es keinen passenden vorhandenen tr()-Key gibt: neuen Key
  (z. B. `proton_tools.save_failed`) in ALLEN 7 Locales anlegen.
- **Test:** `.anvil-tools.json` (bzw. die Zieldatei, Name im Code prüfen) mit
  `chmod 444` schreibschützen → OK klicken → Warnung erscheint, kein Crash,
  Dialog bleibt offen.

---

# PRIORITÄT 2 — MITTEL, UI-Freezes (Diagnose-Tab / Einstellungen)

## Bug 8: Diagnose-Daten werden eager beim Öffnen der Einstellungen geladen

- **Datei:** `anvil/widgets/settings_dialog.py:1101-1102`
  (`self._diag_refresh()` und `self._diag_populate_log_sources()` im Aufbau)
- **Problem:** Läuft bei JEDEM Öffnen der Einstellungen — auch wenn der Diagnose-Tab
  nie angeschaut wird. `collect_deploy_status` macht pro Manifest-Eintrag synchrone
  Stat-Calls (reales Starfield-Manifest: 504+ Einträge) im GUI-Thread;
  `read_log_tail` liest die komplette activity.log. Auf langsamen Mounts
  (z. B. /mnt/gamingS) friert die UI beim Öffnen kurz ein.
- **Lösung:** Lazy-Load beim ersten Aktivieren des Tabs:
  1. Die beiden Aufrufe an Zeile 1101-1102 entfernen, stattdessen Flag
     `self._diag_loaded = False`.
  2. `self._tabs.currentChanged.connect(self._on_tab_changed)` (bzw. an bestehenden
     Handler anhängen, falls es schon einen gibt — prüfen!). Darin: wenn der
     Diagnose-Tab aktiv wird und `not self._diag_loaded` →
     `_diag_refresh()` + `_diag_populate_log_sources()` + Flag setzen.
  3. Der manuelle „Aktualisieren"-Button (Zeile 1082) bleibt unverändert.
- **Test:** Einstellungen öffnen (anderer Tab aktiv) → sofort da, kein Ruckler.
  Diagnose-Tab anklicken → Daten erscheinen. Aktualisieren-Button funktioniert.

## Bug 9: Konflikt-Scan blockiert den GUI-Thread

- **Datei:** `anvil/widgets/settings_dialog.py:1472ff` (`_diag_scan_conflicts`) →
  `mainwindow.collect_diagnostics_conflicts` → `ConflictScanner().scan_conflicts`
- **Problem:** Vollständiger Dateisystem-Scan aller aktiven Mods läuft synchron im
  GUI-Thread — bei vielen Mods spürbarer Freeze ohne Feedback.
- **Lösung:** Scan in Worker auslagern (Muster: `QThread` oder
  `QThreadPool.globalInstance().start(...)` mit einem kleinen `QRunnable` +
  Signal-Objekt — im Projekt nachsehen, ob es schon einen Worker-Helper gibt,
  z. B. beim Download-Manager oder Update-Check, und DENSELBEN Stil verwenden):
  1. Button beim Start deaktivieren + Text auf „Scanne…".
  2. Scan-Ergebnis (Liste von Dicts) per Signal zurück in den GUI-Thread,
     dort Tabelle füllen, Button reaktivieren.
  3. WICHTIG: Im Worker NUR lesen (Scan ist read-only), keine Qt-Widgets anfassen.
  4. Dialog-Close während des Scans absichern (Worker-Ergebnis auf gelöschten
     Dialog prüfen, z. B. via `QPointer`-Äquivalent `shiboken6.isValid` oder
     schlicht try/except RuntimeError).
- **Test:** Instanz mit vielen Mods → Scan starten → UI bleibt bedienbar,
  Ergebnis erscheint, kein Crash wenn man den Dialog währenddessen schließt.

## Bug 10: `read_log_tail` lädt die gesamte Logdatei in den RAM

- **Datei:** `anvil/core/diagnostics.py:257-269`
- **Problem:** `f.readlines()` liest die komplette Datei, erst danach werden die
  letzten `max_lines` geschnitten. Bei großer activity.log unnötiger Speicher-/Zeitaufwand.
- **Lösung:**
  ```python
  from collections import deque
  ...
  lines = list(deque(f, maxlen=max_lines))
  ```
  (`deque` mit `maxlen` iteriert die Datei zeilenweise und behält nur die letzten N —
  eine Zeile Änderung, Import an den Dateikopf.)
- **Test:** Diagnose-Tab → Log-Viewer zeigt weiterhin die letzten Zeilen an.

---

# PRIORITÄT 3 — NIEDRIG (Politur, in beliebiger Reihenfolge)

## Bug 11: Deploy ohne aktive Mods meldet Erfolg UND Fehler gleichzeitig

- **Datei:** `anvil/core/mod_deployer.py:194-196`
- **Problem:** `result.errors.append("No enabled mods found.")` bei `success=True`
  (Default). Aufrufer, die `errors` prüfen, zeigen im legitimen Leerfall eine
  Fehlermeldung; Aufrufer, die `success` prüfen, sehen Erfolg. Widersprüchlich.
- **Lösung:** Den `errors.append(...)` entfernen — der Leerfall ist kein Fehler.
  VORHER alle Aufrufer von `deploy(...)` durchsuchen (`grep -rn "\.errors"`):
  falls einer die Meldung „No enabled mods" aktiv anzeigt und das gewollt ist,
  stattdessen ein eigenes Feld (`result.skipped_reason`) einführen. Im Zweifel:
  einfach entfernen.
- **Test:** Deploy mit 0 aktiven Mods → keine Fehlermeldung, kein Fehl-Status.

## Bug 12: Variable-Shadowing `c` (Spaltenindex vs. QColor) im Model

- **Datei:** `anvil/models/mod_list_model.py:297` (`c = index.column()`) vs.
  `:413` (`c = QColor(r.color)`)
- **Problem:** Im BackgroundRole-Zweig wird `c` mit einer QColor überschrieben.
  Aktuell harmlos, aber latenter Bug sobald danach wieder mit der Spalte
  gearbeitet wird.
- **Lösung:** An Zeile 413 (und den Folgezeilen, die dieses `c` nutzen) in
  `col` o. ä. umbenennen. Reines Rename, keine Logikänderung.

## Bug 13: `_update_priorities` ohne Guard gegen leere Liste

- **Datei:** `anvil/models/mod_list_model.py:736-746`
- **Problem:** Bei `len(self._rows) == 0` erzeugt `self.index(len(self._rows)-1, ...)`
  einen ungültigen Index (-1) in `dataChanged.emit`.
- **Lösung:** Erste Zeile der Methode: `if not self._rows: return`.
  ABER prüfen: danach werden `self._drop_in_progress = True` und
  `self.mods_reordered.emit()` gesetzt/gesendet — sicherstellen, dass der Early-Return
  keinen Aufrufer bricht, der auf `mods_reordered` wartet (Aufrufer von
  `_update_priorities` ansehen). Im Zweifel nur den `dataChanged.emit` absichern.

## Bug 14: Toter Menüeintrag „Benachrichtigungen…"

- **Datei:** `anvil/mainwindow.py:575-576`
- **Problem:** `act.setEnabled(False)` — der Eintrag tut nie etwas. Das echte Feature
  ist der Benachrichtigungen-Button in der Titelzeile
  (`_on_title_notifications_clicked`, Zeile 7568).
- **Lösung (empfohlen):** Verdrahten statt entfernen:
  `act.setEnabled(True)` und `act.triggered.connect(self._on_title_notifications_clicked)`.
  VORHER prüfen, ob der Handler das Panel am Button verankert — falls das Panel
  eine Anker-Position vom Button braucht und über das Menü falsch aufpoppt,
  alternativ den Menüeintrag ersatzlos entfernen (beides ok, Marc bevorzugt
  funktionierende Einträge über tote).

## Bug 15: Notification-Panel aktualisiert sich nicht bei neuen Meldungen

- **Datei:** `anvil/widgets/notification_panel.py` (kein `center.changed`-Connect
  vorhanden; `_refresh` existiert bereits, Zeile 99)
- **Problem:** Trifft während des geöffneten Panels eine neue Meldung ein
  (Download fertig), bleibt die Liste veraltet.
- **Lösung:** Im `__init__` des Panels: `center.changed.connect(self._refresh)`.
  Da das Panel `WA_DeleteOnClose` nutzt: in `closeEvent` (oder via
  `self.destroyed.connect(...)`) die Verbindung wieder trennen —
  sonst feuert das Signal gegen ein gelöschtes C++-Objekt (RuntimeError).
  Muster:
  ```python
  self._center.changed.connect(self._refresh)
  ...
  def closeEvent(self, event):
      try:
          self._center.changed.disconnect(self._refresh)
      except (RuntimeError, TypeError):
          pass
      super().closeEvent(event)
  ```
- **Test:** Panel öffnen, in zweitem Terminal einen Download anstoßen bzw. eine
  Notification künstlich auslösen → Liste aktualisiert sich live.

## Bug 16: NotificationCenter wächst unbegrenzt

- **Datei:** `anvil/core/notification_center.py:34-42` (`add`)
- **Problem:** Kein Limit für `self._items` — lange Sitzung = unbegrenzter Speicher.
- **Lösung:** Konstante `MAX_ITEMS = 100` im Modul; am Ende von `add()`:
  `del self._items[MAX_ITEMS:]`. (Neueste stehen vorn, insert(0) — Zeile 40.)

## Bug 17: Diagnose-Export verschluckt Fehler still, kein Erfolgs-Feedback

- **Datei:** `anvil/widgets/settings_dialog.py:1536-1546` (`_diag_export`,
  `except OSError: pass` an Zeile 1545)
- **Lösung:** Bei Erfolg `self.window().statusBar()...` geht im Dialog nicht —
  stattdessen `QMessageBox.information` mit Zielpfad; bei `OSError`
  `QMessageBox.warning` mit `str(exc)`. Neue tr()-Keys (z. B.
  `settings.diag_export_ok` / `settings.diag_export_failed`) in ALLEN 7 Locales.
- **Test:** Export in schreibgeschützten Ordner → Warnung; normaler Export → Bestätigung.

## Bug 18: Diagnose-Report enthält volle Pfade inkl. Benutzername

- **Datei:** `anvil/core/diagnostics.py` (`build_report`, Abschnitt `[Pfade]`, ~Zeile 288-296)
- **Lösung:** Beim Zusammenbauen der Pfad-Zeilen `str(Path.home())` durch `~` ersetzen:
  `line.replace(str(Path.home()), "~")`. Nur für die Report-Ausgabe, nicht für die
  interne Logik.

## Bug 19: .desktop `Name=`/`Comment=` ungefiltert (Newlines brechen die Datei)

- **Datei:** `anvil/core/desktop_shortcut.py:74-76`
- **Lösung:** Zusammen mit Bug 6 erledigen: Steuerzeichen/Newlines strippen, z. B.
  `re.sub(r'[\x00-\x1f]', ' ', name).strip()`.

## Bug 20: Diagnose-Tab nutzt hardcoded Hex-Farben statt Theme-Palette

- **Datei:** `anvil/widgets/settings_dialog.py:1429-1433` (Pfad-Status) und
  `:1453-1454` (Problem-Severity) — `#98C379/#E5C07B/#E06C75`
- **Problem:** Farben passen sich nicht an Themes an (v. a. Hell-Modus relevant,
  der jetzt existiert).
- **Lösung:** Farben aus der Theme-Palette beziehen — `settings_dialog.py` importiert
  bereits `default_palette` und `COLOR_ROLES` (Zeile 46). Passende Rollen
  (success/warning/error) verwenden; falls es solche Rollen nicht gibt, die Farben
  wenigstens pro Theme (hell/dunkel) unterscheiden. Erst schauen, wie der neue
  Hell-Modus das an anderen Stellen löst (Commit 200c151 „hartkodierte Farben
  theme-bewusst" als Vorbild — `git show 200c151` ansehen und dasselbe Muster nehmen).

## Bug 21: Verwaiste .desktop-Verknüpfungen nach Instanz-Rename/-Delete

- **Datei:** `anvil/core/desktop_shortcut.py` (Erstellung:
  `anvil-game-<slug>-<hash>.desktop`, Slug+Hash aus dem Instanznamen)
- **Problem:** Bei Rename/Delete der Instanz bleibt die alte Verknüpfung in
  `~/.local/share/applications` liegen (plus ggf. gecachtes Icon).
- **Lösung:** Neue Funktion `remove_game_shortcut(instance_name)` in
  `desktop_shortcut.py`, die den Dateinamen mit derselben Slug+Hash-Logik ableitet
  und `unlink(missing_ok=True)` macht (+ Icon-Datei, falls separat gecacht).
  Aufrufen an den Stellen, wo Instanzen umbenannt/gelöscht werden
  (`grep -n "def.*rename\|def.*delete" anvil/core/instance_manager.py` und die
  aufrufenden Dialoge). Beim Rename danach optional neu anlegen, falls vorher
  eine Verknüpfung existierte — im Zweifel nur löschen, nicht neu anlegen.

## Bug 22: Nativer Custom-Tool-Start ohne stdout/stderr-Umleitung

- **Datei:** `anvil/mainwindow.py:2142-2146` (`_on_custom_tool_start`, nativer Zweig)
- **Problem:** Der Direktstart erbt Anvils stdout/stderr → gesprächige Tools spammen
  die Konsole. `run_with_proton` nutzt bereits DEVNULL.
- **Lösung:** `stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL` an den
  `host_popen`-Aufruf anhängen (`subprocess` ist in mainwindow.py bereits
  importiert — prüfen!).

## Bug 23: Alter ExecutablesDialog (Platzhalter) koexistiert mit echtem Editor — ⚠️ ZURÜCKGESTELLT, NICHT UMSETZEN

- **Dateien:** `anvil/widgets/executables_dialog.py` (kompletter Dialog),
  erreichbar über `anvil/widgets/toolbar.py:150` und `anvil/mainwindow.py:854-855`
  (Werkzeuge-Menü, Strg+E)
- **Problem:** Der Dialog ist ein Platzhalter mit `setStyleSheet` (Regel-Verstoß) und
  hardcoded Spielnamen („Cyberpunk 2077", „REDprelauncher"). Das ECHTE Feature #25
  ist der Editor „Eigene Programme verwalten" (ProtonToolsDialog). Zwei Editoren
  verwirren.
- **Lösung (Empfehlung):** Platzhalter-Dialog entfernen und beide Aufrufstellen
  (toolbar.py:150, mainwindow.py:854) auf den echten Editor umleiten
  (nachsehen, wie das Game-Panel „Eigene Programme verwalten" öffnet, und dieselbe
  Methode aufrufen). Datei `executables_dialog.py` danach löschen.
- **⚠️ STATUS (Marc, 2026-07-03): ZURÜCKGESTELLT.** Marc entscheidet später selbst,
  ob der alte Dialog weg kann. Diesen Bug ÜBERSPRINGEN — nichts entfernen,
  nichts umleiten.

## Bug 24: Toter Code / Typ-Drift in instance_manager (kosmetisch)

- **Datei:** `anvil/core/instance_manager.py:35` (`_CURRENT_FILE` — Konstante wird
  nirgends benutzt, es gibt die Methode `_current_file()` an Zeile 419) und
  `save_instance` (Zeile 346ff — persistiert nur eine feste Key-Liste;
  `auto_archive`/`detected_store` fehlen; bool-Werte kommen aus `_read_ini` als
  String und gehen als String zurück).
- **Lösung:** Konstante an Zeile 35 löschen. Rest nur anfassen, wenn ein konkreter
  Aufrufer die fehlenden Keys speichern will — sonst als bekannt dokumentiert lassen.

## Bug 25: `migrate_to_global_modlist` scheitert, wenn das Default-Profil keine modlist hat

- **Datei:** `anvil/core/mod_list_io.py:448ff`
- **Problem:** Quelle für die globale Reihenfolge ist das Default-Profil; hat NUR ein
  anderes Profil eine modlist.txt, wird fälschlich `False` zurückgegeben. Enger
  Edge-Case bei Altbeständen.
- **Lösung:** Fallback: wenn Default keine modlist hat, das erste Profil (sortiert)
  mit vorhandener modlist.txt als Quelle nehmen. Logik in der Funktion, ~5 Zeilen.

---

## Empfohlene Reihenfolge / Commits

1. Bug 2 (Unicode) — kleinster Fix, sofortiger Crash-Schutz → Commit
2. Bug 1 (Legacy-modlist) → Commit
3. Bug 4 (atomares Schreiben) → Commit
4. Bug 3 (shutil.move) → Commit
5. Bug 5 (Theme-Overrides) → Commit
6. Bug 6 + 19 (Desktop-Escaping, eine Datei) → Commit
7. Bug 7 (save_proton_tools) → Commit
8. Bug 8 + 10 (Diag lazy + log tail) → Commit
9. Bug 9 (Konflikt-Scan Worker) → Commit
10. Rest (11-22, 24, 25) in kleinen Gruppen; Bug 23 ÜBERSPRINGEN (zurückgestellt, Marc entscheidet).

Nach JEDEM Commit: `./restart.sh` + Log prüfen. Bei Regressionen: stoppen und melden,
nicht weiterstapeln.
