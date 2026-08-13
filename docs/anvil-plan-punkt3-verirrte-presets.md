# Punkt 3 — Verirrte Presets erkennen und geraderücken

Datum: 2026-08-13
Status: Planung. **Kein Code geändert.**
Grundlage: `docs/stand-2026-08-12.md`, Abschnitt „Punkt 3 — Verirrte Presets erkennen"

Jede Aussage in diesem Papier ist an Datei und Zeile belegt oder an Marcs echter
Installation gemessen. Wo etwas nicht belegbar war, steht es unten unter
**UNSICHER**.

---

## 1. Der Ist-Zustand

### 1.1 Wo der ACU-Zielpfad im Code steht

`anvil/plugins/games/game_cyberpunk2077.py:158-218` — `get_preset_kinds()`
liefert genau eine `PresetKind`:

| Feld | Wert | Zeile |
|---|---|---|
| `name` | `ACU-Preset` | :174 |
| `short` | `ACU` | :175 |
| `suffix` | `.preset` | :176 |
| `target` | `bin/x64/plugins/cyber_engine_tweaks/mods/AppearanceChangeUnlocker/character-presets` | :177-180 |
| `variants` | `[female, male]` | :181 |
| `markers` | 11 weibliche, 18 männliche `LocKey#…` | :182-216 |

Die Basisklasse liefert eine leere Liste: `anvil/plugins/base_game.py:898-903`.
Alle anderen Spiele kennen also keine Presets — geprüft über Grep auf
`get_preset_kinds`, Treffer nur in `base_game.py` und `game_cyberpunk2077.py`.

Der Datentyp `PresetKind` steht in `anvil/core/character_presets.py:26-53`.

### 1.2 Wie Anvil heute ein Preset erkennt

`anvil/core/character_presets.py:142-165` — `is_preset_mod(rel_paths, kinds)`:

- Nebensachen werden übersprungen: versteckte Dateien und
  `{"meta.ini", "codes.txt", "fomod_choices.json"}` (`:132`, gehalten gleich mit
  `mod_deployer._SKIP_FILES`, `anvil/core/mod_deployer.py:41`).
- Jede übrige Datei muss `_gehoert_zu()` bestehen (`:135-139`):
  Pfad beginnt mit `<target>/` **und** endet auf `.preset`.
- Nur wenn **alle** Dateien bestehen und mindestens eine gezählt wurde, ist die
  Mod ein Preset.

Aufruf im Hauptfenster: `anvil/mainwindow.py:2220-2241` (`_preset_mod_names`),
verwendet über `_split_presets` (`:2286-2299`) an zwei Stellen —
`:2028` beim Aufbau der Liste und `:7401` beim Neuzeichnen.

Damit ist der Fall „Bad Corpo" **bewusst** kein Preset: die Datei liegt nicht
unter `target`. Das ist als Test festgehalten:
`tests/test_preset_bereich.py:55-57`.

### 1.3 Welche Preset-Endungen es wirklich gibt

Genau eine: `.preset` (`game_cyberpunk2077.py:176`). Keine weitere
`PresetKind` im Repo.

Nicht verwechseln: die ReShade-Presets sind `.ini`/`.txt`
(`anvil/core/reshade_manager.py:9, 184-207`) und laufen über einen völlig
anderen Weg. Keine Überschneidung.

### 1.4 Was wirklich auf der Platte liegt

Pfad aus der Instanz-Config gelesen, nicht geraten:
`/home/mob/.anvil-organizer/instances/Cyberpunk 2077/.anvil.ini`

```
[Paths]
mods_directory=%INSTANCE_DIR%/.mods        (Zeile 14)
game_path=/mnt/Gaming/SteamLibrary/steamapps/common/Cyberpunk 2077   (Zeile 5)
preset_separator=Presets_separator         (Zeile 9)
selected_profile=Vanilla                   (Zeile 10)
```

Aufgelöst: `/home/mob/.anvil-organizer/instances/Cyberpunk 2077/.mods`

**Der Ordner „Bad Corpo" enthält genau zwei Dateien:**

```
Bad Corpo/Bad Corpo.preset
Bad Corpo/meta.ini
```

Aus `Bad Corpo/meta.ini`:

```
modid = 5277
nexusName = Bad Corpo - ACU Preset by RyBunny
installationFile = Bad Corpo-5277-1-5-1-1663535320.zip
installDate = 2026-08-11T10:48:16
```

Also unstrittig ein ACU-Preset. Es ist **aktiv**:
`.profiles/modlist.txt:525` → `+Bad Corpo`, und
`.profiles/Vanilla/active_mods.json:36` → `"Bad Corpo"`.

**Der Inhalt der Datei sagt „weiblich".** Gegen die Markerlisten aus
`game_cyberpunk2077.py:182-216` geprüft: `Bad Corpo.preset` enthält
`LocKey#6131936511989184869` (Zeile 30) und `LocKey#14444638123505366956`
(Zeile 31) — beide stehen in der **weiblichen** Liste. Kein einziger männlicher
Marker kommt vor. `detect_variant()` (`character_presets.py:70-95`) würde
also `female` liefern: Pfad hilft nicht, der Name „Bad Corpo" hilft nicht,
der Inhalt entscheidet.

