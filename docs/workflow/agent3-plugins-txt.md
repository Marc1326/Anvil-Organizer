# Agent 3 Report: Fallout 4 Plugin + MO2-Vergleich
**Datum:** 2026-03-01

---

## 1. plugins_txt_path() — Wie wird der Pfad bestimmt?

### BaseGame (base_game.py, Zeile 365-367)

```python
def plugins_txt_path(self) -> Path | None:
    """Return path to plugins.txt in the Proton prefix, or None."""
    return None
```

Die Basisklasse gibt immer `None` zurück. Nur Game-Plugins, die plugins.txt brauchen, überschreiben diese Methode.

### Fallout4Game (game_fallout4.py, Zeile 152-161)

```python
def plugins_txt_path(self) -> Path | None:
    prefix = self.protonPrefix()
    if prefix is not None:
        return prefix / self._WIN_PLUGINS_TXT
    return None
```

Der Pfad setzt sich zusammen aus:
- `protonPrefix()` = `<steam-library>/steamapps/compatdata/377160/pfx`
- `_WIN_PLUGINS_TXT` = `drive_c/users/steamuser/AppData/Local/Fallout4/plugins.txt`

**Ergebnis:** Vollständiger Pfad z.B.:
`/mnt/gamingS/SteamLibrary/steamapps/compatdata/377160/pfx/drive_c/users/steamuser/AppData/Local/Fallout4/plugins.txt`

**Lücke:** GOG-Spiele geben `None` zurück, da `protonPrefix()` nur für Steam funktioniert (`if self._detected_store != "steam": return None`).

---

## 2. has_plugins_txt() — Wann gibt es True zurück?

**Datei:** `anvil/plugins/base_game.py` (Zeile 361-363)

```python
def has_plugins_txt(self) -> bool:
    """Return True if this game uses a plugins.txt load order file."""
    return bool(self.PRIMARY_PLUGINS)
```

Gibt `True` zurück wenn die Klasse eine **nicht-leere** `PRIMARY_PLUGINS`-Liste hat. Aktuell hat nur `Fallout4Game` eine solche Liste.

---

## 3. PRIMARY_PLUGINS — Welche Plugins sind definiert?

**Datei:** `anvil/plugins/games/game_fallout4.py` (Zeile 68-77)

```python
PRIMARY_PLUGINS = [
    "Fallout4.esm",
    "DLCRobot.esm",           # Automatron
    "DLCworkshop01.esm",      # Wasteland Workshop
    "DLCCoast.esm",           # Far Harbor
    "DLCworkshop02.esm",      # Contraptions Workshop
    "DLCworkshop03.esm",      # Vault-Tec Workshop
    "DLCNukaWorld.esm",       # Nuka-World
    "DLCUltraHighResolution.esm",
]
```

Zusätzlich gibt es eine **separate** `DLC_PLUGINS`-Liste (Zeile 88-95), die eine Teilmenge ist (ohne `Fallout4.esm` und `DLCUltraHighResolution.esm`). Diese wird aktuell **nirgends verwendet**.

---

## 4. MO2-Vergleich: Wie schreibt MO2 die plugins.txt?

### MO2-Architektur (dreischichtig)

**Schicht 1: Profil-basierte plugins.txt**
- `Profile::getPluginsFileName()`: Speichert plugins.txt im **Profil-Ordner**, NICHT im AppData-Ordner
- Zusätzlich: `loadorder.txt`, `lockedorder.txt`

**Schicht 2: GamePlugins Feature**
- `GamePlugins::writePluginLists()` — Interface das vom Game-Plugin implementiert wird
- Wird über `PluginList::saveTo()` aufgerufen

**Schicht 3: Load-Order-Mechanismen**
MO2 unterstützt drei verschiedene Mechanismen:
- `LoadOrderMechanism::FileTime` — Ältere Spiele (Oblivion): Reihenfolge über Datei-Zeitstempel
- `LoadOrderMechanism::PluginsTxt` — Neuere Spiele (Skyrim SE, Fallout 4): Reihenfolge über plugins.txt
- `LoadOrderMechanism::None` — Spiele ohne Load-Order

### MO2: Plugin-Klassifizierung (3 Typen)

| MO2-Konzept | Bedeutung | Anvil-Äquivalent |
|---|---|---|
| `primaryPlugins` | Kern-ESMs — nicht verschiebbar, nicht deaktivierbar | `PRIMARY_PLUGINS` |
| `enabledPlugins` | Plugins die aktiv sein müssen aber verschiebbar | Nicht implementiert |
| `DLCPlugins` | DLC-ESMs für Mod-Typ-Erkennung | `DLC_PLUGINS` (ungenutzt) |

### MO2: forceLoaded vs. forceEnabled vs. forceDisabled

```cpp
bool forceLoaded  = forceEnableCoreFiles && primaryPlugins.contains(filename);
bool forceEnabled = enabledPlugins.contains(filename);
bool forceDisabled = loadOrderMechanismNone && !forceLoaded && !forceEnabled;
```

