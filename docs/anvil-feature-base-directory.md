# Feature-Spec: Base Directory verschiebbar (#80)

**Status:** Geplant
**Datum:** 2026-06-28
**Betrifft:** Alle Spiele/Instanzen (global, nicht spielspezifisch)

---

## 1. Problem / Ziel

GitHub-Issue #80 (theFisher86): Der Basis-Ordner `~/.anvil-organizer` ist fest im
Home-Verzeichnis verdrahtet. Alle Instanzen, Profile, Downloads, Logs, User-Plugins
und die Credential-Datei liegen darunter. Der User möchte diese Daten auf ein anderes
Laufwerk legen (z.B. SSD/HDD-Trennung, Home auf kleiner Partition) — aktuell gibt es
keine Option dafür.

Im Settings-Dialog wird das Basisverzeichnis sogar angezeigt, aber als
`readonly` (siehe `settings_dialog.py:384`).

**Ziel:**
1. Beim ersten Start (Erst-Setup) frei wählbares Basisverzeichnis.
2. Nachträglich im Settings-Dialog änderbar — **mit Migration** der vorhandenen Daten.
3. Alle 13 hardcoded `~/.anvil-organizer`-Stellen lesen den Pfad zentral aus einer
   Konfiguration, nicht mehr aus `Path.home()`.

**Abgrenzung:** Dies ist **nicht** der "portable Instanz"-Pfad (mods/downloads pro
Instanz, bereits über `path_*_directory` editierbar). Es geht um das **globale
Basisverzeichnis**, das diese Instanzen enthält.

---

## 1a. Bau-Reihenfolge (Phasen) — das Rückgrat

Die zwei Issue-Wünsche („beim Setup setzen" + „nachträglich ändern") teilen sich
natürlich in Phasen mit klar steigendem Risiko. Nach jeder Phase ein testbarer Stand.

| # | Phase | Inhalt | Risiko | Erfüllt #80? | Testbar nach Phase? |
|---|-------|--------|--------|--------------|---------------------|
| **0** | Fundament | `base_dir.py` als Single Source of Truth; die **11** hardcoded `Path.home()`-Stellen darauf umstellen. Default bleibt `~/.anvil-organizer`. | gering, breit gestreut | — (Fundament) | Alles läuft wie bisher, nur zentral aufgelöst; bestehende User unverändert |
| **1** | First-Run-Dialog | Beim Erst-Setup Custom-Pfad wählbar; schreibt `General/base_dir` in die `.conf`. | gering | **„beim Setup setzen" ✓** | Frischer Start → Pfad-Dialog → Custom-Pfad wird genutzt + persistiert |
| **2** | Editierbar + Migration | `settings_dialog.py:384` von `readonly` auf editierbar; bei Änderung Bestätigung → Daten **kopieren** → verifizieren → `.conf` schreiben → Neustart. | **hoch** (Datenverschiebung, Symlinks) | **„nachträglich ändern" ✓** | Base-Dir umstellen → Daten am neuen Ort vollständig + nutzbar |

**Empfehlung — in 2 Etappen ausliefern:**
- **Etappe A = Phase 0 + 1** (niedriges Risiko, sofort nützlich): zentrale Auflösung +
  Custom-Pfad beim Setup. Erfüllt schon den halben Issue.
- **Etappe B = Phase 2** (der Knackpunkt): nachträgliches Verschieben mit Migration.
  Gründlich testen — hier liegt das gesamte Datenverlust-Risiko (§6).

So bekommt theFisher86 nach Etappe A bereits den wichtigsten Teil (Pfad frei wählen),
und das riskante Verschieben kann separat und sorgfältig folgen.

---

## 2. Ist-Zustand im Code (alle hardcoded `~/.anvil-organizer`-Stellen)

Es gibt **13 Stellen** in 9 Dateien. Eine zentrale Definition fehlt — jede Datei
baut den Pfad selbst aus `Path.home()`.

