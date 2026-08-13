# Punkt 5 — Der Presets-Trenner sammelt alles ein

Datum: 2026-08-13
Art: Analyse + Feature-Spec (kein Code geändert)
Instanz der Messung: `Cyberpunk 2077`, Profil `Vanilla`

---

## Kurzfassung

Der Trenner heißt `Presets_separator`, ist aber schlicht **der letzte Trenner
der Datei**. Alles, was Anvil ans Ende der globalen `modlist.txt` hängt, wird
ihm zugeschlagen — heute 19 Einträge, davon nur 7 echte Presets.

Das Problem ist **nicht** presetspezifisch und **nicht** neu: im Sicherungsstand
`modlist.txt.vor_acu` hingen dieselben 10 Framework-Ordner unter dem damals
letzten Trenner `bekliedung- ebb - ebbp_separator`
(`/home/mob/.anvil-organizer/instances/Cyberpunk 2077/.profiles/modlist.txt.vor_acu:508-522`).
Das Schild wechselt, das Verhalten bleibt.

Empfehlung: **Weg a — ein benannter Auffang-Trenner am Ende**, gesteuert über
einen Instanz-Schlüssel in `.anvil.ini` (genau wie `preset_separator` heute
schon). Weg b (Anfang) wird ausdrücklich abgelehnt, Begründung in Abschnitt 3.

---

## 1. Was passiert heute wirklich?

### 1.1 Alle Stellen, die einen Eintrag in die Ladereihenfolge schreiben

| # | Auslöser | Datei:Zeile | Zielposition |
|---|---|---|---|
| 1 | Archiv installieren (Downloads-Tab, Drop ohne Zielzeile, Reinstall, Framework-Reinstall) | `anvil/mainwindow.py:3991` | `mod_names.append(...)` → **ans Ende der globalen Liste** |
| 2 | Archiv auf eine bestimmte Zeile gezogen | `anvil/mainwindow.py:3970-3989` | vor den Ordnernamen der Zielzeile; zweites und jedes weitere Archiv direkt hinter das vorige (`_prev_inserted_name`) |
| 3 | Derselbe Weg im Altsystem (kein globales `modlist.txt`) | `anvil/mainwindow.py:3997` / `4000` | `insert_mod_in_modlist(...)` bzw. `add_mod_to_modlist(...)` |
| 4 | Kontextmenü „Mod installieren…" | `anvil/mainwindow.py:5685` | `add_mod_to_modlist(self._current_profile_path, ...)` — **schreibt die Profil-Datei, nicht die globale** (siehe 1.3) |
| 5 | Kontextmenü „Leere Mod anlegen" | `anvil/mainwindow.py:5725` | dito |
| 6 | Preset aus einem Archiv herausgelöst | `anvil/mainwindow.py:2411-2415` | `order.index(separator) + 1` — direkt hinter den Preset-Trenner, also **richtig** |
| 7 | Preset-Trenner wird zum ersten Mal angelegt | `anvil/mainwindow.py:2181-2184` | `order.append(folder)` → **ans Ende** |
| 8 | Trenner von Hand anlegen | `anvil/mainwindow.py:4711-4717` über `_separator_insert_pos()` (`anvil/mainwindow.py:2266-2284`) | vor die Auswahl, ohne Auswahl ganz oben |
| 9 | Sammlung importieren | `anvil/core/collection_io.py:446-453` | alles, was auf der Platte liegt und nicht in der Sammlung steht, **ans Ende** |
| 10 | Script Merger | `anvil/widgets/script_merger_dialog.py:537-540` | `order.insert(0, "_merged_")` — bewusst Platz 1 |
| 11 | Umsortieren per Drag & Drop | `anvil/mainwindow.py:2729-2764` → `_write_current_modlist()` (`anvil/mainwindow.py:2596-2618`) | schreibt die **komplette** Liste neu; Unsichtbares wird über `merge_hidden_order()` (`anvil/core/mod_list_io.py:515-558`) an seinen alten Nachbarn zurückgesetzt |

Merke: „ans Ende" heißt immer **ans Ende der ganzen Datei**
`.profiles/modlist.txt`, nie „ans Ende eines Trenners". Eine Zielposition gibt
es nur bei Weg 2 (Drop auf eine Zeile) und Weg 6 (Presets).

