# Agent 3 Report: Re-Deploy Architektur-Analyse

**Datum:** 2026-03-02
**Scope:** Analyse von `ModDeployer.deploy()`, `ModDeployer.purge()`, Performance-Einschaetzung und Race-Condition-Risiken

---

## 1. Detaillierte Analyse von deploy()

**Datei:** `anvil/core/mod_deployer.py`, Zeilen 109-338

### Was deploy() genau macht (Schritt fuer Schritt):

1. **Alte Deployment-Bereinigung** (Zeile 124-132): Ruft ZUERST `self.purge()` auf, wenn ein bestehendes Manifest existiert. Jeder deploy() beginnt mit einer kompletten Bereinigung.

2. **Modlist lesen** (Zeile 136-142): Liest die globale `modlist.txt` (Load-Order) und `active_mods.json` (welche Mods aktiv sind) aus dem aktuellen Profil-Verzeichnis.

3. **Mods iterieren** (Zeile 155-307): Iteriert ueber ALLE aktivierten Mods in Prioritaetsreihenfolge (niedrig -> hoch):
   - Ueberspringt Separatoren (`_separator`)
   - **LML-Mods** (mit `install.xml`): Erstellt einen einzelnen Verzeichnis-Symlink
   - **Normale Mods**: Durchlaeuft ALLE Dateien via `mod_dir.rglob("*")`:
     - Ueberspringt Metadaten (`meta.ini`, `codes.txt`)
     - Bei BA2-Packing: Nur bestimmte Dateitypen werden als Symlinks deployed
     - Berechnet den Zielpfad (mit data_path, multi_folder_routes, nest_under_mod_name)
     - **Sicherheitsregel**: Ueberschreibt NIEMALS echte (non-symlink) Game-Dateien
     - Erstellt Parent-Verzeichnisse falls noetig
     - Erstellt Symlinks (`target.symlink_to(src_file)`)
     - **Direct-Install-Mods**: Werden per `shutil.copy2()` kopiert statt gelinkt

4. **Manifest speichern** (Zeile 309-325): Schreibt `.deploy_manifest.json` mit allen erstellten Symlinks und Verzeichnissen.

### Operationstypen:
- **Primaer: Symlinks** (`os.symlink()`) -- extrem schnell, O(1) pro Datei
- **Sekundaer: Kopien** (`shutil.copy2()`) -- nur fuer direct-install Mods
- **Verzeichnisse erstellen** (`mkdir(parents=True)`) -- nur wenn noetig

---

## 2. Detaillierte Analyse von purge()

**Datei:** `anvil/core/mod_deployer.py`, Zeilen 340-434

### Was purge() genau macht:

1. **Manifest lesen** (Zeile 351-362): Liest `.deploy_manifest.json`
2. **Symlinks entfernen** (Zeile 366-406):
   - Direct-Install-Kopien werden NICHT entfernt (bewusste Design-Entscheidung)
   - Verzeichnis-Symlinks (LML) werden entfernt
   - Normale Symlinks: Sicherheitspruefung -- nur entfernen wenn Ziel in `.mods/` liegt
   - Kaputte Symlinks (broken) duerfen entfernt werden
3. **Leere Verzeichnisse aufraemen** (Zeile 414-426): Entfernt leere Verzeichnisse (deepest first)
4. **Manifest loeschen** (Zeile 429-432)

### Operationstypen:
- **Symlinks loeschen** (`unlink()`) -- extrem schnell, O(1) pro Link
- **Verzeichnisse entfernen** (`rmdir()`) -- nur leere Verzeichnisse
- **Manifest loeschen** -- eine einzige Datei

---

## 3. Performance-Einschaetzung

### Symlink-Operationen (deploy + purge):

| Operation | Systemaufruf | Geschwindigkeit | Typ |
|-----------|-------------|-----------------|-----|
| `symlink_to()` | `symlink()` | ~5-20 Mikrosekunden | O(1) |
| `unlink()` | `unlink()` | ~5-15 Mikrosekunden | O(1) |
| `mkdir()` | `mkdir()` | ~10-30 Mikrosekunden | O(1) |
| `rmdir()` | `rmdir()` | ~5-15 Mikrosekunden | O(1) |
| `rglob("*")` | `readdir()` rekursiv | variabel, I/O-bound | O(n) |