### 1.5 Warum die Datei im Spielhauptverzeichnis landet

Der Weg durch den Deployer, Schritt für Schritt in `anvil/core/mod_deployer.py`:

1. `.preset` ist keine Nebensache (`:41 _SKIP_FILES`) und keine der im
   Mod-Wurzelverzeichnis übersprungenen Endungen (`:48-52 _SKIP_ROOT_EXTENSIONS`
   — nur Bilder, Doku, `.db`). Die Datei wird also ausgerollt.
2. `has_deploy_anchor` (`:109-113`) prüft `rel.parts[0]` — das ist hier der
   Dateiname selbst, kein Ankerordner. Kein Treffer.
3. `route_deploy_path` (`:153-198`) mit `GameDeployRoutes`
   (`game_cyberpunk2077.py:93-109`): Regel 1 verlangt `.archive`/`.xl`,
   Regel 2 verlangt einen obersten **Ordner** aus
   `scripts/tweaks/input/config` und `len(rel.parts) > 1`. Beides trifft nicht.
4. `GameDataPath = ""` (`game_cyberpunk2077.py:44`) — es kommt kein Präfix
   davor (`mod_deployer.py:763`).
5. Ergebnis `target = deploy_base / rel` (`:809`) →
   `<Spielordner>/Bad Corpo.preset`.

Zum Zeitpunkt der Messung liegt dort **nichts** — Glob auf
`/mnt/Gaming/SteamLibrary/steamapps/common/Cyberpunk 2077/*.preset` findet
keine Datei. Es ist also gerade nicht ausgerollt (kein aktuelles Deployment
oder seither gepurged). Am Befund ändert das nichts: sobald ausgerollt wird,
landet sie dort.

### 1.6 Warum es diesen Fall überhaupt gibt

Für **neue** Installationen ist das Problem längst gelöst:
`mainwindow.py:3669-3676` fängt Presets **vor** dem gewöhnlichen Weg ab und
`_install_presets_from` (`:2353-2437`) sucht mit
`cp.find_presets()` → `rglob(f"*{kind.suffix}")` (`character_presets.py:56-67`),
also **überall im Paket**, auch in der Wurzel. Aus jedem Fund wird über
`build_mod` (`:168-194`) eine eigene Mod mit fertigem Zielpfad.

`Bad Corpo` wurde am **11.08.2026** installiert, der Presets-Bereich kam am
12.08. (`6def2a8`). Verirrte Presets sind damit vor allem **Altbestand** —
Mods, die vor diesem Umbau installiert wurden. Das begrenzt den Umfang und
spricht dagegen, den Installationsweg noch einmal anzufassen.

---

## 2. Wie viele sind betroffen?

Gemessen im echten Mod-Ordner, Glob über
`.mods/**/*.[Pp][Rr][Ee][Ss][Ee][Tt]` — **14 Treffer in 9 Mod-Ordnern**:

| Mod-Ordner | Presets | Wo liegen sie? | Einordnung |
|---|---|---|---|
| `ACU - Character Customization` | 6 | `bin/x64/.../character-presets/female\|male/` | richtig — aber die Mod ist das **Framework** (enthält zusätzlich `init.lua`, `mirrorUnlocker.reds`, `red4ext/plugins/ACU/acu_rs.dll`), daher kein Preset-Mod |
| `ACU-Preset - Grace (female)` | 1 | `…/character-presets/female/Grace.preset` | richtig, Presets-Bereich |
| `ACU-Preset - Aiko (female)` | 1 | dito | richtig |
| `ACU-Preset - Kaori (female)` | 1 | dito | richtig |
| `ACU-Preset - Mona Chains (female)` | 1 | dito | richtig |
| `ACU-Preset - Shaundi - Female V Preset (female)` | 1 | dito | richtig |
| `ACU-Preset - cloev2 (female)` | 1 | dito | richtig |
| `ACU-Preset - isabella (female)` | 1 | dito | richtig |
| **`Bad Corpo`** | **1** | **`Bad Corpo.preset` in der Ordnerwurzel** | **VERIRRT** |

**Ergebnis: genau ein verirrtes Preset — `Bad Corpo`.** Die 7 Mods im
Presets-Bereich stimmen mit dem Bericht überein (`stand-2026-08-12.md:22-23`).

### 2.1 Der wichtige Unterschied: `FemV - RE9 Grace` ist **nicht** verirrt

Der Bericht nennt `FemV - RE9 Grace` und `Bad Corpo` in einem Atemzug — die
beiden haben aber nichts miteinander zu tun. Der Ordner enthält:

```
FemV - RE9 Grace/archive/pc/mod/00_FacePreset_RE9Grace_xBaebsae.archive
FemV - RE9 Grace/meta.ini
```

**Keine einzige `.preset`-Datei.** Das ist eine ganz gewöhnliche Archiv-Mod
(ein Gesicht als `.archive`), die nur „FacePreset" heißt. Sie gehört in die
Mod-Liste, sie greift ins Spiel ein, sie kann mit anderen Mods kollidieren —
genau deshalb ist sie ja der Streitfall aus Punkt 1 (`000_` gegen
`Unique Eyes - Core`, `stand-2026-08-12.md:161-166`). **Hier ist nichts zu
reparieren.**

