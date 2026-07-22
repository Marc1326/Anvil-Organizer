# #97 Custom Instance Paths – autonomer Ausführungsplan

> **Für Hermes:** Diesen Plan nach Marcs ausdrücklichem `GO` selbstständig und ohne weitere Routine-Rückfragen abarbeiten. **Kein Claude Code, keine Subagents, keine ACP-Weiterleitung und keine Agenten-/Review-Loops.** Nicht committen oder pushen. BG3-Code und GRB-Semantik nicht verändern.

**Erstellt:** 2026-07-22

**Ziel:** Die bereits konfigurierbaren benutzerdefinierten Pfade für Mods, Downloads, Profile und Overwrite müssen in allen normalen Anvil-Abläufen als gemeinsame Datenquelle verwendet werden. Ein fehlendes externes Laufwerk muss fail-closed behandelt werden. Diese Phase schafft das sichere Fundament für den späteren Assistenten „Verzeichnisse verschieben“.

**Architektur:** Ein unveränderliches `InstancePaths`-Objekt löst Pfade genau einmal aus den Instanzdaten auf. MainWindow, Installer, Scanner/Index, Profile/Groups, Collection/Backup und der normale Deployer erhalten diese aufgelösten Pfade, statt selbst `<instance>/.mods` und `<instance>/.profiles` zusammenzubauen. Pfadauflösung erzeugt keine externen Verzeichnisse. Verfügbarkeit und Schreibbarkeit werden getrennt geprüft.

**Technik:** Python 3, PySide6/QSettings, `pathlib`, bestehende Anvil-Core-Klassen, `unittest`/pytest-kompatible Tests.

---

## 1. Freigabe und Auto-Modus

### Einmalige Freigabe

Marc gibt nach Durchsicht dieses Plans einmal **`GO`**. Dieses GO gilt für alle Aufgaben dieser Phase A1–A7 und die Abschlussprüfung.

### Danach arbeitet Hermes ohne Routine-Rückfragen weiter

Hermes darf nach dem GO selbstständig:

- die hier genannten Dateien ändern oder neu anlegen,
- Regressionstests vor der Implementierung schreiben,
- gezielte Tests beliebig oft ausführen,
- kleine direkt verursachte Fehler innerhalb dieses Scopes korrigieren,
- Syntax-, Locale- und vollständige Projekttests ausführen,
- Anvil am Ende über `restart.sh` neu starten und Logs read-only prüfen.

### Hermes unterbricht nur bei einem echten Stop-Grund

1. Gefahr von Datenverlust oder Änderung realer Nutzer-/Spieldaten.
2. Eine notwendige Änderung außerhalb der unten genannten Architektur, besonders BG3 oder gemeinsame GRB-Forge-Semantik.
3. Ein destruktiver Git-Befehl, Commit, Push oder Rollback wäre nötig.
4. Die Tests zeigen einen bereits vorhandenen Fehler, dessen Behebung den Scope deutlich erweitert.
5. Eine Produktentscheidung ist nicht durch diesen Plan beantwortet.
6. Eine Abhängigkeit oder das Build-System ist defekt und zwei direkte Alternativen sind gescheitert.

Ein fehlgeschlagener gewöhnlicher Test ist **kein** Rückfragegrund; Hermes diagnostiziert und korrigiert ihn selbst innerhalb des Scopes.

### Ausdrücklich verboten

- Claude Code, Claude-CLI, Anthropic-VS-Code-Worker oder ACP zu Claude.
- Hermes-Subagents oder andere autonome Review-Agenten.
- automatische Review-Loops.
- automatische Commits oder Pushes.
- Änderungen an BG3-Dateien oder BG3-Verhalten.
- ungefragte Umbauten oder Vereinheitlichungen außerhalb von #97.
- Löschen, Verschieben oder Migrieren echter vorhandener Moddaten in dieser Phase.

---

## 2. Voraussetzung vor dem GO

Der aktuelle Branch `main` enthält noch den großen uncommitteten Loadorder-Umbau mit über 1.000 geänderten Zeilen. Diese Speicherpfad-Phase darf nicht mit ihm vermischt werden.

**Sicherer Ablauf:**

