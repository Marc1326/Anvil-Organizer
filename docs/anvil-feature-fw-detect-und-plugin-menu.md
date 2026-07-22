# Feature-Zusammenfassung: Framework-Erkennung & Game-Plugin Menü

## 1. Automatische Framework-Erkennung

### Was ist das?
Wenn ein Benutzer eine Mod installiert (per Drag & Drop oder "Mod installieren..."), prüft Anvil **automatisch**, ob es sich um eine Framework-Mod handelt. Frameworks sind Mods wie Script Extender, SKSE, F4SE etc., die direkt ins Game-Verzeichnis installiert werden müssen — nicht in den Mod-Ordner.

### Wie funktioniert die Erkennung?

**Stufe 1 — Bekannte Frameworks (`is_framework_mod`):**
Anvil prüft zuerst, ob die Mod zu einem bereits definierten Framework passt (Pattern-Matching gegen die Framework-Liste des Game-Plugins). Wenn ja, wird sie direkt als Framework installiert.

**Stufe 2 — Heuristik für unbekannte Frameworks (`detect_possible_framework`):**
Wenn kein bekanntes Framework erkannt wird, analysiert Anvil den Archiv-Inhalt mit einem Score-System:

| Kriterium | Punkte | Beschreibung |
|---|---|---|
| Executable-Dateien | +30 | `.dll`, `.exe`, `.so`, `.asi` im Archiv |
| Keyword im Dateinamen | +25 | Wörter wie "loader", "extender", "hook", "injector", "patcher" etc. |
| Config neben DLL | +15 | `.ini`, `.toml`, `.cfg`, `.xml`, `.json` im selben Ordner wie eine DLL |
| Keine Mod-Dateien | +20 | Keine `.esp`, `.esm`, `.pak`, `.archive`, `.dds` etc. vorhanden |
| Außerhalb Data/ | +10 | Dateien liegen nicht im `Data/`-Unterordner |

**Schwellenwert: ≥ 60 Punkte** — ab diesem Score wird der Benutzer gefragt.

### Was passiert bei Erkennung?

1. Ein Dialog erscheint mit:
   - Überschrift: "Die Mod [Name] könnte ein Framework sein."
   - Liste der Erkennungsgründe (übersetzt in alle 7 Sprachen)
   - Liste der erkannten Dateien
   - Editierbare Felder: Name, Ziel-Ordner, Prüf-Pfad
2. Der Benutzer kann bestätigen ("Als Framework installieren") oder ablehnen ("Abbrechen")
3. Bei Bestätigung:
   - Dateien werden ins Game-Verzeichnis installiert
   - Das Framework wird in der Plugin-JSON gespeichert (`~/.anvil-organizer/plugins/games/game_[short].json`)
   - Das Frameworks-Panel wird aktualisiert
   - Bei zukünftigen Installationen wird diese Mod automatisch als bekanntes Framework erkannt (Stufe 1)
4. Bei Ablehnung: Die Mod wird normal als Mod installiert

### Technischer Ablauf (Install-Flow)

```
Benutzer installiert Archiv (DnD / Menü)
    │
    ├─ _try_install_as_framework(archive)     ← NEU: Pre-Filter
    │   ├─ is_framework_mod() → bekannt? → direkt installieren
    │   └─ detect_possible_framework() → Score ≥ 60? → Dialog zeigen
    │
    ├─ [BG3] → _on_bg3_archives_dropped()     ← unverändert
    └─ [Andere] → _install_archives()         ← unverändert
```

Der Pre-Filter läuft **vor** dem BG3/Normal-Abzweig, damit die Framework-Erkennung für **alle Games** funktioniert — auch für BG3, das seinen eigenen Install-Pfad hat.

### Betroffene Dateien

| Datei | Änderung |
|---|---|
| `anvil/plugins/base_game.py` | `detect_possible_framework()`, `save_framework_to_json()` |
| `anvil/widgets/framework_detect_dialog.py` | Neuer Dialog (FrameworkDetectDialog) |
| `anvil/mainwindow.py` | `_try_install_as_framework()`, Pre-Filter in 3 Drop-Handlern |
| `anvil/widgets/plugin_creator_dialog.py` | Pattern-Spalte in Framework-Tabelle, `_collect_frameworks()` Fix |
| `anvil/locales/*.json` (7 Dateien) | `fw_detect.*` Keys + `plugin_creator.fw_pattern` |

---

## 2. Game Plugin erstellen

### Was ist das?
Über **Datei → Game Plugin → Game Plugin erstellen...** (oder den Puzzle-Button in der Toolbar) kann ein Benutzer ein komplett neues Game-Plugin anlegen.

### Was wird abgefragt?
- **Pflichtfelder:** Spielname, Kurzname, Game-EXE, Steam-ID
- **Optionale Felder:** Mod-Ordner, Documents-Pfad (Proton), Saves-Pfad (Proton), Savegame-Endung, Nexus Game-ID
- **Frameworks:** Tabelle mit Name, Ziel-Ordner, Nexus-ID, Prüf-Pfad, Pattern, Quelle
- **Bild:** Vorschau-Bild für das Spiel

### Was passiert beim Erstellen?
1. Anvil generiert eine Python-Datei (`game_[kurzname].py`) in `anvil/plugins/games/`
2. Wenn Frameworks definiert wurden, wird zusätzlich eine JSON-Datei in `~/.anvil-organizer/plugins/games/` erstellt
3. Anvil muss neu gestartet werden, damit das Plugin geladen wird

---

## 3. Game Plugin ändern

### Was ist das?
Über **Datei → Game Plugin → Game Plugin ändern...** (oder den Puzzle-Button in der Toolbar) kann das **aktuell geladene** Game-Plugin bearbeitet werden.

### Was kann geändert werden?
- Alle Felder wie beim Erstellen (Name, Pfade, Frameworks, Bild)
- **Built-in Frameworks** (aus dem Python-Plugin) sind sichtbar aber nicht editierbar
- **JSON Frameworks** (manuell oder per Auto-Erkennung hinzugefügt) können bearbeitet und gelöscht werden

### Unterschied zu "Erstellen"
| | Erstellen | Ändern |
|---|---|---|
| Dialog-Titel | "Game Plugin erstellen" | "Plugin bearbeiten — [Name]" |
| Felder | Leer | Vorausgefüllt mit aktuellen Werten |
| Frameworks | Leere Tabelle | Alle Frameworks geladen (Built-in + JSON) |
| Speichern | Neue `.py`-Datei erstellen | Bestehende JSON-Datei aktualisieren |
| Button-Text | "Erstellen" | "Speichern" |

---

## Toolbar-Button

In der Toolbar gibt es einen **Puzzle-Button** (zweiter von links) mit Dropdown-Menü:
- "Game Plugin erstellen..." → Leerer Dialog
- "Game Plugin ändern..." → Dialog mit aktuellem Plugin

Der Button nutzt `InstantPopup` — ein Klick öffnet direkt das Dropdown.

---

## Commits

- `f79e8bb` — Game Plugin Menü mit Erstellen/Ändern, Toolbar-Button, native Dateidialoge
- `9af24e7` — Automatische Framework-Erkennung mit Score-Heuristik
