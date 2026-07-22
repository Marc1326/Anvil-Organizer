# Anvil Organizer — Cleanup-Zusammenfassung

## Ausgangslage

Es wurde nur gelesen und geprüft. Es wurden keine Code-Dateien geändert.

Geprüfter Ordner:

```text
/home/mob/Projekte/Anvil Organizer
```

Projektzustand:

- Python/PySide6-Projekt
- Hauptcode liegt in `anvil/`
- Game-Plugins liegen in `anvil/plugins/games/`
- Version laut `pyproject.toml`: `1.5.2`
- Branch: `main`
- `python -m compileall -q anvil` lief ohne Syntax-/Importfehler durch
- Kein `tests/`-Ordner gefunden

---

## Was gefunden wurde

### 1. Geänderte tracked Dateien

Aktuell sind 4 versionierte Dateien geändert, alle im `docs/`-Bereich:

```text
docs/anvil-agent1-review.md
docs/anvil-agent2-review.md
docs/anvil-agent3-review.md
docs/anvil-qa-report.md
```

Diese Dateien sehen nach QA-/Review-Berichten aus. Der Diff zeigt, dass alte Inhalte durch neue Review-Inhalte ersetzt wurden.

Empfehlung: Vor einem Commit prüfen, ob diese Änderungen gewollt sind oder ob die Dateien zurückgesetzt werden sollen.

---

### 2. Viele untracked Dateien und Ordner

Es gibt sehr viele untracked Dateien/Ordner, u. a.:

```text
REDmodLog.txt
anvil-organizer.flatpak
restart.sh
nexus_categories.json
squashfs-root/
Anvil-Organizer/
docs/workflow/*
viele docs/anvil-feature-*.md
```

Das wirkt wie eine Mischung aus:

- Build-Artefakten
- Laufzeitlogs
- Agent-/Workflow-Dateien
- Release-Dateien
- eventuell einer verschachtelten Projektkopie

Risiko:

- Git-Status wird unübersichtlich.
- Echte Code-Änderungen sind schwer sichtbar.
- Build-Artefakte könnten versehentlich committed werden.
- Die verschachtelte Kopie `Anvil-Organizer/` kann mit dem echten Projekt verwechselt werden.

---

### 3. Verdächtige/große Artefakte

Auffällig:

```text
squashfs-root/
anvil-organizer.flatpak
release/
dist/
build/
Anvil-Organizer/
```

Besonders `squashfs-root/` sieht nach entpacktem AppImage/Bundle aus.

`anvil-organizer.flatpak` ist sehr wahrscheinlich ein Build-Artefakt.

`Anvil-Organizer/` ist besonders vorsichtig zu behandeln, weil es wie eine verschachtelte Kopie oder ein nested Repo aussieht. Nicht blind löschen.

---

### 4. Debug-Prints im Code

In `anvil/mainwindow.py` wurden mehrere Debug-Ausgaben gefunden, z. B.:

```text
DEBUG _install_archives
DEBUG _open_profile_folder
DEBUG reinstall
```

Das ist kein bewiesener Bug, aber unsauber für Release-Code.

Empfehlung: Separat prüfen und klassifizieren:

| Typ | Empfehlung |
|---|---|
| echte Debug-Reste | entfernen |
| Support-/Deploy-Ausgaben | eventuell behalten |
| Fehlerausgaben | auf stderr oder internes Logging umstellen |
| temporäre Install-Debugs | entfernen |

---

### 5. `setStyleSheet()`-Treffer

Es gibt Treffer für `setStyleSheet()` im Code, u. a. in `anvil/mainwindow.py`.

Laut Projektregel soll in neuen Widgets kein `setStyleSheet()` verwendet werden.

Das bedeutet aber nicht automatisch, dass jeder alte Treffer ein Bug ist.

Empfehlung:

- Treffer sammeln
- prüfen, ob Altbestand oder neue UI-Stelle
- nur problematische Stellen ändern
- nicht pauschal alles entfernen