### Beispielrechnungen:

| Szenario | Mods | Dateien gesamt | purge() + deploy() | Geschaetzte Zeit |
|----------|------|---------------|---------------------|------------------|
| Klein (Witcher 3) | 20 | ~200 Symlinks | 400 Operationen + rglob | ~50-100ms |
| Mittel (Skyrim) | 100 | ~2.000 Symlinks | 4.000 Operationen + rglob | ~200-500ms |
| Gross (Skyrim Heavy) | 300 | ~10.000 Symlinks | 20.000 Operationen + rglob | ~1-3 Sekunden |
| Extrem (Fallout 4) | 500+ | ~30.000 Symlinks | 60.000 Operationen + rglob | ~3-8 Sekunden |

### Hauptkosten-Treiber:

1. **`rglob("*")`** -- Der TEUERSTE Teil! Fuer jeden aktivierten Mod wird der komplette Mod-Ordner rekursiv durchsucht. Bei 300 Mods mit je 100 Dateien sind das 30.000 `readdir()`-Aufrufe.
2. **Manifest JSON** -- Serialisierung/Deserialisierung der Manifest-Datei
3. **Symlink-Erstellung selbst** -- Vernachlaessigbar schnell

### Fazit Performance:
- **Fuer 1-50 Mods**: Re-Deploy ist praktisch instantan (<100ms)
- **Fuer 50-200 Mods**: Spuerbar, aber akzeptabel (200-500ms)
- **Fuer 200+ Mods**: Ein Re-Deploy bei JEDEM einzelnen Checkbox-Toggle waere zu teuer (>1 Sekunde pro Toggle)

---

## 4. silent_deploy() -- Der vollstaendige Orchestrator

`GamePanel.silent_deploy()` (`anvil/widgets/game_panel.py:546-603`) macht mehr als nur `ModDeployer.deploy()`:

1. `self._deployer.deploy()` -- Symlinks erstellen
2. **BA2-Packing** (Bethesda-Spiele): `BA2Packer.pack_all_mods()` -- SEHR TEUER (Wine/BSArch, mehrere Sekunden)
3. **plugins.txt schreiben** (Bethesda-Spiele): `PluginsTxtWriter.write()` -- Scannt Data-Verzeichnis
4. **Plugins-Tab aktualisieren**: `self._refresh_plugins_tab()`

**KRITISCH:** Bei einem Re-Deploy nach Mod-Toggle muesste man `silent_purge()` + `silent_deploy()` aufrufen. Das ist bei Bethesda-Spielen MASSIV teuer wegen BA2-Packing.

---

## 5. plugins.txt -- Wie sie geschrieben wird

**Datei:** `anvil/core/plugins_txt_writer.py`

### Ablauf:
1. `scan_plugins()` -- Scannt `game_path/Data/` nach `.esp/.esm/.esl` Dateien via `os.scandir()`
2. Sortierung: Primary Plugins zuerst -> Masters (.esm) -> Rest (.esp/.esl)
3. `write()` -- Schreibt alle Plugins mit `*`-Prefix (aktiv) in UTF-8 mit `\r\n`
4. Entfernt Case-Varianten
5. Ziel: Proton-Prefix-Pfad (von Game-Plugin bestimmt)

### Relevanz fuer Re-Deploy:
Die plugins.txt wird bei jedem `silent_deploy()` neu geschrieben. Da sie deployed Symlinks im Data-Verzeichnis scannt, muss sie NACH dem Symlink-Deploy geschrieben werden.

---

## 6. Race-Condition Risiken

### Szenario: User toggelt schnell mehrere Mods

**Aktueller Zustand (OHNE Re-Deploy bei Toggle):**
- Kein Risiko, da nur `modlist.txt`/`active_mods.json` geschrieben wird
- Diese Schreiboperationen sind atomar genug (Path.write_text)

**Potentieller Zustand (MIT Re-Deploy bei Toggle):**