Nebenbefund zur Dokumentation: der Docstring von `add_mod_to_modlist()` sagt
„Append a mod at the end of modlist.txt (**highest priority**)"
(`anvil/core/mod_list_io.py:99`). Das ist falsch herum — laut Kopf derselben
Datei gilt „first line = highest priority" (`anvil/core/mod_list_io.py:17-18`).
Reine Doku-Frage, aber irreführend.

### 1.2 Wo Anvil Mods entdeckt, die nicht in der `modlist.txt` stehen

`scan_mods_directory()` in `anvil/core/mod_entry.py:207-299`:

- Schritt 3 (`:280-287`) baut die Einträge in der Reihenfolge der Datei.
- Schritt 4 (`:289-297`) nimmt **alle Ordner unter `.mods/`, die nicht in der
  Liste stehen**, sortiert sie alphabetisch (`sorted(on_disk - seen)`) und
  hängt sie **hinten an** — mit `enabled=True`.
- Abschaltbar über die Einstellung `ModList/show_external_mods`
  (`anvil/mainwindow.py:1995`, `7371`) → `include_external=False`.

Gespeichert wird dabei nichts. Die Position wird erst beim nächsten Schreiben
festgeschrieben — also beim ersten Drag & Drop oder Häkchen
(`_write_current_modlist`, `anvil/mainwindow.py:2596`). Genau deshalb wandern
solche Zugänge lautlos unter den letzten Trenner.

