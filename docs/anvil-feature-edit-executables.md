# Feature-Spec: Executables bearbeiten (#25)
**Status:** Geplant (verifiziert gegen echten Code am 2026-06-28)
**Datum:** 2026-06-28

## 1. Problem / Ziel

Im Spiel-Button-Menü (Klappmenü am großen Game-Banner) gibt es den Eintrag
`<Bearbeiten...>` (Locale-Text `game_panel.edit_executables` = `<Bearbeiten...>`),
der aktuell **deaktiviert** ist (`game_panel.py:530` → `setEnabled(False)`, keine
Triggered-Verbindung).

GitHub-Issue #25 ("Edit Executables in Game Button Menu") fordert wörtlich:
- Dialog zum Verwalten der Executables des aktuellen Spiels
- Add / Edit / Delete von Executables
- Pfad, Argumente, Arbeitsverzeichnis konfigurierbar
- Umsortieren per Drag & Drop
- Executables erscheinen im Start-Dropdown des Spiel-Buttons

Issue-Status laut Issue selbst: "Menu entry present but disabled — no functionality
implemented." Bestätigt durch Code (siehe Abschnitt 4).

Ziel: User können eigene Tools (SKSE/F4SE, xEdit/SSEEdit, BodySlide, FNIS, Nemesis,
LOOT, eigene Skripte) **pro Instanz** pflegen und direkt über den Start-Button neben
den Plugin-Executables starten.

**Gute Nachricht (verifiziert):** Die halbe Infrastruktur existiert bereits. Die
"Proton Tools" (`proton_tools_dialog.py` + `proton_tools.json` pro Instanz +
`game_panel.run_with_proton()`) sind faktisch schon ein Executables-Editor — aktuell
nur über das Extras-/Proton-Menü in `mainwindow.py` erreichbar, nicht über das
Spiel-Button-Menü und nicht im Start-Dropdown sichtbar. Das Feature ist primär
**Integration + Wiederverwendung**, kein Neubau.

## 2. Phasen-Rückgrat (Bau-Reihenfolge nach steigendem Risiko)

| # | Phase | Inhalt | Risiko | testbar nach Phase? |
|---|---|---|---|---|
| 1 | i18n-Grundlage | Neue tr-Keys (`proton_tools.run_via_proton`, `move_up_tooltip`, `move_down_tooltip`, `game_panel.custom_executables`) in allen 7 nested Locales anlegen | niedrig | ja — App startet, kein Roh-Key |
| 2 | Editor öffnen | `<Bearbeiten...>` aktivieren + Handler `_on_edit_executables()` in `game_panel.py`, öffnet vorhandenen `ProtonToolsDialog` mit `self._instance_path` | niedrig | ja — Dialog öffnet, Add/Edit/Delete funktionieren bereits |
| 3 | Reihenfolge | ▲/▼-Buttons im Dialog (robuster) oder `InternalMove`-D&D; `self._tools` synchron halten | mittel | ja — Reihenfolge ändern + speichern, JSON prüfen |
| 4 | Custom-Block im Dropdown | Nach Plugin-Executables einen Custom-Block aus `load_proton_tools()` in `_rebuild_executables_menu` einfügen (Trenner + Marker `custom=True`); Aktualität über `aboutToShow` lösen | mittel | ja — eigene Einträge erscheinen, Auswahl setzt Tooltip |
| 5 | Start-Routing | `_on_start_clicked`/`_do_launch`: Custom-Eintrag → `run_with_proton(...)` (Proton) bzw. Direktstart; `proton`-Flag berücksichtigen | hoch | ja — Tool startet im Prefix bzw. direkt |
| 6 | Härtung (optional) | `shlex.split` fürs Args-Feld; Deploy-vor-Custom-Start (mit Marc klären) | hoch | ja — Args mit Leerzeichen, Tool sieht deployte Mods |

Begründung der Reihenfolge: i18n und Editor-Öffnen sind risikolos und sofort testbar.
Reorder ist UI-lokal. Der heikle Teil (Start-Routing, Proton-Env, Index-Sync) kommt
zuletzt, wenn die Datenpipeline schon steht.

## 3. Ist-Zustand im Code (nur VERIFIZIERTE Anker datei:zeile)