1. Marc testet den aktuellen Loadorder-Stand als Endnutzer.
2. Danach separater Commit des Loadorder-Stands – nur nach Marcs Aufforderung.
3. Erst anschließend `GO` für diesen Plan.
4. Vor der ersten Änderung prüft Hermes `git status --short` und `git diff --stat`.
5. Sind unerwartete neue Änderungen vorhanden, wird gestoppt und Marc informiert.

Es erfolgt kein Reset, Checkout, Stash oder sonstiger Rollback ohne Marcs ausdrückliche Erlaubnis.

---

## 3. Aktueller Ist-Zustand

### Bereits vorhanden

- Instanzdaten speichern:
  - `path_mods_directory`
  - `path_downloads_directory`
  - `path_profiles_directory`
  - `path_overwrite_directory`
- `settings_dialog.py` zeigt und persistiert diese Werte.
- MainWindow löst Mods und Downloads beim Instanzladen teilweise auf.
- DownloadManager erhält bereits den aufgelösten Downloadpfad.

### Noch inkonsistent

- `ModInstaller` setzt `mods_path` fest auf `instance_path / ".mods"`.
- `ModDeployer` setzt Mods und Profile fest auf `instance_path / ".mods"` und `.profiles`.
- MainWindow verwendet an vielen operativen Stellen weiterhin direkte `.mods`-/`.profiles`-Pfade:
  - Profilauflistung und aktives Profil,
  - Gruppenbereinigung,
  - globale Modlist,
  - Collection/Backup,
  - Modpfade in Dialogen,
  - Ordner öffnen,
  - Separatoren und weitere Modoperationen.
- Es gibt noch keinen zentralen `InstancePaths`-Vertrag.
- Es gibt keine gezielten Tests für Custom-Pfade.
- Ein fehlender externer Mount könnte an einzelnen Stellen durch `mkdir()` als leeres lokales Verzeichnis neu erzeugt werden.

---

# Aufgabe A1 – Zentraler `InstancePaths`-Vertrag

## Ziel

Alle konfigurierbaren Instanzpfade werden an genau einer Stelle aufgelöst. Die Auflösung bleibt rein und erzeugt keine Verzeichnisse.

## Dateien

- Neu: `anvil/core/instance_paths.py`
- Neu: `tests/test_instance_paths.py`
- Ändern: `anvil/core/instance_manager.py` nur soweit nötig, um die Instanzdaten sauber an den Resolver zu übergeben.

## Vorgesehene API

```python
@dataclass(frozen=True)
class InstancePaths:
    instance: Path
    mods: Path
    downloads: Path
    profiles: Path
    overwrite: Path
    backups: Path
    cache: Path


def resolve_instance_paths(
    instance_path: Path,
    instance_data: Mapping[str, Any],
) -> InstancePaths:
    ...
```

## Regeln

- `%INSTANCE_DIR%` wird nur als führender Platzhalter unterstützt.
- `~` wird aufgelöst.
- Relative Werte ohne `%INSTANCE_DIR%` werden abgelehnt oder dokumentiert auf die Instanz bezogen; Verhalten muss durch Tests festgelegt werden, bevor implementiert wird.
- NUL und leere Custom-Werte werden abgelehnt beziehungsweise verwenden den dokumentierten Default.
- Ergebnis ist absolut und normalisiert, aber bestehende Symlinks werden nicht ungefragt dereferenziert.
- Auflösung ruft niemals `mkdir()` auf.
- Defaults bleiben:
  - `.mods`
  - `.downloads`
  - `.profiles`
  - `.overwrite`
  - `.backups`
  - `.webcache`

## TDD-Schritte

1. Test für alle Defaultpfade schreiben.
2. Test für externe absolute Mods-/Downloads-/Profiles-/Overwrite-Pfade schreiben.
3. Test für Leerzeichen und Unicode schreiben.
4. Test schreiben, dass ein fehlender externer Pfad nicht erzeugt wird.
5. Test für ungültige Werte und Platzhalter schreiben.
6. Gezielt rot ausführen:

```bash
QT_QPA_PLATFORM=offscreen uv run --python .venv/bin/python --with pytest \
  python -m pytest -q tests/test_instance_paths.py
```