Zum Commit `07e20c6` („Mods verschwinden nicht mehr stillschweigend aus dem
Spiel"): der betraf laut `CHANGELOG.md:14` die **Dateiliste im Mod-Index**
(Änderungen eine Ebene tiefer wurden nicht bemerkt), nicht die Zuordnung zur
`modlist.txt`. Der zugehörige Test ist
`tests/test_modindex_aktualitaet.py:177-193` — er prüft, dass eine dem Index
unbekannte Mod trotzdem ausgerollt wird. Die Stelle, die Mods **ohne
Listeneintrag** aufnimmt, ist die oben genannte in `mod_entry.py`.

### 1.3 Echter Nebenfund: zwei Wege schreiben in die falsche Datei

`_ctx_install_mod` (`anvil/mainwindow.py:5685`) und `_ctx_create_empty_mod`
(`anvil/mainwindow.py:5725`) rufen
`add_mod_to_modlist(self._current_profile_path, ...)` auf. Diese Funktion
schreibt `<profil>/modlist.txt` (`anvil/core/mod_list_io.py:96-116` →
`write_modlist`, `:70-93`). Gelesen wird aber die globale Datei, sobald sie
existiert (`anvil/core/mod_entry.py:249-254`). Folge:

1. Der Eintrag landet in einer Datei, die niemand mehr liest.
2. Die Mod gilt beim nächsten Aufbau als „neu" und wird über Schritt 4
   alphabetisch **ans Ende** gehängt — unter den letzten Trenner.
3. Zusätzlich entsteht eine Alt-Datei im Profilordner, die die
   Migration nie wieder anfasst (`migrate_to_global_modlist` steigt bei
   vorhandener globaler Datei sofort aus, `anvil/core/mod_list_io.py:465-469`).

Belegbar vorhanden sind solche Profil-Dateien in Marcs Instanz:
`.profiles/Default/modlist.txt`, `.profiles/Vanilla/modlist.txt`,
`.profiles/ebbp/modlist.txt`. `.profiles/Vanilla/modlist.txt:1-29` enthält eine
völlig andere, viel kürzere Reihenfolge als die globale Datei — sie wirkt
nirgends.

> Ob diese Dateien wirklich aus den beiden Kontextmenü-Wegen stammen, ist nicht
> beweisbar (siehe „UNSICHER"). Der Code-Pfad selbst ist es.

---

## 2. Die echten Daten

Pfade **nicht** geraten, sondern aus der Konfiguration gelesen:

- `QSettings` → `/home/mob/.config/AnvilOrganizer/AnvilOrganizer.conf:2`:
  `base_dir=/home/mob/.anvil-organizer` (Flatpak-Kopie identisch:
  `/home/mob/.var/app/com.github.Marc1326.AnvilOrganizer/config/AnvilOrganizer/AnvilOrganizer.conf:2`)
- aktive Instanz → `/home/mob/.anvil-organizer/.current:1` = `Cyberpunk 2077`
- Instanz-Konfiguration →
  `/home/mob/.anvil-organizer/instances/Cyberpunk 2077/.anvil.ini`
  - `:9` `preset_separator=Presets_separator`
  - `:10` `selected_profile=Vanilla`
  - `:16` `profiles_directory=%INSTANCE_DIR%/.profiles`
- Ladereihenfolge →
  `/home/mob/.anvil-organizer/instances/Cyberpunk 2077/.profiles/modlist.txt`
  (Kopf `# Managed by Anvil Organizer v2`, 536 Einträge in den Zeilen 2–537)

### 2.1 Alle Trenner in Reihenfolge

| # | Trenner (Ordnername) | Dateizeile | Mods darunter |
|---|---|---|---|
| 1 | `wichtige Reihenfolge_separator` | 2 | 30 |
| 2 | `bekleidubg - ebbp_separator` | 33 | 2 |
| 3 | `Body_separator` | 36 | 2 |
| 4 | `main_separator` | 39 | 25 |
| 5 | `ads_separator` | 65 | 6 |
| 6 | `bekleidung - solo_separator` | 72 | 13 |
| 7 | `bekleidung - vanilla_separator` | 86 | 73 |
| 8 | `bekleidung -ebb_separator` | 160 | **0** |
| 9 | `body - shoes- shorts- vanilla_separator` | 161 | 64 |
| 10 | `atelier-shop_separator` | 226 | 55 |
| 11 | `gameplay_separator` | 282 | 10 |
| 12 | `optimierung_separator` | 293 | 60 |
| 13 | `romance_separator` | 354 | 12 |
| 14 | `npc_separator` | 367 | 15 |
| 15 | `bekleidung - all - hyst - angel_separator` | 383 | 27 |
| 16 | `ebb_separator` | 411 | 67 |
| 17 | `naked_separator` | 479 | 11 |
| 18 | `Angel - EVB - EBB - EBBP - Vanilla- Solo_separator` | 491 | 22 |
| 19 | `bekliedung- ebb - ebbp_separator` | 514 | 3 |
| 20 | `Presets_separator` | 518 | **19** |

Summe: 20 Trenner + 516 Mods = 536 Einträge. Vor dem ersten Trenner steht
nichts.

### 2.2 Was konkret unter `Presets_separator` hängt (Zeilen 519–537)

| Dateizeile | Eintrag | Was es wirklich ist |
|---|---|---|
| 519 | `ACU-Preset - Mona Chains (female)` | Preset |
| 520 | `ACU-Preset - Kaori (female)` | Preset |
| 521 | `ACU-Preset - Aiko (female)` | Preset |
| 522 | `ACU-Preset - Shaundi - Female V Preset (female)` | Preset |
| 523 | `ACU-Preset - isabella (female)` | Preset |
| 524 | `ACU-Preset - cloev2 (female)` | Preset |
| 525 | `Bad Corpo` | Mod-Ordner mit `Bad Corpo.preset` **in der Wurzel** |
| 526 | `ACU-Preset - Grace (female)` | Preset |
| 527 | `Fiore` | enthält nur `Fiore.txt` |
| 528 | `ArchiveXL` | Framework |
| 529 | `CET 1.37.1 - Scripting fixes` | Framework |
| 530 | `Codeware` | Framework |
| 531 | `Native Settings UI 1.96` | Framework |
| 532 | `RED4ext` | Framework |
| 533 | `RedData` | Framework |
| 534 | `RedFileSystem` | Framework |
| 535 | `TweakXL` | Framework |
| 536 | `mod_settings_v0.2.21` | Framework |
| 537 | `redscript` | Framework |

**Stimmt der Bericht?** Im Kern ja, in einer Zahl nicht ganz:

- „`Bad Corpo`, `Fiore` und alle 11 Frameworks" — es sind **10 Mod-Ordner**,
  die auf die Framework-Muster passen. `GameDirectInstallMods` in
  `anvil/plugins/games/game_cyberpunk2077.py:111-123` enthält 11 Muster;
  `Cyber Engine Tweaks` trifft keinen Ordner, weil der Ordner
  `CET 1.37.1 - Scripting fixes` heißt und über das Muster `CET 1.37.1`
  erfasst wird (Abgleichregel: `matches_direct_install`,
  `anvil/core/mod_deployer.py:88-106` — Präfix, danach kein Buchstabe).
- 7 Presets, nicht 6 — `ACU-Preset - Grace (female)` steht zwischen
  `Bad Corpo` und `Fiore`.

Warum `Bad Corpo` und `Fiore` überhaupt in der Liste stehen bleiben:
- `Bad Corpo` → `/home/mob/.anvil-organizer/instances/Cyberpunk 2077/.mods/Bad Corpo/`
  enthält `Bad Corpo.preset` **direkt in der Wurzel**, nicht unter dem
  ACU-Zielpfad — die Inhaltsprüfung erkennt es deshalb nicht als Preset
  (Zielpfad-Regel aus `PresetKind.target`, `anvil/core/character_presets.py:26-48`).
- `Fiore` → enthält nur `Fiore.txt`, also gar keine Preset-Datei.

(Punkt 3 des Loops — die Erkennung verirrter Presets — wird parallel bearbeitet
und hier bewusst nur gelesen, nicht angefasst.)

### 2.3 Beleg, dass es nicht am Wort „Presets" liegt

`/home/mob/.anvil-organizer/instances/Cyberpunk 2077/.profiles/modlist.txt.vor_acu:508-522`:
Damals gab es weder `Presets_separator` noch `Bad Corpo` oder `Fiore` — und
dieselben 10 Framework-Ordner standen am Dateiende unter dem letzten Trenner
`bekliedung- ebb - ebbp_separator`. Derselbe Befund in
`modlist.txt.bak:509`/`:518`.

---

## 3. Welcher Weg ist der richtige?

Bewertungsmaßstäbe: Priorität (die **erste** Mod gewinnt), Überraschungs­freiheit
für den Anwender, Aufwand.

### a) Auffang-Trenner am Ende („Nicht einsortiert")

- **Priorität:** neue Mods bekommen die niedrigste Priorität. Bei Konflikten
  verlieren sie zunächst — sichtbar, nachvollziehbar, jederzeit per Drag & Drop
  oder „In Trenner verschieben" (`anvil/mainwindow.py:4487`, `6146-6186`)
  korrigierbar.
- **Überraschungsfreiheit:** hoch. Die Position ändert sich gegenüber heute
  **nicht** — nur das Schild darüber stimmt endlich. Keine bestehende Mod wird
  verschoben.
- **Aufwand:** klein. Eine Zielpositions-Funktion, ein Instanz-Schlüssel, ein
  Aufruf an vier Stellen.
- **Cyberpunk-Sonderfall:** durch die Archiv-Durchnummerierung (`8179975`,
  `GamePakLoadOrderFirstWins = True`,
  `anvil/plugins/games/game_cyberpunk2077.py:78-82`) heißt „unten" jetzt
  wirklich „verliert". Neue Mods wirken also erst nach dem Hochschieben — das
  ist ehrlich und sichtbar, statt zufällig.

### b) Neue Mods an den Anfang

- **Priorität:** jede frisch installierte Mod bekäme sofort **höchste**
  Priorität und überschriebe alles. Bei Cyberpunk erhielte sie zusätzlich die
  Nummer `000_` — das ist exakt der Fall `FemV - RE9 Grace` gegen
  `Unique Eyes - Core`, der Marc die Augen gekostet hat
  (`docs/stand-2026-08-12.md:160-166`).
- **Überraschungsfreiheit:** sehr niedrig. Eine 300-Mod-Ordnung würde von jedem
  Neuzugang von oben her aufgebrochen.
- **Urteil: abgelehnt.**

### c) Nur umbenennen, Anvil ändert nichts

- **Aufwand:** null.
- **Wirkung:** null. Marc könnte den Trenner heute in „Rest" umbenennen — beim
  nächsten Preset-Fund legt Anvil über `_ask_preset_separator()`
  (`anvil/mainwindow.py:2155-2197`) wieder einen eigenen an und hängt ihn per
  `order.append` erneut ans Ende. Der Sammel-Effekt bliebe, nur wandert das
  falsche Schild eine Zeile weiter.
- **Urteil: löst nichts,** taugt aber als Teil der Migration (Abschnitt 4.2).

### d) Automatisch nach Typ einsortieren

- **Machbar?** Teilweise: Frameworks erkennt Anvil sicher
  (`GameDirectInstallMods` + `matches_direct_install`, dazu die Heuristik in
  `anvil/plugins/base_game.py:689`). Für alles andere gibt es keine belastbare
  Typinformation — die Nexus-Kategorie steht erst nach dem Metadaten-Abruf fest
  und passt selten zu Marcs selbstgebauten Trennern („bekleidung - solo",
  „atelier-shop").
- **Überraschungsfreiheit:** niedrig. Anvil würde Mods in Trenner einsortieren,
  die der Anwender nach ganz eigener Logik gebaut hat.
- **Zusatzproblem:** die 10 Cyberpunk-Frameworks sind gesperrt und deshalb gar
  nicht in der Liste sichtbar (`_unlocked_framework_mods`,
  `anvil/mainwindow.py:2492-2515`). Ein „Framework-Trenner" wäre ein Trenner
  für unsichtbare Einträge.
- **Urteil: nicht jetzt.** Höchstens später als abschaltbare Zusatzregel oben
  auf a).

### Empfehlung

**a)**, mit zwei Ergänzungen:
1. Der Auffang-Trenner wird **nicht** beim Start angelegt, sondern erst beim
   ersten Neuzugang ohne Zielposition. Instanzen ohne Zugänge bleiben
   unverändert.
2. Einmalig, auf Nachfrage: die Einträge unter dem Preset-Trenner, die keine
   Presets sind, in den Auffang-Trenner umziehen (Abschnitt 4.2).

---

## 4. Auswirkungen

### 4.1 Tests

Es gibt keine Datei `tests/test_modlist*.py`. Die Reihenfolgen-Logik liegt
verstreut:

| Datei | Was dort geprüft wird | Bricht durch a)? |
|---|---|---|
| `tests/test_preset_bereich.py:111-152` | `merge_hidden_order()` — Verstecktes bleibt hinter seinem Trenner | nein, unberührt |
| `tests/test_preset_bereich.py:680-705` | `_separator_insert_pos()` — neuer Trenner vor der Auswahl | nein |
| `tests/test_preset_bereich.py:722-747` | `_write_current_modlist()` schreibt Presets mit | nein |
| `tests/test_custom_instance_paths.py:28-45` | `scan_mods_directory()` mit eigenen Pfaden | **prüfen** — wenn dort eine Mod ohne Listeneintrag erwartet wird, ändert sich ihre Position |
| `tests/test_modindex_aktualitaet.py:177-193` | unbekannte Mod wird trotzdem ausgerollt | nein |
| `tests/test_archive_load_order*.py`, `test_pak_load_order*.py`, `test_copy_deploy_order.py`, `test_ba2_reihenfolge.py` | Deploy-Reihenfolge aus vorgegebener Liste | nein, alle setzen die Liste selbst per `write_global_modlist` |
| `tests/test_translations.py:8` | 7 Sprachen, jeder Schlüssel auflösbar | **ja**, sobald neue `tr()`-Schlüssel dazukommen |