### 3.1 Deaktivierter Menüeintrag — VERIFIZIERT
- `anvil/widgets/game_panel.py:522` `def _rebuild_executables_menu(self, game_plugin)`
- `anvil/widgets/game_panel.py:529` `edit_action = self._exe_menu.addAction(tr("game_panel.edit_executables"))`
- `anvil/widgets/game_panel.py:530` `edit_action.setEnabled(False)`  ← **hier deaktiviert**
- `anvil/widgets/game_panel.py:531` `self._exe_menu.addSeparator()`
  → Eintrag existiert, **keine** `triggered`-Verbindung, `setEnabled(False)`.

### 3.2 Woher die Executables aktuell kommen (Plugin, relativ zum Spielordner) — VERIFIZIERT
- Default `anvil/plugins/base_game.py:785` `def executables(self) -> list[dict[str, str]]`
  → liefert `[{"name", "binary"}]`, `binary` = Pfad **relativ zum Spielverzeichnis**.
- Overrides (alle Zeilennummern geprüft):
  `game_skyrimse.py:275`, `game_fallout4.py:241`, `game_cyberpunk2077.py:150`,
  `game_witcher3.py:188`, `game_starfield.py:245`.
- Iteration in `_rebuild_executables_menu` `game_panel.py:540-553`:
  - `game_panel.py:551` `action = self._exe_menu.addAction(icon, name)`
  - `game_panel.py:552` `action.triggered.connect(lambda checked, i=idx: self._on_exe_selected(i))`
  - `game_panel.py:553` `self._executables.append({"name": name, "binary": binary})`
  `self._executables` ist die interne Auswahlliste, `self._selected_exe_index`
  (Default 0, gesetzt in Zeile 526/593) merkt den aktiven Eintrag.

### 3.3 Start-Logik — VERIFIZIERT
- `game_panel.py:1069` `_on_exe_selected(index)` — setzt `_selected_exe_index` + Tooltip.
- `game_panel.py:1075` `_on_start_clicked()` — liest `binary` aus
  `self._executables[idx]` (Zeile 1085-1086), prüft REDmod-Bedarf (1100), ruft
  bei Bedarf `silent_deploy()` (1104) + `_run_redmod_deploy_then_launch`, sonst
  `_do_launch(plugin, binary, is_steam)` (1108).
- `game_panel.py:1110` `_do_launch(plugin, binary, is_steam)`:
  - Steam + Hauptbinary ohne Proton-Force → `_launch_via_steam(plugin)` (1118).
  - Steam + sonst → `_launch_via_proton(plugin, binary)` (1120; Methode ab `1721`).
  - Non-Steam → `binary_path = game_path / binary` (1132), Existenzprüfung,
    `self.start_requested.emit(str(binary_path), working_dir)` (`game_panel.py:1141`).
- Signal: `game_panel.py:105` `start_requested = Signal(str, str)  # (binary_path, working_dir)`.
- Empfänger: `mainwindow.py:1854` `_on_start_game(binary_path, working_dir)`:
  - macht **vor** dem Start `silent_purge()` (1863) + `silent_deploy()` (1866),
  - startet via `host_popen([binary_path], cwd=working_dir, env=clean_subprocess_env())`
    (`mainwindow.py:1869-1873`).
  → **Merke:** Das Signal trägt **nur** `(binary, working_dir)`, **keine** Args.
    `_on_start_game` löst zusätzlich einen Full-Deploy aus.
- **Wichtig:** Plugin-Executables sind **relativ** zum Spielordner (`game_path / binary`).
  Eigene Tools liegen oft **außerhalb** (absoluter Pfad) → eigenes Marker-Feld nötig
  (siehe 5.5), nicht über `game_path / binary` auflösbar.

### 3.4 Bereits vorhandene Editor-Logik (Proton Tools) — VERIFIZIERT
- `anvil/widgets/proton_tools_dialog.py` (**243 Zeilen**): vollständiger Editor-Dialog:
  - Liste links + `+`/`−`-Buttons (`_on_add` ab Zeile 190, `_on_remove` ab 208).
  - Formular rechts: Name, Exe-Pfad (+`...`-Browse), Argumente, Arbeitsverzeichnis
    (+`...`-Browse). Felder ab Zeile 92-122.
  - OK (`_on_ok`, Zeile 240) / Abbrechen (`reject`).
  - Persistenz: `proton_tools.json` **pro Instanz**:
    `load_proton_tools(instance_path)` (`proton_tools_dialog.py:28`),
    `save_proton_tools(instance_path, tools)` (`proton_tools_dialog.py:38`),
    Konstante `TOOLS_FILE = "proton_tools.json"` (Zeile 25).
  - `_on_ok` ruft `save_proton_tools(self._instance_path, self._tools)` (Zeile 242).
