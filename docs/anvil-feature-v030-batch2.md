# Feature: v0.3.0 Bugfixes — Batch 2

Datum: 2026-03-04

## User Stories

### BUG 3: Download→Trenner Drag installiert Mod ganz unten
Als User möchte ich eine Mod aus dem Download-Tab auf einen Trenner in der Mod-Liste ziehen und die Mod wird INNERHALB des Trenners an der Drop-Position eingefügt, damit ich Mods direkt beim Installieren sortieren kann.

### BUG 5: Download-Tab versteckt nicht alle installierten Mods
Als User möchte ich, dass der Download-Tab alle bereits installierten Mods korrekt als "Installiert" markiert und bei aktiviertem "Nach Installation ausblenden" auch korrekt ausblendet.

### BUG 2: Icons anpassen
Als User möchte ich, dass alle Icons im Dark Theme gut erkennbar sind und konsistent verwendet werden (Toolbar, Kontextmenü, Game-Panel).

---

## Technische Planung

### BUG 3: Download→Trenner Drag — Drop-Position korrekt setzen

#### Ursache
Der aktuelle Flow:
1. `_DraggableDownloadTable.mimeData()` erzeugt file-URLs
2. `_DropTreeView.dropEvent()` erkennt URLs, emittiert `archives_dropped` Signal
3. `mainwindow._on_archives_dropped()` ruft `_install_archives()` auf
4. `_install_archives()` ruft `add_mod_to_modlist()` auf
5. **`add_mod_to_modlist()` hängt die Mod IMMER ans Ende der modlist.txt** (`mod_list_io.py`, Zeile ~114)

**Die Drop-Position geht verloren!** In MO2 wird `dropPriority()` berechnet (`modlist.cpp:999-1014`) und an `installDownload(row, priority)` übergeben. Bei Anvil fehlt diese Logik komplett.

#### Lösung

**Schritt 1:** `_DropTreeView.dropEvent()` — Drop-Position (Row-Index) via `indexAt()` + `mapToSource()` extrahieren.

**Schritt 2:** Neues Signal `archives_dropped_at(list, int)` in `_DropTreeView` und `ModListView`.

**Schritt 3:** `mainwindow._on_archives_dropped()` erhält `target_row` Parameter und übergibt ihn an `_install_archives()`.

**Schritt 4:** `_install_archives()` erhält optionalen `insert_at_priority: int | None` Parameter.

**Schritt 5:** Neue Funktion `insert_mod_in_modlist(profile_path, mod_name, priority, enabled=True)` in `mod_list_io.py`.

#### Signal-Flow (neu)
```
_DraggableDownloadTable.mimeData() erzeugt file-URLs
  → _DropTreeView.dropEvent() erkennt URLs
     → berechnet target_source_row via indexAt() + mapToSource()
     → self.archives_dropped_at.emit(paths, target_source_row)
        → ModListView.archives_dropped_at.emit(paths, target_source_row)
           → mainwindow._on_archives_dropped_at(paths, target_row)
              → _install_archives(archives, insert_at=target_row)
                 → insert_mod_in_modlist(profile_path, profiles_dir, mod_name, target_row)
                 → _reload_mod_list()
```

#### Betroffene Dateien

| Datei | Änderung |
|---|---|
| `anvil/widgets/mod_list.py` | Neues Signal `archives_dropped_at(list, int)`. `_DropTreeView.dropEvent()` berechnet Drop-Position via `indexAt()` + `mapToSource()`. |
| `anvil/core/mod_list_io.py` | Neue Funktion `insert_mod_in_modlist()` die Mod an korrekter Position einfügt. |
| `anvil/mainwindow.py` | `_on_archives_dropped` und `_install_archives` erhalten optionalen `insert_at` Parameter. Neue Signal-Verbindung. |

---

### BUG 5: Download-Tab Matching-Logik verbessern

#### Ursache
In `game_panel.py` Zeilen 1185-1230:

