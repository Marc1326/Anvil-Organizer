# Feature-Spec: REDmod-Deploy fuer Cyberpunk 2077

Datum: 2026-04-02
Agent: 4 (Konsolidierung aus Agent 1-3 + Marc-Korrekturen + Mod-Liste verifiziert 2026-04-02)

---

## Zusammenfassung

Anvil Organizer soll REDmod-Mods fuer Cyberpunk 2077 korrekt deployen UND kompilieren.
Aktuell werden 7 von 10 REDmod-Mods zwar korrekt platziert (Pattern B), aber `redMod.exe deploy`
wird NIEMALS aufgerufen -- daher funktioniert KEIN einziger REDmod-Mod im Spiel.
3 weitere Mods landen sogar im falschen Verzeichnis (Pattern A und C).

Das Feature besteht aus zwei Teilen:
1. **Symlink-Routing fixen** -- Pattern A und C korrekt nach `game_root/mods/<name>/` deployen
2. **REDmod-Kompilierung** -- `proton run redMod.exe deploy` vor dem Spielstart ausfuehren

---

## Ist-Zustand

### 10 REDmod-Mods installiert, 0 funktionieren

Es gibt 10 REDmod-Mods in der Cyberpunk-Instanz mit 3 verschiedenen Packaging-Patterns:

**Pattern A -- info.json im Mod-ROOT (1 Mod):**
- "Material and Texture Override (REDmod)": `info.json` + `archives/` direkt im Mod-Root
- Aktueller Deploy: `game_root/info.json` -- **FALSCH** (mods/ Prefix fehlt)
- Problem: Der Deployer iteriert alle Dateien und legt sie relativ zum game_root ab.
  Da `GameDataPath = ""` und kein `mods/` Prefix in der Ordnerstruktur vorhanden ist,
  landen `info.json` und `archives/` direkt im game_root.