- Datenmodell pro Tool (verifiziert in `_on_add`/`_on_field_changed`):
  `{"name", "exe_path", "args": [...], "working_dir"}`.
- **Args-Parsing:** `proton_tools_dialog.py:184` `tool["args"] = args_text.split()` —
  zerlegt am Whitespace, bricht bei Argumenten mit Leerzeichen (Härtung in Phase 6).

### 3.5 Verdrahtung der Proton Tools im Hauptfenster — VERIFIZIERT
- `mainwindow.py:796` `_rebuild_proton_menu(menu)` — baut Untermenü: je Tool ein
  Action (Zeile 802-807) + Eintrag `tr("proton_tools.manage")` (Zeile 810).
- `mainwindow.py:813` `_run_proton_tool(idx)` — lädt Tools, liest
  `exe_path`/`args`/`working_dir`, ruft
  `self._game_panel.run_with_proton(exe_path, args, wdir or None)` (`mainwindow.py:826`).
- `mainwindow.py:828` `_on_proton_manage()` — öffnet `ProtonToolsDialog`.

### 3.6 `run_with_proton` (startet beliebige absolute .exe im Prefix) — VERIFIZIERT
- `game_panel.py:1775` `def run_with_proton(self, exe_path, args=None, working_dir=None)`:
  - prüft `self._current_plugin` (1780) und `exe.is_file()` (1789),
  - baut Proton-Env via `_build_proton_env(plugin)` (1796),
  - `cmd = [str(proton_script), "run", str(exe)]` + optionale Args (1810-1812),
  - `host_popen(cmd, cwd=cwd, env=env, …)` (1813). cwd = `working_dir or exe.parent` (1807).
  → Genau das, was eigene Tools brauchen.

### 3.7 Wie das Panel an die Instanz kommt — VERIFIZIERT
- `game_panel.py:1971` `set_instance_path(self, instance_path, profile_name="Default")`
  setzt `self._instance_path`.
- Aufrufer u. a. `mainwindow.py:1335`, `:3683`, `:3746`, `:6103`.
- **Reihenfolge-Falle:** In `update_game()` (`game_panel.py:416`) wird
  `_rebuild_executables_menu()` (`game_panel.py:458`) aufgerufen. `set_instance_path()`
  läuft separat (mainwindow 1335) i. d. R. **danach**. Beim ersten Aufbau kann
  `self._instance_path` daher noch `None`/alt sein. Lösung: Custom-Liste über
  `self._exe_menu.aboutToShow` bei jedem Öffnen frisch laden (siehe 5.4).

### 3.8 Status der Teil-Implementierung — VERIFIZIERT (nichts halb gebaut)
- grep in `game_panel.py` nach `_on_edit_executables`, `aboutToShow`, `custom=`,
  `load_proton_tools`: **keine** Treffer im Executables-Kontext. Das Custom-Executables-
  Feature ist im Panel **nicht** angefangen; nur der disabled Menüeintrag existiert.
- `run_with_proton` und der gesamte Proton-Tools-Editor sind dagegen voll funktionsfähig.

## 4. Lösung / Ansatz

Leitidee: **Bestehendes Proton-Tools-System wiederverwenden und ins Spiel-Button-Menü
integrieren**, statt ein zweites paralleles Executables-System zu bauen. Der
`<Bearbeiten...>`-Eintrag öffnet den (um Reorder + Proton-Flag erweiterten) Dialog;
die gepflegten Einträge erscheinen als eigener Block im Start-Dropdown und sind über
den Start-Button startbar.

## 5. Umsetzungsschritte

### 5.1 Editor-Dialog erweitern (`proton_tools_dialog.py`)
- **Reihenfolge:** ▲/▼-Buttons (Empfehlung, robust gegen Index-Sync-Fehler) ODER
  `QListWidget.setDragDropMode(InternalMove)` + `model.rowsMoved`-Handler, der
  `self._tools` exakt in die neue Reihenfolge bringt. D&D ist Issue-Wortlaut, ▲/▼ ist
  weniger fehleranfällig — Variante mit Marc abstimmen.