Nebenbei belegt der Ordner, dass der Aufteilungsweg funktioniert: das
Nexus-Paket brachte Preset **und** Archiv mit (so beschrieben in
`tests/test_preset_bereich.py:44-48`); Anvil hat daraus zwei Mods gemacht —
`ACU-Preset - Grace (female)` und `FemV - RE9 Grace`.

Kurzfassung der beiden Fälle:

| Mod | Warum steht sie in der Mod-Liste? | Handlungsbedarf |
|---|---|---|
| `Bad Corpo` | enthält ein Preset, aber am falschen Ort | **ja** — geraderücken |
| `FemV - RE9 Grace` | enthält gar kein Preset, sondern ein `.archive` | **nein** |

---

## 3. Wo gehört die Prüfung hin?

### 3.1 Die bestehenden Muster (gesucht und gefunden)

| Muster | Wo | Was es tut |
|---|---|---|
| **Deploy-Routen** | `game_cyberpunk2077.py:84-109`, `mod_deployer.py:109-113, 153-198, 754-759` | biegt falsch gepackte Pfade beim Ausrollen still um (`scripts/` → `r6/scripts/`), Test: `tests/test_cyberpunk_r6_routing.py` |
| **Struktur-Reparatur beim Installieren** | `mod_installer.py:720-744` `_fix_se_plugins_dir` | verschiebt `Plugins/` → `<SE>/Plugins/` **im Mod-Ordner**, still, ohne Rückfrage |
| **Presets beim Installieren abfangen** | `mainwindow.py:3669-3676`, `:2353-2437` | baut aus jeder gefundenen `.preset` eine eigene Mod mit richtigem Zielpfad |
| **„Nicht alles ist angekommen"** | `mod_deployer.py:257-264` → `game_panel.py:1391-1403` (`deploy_gaps`) → `mainwindow.py:9216-9234` | Sammelmeldung über die Glocke + Log, Schlüssel `notifications.deploy_gaps` |
| **Fremde Mods** | `mod_list_model.py:391-392, 431-436`, Schlüssel `foreign.tooltip` | Warnfarbe + Tooltip in der Liste, ohne etwas zu verändern |
| **Diagnose-Probleme** | `diagnostics.py:141-173`, Anzeige `settings_dialog.py:1453-1465` | Liste `{severity, message}`, rein pfadbezogen |

Es gibt also bereits alles, was gebraucht wird. **Nichts Neues erfinden.**

### 3.2 Bewertung der möglichen Orte

| Ort | Bewertung |
|---|---|
| **Beim Einlesen der Mod-Liste** (`_preset_mod_names`, `mainwindow.py:2220-2241`) | **Der richtige Ort.** Die Schleife läuft ohnehin über alle Mods und hat die Dateiliste aus dem Index schon in der Hand. Kosten: eine zusätzliche Prüfung pro Mod, kein einziger Plattenzugriff. Läuft automatisch an beiden Aufrufstellen (`:2028`, `:7401`). |
| Beim Ausrollen | Zu spät und am falschen Ende: der Deployer kennt keine `PresetKind` und dürfte Marcs Ordner ohnehin nicht anfassen. Als **stille Umleitung** denkbar (siehe 4.2), aber nicht als Erkennung. |
| In der Diagnose (`diagnostics.py`) | `detect_problems()` bekommt nur `idata`, `sysinfo`, `path_checks` — keinen Mod-Index. Für eine Mod-Prüfung müsste die Signatur aufgebohrt werden. **Später gern als Zusatz** über den vorhandenen `_diagnostics_provider`-Rückruf (`settings_dialog.py:1475-1495`), aber nicht als Hauptweg: der Diagnose-Tab wird selten geöffnet. |
| Im Detail-Fenster | `mod_has_presets()` (`mod_detail_dialog.py:1156-1170`) sucht mit `rglob` und ist **ortsblind** — für „Bad Corpo" liefert es schon heute `True` und blendet den Voraussetzungs-Tab ein. Genau diese Asymmetrie (`mod_has_presets` = ja, `is_preset_mod` = nein) ist der Beweis, dass etwas nicht stimmt. Als Anzeigeort trotzdem zweite Wahl. |

**Entscheidung: Erkennung in der Mod-Listen-Schleife, Meldung über die Glocke
(wie `deploy_gaps`) plus Markierung in der Liste, Reparatur auf Zuruf über das
Kontextmenü.**

---

## 4. Geraderücken — wie?

### 4.1 Weg A: Datei im Mod-Ordner verschieben (Empfehlung)

`Bad Corpo/Bad Corpo.preset`
→ `Bad Corpo/bin/x64/plugins/cyber_engine_tweaks/mods/AppearanceChangeUnlocker/character-presets/female/Bad Corpo.preset`

Zielpfad kommt aus vorhandenem Code:
`cp.detect_variant()` (`character_presets.py:70-95`) + `cp.target_path()`
(`:120-125`) — dieselben zwei Funktionen, die `build_mod()` (`:191`) beim
Installieren benutzt. Kein neuer Pfadbau, keine zweite Wahrheit.

