# Overlay-Deploy — Umbau des Deployments auf overlayfs

Stand: 04.08.2026
Branch: `feat/overlay-deploy` (Worktree `/home/mob/Projekte/anvil-overlay`)
Basis: `e82a5c3`

---

## Warum

Anvil legt heute Symlinks in den Spielordner und raeumt sie beim Purge wieder weg.
Das funktioniert, hat aber drei Nachteile:

- Der Spielordner wird beschrieben. Nach einem Absturz bleiben Links liegen.
- Echte Spieldateien duerfen nie ueberschrieben werden (`mod_deployer.py:476`).
  Mods, die eine Originaldatei ersetzen wollen, kommen nur halb an — ohne dass
  es in der Oberflaeche auffaellt.
- Deploy und Purge kosten bei 342 aktiven Mods spuerbar Zeit.

Mit overlayfs sieht das Spiel eine gemischte Sicht aus Spielordner und Mods,
ohne dass am Spielordner etwas geaendert wird.

## Was gemessen wurde

Kernel-overlayfs, unprivilegiert im User-Namespace, gegen die echte
Cyberpunk-Installation:

```
lowerdir = RED4ext : TweakXL : Spielordner

merged/                      → archive, bin, engine, ... + red4ext/ aus der Mod
merged/bin/x64/Cyberpunk2077.exe   → 59945608 Bytes, das echte Binary
```

Mit Testdateien geprueft:

- Bei gleichem Pfad gewinnt die Mod ueber die Spieldatei — die Prioritaets-
  reihenfolge der lowerdirs bildet `modlist.txt` ab
- Zur Laufzeit geschriebene Dateien landen in der oberen Schicht, nicht im
  Spielordner
- Nach dem Namespace ist der Mountpoint leer, der Spielordner unveraendert

Voraussetzungen auf dem Zielsystem:

- unprivilegierte User-Namespaces (hier: aktiv)
- Kernel-Modul `overlay` (hier: vorhanden, wird bei Bedarf geladen)
- obere Schicht **nicht** auf tmpfs — dort scheitert der Mount. ext4 und btrfs
  laufen.

`fuse-overlayfs` wird **nicht** gebraucht. Der Kernel kann es selbst.

## Zielbild

```
Anvil startet das Spiel
  └─ Steam startet den Wrapper   (Startoption: anvil-overlay %command%)
       └─ Wrapper oeffnet Namespace und mountet:
             lowerdir   = mod_N : ... : mod_1 : Spielordner
             upperdir   = .overwrite
             Mountpoint = der Spielordner
       └─ exec Spiel
  Spiel endet → Namespace endet → Mount weg → Spielordner wie vorher
```

Der Mount lebt im Namespace des Wrapper-Prozesses. Damit entfaellt das
Aufraeumen komplett: kein Purge, kein Prozess-Watcher, keine Leichen. Das
loest nebenbei den Fehler, der zu `8499028` gefuehrt hat.

## Bausteine

### `anvil/core/overlay_staging.py` (~450 Zeilen)

Der Kernel nimmt keine 342 lowerdirs in einem Mount-Aufruf. Die Mods werden
vorher per Hardlink zu wenigen Schichten zusammengefuehrt. Hier faellt
ausserdem die Filterung an, die heute im Deployer steckt:

- `_SKIP_FILES` (`meta.ini`, `codes.txt`, `fomod_choices.json`)
- `_SKIP_DIRS` (`fomod/`)
- Bilder und Dokumentation im Mod-Wurzelverzeichnis
- `root/`-Praefix (RootBuilder-Muster)
- `data_path`, Multi-Folder-Routen, Separator-Ziele

Ohne diesen Schritt landet `meta.ini` im Spielordner — im Test passiert.

### `anvil/core/overlay_deployer.py` (~250 Zeilen)

Bedient die vorhandene Schnittstelle aus `game_panel.py:70`
(`deploy` / `purge` / `is_deployed`) und haengt sich ueber die Fabrik
`_create_deployer` (`game_panel.py:2904`) ein — dort, wo Ghost Recon schon
heute seinen eigenen Deployer bekommt.