Neue Tests sind Pflicht (siehe Akzeptanzliste), insbesondere eine
Mutationsprobe: „Zielposition durch `len(order)` ersetzen → Test muss rot
werden". Die Lehre aus dem letzten Loop war genau das
(`docs/stand-2026-08-12.md:197-200`).

### 4.2 Migration bestehender Instanzen

- Kein Zwang, kein automatisches Umsortieren beim Start. Der Auffang-Trenner
  entsteht erst beim ersten Neuzugang.
- **Einmaliges Angebot** (nur wenn ein Preset-Trenner laut `.anvil.ini`
  existiert und darunter Einträge liegen, die keine Presets sind): Dialog mit
  Namensliste, „Verschieben" / „So lassen". Bei „So lassen" wird die Frage über
  einen Instanz-Schlüssel dauerhaft stillgelegt.
- Die Preset-Erkennung dafür ist vorhanden (`_preset_mod_names()`,
  `anvil/mainwindow.py:2220-2245`) und wird **nur aufgerufen, nicht geändert** —
  Punkt 3 läuft parallel.
- `.anvil.ini` bekommt einen zusätzlichen Schlüssel; alte Dateien ohne diesen
  Schlüssel funktionieren unverändert (`load_instance` liefert ein flaches
  Dict, `anvil/core/instance_manager.py:357-372`).