**Vorteile**

- Danach greift `is_preset_mod()` (`:142-165`) ohne jede Änderung, die Mod
  wandert von selbst in den Presets-Bereich, bekommt die Spalte „Variante" und
  das Kontextmenü mit Umbenennen/Entfernen (`mainwindow.py:7261-7281`).
- Der gewöhnliche Deploy-Weg trägt die Datei an die richtige Stelle — genau die
  Begründung, die im Modulkopf steht (`character_presets.py:1-12`).
- Ein Update des Frameworks wirft sie nicht weg (ebenda).
- Es gibt bereits einen Präzedenzfall im Code: `_fix_se_plugins_dir`
  (`mod_installer.py:720-744`) verschiebt genauso innerhalb des Mod-Ordners.

**Nachteile / Auflagen**

- Anvil fasst Marcs Ordner an. **Nur nach ausdrücklicher Bestätigung**, mit
  Quelle und Ziel im Text. `_fix_se_plugins_dir` macht das still — das ist beim
  Installieren vertretbar (die Mod ist noch niemandes Bestand), beim Altbestand
  nicht.
- Ist die Variante nicht erkennbar, muss gefragt werden. Der Dialog existiert:
  `_ask_preset_variant` (`mainwindow.py:2199-2212`) mit den Schlüsseln
  `preset.variant_title` / `preset.variant_prompt` / `preset.variant_female` /
  `preset.variant_male`.
- Danach muss der Index nachgezogen werden:
  `self._mod_index.invalidate_and_rescan(name)` (`modindex.py:206-223`), dann
  `_reload_mod_list()` und `_do_redeploy()` — dasselbe Nachspiel wie beim
  Umbenennen (`mainwindow.py:7109-7114`).

### 4.2 Weg B: Beim Ausrollen umleiten

Eine Regel in `GameDeployRoutes` (`game_cyberpunk2077.py:93-109`):

```
{"dest": "bin/x64/.../character-presets", "suffixes": [".preset"], "flatten": True}
```

**Vorteile:** vier Zeilen, greift für alle Zeiten, rührt Marcs Ordner nicht an,
und die Testvorlage steht schon (`tests/test_cyberpunk_r6_routing.py`).

**Warum es trotzdem nicht reicht**

1. **Die Variante geht verloren.** Eine Route kennt nur Pfadmuster, keinen
   Dateiinhalt. Sie kann nur nach `character-presets/` schreiben, nicht nach
   `character-presets/female/`. Ob ACU dort liest, ist **nicht belegt** — alle
   sechs mitgelieferten Presets liegen in `female/` bzw. `male/`, und die
   Auswertung macht `red4ext/plugins/ACU/acu_rs.dll`; die `init.lua` daneben ist
   ein Platzhalter („Dummy Mod so CET doesn't complain", 10 Zeilen). Siehe
   **UNSICHER**.
2. **Der Presets-Bereich bliebe leer.** `is_preset_mod()` urteilt über den
   **Mod-Ordner**, nicht über das Deploy-Ziel. `Bad Corpo` stünde weiter in der
   Mod-Liste. Punkt 3 wäre nur halb erledigt.
3. **Zu grob.** Die Regel griffe für jede beliebige lose `.preset` in jeder Mod
   und schöbe sie nach ACU — auch dann, wenn sie gar nicht dorthin gehört.
4. Marc sähe nie, dass etwas schief lag. Es bliebe ein stiller Automatismus.

**Fazit:** Weg B als alleinige Lösung nein. Als **Sicherheitsnetz** hinter Weg A
denkbar, aber erst wenn 1. geklärt ist. Für diesen Punkt: nicht bauen.

### 4.3 Was passiert bei Rückgängig?

Es gibt in Anvil **kein** Rückgängig-System — Grep auf `undo`/`rueckgaengig`
über `anvil/` liefert null Treffer. Also:

- **Der Schritt ist verlustfrei umkehrbar.** Die Datei bleibt im selben
  Mod-Ordner, sie liegt nur tiefer. Kein Löschen, kein Umbenennen, kein
  Kopieren über Ordnergrenzen.
- **Der Spielordner räumt sich selbst auf.** `deploy()` purged zuerst nach
  Manifest (`mod_deployer.py:435-444`, `purge()` ab `:1191`); die alte
  `<Spielordner>/Bad Corpo.preset` verschwindet beim nächsten Ausrollen von
  selbst. Niemand muss von Hand im Spielordner aufräumen.
- **Rückweg für Marc:** Rechtsklick → „Im Dateimanager öffnen" (existiert für
  Presets: `mainwindow.py:7268, 7276-7279`) und die Datei zurückschieben. Oder
  Rechtsklick → „Neu installieren" (`_ctx_reinstall_mod`, `mainwindow.py:7117`)
  — das Nexus-Archiv liegt vor (`installationFile` in der `meta.ini`).
- Der Bestätigungsdialog nennt deshalb **beide** Pfade im Klartext, damit der
  Rückweg ohne Nachfragen möglich ist.
- **Nicht** vorgesehen: eine Sicherungskopie der Datei. Sie bliebe ewig liegen
  und würde beim nächsten Deploy als zusätzliche Datei mitwandern.

