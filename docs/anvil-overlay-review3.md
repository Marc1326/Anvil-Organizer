# Review 3 — Overlay-Deploy: Architektur und Wartbarkeit

Datum: 04.08.2026
Worktree: `/home/mob/Projekte/anvil-overlay`
Branch: `feat/overlay-deploy`
Prüfumfang: `git diff e82a5c3..HEAD` (24 Dateien, 3 Commits: 8772484, 7676ead, b34e345)
Referenz: keine ARCHITEKTUR.md und kein Referenzordner vorhanden — geprüft gegen die im
Bestand erkennbaren Konventionen (`mod_deployer.py`, `instance_paths.py`, `game_panel.py`,
CLAUDE.md).

Testlauf: `285 passed, 1 skipped` (voller Suite-Lauf, unverändert grün).
Es wurde **kein** Code geändert.

---

## Kurzfazit

Der Entwurf ist tragfähig und der Kern (Staging, Mount-Beschreibung, Wrapper) ist sauber
gebaut und gut getestet. Der Symlink-Weg ist unangetastet. Die Probleme liegen nicht im
Overlay-Kern, sondern **an den Rändern**: an den Stellen, an denen die restliche App noch
davon ausgeht, dass Mods im Spielordner liegen, und beim Rückweg.

Zwei Befunde wiegen schwer:

* Trenner-Zielpfade kommen im Overlay nicht an (nachgewiesen, siehe H1).
* Ein Wechsel zurück auf Symlinks lässt den Wrapper scharf — das Spiel bekommt danach
  einen eingefrorenen alten Modstand über den frischen Deploy gelegt (H2).

---

## Befunde

### [HIGH] H1 — Trenner-Zielpfade werden vom Overlay stillschweigend ignoriert

* Datei: `anvil/widgets/game_panel.py:1105`, `anvil/core/overlay_deployer.py:148` und `:152`
* Problem: `set_separator_deploy_paths()` aktualisiert den Deployer per direktem
  Attributzugriff (`self._deployer._separator_deploy_paths = ...`). Beim `ModDeployer`
  wirkt das, weil `deploy()` genau dieses Attribut liest. Der `OverlayDeployer` hält
  dieses Attribut ebenfalls, benutzt es aber nirgends — das Staging liest die **eigene
  Kopie** in `OverlayStage._separator_deploy_paths`, die nur im Konstruktor gesetzt wird.
  Verschärfend: `mainwindow.py:1963` ruft `set_instance_path()` (Deployer wird gebaut) und
  erst danach `_sync_separator_deploy_paths()` (`mainwindow.py:1964` → `:2048`). Der
  Deployer entsteht also grundsätzlich mit dem Trenner-Stand der *vorherigen* Instanz bzw.
  mit `{}`, und die Nachbesserung verpufft.
* Nachweis (Wegwerf-Instanz, ein Mod in einem Trenner mit eigenem Ziel):

  ```
  d._separator_deploy_paths = {"Sep_separator": str(ziel)}   # so macht es game_panel
  d.deploy()
  layers: {'': .../.overlay/stage/main}                      # erwartet: 2 Schichten
  mounts: [(G, [stage/main, G])]                             # Ziel Z bekommt keinen Mount
  ```
* Begründung: Genau diese Lücke steht in `docs/anvil-feature-overlay-deploy.md:275` als
  bereits geschlossen. Sie ist über einen anderen Weg zurück. Die Mods landen unbemerkt im
  Hauptspielordner-Layer statt am eingestellten Ziel.
* Schweregrad: HIGH
* Vorschlag: `_separator_deploy_paths` im `OverlayDeployer` zur Property machen, deren
  Setter zusätzlich `self._stage._separator_deploy_paths` nachzieht — oder sauberer:
  `set_separator_deploy_paths()` in das `_Deployer`-Protocol aufnehmen, in beiden Deployern
  implementieren und `game_panel.py:1105` auf den Methodenaufruf umstellen (mit
  `getattr(..., None)`-Rückfall für Plugin-Deployer). Zusätzlich in
  `test_overlay_matches_symlink.py` einen Fall ergänzen, der die Pfade **nach** der
  Konstruktion setzt — der vorhandene Test `test_separator_zielpfad` übergibt sie im
  Konstruktor und trifft den Fehler deshalb nicht.

### [HIGH] H2 — Zurückschalten auf Symlinks lässt den Wrapper scharf

* Datei: `anvil/widgets/game_panel.py:2934` (`set_overlay_enabled`),
  `anvil/core/overlay_launch.py:32`, `anvil/widgets/settings_dialog.py:1966`
* Problem: `set_overlay_enabled(False)` baut nur den Deployer neu. Es bleiben liegen:
  `.overlay/stage/` (die alte Mod-Schicht), `.overlay/mount.conf`,
  `.overlay/anvil-overlay-mount`, `.overlay_manifest.json` — und vor allem die
  Steam-Startoption. Der Wrapper prüft ausschließlich `[ ! -r "$CONF" ]`; da `mount.conf`
  noch existiert, mountet er weiter. Beim nächsten Start liegt die **eingefrorene alte
  Schicht** über dem Spielordner, in dem inzwischen frische Symlinks liegen. Da die Schicht
  im lowerdir vor dem Spielordner steht, gewinnt der alte Stand.