### 4.3 Betrifft es nur Cyberpunk?

Nein. `scan_mods_directory()` und `_install_archives()` sind spielunabhängig.
Cyberpunk fällt nur auf, weil Marc dort 536 Einträge und 20 Trenner hat und die
Archiv-Nummerierung die Reihenfolge inzwischen wirklich ins Spiel bringt. BG3
geht über einen eigenen Weg (`_on_bg3_archives_dropped`,
`anvil/mainwindow.py:8334`, `anvil/core/bg3_mod_installer.py`) und bleibt
ausdrücklich unberührt.

---

## 5. Spec

### 5.1 User Stories

- Als Anwender möchte ich, dass ein Trenner nur das enthält, was sein Name
  verspricht — sonst suche ich Mods an der falschen Stelle.
- Als Anwender möchte ich sehen, was Anvil neu aufgenommen hat, ohne die
  ganze Liste durchzugehen.
- Als Anwender möchte ich, dass eine neu installierte Mod meine gewachsene
  Reihenfolge nicht von oben her umwirft.
- Als Anwender möchte ich den Auffang-Trenner wie jeden anderen behandeln
  können: umbenennen, einfärben, verschieben.

### 5.2 Betroffene Dateien

| Datei | Änderung |
|---|---|
| `anvil/core/mod_list_io.py` | neu: `catch_all_position(order, catch_all)` — liefert die Einfügeposition für einen Neuzugang (hinter dem Auffang-Trenner und seinen bisherigen Kindern, sonst `len(order)`). Docstring von `add_mod_to_modlist` richtigstellen (`:99`). |
| `anvil/core/mod_entry.py` | `scan_mods_directory(..., catch_all: str = "")`: Schritt 4 (`:289-297`) fügt Neuzugänge an der Auffang-Position ein statt sie anzuhängen |
| `anvil/mainwindow.py` | neu: `_catch_all_separator()` (liest `.anvil.ini`, prüft ob der Ordner noch existiert — Vorbild `_preset_separator()`, `:2135-2153`) und `_ensure_catch_all_separator()` (legt Ordner + `meta.ini` + Eintrag am Listenende an, Vorbild `_ask_preset_separator()`, `:2155-2197`, aber **ohne** Rückfrage). Aufruf an den Einfügestellen `:3991`, `:5685`, `:5725`, `collection_io`-Aufrufer; Weitergabe von `catch_all` an `scan_mods_directory` (`:1996`, `:7372`) |
| `anvil/mainwindow.py` (Fehlerbehebung 1.3) | `:5685` und `:5725` schreiben in die **globale** Liste, wenn `.profiles/modlist.txt` existiert |
| `anvil/core/collection_io.py:446-453` | Nicht-Sammlungs-Mods hinter den Auffang-Trenner statt ans blanke Ende |
| `anvil/locales/*.json` (**7 Dateien**) | neue Schlüssel, siehe 5.4 |
| `tests/test_auffang_trenner.py` (neu) | Positionslogik, Scan, Migration |