| # | Datei : Zeile | Verwendung | Kategorie |
|---|---------------|------------|-----------|
| 1 | `anvil/core/instance_manager.py:34` | `_DEFAULT_BASE = Path.home() / ".anvil-organizer" / "instances"` | **Instanzen (Kern)** |
| 2 | `anvil/core/instance_manager.py:35` | `_CURRENT_FILE = Path.home() / ".anvil-organizer" / ".current"` | **Aktive Instanz** |
| 3 | `anvil/main.py:28` | `(Path.home() / ".anvil-organizer").mkdir(...)` — pre-create vor Single-Instance | **Bootstrap** |
| 4 | `anvil/core/single_instance.py:14` | `SERVER_NAME = str(Path.home() / ".anvil-organizer" / "instance.sock")` | **IPC-Socket** |
| 5 | `anvil/core/activity_log.py:13` | `_LOG_DIR = Path.home() / ".anvil-organizer" / "logs"` | **Logs** |
| 6 | `anvil/mainwindow.py:3469` | `path = Path.home() / ".anvil-organizer" / "logs"` (Logs-Ordner öffnen) | **Logs** |
| 7 | `anvil/core/secure_storage.py:28` | `_config_dir() → Path.home() / ".anvil-organizer"` (credentials.bin) | **Credentials** |
| 8 | `anvil/plugins/plugin_loader.py:34` | `_USER_GAMES_DIR = Path.home() / ".anvil-organizer" / "plugins" / "games"` | **User-Plugins** |
| 9 | `anvil/plugins/base_game.py:546` | `Path.home() / ".anvil-organizer" / "plugins" / "games"` (Framework-JSON-Suche) | **User-Plugins** |
| 10 | `anvil/plugins/base_game.py:672` | `Path.home() / ".anvil-organizer" / "plugins" / "games" / f"game_{short}.json"` | **User-Plugins** |
| 11 | `anvil/widgets/plugin_creator_dialog.py:42` | `_USER_PLUGINS_DIR = Path.home() / ".anvil-organizer" / "plugins" / "games"` | **User-Plugins** |
| 12 | `anvil/widgets/settings_dialog.py:384` | Base-Dir-Zeile **readonly** angezeigt | **UI (zu ändern)** |
| 13 | `anvil/core/ba2_packer.py:145` | `Path.home() / ".local" / "share" / "anvil-organizer" / "tools"` | **NICHT betroffen** (XDG-data, eigener Pfad) |

### Wichtige Unterscheidungen (nicht verwechseln!)

- **`get_anvil_base()` (`resource_path.py`)** = App-**Installverzeichnis** (read-only,
  PyInstaller `_MEIPASS`). Hat **nichts** mit dem Daten-Basisverzeichnis zu tun und
  bleibt unverändert.
- **`~/.config/AnvilOrganizer/AnvilOrganizer.conf`** = bereits existierende Top-Level
  QSettings-INI-Datei (siehe `main.py:44`, `settings_dialog.py:1001`,
  `persistent_header.py:23`, `ui_helpers.py:14`, `secure_storage.py:149`). **Diese
  liegt bereits AUSSERHALB des Basisverzeichnisses** → ideale Henne-Ei-Lösung für die
  Speicherung des Base-Pfads.
- **`ba2_packer.py:145`** nutzt `~/.local/share/anvil-organizer` (XDG, globale Tools)
  — separater Pfad, **bleibt unverändert** (außerhalb Scope, kein User-Wunsch).

### Wie das Basisverzeichnis heute entsteht

- `InstanceManager(base_path=None)` → fällt auf `_DEFAULT_BASE` zurück
  (`instance_manager.py:43-45`). Wird **nur einmal** ohne Argument instanziiert:
  `mainwindow.py:156` → `InstanceManager()`.
- `instances_path()` liefert das Basisverzeichnis und wird an ~12 Stellen in
  `mainwindow.py` und den Dialogen verwendet (alle relativ, daher unkritisch sobald
  `InstanceManager` den richtigen Pfad kennt).
- Die `.current`-Datei und der `instance.sock` liegen eine Ebene **über** `instances/`,
  also direkt in `~/.anvil-organizer/`.

---

## 3. Lösung / Ansatz

### 3.1 Zentrale Base-Pfad-Auflösung (neues Modul)

Neues Modul **`anvil/core/base_dir.py`** mit einer einzigen Quelle der Wahrheit:

```python
def get_base_dir() -> Path:
    """Liefert das Anvil-Basisverzeichnis.

    Reihenfolge:
    1. Pfad aus ~/.config/AnvilOrganizer/AnvilOrganizer.conf [General/base_dir]
    2. Fallback: ~/.anvil-organizer  (Default, Abwärtskompatibilität)
    """
```

- Speicherort des Pfads: **`~/.config/AnvilOrganizer/AnvilOrganizer.conf`**, Key
  `General/base_dir`. Diese Datei liegt fest unter `$XDG_CONFIG_HOME` und damit
  **außerhalb** des Basisverzeichnisses → **kein Henne-Ei-Problem**.