* Begründung: Der Overlay-Weg ist damit nicht sauber rückbaubar, und der Fehler äußert
  sich als „meine Änderungen kommen nicht an" — schwer zuzuordnen.
* Schweregrad: HIGH
* Vorschlag: Beim Abschalten (und beim Instanzwechsel weg vom Overlay) `purge()` laufen
  lassen **und** `mount.conf` löschen; das allein macht den Wrapper harmlos, er meldet dann
  „keine Mount-Angaben — starte ohne Mods". Zusätzlich einen Knopf
  „Startoption entfernen" neben `settings.overlay_set_launch_option` anbieten, der
  `set_launch_options()` mit dem um das Wrapper-Präfix bereinigten Wert aufruft. Solange
  das fehlt, sollte die Checkbox beim Abwählen wenigstens einen Hinweisdialog zeigen.

### [HIGH] H3 — Proton-Shims werden weiter direkt in den Spielordner kopiert

* Datei: `anvil/widgets/game_panel.py:1318-1330` und `:1440-1479`
* Problem: `silent_deploy()` ruft am Ende unverändert `_deploy_proton_shims()` auf. Die
  Funktion kopiert DLLs (z. B. F4SE `version.dll`) mit `shutil.copy2` direkt nach
  `game_path/`. Der Vermerk erfolgt in `.deploy_manifest.json` — die Datei existiert im
  Overlay-Betrieb nicht, der Block wird durch `if manifest_path.is_file()` still
  übersprungen. Ergebnis: echte Dateien im Spielordner, die **niemand** je wieder entfernt.