Der Preset-Weg (`:2411-2415`) bleibt unverändert — er setzt schon richtig ein.

### 5.3 Signal-Flow

```
Installation / Sammlung / Kontextmenü
        │
        ▼
 _ensure_catch_all_separator()          .anvil.ini: catchall_separator=<Ordner>
        │  (legt an, falls nicht vorhanden — Ordner + meta.ini + Listenende)
        ▼
 catch_all_position(order, name)  ──►  order.insert(pos, neue_mod)
        │
        ▼
 write_global_modlist()   →  .profiles/modlist.txt
        │
        ▼
 _reload_mod_list()  →  scan_mods_directory(catch_all=name)
        │                    └─ Schritt 4: Ordner ohne Eintrag ebenfalls an die Auffang-Position
        ▼
 _split_presets() → set_mods() → Anzeige
        │
        ▼
 (erst bei Drag & Drop / Häkchen)  _write_current_modlist() schreibt endgültig fest
```

### 5.4 Neue `tr()`-Schlüssel

Im Repo liegen **7** Locale-Dateien: `anvil/locales/de.json`, `en`, `es`, `fr`,
`it`, `pt`, `ru` (per Glob gezählt). `tests/test_translations.py:8` führt
dieselben 7 Sprachen. Die im Projekt kursierende Zahl „6" ist veraltet.