- **Checkbox "Über Proton starten"** pro Eintrag (Feld `proton: bool`, Default `True`).
  Erlaubt native Linux-Tools/Skripte (bash-Skript, LOOT-Flatpak) ohne Proton.
  Laden/Speichern in `_on_selection_changed` (Zeile 156), `_on_field_changed` (174),
  `_on_add` (190) ergänzen.
- Bestehende Felder bleiben unverändert. Beim OK → `save_proton_tools()` (schon
  vorhanden, Zeile 242); danach muss das Spiel-Button-Menü neu gebaut werden (über
  `aboutToShow`, siehe 5.4 — kein Callback nötig).

### 5.2 Datenmodell (pro Eintrag, in `proton_tools.json` der Instanz)
```jsonc
{
  "name": "SSEEdit",
  "exe_path": "/pfad/zu/SSEEdit.exe",   // absoluter Pfad (eigene Tools)
  "args": ["-IKnowWhatImDoing"],
  "working_dir": "/pfad/zu",
  "proton": true                          // NEU: false = Direktstart ohne Proton
}
```
- Abwärtskompatibel: fehlt `proton`, gilt `True` (bisheriges Verhalten).
- Bewusst **dasselbe** Schema/Datei wie Proton Tools → kein doppelter Datenbestand.
  (Offen: redundanten Extras-Menü-Eintrag `proton_tools.manage` belassen/umbenennen/
  entfernen — mit Marc klären, siehe Abschnitt 9.)

### 5.3 Persistenz pro Instanz
- Unverändert: `<instance_path>/proton_tools.json` via `load_proton_tools` /
  `save_proton_tools` (`proton_tools_dialog.py:28/38`). Pfad kommt aus
  `self._instance_path` (Instanz-Config) — **kein hardcoded Pfad**.
- Keine `instance.json`-Änderung nötig.

### 5.4 Integration ins Spiel-Button-Menü (`_rebuild_executables_menu`, game_panel.py)
- `<Bearbeiten...>` **aktivieren** + Handler verbinden:
  ```python
  edit_action.setEnabled(self._instance_path is not None)
  edit_action.triggered.connect(lambda checked=False: self._on_edit_executables())
  ```
- Nach dem Plugin-Executables-Block einen **Custom-Block** einfügen:
  - `load_proton_tools(self._instance_path)` laden (Import aus `proton_tools_dialog`),
  - je Tool `self._exe_menu.addAction(name)` + Eintrag in `self._executables` mit
    Marker `custom=True` und Feldern `exe_path`, `args`, `working_dir`, `proton`,
  - Trenner (`addSeparator`) + optional Titel-Label `tr("game_panel.custom_executables")`
    zwischen Plugin- und Custom-Block.
- **Reihenfolge-Falle (3.7) lösen:** `self._exe_menu.aboutToShow.connect(...)` **einmalig**
  in `__init__` anbinden, der die Custom-Liste bei jedem Öffnen frisch aus der JSON lädt.
  Dadurch unabhängig von der `update_game`/`set_instance_path`-Reihenfolge und immer
  aktuell nach Editor-Schließen (kein expliziter Rebuild-Callback nötig).
  Achtung: nicht das ganze Menü doppelt aufbauen — entweder nur den Custom-Block
  nachladen oder Rebuild idempotent halten.

### 5.5 Start-Routing für Custom-Executables (`_on_start_clicked` / `_do_launch`)
- In `_on_start_clicked` (game_panel.py:1075) `self._executables[idx]` auf `custom`
  prüfen. Wenn `custom`:
  - `proton == True` → `self.run_with_proton(exe_path, args, working_dir)`
    (vorhandene Methode, `game_panel.py:1775`).
  - `proton == False` → Direktstart. **Achtung (verifiziertes Risiko):** das Signal
    `start_requested` (`game_panel.py:105`) trägt **nur** `(binary, working_dir)`,
    keine Args. Entweder Signal um Args erweitern (zieht `_on_start_game`-Anpassung in
    `mainwindow.py:1854` nach sich) ODER Custom-Tools direkt im Panel via `host_popen`
    starten. Variante festlegen (Abschnitt 9).
  - **Kein** REDmod-Deploy-Pfad für Custom-Tools erzwingen.
