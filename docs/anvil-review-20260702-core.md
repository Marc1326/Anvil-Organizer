# Querschnitts-Review Kern-Module — Anvil Organizer
Datum: 2026-07-02
Prüfer: QA (Kern-Pfade + Feature-Anbindungen #14/#18/#21/#23/#24/#25)
Geprüft (nur gelesen, kein Code geändert):
mod_deployer.py, mod_list_io.py, instance_manager.py, mod_installer.py,
mod_list_model.py, mainwindow.py (nur strukturell) + Quervergleich mod_entry.py.

Vorab gelesen: ARCHITEKTUR.md. Prioritätsrichtung gegen mod_list_io ↔ mod_deployer ↔
mod_list_model ↔ mainwindow._write_current_modlist verifiziert.

---

## Funde (nach Schweregrad)

### 1. [MEDIUM] UnicodeDecodeError beim Lesen von modlist.txt nicht abgefangen
- Datei: anvil/core/mod_list_io.py:49-50, 268-269, 346-347
- Problem: `read_text(encoding="utf-8")` wird nur in `except OSError` gekapselt.
  `UnicodeDecodeError` ist ein `ValueError`, KEIN `OSError` → propagiert.
  Eine aus MO2/altem Bestand importierte modlist.txt mit Latin-1-Mod-Namen (Umlaute)
  lässt `read_modlist` / `read_global_modlist` / `migrate_modlist_order` abstürzen —
  im Zweifel schon beim App-Start / Instanz-Load.
- Fix: `except (OSError, UnicodeDecodeError)` oder `read_text(encoding="utf-8", errors="replace")`.

### 2. [MEDIUM] Einzel-Install / "Leeren Mod erstellen" schreiben in Legacy per-Profile-modlist statt global
- Datei: anvil/mainwindow.py:4038 (`_ctx`-Archiv-Install) und 4078 (`_ctx_create_empty_mod`)
- Problem: Beide rufen `add_mod_to_modlist(self._current_profile_path, name, False)` auf —
  das schreibt in `.profiles/Default/modlist.txt` (LEGACY, per-Profil), NICHT in die
  globale `.profiles/modlist.txt`. `scan_mods_directory` (mod_entry.py:224-272) liest bei
  vorhandener globaler modlist NUR die globale Reihenfolge; der neue Mod steht dort nicht →
  landet in Schritt 4 als "external" und wird mit **enabled=True** angehängt.
  Folgen:
  (a) Der übergebene `False` (Intent: deaktiviert) geht verloren — der Mod erscheint AKTIV.
      Inkonsistent zum Batch-Installer (mainwindow.py:2452-2481), der korrekt global
      schreibt und dadurch deaktiviert bleibt.
  (b) Eine tote Legacy-`.profiles/Default/modlist.txt` wird (wieder) erzeugt →
      verletzt Architektur-Regel 5 (nur globale API).
- Fix: In 4038/4078 die globale API nutzen (analog 2452-2481: `read_global_modlist` →
  `insert/append` → `write_global_modlist`, ohne active_mods → bleibt deaktiviert),
  oder nach `_reload_mod_list()` `_write_current_modlist()` mit korrektem enabled-State.

### 3. [MEDIUM] shutil.move ohne Ziel-Existenz-Prüfung → Struktur-Korruption bei Namenskollision
- Datei: anvil/core/mod_installer.py:188 (`install_from_archive`), 264 (`install_from_extracted`)
- Problem: `shutil.move(str(tmp), str(dest))` verschiebt bei bereits existierendem `dest`-Ordner
  den Temp-Ordner ALS UNTERORDNER in `dest` hinein (`.mods/ModName/anvil_install_XXXX/...`)
  statt zu ersetzen — die Mod-Ordnerstruktur ist damit kaputt (Symlinks würden ins Leere
  zeigen). `install_from_archive` verlässt sich laut Docstring auf "caller handled duplicates";
  `install_from_extracted` prüft gar nicht. Kein defensiver Check.
- Fix: Vor dem move `dest.exists()` prüfen und entweder eindeutigen Namen erzwingen
  (`_unique_name`) oder klar fehlschlagen. Alternativ `dest` vorher entfernen (nur wenn
  bewusst gewünscht).

### 4. [MEDIUM] Kein atomares Schreiben kritischer Dateien (Datenverlust-Risiko)
- Datei: mod_list_io.py:88, 237, 312, 379 (modlist/active_mods); mod_deployer.py:557
  (Manifest); instance_manager.py (QSettings sync ist ok, aber .current write_text).
- Problem: Alle nutzen direktes `write_text`/`write`. Wird der Prozess mitten im Schreiben
  beendet (Absturz, OOM-Kill, Stromausfall), bleibt eine abgeschnittene/leere modlist.txt,
  active_mods.json oder .deploy_manifest.json zurück → Reihenfolge/Aktiv-Status verloren
  bzw. Purge findet die Symlinks nicht mehr (Orphans im Game-Verzeichnis).
  Zusätzlich schreibt `_write_current_modlist` (mainwindow.py:1502-1507) globale modlist
  und active_mods als ZWEI getrennte Writes → Inkonsistenz-Fenster dazwischen.
- Fix: Atomar schreiben (temp-Datei + `os.replace`/`Path.replace`) für modlist.txt,
  active_mods.json und Manifest.

### 5. [LOW] Deploy ohne aktive Mods: success=True trotz gefülltem errors
- Datei: anvil/core/mod_deployer.py:194-196
- Problem: `if not enabled_mods: result.errors.append("No enabled mods found."); return result`
  gibt `result.success` (default True) mit nicht-leerer `errors`-Liste zurück. Aufrufer, die
  `result.errors` prüfen, zeigen im legitimen Leerfall eine Fehlermeldung; Aufrufer, die
  `result.success` prüfen, sehen Erfolg. Semantisch widersprüchlich.
- Fix: Entweder nichts in errors schreiben (Leerfall ist kein Fehler) oder success=False setzen.

### 6. [LOW] Variable-Shadowing von `c` (Spaltenindex) mit QColor
- Datei: anvil/models/mod_list_model.py:283 vs. 382
- Problem: In `data()` ist `c = index.column()`; im BackgroundRole-Zweig wird `c = QColor(r.color)`
  neu zugewiesen. Aktuell harmlos, da danach kein Spalten-`c` mehr genutzt wird — aber latenter
  Bug, sobald jemand nach dem Block wieder mit der Spalte arbeitet.
- Fix: Lokale Farbvariable umbenennen (z.B. `col`).

### 7. [LOW] _update_priorities nicht gegen leere Zeilenliste abgesichert
- Datei: anvil/models/mod_list_model.py:695-703
- Problem: Bei `len(self._rows)==0` erzeugt `self.index(len(self._rows)-1, ...)` = `index(-1,…)`
  einen ungültigen Index in `dataChanged.emit`. Andere Methoden (set_highlighted_rows) prüfen
  `if changed and self._rows` — hier fehlt der Guard. Über DnD real kaum erreichbar, aber inkonsistent.
- Fix: Frühzeitiges `if not self._rows: return`.

### 8. [LOW] Toter Code / Typ-Drift in instance_manager
- Datei: anvil/core/instance_manager.py:35 (`_CURRENT_FILE` definiert, nie benutzt — `_current_file()`
  baut den Pfad aus `_base.parent`); 287-322 (`save_instance` persistiert `auto_archive`/
  `detected_store` nicht; bool-Werte kommen aus `_read_ini` als String zurück und werden als
  String zurückgeschrieben → Typ-Drift bool→str über Round-Trips).
- Fix: Konstante entfernen oder nutzen; bei save_instance Typen konsistent halten bzw. fehlende
  Keys ergänzen falls Caller sie ändert.

### 9. [LOW] migrate_to_global_modlist bricht ab wenn Default-Profil keine modlist hat
- Datei: anvil/core/mod_list_io.py:480-491
- Problem: Quelle für globale Reihenfolge ist Default-Profil; existiert dort keine modlist.txt,
  wird `return False` obwohl ein ANDERES Profil eine hätte. Enger Edge-Case bei Altbeständen.
- Fix: Auf `profile_folders[0]` mit vorhandener modlist ausweichen.

---

## Positiv bestätigt (keine Funde)

- **Prioritätsrichtung konsistent:** mod_list_io (erste Zeile = höchste Prio) → deployer
  `enabled_mods.reverse()` verarbeitet höchste Prio zuletzt (last-wins) → model `priority=index`
  (oben=0=höchste) → mainwindow schreibt `self._current_mod_entries` in GUI-Reihenfolge.
  Keine Inversion, deckt sich mit ARCHITEKTUR.md Kap. 5/7.
- **Instanzwechsel:** `_teardown_current_instance` (mainwindow.py:1120-1146) räumt gründlich auf:
  silent_purge, collapsed_separators, conflict_win/lose/highlighted_rows, Filter/Suche,
  alle State-Variablen genullt. `switch_instance` mit 2-Phasen + Fallback-Reset bei Fehler.
- **Path-Traversal-Schutz** in ZIP-Extract und RAR/7z-Nachvalidierung vorhanden (mod_installer).
- Kein hardcoded Game-/Instanz-Pfad in den geprüften Kern-Modulen; alles aus instance_manager
  bzw. übergebenen Pfaden.

---

## mainwindow.py — Struktureinschätzung (nur grob)

7435 Zeilen, eine Klasse `MainWindow` mit 204 Methoden — klarer God-Object-Antipattern.
Sie mischt UI-Aufbau, Kontextmenü-Aktionen (`_ctx_*`), Mod-Persistenz (`_write_current_modlist`),
Instanz-/Profil-Lebenszyklus, Installations-Orchestrierung, Separator-/Deploy-Pfad-Logik und
BG3-Sonderwege in einer Datei. Auslagern lohnt sich für: (1) Mod-Persistenz + modlist/active_mods
in einen Controller (dann wäre Fund 2 zentral behebbar statt an drei Stellen dupliziert),
(2) Installations-/Downloads-Flow, (3) Kontextmenü-Aktionen, (4) Instanz-/Profil-Wechsel.
Die duplizierte "global vs. legacy modlist"-Verzweigung (2452 sauber, 4038/4078 nicht) ist ein
direktes Symptom der fehlenden Kapselung. Wartbarkeit: hoch riskant für Regressionen, aber der
State-Reset beim Wechsel ist überraschend diszipliniert gelöst. Empfehlung: schrittweise
Extraktion, keine Big-Bang-Umschreibung.

---

## Ergebnis
NEEDS FIXES — 0 KRITISCH, 4 MEDIUM, 5 LOW.
Wichtigster funktionaler Fund: #2 (neu installierte/erstellte Mods erscheinen entgegen dem
übergebenen `False` als aktiv + Legacy-modlist-Resurrection). Danach #1 (Absturz bei nicht-UTF8)
und #3/#4 (Datenintegrität).