**Pattern B -- mods/<name>/ Prefix bereits vorhanden (7 Mods):**
- "NIGHT CITY ALIVE High Gang Density 2.2": `mods/NIGHT CITY ALIVE/info.json`
- "Kwek's Sartorial Omnibus Shop - REDMod Version": `mods/kwekSartorialOmnibusShopForVirtualAtelier/info.json`
- "Kwek's Seawright Optometry Shop - REDMod": `mods/kwekSeawrightOptometryForVirtualAtelier/info.json`
- "Kwek's Swimwear Oriented Shop - REDMod Version": `mods/kwekSOSForVirtualAtelier/info.json`
- "-4x- NSFW Vending Machines Androids": `mods/NSFW_Vending_Machines_Androids/info.json`
- "-4x- NSFW Posters Androids": `mods/4x_NSFW_Posters_Androids/info.json`
- "NSFW Erotic Magazines (Lore Friendly)": `mods/00Erotic_Magazines/info.json`
- Aktueller Deploy: `game_root/mods/<name>/info.json` -- **KORREKT platziert**
- ABER: redMod.exe wird nie aufgerufen, daher trotzdem nicht funktional
- Einige sind MIXED Mods (z.B. Kwek's hat auch `r6/scripts/...` -- Einzel-Symlinks funktionieren fuer den Non-REDmod-Anteil)

**Pattern C -- Subfolder OHNE mods/ Prefix (2 Mods):**
- "NCPDPPE V2.7 ARCADE": `NCPDPPE/info.json` -- Deploy: `game_root/NCPDPPE/info.json` -- **FALSCH**
- "VEHICLE REPAIR COST": `VEHICLE REPAIR COST/info.json` -- Deploy: `game_root/VEHICLE REPAIR COST/info.json` -- **FALSCH**
- Problem: Der Subfolder enthaelt `info.json`, aber ohne `mods/` Prefix. Der Deployer
  erkennt den Subfolder nicht als REDmod-Ordner und legt ihn als regulaeren Unterordner an.

### redMod.exe wird NIEMALS aufgerufen

Selbst die 7 korrekt platzierten Mods (Pattern B) werden nicht kompiliert, weil
`redMod.exe deploy` an keiner Stelle im Code aufgerufen wird. Der Pfad
`_REDMOD_BINARY = "tools/redmod/bin/redMod.exe"` ist zwar in `game_cyberpunk2077.py`
definiert (Zeile 103), wird aber nirgends verwendet.

### game_root/mods/ ist quasi leer

```
game_root/mods/.stub  (0 Bytes)
```

Aber `game_root/r6/cache/modded/` existiert mit `mods.json`, `final.redscripts`,
`tweakdb.bin` -- redMod.exe wurde frueher offenbar manuell ausgefuehrt.

---

## Soll-Zustand

### Teil 1: Korrektes Symlink-Routing fuer ALLE REDmod-Mods

Alle 3 Packaging-Patterns muessen erkannt und korrekt nach `game_root/mods/<name>/` deployed werden:

- **Pattern A** (info.json im Root): Ordner-Symlink `game_root/mods/<modname>/ -> .mods/<modname>/`
- **Pattern B** (mods/<name>/ Prefix): Bereits korrekt -- KEINE Aenderung noetig
- **Pattern C** (Subfolder mit info.json ohne mods/): Ordner-Symlink `game_root/mods/<subfolder>/ -> .mods/<modname>/<subfolder>/`

Die Erkennung erfolgt analog zum bestehenden LML-Pattern (install.xml -> Ordner-Symlink),
aber mit `info.json` als Erkennungsmerkmal.

### Teil 2: Automatischer REDmod-Deploy vor Spielstart

Beim Klick auf "Start" (Play-Button):
1. Pruefen ob aktive REDmod-Mods vorhanden sind
2. Pruefen ob `redMod.exe` existiert und Proton verfuegbar ist
3. Fortschritts-Overlay anzeigen (modern, kein Terminal)
4. `proton run tools/redmod/bin/redMod.exe deploy` ausfuehren (async in Worker-Thread)
5. Bei Erfolg: Spiel normal starten
6. Bei Fehler: Dialog mit Option "Trotzdem starten?"
7. Menue-Eintraege "skip REDmod deploy" und "Manually deploy REDmod" aktivieren

---

## Betroffene Dateien

| Datei | Aenderungstyp | Beschreibung |
|-------|---------------|-------------|
| `anvil/core/mod_deployer.py` | Erweitert | REDmod-Erkennung (Pattern A + C): Ordner-Symlinks fuer Mods mit `info.json` nach `mods/` |
| `anvil/widgets/game_panel.py` | Erweitert | `_needs_redmod_deploy()`, `_run_redmod_deploy_then_launch()`, `_on_redmod_finished()`, `_do_launch()` Refactoring, Overlay-Widget, Menu-Aktivierung |
| `anvil/plugins/games/game_cyberpunk2077.py` | Erweitert | `NeedsRedmodDeploy = True` Attribut |
| `anvil/plugins/base_game.py` | Erweitert | `NeedsRedmodDeploy = False` Default-Attribut |
| `anvil/locales/*.json` (6 Dateien) | Erweitert | Neue tr()-Keys fuer Fortschritts-Overlay und Fehlerdialoge |
| `anvil/mainwindow.py` | Minimal | ggf. Timer-Stop fuer Steam-Launches |

---

## Architektur

### Gesamt-Flow (zeitliche Abfolge)

```
[1] Instanzwechsel / Mod-Toggle / Profil-Wechsel
    -> silent_deploy() [SOFORT, synchron, <1s]
       -> ModDeployer.deploy()
          -> Fuer jede Mod:
             A) info.json im Root?          -> Ordner-Symlink nach mods/<modname>/     [NEU]
             B) mods/<name>/info.json?      -> Einzel-Symlinks (bestehendes Verhalten) [OK]
             C) <subfolder>/info.json?      -> Ordner-Symlink nach mods/<subfolder>/   [NEU]
             D) install.xml im Root?        -> LML Ordner-Symlink                      [BESTEHEND]
             E) Sonst                       -> Einzel-Symlinks                         [BESTEHEND]
       -> BA2-Packing, plugins.txt, Proton-Shims, DLL-Overrides [BESTEHEND]

[2] User klickt "Start"
    -> _on_start_clicked()
       -> _needs_redmod_deploy()?
       |  +-- plugin hat NeedsRedmodDeploy == True?      -> nein -> skip
       |  +-- Mindestens 1 aktiver Mod mit info.json?    -> nein -> skip
       |  +-- redMod.exe existiert im Game-Dir?          -> nein -> warnen, skip
       |  +-- Proton verfuegbar (findProtonRun)?         -> nein -> warnen, skip
       |
       +-- JA -> _run_redmod_deploy_then_launch(plugin, binary, is_steam)
       |   +-- Overlay anzeigen (pulsierend, "REDmod kompiliert...")
       |   +-- Start-Button + Redeploy-Timer deaktivieren
       |   +-- Worker-Thread:
       |   |     proton_env = _build_proton_env(plugin)
       |   |     subprocess.Popen(
       |   |       [proton_script, "run", "tools/redmod/bin/redMod.exe", "deploy"],
       |   |       cwd=game_path, env=proton_env,
       |   |       stdout=PIPE, stderr=PIPE
       |   |     )
       |   |     proc.communicate(timeout=300)
       |   +-- Thread fertig -> Signal -> Main-Thread:
       |       +-- _on_redmod_finished(exit_code, stdout, stderr)
       |           +-- Overlay entfernen
       |           +-- Start-Button aktivieren
       |           +-- exit_code == 0?
       |           |   +-- JA -> _do_launch(plugin, binary, is_steam)
       |           +-- exit_code != 0?
       |               +-- Dialog: "REDmod-Deploy fehlgeschlagen. Trotzdem starten?"
       |                   +-- JA -> _do_launch(plugin, binary, is_steam)
       |                   +-- NEIN -> Abbruch
       |
       +-- NEIN -> _do_launch(plugin, binary, is_steam)
           +-- is_steam + main_binary  -> _launch_via_steam()
           +-- is_steam + !main        -> _launch_via_proton()
           +-- !is_steam               -> start_requested.emit()

[3] Game beendet
    -> _unlock_ui()
    (Kein auto-purge — Mods bleiben deployed)
```

### REDmod-Erkennung im Deployer (mod_deployer.py)

Die Erkennung erfolgt IN der bestehenden Deploy-Schleife, NACH dem LML-Check und VOR der
Einzeldatei-Iteration. Neuer Parameter `redmod_path: str = ""` im Konstruktor (analog zu `lml_path`).

```
Fuer jeden aktivierten Mod:
  1. Ist Separator? -> skip
  2. Hat install.xml? -> LML Ordner-Symlink (BESTEHEND)
  3. [NEU] REDmod-Erkennung:
     a) info.json im Mod-Root? (Pattern A)
        -> Ordner-Symlink: game_path/mods/<modname>/ -> mod_dir
        -> continue (keine Einzel-Symlinks)
     b) Subfolder mit info.json, OHNE mods/ Prefix? (Pattern C)
        -> Ordner-Symlink: game_path/mods/<subfolder>/ -> mod_dir/<subfolder>/
        -> Restliche Dateien (ausserhalb des Subfolders) als Einzel-Symlinks
     c) mods/<name>/info.json vorhanden? (Pattern B)
        -> Normales Verhalten (Einzel-Symlinks), da mods/ Prefix schon korrekt ist
  4. Einzel-Symlinks (BESTEHEND)
```

**Pattern A Erkennung:**
```python
if self._redmod_path and (mod_dir / "info.json").is_file():
    # info.json im Root = gesamter Mod ist ein REDmod-Mod
    redmod_target = self._game_path / "mods" / mod_name
    redmod_target.symlink_to(mod_dir)
    continue
```

**Pattern C Erkennung:**
```python
if self._redmod_path:
    for child in mod_dir.iterdir():
        if child.is_dir() and (child / "info.json").is_file():
            first_part = child.name
            # Pruefen ob NICHT schon unter mods/ (Pattern B)
            if not (mod_dir / "mods").is_dir() or child.parent.name != "mods":
                redmod_target = self._game_path / "mods" / first_part
                redmod_target.symlink_to(child)
```

**Pattern B:** Keine Aenderung noetig. Der bestehende Einzel-Symlink-Deploy erkennt
`mods/<name>/info.json` korrekt und deployed es als `game_root/mods/<name>/info.json`.

### Proton-Environment (wiederverwendbar)

Die Proton-Env-Logik aus `_launch_via_proton()` (Zeile 1127-1161) wird in eine
separate Helper-Methode `_build_proton_env(plugin)` extrahiert, die sowohl vom
REDmod-Deploy als auch vom Proton-Launch wiederverwendet werden kann.

REDmod braucht Proton (NICHT Wine direkt wie BA2Packer), weil:
- redMod.exe benoetigt das korrekte Wine-Prefix mit spielspezifischen DLLs
- Das Proton-Script setzt interne Env-Vars die plain Wine nicht kennt
- findProtonRun() liefert das passende Proton-Script + compat_data

### Worker-Thread (kein UI-Freeze)

`redMod.exe deploy` dauert 10-60+ Sekunden. Die UI darf nicht einfrieren.
Ansatz: `threading.Thread` (wie `_start_process_watcher()` bereits verwendet)
mit `QMetaObject.invokeMethod()` fuer den Callback in den Main-Thread.

Kein QProcess, weil das Proton-Environment mit QProcessEnvironment umstaendlich ist
und threading.Thread bereits im Projekt etabliert ist.

### Manifest-Tracking

REDmod-Ordner-Symlinks (Pattern A + C) werden im bestehenden `.deploy_manifest.json`
mit `"type": "dir_symlink"` getrackt (gleiches Format wie LML). Der bestehende
Purge-Code (mod_deployer.py:486-492) entfernt dir_symlinks bereits automatisch.

Die von redMod.exe erzeugten Cache-Dateien unter `r6/cache/modded/` werden NICHT
im Manifest getrackt und NICHT beim Purge geloescht. redMod.exe verwaltet sie selbst.

---

## Aufwand-Schaetzung

| Bereich | Aufwand | LOC geschaetzt | Beschreibung |
|---------|---------|---------------|-------------|
| REDmod-Erkennung (mod_deployer.py) | Klein | ~40-60 | Pattern A + C Erkennung + Ordner-Symlinks, analog zu LML-Pattern |
| Cyberpunk-Plugin Attribut | Klein | ~5 | `NeedsRedmodDeploy = True` + `redmod_path = "mods"` |
| base_game.py Default | Klein | ~2 | `NeedsRedmodDeploy = False` Default |
| _build_proton_env() Extraktion | Klein | ~30 | Refactoring aus _launch_via_proton() |
| _needs_redmod_deploy() | Klein | ~20 | Pre-Flight-Checks |
| _run_redmod_deploy_then_launch() | Mittel | ~50-70 | Worker-Thread + subprocess.Popen |
| _on_redmod_finished() | Klein | ~30 | Callback + Fehlerbehandlung |
| _do_launch() Refactoring | Klein | ~25 | Extrahiert aus _on_start_clicked() |
| Fortschritts-Overlay | Mittel | ~40-60 | QWidget mit pulsierender QProgressBar + Label + Abbrechen |
| Menu-Aktivierung | Klein | ~20 | skip_redmod Toggle + Manually deploy verbinden |
| Locale-Keys (6 Sprachen) | Klein | ~30 | Neue Keys fuer Overlay, Fehler, Erfolg |
| ModDeployer Konstruktor-Erweiterung | Klein | ~10 | Neuer Parameter `redmod_path` |
| GamePanel Deployer-Instanziierung | Klein | ~5 | `redmod_path` aus Plugin lesen und uebergeben |

## Gesamt-Aufwand

**Mittel bis Gross** -- ca. 300-400 LOC Aenderungen verteilt auf 7+ Dateien.
Die Kernlogik (Erkennung + Proton-Aufruf) ist einfach, die Komplexitaet liegt in der
asynchronen Ausfuehrung, der UI-Integration und der Fehlerbehandlung.

Geschaetzte Implementierungszeit: 3-5 Stunden (erfahrener Entwickler).

---

## Implementierungsreihenfolge

### Phase 1: Symlink-Routing fixen (kann sofort getestet werden)

1. `base_game.py`: `NeedsRedmodDeploy = False`, `GameRedmodPath = ""` Defaults
2. `game_cyberpunk2077.py`: `NeedsRedmodDeploy = True`, `GameRedmodPath = "mods"` setzen
3. `mod_deployer.py`: Neuer Parameter `redmod_path`, REDmod-Erkennung (Pattern A + C)
4. `game_panel.py`: `redmod_path` aus Plugin lesen und an ModDeployer uebergeben
5. **Test:** `restart.sh`, Instanz laden, pruefen ob Symlinks in `game_root/mods/` korrekt sind

### Phase 2: REDmod-Kompilierung

6. `game_panel.py`: `_build_proton_env()` aus `_launch_via_proton()` extrahieren
7. `game_panel.py`: `_needs_redmod_deploy()` implementieren
8. `game_panel.py`: `_do_launch()` aus `_on_start_clicked()` extrahieren
9. `game_panel.py`: `_run_redmod_deploy_then_launch()` + Worker-Thread
10. `game_panel.py`: `_on_redmod_finished()` Callback
11. **Test:** Start-Button klicken, Overlay pruefen, redMod.exe Ausfuehrung pruefen

### Phase 3: UI + Polish

12. `game_panel.py`: Fortschritts-Overlay (QWidget, pulsierend)
13. `game_panel.py`: Menu-Eintraege aktivieren ("skip REDmod", "Manually deploy")
14. `locales/*.json`: Neue tr()-Keys in allen 6 Sprachen
15. `game_panel.py`: Redeploy-Timer in _on_start_clicked() stoppen (Race Condition Fix)
16. **Test:** Kompletter End-to-End-Test

---

## UI-Design

### Fortschritts-Overlay (waehrend REDmod-Deploy)

Kein separater Dialog, sondern ein Overlay-Widget ueber dem GamePanel (analog zum
bestehenden `_lock_overlay` in mainwindow.py):

```
+--------------------------------------------------+
|                                                  |
|     REDmod Deploy                                |
|                                                  |
|     [=============================>    ]         |
|     Kompiliere 10 Mods...                        |
|                                                  |
|                            [Abbrechen]           |
|                                                  |
+--------------------------------------------------+
```

- QProgressBar im "busy" Modus (`setRange(0, 0)`) -- pulsierend, da redMod.exe
  keinen prozentualen Fortschritt ausgibt
- QLabel mit Status-Text ("Kompiliere X Mods...")
- QPushButton "Abbrechen" zum Killen des Prozesses
- Kein Terminal-Fenster, kein separater Dialog
- Erbt QSS-Theme automatisch (kein setStyleSheet!)
- Start-Button ist deaktiviert waehrend Overlay sichtbar ist

### Fehler-Dialog (bei fehlgeschlagenem Deploy)

Standard-QMessageBox mit Details:

```
+--------------------------------------------------+
|  (!) REDmod-Deploy fehlgeschlagen                |
|                                                  |
|  Die REDmod-Kompilierung ist mit Fehler-Code 1   |
|  fehlgeschlagen. Das Spiel kann trotzdem         |
|  gestartet werden, aber REDmod-Mods werden       |
|  moeglicherweise nicht funktionieren.            |
|                                                  |
|        [Trotzdem starten]    [Abbrechen]         |
|                                                  |
|  [Details anzeigen v]                            |
|    stderr: ...                                   |
+--------------------------------------------------+
```

### Menu-Eintraege (Exe-Dropdown)

Die bestehenden deaktivierten Platzhalter (game_panel.py:536-545) werden aktiviert:

- **"Cyberpunk 2077 - skip REDmod deploy"**: Toggle-Action (Checkable). Wenn aktiviert,
  wird beim naechsten Start der REDmod-Deploy uebersprungen. Gespeichert als
  Setting pro Instanz in QSettings.
- **"Manually deploy REDmod"**: Fuehrt `redMod.exe deploy` sofort aus (ohne Spielstart).
  Zeigt das gleiche Overlay wie beim automatischen Deploy.

---

## Edge Cases

| Situation | Verhalten |
|-----------|-----------|
| Kein REDmod-Mod installiert | REDmod-Deploy komplett ueberspringen, Spiel normal starten |
| redMod.exe existiert nicht (kein REDmod DLC) | Warnung loggen, Spiel trotzdem starten |
| Proton nicht verfuegbar | Warnung anzeigen (gleiche Logik wie _launch_via_proton) |
| User klickt "Start" waehrend REDmod laeuft | Start-Button ist deaktiviert -- kein Doppelstart moeglich |
| User wechselt Instanz waehrend REDmod laeuft | Worker-Thread abbrechen via Flag, Overlay entfernen |
| Auto-Redeploy waehrend REDmod laeuft | Redeploy-Timer wird in _on_start_clicked() gestoppt |
| Deploy-Abbruch durch User (Abbrechen-Button) | proc.kill(), Overlay entfernen, Spiel NICHT starten |
| redMod.exe haengt (>300s Timeout) | Dialog: "REDmod-Deploy dauert ungewoehnlich lange. Abbrechen?" |
| Exit-Code != 0 von redMod.exe | Dialog: "Fehlgeschlagen. Trotzdem starten?" mit stderr in Details |
| Gleichzeitig REDmod UND normale Mods | Beide Typen werden unabhaengig deployed |
| Nicht-Cyberpunk-Spiel | REDmod-Deploy nur wenn NeedsRedmodDeploy == True |
| Deaktivierter REDmod-Mod | Wird NICHT deployed (nur aktive Mods aus active_mods.json) |
| MIXED Mod (REDmod + normale Dateien, z.B. Kwek's mit r6/scripts/) | Pattern B: Einzel-Symlinks fuer alle Dateien inkl. mods/ und r6/ -- funktioniert bereits korrekt |
| Pattern A Mod mit Dateien ausserhalb info.json/archives/ | Ordner-Symlink fuer gesamten Mod -- alle Dateien werden ueber den Symlink erreichbar |
| mods/ Ordner hat echte Dateien (z.B. .stub) | Nur Symlinks anlegen/entfernen, echte Dateien nicht anfassen |
| "skip REDmod deploy" aktiv | REDmod-Deploy wird uebersprungen, Spiel startet direkt |
| Cross-Filesystem Symlinks (.mods/ auf anderer Partition als Game) | Sollte funktionieren (Wine loest Symlinks transparent auf). Fallback: shutil.copytree() -- erst implementieren wenn noetig |
| GOG/Epic (Non-Steam) | Phase 1 (Routing) funktioniert sofort. Phase 2 (Kompilierung) braucht Wine statt Proton -- spaetere Erweiterung (P2) |

---

## MO2-Vergleich

| Aspekt | MO2 | Anvil |
|--------|-----|-------|
| REDmod-Platzierung | VFS mappt mods/ transparent | Ordner-Symlinks nach game_root/mods/ |
| REDmod-Kompilierung | User muss manuell "redMod.exe deploy" als Pre-Launch konfigurieren | Automatisch vor Spielstart (kein manueller Schritt noetig) |
| Fortschrittsanzeige | Terminal-Fenster | Modernes Overlay mit pulsierender Progressbar |
| Fehlerbehandlung | Exit-Code im Terminal | Dialog mit "Trotzdem starten?" Option |
| Skip-Option | User entfernt Pre-Launch Konfiguration | Toggle im Exe-Menu |

**Anvil-Vorteil:** Vollautomatisch, kein manueller Pre-Launch-Schritt noetig. Bessere UX.

---

## Verwandte Funktionen (geprueft)

| Funktion | Gleicher Fix noetig? | Begruendung |
|----------|---------------------|-------------|
| LML-Pattern (mod_deployer.py:200-223) | Nein | Funktioniert bereits, wird als Vorlage verwendet |
| BA2Packer (ba2_packer.py) | Nein | Nutzt Wine direkt, nicht Proton. Eigener Mechanismus. |
| _launch_via_proton() (game_panel.py:1102) | Ja -- Refactoring | Proton-Env-Logik soll in Helper extrahiert werden (DRY) |
| _on_start_clicked() (game_panel.py:1009) | Ja -- Refactoring | Launch-Logik in _do_launch() extrahieren |
| silent_deploy() (game_panel.py:603) | Nein | REDmod-Kompilierung gehoert NICHT hierhin (zu langsam fuer Mod-Toggle) |
| Redeploy-Timer (mainwindow.py) | Ja -- Bug | Timer wird fuer Steam-Launches nicht gestoppt (Race Condition) |
| Exe-Menu Platzhalter (game_panel.py:536-545) | Ja | Muessen aktiviert und verbunden werden |
| Pre-Launch Deploy (mainwindow.py:1471-1479) | Nein | Betrifft nur Non-Steam; REDmod-Deploy wird in _on_start_clicked() eingefuegt |

---

## Risiken

| Risiko | Schwere | Beschreibung | Mitigation |
|--------|---------|-------------|------------|
| Symlinks unter Proton | MITTEL | redMod.exe laeuft in Wine/Proton und koennte Probleme mit Symlinks haben | LML-Pattern (Witcher 3) nutzt bereits Ordner-Symlinks unter Proton -- funktioniert. Fallback: shutil.copytree() |
| REDmod CLI-Argumente | NIEDRIG | Exakte Argumente koennten von der REDmod-Version abhaengen | Ohne Argumente starten (cwd=game_path), redMod.exe findet mods/ automatisch |
| Laufzeit >5 Minuten | NIEDRIG | Bei vielen/grossen REDmod-Mods | Timeout auf 300s, Abbrechen-Button |
| Pattern-C-Erkennung Fehlpositiv | NIEDRIG | Ein Subfolder mit info.json koennte kein REDmod sein | Zusaetzlich pruefen ob info.json die erwarteten Keys enthaelt (name, version) |

---

## Akzeptanz-Checkliste

- [ ] 1. Wenn Anvil die Cyberpunk-Instanz laedt, wird fuer "Material and Texture Override (REDmod)" (Pattern A) ein Ordner-Symlink `game_root/mods/Material and Texture Override (REDmod)/` erstellt, der auf den Mod-Ordner in .mods/ zeigt
- [ ] 2. Wenn Anvil die Cyberpunk-Instanz laedt, werden fuer "NCPDPPE" und "VEHICLE REPAIR COST" (Pattern C) Ordner-Symlinks unter `game_root/mods/NCPDPPE/` bzw. `game_root/mods/VEHICLE REPAIR COST/` erstellt
- [ ] 3. Wenn Anvil die Cyberpunk-Instanz laedt, werden die 7 Pattern-B-Mods (NIGHT CITY ALIVE, 3x Kwek's, 2x NSFW, Erotic Magazines) weiterhin korrekt als Einzel-Symlinks deployed (kein Regressionsbruch)
- [ ] 4. Wenn der User auf "Start" klickt und aktive REDmod-Mods vorhanden sind, erscheint ein Fortschritts-Overlay mit pulsierender Progressbar und dem Text "REDmod kompiliert..."
- [ ] 5. Wenn das Fortschritts-Overlay sichtbar ist, ist der Start-Button deaktiviert und kann nicht erneut geklickt werden
- [ ] 6. Wenn der User waehrend des REDmod-Deploys auf "Abbrechen" klickt, wird der Prozess gekillt, das Overlay entfernt und das Spiel NICHT gestartet
- [ ] 7. Wenn `redMod.exe deploy` mit Exit-Code 0 beendet wird, startet das Spiel automatisch (Steam oder Proton, je nach Auswahl)
- [ ] 8. Wenn `redMod.exe deploy` mit Exit-Code != 0 beendet wird, erscheint ein Dialog "Fehlgeschlagen. Trotzdem starten?" mit stderr in den Details
- [ ] 9. Wenn keine REDmod-Mods aktiv sind, startet das Spiel SOFORT ohne Overlay und ohne REDmod-Deploy
- [ ] 10. Wenn `redMod.exe` nicht existiert (kein REDmod DLC installiert), startet das Spiel normal und eine Warnung wird ins Log geschrieben
- [ ] 11. Wenn der User "skip REDmod deploy" im Exe-Menu aktiviert, wird der REDmod-Deploy beim naechsten Start uebersprungen
- [ ] 12. Wenn der User "Manually deploy REDmod" im Exe-Menu klickt, wird `redMod.exe deploy` sofort ausgefuehrt (ohne Spielstart) und das Fortschritts-Overlay angezeigt
- [ ] 13. Wenn ein Nicht-Cyberpunk-Spiel gewaehlt ist, wird kein REDmod-Deploy ausgefuehrt (NeedsRedmodDeploy = False)
- [ ] 14. Wenn ein REDmod-Mod deaktiviert ist (in active_mods.json), wird er NICHT als Ordner-Symlink deployed und nicht von redMod.exe kompiliert
- [ ] 15. Wenn Purge ausgefuehrt wird, werden die REDmod-Ordner-Symlinks (Pattern A + C) sauber entfernt (type: dir_symlink im Manifest)
- [ ] 16. Wenn ein MIXED Mod (Pattern B mit zusaetzlichen Dateien unter r6/scripts/) deployed wird, funktionieren sowohl die REDmod-Dateien (unter mods/) als auch die Non-REDmod-Dateien (unter r6/)
- [ ] 17. Alle neuen UI-Texte sind in allen 6 Locale-Dateien (de, en, es, fr, it, pt) vorhanden
- [ ] 18. Die Proton-Env-Logik ist in eine wiederverwendbare `_build_proton_env()` Methode extrahiert und wird sowohl vom REDmod-Deploy als auch von `_launch_via_proton()` verwendet
- [ ] 19. restart.sh startet ohne Fehler