1. **`installed_names`** = nur Ordnernamen (lowercase) aus `.mods/` — kein `display_name` aus `meta.ini`
2. **Clean-Logik zu simpel:** Verwendet `re.sub(r"-\d+(-\d+)*$", "")`, entfernt nur Nexus-Suffixe wie `-12345-1-0-1`, aber NICHT den vollen Regex den `suggest_name()` verwendet
3. **`suggest_name()` wird nicht verwendet:** `ModInstaller.suggest_name()` (Zeile 43-66) hat einen vollständigen Nexus-Regex, der im Download-Tab NICHT genutzt wird

**Beispiel-Mismatch:**
- Archiv: `Enhanced Blood Textures-60-3-75-1558912390.7z`
- `suggest_name()` → `Enhanced Blood Textures` → Ordner `.mods/Enhanced Blood Textures/`
- Clean-Logik → `Enhanced Blood Textures-60-3-75` (nur letzter `-\d+` Block entfernt) → **KEIN Match**

#### Lösung

**Schritt 1:** `installed_names` erweitern um `display_name` aus `meta.ini`.

```python
installed_names: set[str] = set()
if self._mods_path and self._mods_path.is_dir():
    for d in self._mods_path.iterdir():
        if d.is_dir():
            installed_names.add(d.name.lower())
            # Auch display_name aus meta.ini einbeziehen
            meta_ini = d / "meta.ini"
            if meta_ini.is_file():
                cp = configparser.ConfigParser(interpolation=None)
                cp.optionxform = str
                try:
                    cp.read(str(meta_ini), encoding="utf-8")
                    dn = cp.get("installed", "name", fallback="")
                    if dn.strip():
                        installed_names.add(dn.strip().lower())
                except Exception:
                    pass
```

**Schritt 2:** Clean-Logik durch `ModInstaller.suggest_name()` ersetzen:

```python
# Ersetze bisherige Clean-Logik:
else:
    suggested = ModInstaller.suggest_name(path)
    is_installed = suggested.lower() in installed_names or path.stem.lower() in installed_names
```

**Schritt 3:** Matching-Reihenfolge (korrigiert):
1. `meta_installed=true` → sofort installiert
2. `meta_install_file` in `installed_names` → installiert
3. **NEU:** `suggest_name(archive_path)` in `installed_names` → verwendet denselben Algorithmus wie Installation
4. Fallback: `stem.lower()` in `installed_names` → beibehalten

#### Betroffene Dateien

| Datei | Änderung |
|---|---|
| `anvil/widgets/game_panel.py` | `refresh_downloads()`: `installed_names` erweitern, Matching-Logik in `_insert_archive_row` korrigieren mit `suggest_name()`. |
| `anvil/core/mod_installer.py` | Keine Änderung — `suggest_name()` ist `@staticmethod`, bereits importierbar. |

---

### BUG 2: Icons anpassen — Analyse

#### Ist-Zustand

| Ort | Aktuelle Icons | Format |
|---|---|---|
| **Toolbar** (`toolbar.py`) | `instances.svg`, `archives.svg`, `profiles.svg`, `refresh.svg`, `executables.svg`, `tools.svg`, `settings.svg`, `endorse.svg`, `problems.svg`, `update.svg`, `help.svg`, `check.svg` | SVG |
| **Profile-Bar** (`profile_bar.py`) | `dots.png`, `archives.png`, `restore.png`, `backup.png` aus `icons/files/` | PNG |
| **Game-Panel** (`game_panel.py`) | `executables.svg`, `play.png`, `refresh.svg` | Gemischt |
| **Kontextmenü Mod-Liste** (`mainwindow.py`) | KEINE Icons — reine Text-Actions | — |
| **Kontextmenü Download-Tab** | KEINE Icons | — |
| **Mod-Liste** | Conflict-Icons (SVG), programmatische Icons (Stern, Checkmark) | SVG/programmatisch |

#### Änderungsliste