### `anvil/core/overlay_launch.py` + Wrapper (~300 Zeilen)

Erzeugt das Wrapper-Skript, traegt die Steam-Startoption ein, prueft die
Voraussetzungen und meldet verstaendlich, wenn eine fehlt.

## Betroffene Dateien

| Datei | Zeilen heute | Was passiert |
|---|---|---|
| `widgets/game_panel.py` | 3616 | Fabrik erweitern, `silent_deploy` (153 Zeilen) verzweigt |
| `mainwindow.py` | 8326 | Aufraeum-Pfad beim Start, ca. 40 Zeilen |
| `core/ba2_packer.py` | 675 | schreibt `anvil_*.ba2` nach `Data/` → in die Staging-Schicht |
| `core/plugins_txt_writer.py` | 471 | 8 Stellen mit `game_path` |
| `core/diagnostics.py` | 319 | liest das Deploy-Manifest |
| `core/reshade_manager.py` | — | schreibt in den Spielordner |
| Data-Reiter | — | "echt vs. virtuell" entfaellt, im Overlay ist alles echt |
| 7 Locale-Dateien | — | neue Meldungen |

`mod_deployer.py` bleibt als Rueckfallebene bestehen — fuer NTFS, fuer Systeme
ohne User-Namespaces, fuer die Flatpak-Sandbox. Zwei Wege werden dauerhaft
gepflegt, nicht einer ersetzt.

Ghost Recon bleibt unberuehrt (eigener Deployer).

## Etappen

| # | Was | Stand |
|---|---|---|
| 0 | Prototyp: reicht pressure-vessel die Overlay-Sicht durch? | **erledigt — ja** |
| 1 | Staging und Mount-Kern, ohne GUI, mit Tests | **erledigt** |
| 2 | Wrapper, Startoption, Voraussetzungspruefung | **erledigt** |
| 3 | Einhaengen ueber die Fabrik, Umschalter pro Instanz | **erledigt** |
| 4 | Die angehaengten Subsysteme nachziehen | **erledigt** |
| 5 | Locales (7 Sprachen), Umschalter in den Einstellungen | **erledigt** |
| 6 | Migrationspfad, echter Spieldurchlauf | offen |

Jede Etappe muss fuer sich lauffaehig sein. Vorgabe bleibt der Symlink-Weg,
bis der Overlay wirklich steht.

## Groesse

```
Neuer Code:        ~1000 Zeilen (3 Module)
Geaenderter Code:   ~600 Zeilen (7 Dateien)
Tests:              ~600 Zeilen
Locales:              7 Dateien
                   ─────────────
Angefasst:        ~2200 Zeilen ueber ~15 Dateien
```

Zeit: 4–6 Wochen nebenher, 2–3 Wochen konzentriert. Der heutige Deployer hat
830 Zeilen — der Umbau ist etwa dreimal so gross wie das, was er ersetzt.

## Was wegfaellt

- Deploy-Manifest, `remove_orphaned_links()`, Purge-Pfad
- Prozess-Watcher fuers Aufraeumen
- `skipped_real_files` und die Ueberschreib-Frage
- Warten beim Profilwechsel

## Risiken

1. **pressure-vessel.** Steams Container baut seine Mounts selbst. Ob er die
   Overlay-Sicht durchreicht, klaert nur Etappe 0. Faellt sie negativ aus,
   bliebe nur, Proton selbst zu starten — damit gingen Steam-Overlay,
   Spielzeit und Controller-Profile verloren. Das waere ein schlechterer
   Handel.
2. **Halbfertig.** Der Umbau trifft das Herz der App. Bleibt er liegen, gibt
   es zwei kaputte Wege statt einem funktionierenden.
3. **Staging-Aufwand.** Die Hardlink-Zusammenfuehrung ist der Teil, den man
   unterschaetzt, und sie kostet bei jedem Start Zeit.

## Akzeptanzkriterien