---

### 6. Viele TODOs in Game-Plugins

Gefunden wurden mehrere TODOs, z. B. in:

```text
anvil/plugins/games/game_fallout4.py
anvil/plugins/games/game_starfield.py
anvil/plugins/games/game_cyberpunk2077.py
anvil/plugins/games/game_baldursgate3.py
anvil/plugins/games/game_rdr2.py
```

Beispiele:

- `plugins.txt Parser/Writer`
- `.esp/.esm Scanner`
- Archive Handling
- Script Extender Integration
- Savegame Parsing
- RDR2 Nexus-ID noch `0`

Diese TODOs sind eher Roadmap-/Feature-Lücken, keine belegten akuten Bugs.

BG3-Code sollte gemäß Projektregel nicht angefasst werden.

---

### 7. Log-Zustand

Der gelesene Ausschnitt aus `debug.log` zeigte zuletzt keinen Python-Crash.

Auffällig war:

```text
[DEPLOY] Result: 628 symlinks, 266 copies, 0 errors
[DEPLOY-CHAIN] silent_deploy() DONE
```

Danach kam eine Qt/Portal-Warnung:

```text
Failed to register with host portal ... Connection already associated with an application ID
```

Das sieht eher nach Desktop-/Portal-Warnung aus, nicht nach App-Crash.

---

## Was ich ändern würde

Ich würde das Aufräumen in zwei getrennte Bereiche aufteilen:

1. Repo-/Dateisystem-Cleanup
2. Code-Smell-Cleanup

Nicht beides gleichzeitig ändern.

---

# Teil A — Repo/Ordner aufräumen

## A1. Inventar erstellen

Zuerst nur prüfen:

```bash
git status --short
git status --ignored --short
git ls-files
git ls-files --others --exclude-standard
du -sh ./*
```

Ziel:

- versionierte Dateien erkennen
- untracked Dateien erkennen
- ignorierte Dateien erkennen
- große Artefakte finden
- gefährliche Löschkandidaten erkennen

---

## A2. Verdächtige Ordner prüfen

Besonders prüfen:

```text
squashfs-root/
Anvil-Organizer/
release/
dist/
build/
docs/workflow/
```

Für `Anvil-Organizer/` vor jeder Aktion prüfen:

```bash
git -C Anvil-Organizer status --short
git -C Anvil-Organizer log --oneline -3
diff -qr anvil Anvil-Organizer/anvil | head -100
```

Erst danach entscheiden, ob es gelöscht, verschoben oder behalten wird.

---

## A3. `.gitignore` erweitern

Wahrscheinlich sinnvolle Einträge:

```gitignore
# Runtime logs
debug.log
REDmodLog.txt
*.log

# Build artifacts
build/
dist/
squashfs-root/
*.AppImage
*.appimage
*.flatpak

# Python cache
__pycache__/
*.py[cod]
.pytest_cache/
.mypy_cache/
```

Bei `docs/workflow/` vorher entscheiden, ob diese Dateien bewusst versioniert werden sollen.

Optional, falls Agent-/Workflow-Ausgaben nicht ins Repo sollen:

```gitignore
docs/workflow/
```

---

## A4. Artefakte nicht sofort löschen, sondern verschieben

Sicherer als direktes Löschen:

```bash
mkdir -p ../anvil-cleanup-quarantine
mv squashfs-root ../anvil-cleanup-quarantine/
mv anvil-organizer.flatpak ../anvil-cleanup-quarantine/
mv REDmodLog.txt ../anvil-cleanup-quarantine/
```

Vorteil:

- nichts ist sofort endgültig weg
- App kann danach getestet werden
- bei Problemen kann man Dateien zurückschieben

---

## A5. Geänderte Review-Docs entscheiden

Die 4 geänderten Dateien separat prüfen:

```bash
git diff -- docs/anvil-agent1-review.md
git diff -- docs/anvil-agent2-review.md
git diff -- docs/anvil-agent3-review.md
git diff -- docs/anvil-qa-report.md
```

