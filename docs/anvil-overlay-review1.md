# Review 1 — Overlay-Deploy (Bugs, Logik, Edge Cases, Fehlerbehandlung)

Datum: 2026-08-04
Umfang: `git diff e82a5c3..HEAD` im Worktree `/home/mob/Projekte/anvil-overlay`
(Commits 8772484, 7676ead, b34e345)
Geprueft gegen: `anvil/core/mod_deployer.py`, `/home/mob/Projekte/anvil-wiki/dev-notes/ARCHITEKTUR.md`,
`docs/anvil-feature-overlay-deploy.md`, `man bwrap` (bubblewrap 0.11.2 auf diesem Rechner)

Drei Befunde sind experimentell belegt (bwrap-Lauf bzw. Python-Probe), nicht nur gelesen.
Die Testsuite laeuft gruen (67 Tests) — sie deckt die schweren Faelle nicht ab, siehe Abschnitt
"Luecken im Vergleichstest".

---

## CRITICAL

### C1 — Schichtreihenfolge ist verdreht: der Spielordner gewinnt gegen die Mods
- Datei: `anvil/core/overlay_deployer.py:230-234` (`lowerdirs`), `anvil/core/overlay_launch.py:57-62` (`_WRAPPER`)
- Problem: `lowerdirs()` liefert `[schicht, spielordner]` ("hoechste Prioritaet zuerst" — das ist die
  Konvention der Kernel-Option `lowerdir=`). Der Wrapper reicht diese Liste in genau dieser Reihenfolge
  als `--overlay-src` an bwrap weiter. bwrap dreht die Reihenfolge aber um:

  > "The sources are overlaid in the order given, with the first source on the command line at the
  > bottom of the stack: if a given path to be read exists in more than one source, the file is read
  > from the last such source specified. (For readers familiar with overlayfs, note that this is the
  > reverse of the order used by the kernel's lowerdir mount option.)"

- Belegt: 
  ```
  bwrap --dev-bind / / --overlay-src $D/stage --overlay-src $D/game --overlay upper work $D/game -- cat $D/game/datei.txt
  -> VANILLA      (Mod-Datei in stage/ wird ignoriert)
  bwrap --dev-bind / / --overlay-src $D/game --overlay-src $D/stage --overlay upper work $D/game -- cat $D/game/datei.txt
  -> MOD          (richtig)
  ```
- Auswirkung: Jede Mod, die eine vorhandene Spieldatei ersetzt, ist wirkungslos. Nur Dateien, die es im
  Spielordner noch nicht gibt, kommen an. Frameworks duerfen im Symlink-Weg ausdruecklich echte
  Spieldateien ueberschreiben (`mod_deployer.py:474-478`) — mit dem Overlay koennen sie es nicht mehr.
  Widerspricht direkt der Feature-Spec (`docs/anvil-feature-overlay-deploy.md:37`: "Bei gleichem Pfad
  gewinnt die Mod ueber die Spieldatei") und dem abgehakten Akzeptanzkriterium in Zeile 171.
- Fix: In `_write_mount_conf` bzw. `lowerdirs` die Liste fuer den Wrapper umdrehen (niedrigste zuerst),
  oder im Wrapper `LAYERS` rueckwaerts durchlaufen. Dazu ein Test, der bwrap wirklich startet und eine
  Datei liest, die es in Mod **und** Spiel gibt.

### C2 — `set_launch_options` zerstoert die Startoptionen einer fremden Steam-App
- Datei: `anvil/core/overlay_launch.py:136-146` (`_app_block`), `168-206` (`set_launch_options`), `149-165` (`read_launch_options`)
- Problem: Die Suche nach einer vorhandenen `LaunchOptions`-Zeile laeuft ueber ein festes Fenster
  `text[match.end()-1 : match.end()+4000]` — das ist **nicht** auf den App-Block begrenzt. Alle Apps in
  `localconfig.vdf` stehen auf derselben Einrueckungstiefe, App-Bloecke sind meist nur ein paar hundert
  Byte gross. Hat die Ziel-App keine `LaunchOptions`, trifft die Regex die Zeile der **naechsten** App.
  Zusaetzlich ist der Blockanker unsauber: die Lookahead `(?:.*\n)*?\1\t"(?:LastPlayed|Playtime|LaunchOptions)"`
  kann ueber Blockgrenzen hinweg matchen, weil `.*\n` beliebig viele Zeilen ueberspringt.
- Belegt (Probe mit 1091500 ohne und 22380 mit LaunchOptions):
  ```
  VORHER  22380: 'PROTON_NO_ESYNC=1 %command%'
  set_launch_options("1091500", "/wrapper %command%", cfg)
  NACHHER 22380: '/wrapper %command%'     <-- ueberschrieben
  NACHHER 1091500: (hat weiterhin keine eigene Zeile)
  ```
  Die Startoption des Nutzers fuer ein anderes Spiel ist weg, der Wrapper haengt am falschen Spiel, und
  das Zielspiel bekommt gar keine Option.
- `read_launch_options` hat denselben Fehler (`block[:4000]`) und liefert den Wert einer fremden App —
  jede darauf gestuetzte "ist schon gesetzt"-Pruefung ist falsch.
- Auswirkung: Beschaedigte, gueltige Steam-Konfiguration. Das `.anvil-backup` rettet nur den allerersten
  Stand und wird nie zurueckgespielt.
- Fix: Den App-Block ueber Klammerzaehlung exakt begrenzen (Start = `{` nach der AppID, Ende = passende
  `}` auf gleicher Tiefe) und nur innerhalb dieses Bereichs suchen/ersetzen. Kein Zeichenfenster.

### C3 — Datei/Ordner-Kollision zwischen zwei Mods laesst den Deploy mit Traceback abstuerzen
- Datei: `anvil/core/overlay_staging.py:106-119` (`_place`), Aufruf `327`
- Problem: `_place` faengt `OSError` nur um `os.link`/`copy2`. `dest.parent.mkdir(...)` (Zeile 107) und
  `dest.unlink()` (Zeile 109) sind ungeschuetzt. Liefert eine Mod `Data/foo` als Datei und eine andere
  `Data/foo/bar.esp`, fliegt je nach Reihenfolge `IsADirectoryError` oder `FileExistsError` bis nach
  oben. `OverlayStage.build` und `OverlayDeployer.deploy` haben kein `try`, `game_panel.silent_deploy`
  auch nicht.
- Belegt:
  ```
  FALL1 overlay CRASH: IsADirectoryError: [Errno 21] .../stage/main/foo   |  FALL1 symlink ok: skipped: ['foo']
  FALL2 overlay CRASH: FileExistsError:   [Errno 17] .../stage/main/foo   |  FALL2 symlink ok (Fehler im Result)
  ```
- Auswirkung: Der Deploy laeuft seit 33413b9 beim Spielstart. Eine solche Kollision (durchaus normal bei
  falsch gepackten Mods) bricht den Spielstart mit einem Traceback ab, statt die Datei zu ueberspringen.
  Der Symlink-Deployer behandelt beide Faelle sauber.
- Fix: `_place` komplett in `try/except OSError` und den Fehler in `result.errors` sammeln; wie beim
  Symlink-Weg entscheiden, wer gewinnt.

---

## HIGH

### H1 — Eigene Zielpfade der Trenner erreichen die Stage nie
- Datei: `anvil/widgets/game_panel.py:1104-1105`, `anvil/core/overlay_deployer.py:148`, `anvil/core/overlay_staging.py:151`
- Problem: `set_separator_deploy_paths()` setzt `self._deployer._separator_deploy_paths` direkt. Beim
  OverlayDeployer ist dieses Attribut aber tot — die Zuordnung passiert in `OverlayStage`, das seine
  Kopie im Konstruktor bekommt. `mainwindow._apply_instance` ruft `set_instance_path` (baut den Deployer)
  **vor** `_sync_separator_deploy_paths()` (mainwindow.py:1960/1964), und `_predeploy_for_launch` ruft
  `_sync_separator_deploy_paths()` unmittelbar vor dem Deploy.
- Auswirkung: Der Overlay arbeitet mit den Trenner-Pfaden des *vorherigen* Zustands (beim ersten
  Instanzwechsel: mit gar keinen). Mods, die in einen eigenen Zielordner sollen, landen in der
  Hauptschicht — also im Spielordner. Der Symlink-Weg macht es richtig, weil er `_separator_deploy_paths`
  bei jedem `deploy()` frisch liest.
- Fix: Setter auf dem OverlayDeployer, der auch `self._stage._separator_deploy_paths` aktualisiert
  (und das Attribut nicht von aussen setzen lassen).

### H2 — Verschachtelte Schreibschichten: `.overwrite` ist Vorfahr von `.overwrite/extern-N`
- Datei: `anvil/core/overlay_deployer.py:317-320` (`_write_mount_conf`)
- Problem: Mount 0 bekommt `upper = .overwrite`, Mount N bekommt `upper = .overwrite/extern-N`.
  `man bwrap`: "no host directory given via --overlay-src or --overlay may be an ancestor of another,
  after resolving symlinks. ... overlayfs's behavior is undefined."
- Belegt: Bei zwei Mounts taucht `extern-1` als Eintrag **im Spielordner** auf (`ls game` listet
  `datei.txt extern-1 nur_mod.txt`). Das Spiel sieht einen Fremdordner in seinem Wurzelverzeichnis.
- Zusaetzlich: der Name `extern-{index}` haengt an der Iterationsreihenfolge von `self._layers`. Aendert
  sich die Trenner-Konfiguration, benutzt ein anderes Ziel dieselbe Schreibschicht weiter — Reste aus
  dem alten Ziel wandern ins neue.
- Fix: Schreibschichten getrennt ablegen, z.B. `.overlay/upper/mN`, und den Spielordner-Mount als einzigen
  auf `.overwrite` zeigen lassen. Namen aus dem Zielpfad ableiten (Hash), nicht aus dem Index.

### H3 — Kein Fallback, wenn bwrap scheitert; die Voraussetzungspruefung prueft das Falsche
- Datei: `anvil/core/overlay_deployer.py:72-105` (`environment_problems`), `anvil/core/overlay_launch.py:80-83`
- Problem a: `Path("/proc/self/uid_map").exists()` ist auf jedem Linux seit 3.8 wahr — der Check
  `overlay.no_userns` kann nie zuschlagen. Nicht geprueft werden: bwrap-Version (`--overlay` gibt es
  erst ab bubblewrap 0.9), Kernelversion (unprivilegiertes overlayfs erst ab 5.11), AppArmor-Sperre
  (`kernel.apparmor_restrict_unprivileged_userns=1`, Ubuntu 24.04+), `user.max_user_namespaces=0`.
- Problem b: Schlaegt bwrap zur Laufzeit fehl, endet der Wrapper bei `exec bwrap ...` mit dessen
  Fehlercode. Es gibt keinen "wenn der Mount nicht klappt, starte trotzdem"-Zweig — anders als bei den
  drei vorgelagerten Pruefungen. Das Spiel startet dann **gar nicht**, und die Meldung steht in Steams
  Log, nicht in `start.log`.
- Auswirkung: Auf einem System, das den Mount nicht kann, meldet Anvil "alles in Ordnung", der Deploy
  gilt als erfolgreich, und der Spielstart bricht ohne verstaendliche Meldung ab.
- Fix: Version/Kernel/AppArmor pruefen; im Wrapper `bwrap ... || exec "$@"` mit Protokolleintrag statt
  bedingungslosem `exec`.

### H4 — Der Overlay greift nur beim Steam-Start des Hauptbinaries
- Datei: `anvil/widgets/game_panel.py:1969-1990` (`_do_launch`), `anvil/mainwindow.py:2598-2622` (`_on_start_game`),
  `anvil/mainwindow.py:2624-2660` (`_on_custom_tool_start`)
- Problem: Der Mount haengt allein an der Steam-Startoption. Nicht ueber Steam laufen: Nicht-Steam-Instanzen
  (GOG/Epic — Cyberpunk gibt es genau so), Zweit-Executables ueber `_launch_via_proton`, und alle eigenen
  Programme (xEdit, LOOT, BodySlide) ueber `_on_custom_tool_start`/`run_with_proton`. Die laufen ueber
  `host_popen` direkt auf dem Spielordner.
- Auswirkung: Fuer diese Wege ist der Spielordner unmodifiziert — und weil `_migrate_from_symlinks` beim
  Umstellen die alten Symlinks entfernt, sind die Mods dort *komplett* weg statt nur teilweise. Werkzeuge
  wie LOOT/xEdit sehen ein leeres `Data/`. Es gibt weder eine Warnung noch eine Sperre der Checkbox fuer
  Nicht-Steam-Instanzen.
- Fix: Mindestens harte Warnung + Deaktivierung der Option ausserhalb von Steam; besser die eigenen
  Startwege durch denselben Wrapper schicken.

### H5 — REDmod-Deploy laeuft ausserhalb des Mounts
- Datei: `anvil/widgets/game_panel.py:2097-2175` (`_run_redmod_deploy_then_launch`)
- Problem: `redMod.exe deploy -root <game_path>` wird per `host_popen` gestartet, also ohne bwrap. Die
  REDmods liegen aber nur in `.overlay/stage/main/mods/` — im echten `game_path/mods/` steht nichts mehr.
- Auswirkung: Fuer das Hauptzielspiel des Features (Cyberpunk) deployt REDmod ins Leere; gleichzeitig
  schreibt es sein Ergebnis (`r6/cache/modded/...`) und `_shim_redmod_scripts()` verschiebt Ordner —
  beides direkt im Spielordner, den das Feature ausdruecklich unberuehrt lassen will.
- Fix: REDmod-Lauf ebenfalls durch den Wrapper schicken oder den Overlay fuer REDmod-Spiele sperren.

### H6 — Purge zieht die Schicht unter dem laufenden Spiel weg
- Datei: `anvil/mainwindow.py:2291-2317` (`_do_redeploy`), `anvil/mainwindow.py:7028-7031` (`closeEvent`),
  `anvil/widgets/game_panel.py:1398-1437` (`silent_purge`)
- Problem: Die Schutzpruefung aus 8499028 sitzt nur in `_unlock_ui`. `_do_redeploy` (500 ms nach jeder
  Aenderung an der Modliste) und `closeEvent` purgen ohne jede Pruefung. Beim Overlay startet das Spiel
  aber ueber Steam — Anvil setzt `_game_running` nur beim eigenen Startknopf, der Prozess-Watcher wird
  ebenfalls nur dort gestartet. Anvil weiss also im Normalfall nicht, dass das Spiel laeuft.
- Auswirkung: `force_rmtree(stage_root)` loescht eine Lower-Schicht, die gerade gemountet ist. Das
  Verhalten von overlayfs bei veraenderten Lower-Layern ist laut Kernel-Doku undefiniert — Absturz oder
  Datenmuell im laufenden Spiel.
- Fix: `silent_purge`/`_do_redeploy` gegen `is_game_running()` absichern und beim Overlay zusaetzlich
  pruefen, ob der Mount noch benutzt wird.

### H7 — Die Steam-Startoption wird nie zurueckgenommen
- Datei: `anvil/widgets/settings_dialog.py:1334-1367`, `anvil/core/overlay_deployer.py:355-381` (`purge`)
- Problem: Es gibt nur "eintragen". `purge()` entfernt weder `mount.conf` noch den Wrapper; das
  Abschalten der Checkbox entfernt gar nichts.
- Auswirkung zwei Varianten:
  1. Wrapper bleibt liegen, Overlay aus, Symlink-Weg aktiv: der Wrapper mountet beim naechsten Steam-Start
     zusaetzlich die eingefrorene alte Schicht ueber den frisch symlinkten Spielordner.
  2. Instanz/`.overlay` geloescht: Steam ruft einen nicht existierenden Pfad auf — das Spiel startet
     ueberhaupt nicht mehr, ohne dass Anvil beteiligt ist.
- Fix: Gegenstueck "Startoption entfernen" (mit Backup-Rueckspielung) und automatisches Aufraeumen beim
  Abschalten.

### H8 — Einstellungen schalten ein aktives Overlay stillschweigend ab
- Datei: `anvil/widgets/settings_dialog.py:1391-1408` (`_check_overlay_requirements`), `1963-1966` (`accept`)
- Problem: Bei irgendeinem Umgebungsproblem wird die Checkbox auf `False` gesetzt und gesperrt. `accept()`
  speichert `idata["use_overlay"] = self._cb_use_overlay.isChecked()` bedingungslos.
- Auswirkung: Wer die Einstellungen oeffnet, waehrend bwrap gerade fehlt (oder Anvil als Flatpak laeuft und
  `shutil.which("bwrap")` ins Leere greift), und auf OK klickt, verliert die Einstellung — ohne Hinweis.
  Ausserdem prueft die Funktion `self._idata["game_path"]`, waehrend `accept()` `self._le_game_path.text()`
  speichert; nach einer Pfadaenderung ist die Pruefung veraltet.
- Fix: Nur die Bedienbarkeit sperren, den gespeicherten Wert nicht ueberschreiben.

### H9 — Halbfertiger Zustand: Manifest, mount.conf und Schicht koennen auseinanderlaufen
- Datei: `anvil/core/overlay_deployer.py:244-309` (`deploy`)
- Probleme:
  - Reihenfolge: erst Manifest, dann `mount.conf`, dann Wrapper. Faellt einer der spaeteren Schritte aus,
    meldet `is_deployed()` "deployed", der Startweg ist aber unvollstaendig.
  - Bricht `build()` mit Fehlern ab (Zeile 276) oder findet keine Mods (Zeile 279), bleiben `mount.conf`
    und Wrapper vom **vorherigen** Deploy stehen und zeigen auf eine gerade neu gebaute, unvollstaendige
    Schicht. Der Wrapper prueft nur `[ -d "$d" ]`, nicht ob die Schicht zum Manifest passt — das Spiel
    startet mit halbem Modsatz.
  - `purge()` loescht `mount.conf`/Wrapper ebenfalls nicht.
- Fix: Erst Schicht bauen, dann Wrapper, dann `mount.conf`, zuletzt das Manifest (das Manifest ist das
  Siegel). Bei jedem Fehlschlag `mount.conf` entfernen. Eine Kennung (z.B. Zeitstempel) in beide Dateien
  schreiben und im Wrapper abgleichen.

### H10 — Schreibschicht ignoriert `path_overwrite_directory`
- Datei: `anvil/core/overlay_deployer.py:143-145`, `anvil/widgets/game_panel.py:2979-2995` (kein `overwrite_path`),
  `anvil/widgets/settings_dialog.py:1394-1396`
- Problem: Der Deployer benutzt immer `instance_path/".overwrite"`. Anvil hat aber einen konfigurierbaren
  Overwrite-Ordner (`instance_paths.py:72`, `resolve_instance_paths`), und die Einstellungen pruefen genau
  diesen konfigurierten Pfad auf sein Dateisystem — also einen anderen als den, der tatsaechlich benutzt wird.
- Auswirkung: Nach einer Speicher-Migration schreibt das Spiel in `.overwrite`, waehrend die
  Overwrite-Ansicht woanders hinschaut — die Dateien sind fuer den Nutzer verschwunden. Zusaetzlich prueft
  niemand die overlayfs-Bedingung "workdir auf demselben Dateisystem wie upperdir"; liegt der Overwrite-
  Ordner auf einer anderen Platte, scheitert der Mount mit EXDEV (und damit, siehe H3, der Spielstart).
- Fix: `overwrite_path=paths.overwrite` durchreichen, `work_dir` daneben legen und beide auf gleiches
  Dateisystem pruefen.

### H11 — Alter `.overwrite`-Inhalt ueberdeckt saemtliche Mods
- Datei: `anvil/core/overlay_deployer.py:187-188`, `_write_mount_conf`
- Problem: `.overwrite` wird als Schreibschicht eingehaengt und liegt damit **ueber** allen Mods. Der
  Ordner enthaelt aber typischerweise Reste aus der Symlink-Zeit (genau der Fall, den die Feature-Doku bei
  `final.redscripts.modded` selbst beschreibt: "das Spiel kam nicht bis ins Menue").
- Auswirkung: Eine veraltete Datei aus `.overwrite` schlaegt jede Mod und laesst sich ueber die Modliste
  nicht korrigieren. Fehlersuche praktisch unmoeglich, weil die Datei im Spielordner nicht sichtbar ist.
- Fix: Beim Umstellen auf Overlay auf vorhandenen `.overwrite`-Inhalt hinweisen (Anzahl Dateien) und ein
  Leeren anbieten; in der Diagnose die obersten Ueberdeckungen anzeigen.

---

## MEDIUM

### M1 — Hardlink-Fallback kopiert bei jedem Spielstart den kompletten Modsatz
- Datei: `anvil/core/overlay_staging.py:110-119` (`_place`)
- Liegt `.mods` auf einem anderen Dateisystem als die Instanz (durch die Speicher-Migration ausdruecklich
  moeglich) oder auf exFAT, schlaegt `os.link` fuer **jede** Datei fehl und es wird kopiert. Da der Deploy
  seit 33413b9 bei jedem Spielstart laeuft und `build()` die Schicht vorher komplett loescht, bedeutet das
  bei grossen Sammlungen dutzende bis hunderte GB Schreiblast pro Start. Es gibt keine Warnung, keine
  Platzpruefung und keinen Hinweis in `check_requirements()`.

### M2 — BA2-Archive werden in ein moeglicherweise nicht existierendes Verzeichnis geschrieben
- Datei: `anvil/core/ba2_packer.py:130-140` (`set_output_root`), `394`/`407`, `_run_bsarch` legt nichts an
- `out_ba2 = self._data_path / ...` zeigt beim Overlay auf `.overlay/stage/main/Data`. Hat kein Mod eine
  lose Datei unterhalb von `Data/` gestaged (moeglich, wenn alles gepackt wird), existiert der Ordner nicht
  und BSArch scheitert. Der Deploy gilt dann als fehlgeschlagen und der Spielstart wird abgebrochen.

### M3 — Alte `anvil_*.ba2` im echten Spielordner bleiben liegen
- Datei: `anvil/core/ba2_packer.py:552-566` (`cleanup_ba2s`), `anvil/core/overlay_deployer.py:332-353` (`_migrate_from_symlinks`)
- Nach der Umstellung zeigt `cleanup_ba2s()` in die Schicht. Die im Symlink-Betrieb *real* in
  `game/Data/` erzeugten `anvil_*.ba2` raeumt niemand mehr weg — `_migrate_from_symlinks` entfernt nur
  Symlinks. Sie bleiben im Spielordner und in der INI stehen und ueberlagern (wegen C1 sogar bevorzugt)
  die neuen Archive.

### M4 — BA2-Filter bekommt im Staging den bereits praefixierten Pfad
- Datei: `anvil/core/overlay_staging.py:325` vs. `anvil/core/mod_deployer.py:427-437`
- Der Symlink-Weg prueft `is_archive_loose_path(rel, ...)` **vor** dem `data_path`-Praefix, das Staging
  **danach** (`dest_rel`). Ohne `nest_under_mod_name` faellt das nicht auf, weil `is_archive_loose_path`
  ein fuehrendes `Data/` selbst abschneidet. Mit `nest_under_mod_name=True` steht danach der Modname vorn
  (`Data/<Mod>/SKSE/...`) und der Vergleich mit den `Ba2LoosePaths` schlaegt fehl. Dasselbe gilt nach
  `multi_folder_routes`.
- Folge: Die Datei wird als "wird gepackt" aus der Schicht ausgelassen, der Packer haelt sie umgekehrt fuer
  "bleibt lose" und packt sie nicht — sie verschwindet ersatzlos.

### M5 — Bewusste Verhaltensabweichung ist weder dokumentiert noch geprueft
- Datei: `anvil/core/mod_deployer.py:474-481` vs. `anvil/core/overlay_staging.py:307-331`
- Der Symlink-Deployer ueberschreibt echte Spieldateien nie und meldet sie als `skipped_real_files`; das
  Staging kennt diesen Begriff nicht. `DeployResult.skipped_real_files` bleibt beim Overlay immer leer,
  die Ausgabe in `game_panel.py:1230-1238` laeuft ins Leere. Ob diese Abweichung gewollt ist, steht weder
  in der Feature-Doku noch in ARCHITEKTUR.md.

### M6 — Wrapper-Erzeugung ohne jedes Escaping
- Datei: `anvil/core/overlay_launch.py:29-30`, `91-101` (`write_wrapper`), `104-106` (`launch_option`)
- `CONF="{conf}"` / `LOG="{log}"` werden per `str.format` in doppelte Anfuehrungszeichen gesetzt. Ein
  Instanzname mit `"`, `$`, Backtick oder `\` erzeugt ein kaputtes oder ausfuehrbares Skript
  (`Instanz$(rm -rf ...)` ist konstruierbar, Instanznamen kommen vom Nutzer). `launch_option` klammert den
  Pfad ebenfalls ungeprueft in `"`.
- Dazu passend: `mount.conf` trennt mit `|` und `:` — ein Spiel- oder Zielpfad mit einem dieser Zeichen
  zerlegt die Zeile falsch (`overlay_launch.py:51`, `57`).

### M7 — Zwei gleichzeitige Mounts auf dieselbe Schreibschicht
- Datei: `anvil/core/overlay_deployer.py:311-330`
- Startet der Nutzer das Spiel zweimal (oder zwei Instanzen mit demselben Spiel), mounten zwei bwrap-
  Prozesse ein Overlay mit identischem `upperdir`/`workdir`. Das verbietet overlayfs ausdruecklich; die
  Folge sind Warnungen im Kernel-Log und inkonsistente Sicht. Es gibt keine Sperrdatei.

### M8 — `build()` raeumt mit `ignore_errors=True` auf
- Datei: `anvil/core/overlay_staging.py:256-257`
- Schlaegt das Loeschen der alten Schicht teilweise fehl, faellt das nirgends auf, und Dateien
  abgeschalteter Mods werden weiter ausgeliefert. `purge()` benutzt an derselben Stelle das robustere
  `force_rmtree` — die beiden Wege sollten identisch sein und Fehler melden.

### M9 — Steam-Erkennung greift zu kurz
- Datei: `anvil/core/overlay_launch.py:111-133`
- `localconfig_files` kennt nur `~/.local/share/Steam`; `~/.steam/steam`, `~/.steam/root` und Flatpak-Steam
  (`~/.var/app/com.valvesoftware.Steam/...`) fehlen. `steam_is_running()` per `pgrep` sieht in einer
  Flatpak-Sandbox (Anvil wird laut Projektstand primaer als Flatpak installiert) keine Host-Prozesse und
  meldet immer "laeuft nicht" — dann wird in eine Datei geschrieben, die Steam im Speicher haelt und beim
  Beenden zurueckschreibt. Die Aenderung ist verloren, im schlimmsten Fall inkonsistent.
  Zusaetzlich koennte Flatpak-Steam den Wrapper im Instanzordner gar nicht ausfuehren.

### M10 — Regeln und Konstanten sind dupliziert statt geteilt
- Datei: `anvil/core/overlay_staging.py:24-43` vs. `anvil/core/mod_deployer.py:39-58`
- `SKIP_FILES`, `SKIP_DIRS`, `SKIP_ROOT_EXTENSIONS`, `BA2_KEEP_EXTENSIONS` sind wortgleiche Kopien. Genau
  die Fehlerklasse, die `test_overlay_matches_symlink.py` abfangen soll — der Test prueft aber nur
  Beispiele, keine Mengengleichheit. Aendert jemand eine Liste, faellt das erst im Spiel auf.

### M11 — `ReshadeManager.set_target_root` ist toter Code
- Datei: `anvil/core/reshade_manager.py:50-57`; einzige Instanziierung: `anvil/dialogs/reshade_wizard.py:62`
- `_tune_for_overlay` wird auf den Packer und den Plugins-Writer angewandt, nie auf den ReshadeManager.
  ReShade installiert also weiterhin `dxgi.dll` & Co. direkt in den Spielordner — der Kernanspruch
  "Spielordner bleibt unberuehrt" gilt damit nicht, und die neue Methode hat keinen Aufrufer.

### M12 — Diagnose meldet Falsches
- Datei: `anvil/core/diagnostics.py:179-211`, `anvil/locales/de.json:419`
- Die Anzeige benutzt `label.diag_deploy_summary` = "{total} Links, {broken} defekt, {missing} fehlend" —
  beim Overlay sind es gestagte Dateien, keine Links, und `broken` ist fest 0.
- Ist das Overlay-Manifest defekt, gibt `_overlay_status` `{"manifest": False}` zurueck und verdeckt damit
  einen eventuell vorhandenen Symlink-Deploy, statt weiterzupruefen.

### M13 — Zugriff auf private Attribute ueber Modulgrenzen
- Datei: `anvil/core/overlay_deployer.py:213-215` (`self._stage._skipped = ...`),
  `anvil/widgets/game_panel.py:1105` (`self._deployer._separator_deploy_paths = ...`)
- Fuer `_skipped` gibt es keinen Setter, obwohl direkt daneben `set_ba2_packing_enabled` sauber
  durchgereicht wird. Das zweite ist die Ursache von H1.

---

## LOW

- **L1** `anvil/core/overlay_deployer.py:53-69` — `force_rmtree` setzt alle Unterverzeichnisse dauerhaft auf
  0700, auch wenn `shutil.rmtree` danach scheitert; auf einem Symlink wirft `rmtree`, das wird in `purge()`
  fuer `work_dir` verschluckt (Zeile 370-373), sodass ein Fehlschlag unbemerkt bleibt.
- **L2** `anvil/core/overlay_launch.py:34/39/75` — `exec "$@"` ohne Argumente ist unter bash ein no-op; das
  Skript laeuft danach weiter statt abzubrechen (nur bei Handaufruf relevant).
- **L3** `anvil/core/overlay_launch.py:33` — `start.log` waechst unbegrenzt, es gibt keine Rotation.
- **L4** `anvil/core/overlay_launch.py:80-83` — kein `--die-with-parent`; bricht Steam den Prozessbaum ab,
  koennen Kinder im Namespace haengenbleiben.
- **L5** `anvil/core/overlay_launch.py:43/68` — leere Arrays unter `set -u` sind erst ab bash 4.4 unkritisch.
  Auf diesem System ok, auf alten Distributionen nicht.
- **L6** `anvil/core/overlay_deployer.py:46` — `filesystem_of` dekodiert nur `\040` aus `/proc/mounts`,
  nicht `\011`, `\012`, `\134`.
- **L7** `anvil/core/overlay_deployer.py:296` — der Zaehler `files` im Manifest zaehlt die spaeter gepackten
  BA2 nicht mit; die Diagnose zeigt eine zu kleine Zahl.
- **L8** `anvil/core/overlay_launch.py:204-206` — schlaegt `os.replace` fehl, bleibt `localconfig.vdf.tmp`
  liegen; kein `fsync` vor dem Umbenennen.
- **L9** `anvil/core/overlay_staging.py:111` — die Schicht besteht aus Hardlinks auf die Originaldateien in
  `.mods`. Alles, was Rechte oder Inhalt *in der Schicht* aendert, aendert die Mod selbst. Aktuell tut das
  niemand, sollte aber als Regel irgendwo stehen.
- **L10** `anvil/mainwindow.py:1960-1962` — `set_overlay_enabled` laeuft vor `set_instance_path` und baut den
  Deployer einmal mit den Pfaden der *vorigen* Instanz. Folgenlos, aber irrefuehrend.

---

## Luecken im Vergleichstest (`tests/test_overlay_matches_symlink.py`)

Der Test behauptet: "was der Symlink-Deployer ins Spiel legt, muss der Overlay in seine Schichten legen".
Das prueft er nur eingeschraenkt:

1. **Der Spielordner ist immer leer** (`_welt`, Zeile 31-40). Damit wird die wichtigste Regel des
   Symlink-Deployers — echte Spieldateien nie ueberschreiben (`skipped_real_files`) — nie ausgeloest.
   Genau an dieser Stelle laufen beide Wege auseinander (M5), und genau hier sitzt auch C1.
2. **Die Mount-Reihenfolge wird nirgends geprueft.** Kein Test startet bwrap mit einer Datei, die es in
   Mod *und* Spiel gibt. C1 ist deshalb durch die komplette gruene Suite gelaufen.
3. **LML-/REDmod-Testmods haben kein `meta.ini`.** Der Symlink-Weg verlinkt den ganzen Ordner (inklusive
   `meta.ini`, `fomod/`, Readmes), das Staging filtert diese Dateien (`overlay_staging.py:297`). Jede real
   installierte Mod hat ein `meta.ini` — mit echten Daten waere der Test rot. Die Testdaten umgehen die
   Abweichung.
4. **Keine Datei/Ordner-Kollision zwischen zwei Mods** — der Absturz aus C3 bleibt unentdeckt.
5. **`copy_deploy_paths` (GameCopyDeployPaths) und `mod_index`** werden dem OverlayDeployer gar nicht
   uebergeben (`game_panel.py:2979-2995`) und im Test nie gesetzt. Ob der Overlay fuer Spiele mit
   Kopier-Pfaden richtig liegt, ist offen.
6. **`separator_deploy_paths` werden nur ueber den Konstruktor getestet** (Zeile 208-214), nicht ueber den
   Weg, den die App tatsaechlich nimmt (`set_separator_deploy_paths`). H1 bleibt unentdeckt.
7. **`needs_ba2_packing` wird nie mit `nest_under_mod_name` kombiniert** — M4 bleibt unentdeckt.
8. **`check_requirements` wird komplett weggepatcht** (Fixture `ohne_umgebungspruefung`); zu
   `environment_problems` selbst gibt es keinen Test.
9. **Verglichen werden nur Pfadmengen, keine Inhalte** (Ausnahme: ein Zwei-Mod-Prioritaetstest). Gleiche
   Pfade mit falschem Inhalt faendet der Test nicht.
10. **Symlinks innerhalb eines Mods**: `Path.rglob` steigt nicht in verlinkte Unterordner ab — beide Wege
    verhalten sich gleich, aber ungeprueft und undokumentiert. Ein Mod, dessen Unterordner ein Symlink ist,
    wird auf beiden Wegen still ausgelassen.

---

## Was in Ordnung ist

- Alle zwoelf neuen `tr()`-Schluessel liegen in allen sieben Locale-Dateien (`de, en, es, fr, it, pt, ru`),
  Platzhalter (`{fs}`, `{path}`, `{count}`) passen zusammen.
- Das erzeugte Wrapper-Skript ist syntaktisch gueltiges bash (`bash -n`), `IFS` wird korrekt nur pro
  `read`-Aufruf gesetzt, leere Arrays sind durch die `schichten -ge 2`- und `MOUNTS -eq 0`-Pruefungen
  abgesichert.
- `_migrate_from_symlinks` laeuft nur bei vorhandenem Altmanifest — der Spielordner wird nicht bei jedem
  Start durchsucht (mit Test abgesichert).
- Der Umbau in `plugins_txt_writer.scan_plugins` ist sauber: mehrere Wurzeln, Fehler pro Wurzel werden
  uebersprungen statt den ganzen Scan abzubrechen, `os.scandir` weiterhin im `with`.
- Keine offenen Dateihandles gefunden: alle Lese-/Schreibzugriffe laufen ueber `read_text`/`write_text`
  bzw. `with open(...)`; `subprocess.run` mit `capture_output`.
- `force_rmtree` loest den 000-Fall des Kernel-Arbeitsverzeichnisses korrekt auf (topdown-Walk mit chmod
  vor dem Abstieg), mit Test.

---

## Ergebnis

**NEEDS FIXES.**

3 CRITICAL (davon 3 experimentell belegt), 11 HIGH, 13 MEDIUM, 10 LOW.

C1 allein bedeutet, dass das Feature seinen Zweck nicht erfuellt: Mods, die Spieldateien ersetzen, kommen
nicht an — und das abgehakte Akzeptanzkriterium "Prioritaet: hoeher priorisierte Mod gewinnt bei gleichem
Pfad" ist fuer den Fall Mod-gegen-Spieldatei nicht erfuellt. C2 beschaedigt fremde Steam-Konfiguration.
C3 bricht den Spielstart mit einem Traceback ab.

Nicht committen, bevor mindestens C1-C3 und H1-H3 behoben und mit Tests abgesichert sind, die den
tatsaechlichen bwrap-Lauf und eine im Spielordner bereits vorhandene Datei einschliessen.