---

## 5. Die Spec

### 5.1 User Stories

- Als Nutzer möchte ich erfahren, wenn ein Preset in meiner Sammlung an einer
  Stelle liegt, an der das Spiel es nie findet — statt mich zu wundern, warum es
  im Charaktermenü fehlt.
- Als Nutzer möchte ich so ein Preset mit einem Klick geraderücken lassen,
  ohne selbst durch sechs Ordnerebenen zu klicken.
- Als Nutzer möchte ich, dass Anvil meinen Mod-Ordner **nicht ohne Nachfrage**
  umbaut.
- Als Nutzer möchte ich sehen, für welche Figur (weiblich/männlich) das Preset
  einsortiert wird, bevor ich zustimme.

### 5.2 Betroffene Dateien

| Datei | Änderung |
|---|---|
| `anvil/core/character_presets.py` | **neu:** `stray_presets(rel_paths, kinds) -> list[str]` — liefert die relativen Pfade, die auf `kind.suffix` enden, aber nicht unter `kind.target` liegen. Nebensachen (`_NEBENSACHE`, `:132`) und versteckte Dateien werden wie in `is_preset_mod` übersprungen. **neu:** `fix_stray_path(mod_dir, rel, kind, variant) -> Path` — verschiebt die Datei nach `mod_dir / target_path(kind, variant, name)`, legt Elternordner an, wirft `FileExistsError`, wenn das Ziel belegt ist (gleiche Haltung wie `build_mod`, `:188-189`) |
| `anvil/mainwindow.py` | **neu:** `_stray_preset_mods(plugin, entries) -> dict[str, list[str]]` — direkt neben `_preset_mod_names` (`:2220`), gefüttert aus demselben Index-Durchlauf. **neu:** `_report_stray_presets(fundstellen)` — Glocke + Log, Muster von `_on_deploy_gaps` (`:9216-9234`). **neu:** `_fix_stray_preset(mod_name)` — Rückfrage, ggf. `_ask_preset_variant` (`:2199`), verschieben, `invalidate_and_rescan`, `_reload_mod_list`, `_do_redeploy`. Erweiterung: `_split_presets` (`:2286-2299`) ruft die Erkennung mit auf; Kontextmenü (`:4495-4530`) bekommt einen Eintrag, der nur bei verirrten Presets aktiv ist |
| `anvil/models/mod_list_model.py` | `ModRow` bekommt `has_stray_preset: bool` (Vorbild: `is_foreign`, `:80`); `mod_entry_to_row` (`:83-122`) reicht es durch; `ToolTipRole` auf `COL_NAME` zeigt `tooltip.stray_preset` (Vorbild: `foreign.tooltip`, `:391-392`); **keine** eigene Hintergrundfarbe — Warnfarbe ist für fremde Mods vergeben |
| `anvil/core/mod_entry.py` | `ModEntry` bekommt das Feld, das der Row-Bau abgreift (Vorbild `is_foreign`, `:41` Umfeld) |
| `anvil/locales/*.json` (**7 Dateien**) | neue Schlüssel, siehe 5.5 |
| `tests/test_verirrte_presets.py` | neu, siehe 5.6 |

**Nicht angefasst:** `mod_deployer.py`, `GameDeployRoutes`, `mod_installer.py`,
`diagnostics.py`, Cover-Bilder, REDmod, redprelauncher.

### 5.3 Signal-Flow

```
_reload_mod_list / _on_mods_reordered
  └─ _split_presets(plugin, visible_entries)          mainwindow.py:2286
       ├─ _preset_mod_names(...)                      :2220   (unverändert)
       └─ _stray_preset_mods(...)            NEU      dict{Mod: [rel, …]}
            ├─ Markierung an die ModRow                → Tooltip in der Liste
            └─ _report_stray_presets(...)     NEU
                 ├─ self._notification_center.add("warning", …)   (wie :9227)
                 └─ self._log_panel.add_log("warning", …)          (wie :9232)

Rechtsklick auf die Mod  →  Kontextmenü „Preset einsortieren"
  └─ _fix_stray_preset(mod_name)              NEU
       ├─ cp.detect_variant(datei, kind)              character_presets.py:70
       ├─ leer? → _ask_preset_variant(…)              mainwindow.py:2199
       ├─ QMessageBox.question  (Quelle → Ziel im Klartext)
       ├─ cp.fix_stray_path(...)              NEU     shutil.move im Mod-Ordner
       ├─ self._mod_index.invalidate_and_rescan(name) modindex.py:206
       ├─ self._reload_mod_list()                     → Mod wandert in den Presets-Bereich
       └─ self._do_redeploy()                         → purge räumt die alte Datei weg
```

Es wird **kein neues Qt-Signal** gebraucht. Die Glocke und das Kontextmenü sind
vorhanden, `preset_context_menu_requested` (`mod_list.py:1651-1660`) bleibt
unverändert — der neue Eintrag hängt im **Mod-Listen**-Menü, weil die verirrte
Mod ja gerade noch nicht im Presets-Bereich steht.

### 5.4 Gemeldet wird einmal, nicht bei jedem Neuzeichnen