Mögliche Entscheidungen:

1. Änderungen sind gewollt → behalten/committen
2. Änderungen sind versehentlich → zurücksetzen

Zurücksetzen, falls gewünscht:

```bash
git restore docs/anvil-agent1-review.md docs/anvil-agent2-review.md docs/anvil-agent3-review.md docs/anvil-qa-report.md
```

---

# Teil B — Code-Smells aufräumen

## B1. Debug-Prints inventarisieren

Erst nur auflisten:

```bash
grep -RIn "print(.*DEBUG\|DEBUG " anvil --include="*.py"
grep -RIn "print(" anvil --include="*.py"
```

Dann pro Treffer entscheiden:

| Kategorie | Aktion |
|---|---|
| temporärer Debug-Rest | entfernen |
| Deploy-/Support-Ausgabe | behalten oder sauber loggen |
| Fehlerausgabe | stderr oder Logger |
| dauerhaft nützliche Diagnose | Logging-Konzept verwenden |

Wahrscheinliche Kandidaten:

```text
anvil/mainwindow.py::_install_archives
anvil/mainwindow.py::_open_profile_folder
anvil/mainwindow.py::reinstall/debug output
```

---

## B2. `setStyleSheet()` prüfen

Treffer sammeln:

```bash
grep -RIn "setStyleSheet" anvil --include="*.py"
```

Dann prüfen:

- Ist es Altbestand?
- Ist es für dynamische Statusfarbe nötig?
- Kann es über QSS/Property ersetzt werden?
- Betrifft es neue Widgets?

Nicht pauschal alles entfernen.

---

## B3. TODOs separat behandeln

TODOs nicht im Cleanup lösen.

Stattdessen Liste erstellen:

```bash
grep -RIn "TODO\|FIXME\|HACK\|XXX" anvil --include="*.py"
```

Dann kategorisieren:

- echte Bugs
- geplante Features
- tote Kommentare
- WIP-Plugin-Hinweise

BG3-Code nicht anfassen.

---

## Empfohlene Reihenfolge

### Schritt 1

Nur Cleanup-Analyse finalisieren:

- untracked Dateien
- große Artefakte
- Logs
- verschachtelte Kopien
- Build-Ausgaben

### Schritt 2

`.gitignore` für klare Artefakte erweitern.

### Schritt 3

Artefakte in Quarantäne verschieben, nicht sofort löschen.

### Schritt 4

Git-Status kontrollieren:

```bash
git status --short
```

Ziel: Der Status soll wieder lesbar sein.

### Schritt 5

App prüfen:

```bash
python -m compileall -q anvil
./restart.sh
tail -n 120 debug.log
```

### Schritt 6

Erst danach Code-Smells angehen:

- Debug-Prints
- eventuell `setStyleSheet()`
- keine Feature-TODOs
- kein BG3-Code

---

## Was ich nicht sofort tun würde

Nicht direkt ausführen:

```bash
git clean -fd
```

Nicht blind löschen:

```text
Anvil-Organizer/
docs/workflow/
release/
dist/
build/
```

Nicht pauschal ändern:

- alle `print()` entfernen
- alle `setStyleSheet()` entfernen
- alle TODOs bearbeiten
- BG3-Code anfassen

---

## Fazit

Das größte aktuelle Problem wirkt nicht wie ein akuter Code-Crash, sondern wie ein unaufgeräumter Arbeitsbaum.

Priorität:

1. Git-Status und Arbeitsordner aufräumen
2. Build-Artefakte/Logs ignorieren oder verschieben
3. verschachtelten Ordner `Anvil-Organizer/` prüfen
4. geänderte Review-Docs bewusst entscheiden
5. danach Debug-Prints und kleinere Code-Smells separat angehen

Sicherste Strategie:

```text
Inventarisieren → .gitignore ergänzen → Artefakte in Quarantäne verschieben → testen → erst danach Code-Cleanup
```