- [ ] Cyberpunk startet mit Overlay, CET und RED4ext laufen
- [ ] Spielordner nach dem Spiel byte-identisch zu vorher
- [ ] Prioritaet: hoeher priorisierte Mod gewinnt bei gleichem Pfad
- [ ] Zur Laufzeit geschriebene Dateien landen in `.overwrite`
- [ ] `meta.ini` und `fomod/` tauchen im Spiel nicht auf
- [ ] Absturz des Spiels hinterlaesst keinen Mount
- [ ] Symlink-Weg weiterhin waehlbar und unveraendert funktionsfaehig
- [ ] Voraussetzungen werden geprueft und verstaendlich gemeldet
- [ ] Tests gruen


---

## Stand 04.08.2026 — was gebaut ist

### Etappe 0, Prototyp

Steam ruft den Wrapper **vor** dem SteamLinuxRuntime-Einstiegspunkt auf:

```
steam-launch-wrapper -- reaper SteamLaunch AppId=1091500
  -- SteamLinuxRuntime_4/_v2-entry-point --verb=waitforexitandrun
  -- Proton - Experimental/proton waitforexitandrun REDprelauncher.exe --launcher-skip
```

Pressure-vessel startet also im Namespace des Wrappers und reicht die Sicht
durch.  Beweis aus dem redscript-Log des Spiels:

```
Compiling files in S:\common\Cyberpunk 2077\r6\scripts:
  RedData\RedData.Json.reds
  RedFileSystem\RedFileSystem.reds
Compilation complete
```

Beide Dateien liegen ausschliesslich in den Mod-Ordnern.  Die erzeugten
Cache- und Log-Dateien landeten in der oberen Schicht, im Spielordner blieb
`r6/cache/final.redscripts` unveraendert vom 4. Mai.

**Nicht geklaert:** das Spiel kam nicht bis ins Menue.  Naheliegend ist der
alte `final.redscripts.modded` aus dem letzten Symlink-Deploy, der nicht zu
einer Schicht aus nur zehn Frameworks passt.  Muss mit vollem Modsatz
wiederholt werden.

### Massstab

Gegen die echte Cyberpunk-Sammlung, lesend:

```
aktive Mods:   352
Hardlinks:    1458      Kopien: 0      Fehler: 0
Dauer:        0,23 s
```

Die ARG_MAX-Sorge ist damit erledigt: es sind zwei lowerdirs, nicht 352.

### Abweichungen vom urspruenglichen Entwurf

- **bubblewrap statt `unshare`.** `unshare -r` landet als root im Namespace,
  und Steam verweigert den Start als root.  `unshare --map-user=1000` behaelt
  zwar die Kennung, verliert aber beim internen setuid die Rechte, und der
  Mount scheitert.  `bwrap` macht dieses setuid nicht und ist damit der
  einzige gangbare Weg.  Neue Abhaengigkeit, dafuer auf Linux-Desktops
  praktisch ueberall vorhanden.
- **Eine Schicht statt vieler.** Alle Mods werden per Hardlink zu einer
  Schicht zusammengefuehrt.  Einfacher als die geplante Staffelung und
  schnell genug.
- **`fuse-overlayfs` wird nicht gebraucht** -- der Kernel kann es selbst.

### Stolpersteine, die beim Bauen auffielen

- Der Wrapper zaehlte anfangs die Array-Elemente statt der Schichten; jede
  Schicht belegt zwei (`--overlay-src` plus Pfad).  Damit haette auch die
  Mindestpruefung nie gegriffen.
- overlayfs legt im Arbeitsverzeichnis ein `work/`-Unterverzeichnis mit den
  Rechten 000 an.  Ein normales Loeschen scheitert daran -- `force_rmtree()`
  sperrt vorher auf.
- Ohne Metadaten-Filter landet `meta.ini` im Spielordner.

### Offen

- **Die Steam-Startoption wird noch nicht aus der Oberflaeche gesetzt.**
  `overlay_launch.set_launch_options()` kann es, aber kein Knopf ruft es auf.
  Ohne den Eintrag laeuft das Spiel weiter ohne Mods -- der Wrapper wird gar
  nicht erst aufgerufen.
- Migrationspfad fuer Instanzen, die noch Symlinks ausgerollt haben
- Voller Spieldurchlauf mit allen 352 Mods bis ins Menue
- Separator-Zielpfade (`separator_deploy_paths`) brauchen eigene Mounts