7. Minimalen Resolver implementieren.
8. Tests grün ausführen.

---

# Aufgabe A2 – Installer nutzt den aufgelösten Mods-Pfad

## Ziel

Jede normale Installation landet im konfigurierten Mods-Verzeichnis und niemals zusätzlich in `<instance>/.mods`.

## Dateien

- Ändern: `anvil/core/mod_installer.py`
- Ändern: `anvil/mainwindow.py`
- Neu: `tests/test_custom_mods_path.py`

## Umsetzung

- `ModInstaller.__init__` erhält optional explizit `mods_path: Path | None = None`.
- Ohne Übergabe bleibt aus Rückwärtskompatibilität `instance_path / ".mods"` erhalten.
- MainWindow übergibt immer `InstancePaths.mods` für normale Installationen.
- FOMOD-, Drag-and-drop-, Download- und Framework-Aufrufe werden inventarisiert und auf denselben Installerpfad geführt.
- Kein BG3-Installer wird verändert.

## Tests

1. Echtes kleines ZIP in ein externes temporäres Mods-Verzeichnis installieren.
2. Ziel existiert ausschließlich extern.
3. `<instance>/.mods/<mod>` wurde nicht erzeugt.
4. Fehlender/nicht schreibbarer externer Pfad führt sichtbar zum Fehlschlag und nicht zum Default-Fallback.
5. Default-Aufruf ohne `mods_path` verhält sich unverändert.

---

# Aufgabe A3 – MainWindow, Scan, Index, Gruppen und Profile

## Ziel

Alle normalen Lese- und Profiloperationen verwenden dasselbe `InstancePaths`-Objekt.

## Dateien

- Ändern: `anvil/mainwindow.py`
- Ändern: `anvil/core/mod_entry.py`, falls der Scanner dort den Root selbst bildet.
- Ändern: `anvil/core/mod_index.py`, falls der Index den Root selbst bildet.
- Ändern: Profile-/Group-Helfer nur dort, wo sie einen Instanzroot statt eines expliziten Pfads erwarten.
- Neu: `tests/test_custom_instance_paths.py`
- Bestehenden Symlink-Schutz in `anvil/core/profile_name.py` beibehalten und auf den aufgelösten Profiles-Root abstimmen.

## Umsetzung

- MainWindow speichert für die aktive Instanz `self._current_instance_paths`.
- `_current_downloads_path` darf zunächst als Kompatibilitätsalias bestehen bleiben, wird aber aus `InstancePaths.downloads` gesetzt.
- Aktives Profil ist `InstancePaths.profiles / profile_name`.
- Profil erstellen, umbenennen, wechseln und löschen bleibt gegen Traversal und Symlinks geschützt.
- Modscan, Gruppenbereinigung, Separatoren, Moddetails und „Mods-Ordner öffnen“ verwenden `InstancePaths.mods`.
- Download-Metadaten und „Downloads-Ordner öffnen“ verwenden `InstancePaths.downloads`.
- Keine externe fehlende Root wird während des normalen Ladens erzeugt.

## Tests

- Modscan sieht Mods im externen Root.
- Profilwechsel liest/schreibt im externen Profiles-Root.
- Profile zweier Roots bleiben getrennt.
- Gruppenbereinigung schaut in den externen Mods-Root.
- Profil-Symlink nach außerhalb bleibt abgelehnt.
- Defaults bleiben unverändert.

---

# Aufgabe A4 – Collection, Backup und weitere Pfadverbraucher

## Ziel

Collection- und Backup-Abläufe lesen dieselben Roots wie UI und Installer.

## Dateien

- Ändern: `anvil/core/collection_io.py`
- Ändern: `anvil/mainwindow.py` für integrierte Backup-/Restore-Pfade.
- Weitere Datei nur, wenn die read-only Inventur einen direkten operativen `.mods`-/`.profiles`-Pfad nachweist.
- Neu/erweitern: `tests/test_custom_instance_paths.py`

## Vorgehen

1. Vor Änderungen alle operativen Treffer suchen:

```bash
rg 'instance_path\s*/\s*["'"']\.(mods|downloads|profiles|overwrite|backups|webcache)["'"']' anvil
```

