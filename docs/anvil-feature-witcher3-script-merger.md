# Feature-Spec: Witcher 3 Script Merger + Filelist Updater (#61, #36, #35)

**Status:** Geplant
**Datum:** 2026-06-28
**Betrifft:** The Witcher 3
**Konsolidiert:** GitHub-Issues #61 (Native Script Merger), #36 (Script Merger support), #35 (Menu Filelist Updater)

---

## 1. Problem / Ziel

Drei eng verwandte Witcher-3-Probleme, die zusammen das Mod-Loading bei TW3 vervollstaendigen:

**#61 / #36 — Script Merger (.ws-Konflikte):**
Witcher-3-Mods aendern oft dieselben `.ws`-Script-Dateien. Der Spiel-eigene
Script-Compiler laedt fuer jede Datei nur EINE Version (alphabetisch erster `modXXX`
gewinnt) — alle anderen Aenderungen gehen verloren. Es braucht ein Werkzeug, das
konfligierende `.ws`-Skripte zusammenfuehrt: automatisch bei nicht-ueberlappenden
Aenderungen, manuell (KDiff3) bei harten Konflikten. Das Ergebnis wird als
`mod0000_MergedFiles`-Merge-Mod geschrieben, der alphabetisch vor allen anderen steht.
**Nativ in Python/Linux — kein Wine, kein .NET, kein Windows.**
Referenz: Script Merger - Fresh and Automated Edition (nexusmods.com/witcher3/mods/8405).

**#35 — Menu Filelist Updater (XML-Menue-Registrierung):**
Seit dem Witcher-3-Next-Gen-Patch (4.0) muessen Mod-Menues (XML-Dateien) in
`dx11filelist.txt` und `dx12filelist.txt` registriert werden, damit ihre In-Game-Optionen
ueberhaupt erscheinen. Ohne Eintrag ist das Menue da, aber wirkungslos. Anvil soll
deployte Mods nach Menue-XMLs scannen und die Filelists automatisch beim Deploy
aktualisieren bzw. beim Purge zuruecksetzen.
Referenz: Menu Filelist Updater (nexusmods.com/witcher3/mods/7171).

**Gemeinsames Ziel:** Witcher-3-Mods, die Scripts UND/ODER Menues aendern, funktionieren
in Anvil ohne externe Windows-Tools — vollstaendig nativ unter Linux.

---

## 2. Ist-Zustand im Code

### 2a. Script Merger (#61, #36) — GROSSTEILS FERTIG

Der Script Merger ist bereits vollstaendig implementiert und in die App verdrahtet.
Bereits umgesetzt:

| Komponente | Datei | Status |
|------------|-------|--------|
| Datenmodell (Enums/Dataclasses) | `anvil/core/script_merger/models.py` | Fertig — `MergeStatus`, `DiffHunk` (mit `overlaps()`), `ModVersion`, `ScriptConflict`, `MergeResult`, `MergeInventoryEntry` |
| Scanner | `anvil/core/script_merger/scanner.py` | Fertig — Pattern A+B via `rglob("content")` (`scanner.py:33-45`), `.ws`+`.xml` (`:94-122`), `local/`-Ausschluss (`:99`), Vanilla-Suche (`:131-139`), 3-Wege-Diff (`_compute_diffs` `:164`), Hunk-Overlap (`:182-194`) |
| Auto-Merger | `anvil/core/script_merger/merger.py` | Fertig — Bottom-Up-Hunk-Anwendung (`merger.py:20-62`), Batch (`auto_merge_all` `:64`), 3+ Mods ok |
| Inventar (JSON) | `anvil/core/script_merger/inventory.py` | Fertig — load/save (`:26/:47`), add/ignore (`:71/:82`), `validate()` Hash-Mismatch (`:91`), clear (`:110`) |
| UTF-16-Codec | `anvil/core/script_merger/ws_codec.py` | Fertig — BOM-Detection (`:7`), UTF-16 LE + CRLF schreiben (`:27`), SHA256 (`:36`) |
| Dialog (UI) | `anvil/widgets/script_merger_dialog.py` | Fertig — Scan/Merge/Cleanup/Ignore, Worker-Threads (`:79/:100`), Detail-Panel, Merge-Mod erstellen (`:493`), Inventar-Aufzeichnung (`:567`) |
| **KDiff3-Integration** | `anvil/widgets/script_merger_dialog.py` | Fertig — `_on_kdiff3()` (`:765`), Temp-Dateien (`:798`), QProcess + Flatpak-Spawn (`:822-834`), Ergebnis-Rueckimport (`_on_kdiff3_finished` `:836`) |
| Toolbar-Button | `anvil/widgets/toolbar.py:171-189` | Fertig — `merger_btn`, Separator, Sichtbarkeit default `False` |
| Mainwindow-Handler | `anvil/mainwindow.py:6430-6470` | Fertig — `_on_script_merger_clicked()`, Witcher-3-Guard, aktive Mods, Dialog-Aufruf, Reload bei `has_changes` |
| Button-Sichtbarkeit | `anvil/mainwindow.py:1225-1227` | Fertig — `is_witcher3 = short_name == "witcher3"` |
| Plugin-Pfade | `anvil/plugins/games/game_witcher3.py` | Fertig — `vanilla_scripts_dir()` (`:151`), `mods_path()`, `menu_config_path()` (`:138`), `has_script_merger()` (`:163`) |
| i18n | `anvil/locales/*.json` (7 Locales) | Fertig — `script_merger`-Block mit **39 Keys** in de/en/es/fr/it/pt/ru (geprueft, keine fehlen), `toolbar.script_merger` vorhanden |