- **Deploy-vor-Start-Nuance (verifiziert):** Der Plugin-Non-Steam-Pfad löst über
  `_on_start_game` automatisch `silent_purge()` + `silent_deploy()` aus
  (`mainwindow.py:1863/1866`). `run_with_proton` macht das **nicht**. Tools wie
  xEdit/BodySlide brauchen die virtuellen Dateien → vor Custom-Start ggf. ebenfalls
  `silent_deploy()` aufrufen. Mit Marc klären (Abschnitt 9, Empfehlung: ja).

### 5.6 Argument-Quoting (optional, Phase 6)
- `proton_tools_dialog.py:184` nutzt `args_text.split()` — bricht bei Leerzeichen in
  Argumenten. Empfehlung `shlex.split()`. Mit Marc abklären, ob im Scope.

## 6. Betroffene Dateien

| Datei | Änderung |
|---|---|
| `anvil/widgets/game_panel.py` | `<Bearbeiten...>` aktivieren + `_on_edit_executables`; Custom-Block in `_rebuild_executables_menu`; `aboutToShow`-Anbindung in `__init__`; Start-Routing in `_on_start_clicked`/`_do_launch` für Custom/Proton/Direkt |
| `anvil/widgets/proton_tools_dialog.py` | ▲/▼ bzw. D&D zum Umsortieren; Checkbox "Über Proton starten" (Feld `proton`); ggf. `shlex.split`; Laden/Speichern des neuen Felds |
| `anvil/mainwindow.py` | Optional: ggf. Args-fähiges `start_requested`/`_on_start_game` (`:105`/`:1854`), falls Direktstart-Variante mit Args gewählt; ggf. redundanten `proton_tools.manage`-Eintrag im Extras-Menü anpassen |
| `anvil/locales/{de,en,es,fr,it,pt,ru}.json` | Neue tr-Keys (siehe 7) — **7 nested Locales** |

Keine Plugin-Dateien anfassen (Plugin-`executables()` bleibt unverändert).
Keine BG3-, Cover-, REDmod-Icon-Dateien anfassen.

## 7. i18n (tr-Keys, 7 Locales)

Locales: **de, en, es, fr, it, pt, ru** (alle 7 unter `anvil/locales/`, verifiziert
vorhanden).

**WICHTIG (korrigiert):** Die Locale-Dateien sind **nested JSON-Objekte**, KEINE flach
gepunkteten Keys. `tr("proton_tools.run_via_proton")` adressiert den Schlüssel
`run_via_proton` **innerhalb** des Objekts `proton_tools`:
```jsonc
{ "proton_tools": { "run_via_proton": "Über Proton starten", ... },
  "game_panel":   { "edit_executables": "<Bearbeiten...>", ... } }
```
Neue Keys MÜSSEN ins jeweilige Eltern-Objekt eingefügt werden (nicht als Top-Level-Key
mit Punkt im Namen).

**Wiederverwenden (verifiziert vorhanden, 25 Subkeys unter `proton_tools`):**
`manage_title`, `name_label`, `name_placeholder`, `exe_label`, `exe_placeholder`,
`args_label`, `args_placeholder`, `dir_label`, `dir_placeholder`, `select_exe`,
`exe_filter`, `select_dir`, `add_tooltip`, `remove_tooltip`, `manage`, `title`,
`no_game`, `no_instance`, `proton_not_found`, `exe_not_found`, `launch`,
`launch_failed`, `new_tool`, `tools_label`, `browse`.
Unter `button`: `ok`, `cancel` (verifiziert vorhanden).

**Vorhanden, wird umfunktioniert:** `game_panel.edit_executables` (= `<Bearbeiten...>`)
— Trigger statt deaktiviert. Kein neuer Key nötig.

**Neu hinzuzufügen (in allen 7 Locales, ins richtige Eltern-Objekt):**
| Key (Objekt → Schlüssel) | de (Beispiel) |
|---|---|
| `proton_tools.run_via_proton` | "Über Proton starten" |
| `proton_tools.move_up_tooltip` | "Nach oben" |
| `proton_tools.move_down_tooltip` | "Nach unten" |
| `game_panel.custom_executables` (Trenner-/Blocktitel) | "Eigene Programme" |

(Falls Drag&Drop statt Buttons gewählt wird: `move_up_tooltip`/`move_down_tooltip`
entfallen.)

## 8. Akzeptanzkriterien