2. Jeden Treffer klassifizieren:
   - zu ersetzen,
   - absichtlicher Rückwärtskompatibilitätsdefault,
   - Test/Dokumentation/Kommentar.
3. Nur operative Treffer dieser Phase ersetzen.
4. Collection-Analyse/-Export und Backup lesen externe Mods/Profile.
5. Backupziel verwendet `InstancePaths.backups`.
6. Restore schreibt nur in die explizit aufgelösten Roots und folgt keinen fremden Symlinks.

## Tests

- Collection sieht extern installierte Mods.
- Backup enthält Metadaten aus externem Mods-/Profiles-Root.
- Defaultinstanz erzeugt denselben Aufbau wie bisher.
- Externe Quellen werden bei fehlendem Laufwerk nicht als leer interpretiert.

---

# Aufgabe A5 – Normaler Deployer und Purge

## Ziel

Der Standard-Deployer deployt aus dem konfigurierten Mods-Root und liest die Modlist aus dem konfigurierten Profiles-Root.

## Dateien

- Ändern: `anvil/core/mod_deployer.py`
- Ändern: `anvil/widgets/game_panel.py`
- Ändern: zentrale Deployer-Factories nur wenn nötig.
- Neu: `tests/test_custom_deployer_paths.py`

## Umsetzung

- `ModDeployer` erhält optionale explizite `mods_path` und `profiles_path`.
- Alte Aufrufe ohne Parameter behalten Defaults.
- Manifest bleibt im Instanzroot.
- Purge entfernt nur verwaltete Links, deren Ziel innerhalb des konfigurierten erlaubten Mods-Roots liegt.
- Links in fremde externe Pfade bleiben unangetastet.
- GamePanel übergibt die aufgelösten Pfade an normale Deployer.
- GRB erhält bei Bedarf nur die bereits aufgelösten Bibliothekspfade; Forge-Logik und GRB-spezifische Semantik werden nicht geändert.
- BG3-Dateien und BG3-Zweig bleiben unverändert.

## Tests

- Aktiver Mod aus externem Root wird korrekt verlinkt.
- Linkziel liegt im externen Root.
- Purge entfernt den verwalteten Link.
- Fremder Link außerhalb des registrierten Roots bleibt bestehen.
- Default-Deployer verhält sich unverändert.
- Bestehende GRB-Tests bleiben grün.

---

# Aufgabe A6 – Missing-Drive-/Offline-Verhalten

## Ziel

Ein fehlendes konfiguriertes Laufwerk wird sichtbar und fail-closed behandelt. Anvil erzeugt dort oder auf der Systemplatte keinen leeren Ersatz.

## Dateien

- Erweitern: `anvil/core/instance_paths.py`
- Ändern: `anvil/mainwindow.py`
- Ändern: vorhandene Settings-/Diagnoseanzeige nur mit bestehendem QSS und bestehenden Widgets.
- Neu: `tests/test_instance_storage_offline.py`
- Locale-Keys nur falls neue Meldungen nötig: alle sieben `anvil/locales/*.json`.

## Statusmodell

```python
@dataclass(frozen=True)
class StorageComponentStatus:
    component: str
    path: Path
    exists: bool
    is_directory: bool
    readable: bool
    writable: bool
```

## Verhalten

- Extern konfigurierter, fehlender Pfad markiert Komponente/Instanz offline.
- Meldung nennt den exakten fehlenden Pfad.
- Kein Installieren, Scannen als leer oder Deployen.
- Keine automatische Rückkehr zu `.mods`/`.profiles`.
- Kein `mkdir(parents=True)` auf dem fehlenden externen Mount während normalen Ladens.
- Bestehende Instanz bleibt in der Auswahl sichtbar.
- Für diese Phase genügt eine klare Meldung plus sicherer Abbruch; ein vollständiger „Wiederfinden“-Dialog gehört zum späteren Verschiebe-Assistenten.

## Tests

- Fehlende Mods-Root bleibt nicht existent.
- Instanzladen löscht oder überschreibt keinen konfigurierten Pfad.
- Installer/Deployer starten nicht.
- Defaultpfad darf bei einer neuen lokalen Instanz weiterhin regulär erzeugt werden.