| Nr | Ort | Problem | Vorschlag |
|---|---|---|---|
| 1 | `anvil/styles/icons/toolbar/` | 16 PNG-Dateien, NICHT verwendet — toter Code | Entfernen oder verwenden — Entscheidung Marc |
| 2 | `anvil/styles/icons/profile/` | Teilweise ungenutzt (`view.png`, `undo.png`, `filter.png`) | Prüfen ob für zukünftige Features vorgesehen |
| 3 | Kontextmenü Mod-Liste | Keine Icons | Optional: Icons hinzufügen (MO2 hat dort auch keine) |
| 4 | Kontextmenü Download-Tab | Keine Icons | Optional: Icons hinzufügen |

**HINWEIS:** BUG 2 erfordert Marc's Entscheidung welche Icons konkret geändert werden sollen.

#### Betroffene Dateien

| Datei | Änderung |
|---|---|
| `anvil/widgets/toolbar.py` | Entscheidung: SVG beibehalten oder auf PNG wechseln |
| `anvil/styles/icons/toolbar/` | Ungenutzte PNGs ggf. entfernen |
| `anvil/styles/icons/profile/` | Ungenutzte PNGs ggf. entfernen |

---

## MO2-Vergleich

| Aspekt | MO2 | Anvil (aktuell) | Änderung |
|---|---|---|---|
| Download-Drop Position | `dropPriority()` berechnet Position, `installDownload(index, priority)` fügt an Position ein | Immer ans Ende (`add_mod_to_modlist`) | FIX: Position übergeben |
| Download "Installed" Matching | `installationFile` in `.meta`, plus `modID`-basiertes Matching | 3-Stufen-Matching, aber Clean-Logik zu simpel | FIX: `suggest_name()` verwenden |
| Icons | Paper Dark Theme, SVG-basiert | SVG-Icons vorhanden, funktionieren | Prüfen mit Marc |

## Abhängigkeiten
- BUG 3 benötigt korrektes Proxy-to-Source Mapping im TreeView (bereits vorhanden)
- BUG 5 benötigt `ModInstaller.suggest_name()` (bereits als `@staticmethod` vorhanden)
- BUG 2 hängt von Marc's Entscheidung ab

## Risiken
- **BUG 3:** Drop-Position muss korrekt von Proxy zu Source gemappt werden. Bei nicht-Standard-Sortierung könnte das Mapping anders sein.
- **BUG 5:** Performance: `meta.ini` lesen für jeden Mod-Ordner bei `refresh_downloads()`. Akzeptabel, da `scan_mods_directory()` dies bereits bei jedem Reload tut.
- **BUG 2:** Minimales Risiko, rein kosmetisch.

---

## Akzeptanz-Kriterien

- [ ] **K1:** Download→aufgeklappter Trenner: Mod wird an Drop-Position innerhalb des Trenners eingefügt (nicht ganz unten)
- [ ] **K2:** Download→zwischen zwei Mods: Neue Mod wird genau an dieser Position eingefügt
- [ ] **K3:** Download→zugeklappter Trenner: Mod wird als letztes Kind des Trenners eingefügt
- [ ] **K4:** Doppelklick-Installation im Download-Tab: Mod wird weiterhin ans Ende der Liste angefügt (bestehendes Verhalten)
- [ ] **K5:** Nexus-Dateiname (z.B. `Enhanced Blood Textures-60-3-75-1558912390.7z`) → Ordner `Enhanced Blood Textures` → Download-Tab zeigt "Installiert"
- [ ] **K6:** Umbenannter Mod via Quick-Install-Dialog → Download-Tab zeigt trotzdem "Installiert" (via `installationFile` in `.meta`)
- [ ] **K7:** Nicht-installiertes Archiv → Download-Tab zeigt "Nicht installiert" (kein falsch-positives Matching)
- [ ] **K8:** "Nach Installation ausblenden" aktiv + Archiv installiert → Zeile im Download-Tab ausgeblendet
- [ ] **K9:** Matching-Logik verwendet `ModInstaller.suggest_name()` für konsistenten Vergleich
- [ ] **K10:** Drag aus Dateimanager (nicht Download-Tab) auf Mod-Liste funktioniert weiterhin (bestehendes Signal bleibt)
- [ ] **K11:** Ungenutzte PNG-Dateien in `toolbar/` sind dokumentiert — Entscheidung Marc
- [ ] **K12:** `./restart.sh` startet ohne Fehler