**Fazit #61/#36: Funktional komplett, inkl. KDiff3 (das in den Issues als Feature gefordert
war). Es bleibt nur Verifikation/QA und ggf. Bugfixing — keine neue Kern-Implementierung.**

### 2b. Menu Filelist Updater (#35) — EXISTIERT NICHT

Suche nach `filelist`/`dx11filelist`/`dx12filelist`/`input.xml` ergibt **keine** Treffer in
Witcher-3-relevantem Code (nur unbezogene `textFileList`-QSS-Objektnamen und `lspk_parser`).

Vorhanden als Anknuepfungspunkte:
- `game_witcher3.py:138` `menu_config_path()` → `bin/config/r4game/user_config_matrix/pc/`
  (das ist der Menue-XML-Zielordner; die **Filelists liegen daneben** im selben `pc/`-Ordner).
- `game_panel.py:653` `silent_deploy()` enthaelt bereits Game-spezifische **Post-Deploy-Hooks**
  nach demselben Muster (BA2-Packing `:668`, `plugins.txt` `:705`, Proton-Shims `:729`,
  DLL-Overrides `:743`). Hier gehoert der Filelist-Updater hin.
- `game_panel.py:748` `silent_deploy_fast()` (Quick-Redeploy) braucht denselben Hook.
- `mod_deployer.py:577` `purge()` entfernt Symlinks anhand Manifest — der Filelist-Updater
  muss seine Eintraege selbst zuruecksetzen (Filelists sind echte Dateien, keine Symlinks).

**Fazit #35: Muss komplett neu gebaut werden — Core-Modul + 2 Hook-Aufrufe + Plugin-Pfade.**

### 2c. Was technisch ein Script Merger ist (Kontext)

- **`.ws`-Scripts:** Spiel-Logik in WitcherScript. Mehrere Mods patchen dieselbe Datei.
  Merge = Vanilla als Basis, Diff jeder Mod-Version gegen Vanilla, nicht-ueberlappende
  Aenderungen (Hunks) zusammenfuehren. Ueberlappende Hunks = harter Konflikt → manuell.
- **Nativer 3-Wege-Merge** (bereits da): `difflib.SequenceMatcher` liefert Opcodes →
  `DiffHunk`s; Bottom-Up angewendet auf Vanilla-Zeilen. Vollautomatisch, kein externes Tool.
- **KDiff3** (bereits da): externes 3-Wege-Merge-GUI fuer harte Konflikte. Aufruf mit
  Vanilla + bis zu 2 Mod-Versionen + Output-Pfad, Ergebnis wird zurueckgelesen. Linux-nativ,
  Flatpak-aware (`flatpak-spawn --host`).
- **Menu Filelist Updater** ist KEIN Merge, sondern eine **Registrierung**: nach jedem Deploy
  die `dx11filelist.txt`/`dx12filelist.txt` so erweitern, dass sie alle deployten Menue-XMLs
  auflisten. Reines Datei-Scannen + Text-Datei-Schreiben.

---

## 3. Loesung / Ansatz

### 3a. Script Merger (#61/#36) — keine neue Logik

Implementierung ist vollstaendig. Der Plan beschraenkt sich auf:
1. End-to-End-Verifikation gegen die 31 Akzeptanzkriterien aus `docs/anvil-feature-script-merger.md`.
2. KDiff3-Pfad in `settings_dialog.py` konfigurierbar machen, falls noch nicht vorhanden
   (Dialog liest `QSettings("ScriptMerger/kdiff3_path", "kdiff3")` — pruefen ob es einen
   UI-Eintrag dafuer gibt; wenn nicht, optional ergaenzen).