---

# Aufgabe A7 – Regression, Scope- und Startprüfung

## Ziel

Nachweisen, dass #97 funktioniert, Defaults unverändert sind und keine verbotenen Bereiche verändert wurden.

## Gezielte Tests

```bash
QT_QPA_PLATFORM=offscreen uv run --python .venv/bin/python --with pytest \
  python -m pytest -q \
  tests/test_instance_paths.py \
  tests/test_custom_mods_path.py \
  tests/test_custom_instance_paths.py \
  tests/test_custom_deployer_paths.py \
  tests/test_instance_storage_offline.py
```

## Bestehende Risikobereiche

```bash
QT_QPA_PLATFORM=offscreen uv run --python .venv/bin/python --with pytest \
  python -m pytest -q \
  tests/test_plugin_load_order.py \
  tests/test_predeploy_launch.py \
  tests/test_grb_deployer.py \
  tests/test_game_ghostreconbreakpoint.py \
  tests/test_grb_forge.py
```

## Vollständiger Lauf

```bash
QT_QPA_PLATFORM=offscreen uv run --python .venv/bin/python --with pytest \
  python -m pytest -q tests
.venv/bin/python -m compileall -q anvil tests
git diff --check
```

## Locale-Prüfung

Alle sieben JSON-Dateien werden geparst. Neue Schlüssel müssen in `de`, `en`, `es`, `fr`, `it`, `pt`, `ru` vorhanden sein.

## Scope-Prüfung

- `git diff --name-only` darf keine BG3-Datei enthalten.
- Keine Änderung an GRB-Forge-Dateien.
- Keine Inline-Styles oder neue QSS-Farben.
- Keine Claude-/ACP-/Subagent-Prozesse.
- Kein Commit oder Push.

## Laufzeitprüfung

1. Vorhandenen Anvil-Prozess kontrolliert beenden.
2. `./restart.sh` starten.
3. `debug.log` auf Tracebacks, Import-/Signalfehler und Pfadfehler prüfen.
4. Nur synthetische/tempfile-basierte Daten verwenden; keine realen Modbibliotheken migrieren.

---

## 4. Akzeptanzkriterien für dieses eine GO

Die autonome Phase ist abgeschlossen, wenn:

- externe Mods-, Downloads-, Profiles- und Overwrite-Pfade zentral aufgelöst werden,
- normaler Installer, Scan/Index, Profile/Groups, Collection/Backup und Standard-Deployer dieselben Roots verwenden,
- Defaultinstanzen unverändert funktionieren,
- ein fehlendes externes Laufwerk fail-closed bleibt und kein leeres Fallback erzeugt,
- Purge keine fremden externen Symlinks löscht,
- BG3 unverändert bleibt,
- GRB-Forge-Semantik unverändert bleibt,
- gezielte und vollständige Tests grün sind,
- Anvil startet und der Log keine neuen Fehler enthält,
- kein Claude Code/Subagent verwendet wurde,
- kein Commit oder Push erfolgt ist.

Danach meldet Hermes kompakt:

1. welche Dateien geändert wurden,
2. welche Tests tatsächlich mit welchem Ergebnis liefen,
3. bekannte Grenzen,
4. ob Marc als Endnutzer testen kann,
5. Erinnerung: „Soll ich committen?“ erst nach Marcs Test.

---

## 5. Noch nicht Teil dieses GO

Diese Punkte werden erst nach erfolgreichem #97-Endnutzertest separat geplant/freigegeben:

- GUI-Assistent „Verzeichnisse verschieben“,
- Größen-/Dateiinventur im Hintergrund,
- journaled copy/verify/switch/rollback,
- Abbruch und Wiederaufnahme langer Migrationen,
- mehrere Spiele in einer Warteschlange,
- globale Basisverzeichnis-Migration #80,
- Verteilung der Mods eines Spiels auf mehrere Laufwerke,
- vollständiger Instanzexport/-import.

Der bestehende Gesamtbericht bleibt die Architekturreferenz:

```text
.hermes/plans/2026-07-21_221519-storage-management-and-directory-migration.md
```