`_split_presets` läuft an zwei Stellen (`:2028`, `:7401`) und zusätzlich nach
jedem Umsortieren. Ohne Bremse käme bei jedem Klick eine neue Glockenmeldung.
Lösung: Die zuletzt gemeldete Menge in `self._stray_preset_namen` merken (wie
`self._preset_namen`, `:415`) und nur melden, wenn sich die Menge geändert hat
oder die Instanz gewechselt wurde. Beim Instanzwechsel wird sie geleert — an
derselben Stelle wie `self._preset_namen = set()` (`:1701`).

### 5.5 Neue tr()-Schlüssel

**Es gibt 7 Locale-Dateien**, nachgezählt per Glob über `anvil/locales/*.json`:
`de, en, es, fr, it, pt, ru`. Die Testsuite führt dieselben sieben:
`tests/test_translations.py:8`, `tests/test_preset_bereich.py:213`. Die im
Bericht genannten „6 Sprachen" (auch in `CLAUDE.md`) sind veraltet — die
Checkliste vor dem Commit muss **7** sagen.

| Schlüssel | Deutscher Text (Vorschlag) |
|---|---|
| `preset.stray_title` | `Preset liegt falsch` |
| `preset.stray_prompt` | `„{file}" liegt im Ordner von „{mod}" an einer Stelle, an der {kind} nicht danach sucht.\n\nAnvil verschiebt die Datei innerhalb des Mod-Ordners:\n\nVon:  {from}\nNach: {to}\n\nAm Spielordner ändert sich dabei nichts. Verschieben?` |
| `preset.stray_moved` | `„{name}" eingeräumt — das Preset wirkt ab dem nächsten Ausrollen` |
| `preset.stray_failed` | `Verschieben fehlgeschlagen: {error}` |
| `preset.stray_exists` | `Am Zielort liegt bereits „{name}". Es wurde nichts verändert.` |
| `context.fix_preset` | `Preset einsortieren` |
| `notifications.stray_presets` | `Presets liegen an einer Stelle, an der das Spiel nicht sucht ({count})` |
| `tooltip.stray_preset` | `Diese Mod enthält ein Preset an einer Stelle, an der das Spiel nicht danach sucht.\nRechtsklick → „Preset einsortieren" rückt es gerade.` |

Alle acht Schlüssel in **allen sieben** Dateien. Kein roher Schlüssel darf in
der Oberfläche stehen — genau dieser Fehler ist beim letzten Umbau passiert
(`stand-2026-08-12.md:34-36`).

### 5.6 Tests

**Bestehende Tests zum Thema** (nicht löschen, erweitern):

| Datei | Inhalt |
|---|---|
| `tests/test_preset_bereich.py` | Erkennung `is_preset_mod` (`:26-81`), darunter `test_preset_am_falschen_ort_ist_kein_preset` (`:55-57`) — der Ausgangspunkt; Anzeigename (`:84-106`); Sprachschlüssel (`:203-223`) |
| `tests/test_character_presets.py` | `detect_variant`, `target_path`, `build_mod`, `find_presets` (`:46-158`); Einbau ins Hauptfenster als Quelltextprüfung (`:167-273`); Sprachschlüssel (`:275-290`) |
| `tests/test_cyberpunk_r6_routing.py` | Vorlage für „Datei landet wirklich am richtigen Ort", inklusive echtem Deployer-Durchlauf (`:117-146`) |
| `tests/test_translations.py` | sieben Sprachen, alle Schlüssel auflösbar |

**Neu: `tests/test_verirrte_presets.py`**

1. `stray_presets` findet `["Bad Corpo.preset"]` und liefert den Pfad zurück.
2. `stray_presets` liefert **leer** für ein richtig einsortiertes Preset.
3. `stray_presets` liefert **leer** für `FemV - RE9 Grace`
   (`archive/pc/mod/00_FacePreset_RE9Grace_xBaebsae.archive` + `meta.ini`) —
   der Fall, der ausdrücklich **nicht** gemeldet werden darf.