* Begründung: Bricht die Kernzusage des Features („Der Spielordner wird nicht mehr
  beschrieben", `overlay_deployer.py:3`) und hinterlässt unverfolgte Rückstände — genau
  das, was der Umbau abschaffen soll.
* Schweregrad: HIGH
* Vorschlag: Im Overlay-Betrieb die Shims in `stage_dir` legen (dieselbe Mechanik wie bei
  `_tune_for_overlay`) und den Vermerk weglassen, da die Schicht ohnehin bei jedem Deploy
  neu gebaut wird. Alternativ die Shim-Auslieferung als eigenen Mini-Baustein mit
  `set_target_root()` ausführen, damit sie derselben Regel folgt wie Packer und ReShade.

### [HIGH] H4 — Plugin-Sortierung liest weiter nur den Spielordner

* Datei: `anvil/core/plugins_txt_writer.py:338`, `:364`, `:386`, `:301`
* Problem: Erweitert wurde nur `scan_plugins()` (`:418`, über `set_extra_scan_roots`).
  `sort_entries()`, `sort_and_write()`, `plugin_indices()` und die
  Creation-Club-Erkennung bilden ihr `data_dir` weiterhin ausschließlich aus
  `self._game_path`. Im Overlay-Betrieb liegen die Mod-Plugins physisch in der Schicht.
  `stable_dependency_sort()` ruft `parse_plugin_header(data_dir / name)`
  (`plugin_sorter.py:276`) — für jedes nicht gefundene Plugin setzt das `header.error`, was
  in `parse_errors` landet. `sort_and_write()` schreibt nur, wenn `missing_masters`,
  `cycles` und `parse_errors` **alle** leer sind (`:372`). Sortieren tut also im
  Overlay-Betrieb für Bethesda-Spiele nichts, und `plugin_indices()` liefert falsche
  FE-/Ladeindizes.
* Begründung: Die Feature-Doku führt `plugins_txt_writer.py` mit „8 Stellen mit game_path"
  auf; umgestellt ist eine.
* Schweregrad: HIGH
* Vorschlag: Eine Hilfsmethode `_data_dirs() -> list[Path]` einführen, die
  `game_path/sub` plus `extra_scan_roots/sub` liefert, und alle vier Stellen darauf
  umstellen. Für `parse_plugin_header` reicht ein kleiner Auflöser
  `_locate(name) -> Path | None`, der die Wurzeln in Prioritätsreihenfolge durchgeht.

### [HIGH] H5 — `ReshadeManager.set_target_root()` ist toter Code

* Datei: `anvil/core/reshade_manager.py:50`, Aufrufer fehlt;
  `anvil/dialogs/reshade_wizard.py:62` ist die einzige Instanziierung
* Problem: Die neue Methode wird nirgends aufgerufen. `_tune_for_overlay()`
  (`game_panel.py:78`) kennt zwar den Namen `set_target_root`, bekommt aber nie einen
  `ReshadeManager` übergeben — der Assistent baut seinen Manager selbst.
* Begründung: Der ReShade-Assistent schreibt im Overlay-Betrieb weiter echte Dateien neben
  das Spielbinary. Gleichzeitig gaukelt die Methode vor, der Fall sei erledigt (die
  Feature-Doku listet `reshade_manager.py` als behandelt).
* Schweregrad: HIGH (funktional MEDIUM, als Wartbarkeitsfalle HIGH: tote API, die
  Erledigt-Eindruck erzeugt)
* Vorschlag: Entweder den Assistenten den Panel-Zustand mitgeben lassen und dort
  `_tune_for_overlay(panel, manager)` aufrufen — oder die Methode ersatzlos entfernen und
  im Feature-Dokument als offenen Punkt führen. Halbfertig ist die schlechteste Variante.

### [HIGH] H6 — Nur der Steam-Hauptstart geht durch den Wrapper

* Datei: `anvil/widgets/game_panel.py:1969-2003` (`_do_launch`), `:2611`
  (`_launch_via_proton`), `:1922` (`custom_start_requested`), `:2151`/`:2451` (REDmod)
* Problem: Der Mount hängt an der Steam-Startoption. Alle anderen Startwege umgehen ihn:
  * Nicht-Steam-Instanzen (GOG/Epic) → `start_requested` → direkter Start, nie ein Mount.
  * Zweitbinaries und `GameLaunchViaProton` → `_launch_via_proton()` startet Proton selbst.
  * Eigene Programme (Executables-Editor) → `custom_start_requested`.
  * `redMod.exe deploy` läuft gegen den echten Spielordner; der Kommentar bei `:1959`
    („Sicherstellen dass /mods/ gefuellt ist bevor redMod.exe darueber laeuft") gilt im
    Overlay-Betrieb nicht mehr — REDmod findet dort nichts.
* Begründung: Anvil meldet einen erfolgreichen Deploy, das Spiel bzw. das Werkzeug läuft
  aber ohne Mods. Für Cyberpunk, das Leitspiel dieses Zweigs, betrifft das den
  REDmod-Weg direkt.
* Schweregrad: HIGH
* Vorschlag: Kurzfristig den Schalter nur für Steam-Instanzen mit Hauptbinary anbieten
  (`detectedStore() == "steam"` und kein `GameLaunchViaProton`) und in
  `check_requirements()` als Voraussetzung melden. Mittelfristig alle Startwege durch den
  Wrapper leiten — er ist ein generischer `wrapper … -- kommando`, das lässt sich auch vor
  `proton run` und vor eigene Programme setzen.

### [HIGH] H7 — `path_overwrite_directory` wird ignoriert (hartkodierter Pfad)

* Datei: `anvil/core/overlay_deployer.py:143-145`; Aufrufer
  `anvil/widgets/game_panel.py:2981-2996` (kein `overwrite_path=`);
  Gegenstück `anvil/widgets/settings_dialog.py:1390`
* Problem: `OverlayDeployer` nimmt zwar `overwrite_path` entgegen, `game_panel` reicht es
  aber nie durch. Damit ist die Schreibschicht immer `instance_path/.overwrite` — obwohl
  `instance_paths.resolve_instance_paths()` (`instance_paths.py:72`) genau dafür
  `path_overwrite_directory` auflöst und der Einstellungsdialog seine
  Voraussetzungsprüfung auf **diesen konfigurierten** Pfad stützt. Prüfung und Praxis
  können also auf zwei verschiedene Verzeichnisse zeigen.
* Begründung: Direkter Verstoß gegen die Projektregel „NIEMALS hartkodierte Pfade — immer
  aus Instanz-Config lesen". Wer sein Overwrite auf eine andere Platte gelegt hat, bekommt
  eine grüne Prüfung und danach einen Mount-Fehler oder Schreibvorgänge am falschen Ort.
* Schweregrad: HIGH
* Vorschlag: `game_panel` hält bereits `_mods_path` und `_profiles_path`; analog ein
  `_overwrite_path` aus `resolve_instance_paths()` mitführen (gesetzt in
  `set_downloads_path()` oder besser in einem eigenen `set_storage_paths()`) und an den
  `OverlayDeployer` durchreichen. Dieselbe Quelle dann auch im Dialog verwenden.

---

### [MEDIUM] M1 — Staging-Ordner fest in der Instanz; stilles Kopieren statt Hardlink

* Datei: `anvil/core/overlay_deployer.py:116` (`STAGE_DIR = ".overlay"`),
  `anvil/core/overlay_staging.py:106-119` (`_place`)
* Problem: Die Schicht liegt immer unter `instance_path/.overlay`. `path_mods_directory`
  darf aber auf ein anderes Dateisystem zeigen (`instance_paths.py:69`). Dann scheitert
  `os.link()` bei **jeder** Datei und `shutil.copy2()` greift — aus 0,23 s und 0 Bytes
  werden je nach Sammlung zweistellige Gigabyte-Kopien bei jedem Deploy. Gemeldet wird das
  nur als Zahl in `files_copied`, ohne Einordnung.
* Schweregrad: MEDIUM
* Vorschlag: In `check_requirements()` `os.stat(mods).st_dev` gegen `st_dev` des
  Instanzverzeichnisses prüfen und bei Ungleichheit eine eigene Meldung ausgeben
  (`overlay.cross_device`). Zusätzlich den Staging-Ort konfigurierbar machen — mindestens
  intern als Konstruktorargument wie `mods_path`/`profiles_path`.

### [MEDIUM] M2 — Voraussetzungsprüfung deckt die Dateisystem-Regeln nur halb ab

* Datei: `anvil/core/overlay_deployer.py:26` (`_UNSUPPORTED_UPPER`), `:97-100`
* Problem: (a) Geprüft wird eine Sperrliste (`tmpfs`, `overlay`, `ramfs`), die Meldung
  `overlay.bad_filesystem` nennt aber eine Positivliste („braucht ext4, btrfs oder xfs").
  `ntfs3`/`fuseblk`/`exfat`/`vfat` rutschen durch und scheitern erst beim Mount — für einen
  Linux-Modmanager mit Spielen auf NTFS-Platten ein realistischer Fall.
  (b) overlayfs verlangt upperdir und workdir auf **demselben** Dateisystem; geprüft wird
  nur der Typ des upperdir. Sobald H7 behoben ist, wird das scharf.
* Schweregrad: MEDIUM
* Vorschlag: Auf Positivliste umstellen (`ext4`, `btrfs`, `xfs`, `f2fs`) und zusätzlich
  `st_dev` von `upper_dir` und `work_dir` vergleichen.

### [MEDIUM] M3 — Pfadregeln existieren zweimal, mit bereits messbarer Abweichung

* Datei: `anvil/core/overlay_staging.py:24-43` und `:70-103` gegen
  `anvil/core/mod_deployer.py:39-58` und `:402-465`
* Problem: Vier Konstantenmengen sind wortgleich dupliziert
  (`SKIP_FILES`/`_SKIP_FILES`, `SKIP_DIRS`/`_SKIP_DIRS`,
  `SKIP_ROOT_EXTENSIONS`/`_SKIP_ROOT_EXTENSIONS`,
  `BA2_KEEP_EXTENSIONS`/`_BA2_SYMLINK_EXTENSIONS`), dazu die komplette Zielpfadrechnung
  (`target_rel()` gegen den Inline-Block ab `mod_deployer.py:424`).
  Und die Kopien laufen bereits auseinander: Der Symlink-Weg prüft die BA2-Regel auf `rel`
  **vor** dem Data-Präfix (`mod_deployer.py:430-438`), das Staging auf `dest_rel`
  **danach** (`overlay_staging.py:325`). `is_archive_loose_path()` streift zwar ein
  führendes `data_path` wieder ab (`archive_packing.py:24`), aber nicht ein
  eingeschobenes `<modname>` (bei `nest_under_mod_name`) und nicht eine umgeschriebene
  erste Ebene (Multi-Folder-Routen). Bei dieser Kombination entscheiden die beiden Wege
  unterschiedlich.
* Begründung: Zwei Wahrheiten für dieselbe Regel sind auf Dauer nicht haltbar — die
  nächste Pfadregel wird wieder nur an einer Stelle nachgezogen, und
  `test_overlay_matches_symlink.py` fängt das nur ab, wenn jemand daran denkt, den Fall zu
  ergänzen (die BA2/nest-Kombination ist heute nicht abgedeckt).
* Schweregrad: MEDIUM (Wartungsfalle, nicht vertretbar)
* Vorschlag, konkret:
  1. Neues Modul `anvil/core/deploy_rules.py` mit `SKIP_FILES`, `SKIP_DIRS`,
     `SKIP_ROOT_EXTENSIONS`, `ARCHIVE_KEEP_EXTENSIONS`, `is_metadata()` und
     `target_rel()` — im Wesentlichen der heutige Inhalt von `overlay_staging.py:23-103`,
     unverändert verschoben.
  2. `overlay_staging.py` importiert daraus statt selbst zu definieren.
  3. `mod_deployer.py:402-465` ersetzt den Inline-Block durch `is_metadata()` +
     `target_rel()`; die BA2-Prüfung bleibt dabei bewusst auf dem Pfad **vor** dem Präfix
     — dann in beiden Wegen gleich, indem `target_rel()` in zwei Schritten aufgerufen wird
     (`strip_root()` → BA2-Prüfung → `apply_data_path()`) oder `_packed_away()` den
     ungepräfixten Pfad bekommt.
  4. `test_overlay_matches_symlink.py` um einen Fall „BA2-Packen + `nest_under_mod_name`"
     und einen Fall „BA2-Packen + Multi-Folder-Route" erweitern.
  Der Vergleichstest ist die Absicherung, die diesen Umbau risikoarm macht — er sollte
  genutzt werden, statt die Duplikate stehen zu lassen.

### [MEDIUM] M4 — `extern-N` als dauerhafter Speicherort für Nutzerdaten

* Datei: `anvil/core/overlay_deployer.py:319`, `anvil/core/overlay_staging.py:271`
* Problem: Die zusätzlichen Schreibschichten heißen `upper_dir/extern-1`, `extern-2` …,
  wobei der Index aus `enumerate(self.mounts())` stammt und damit von der
  Einfügereihenfolge im `_layers`-Dict abhängt. Diese Reihenfolge ergibt sich daraus,
  welcher Mod mit eigenem Trennerziel zuerst gestaget wurde. Ändert der Nutzer die
  Modliste, wandert derselbe Zielpfad auf einen anderen Index — die dort zur Laufzeit
  geschriebenen Dateien gehören dann plötzlich zu einem anderen Mount. Zusätzlich liegen
  diese Verzeichnisse **innerhalb** des upperdir von Mount 0.
* Schweregrad: MEDIUM
* Vorschlag: Den Namen aus dem Zielpfad ableiten (stabiler Hash oder bereinigter Pfad
  statt Laufindex) und die Zusatz-Upperdirs neben, nicht in `.overwrite` legen, z. B.
  `.overwrite/.extern/<schluessel>` ist noch drin — besser `<instanz>/.overlay/upper/<schluessel>`.

### [MEDIUM] M5 — Steam-Wurzel hartkodiert, Startoption ohne Rückweg und ohne Auswahl

* Datei: `anvil/core/overlay_launch.py:124`, `:168-206`;
  `anvil/widgets/settings_dialog.py:1336-1385`
* Problem: (a) `localconfig_files()` nimmt fest `~/.local/share/Steam` an. Verbreitet sind
  auch `~/.steam/steam` und die Flatpak-Variante unter
  `~/.var/app/com.valvesoftware.Steam/data/Steam`. Der Parameter `steam_root` wird
  produktiv nie gesetzt. Die Spiel-Plugins lösen die Steam-Wurzel über `findProtonRun()`
  bereits auf — dieses Wissen liegt ungenutzt daneben.
  (b) `_set_overlay_launch_option()` schreibt in **alle** gefundenen Konten, ohne den
  Nutzer zu fragen. Auf einem Rechner mit mehreren Steam-Konten trifft das fremde Profile.
  (c) Ein Gegenstück zum Entfernen fehlt vollständig (siehe H2); die `.anvil-backup`-Datei
  wird angelegt, aber von nichts wieder eingespielt.
* Schweregrad: MEDIUM
* Vorschlag: Steam-Wurzel über die vorhandene Plugin-Logik ermitteln und zusätzlich
  `~/.steam/steam` sowie den Flatpak-Pfad prüfen; bei mehreren Konten eine Auswahl
  anbieten (`QInputDialog.getItem`, wie in `mainwindow._on_locate_storage`); eine Funktion
  `clear_launch_options()` ergänzen.

### [MEDIUM] M6 — Diagnose bleibt nach dem Zurückschalten auf „overlay" stehen

* Datei: `anvil/core/diagnostics.py:179-211`, Aufruf `:222`
* Problem: `_overlay_status()` entscheidet allein an der Existenz von
  `.overlay_manifest.json`. Eine Instanz, die wieder auf Symlinks läuft, deren
  Overlay-Manifest aber liegen geblieben ist (H2), meldet dauerhaft den Overlay-Zustand;
  der echte Symlink-Status wird nie mehr erreicht. Bei unlesbarem Overlay-Manifest wird
  `{"manifest": False}` zurückgegeben statt auf den Symlink-Zweig durchzufallen.
* Schweregrad: MEDIUM
* Vorschlag: Bei defektem Overlay-Manifest `None` liefern, damit der Symlink-Zweig greift;
  und den Overlay-Zweig zusätzlich an den Instanz-Schalter `use_overlay` koppeln (die
  `idata` liegt im Diagnose-Tab ohnehin vor).

### [MEDIUM] M7 — Einstellungsdialog schaltet stumm ab und zeigt den Schalter zu breit

* Datei: `anvil/widgets/settings_dialog.py:1387-1406`, `:1966`
* Problem: Fehlt eine Voraussetzung, setzt `_check_overlay_requirements()` die Checkbox auf
  `False` und deaktiviert sie. Beim Bestätigen wird dieser Wert in `idata["use_overlay"]`
  gespeichert (`:1966`) — die Einstellung des Nutzers ist damit weg, ohne dass es irgendwo
  gesagt wird. Wer einmal auf einem Rechner ohne `bwrap` die Einstellungen öffnet und OK
  drückt, verliert seine Konfiguration.
  Zweitens erscheint der Schalter auch bei Spielen, deren Plugin einen eigenen Deployer
  mitbringt — `_create_deployer()` zieht die Fabrik vor (`game_panel.py:2963-2971`), der
  Schalter bliebe wirkungslos.
* Schweregrad: MEDIUM
* Vorschlag: Bei gesperrter Checkbox den gespeicherten Wert unverändert lassen
  (`if self._cb_use_overlay.isEnabled(): idata["use_overlay"] = ...`) und den
  Sperrgrund im vorhandenen Problem-Label um einen Satz ergänzen. Zeile und Knopf
  ausblenden, wenn das Plugin `create_deployer` mitbringt.

---

### [LOW] L1 — `start-sandbox.sh` enthält persönliche Pfade

* Datei: `start-sandbox.sh:13`, `:35`, Kommentar `:5-7`
* Problem: `DATA="/home/mob/anvil-overlay-data"` ist fest verdrahtet, ebenso die
  Kommentarzeilen mit `/home/mob/Projekte/…` und `/home/mob/.config/…`, und der
  Interpreter ist auf `.venv/bin/python` festgelegt. Die Datei liegt im
  Wurzelverzeichnis neben `restart.sh` und `install.sh`, also da, wo ausgelieferte
  Skripte stehen.
* Begründung: Für einen Worktree-Helfer verständlich, aber es ist ein Entwicklerpfad in
  einem öffentlichen Projekt — genau die Art Rückstand, die im Repo nichts verloren hat.
  Der Kern der Projektregel („keine hartkodierten Pfade") ist auf Instanz-Konfiguration
  gemünzt, hier wird sie aber sichtbar gedehnt.
* Schweregrad: LOW
* Vorschlag: `DATA="${ANVIL_SANDBOX_DATA:-$HOME/anvil-overlay-data}"`,
  `PY="${PYTHON:-$WORKTREE/.venv/bin/python}"`, Kommentare ohne Benutzernamen — oder das
  Skript nach `tools/` verschieben und nicht mit dem Feature-Zweig mergen.

### [LOW] L2 — Deutsche Locale-Texte ohne Umlaute

* Datei: `anvil/locales/de.json:899`, `:1388-1391`
* Problem: „daruebergelegt", „erfuellt", „gehoert", „laeuft", „Aenderung" in
  nutzersichtbaren Texten. Der weit überwiegende Rest von `de.json` benutzt echte Umlaute
  („Wähle", „Kategorie-Zuweisungen übernehmen").
* Schweregrad: LOW
* Vorschlag: In den JSON-Dateien echte Umlaute setzen (im Quelltext dürfen die
  ASCII-Ersatzformen bleiben, das ist bestehende Praxis).

### [LOW] L3 — Zwei unbenutzte Locale-Schlüssel in sieben Sprachen

* Datei: `anvil/locales/*.json` → `overlay.requirements_ok`, `overlay.launch_option_hint`
* Problem: Beide werden von keiner Codestelle gelesen (geprüft über alle `.py`).
* Schweregrad: LOW
* Vorschlag: Entweder verwenden (`requirements_ok` würde sich im Problem-Label gut machen,
  wenn alles passt — das Label wird sonst nur bei Fehlern sichtbar) oder entfernen.

### [LOW] L4 — Diagnose-Anzeige spricht im Overlay-Betrieb von „Links"

* Datei: `anvil/core/diagnostics.py:205` (`"mode": "overlay"`),
  `anvil/widgets/settings_dialog.py:1548-1554`, `anvil/locales/de.json:419`
* Problem: Der neue Schlüssel `mode` wird gesetzt, aber von niemandem gelesen. Angezeigt
  wird weiter `„{total} Links, {broken} defekt, {missing} fehlend"` — im Overlay sind es
  keine Links, und `missing` zählt fehlende Schichten, nicht fehlende Dateien.
* Schweregrad: LOW
* Vorschlag: Eigenen Text `label.diag_deploy_summary_overlay` („{total} Dateien in der
  Schicht, {missing} Schicht(en) fehlen") und `mode` dafür auswerten.

### [LOW] L5 — Wrapper: keine Maskierung der Trennzeichen, Log wächst unbegrenzt

* Datei: `anvil/core/overlay_launch.py:42-71`, `:33`
* Problem: `mount.conf` trennt Felder mit `|` und Schichten mit `:`. Enthält ein Instanz-
  oder Spielpfad eines dieser Zeichen, zerfällt die Zeile still (`|| continue`), und der
  Mount entfällt kommentarlos. Der Log (`start.log`) wird nur angehängt, nie gekürzt.
* Schweregrad: LOW
* Vorschlag: Beim Schreiben in `_write_mount_conf()` prüfen und einen Fehler ins
  `DeployResult` legen, wenn ein Pfad `|` oder `:` enthält; den Log beim Deploy neu
  anlegen (`write_text("")`), er beschreibt ohnehin immer nur den letzten Start.

### [LOW] L6 — Zugriff auf private Felder statt eines Setters

* Datei: `anvil/core/overlay_deployer.py:215`
* Problem: `set_skipped_mods()` schreibt `self._stage._skipped` direkt, obwohl für den
  BA2-Schalter direkt daneben (`:218`) ein ordentlicher Setter auf `OverlayStage`
  existiert. Zwei Stile für dieselbe Sache.
* Schweregrad: LOW
* Vorschlag: `OverlayStage.set_skipped_mods()` ergänzen und aufrufen.

### [LOW] L7 — `_tune_for_overlay()` verlässt sich auf Methodennamen als Zeichenkette

* Datei: `anvil/widgets/game_panel.py:78-95`
* Problem: Die Zuordnung läuft über `getattr(component, name)` mit den Literalen
  `"set_output_root"`, `"set_target_root"`, `"set_extra_scan_roots"`. Wird eine dieser
  Methoden umbenannt, passiert stillschweigend nichts — kein Fehler, kein Log. Genau so
  ist H5 (`set_target_root` ohne Aufrufer) unbemerkt geblieben. Zusätzlich greift die
  Funktion von außen auf `panel._use_overlay` und `panel._deployer` zu und ist damit eher
  eine Methode als eine freie Funktion.
* Schweregrad: LOW
* Vorschlag: Ein schmales `Protocol` (`class _OverlayAware(Protocol): def
  set_overlay_root(self, root: Path) -> None: ...`) definieren und die drei Klassen diese
  eine Methode implementieren lassen; dann ist die Verbindung typgeprüft. Mindestens aber
  eine Debug-Zeile ausgeben, wenn kein Haken greift.

### [LOW] L8 — Produktionscode auf den Test zugeschnitten

* Datei: `anvil/widgets/game_panel.py:2979`, `:78`
* Problem: `getattr(self, "_use_overlay", False)`, obwohl `__init__` das Feld bei `:549`
  setzt. Nötig ist der Rückfall nur, weil `tests/test_overlay_panel_switch.py` mit einem
  `FakePanel` arbeitet, das das Feld nicht kennt.
* Schweregrad: LOW
* Vorschlag: `_use_overlay = False` als Klassenattribut auf `FakePanel` setzen und im
  Produktionscode `self._use_overlay` direkt lesen.

### [LOW] L9 — `set_overlay_enabled()` baut den Deployer mit den alten Pfaden neu

* Datei: `anvil/mainwindow.py:1960` vor `:1963`
* Problem: Beim Instanzwechsel läuft `set_overlay_enabled()` vor `set_instance_path()`.
  Ändert sich der Schalter, entsteht dort ein Deployer mit dem `_instance_path` der
  **vorherigen** Instanz, der drei Zeilen später verworfen wird. Ohne Folgen, weil beide
  Konstruktoren nichts am Dateisystem tun — aber irreführend.
* Schweregrad: LOW
* Vorschlag: `set_overlay_enabled()` zum reinen Setter machen (`self._use_overlay = ...`)
  und den Neubau `set_instance_path()` überlassen; die Wirkung beim Umschalten im
  laufenden Betrieb entsteht ohnehin über `switch_instance()`
  (`mainwindow.py:929-930`).

### [LOW] L10 — `filesystem_of()` entschlüsselt nur Leerzeichen

* Datei: `anvil/core/overlay_deployer.py:46`
* Problem: `/proc/mounts` maskiert `\040` (Leerzeichen), `\011` (Tab), `\012` (Zeilenende)
  und `\134` (Backslash). Behandelt wird nur der erste Fall.
* Schweregrad: LOW
* Vorschlag: Alle vier ersetzen — vier Zeilen, und der Rest der Funktion wird dadurch
  verlässlich.

---

## Antworten auf die gestellten Fragen

**1. Bleibt der Symlink-Weg unangetastet?**
Ja, `anvil/core/mod_deployer.py` ist im Diff nicht enthalten — keine einzige Zeile geändert.
Indirekt berührt sind vier Dateien, jeweils rückwärtskompatibel:

* `ba2_packer.py` — `_output_root` startet als `None`, `_archive_base` fällt auf
  `_game_path` zurück, `set_output_root()` hat keinen Aufrufer im Symlink-Betrieb.
* `reshade_manager.py` — neue Methode ohne Aufrufer (siehe H5), Verhalten unverändert.
* `plugins_txt_writer.py` — `_extra_scan_roots` startet leer; `scan_plugins()` wurde
  umgebaut, liefert aber für eine einzelne Wurzel dasselbe Ergebnis. Eine kleine
  Verhaltensänderung: Bei `OSError` bricht der Scan nicht mehr mit `return []` ab, sondern
  läuft weiter und meldet am Ende „No plugin files found". Für den Einzelwurzel-Fall ist
  das Endergebnis identisch (leere Liste), nur der Text im Log ändert sich. Vertretbar.
* `diagnostics.py` — der Overlay-Zweig greift nur, wenn ein Overlay-Manifest existiert;
  siehe aber M6.

Testlage: 285 Tests grün, davon 67 neue. Der Symlink-Weg ist also belegt unverändert.

**2. Bedient `OverlayDeployer` die Schnittstelle vollständig?**
Das Protocol `_Deployer` (`game_panel.py:70-75`) verlangt `deploy`, `purge`, `is_deployed`
und das Feld `_separator_deploy_paths` — formal erfüllt. Die App ruft darüber hinaus per
`getattr` `set_skipped_mods` (`:1147`) und `set_ba2_packing_enabled` (`:1217`, `:1355`) auf;
beide sind vorhanden. `deployed_mod_count`/`deployed_link_count`/`remove_orphaned_links`
haben aktuell keinen Aufrufer außerhalb von `mod_deployer` selbst.
**Nicht erfüllt ist die Semantik von `_separator_deploy_paths`** — das Feld existiert,
wirkt aber nicht (H1). Das Protocol beschreibt hier zu wenig: Ein Feld im Protocol, das nur
per direktem Attributzugriff bedient wird, kann von einer Implementierung nicht sinnvoll
abgefangen werden. Empfehlung: Protocol um `set_separator_deploy_paths()` erweitern.
Zusätzlich fehlt `DeployResult.skipped_real_files` inhaltlich nie — der Overlay füllt es
korrekterweise nicht, `game_panel:1188` verträgt die leere Liste.

**3. Instanz-Konfiguration statt hartkodierter Pfade?**
Teilweise. `mods_path` und `profiles_path` werden korrekt durchgereicht.
`path_overwrite_directory` **nicht** (H7), das Staging-Verzeichnis ist fest (M1),
die Steam-Wurzel ist fest (M5), und `start-sandbox.sh` enthält persönliche Pfade (L1).

**4. Doppelter Code zwischen `mod_deployer.py` und `overlay_staging.py`?**
Nicht vertretbar — die Kopien laufen bereits messbar auseinander (M3). Konkreter Vorschlag
mit Umbauschritten steht dort.

**5. Kommentare und Docstrings?**
Insgesamt gut getroffen und angenehm zu lesen: Die Modulköpfe erklären **warum**
(„Der Kernel nimmt keine dreihundert lowerdirs entgegen", „Bewusst kein JSON — der
Startwrapper ist ein Shell-Skript"), nicht was ohnehin dasteht. Kein AI-Duktus, keine
Docstring-Inflation. Drei Lücken an kniffligen Stellen:

* `overlay_deployer.py:230-234` (`lowerdirs`) — die zentrale Korrektheitsannahme, dass bei
  `bwrap --overlay-src` die **zuerst** genannte Quelle gewinnt, ist nirgends festgehalten.
  Sie ist nur durch einen Handversuch belegt (Feature-Doku). Das gehört als Kommentar an
  die Funktion, sonst dreht sie irgendwann jemand „aufräumend" um.
* `overlay_staging.py:106-119` (`_place`) — der Fallback auf `shutil.copy2` ist der
  teuerste Pfad im ganzen Feature (M1) und steht kommentarlos als „Anderes Dateisystem
  oder Hardlink-Grenze erreicht" da.
* `overlay_deployer.py:319` — das `extern-{index}`-Namensschema (M4) verdient einen Satz.

Sprachlich mischt `overlay_staging.py` deutsche und englische Bezeichner in derselben
Funktion (`result`, `dest_rel`, `staged_any` neben `ziel_schicht`, `ordner`, `kinder`,
`gefunden`). Innerhalb einer Datei wäre eine Sprache besser.

**6. „MO2"/„ModOrganizer" und maschineller Eindruck?**
Sauber. Kein Treffer für `MO2`, `ModOrganizer`, `Mod Organizer`, `Claude`, `Co-Authored`
oder `Generated with` im gesamten Diff. Die Commit-Titel sind kurz und natürlich
(„Mods per overlayfs einbinden statt per Symlink"). Der Code liest sich handgeschrieben.

**7. Abschaltbar und rückbaubar?**
Abschaltbar ja (Checkbox pro Instanz, Fabrik verzweigt sauber). Rückbaubar **nein** — das
ist der schwächste Punkt des Zweigs:

* Wrapper, `mount.conf`, Manifest, Schicht und Steam-Startoption bleiben stehen (H2), der
  alte Modstand wird weiter über den Spielordner gelegt.
* Es gibt keinen Weg, die Startoption wieder loszuwerden (M5c).
* Die Diagnose meldet weiter „overlay" (M6).
* Wandert die Instanz (Basisverzeichnis-Migration, Umbenennen), zeigt die Startoption auf
  einen nicht mehr existierenden Wrapper. Steam führt dann eine fehlende Datei aus — das
  Spiel startet gar nicht, und in Anvil deutet nichts darauf hin.

Mindestpaket, damit der Rückweg sitzt: beim Abschalten `purge()` + `mount.conf` löschen,
einen Knopf „Startoption entfernen", und beim Instanz-Umzug die Startoption entweder
mitziehen oder entfernen.

---

## Ergebnis

**NEEDS FIXES**

Blockierend vor einem Merge: H1, H2, H3, H4, H7.
H5 und H6 sind entweder zu beheben oder ausdrücklich als bekannte Grenze im Feature-Dokument
und im Einstellungstext zu führen — halbfertig darf nichts davon bleiben.
M3 (Regel-Dedup) sollte im selben Zug erledigt werden, solange der Vergleichstest frisch
ist und die Absicherung bietet; später wird der Umbau nur teurer.

Der Kern des Features ist gut gebaut — Staging, `mount.conf`, Wrapper und die
Voraussetzungsprüfung sind schlank, verständlich und ordentlich getestet. Die Arbeit steckt
nicht mehr im Overlay selbst, sondern darin, die übrige App vollständig mitzuziehen.