- [ ] `<Bearbeiten...>` im Spiel-Button-Menü ist aktiv (nur wenn `_instance_path` gesetzt)
      und öffnet den Editor-Dialog.
- [ ] Editor zeigt vorhandene Einträge der aktuellen Instanz, erlaubt Hinzufügen
      (Datei-Dialog), Bearbeiten (Name/Pfad/Args/Arbeitsverzeichnis), Löschen.
- [ ] Reihenfolge änderbar (Drag&Drop oder ▲/▼) und wird in `proton_tools.json`
      gespeichert.
- [ ] Checkbox "Über Proton starten" pro Eintrag vorhanden und persistiert (Feld
      `proton`).
- [ ] Speichern schreibt `proton_tools.json` in den Instanz-Ordner (kein Home, kein
      hardcoded Pfad).
- [ ] Eigene Executables erscheinen als eigener Block im Start-Dropdown des
      Spiel-Buttons (durch Trenner von Plugin-Executables getrennt).
- [ ] Auswahl eines Custom-Eintrags + Start-Button startet das Tool: bei `proton:true`
      via Proton-Prefix (`run_with_proton`), sonst direkt.
- [ ] Einträge sind **pro Instanz** isoliert (Instanz wechseln → andere Liste).
- [ ] Menü ist nach Editor-Schließen sofort aktuell (über `aboutToShow`, kein Neustart).
- [ ] Alle neuen tr-Keys in allen 7 Locales im **richtigen Eltern-Objekt**, kein
      Roh-Key sichtbar.
- [ ] `./restart.sh` startet fehlerfrei (kein NameError/ImportError/AttributeError).
- [ ] Kein `setStyleSheet()` in neuen Widgets; QSS-Theme wird vererbt.
- [ ] Keine Referenz-Manager-Erwähnungen im Code/Kommentaren.

## 9. Aufwand / Risiko / offene Punkte

**Aufwand:** Mittel-niedrig (~0,5–1 Tag). Editor-Dialog und Persistenz existieren;
Kernarbeit ist Menü-Integration, Start-Routing und das `proton`-Flag/Reorder + 7 Locales.

**Risiken / offene Punkte (mit Marc abzustimmen):**
1. **Redundanz Proton Tools vs. neues Feature** — gleiches `proton_tools.json`. Soll der
   bestehende `proton_tools.manage`-Eintrag im Extras-/Proton-Menü bleiben, umbenannt
   oder entfernt werden?
2. **Reihenfolge-Falle** (`update_game` → Menü-Rebuild VOR `set_instance_path`). Lösung
   über `aboutToShow` empfohlen — bestätigen. Achtung: keinen doppelten Menüaufbau.
3. **Non-Proton-Start mit Argumenten:** `start_requested` (`game_panel.py:105`) trägt
   nur `(binary, working_dir)`, keine Args; `_on_start_game` (`mainwindow.py:1854`) löst
   zudem Full-Deploy aus. Entweder Signal/Slot um Args erweitern oder Custom-Tools direkt
   im Panel via `host_popen` starten. Variante festlegen.
4. **Deploy vor Custom-Start:** ✅ ENTSCHIEDEN (2026-06-29) — **Variante A**: vor jedem
   Custom-Start denselben Chain wie der Plugin-Spielstart laufen lassen
   (`silent_purge()` → `_sync_separator_deploy_paths()` → `silent_deploy()`,
   vgl. `mainwindow.py:1891-1894`), damit das Tool exakt denselben Stand wie das Spiel
   sieht. Per-Eintrag-Checkbox „Mods vorher bereitstellen" (Opt-out, Variante B) nur
   optional später als Phase-6-Härtung, falls Deploy bei reinen Utilities stört.
5. **Argument-Quoting:** `str.split()` (Zeile 184) vs. `shlex.split()` — im Scope?
6. **Drag&Drop vs. ▲/▼:** D&D ist Issue-Wortlaut, aber Index-Sync mit `self._tools` ist
   fehleranfällig; ▲/▼ robuster. Welche Variante?

**Verbote (CLAUDE.md):** kein Code-Anfassen ohne GO; keine BG3-Dateien; keine
Cover/REDmod-Icons; keine hardcoded Pfade; keine `setStyleSheet()` in neuen Widgets;
keine Referenz-Manager-Erwähnungen im Code; alle 7 Locales pflegen.