4. `meta.ini`, versteckte Dateien und `codes.txt` lösen keine Meldung aus.
5. Groß-/Kleinschreibung und `\`-Trenner: `BAD CORPO.PRESET` wird gefunden
   (Vorbild `test_preset_bereich.py:70-76`).
6. Ein Spiel ohne `PresetKind` liefert nie einen Fund (leere `kinds`-Liste).
7. Ein Ordner, der nur ähnlich heißt (`…character-presets-backup/x.preset`),
   zählt als verirrt (Gegenstück zu `test_preset_bereich.py:79-81`).
8. `detect_variant` auf dem echten Inhalt: eine Datei mit zwei weiblichen
   Markern und ohne männliche ergibt `female`.
9. `fix_stray_path` verschiebt in `tmp_path` nach
   `…/character-presets/female/<name>.preset`, die Wurzel ist danach leer.
10. `fix_stray_path` wirft `FileExistsError`, wenn am Ziel schon etwas liegt,
    und lässt die Quelle unangetastet.
11. **Durchstich mit echtem Deployer** (Vorbild
    `test_cyberpunk_r6_routing.py:117-146`): vor der Reparatur landet die Datei
    als `<spiel>/Bad Corpo.preset`; nach `fix_stray_path` landet sie unter
    `<spiel>/bin/x64/.../character-presets/female/Bad Corpo.preset` und **nicht
    mehr** in der Wurzel.
12. `is_preset_mod` liefert für den reparierten Ordner `True` — die Mod wandert
    also wirklich in den Presets-Bereich.
13. Sprachschlüssel: alle acht neuen Schlüssel in allen sieben Dateien,
    Platzhalter `{mod}`, `{file}`, `{from}`, `{to}`, `{count}`, `{name}`,
    `{error}` vorhanden (Vorbild `test_preset_bereich.py:213-223`).
14. Quelltextprüfung: `_split_presets` ruft die Erkennung auf, und der
    Kontextmenü-Eintrag hängt an `context.fix_preset` (Vorbild
    `test_character_presets.py:172-183`).

---

## 6. Verwandte Funktionen (geprüft)

| Funktion | Gleicher Fix nötig? |
|---|---|
| `is_preset_mod` (`character_presets.py:142`) | **Nein.** Sie urteilt richtig — „Bad Corpo" ist als Ordner eben kein sauberer Preset-Mod. Ändert man sie, landet die Mod im Presets-Bereich, ohne dass die Datei je im Spiel ankommt. Das wäre schlimmer als jetzt. |
| `mod_has_presets` (`mod_detail_dialog.py:1156-1170`) | **Nein**, aber im Auge behalten: sie sucht ortsblind per `rglob` und liefert für „Bad Corpo" schon heute `True`. Genau diese Asymmetrie zu `is_preset_mod` ist der Fingerzeig. Für den Voraussetzungs-Tab ist das Verhalten richtig. |
| `find_presets` (`character_presets.py:56`) | **Nein.** Sucht bewusst überall im Paket — deshalb greift der Installationsweg für neue Pakete schon korrekt. |
| `_install_presets_from` (`mainwindow.py:2353`) | **Nein.** Fängt Presets in der Paketwurzel bereits ab (`rglob`). Das Problem betrifft nur Altbestand. |
| `_preset_variant` (`mainwindow.py:2243-2264`) | **Nein**, aber wiederverwenden: nach der Reparatur liefert sie die Variante für die Spalte, ohne Änderung. |
| `route_deploy_path` / `GameDeployRoutes` | **Nein** — siehe 4.2. Bewusst nicht angefasst. |
| `_fix_se_plugins_dir` (`mod_installer.py:720`) | **Nein.** Anderes Spiel (Bethesda), anderer Zeitpunkt (Installation). Dient nur als Vorbild. |
| `detect_problems` (`diagnostics.py:141`) | **Nein** für diesen Punkt. Später möglich, braucht aber eine erweiterte Signatur. |
| Punkt 5 (Presets-Trenner heißt falsch) | **Getrennt halten.** „Bad Corpo" steht unter dem Trenner „Presets", weil dieser der letzte der Liste ist (`stand-2026-08-12.md:109-113`) — das ist eine andere Baustelle. Nach dem Geraderücken verschwindet die Mod aus der sichtbaren Liste, der falsch beschriftete Trenner bleibt. |

---

## 7. ✅ Akzeptanz-Kriterien

- [ ] 1. Wenn die Cyberpunk-Instanz geladen wird und `Bad Corpo` unverändert in
      der Wurzel liegt, erscheint an der Glocke **eine** Warnmeldung mit dem
      Text aus `notifications.stray_presets` und der Anzahl 1.
- [ ] 2. Wenn dieselbe Liste danach durch Umsortieren oder Filtern neu gezeichnet
      wird, kommt **keine zweite** Meldung dazu (Zähler an der Glocke bleibt).
- [ ] 3. Wenn der Mauszeiger in der Mod-Liste auf `Bad Corpo` steht, zeigt der
      Tooltip den Text aus `tooltip.stray_preset`.
- [ ] 4. Wenn der Mauszeiger auf `FemV - RE9 Grace` steht, erscheint **kein**
      solcher Tooltip, und die Mod taucht in keiner Warnmeldung auf.
- [ ] 5. Wenn der Nutzer `Bad Corpo` rechtsklickt, ist „Preset einsortieren"
      im Menü **aktiv**; bei jeder anderen Mod ist der Eintrag ausgegraut oder
      nicht vorhanden.
- [ ] 6. Wenn der Nutzer „Preset einsortieren" wählt, erscheint eine Rückfrage,
      die Quell- **und** Zielpfad im Klartext nennt.
- [ ] 7. Wenn der Nutzer die Rückfrage mit „Nein" beantwortet, liegt
      `Bad Corpo/Bad Corpo.preset` unverändert an derselben Stelle.
- [ ] 8. Wenn der Nutzer bestätigt, liegt die Datei danach unter
      `Bad Corpo/bin/x64/plugins/cyber_engine_tweaks/mods/AppearanceChangeUnlocker/character-presets/female/Bad Corpo.preset`,
      und in der Ordnerwurzel liegt nur noch `meta.ini`.
- [ ] 9. Die Variante `female` wird ohne Rückfrage aus dem Dateiinhalt bestimmt
      (zwei weibliche Marker, kein männlicher) — es geht **kein**
      Geschlechtsdialog auf.
- [ ] 10. Wenn ein Preset weder über Pfad noch Name noch Inhalt zuzuordnen ist,
      geht der vorhandene Geschlechtsdialog auf; „Abbrechen" lässt die Datei
      unangetastet.
- [ ] 11. Nach dem Verschieben verschwindet `Bad Corpo` aus der Mod-Liste und
      steht im Bereich „ACU-Presets", Spalte „Variante" zeigt „Weiblich"; die
      Zählung in der Bereichsleiste steigt von 7 auf 8.
- [ ] 12. Nach dem nächsten Ausrollen liegt im Spielordner
      `bin/x64/plugins/cyber_engine_tweaks/mods/AppearanceChangeUnlocker/character-presets/female/Bad Corpo.preset`
      und **keine** Datei `<Spielordner>/Bad Corpo.preset` mehr.
- [ ] 13. Wenn am Zielort bereits eine gleichnamige Datei liegt, erscheint
      `preset.stray_exists`, und die Quelldatei bleibt, wo sie ist.
- [ ] 14. Wenn der Mod-Ordner schreibgeschützt ist, erscheint
      `preset.stray_failed` mit dem Systemfehler; Anvil stürzt nicht ab und die
      Liste bleibt bedienbar.
- [ ] 15. Bei einer Instanz ohne Presets (z. B. Skyrim SE) erscheint keine
      Meldung, kein Tooltip und kein Menüeintrag.
- [ ] 16. Beim Wechsel von Cyberpunk zu einer anderen Instanz und zurück steht
      die Warnung nur einmal an der Glocke, nicht doppelt.
- [ ] 17. Alle acht neuen tr()-Schlüssel liegen in allen **sieben** Locale-Dateien
      (de, en, es, fr, it, pt, ru); `tests/test_translations.py` bleibt grün.
- [ ] 18. `tests/test_verirrte_presets.py` läuft mit allen 14 Fällen grün,
      darunter der Deployer-Durchstich (Kriterium 12 als Test).
- [ ] 19. Die bestehenden Tests `tests/test_preset_bereich.py` und
      `tests/test_character_presets.py` laufen unverändert grün — insbesondere
      `test_preset_am_falschen_ort_ist_kein_preset`.
- [ ] 20. Die Gesamtsuite bleibt auf dem Stand von `8179975` oder besser
      (672 grün, 1 übersprungen).
- [ ] 21. `restart.sh` startet ohne Fehler (Log frei von Traceback, NameError,
      ImportError, AttributeError).

---

## 8. UNSICHER

1. **Liest ACU Presets auch ohne Geschlechtsordner?** Nicht belegbar. Die
   Auswertung steckt in
   `ACU - Character Customization/red4ext/plugins/ACU/acu_rs.dll`; die
   `init.lua` daneben ist ein 10-Zeilen-Platzhalter („Dummy Mod so CET doesn't
   complain") und enthält das Wort „preset" nicht. Alle sechs mitgelieferten
   Presets liegen in `character-presets/female/` bzw. `male/`. Deshalb sieht
   der Plan die Variante vor — das ist der belegbar funktionierende Aufbau.
   `is_preset_mod` lässt ein Preset direkt unter `character-presets/` gelten
   (`tests/test_preset_bereich.py:32-33`); ob das Spiel es dort findet, ist
   damit **nicht** bewiesen.
2. **Wirkt das geradegerückte „Bad Corpo" im Spiel?** Ungeprüft. Der Beweis geht
   nur über einen Spielstart: Preset abhaken → Spiel starten → im Charaktermenü
   muss es auftauchen bzw. verschwinden (Verfahren aus
   `stand-2026-08-12.md:155-157`).
3. **Ob im Spielordner heute eine verwaiste `Bad Corpo.preset` liegt.** Gemessen:
   nein — Glob auf `<Spielordner>/*.preset` findet nichts. Ob sie dort einmal
   lag und durch einen Purge verschwand oder ob seit dem 11.08. gar nicht
   ausgerollt wurde, ist aus den vorhandenen Dateien nicht zu entscheiden.
4. **Ob es außerhalb der Cyberpunk-Instanz verirrte Presets gibt.** Geprüft
   wurde nur die Cyberpunk-Instanz — sie ist die einzige mit `PresetKind`.
   Andere Instanzen können per Definition keine haben.
5. **Wie viele Mods die Instanz insgesamt hat.** Nicht nachgezählt; der Bericht
   nennt 536 (`stand-2026-08-12.md:22`). Für diesen Punkt ohne Belang — gezählt
   wurden die 14 `.preset`-Dateien in 9 Ordnern.
6. **Ob der Mod-Index zum Zeitpunkt der Erkennung immer aktuell ist.**
   `_preset_mod_names` liest den Index (`mainwindow.py:2238`), nicht die Platte.
   Verschiebt jemand die Datei außerhalb von Anvil, wird der Fund erst nach
   einem Neuaufbau des Index sichtbar. Der Deployer hat für genau diesen Fall
   eine Nachlese (`mod_deployer.py:686, 720-727`); ob die Erkennung ebenfalls
   eine braucht, sollte beim Bauen entschieden werden.