- `forceLoaded` = NICHT deaktivierbar und NICHT verschiebbar (immer ganz oben)
- `forceEnabled` = NICHT deaktivierbar, aber VERSCHIEBBAR
- `forceDisabled` = NICHT aktivierbar (LoadOrderMechanism == None)

**Anvil-Status:** Kennt nur `PRIMARY_PLUGINS` (= forceLoaded). `enabledPlugins` und `forceDisabled` nicht implementiert.

### MO2: Light Plugins (.esl)

MO2 prüft ob das Spiel Light Plugins unterstützt (`lightPluginsAreSupported()`). Falls nicht, werden `.esl`-Dateien als `forceDisabled` markiert.

**Anvil-Status:** Scannt `.esl`-Dateien und zeigt sie an, aber prüft nicht ob das Spiel sie unterstützt.

---

## 5. Unterschiede Anvil vs. MO2

| Feature | MO2 | Anvil | Differenz |
|---|---|---|---|
| **Scan-Quelle** | Virtuelles Dateisystem (VFS) | Nur `game_path/Data/` (physisch) | KRITISCH: Anvil sieht nur deployed Plugins |
| **plugins.txt Speicherort** | Profil-Ordner (pro Profil) | AppData im Proton-Prefix | Anvil hat kein Profil-System dafür |
| **Schreibzeitpunkt** | Bei jeder Änderung (Drag&Drop, Checkbox, LOOT-Sort) | Nur bei Deploy/Purge | MO2 ist reaktiver |
| **Plugin aktivieren/deaktivieren** | Per Checkbox, persistent im Profil | Phase 1: Alle Plugins immer aktiv (`*`-Prefix) | Keine User-Auswahl |
| **Load-Order ändern** | Drag&Drop in Plugin-Liste | Nicht implementiert | Reihenfolge ist fest |
| **Primary Plugins** | `forceLoaded` = nicht verschieb-/deaktivierbar | Grau/kursiv dargestellt, ohne Checkbox | Ähnlich |
| **Light Plugins (.esl)** | Spezial-Index (FE:xxx), Prüfung ob unterstützt | Werden angezeigt, aber kein Spezial-Index | Fehlt |
| **Mod-Index-Berechnung** | Regular (00-FD), ESL (FE:xxx), Medium (FD:xx) | Einfach fortlaufend: `idx:02X` | Falsch bei ESLs |
| **Plugin-Herkunft (Origin)** | Zeigt welcher Mod das Plugin liefert | Nicht implementiert | Fehlt |
| **Master-Prüfung** | `testMasters()` | Nicht implementiert | Fehlt |
| **Locked Order** | Feste Positionen für bestimmte Plugins | Nicht implementiert | Fehlt |
| **GOG-Support** | Voller Support | `plugins_txt_path()` gibt None zurück | Fehlt |

### Kritische Unterschiede im Detail

**1. Scan-Quelle (WICHTIGSTER Unterschied)**

MO2 scannt sein virtuelles Dateisystem — es sieht ALLE Plugins aus ALLEN aktivierten Mods, auch wenn sie noch nicht deployed sind. Anvil scannt nur `game_path/Data/`, also nur Plugins die physisch auf der Festplatte liegen.

**2. Mod-Index-Berechnung**

MO2 berechnet den Mod-Index korrekt:
- Reguläre Plugins: `00` bis `FD` (max. 254)
- Light Plugins (.esl / ESL-flagged): `FE:000` bis `FE:FFF` (teilen sich Slot FE, max. 4096)

Anvil zählt einfach fortlaufend, was für ESL-Plugins falsche Werte ergibt.

**3. Purge-Verhalten**

Laut Git-History (Commit `69521fc`): Es gab einen Bug wo plugins.txt bei jedem Purge-Zyklus gelöscht wurde. Dies wurde gefixt.

---

## 6. Empfehlungen für zukünftige Verbesserungen

1. **Plugin-Aktivierung/Deaktivierung** — Checkbox im Plugins-Tab sollte steuern ob `*` vor dem Plugin-Namen in plugins.txt steht
2. **Load-Order per Drag&Drop** — User sollten die Reihenfolge ändern können
3. **ESL-Index-Berechnung** — Mod-Index für `.esl`-Dateien ist falsch, sollte MO2-Algorithmus übernehmen
4. **GOG-Support** — `plugins_txt_path()` sollte auch für GOG-/Lutris-/Heroic-Wine-Prefixe funktionieren
5. **Mod-Origin-Anzeige** — Zeigen welcher Mod ein Plugin liefert
6. **Master-Validation** — Prüfen ob alle Master-Abhängigkeiten erfüllt sind

---

## 7. Betroffene Dateien

| Datei | Rolle |
|-------|-------|
| `anvil/plugins/base_game.py` | Basisklasse: has_plugins_txt(), plugins_txt_path(), PRIMARY_PLUGINS |
| `anvil/plugins/games/game_fallout4.py` | Fallout 4: überschreibt plugins_txt_path(), definiert PRIMARY/DLC_PLUGINS |
| `anvil/core/plugins_txt_writer.py` | Scan, Write, Remove von plugins.txt |
| `anvil/widgets/game_panel.py` | UI: Plugins-Tab, Deploy/Purge-Integration |