3. Etwaige Bugfindings aus QA beheben.

Es wird **keine** neue Merge-Logik, kein `merge3`, keine Bundle-Unterstuetzung gebaut
(Bundle bleibt explizit out-of-scope, wie in #36 als "Phase 3" markiert).

### 3b. Menu Filelist Updater (#35) — Neuentwicklung

**Neues Core-Modul `anvil/core/witcher_filelist.py`** mit Klasse `MenuFilelistUpdater`:

- **Erkennen der Filelist-Pfade** ueber das Plugin: neue Methode
  `game_witcher3.menu_filelist_paths()` → Liste von `(filelist_path, render_tag)` fuer
  `bin/config/r4game/user_config_matrix/pc/dx11filelist.txt` und `.../dx12filelist.txt`.
- **Scannen** des deployten Menue-Ordners (`menu_config_path()`,
  `bin/config/r4game/user_config_matrix/pc/`) nach `*.xml` (rekursiv), relative Pfade
  ermitteln. Vanilla-Menues (`input.xml` und die mitgelieferten Eintraege) NICHT doppelt
  registrieren.
- **Update-Logik:** Filelist hat das Format
  ```
  <userConfig>
    <group ...>
      ...
    </group>
  </userConfig>
  ```
  bzw. eine Liste von `<entry>`-Verweisen je nach TW3-Version. Der Updater liest die
  bestehende (Vanilla-)Filelist, fuegt fehlende Eintraege fuer deployte Mod-XMLs **idempotent**
  hinzu (Marker-Block `<!-- ANVIL_MANAGED_START --> ... <!-- ANVIL_MANAGED_END -->`),
  und schreibt sie zurueck. Encoding wie Vanilla beibehalten (i. d. R. UTF-8).
- **Backup/Restore:** Vor der ersten Aenderung Original-Filelist als
  `dx11filelist.txt.anvil-bak` sichern (falls noch nicht vorhanden). Beim Purge bzw. wenn
  keine Mod-XMLs mehr da sind → Anvil-Block entfernen (Marker-basiert), oder aus Backup
  wiederherstellen.
- **Idempotenz:** Mehrfaches Deploy darf keine Duplikate erzeugen — Marker-Block wird immer
  komplett ersetzt, nicht angehaengt.
- **Robustheit:** Fehlt eine Filelist (alte TW3-Version, kein Next-Gen) → still ueberspringen,
  kein Crash. IO-Fehler abfangen und als Warnung loggen.

**Hook-Verdrahtung in `game_panel.py`:**
- In `silent_deploy()` (`:653`) nach den bestehenden Post-Deploy-Schritten einen neuen Block
  ergaenzen: nur fuer `GameShortName == "witcher3"`, `MenuFilelistUpdater(plugin, game_path).update()`.
- In `silent_deploy_fast()` (`:748`) denselben Aufruf ergaenzen (Quick-Redeploy).
- Beim Purge: Da `purge()` im `mod_deployer` game-agnostisch ist, wird der Restore am
  besten ebenfalls game-spezifisch ausgeloest — entweder ueber den Purge-Pfad in
  `game_panel`/`mainwindow` (analog zu den Deploy-Hooks) oder durch erneuten `update()`
  nach Purge (der dann 0 Mod-XMLs findet und den Anvil-Block entfernt). Bevorzugt:
  `MenuFilelistUpdater.restore()` im Purge-Pfad von `game_panel`.

**Optionaler Schalter:** `QSettings("Witcher3/auto_filelist_update", True)` analog zu
`LOOT/auto_sort_on_deploy`, damit der User es abschalten kann.

---

## 4. Betroffene Dateien

| Datei | Aenderung |
|-------|-----------|
| `anvil/core/witcher_filelist.py` | **NEU** — `MenuFilelistUpdater` (scan, update, restore, backup, Marker-Block, Idempotenz) |
| `anvil/plugins/games/game_witcher3.py` | `menu_filelist_paths()` ergaenzen (dx11/dx12 Pfade + Render-Tag); ggf. Helper zum Erkennen ob Next-Gen-Filelists existieren |
| `anvil/widgets/game_panel.py` | In `silent_deploy()` und `silent_deploy_fast()` Post-Deploy-Hook fuer Witcher-3-Filelist; im Purge-Pfad `restore()` aufrufen |
| `anvil/widgets/settings_dialog.py` | Optional: Checkbox `Witcher3/auto_filelist_update`; optional KDiff3-Pfad-Eingabe pruefen/ergaenzen |
| `anvil/locales/de.json` | Neue tr-Keys (`witcher_filelist.*`), ggf. Settings-Labels |
| `anvil/locales/en.json` | dito |
| `anvil/locales/es.json` | dito |
| `anvil/locales/fr.json` | dito |
| `anvil/locales/it.json` | dito |
| `anvil/locales/pt.json` | dito |
| `anvil/locales/ru.json` | dito |

**NICHT geaendert (Script Merger ist fertig):** `script_merger/*.py`, `script_merger_dialog.py`,
`toolbar.py`, der Script-Merger-Teil von `mainwindow.py`. Nur bei QA-Findings anfassen.

**NICHT geaendert:** `mod_deployer.py` (game-agnostisch; Filelist laeuft als Post-Hook im
`game_panel`, nicht im Deployer).

---

## 5. Umsetzungsschritte

1. **Verifikation Script Merger (#61/#36):** App starten (`./restart.sh`), Witcher-3-Instanz
   laden, Script-Merger-Button pruefen, Scan/Auto-Merge/Merge-Mod/Cleanup/Ignore + KDiff3
   gegen die 31 AK aus `docs/anvil-feature-script-merger.md` durchgehen. Findings notieren.
2. **Plugin-Pfade (#35):** `menu_filelist_paths()` in `game_witcher3.py` ergaenzen (dx11/dx12
   im `pc/`-Ordner), plus Helper zur Existenzpruefung der Filelists.
3. **Core-Modul (#35):** `anvil/core/witcher_filelist.py` mit `MenuFilelistUpdater`:
   `scan_menu_xmls()`, `update()` (Marker-Block idempotent), `backup()`, `restore()`.
   IO-Fehler abfangen, fehlende Filelists ueberspringen.
4. **Deploy-Hook (#35):** In `game_panel.silent_deploy()` + `silent_deploy_fast()` den
   Updater nach den bestehenden Post-Deploy-Schritten aufrufen (nur witcher3, nur wenn
   `Witcher3/auto_filelist_update` aktiv).
5. **Purge-Restore (#35):** Im Purge-Pfad `MenuFilelistUpdater.restore()` aufrufen, sodass
   die Vanilla-Filelist wiederhergestellt wird.
6. **i18n (#35):** Neue `witcher_filelist.*`-Keys + ggf. Settings-Labels in ALLE 7 Locales.
7. **Settings (#35, optional):** Checkbox fuer Auto-Filelist-Update; KDiff3-Pfad-Feld pruefen.
8. **Test:** `./restart.sh`, Deploy einer Menue-Mod → Filelist-Eintrag pruefen; erneuter
   Deploy → keine Duplikate; Purge → Filelist zurueckgesetzt; Log auf Tracebacks pruefen.
9. **QA:** 4 Review-Agents gemaess CLAUDE.md (Bugs, Signal/Scope, MO2-Vergleich/i18n,
   Konsolidierung) — null Findings, dann Commit.

---

## 6. i18n (tr-Keys, 7 Locales de/en/es/fr/it/pt/ru)

**Script Merger (#61/#36):** Bereits vollstaendig — `script_merger`-Block mit 39 Keys
in allen 7 Locales (geprueft, keine fehlen), `toolbar.script_merger` vorhanden. Hier nichts zu tun.

**Menu Filelist Updater (#35) — neu in ALLEN 7 Locales (`witcher_filelist.*`):**

| Key | Verwendung |
|-----|------------|
| `witcher_filelist.updated` | Statusmeldung "Menue-Filelist aktualisiert (N Eintraege)" |
| `witcher_filelist.restored` | "Menue-Filelist zurueckgesetzt" |
| `witcher_filelist.no_filelist` | "Keine Next-Gen-Filelist gefunden — uebersprungen" |
| `witcher_filelist.error` | "Filelist-Update fehlgeschlagen: {error}" |
| `settings.witcher3_filelist_label` | Settings-Checkbox-Label (falls Settings-Schalter umgesetzt) |
| `settings.witcher3_filelist_tooltip` | Tooltip dazu |

**Pflicht:** Jeder neue Key in `de`, `en`, `es`, `fr`, `it`, `pt`, `ru` — nie nur in einer Datei.

---

## 7. Akzeptanzkriterien

### Script Merger (#61/#36) — Verifikation der bestehenden Implementierung
- [ ] **AK-01:** Bei Witcher-3-Instanz ist der "Script Merger"-Button sichtbar; bei anderen Games unsichtbar
- [ ] **AK-02:** Klick oeffnet Dialog mit Pfad-Info; fehlt Vanilla-Dir → Warnung statt Dialog
- [ ] **AK-03:** Scan findet `.ws`-Konflikte (Pattern A + B) und `.xml`-Konflikte; `local/` wird ignoriert; 0 Konflikte → Meldung
- [ ] **AK-04:** AUTO_MERGEABLE bei nicht-ueberlappenden Hunks, CONFLICT bei ueberlappenden / fehlendem Vanilla
- [ ] **AK-05:** Auto-Merge (einzeln + alle) funktioniert, auch bei 3+ Mods; CONFLICT/IGNORED uebersprungen
- [ ] **AK-06:** "Merge-Mod erstellen" schreibt `_merged_/mods/mod0000_MergedFiles/` (UTF-16 LE + BOM + CRLF), Position 0 in modlist.txt, aktiv in allen Profilen; kein Duplikat bei Wiederholung
- [ ] **AK-07:** KDiff3-Button startet KDiff3 (Linux-nativ, Flatpak via `flatpak-spawn --host`), Ergebnis wird als MERGED zurueckgelesen; fehlt KDiff3 → Warnung
- [ ] **AK-08:** Cleanup entfernt `_merged_` + modlist-Eintrag (alle Profile) + Inventar; danach Scan = UNSCANNED
- [ ] **AK-09:** Ignorieren ist persistent; Hash-Mismatch markiert veraltete Merges
- [ ] **AK-10:** Worker-Threads beim Dialog-Schliessen sauber beendet; IO-Fehler ohne Crash; `restart.sh` ok

### Menu Filelist Updater (#35) — Neuentwicklung
- [ ] **AK-11:** Nach Deploy einer Menue-Mod werden deren `.xml` in `dx11filelist.txt` UND `dx12filelist.txt` registriert
- [ ] **AK-12:** In-Game erscheinen die Mod-Menue-Optionen (manuell verifiziert, soweit moeglich)
- [ ] **AK-13:** Erneuter Deploy erzeugt KEINE Duplikat-Eintraege (Marker-Block wird ersetzt, nicht angehaengt)
- [ ] **AK-14:** Vor erster Aenderung wird ein Backup der Original-Filelists angelegt
- [ ] **AK-15:** Purge entfernt den Anvil-Block / stellt Vanilla-Filelist wieder her
- [ ] **AK-16:** Fehlende Filelists (alte TW3-Version) werden still uebersprungen, kein Crash
- [ ] **AK-17:** Vanilla-Menue-Eintraege bleiben unangetastet und werden nicht doppelt registriert
- [ ] **AK-18:** Encoding/Format der Filelists bleibt gueltig (Spiel laedt sie ohne Fehler)
- [ ] **AK-19:** Optionaler Settings-Schalter `Witcher3/auto_filelist_update` greift (an/aus)
- [ ] **AK-20:** Alle `witcher_filelist.*`-Keys in allen 7 Locales vorhanden

### Allgemein
- [ ] **AK-21:** `./restart.sh` startet ohne Traceback/NameError/ImportError
- [ ] **AK-22:** 4 QA-Review-Agents melden null Findings

---

## 8. Aufwand / Risiko

**#61 / #36 — Script Merger:** Aufwand **niedrig** (nur Verifikation + ggf. Bugfix).
Risiko **niedrig** — Code existiert vollstaendig inkl. KDiff3 und i18n. Hauptrisiko ist
verstecktes Fehlverhalten bei den zwei Mod-Patterns oder UTF-16-Edge-Cases, das nur ein
echter Durchlauf aufdeckt.

**#35 — Menu Filelist Updater:** Aufwand **mittel** — ein neues Core-Modul, zwei Hook-Aufrufe,
Plugin-Pfade, 7 Locales. Risiko **mittel**:
- Genaues Format der Next-Gen-Filelists muss am realen Spiel verifiziert werden (XML-Struktur
  vs. einfache Pfadliste), sonst laedt das Spiel die Datei nicht.
- Idempotenz und Backup/Restore muessen wasserdicht sein, sonst korrumpiert wiederholtes
  Deploy die Vanilla-Filelist.
- Purge-Restore haengt am game-spezifischen Hook — der Deployer ist game-agnostisch, daher
  muss der Restore zuverlaessig im `game_panel`-Purge-Pfad ausgeloest werden.

**Abhaengigkeiten:** KDiff3 optional (`pacman -S kdiff3`) nur fuer manuelle Merges. Sonst keine
externen Tools — alles nativ Python.

**Out-of-scope (bewusst):** `.bundle`-Konflikte/Merge (braucht `wcc_lite`/Wine, #36 "Phase 3"),
`merge3`-basierter Multi-Way-Merge, DLC-Konflikte.