| Schlüssel | Deutsch |
|---|---|
| `separator.catch_all_default` | `Nicht einsortiert` |
| `status.catch_all_created` | `Trenner „{name}" angelegt — neue Mods landen dort` |
| `dialog.tidy_catch_all_title` | `Trenner aufräumen` |
| `dialog.tidy_catch_all_message` | `Unter „{sep}" stehen {count} Einträge, die keine Presets sind. In „{ziel}" verschieben?` |
| `status.tidy_catch_all_done` | `{count} Einträge nach „{ziel}" verschoben` |

Alle fünf in allen 7 Sprachen; keine flach gepunkteten Schlüssel
(`tests/test_translations.py:20-25`).

### 5.5 Nicht Teil dieser Aufgabe

- Erkennung verirrter Presets (`Bad Corpo`) — Punkt 3, läuft parallel.
- Konflikte innerhalb von Archiven — Punkt 2.
- BG3-Pfade, Cover-Bilder, REDmod, redprelauncher.

---

## ✅ Akzeptanz-Kriterien

- [ ] 1. Wenn ein Archiv über den Downloads-Tab installiert wird und die
  Instanz noch keinen Auffang-Trenner hat, legt Anvil den Ordner
  `Nicht einsortiert_separator` unter `.mods/` an, trägt ihn ans Ende der
  globalen `modlist.txt` ein und schreibt `catchall_separator` in `.anvil.ini`.
- [ ] 2. Wenn danach ein zweites Archiv installiert wird, steht dessen Eintrag
  **hinter** dem Auffang-Trenner und hinter dem ersten Neuzugang — nicht davor
  und nicht vor irgendeinem anderen Trenner.
- [ ] 3. Wenn ein Ordner von Hand unter `.mods/` abgelegt und Anvil neu geladen
  wird, erscheint er in der Liste **unterhalb des Auffang-Trenners** und nicht
  unterhalb des Preset-Trenners.
- [ ] 4. Wenn danach eine beliebige Mod per Drag & Drop verschoben wird, steht
  dieser Ordner in der geschriebenen `modlist.txt` weiterhin hinter dem
  Auffang-Trenner.
- [ ] 5. Wenn ein Archiv auf eine **bestimmte Zeile** gezogen wird, landet es
  weiterhin genau dort und **nicht** im Auffang-Trenner.
- [ ] 6. Wenn ein Preset aus einem Archiv gelöst wird, steht es weiterhin direkt
  hinter dem Preset-Trenner (`Presets_separator`) und nicht im Auffang-Trenner.
- [ ] 7. Wenn der Anwender den Auffang-Trenner umbenennt, folgt der Schlüssel in
  `.anvil.ini`, und der nächste Neuzugang landet unter dem neuen Namen.
- [ ] 8. Wenn der Anwender den Auffang-Trenner löscht und danach ein Archiv
  installiert, legt Anvil ihn neu an — ohne Absturz und ohne doppelten Eintrag.
- [ ] 9. Wenn der Anwender den Auffang-Trenner mitten in die Liste zieht,
  landen neue Mods **dort** (hinter ihm), nicht am Dateiende.
- [ ] 10. Wenn eine Instanz einen Preset-Trenner hat, unter dem Einträge stehen,
  die keine Presets sind, fragt Anvil **genau einmal**, ob sie in den
  Auffang-Trenner sollen; bei „So lassen" kommt die Frage nach einem Neustart
  nicht wieder.
