# QA-Review 2 — Overlay-Deploy (Branch feat/overlay-deploy)

Datum: 2026-08-04
Umfang: `git diff e82a5c3..HEAD` (b34e345, 7676ead, 8772484)
Schwerpunkt: Integration, Signal/Slot, Variablen-Gueltigkeit, Imports, Qt, Locales
Gelesen vorab: `anvil-wiki/dev-notes/ARCHITEKTUR.md`, `docs/anvil-feature-overlay-deploy.md`

---

## CRITICAL

### C1 — Schichtreihenfolge ist verkehrt herum, das Spiel gewinnt gegen die Mods
- Datei: `anvil/core/overlay_deployer.py:230-234` (`lowerdirs`), `anvil/core/overlay_launch.py:57-62` (Wrapper)
- Problem: `lowerdirs()` liefert `[Mod-Schicht, Spielordner]` ("hoechste Prioritaet zuerst" —
  das ist die Kernel-`lowerdir`-Reihenfolge). Der Wrapper reicht diese Liste in genau dieser
  Reihenfolge als `--overlay-src` an bwrap. bwrap dreht die Bedeutung aber um.
  Aus `man bwrap`:
  > The sources are overlaid in the order given, with the first source on the command line at the
  > bottom of the stack: if a given path to be read exists in more than one source, the file is read
  > from the last such source specified. (For readers familiar with overlayfs, note that this is the
  > reverse of the order used by the kernel's lowerdir mount option.)
- Nachgemessen auf diesem System (bwrap `/usr/bin/bwrap`):
  ```
  --overlay-src modlayer --overlay-src game   -> cat datei.txt = VANILLA
  --overlay-src game --overlay-src modlayer   -> cat datei.txt = MOD
  ```
- Auswirkung: Jede Mod, die eine vorhandene Spieldatei ersetzt, ist wirkungslos — die
  Originaldatei ueberdeckt sie. Nur Dateien, die es im Spielordner gar nicht gibt, kommen an.
  Das ist exakt der Fehler, den das Feature laut `docs/anvil-feature-overlay-deploy.md` (Abschnitt
  "Warum") beseitigen soll. Es erklaert auch den im Dokument als "Offener Punkt" beschriebenen
  Effekt, dass redscript Funktionen aus `Codeware.Global.reds` nicht findet, obwohl die Datei in
  der Schicht liegt: der Spielordner-Stand gewinnt.
  Das Akzeptanzkriterium "Prioritaet: hoeher priorisierte Mod gewinnt bei gleichem Pfad" ist damit
  NICHT erfuellt, obwohl es abgehakt ist.
- Zusaetzlich: `tests/test_overlay_deploy.py:207` friert die falsche Reihenfolge als Sollwert ein
  (`lowerdirs == [stage_dir, game]`), der Test kann den Fehler also nie finden.
- Fix: In `lowerdirs()` (oder spaetestens in `_write_mount_conf`) die Liste fuer den Wrapper
  umdrehen: `[Spielordner, Mod-Schicht]`, bei mehreren Mod-Schichten die niedrigste Prioritaet
  zuerst. Test entsprechend anpassen und um einen echten Mount-Vergleich ergaenzen.
- Schweregrad: CRITICAL

---

## HIGH

### H1 — Staging stuerzt ab, wenn zwei Mods Datei gegen Ordner stellen
- Datei: `anvil/core/overlay_staging.py:106-119` (`_place`)
- Problem: `dest.parent.mkdir(parents=True, exist_ok=True)` wirft `FileExistsError`, wenn ein
  Pfadbestandteil bereits als Datei in der Schicht liegt. `dest.unlink()` wirft
  `IsADirectoryError`, wenn dort ein Verzeichnis liegt. Beides ist nicht abgefangen.
  Der Symlink-Deployer faengt genau diesen Fall ab (`mod_deployer.py:486-507`: `except OSError ->
  errors.append + continue`).
- Reproduziert (ModA hat die Datei `gemeinsam`, ModB den Ordner `gemeinsam/`):
  ```
  File "anvil/core/overlay_staging.py", line 107, in _place
      dest.parent.mkdir(parents=True, exist_ok=True)
  FileExistsError: [Errno 17] File exists: .../stage/main/gemeinsam
  ```
- Auswirkung: Die Ausnahme laeuft ungefangen durch `OverlayStage.build()` ->
  `OverlayDeployer.deploy()` (`overlay_deployer.py:270`, kein try) -> `GamePanel.silent_deploy()`
  -> `MainWindow._predeploy_for_launch()` (`mainwindow.py:2580`, kein try) in den Qt-Slot
  `_on_start_game`. Der Spielstart bricht mit Traceback ab statt mit einer Fehlermeldung.
- Fix: `_place` komplett in `try/except OSError` fassen und den Fehler wie im Symlink-Deployer in
  `result.errors` sammeln.
- Schweregrad: HIGH

### H2 — Trenner-Zielpfade erreichen den OverlayStage nie
- Datei: `anvil/widgets/game_panel.py:1104-1105`, `anvil/core/overlay_deployer.py:148,152-165`,
  `anvil/mainwindow.py:1963-1964`
- Problem: `set_separator_deploy_paths()` schiebt die Zuordnung nachtraeglich per
  `self._deployer._separator_deploy_paths = ...` in den Deployer. Beim `ModDeployer` funktioniert
  das, weil er das Feld erst beim Deploy liest. Der `OverlayDeployer` reicht die Zuordnung dagegen
  im Konstruktor an `OverlayStage` weiter; sein eigenes `self._separator_deploy_paths` wird danach
  nirgends mehr gelesen (nur Zeile 148). Die nachtraegliche Zuweisung ist tot.
  Verschaerfend: In `_apply_instance` wird `set_instance_path()` (Zeile 1963, baut den Deployer)
  VOR `_sync_separator_deploy_paths()` (Zeile 1964) aufgerufen. Beim Laden einer Instanz bekommt
  der Stage also `{}` bzw. die Zuordnung der vorher geladenen Instanz.
  Auch der Aufruf direkt vor dem Spielstart (`mainwindow.py:2579`) laeuft ins Leere.
- Auswirkung: Mods in einem Trenner mit eigenem Zielpfad landen im Overlay stillschweigend im
  Hauptspielordner — genau der Fehler, der laut Doku ("Nachtrag 04.08.2026") geschlossen sein soll.
  Nach einem Profilwechsel verhaelt es sich anders als nach einem Instanzwechsel, das Verhalten ist
  also zusaetzlich nicht reproduzierbar.
- Fix: `OverlayDeployer` braucht einen echten Setter, der auch `self._stage._separator_deploy_paths`
  nachzieht (analog `set_skipped_mods`), oder `GamePanel.set_separator_deploy_paths()` baut den
  Deployer neu. Zusaetzlich in `_apply_instance` die Reihenfolge drehen.
- Schweregrad: HIGH

### H3 — upperdir eines Mounts liegt im upperdir eines anderen
- Datei: `anvil/core/overlay_deployer.py:319`
- Problem: Mount 0 bekommt `.overwrite` als Schreibschicht, jeder weitere Mount
  `.overwrite/extern-N`. `man bwrap`:
  > Due to limitations of overlayfs, no host directory given via --overlay-src or --overlay may be
  > an ancestor of another, after resolving symlinks. Depending on version, the Linux kernel may or
  > may not enforce this, but if not then overlayfs's behavior is undefined.
- Auswirkung: Sobald Trenner-Zielpfade eingerichtet sind (siehe H2), entstehen zwei Mounts, deren
  Schreibschichten ineinander liegen. Je nach Kernel schlaegt der Mount fehl oder verhaelt sich
  undefiniert. Wird heute nur deshalb nicht sichtbar, weil H2 die zweiten Schichten verhindert.
- Fix: Die Schreibschichten nebeneinander legen, z.B. `.overwrite` und
  `<instanz>/.overlay/upper/extern-N`, oder alle unter einem gemeinsamen Elternordner, der selbst
  nicht Schreibschicht ist.
- Schweregrad: HIGH

### H4 — Der eingestellte Overwrite-Ordner wird ignoriert
- Datei: `anvil/widgets/game_panel.py:2979-2994` (Fabrik), `anvil/core/overlay_deployer.py:134,143-145`
- Problem: `_create_deployer` uebergibt `overwrite_path` nicht. Der `OverlayDeployer` faellt damit
  immer auf `<instanz>/.overwrite` zurueck, auch wenn `path_overwrite_directory` auf ein anderes
  Laufwerk zeigt (`instance_paths.py:72`).
- Auswirkung: Alle Schreibvorgaenge des Spiels landen an einer anderen Stelle als vom Nutzer
  eingestellt. Zusammen mit F2 prueft der Einstellungsdialog ausserdem ein anderes Dateisystem als
  das, welches spaeter wirklich benutzt wird — die Voraussetzungspruefung kann gruen sein, waehrend
  der Mount scheitert.
- Fix: In der Fabrik `overwrite_path=` aus `resolve_instance_paths(...)` durchreichen (das Panel
  bekommt die Pfade bereits ueber `set_downloads_path`/`_profiles_path`, `overwrite` fehlt dort noch).
- Schweregrad: HIGH

---

## MEDIUM

### M1 — Der Einstellungsdialog schaltet den Overlay-Schalter still ab und speichert das auch
- Datei: `anvil/widgets/settings_dialog.py:1396-1406` und `:1966`
- Problem: `_check_overlay_requirements()` setzt bei jedem Problem
  `self._cb_use_overlay.setChecked(False)` und `setEnabled(False)`. `accept()` schreibt danach
  bedingungslos `idata["use_overlay"] = self._cb_use_overlay.isChecked()`.
- Auswirkung: Wer den Dialog auf einem System oeffnet, auf dem gerade `bwrap` fehlt, das
  Spiellaufwerk nicht gemountet ist oder der Spielordner nicht erreichbar ist, verliert seine
  Einstellung dauerhaft — ohne Rueckfrage und ohne dass er den Schalter angefasst haette.
  Der Schalter laesst sich danach im gleichen Dialog auch nicht mehr zuruecksetzen.
- Fix: Bei Problemen nur sperren und den Grund anzeigen, den gespeicherten Wert aber nicht
  ueberschreiben (in `accept()` bei `not isEnabled()` den alten Wert aus `_idata` uebernehmen).
- Schweregrad: MEDIUM

### M2 — Die Voraussetzungspruefung prueft im Normalfall gar kein Dateisystem
- Datei: `anvil/widgets/settings_dialog.py:1391-1394`
- Problem: `overwrite = self._idata.get("path_overwrite_directory", "")`. Der Schluessel ist im
  Regelfall nicht gesetzt (Vorgabe `.overwrite` relativ zur Instanz, siehe `instance_paths.py:72`),
  dann ist `upper = None` und `environment_problems()` ueberspringt die Dateisystem-Pruefung
  komplett. Ist der Schluessel gesetzt, wird der Rohwert per `Path(overwrite)` genommen, also ohne
  `resolve_instance_paths()` — Platzhalter- und Relativpfade landen ungeprueft in
  `filesystem_of()`, das dann relativ zum Arbeitsverzeichnis aufloest.
- Auswirkung: Genau die Pruefung, die tmpfs/ramfs abfangen soll (der einzige harte Blocker laut
  `_UNSUPPORTED_UPPER`), laeuft bei der Standardkonfiguration nie. Akzeptanzkriterium
  "Voraussetzungen werden geprueft und verstaendlich gemeldet" ist nur teilweise erfuellt.
- Fix: `resolve_instance_paths(self._instance_path, self._idata).overwrite` verwenden.
- Schweregrad: MEDIUM

### M3 — Startoption kann gesetzt werden, bevor der Wrapper existiert
- Datei: `anvil/widgets/settings_dialog.py:1329-1335, 1337-1381`, `anvil/core/overlay_launch.py:91-101`
- Problem: `_overlay_launch_option()` baut den Pfad aus `wrapper_path(instance_path)`. Geschrieben
  wird das Skript aber ausschliesslich in `OverlayDeployer.deploy()` (`overlay_deployer.py:304`).
  Der Knopf prueft nicht, ob die Datei da ist.
- Auswirkung: Wer den Knopf vor dem ersten Deploy drueckt, traegt bei Steam einen Pfad ein, der
  nicht existiert. Steam startet das Spiel dann gar nicht mehr — auch nicht ohne Mods. Fuer den
  Nutzer sieht das nach einem kaputten Spiel aus, nicht nach einer Anvil-Einstellung.
  Ergaenzend fehlt der Rueckweg: es gibt keinen Knopf, der die Startoption wieder entfernt, wenn
  der Nutzer auf Symlinks zurueckschaltet.
- Fix: Vor dem Eintragen `write_wrapper()` aufrufen (das Skript ist unabhaengig vom Deploy-Inhalt)
  und einen "Startoption entfernen"-Weg anbieten.
- Schweregrad: MEDIUM

### M4 — Steam-Pfad fest verdrahtet, obwohl es dafuer eine Funktion gibt
- Datei: `anvil/core/overlay_launch.py:123-124`
- Problem: `root = steam_root or (Path.home() / ".local" / "share" / "Steam")`. Im Projekt gibt es
  `anvil/stores/steam_utils.py:89 find_steam_path()`, das zusaetzlich `~/.steam/steam`, Flatpak und
  Snap kennt und bereits in `base_game.py:328` benutzt wird.
- Auswirkung: Nutzer mit Flatpak-Steam oder `~/.steam/steam` bekommen "Keine Steam-Konfiguration
  gefunden", obwohl Steam installiert ist. Verstoesst zusaetzlich gegen die Projektregel
  "NIEMALS hardcoded Pfade".
- Fix: `find_steam_path()` als Vorgabe verwenden.
- Schweregrad: MEDIUM

### M5 — Proton-Shim-DLLs landen im Overlay-Betrieb weiterhin echt im Spielordner
- Datei: `anvil/widgets/game_panel.py:1318-1330`, `:1440-1481`
- Problem: `_deploy_proton_shims()` kopiert die DLLs mit `shutil.copy2` direkt nach
  `game_path / fname` und traegt sie in `ModDeployer.MANIFEST_NAME` ein. Im Overlay-Betrieb gibt es
  dieses Manifest nicht (`manifest_path.is_file()` ist falsch), der Eintrag entfaellt.
- Auswirkung: Verstoss gegen Architektur-Regel 1 und gegen das Kernversprechen des Features
  ("Spielordner nach dem Deploy unveraendert"). Die Dateien werden ausserdem nie wieder entfernt,
  weil kein Manifest sie kennt. Betrifft Fallout 4 (`X3DAudio1_7.dll`) und Skyrim SE
  (`winhttp.dll`).
- Fix: Im Overlay-Betrieb in `deployer.stage_dir` kopieren statt in den Spielordner.
- Schweregrad: MEDIUM

### M6 — `ReshadeManager.set_target_root()` wird nie aufgerufen
- Datei: `anvil/core/reshade_manager.py:50-56`, `anvil/widgets/game_panel.py:78-95`
- Problem: Der Docstring von `_tune_for_overlay` nennt ausdruecklich "Packer, Plugin-Leser und
  ReShade". Alle acht Aufrufstellen (1208, 1297, 1377, 1429, 1695, 1726, 1796, 1863) uebergeben
  aber nur `BA2Packer` oder `PluginsTxtWriter`. Der einzige Ort, an dem ein `ReshadeManager`
  entsteht, ist `anvil/dialogs/reshade_wizard.py:62` — dort ohne jede Overlay-Behandlung.
- Auswirkung: ReShade installiert weiterhin echte Dateien in den Spielordner. Der neue Setter ist
  toter Code, die Tabelle "Betroffene Dateien" im Feature-Dokument suggeriert faelschlich, dass
  dieser Punkt erledigt ist.
- Fix: Entweder den Wizard anbinden (er braucht dazu Zugriff auf den Deployer) oder den Setter
  entfernen und den Punkt im Dokument als offen fuehren.
- Schweregrad: MEDIUM

### M7 — Deutsche Fehlertexte ohne `tr()` landen in der Oberflaeche
- Datei: `anvil/core/overlay_deployer.py:267,281,307,368,379`, `anvil/core/overlay_launch.py:175,180`
- Problem: `"Keine aktiven Mods gefunden."`, `f"Manifest schreiben: {exc}"`,
  `"Schicht entfernen: ..."`, `"Manifest entfernen: ..."`, `"Steam laeuft -- Startoption kann nicht
  gesetzt werden"`, `f"App {app_id} steht nicht in {config}"` sind fest deutsch.
  Die beiden `RuntimeError`-Texte werden in `settings_dialog.py:1373-1377` woertlich per
  `"\n".join(fehler)` in eine `QMessageBox` gelegt.
- Auswirkung: Nutzer der uebrigen sechs Sprachen bekommen deutsche Fehlermeldungen. Der
  Symlink-Deployer benutzt an derselben Stelle englische Texte ("No enabled mods found."), das
  Ergebnis ist zusaetzlich uneinheitlich.
- Fix: Locale-Schluessel anlegen und `tr()` benutzen, wie bei den uebrigen Overlay-Meldungen.
- Schweregrad: MEDIUM

### M8 — Umlaute und Akzente fehlen in den neuen Locale-Texten
- Datei: `anvil/locales/de.json:898-900,1382-1394`, entsprechend `es/fr/it/pt`
- Problem: Die neuen Strings sind ASCII-transliteriert: "daruebergelegt", "erfuellt", "Steam
  laeuft", "Aenderung", "ueberschreiben"; im Spanischen "no esta instalado", Franzoesisch
  "n'est pas installe", Italienisch "non e installato", Portugiesisch "nao esta".
  Der Rest derselben Dateien schreibt korrekt ("Farbe wählen", "vollständige", "Änderung").
- Auswirkung: Sichtbar unsaubere Oberflaeche, faellt gegenueber dem restlichen Text auf.
- Fix: Umlaute und Akzente nachziehen. (Betrifft nur die Locale-Dateien, nicht den Quelltext.)
- Schweregrad: MEDIUM

### M9 — BA2-Angaben werden im Overlay-Betrieb nicht mehr fortgeschrieben
- Datei: `anvil/widgets/game_panel.py:1273-1274` und `:1622-1650` (`_update_manifest_ba2`)
- Problem: `self._deployer.is_deployed()` liefert im Overlay `True` (Overlay-Manifest da),
  `_update_manifest_ba2()` greift danach aber hart auf `ModDeployer.MANIFEST_NAME` zu und kehrt
  wortlos zurueck, weil diese Datei fehlt.
- Auswirkung: `ba2_archives` und `ini_backup` werden nicht mehr festgehalten. Aktuell liest zwar
  niemand diese Felder, die Stelle ist aber eine stille Sackgasse, die beim naechsten Feature
  auffaellt. Gleiches Muster in `_deploy_proton_shims` (siehe M5).
- Fix: Manifestnamen ueber den Deployer beziehen (`type(self._deployer).MANIFEST_NAME`) oder die
  Funktion im Overlay-Betrieb bewusst ueberspringen und das im Code vermerken.
- Schweregrad: MEDIUM

### M10 — Spiele mit eigenem Deployer nehmen den Schalter stillschweigend nicht an
- Datei: `anvil/widgets/game_panel.py:2956-2965`
- Problem: Der Zweig `factory = getattr(plugin, "create_deployer", None)` kommt vor dem
  Overlay-Zweig. Fuer Ghost Recon Breakpoint (und jedes kuenftige Plugin mit eigenem Deployer)
  bleibt `use_overlay` wirkungslos.
- Auswirkung: Der Schalter ist im Dialog sichtbar, laesst sich setzen, wird gespeichert — und tut
  nichts. Kein Hinweis an den Nutzer. (Der Vorrang selbst ist richtig so und durch
  `tests/test_overlay_panel_switch.py` abgesichert; es fehlt nur die Rueckmeldung.)
- Fix: Schalter fuer solche Instanzen sperren und den Grund anzeigen.
- Schweregrad: MEDIUM

### M11 — Kein Test auf das Dateisystem des Spielordners
- Datei: `anvil/core/overlay_deployer.py:72-105`
- Problem: `environment_problems()` prueft nur die Schreibschicht. Der Spielordner ist die unterste
  Schicht; liegt er auf NTFS (ntfs-3g/FUSE) oder einem anderen Netz-/FUSE-Dateisystem, scheitert
  oder verhaelt sich der Mount je nach Kernel unzuverlaessig. Das Feature-Dokument nennt NTFS
  ausdruecklich als Grund, den Symlink-Weg zu behalten — geprueft wird es nicht.
- Auswirkung: Auf NTFS-Installationen kann der Schalter gesetzt werden; der Fehler faellt erst
  beim Spielstart auf, dann aber nur im Wrapper-Log.
- Fix: `filesystem_of(game_path)` mit auswerten und FUSE/NTFS melden.
- Schweregrad: MEDIUM

---

## LOW

### L1 — Deployer wird pro Instanzwechsel dreimal gebaut, einmal mit falscher Instanz
- Datei: `anvil/mainwindow.py:1768` (`update_game`), `:1960` (`set_overlay_enabled`), `:1963`
  (`set_instance_path`); `anvil/widgets/game_panel.py:2934-2945`
- Problem: `update_game()` baut den Deployer bereits mit dem `_use_overlay` der VORIGEN Instanz.
  `set_overlay_enabled()` baut ihn danach ggf. neu — zu diesem Zeitpunkt zeigt `self._instance_path`
  aber noch auf die alte Instanz, waehrend `_current_game_path` schon die neue ist. Erst
  `set_instance_path()` stellt den korrekten Zustand her.
- Auswirkung: Heute folgenlos, weil `OverlayDeployer.__init__` nichts anlegt. Sobald der
  Konstruktor Nebenwirkungen bekommt (z.B. `mkdir`), entstehen Ordner in der falschen Instanz.
- Fix: `set_overlay_enabled()` nur das Flag setzen lassen, den Neubau `set_instance_path()`
  ueberlassen — oder in `_apply_instance` erst `set_instance_path`, dann den Schalter.
- Schweregrad: LOW

### L2 — `purge()` laesst `mount.conf` und den Wrapper liegen
- Datei: `anvil/core/overlay_deployer.py:355-381`
- Problem: Entfernt werden `stage/`, `work/` und das Manifest — `mount.conf`, `start.log` und das
  Wrapper-Skript bleiben.
- Auswirkung: Nach einem Purge beschreibt `mount.conf` Schichten, die es nicht mehr gibt. Der
  Wrapper faengt das ueber `[ -d "$d" ]` und die Mindestzahl von zwei Schichten ab und startet ohne
  Mods — richtig, aber nur zufaellig richtig, und im Log steht nichts Erklaerendes.
- Fix: `mount.conf` beim Purge mit entfernen oder leeren.
- Schweregrad: LOW

### L3 — Diagnose zeigt Overlay-Status, auch wenn die Instanz auf Symlinks steht
- Datei: `anvil/core/diagnostics.py:219-224`
- Problem: `collect_deploy_status()` prueft `_overlay_status()` bedingungslos zuerst. Ein
  liegengebliebenes `.overlay_manifest.json` (etwa nach einem Versuch mit Overlay) verdeckt den
  echten Symlink-Status.
- Auswirkung: Falsche Diagnoseanzeige. Der Overlay-Zweig meldet ausserdem immer `"broken": 0`, was
  im Diagnose-Text (`settings_dialog.py:1551-1553`) so aussieht, als sei alles geprueft worden.
- Fix: Am `use_overlay`-Schalter der Instanz entscheiden, nicht am Vorhandensein der Datei.
- Schweregrad: LOW

### L4 — Zwei ungenutzte Locale-Schluessel in allen sieben Sprachen
- Datei: `anvil/locales/*.json` — `overlay.requirements_ok`, `overlay.launch_option_hint`
- Problem: Beide Schluessel sind in de/en/es/fr/it/pt/ru gepflegt, werden aber nirgends
  referenziert (`grep` liefert 0 Treffer im Quelltext).
- Auswirkung: Toter Ballast; deutet darauf hin, dass ein geplanter Hinweis-Text im Dialog fehlt.
- Fix: Entweder benutzen (der Hinweistext waere fuer M3 nuetzlich) oder entfernen.
- Schweregrad: LOW

### L5 — Zugriff auf ein privates Feld des Stage
- Datei: `anvil/core/overlay_deployer.py:213-215`
- Problem: `set_skipped_mods()` schreibt direkt `self._stage._skipped`. `OverlayStage` hat dafuer
  keinen Setter, obwohl es fuer `needs_ba2_packing` einen gibt.
- Auswirkung: Faellt beim naechsten Umbau von `OverlayStage` still um.
- Fix: `OverlayStage.set_skipped_mods()` ergaenzen.
- Schweregrad: LOW

### L6 — Der neue Knopf haengt roh im Layout, nicht in einer Zeile
- Datei: `anvil/widgets/settings_dialog.py:236-244`
- Problem: `self._btn_overlay_launch` und `self._lbl_overlay_problems` werden direkt mit
  `prof_layout.addWidget()` eingehaengt, waehrend alle benachbarten Elemente ueber
  `self._setting_row(...)` als Karte laufen.
- Auswirkung: Im modernen Theme bricht die Optik der Gruppe. (Positiv: kein `setStyleSheet()`, die
  Projektregel ist eingehalten; Widgets bekommen ueber `addWidget` einen Parent und sind sichtbar,
  `setVisible(False)` beim Label ist gewollt.)
- Fix: In eine Zeile/Karte einbetten wie die uebrigen Eintraege.
- Schweregrad: LOW

### L7 — Wrapper-Log waechst unbegrenzt
- Datei: `anvil/core/overlay_launch.py:33,38,70,74,78`
- Problem: Jeder Spielstart haengt Zeilen an `start.log` an, nichts rotiert oder kuerzt.
- Auswirkung: Ueber Monate eine grosse Datei in der Instanz; kein Funktionsfehler.
- Schweregrad: LOW

### L8 — `mount.conf` vertraegt keine `|` und `:` in Pfaden
- Datei: `anvil/core/overlay_deployer.py:311-330`, `anvil/core/overlay_launch.py:50-57`
- Problem: Felder werden mit `|` getrennt, Schichten mit `:`. Ein Instanz- oder Spielpfad, der
  eines dieser Zeichen enthaelt, zerlegt die Zeile falsch.
- Auswirkung: Selten, aber der Fehler waere dann stumm (`continue` im Wrapper) — das Spiel startet
  einfach ohne Mods.
- Fix: Wenigstens beim Schreiben pruefen und einen Fehler melden.
- Schweregrad: LOW

### L9 — Frameworks bekommen im Overlay eine andere Prioritaet als beim Symlink-Weg
- Datei: `anvil/core/overlay_staging.py:175-191` gegen `anvil/core/mod_deployer.py:196-236`
- Problem: Der Symlink-Deployer haengt Direct-Install-Mods hinten an und verarbeitet sie nach dem
  `reverse()` als erste, also mit der niedrigsten Prioritaet. `enabled_mods()` im Overlay behaelt
  die Position aus der modlist.txt bei.
- Auswirkung: Nur relevant, wenn ein Framework doch in der modlist.txt steht (laut Architektur
  Regel 3 soll das nicht vorkommen). Dann gewinnt im Overlay ein anderer Datei-Stand als beim
  Symlink-Weg.
- Fix: Reihenfolge angleichen, damit beide Wege beweisbar dasselbe liefern.
- Schweregrad: LOW

### L10 — `start-sandbox.sh` enthaelt feste Benutzerpfade und ist eingecheckt
- Datei: `start-sandbox.sh:14`
- Problem: `DATA="/home/mob/anvil-overlay-data"`, dazu ein fester Verweis auf `.venv`.
- Auswirkung: Auf jedem anderen Rechner unbrauchbar; als Entwicklerhilfe im Repo grenzwertig.
- Schweregrad: LOW

---

## Geprueft und in Ordnung

- **Imports:** `QMessageBox` und `QPushButton` sind in `settings_dialog.py` importiert, `Path` ist
  vorhanden. Die verzoegerten Importe in `_overlay_launch_option`, `_set_overlay_launch_option`,
  `_check_overlay_requirements`, `_create_deployer` und `_migrate_from_symlinks` sind sinnvoll
  platziert (Zirkelbezug/Startzeit) und alle Namen existieren. `os`, `re`, `shutil`, `subprocess`
  in `overlay_launch.py` werden alle benutzt. `py_compile` laeuft auf allen geaenderten Dateien
  durch.
- **Qt-Signal:** `self._btn_overlay_launch.clicked.connect(lambda checked=False: ...)` — korrekt,
  der bool-Parameter wird abgefangen (`settings_dialog.py:242-244`).
- **Widget-Sichtbarkeit:** Beide neuen Widgets gehen ueber `addWidget()` ins Layout und bekommen
  damit einen Parent; `setVisible(False)` beim Problem-Label ist Absicht und wird in
  `_check_overlay_requirements` wieder aufgehoben.
- **Kein `setStyleSheet()`** in den neuen Widgets.
- **Reihenfolge im Konstruktor:** `_check_overlay_requirements()` (Zeile 247) laeuft NACH dem
  Anlegen von `_cb_use_overlay` (233), `_lbl_overlay_problems` (236) und `_btn_overlay_launch`
  (241). Kein Zugriff auf noch nicht existierende Attribute.
- **Ohne gewaehlte Instanz:** `self._idata` ist `{}` (Zeile 146), alle Zugriffe laufen ueber
  `.get()`; `_overlay_launch_option()` und `_steam_app_id()` fangen `instance_manager`/
  `plugin_loader` gleich `None` ab; `accept()` speichert nur bei vorhandener Instanz. Kein Absturz.
- **Wirkung des Schalters:** Nach `accept()` ruft `mainwindow.py:931` `switch_instance()` auf ->
  `_apply_instance` -> `set_overlay_enabled`. Der Schalter greift also ohne Neustart.
- **Aufraeumen beim Wechsel:** `_teardown_current_instance()` ruft `silent_purge()` (Zeile 1627)
  noch mit dem alten Deployer auf, die Overlay-Schicht wird also beim Umschalten entfernt.
- **Attrappen:** `_create_deployer` und `_tune_for_overlay` lesen `_use_overlay` per `getattr(...,
  False)`; `tests/test_overlay_panel_switch.py::FakePanel` funktioniert damit. `_tune_for_overlay`
  prueft `isinstance(stage, Path)` und ruft nur vorhandene Haken auf — ein Plugin-Deployer ohne
  `stage_dir` faellt sauber durch.
- **Persistenz:** `instance_manager.save_instance` schreibt `use_overlay` (Zeile 395-396); das
  Auslesen in `mainwindow.py:1960-1962` vertraegt sowohl `True/False` als auch `"true"/"1"/"yes"`.
- **Locales:** Alle 14 neuen Schluessel liegen in allen 7 Dateien (de, en, es, fr, it, pt, ru), die
  Platzhalter stimmen ueberein (`{fs}`, `{path}`, `{count}`). Kein Schluessel fehlt.
- **Tests:** 67 Tests in den vier Overlay-Dateien laufen gruen.

---

## Zusammenfassung

Der Umbau ist sauber geschnitten — die Fabrik greift an der richtigen Stelle, die Schnittstelle des
Symlink-Deployers wird eingehalten, der Umschalter ist pro Instanz gespeichert und wirkt sofort,
Imports und Signalverbindungen sind fehlerfrei, alle sieben Locales sind vollstaendig.

Er ist aber nicht einsatzbereit:

- **1 CRITICAL** — die Schichten sind gegenueber bwrap verkehrt herum aufgereiht. Mods, die eine
  Spieldatei ersetzen, wirken nicht. Das ist der Kern des Features und laut Doku bereits abgehakt;
  der zugehoerige Test friert die falsche Reihenfolge ein.
- **4 HIGH** — Absturz beim Spielstart bei Datei/Ordner-Kollision zwischen zwei Mods,
  Trenner-Zielpfade erreichen den Stage nie, ineinanderliegende Schreibschichten,
  eingestellter Overwrite-Ordner wird ignoriert.
- **11 MEDIUM**, davon zwei mit Architekturbezug (Proton-Shims und ReShade schreiben weiterhin echt
  in den Spielordner) und einer mit Datenverlust in den Einstellungen.
- **10 LOW.**

Prüfung der sieben Architektur-Regeln: Regel 1 (nichts echt in den Spielordner kopieren) ist durch
M5 und M6 verletzt, Regel 2, 3, 5 sind eingehalten, Regel 4 ist nicht betroffen, Regeln 6 und 7
(MO2-Referenz und Architektur-Doku gelesen) sind fuer dieses Review erfuellt.

**Ergebnis: NEEDS FIXES.**