| Risiko | Beschreibung | Schwere |
|--------|-------------|---------|
| **Concurrent Filesystem Access** | purge() loescht Symlinks waehrend deploy() neue erstellt | HOCH |
| **Manifest Corruption** | deploy() liest altes Manifest waehrend purge() es loescht | HOCH |
| **UI-Freeze** | deploy() blockiert den Main-Thread (synchron!) | MITTEL |
| **BA2-Packing Conflict** | Wine/BSArch-Prozess laeuft noch waehrend neuer gestartet wird | KRITISCH |
| **Stale Data** | User toggelt Mod A+B schnell, aber deploy() liest nur den Zustand von A | MITTEL |

### Detaillierte Analyse:

1. **Kein Threading/Async**: `deploy()` und `purge()` sind synchrone Methoden im Main-Thread. Das schuetzt paradoxerweise vor echten Race Conditions, fuehrt aber zu UI-Freeze.

2. **BA2-Packing als Flaschenhals**: BA2Packer verwendet `QProcess` (Wine/BSArch). Wenn synchron abgewartet, ist die UI-Freeze-Zeit enorm.

---

## 7. Empfehlung: Debounce-Strategie

### Empfehlung: JA, Debounce ist DRINGEND empfohlen

**Vorgeschlagene Architektur:**

```python
# In MainWindow.__init__():
self._redeploy_timer = QTimer()
self._redeploy_timer.setSingleShot(True)
self._redeploy_timer.setInterval(500)  # 500ms Debounce
self._redeploy_timer.timeout.connect(self._do_redeploy)
```

```python
# In MainWindow._on_mod_toggled():
def _on_mod_toggled(self, row: int, enabled: bool) -> None:
    # ... bestehende Logik (entry update, modlist write) ...
    self._redeploy_timer.start()  # Reset bei jedem Toggle
```

```python
# Neuer Slot:
def _do_redeploy(self) -> None:
    self._game_panel.silent_purge()
    self._game_panel.silent_deploy()
```

### Warum 500ms?
- Genuegend Pause, damit User mehrere Mods schnell toggeln kann
- Kurz genug, dass das Ergebnis "sofort" sichtbar erscheint
- Standard-Debounce-Wert in vielen UI-Frameworks

### Alternativen:

| Strategie | Vorteile | Nachteile |
|-----------|---------|-----------|
| **Kein Re-Deploy** (aktuell) | Einfach, keine Risiken | Mods erst nach Neustart deployed |
| **Sofort Re-Deploy** | Immer aktuell | UI-Freeze bei vielen Mods |
| **Debounce 500ms** (empfohlen) | Responsiv + Effizient | Leichte Verzoegerung |
| **Manueller "Deploy"-Button** | Volle Kontrolle | Zusaetzlicher Klick noetig |
| **Async Worker-Thread** | Keine UI-Freeze | Komplexer, Thread-Sicherheit noetig |

### Wichtiger Sonderfall: Bethesda-Spiele mit BA2-Packing

Fuer Bethesda-Spiele (Skyrim, Fallout 4) ist der Re-Deploy SEHR teuer wegen BA2-Packing. Optionen:

1. **BA2 ueberspringen bei Checkbox-Toggle** -- Nur Symlinks re-deployen, BA2 nur vor Game-Start
2. **Laengerer Debounce** (2-3 Sekunden) fuer BA2-Spiele
3. **Worker-Thread** fuer BA2-Packing (langfristig beste Loesung)

**Empfehlung:** Option 1 -- Bei Re-Deploy nach Mod-Toggle NUR Symlinks + plugins.txt, KEIN BA2-Packing. BA2 nur vor Game-Start (`Run`-Button).

---

## 8. Zusammenfassung

| Aspekt | Ergebnis |
|--------|----------|
| **deploy() Mechanismus** | Symlinks (primaer), Kopien (direct-install) |
| **purge() Mechanismus** | Symlink-Entfernung via Manifest, leere Dirs aufraemen |
| **Performance deploy()** | ~50ms (klein) bis ~8s (extrem gross) |
| **Performance purge()** | ~20ms (klein) bis ~3s (extrem gross) |
| **Race Conditions** | Durch synchrone Ausfuehrung geschuetzt, aber UI-Freeze-Risiko |
| **Debounce empfohlen?** | JA, 500ms QTimer.singleShot |
| **Groesstes Risiko** | BA2-Packing bei Bethesda-Spielen (mehrere Sekunden) |
| **plugins.txt** | Wird bei jedem deploy() neu geschrieben (scannt Data/) |