- **Bewusst NICHT** in QSettings-Organisation-Pfad-Magie verlassen: wir nutzen exakt
  denselben absoluten `.conf`-Pfad, der bereits an 5+ Stellen verwendet wird (siehe
  oben). Das hält alles konsistent.
- Hilfsfunktionen: `get_instances_dir()` (= base/`instances`),
  `get_current_file()`, `get_logs_dir()`, `get_user_plugins_dir()`,
  `get_socket_path()`, `get_credentials_dir()`, `set_base_dir(path)`.
- **Trade-off Caching:** Der Pfad wird beim ersten Aufruf gecacht (Modul-Level), damit
  nicht jede Stelle die INI neu liest. Nach Migration im selben Prozess muss
  `set_base_dir()` den Cache invalidieren **und** ein Neustart empfohlen werden
  (Socket/Logs/InstanceManager sind bereits im alten Pfad initialisiert).

Alle 12 betroffenen Stellen (Tabelle #1-12, ohne #13) lesen künftig aus `base_dir.py`
statt aus `Path.home()`.

### 3.2 Erst-Setup (First-Run)

Aktuell gibt es **keinen** dedizierten First-Run-Wizard für das Basisverzeichnis. Zwei
Varianten:

- **Variante A (empfohlen, minimal-invasiv):** First-Run wird erkannt, wenn
  `General/base_dir` in der `.conf` noch nicht gesetzt **und** `~/.anvil-organizer`
  noch nicht existiert. Dann **vor** `MainWindow()` ein kleiner Dialog
  (`BaseDirSetupDialog`): "Wo sollen Anvil-Daten gespeichert werden?" mit
  vorausgefülltem Default `~/.anvil-organizer` und Browse-Button. Bestätigung schreibt
  `base_dir` in die `.conf`. Bei "Standard verwenden" → Default-Pfad, kein weiterer
  Eingriff.
- **Variante B:** Integration in den bestehenden `instance_wizard.py`. Verworfen, weil
  der Base-Dir global ist und der Instanz-Wizard pro Instanz läuft — falsche Ebene.

**Henne-Ei beim Bootstrap (`main.py:28`):** Das `mkdir` muss **nach** dem
First-Run-Dialog passieren bzw. den aufgelösten Pfad nutzen. Reihenfolge in `main.py`:
`get_base_dir()` (liest .conf) → ggf. First-Run-Dialog → `mkdir(base)` → Single-Instance.

### 3.3 Nachträgliches Ändern + Migration (Settings-Dialog)

Im **Pfade-Tab** des Settings-Dialogs (`settings_dialog.py:383-391`):

- Die Base-Dir-Zeile (Zeile 384) wird von `readonly=True` auf **editierbar mit
  Browse-Button** umgestellt — aber **getrennt** von den Instanz-Pfaden behandelt
  (eigene GroupBox/Hinweis, da global statt instanzspezifisch).
- Beim Übernehmen mit geändertem Base-Dir: **Bestätigungsdialog** mit Migrations-Warnung
  → bei "Ja" Migration durchführen (siehe Abschnitt 6), `set_base_dir()`, dann
  **Neustart-Dialog** (analog Sprachwechsel `settings_dialog.py:1127-1146`).
- Migration läuft in einer eigenen Funktion in `base_dir.py` bzw. einem
  `migrate_base_dir(old, new, progress_cb)` — mit Fortschritts-Dialog für große
  Download-Ordner.

---

## 4. Betroffene Dateien (Tabelle)

| Datei | Art der Änderung |
|-------|------------------|
| `anvil/core/base_dir.py` | **NEU** — zentrale Pfadauflösung + `migrate_base_dir()` |
| `anvil/core/instance_manager.py` | `_DEFAULT_BASE`/`_CURRENT_FILE` aus `base_dir.py` |
| `anvil/main.py` | Bootstrap-`mkdir` + First-Run-Dialog + `get_base_dir()` |
| `anvil/core/single_instance.py` | `SERVER_NAME` aus `base_dir.get_socket_path()` |
| `anvil/core/activity_log.py` | `_LOG_DIR` aus `base_dir.get_logs_dir()` |
| `anvil/core/secure_storage.py` | `_config_dir()` aus `base_dir.get_credentials_dir()` |
| `anvil/plugins/plugin_loader.py` | `_USER_GAMES_DIR` aus `base_dir.get_user_plugins_dir()` |
| `anvil/plugins/base_game.py` | 2 Stellen (Z. 546, 672) aus `base_dir` |
| `anvil/widgets/plugin_creator_dialog.py` | `_USER_PLUGINS_DIR` aus `base_dir` |
| `anvil/mainwindow.py:3469` | Logs-Ordner-Öffnen aus `base_dir.get_logs_dir()` |
| `anvil/widgets/settings_dialog.py` | Base-Dir-Zeile editierbar + Migration + Neustart |
| `anvil/widgets/base_dir_setup_dialog.py` | **NEU** (optional) — First-Run-Dialog |
| `anvil/locales/*.json` (7 Dateien) | neue tr-Keys |

**Nicht ändern:** `ba2_packer.py` (XDG-data Tools), `resource_path.py`
(App-Installdir), alle `instances_path()`-Aufrufer (lesen relativ, ziehen automatisch nach).

---

## 5. Umsetzungsschritte (nummeriert)

1. **`anvil/core/base_dir.py` anlegen** — `get_base_dir()`, `set_base_dir()`,
   abgeleitete Getter, Modul-Cache, `migrate_base_dir(old, new, progress_cb)`.
2. **Module-Level-Konstanten ersetzen** in den 9 Kern-Dateien (Tabelle Abschnitt 4)
   durch Funktionsaufrufe. **Achtung:** Modul-Level-Konstanten wie `_LOG_DIR`,
   `SERVER_NAME`, `_DEFAULT_BASE` werden beim Import **einmal** ausgewertet — entweder
   in Funktionen umwandeln (`_log_dir()`) oder beim Import `get_base_dir()` aufrufen
   (akzeptabel, da Cache). Import-Reihenfolge prüfen: `base_dir.py` darf **keine**
   schweren Anvil-Module importieren (nur `pathlib`, `PySide6.QtCore.QSettings`),
   um Zirkularimporte zu vermeiden.
3. **`main.py` Bootstrap umstellen**: `get_base_dir()` zuerst, dann First-Run-Dialog
   (falls nötig), dann `mkdir(base)`, dann Single-Instance.
4. **First-Run-Dialog** (`base_dir_setup_dialog.py`) bauen — schlicht: Label, LineEdit,
   Browse-Button, "Standard"/OK. Schreibt `General/base_dir`.
5. **Settings-Dialog Pfade-Tab**: Base-Dir-Zeile editierbar machen (eigene Sektion,
   getrennt von Instanz-Pfaden), Browse-Button, Migrations-/Neustart-Logik in `accept()`.
6. **Migrationsfunktion** mit Fortschrittsdialog (`QProgressDialog`) und allen
   Edge-Cases aus Abschnitt 6.
7. **i18n**: neue Keys in allen 7 Locales (Abschnitt 7).
8. **Test**: `./restart.sh`; Erst-Setup mit Custom-Pfad; Migration auf zweites
   Laufwerk; Default beibehalten (Abwärtskompatibilität, bestehende User).

---

## 6. Migration & Edge-Cases (KRITISCH)

Das Verschieben ist der eigentliche Knackpunkt — der Default zu ändern reicht nicht,
die **vorhandenen Daten müssen mit**.

### 6.1 Was muss migriert werden

Der **komplette** Inhalt des alten Basisverzeichnisses:
`instances/` (inkl. `.mods`, `.downloads`, `.profiles`, `.overwrite` pro Instanz),
`.current`, `logs/`, `plugins/games/`, `credentials.bin`. Der `instance.sock` wird
**nicht** mitkopiert (Laufzeit-Artefakt, wird neu erstellt).

### 6.2 Reihenfolge der Migration

1. **Vorbedingungen prüfen** (siehe 6.3) — bei Fehler abbrechen, **nichts** anfassen.
2. Daten **kopieren** (`shutil.copytree` mit `dirs_exist_ok=False`), **nicht** moven —
   so bleibt bei Abbruch der Originalzustand erhalten.
3. **Verifizieren** (Anzahl/Größe grob, oder zumindest dass alle `.anvil.ini` vorhanden).
4. `set_base_dir(new)` in die `.conf` schreiben.
5. **Erst nach erfolgreicher Verifikation** das alte Verzeichnis löschen — **oder**
   (sicherer, empfohlen) stehen lassen und dem User in der Erfolgsmeldung den alten
   Pfad nennen ("kann manuell gelöscht werden"). Automatisches Löschen nur nach
   expliziter Rückfrage.
6. **Neustart erzwingen** (Socket, Logs, InstanceManager sind im alten Prozess noch auf
   alten Pfad gebunden). Analog Sprachwechsel-Neustart (`settings_dialog.py:1127`).

### 6.3 Edge-Cases

| Fall | Verhalten |
|------|-----------|
| **Ziel == Quelle** | No-op, keine Migration. |
| **Ziel liegt INNERHALB der Quelle** (z.B. `base/sub`) | Verbieten — `copytree` würde rekursiv scheitern. Klare Fehlermeldung. |
| **Ziel existiert + nicht leer** | Warnen; nur erlauben wenn leer **oder** explizite Zustimmung zum Mergen (Risiko `dirs_exist_ok`). Default: ablehnen, neuen leeren Ordner verlangen. |
| **Kein Schreibrecht am Ziel** | Vorab `os.access(parent, W_OK)` prüfen → Fehlermeldung, Abbruch ohne Änderung. |
| **Kein Platz** (`shutil.disk_usage`) | Größe der Quelle vs. freier Platz am Ziel prüfen → Abbruch wenn knapp. |
| **Laufendes Deployment / aktive Operation** | Migration **blockieren**, solange Deploy/Download/Install läuft. Über bestehende Locks/Flags in `mainwindow` prüfen; sonst Hinweis "Bitte alle Vorgänge abschließen". |
| **Anderes Laufwerk (cross-device)** | `copytree` funktioniert; Symlinks in `.mods` (Anvil nutzt Symlinks beim Deploy!) prüfen — `copytree(symlinks=True)` damit Symlinks **als Symlinks** kopiert werden, **nicht** dereferenziert. ABER: relative vs. absolute Symlink-Ziele beachten — Deploy-Symlinks zeigen ggf. auf instanz-interne Pfade, die nach Verschiebung umziehen → nach Migration **Re-Deploy empfehlen** oder Symlinks neu setzen. Sicherste Variante: User-Hinweis "nach Verschiebung neu deployen". |
| **Pfad mit `~`/Tilde** | Über `Path.expanduser()` auflösen, absolut speichern. |
| **Quelle existiert noch nicht** (frischer First-Run) | Keine Migration nötig — nur `mkdir(new)`. |
| **Abbruch mitten in copytree** | Da kopiert (nicht gemoved): Original intakt, halb-kopiertes Ziel aufräumen/markieren, `.conf` **nicht** umschreiben. |
| **Custom Instanz-Pfade außerhalb base** | Instanzen mit absoluten `path_mods_directory` (nicht `%INSTANCE_DIR%`) liegen ggf. außerhalb des Base-Dir → werden **nicht** migriert, bleiben gültig. Im Hinweis erwähnen. |

### 6.4 Persistenz-Detail

`General/base_dir` wird **immer absolut** (`str(Path(...).expanduser().resolve())`)
gespeichert. Leerer/ungültiger Wert in der `.conf` → Fallback auf Default
`~/.anvil-organizer` (robust gegen manuelle Fehl-Edits).

---

## 7. i18n (tr-Keys, 7 Locales: de, en, es, fr, it, pt, ru)

Neue Keys (Beispiele DE; in allen 7 Dateien identische Keys):

| Key | DE (Beispiel) |
|-----|---------------|
| `base_dir.setup_title` | "Basisverzeichnis wählen" |
| `base_dir.setup_intro` | "Wo sollen die Anvil-Daten (Instanzen, Downloads, Profile) gespeichert werden?" |
| `base_dir.use_default` | "Standard verwenden (~/.anvil-organizer)" |
| `base_dir.browse` | "Durchsuchen…" |
| `base_dir.change_confirm_title` | "Basisverzeichnis verschieben?" |
| `base_dir.change_confirm_text` | "Alle Daten werden nach „%1" kopiert. Anvil startet danach neu. Fortfahren?" |
| `base_dir.migrating` | "Daten werden verschoben…" |
| `base_dir.migrate_done` | "Verschoben. Alter Ordner „%1" kann manuell gelöscht werden." |
| `base_dir.err_no_write` | "Keine Schreibrechte im Zielverzeichnis." |
| `base_dir.err_target_not_empty` | "Zielverzeichnis ist nicht leer. Bitte einen leeren Ordner wählen." |
| `base_dir.err_inside_source` | "Das Ziel darf nicht innerhalb des aktuellen Basisverzeichnisses liegen." |
| `base_dir.err_no_space` | "Nicht genug freier Speicherplatz im Zielverzeichnis." |
| `base_dir.err_busy` | "Migration nicht möglich, während ein Vorgang läuft. Bitte zuerst abschließen." |
| `base_dir.redeploy_hint` | "Tipp: Mods nach dem Verschieben neu bereitstellen (Deploy)." |

Bestehende Keys ggf. anpassen: `label.base_dir_hint` (heute %BASE_DIR%-Bezug),
`settings.path_base_dir`. **Pflicht:** Alle Keys in **allen 7** Locale-Dateien
(de, en, es, fr, it, pt, ru) — sonst Lücken.

---

## 8. Akzeptanzkriterien (Checkliste)

- [ ] Neues Modul `base_dir.py` ist einzige Quelle des Base-Pfads; **0** verbleibende
      `Path.home() / ".anvil-organizer"` in den 12 betroffenen Stellen (außer `ba2_packer`).
- [ ] Bestehende User (Default-Pfad, keine `.conf`-Eintragung) funktionieren **unverändert**
      weiter (Abwärtskompatibilität, Fallback greift).
- [ ] First-Run zeigt Setup-Dialog; gewählter Custom-Pfad wird verwendet und persistiert.
- [ ] "Standard verwenden" legt `~/.anvil-organizer` an wie bisher.
- [ ] Settings-Dialog: Base-Dir-Zeile ist editierbar (nicht mehr readonly).
- [ ] Base-Dir-Änderung → Bestätigung → Migration → Neustart-Aufforderung.
- [ ] Nach Migration: Instanzen, Profile, Downloads, Logs, User-Plugins, Credentials
      sind am neuen Ort vollständig und nutzbar.
- [ ] Edge-Cases abgedeckt: Ziel nicht leer, kein Schreibrecht, zu wenig Platz, Ziel
      innerhalb Quelle, laufender Vorgang, Ziel==Quelle (alle → klare Meldung, kein
      Datenverlust).
- [ ] Migration **kopiert** (Original bleibt bis Erfolg bestätigt); kein automatisches
      Löschen ohne Rückfrage.
- [ ] Symlinks im `.mods`-Ordner werden korrekt behandelt (copytree symlinks=True) bzw.
      Re-Deploy-Hinweis angezeigt.
- [ ] Alle neuen tr-Keys in **allen 7** Locale-Dateien vorhanden.
- [ ] `python -m py_compile` sauber; `./restart.sh` startet ohne Traceback.
- [ ] Keine MO2-/AI-typischen Spuren; Kommentare sparsam; Commit-Message natürlich.

---

## 9. Aufwand / Risiko

**Aufwand:** mittel-hoch.

- Mechanische Umstellung der 12 Pfad-Stellen: gering, aber breit gestreut (9 Dateien) →
  sorgfältig, jeder Modul-Level-Konstante einzeln nachgehen (Import-Zeitpunkt!).
- `base_dir.py` + Getter: gering.
- First-Run-Dialog: gering.
- **Migration + Edge-Cases: der Löwenanteil** — hier liegt das gesamte Risiko.

**Risiken:**

1. **Datenverlust bei Migration** — höchstes Risiko. Mitigation: kopieren statt moven,
   verifizieren, Original nie automatisch löschen.
2. **Symlinks der deployten Mods** — Anvil deployt per Symlink; nach Verschiebung können
   absolute Ziele brechen. Mitigation: `symlinks=True` + Re-Deploy-Empfehlung; ggf.
   Hinweis "vor Verschiebung undeployen".
3. **Import-Zeitpunkt der Modul-Konstanten** — `_LOG_DIR`/`SERVER_NAME` werden beim
   Import einmalig gesetzt; nach Laufzeit-Änderung greift nur ein Neustart. Mitigation:
   Neustart erzwingen (wie Sprachwechsel).
4. **Zirkularimport** in `base_dir.py` — nur Stdlib + QtCore importieren.
5. **Cross-Device + großer Download-Ordner** — lange Kopierzeit; Mitigation:
   `QProgressDialog`, Vorgang nicht im UI-Thread blockieren (oder zumindest
   `processEvents`/Worker).

**Empfehlung:** In 2 Etappen umsetzen — (A) zentrale Pfadauflösung + First-Run
(niedriges Risiko, sofort nützlich), (B) Migration im Settings-Dialog (höheres Risiko,
gründlich testen). Etappe A allein erfüllt Issue #80 schon teilweise (Custom-Pfad beim
Setup); B liefert das nachträgliche Verschieben.