- [ ] 11. Wenn der Anwender im Aufräum-Dialog „Verschieben" wählt, stehen
  anschließend in Marcs Cyberpunk-Instanz unter `Presets_separator` nur noch die
  7 `ACU-Preset - …`-Einträge, und `Bad Corpo`, `Fiore` sowie die 10
  Framework-Ordner stehen unter dem Auffang-Trenner.
- [ ] 12. Nach dem Aufräumen hat die `modlist.txt` weiterhin genau so viele
  Einträge wie vorher (536 im Messstand) — kein Eintrag geht verloren, keiner
  kommt doppelt vor.
- [ ] 13. Wenn über das Kontextmenü „Mod installieren…" eine Mod installiert
  wird, steht ihr Name danach in `.profiles/modlist.txt` (globale Datei) und
  **nicht** in `.profiles/<Profil>/modlist.txt`.
- [ ] 14. Wenn über „Leere Mod anlegen" ein Ordner erzeugt wird, gilt dasselbe.
- [ ] 15. Wenn `ModList/show_external_mods` abgeschaltet ist, erscheinen Ordner
  ohne Listeneintrag weiterhin gar nicht — der Auffang-Trenner erzwingt sie
  nicht in die Anzeige.
- [ ] 16. Ein Test ersetzt die Zielposition durch `len(order)` (Mutationsprobe);
  mindestens ein Test der neuen Datei wird dadurch rot.
- [ ] 17. Alle 5 neuen `tr()`-Schlüssel liegen in allen 7 Locale-Dateien vor,
  `tests/test_translations.py` bleibt grün.
- [ ] 18. Die vollständige Testsuite läuft ohne neue Fehlschläge (Messlatte:
  672 grün / 1 übersprungen aus `8179975`).
- [ ] 19. Beim Start einer Instanz **ohne** Neuzugänge wird kein Ordner
  angelegt und die `modlist.txt` nicht verändert (Prüfung: Datei-Inhalt vor und
  nach dem Start identisch).
- [ ] 20. `restart.sh` startet ohne Fehler (Log frei von Traceback, NameError,
  ImportError, AttributeError).

---

## UNSICHER

1. **Wie die heutige Reihenfolge entstanden ist**, lässt sich nicht
   rekonstruieren. `Presets_separator` wurde per `order.append()` ans Ende
   gesetzt (`anvil/mainwindow.py:2183`), steht heute aber **vor** den 10
   Frameworks. Dazwischen liegen mehrere Umbauten (`6def2a8`, `07e20c6`) und
   Handeingriffe (die vielen `modlist.txt.backup_*`-Dateien). Ich habe keinen
   Nachweis für den genauen Ablauf und behaupte keinen.
2. **Herkunft der Profil-`modlist.txt`-Dateien** (`Default`, `Vanilla`, `ebbp`):
   der Code-Pfad aus 1.3 erzeugt genau solche Dateien, aber ohne Zeitstempel-
   Vergleich (kein Shell-Zugriff in dieser Sitzung) ist es nicht belegt. Es
   können auch Reste aus der Zeit vor der globalen Liste sein.
3. **Ob Marc den Aufräum-Dialog überhaupt will.** Er greift in eine gewachsene
   536-Zeilen-Ordnung ein. Der Umbau funktioniert auch ohne ihn — dann bleibt
   der Altbestand, wo er ist, und nur Neuzugänge werden richtig einsortiert.
4. **Verhalten anderer Spiel-Plugins bei Neuzugängen** habe ich nur über die
   gemeinsamen Wege belegt (`_install_archives`, `scan_mods_directory`). BG3
   hat einen eigenen Installer, den ich nicht geprüft habe — er ist laut
   Projektregel tabu.
5. **Kein Vergleich mit fremden Managern** durchgeführt: das Referenzverzeichnis
   `/home/mob/Projekte/Fremd-Mod Manager/mo2-referenz/` wurde in dieser Analyse
   nicht gelesen, weil die Frage („wohin gehen Neuzugänge") in Anvil vollständig
   aus dem eigenen Code beantwortbar war.
