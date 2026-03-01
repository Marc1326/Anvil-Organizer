# Agent 1 Report: Analyse plugins_txt_writer.py
**Datum:** 2026-03-01

---

## 1. Symlink-Verhalten von `os.scandir()` + `entry.is_file()`

**Kritischer Befund:** In Zeile 56 wird `entry.is_file()` **ohne** den Parameter `follow_symlinks=False` aufgerufen. Das Standardverhalten von `os.DirEntry.is_file()` ist `follow_symlinks=True`.

Das bedeutet:
- **Symlinks auf reguläre Dateien werden als `True` erkannt** — das ist KORREKT für Anvils Anwendungsfall. Der Deployer erstellt Symlinks von `.mods/` nach `Data/`. Wenn `scan_plugins()` nach dem Deploy aufgerufen wird, sieht er die .esp/.esm/.esl Symlinks als normale Dateien — genau das gewünschte Verhalten.
- **Broken Symlinks** (Ziel existiert nicht) werden als `False` erkannt und übersprungen — ebenfalls korrekt.
- **Symlinks auf Verzeichnisse** werden als `False` erkannt — korrekt.

**Fazit:** Das `follow_symlinks`-Verhalten ist korrekt und passend. Kein Bug.

---

## 2. Verhalten bei leerer Plugin-Liste

In `write()` (Zeile 91-122):

```python
def write(self) -> Path | None:
    txt_path = self._game_plugin.plugins_txt_path()
    if txt_path is None:                          # Guard 1: kein Pfad
        return None

    plugins = self.scan_plugins()
    if not plugins:                                # Guard 2: keine Plugins
        print(f"{_TAG} No plugins found — skipping write")
        return None
```

**Verhalten:** Wenn `scan_plugins()` eine leere Liste zurückgibt, wird `write()` **abgebrochen und `None` zurückgegeben**. Es wird KEINE leere plugins.txt geschrieben. Das ist defensiv und korrekt.

Der Aufrufer in `game_panel.py` (Zeile 597-601) prüft das Ergebnis von `write()` **nicht**:

```python
writer = PluginsTxtWriter(...)
writer.write()  # Rückgabewert wird ignoriert
self._refresh_plugins_tab()
```

Kein Bug, aber keine Fehlermeldung an den User.

---

## 3. Plugin-Erkennung: Dateiendungen, Filter, Sortierung

**Dateiendungen** (Zeile 16):
```python
_PLUGIN_EXTENSIONS = {".esp", ".esm", ".esl"}
```

Groß-/Kleinschreibung wird in Zeile 58 normalisiert:
```python
ext = Path(entry.name).suffix.lower()
```

**Filter:**
- Nur direkt in `Data/` liegende Dateien (kein rekursives Scanning — `os.scandir` ist nicht rekursiv)
- Nur Dateien, keine Verzeichnisse
- Dateiname wird original beibehalten (case-preserving)

**Sortierung** (Zeile 69-88):
1. **PRIMARY_PLUGINS zuerst** — in der Reihenfolge der PRIMARY_PLUGINS-Liste (nur wenn auf Disk vorhanden)
2. **Masters (.esm)** — alphabetisch (case-insensitive)
3. **Andere (.esp/.esl)** — alphabetisch (case-insensitive)

Die Primary-Plugins werden case-insensitiv abgeglichen (`p.lower()`), aber der originale Dateiname wird beibehalten.

---

## 4. Edge Cases die zu einer leeren plugins.txt führen könnten

| Edge Case | Ergebnis | Risiko |
|-----------|----------|--------|
| `Data/` existiert nicht | `scan_plugins()` gibt `[]` zurück, `write()` bricht ab | Niedrig — normaler Zustand vor erstem Deploy |
| `Data/` hat nur Unterverzeichnisse | `is_file()` filtert diese raus, leere Liste | Unwahrscheinlich |
| Nur .ba2/.bsa Dateien in Data/ | Werden nicht als Plugins erkannt | Korrekt — kein Bug |
| `OSError` beim Scannen | `scan_plugins()` gibt `[]` zurück nach Print | Möglich bei Berechtigungsproblemen |
| `plugins_txt_path()` gibt `None` zurück | `write()` bricht ab, kein File geschrieben | Bei GOG-Spielen (kein Proton-Prefix) |
| Proton-Prefix existiert nicht / nicht gemountet | `protonPrefix()` gibt `None` zurück | Reales Risiko |
| Deploy vor Scan (Timing) | `scan_plugins()` sieht Symlinks als Dateien — korrekt | Kein Problem dank follow_symlinks=True Default |
| `GameDataPath` ist nicht "Data" | Anderer Pfad wird verwendet via `getattr(game_plugin, "GameDataPath", "Data")` | Korrekt implementiert |

---

## 5. Zusammenfassung

Der Code in `plugins_txt_writer.py` ist solide und defensiv geschrieben:

1. **Symlink-Handling ist korrekt** — `is_file()` mit Default `follow_symlinks=True` erkennt deployed Symlinks als reguläre Dateien
2. **Leere Listen werden sicher behandelt** — `write()` bricht ab ohne eine leere Datei zu schreiben
3. **Die Sortierung ist MO2-konform** — Primary Plugins zuerst, dann Masters, dann Rest

**Kein akuter Bug erkennbar.** Verbesserungspotential:
- Rückgabewert von `write()` wird vom Aufrufer ignoriert — kein Feedback wenn keine Plugins gefunden
- Keine Logging-Unterscheidung zwischen "Data/ nicht vorhanden" und "Data/ leer"

---

## Betroffene Dateien

| Datei | Rolle |
|-------|-------|
| `anvil/core/plugins_txt_writer.py` | Hauptdatei (137 Zeilen) |
| `anvil/widgets/game_panel.py` | Aufrufer (Zeilen 589-601, 621-632, 662-693) |
| `anvil/plugins/games/game_fallout4.py` | Game-Plugin mit PRIMARY_PLUGINS und plugins_txt_path() |
| `anvil/plugins/base_game.py` | Basis mit has_plugins_txt() und protonPrefix() |
