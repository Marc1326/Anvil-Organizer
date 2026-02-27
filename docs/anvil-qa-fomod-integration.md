# QA Report -- FOMOD MainWindow-Integration
Datum: 2026-02-26

Gegenstand: Integration von FOMOD-Installer in `anvil/mainwindow.py` und `anvil/dialogs/__init__.py`
Begleitend geprueft: `anvil/core/fomod_parser.py`, `anvil/dialogs/fomod_dialog.py`, alle 6 Locale-Dateien
Diff-Umfang: 8 Dateien, +139/-1 Zeilen

---

## Findings

### [KRITISCH] parse_fomod_info() wird auf bereits geloeschtem Verzeichnis aufgerufen

- **Datei:** `/home/mob/Projekte/Anvil Organizer/anvil/mainwindow.py:1255,1260`
- **Problem:** In Zeile 1255 wird `shutil.rmtree(temp_dir, ignore_errors=True)` aufgerufen. Das loescht das gesamte extrahierte Archiv inklusive des `fomod/`-Unterverzeichnisses. Direkt danach in Zeile 1260 wird `parse_fomod_info(fomod_xml.parent)` aufgerufen. `fomod_xml.parent` zeigt auf das `fomod/`-Verzeichnis innerhalb des soeben geloeschten `temp_dir`.

  ```python
  # Zeile 1254-1260:
  new_temp = assemble_fomod_files(temp_dir, all_files)
  shutil.rmtree(temp_dir, ignore_errors=True)   # <-- loescht temp_dir + fomod/
  if new_temp is None:
      continue
  temp_dir = new_temp
  # Use FOMOD name for suggestion
  info = parse_fomod_info(fomod_xml.parent)      # <-- fomod_xml.parent existiert nicht mehr!
  ```

  `parse_fomod_info()` hat zwar ein `try/except Exception: pass`, was verhindert dass die App abstuerzt, aber die Funktion wird IMMER ein leeres Dict zurueckgeben, weil `fomod_dir.iterdir()` auf einem geloeschten Verzeichnis fehlschlaegt. Ergebnis: FOMOD-Name aus info.xml wird NIE verwendet.

  **Gleiches Problem** tritt in Zeile 1267-1272 auf (Branch fuer "no steps but required files").

- **Fix:** `parse_fomod_info()` VOR `shutil.rmtree()` aufrufen und das Ergebnis speichern. Alternativ: info.xml vor dem rmtree auslesen und das Ergebnis cachen:

  ```python
  info = parse_fomod_info(fomod_xml.parent)  # VORHER lesen
  new_temp = assemble_fomod_files(temp_dir, all_files)
  shutil.rmtree(temp_dir, ignore_errors=True)
  if new_temp is None:
      continue
  temp_dir = new_temp
  if "name" in info:
      fomod_name_override = info["name"]
  elif config.module_name and config.module_name != "FOMOD Package":
      fomod_name_override = config.module_name
  ```

- **Schweregrad:** KRITISCH — Die FOMOD-Name-Erkennung ist in der Praxis komplett kaputt. Mods werden immer mit dem Archiv-Namensvorschlag statt dem FOMOD-Namen installiert.


### [HOCH] Path Traversal in assemble_fomod_files -- keine Pruefung auf ".." in destination

- **Datei:** `/home/mob/Projekte/Anvil Organizer/anvil/core/fomod_parser.py:451,463`
- **Problem:** `f.destination` wird direkt als Pfadkomponente verwendet (`dest / f.destination`). Die `_norm_path()`-Funktion in Zeile 87 entfernt nur fuehrende/abschliessende Slashes, validiert aber KEINE `..`-Komponenten. Ein boesartiges FOMOD-XML mit `destination="../../.config/autostart/malware"` wuerde die Datei ausserhalb des Temp-Verzeichnisses platzieren.

  Hinweis: Dieser Bug wurde bereits im vorherigen QA-Report (anvil-qa-report.md) als KRITISCH gemeldet. Er betrifft aber auch die Integration, da die mainwindow.py den Rueckgabewert von `assemble_fomod_files()` direkt als `temp_dir` verwendet.

- **Fix:** Path-Traversal-Pruefung in `assemble_fomod_files()`:
  ```python
  target = dest / f.destination
  if not target.resolve().is_relative_to(dest.resolve()):
      print(f"fomod: SECURITY -- skipping path traversal: {f.destination!r}")
      continue
  ```


### [HOCH] setStyleSheet() in fomod_dialog.py -- ueberschreibt QSS-Theme

- **Datei:** `/home/mob/Projekte/Anvil Organizer/anvil/dialogs/fomod_dialog.py:111,120,144,152`
- **Problem:** Laut Projekt-Regeln (CLAUDE.md): "NIEMALS `setStyleSheet()` in neuen Widgets -- QSS-Theme wird vererbt". Der FomodDialog verwendet einen 40-zeiligen `_STYLE`-Block (Zeile 36-75) und setzt ihn via `self.setStyleSheet(_STYLE)`. Zusaetzlich werden einzelne Widgets mit inline-Styles versehen:
  - Zeile 120: `_step_label.setStyleSheet("font-size: 13px; font-weight: bold; color: #E0E0E0;")`
  - Zeile 144: `_preview_image.setStyleSheet("background: #242424; border: ...")`
  - Zeile 152: `_preview_desc.setStyleSheet("padding: 8px; color: #AAAAAA;")`

  Das hardcoded Dark-Theme wird nicht zum restlichen App-Theme passen wenn der User ein anderes Theme waehlt. MO2 verwendet fuer den FOMOD-Dialog das gleiche Theme wie die Hauptanwendung.

- **Fix:** Alle `setStyleSheet()`-Aufrufe entfernen. Widget-Styling ueber die QSS-Theme-Dateien in `anvil/styles/` steuern. Falls FOMOD-spezifische Styles noetig sind, eigene CSS-Klassen via `setObjectName()` oder `setProperty()` verwenden.


### [MITTEL] Verschachtelte Dependencies verlieren inneren Operator

- **Datei:** `/home/mob/Projekte/Anvil Organizer/anvil/core/fomod_parser.py:132-134`
- **Problem:** Bei verschachtelten `<dependencies>`-Elementen wird rekursiv `_parse_flag_conditions()` aufgerufen, aber der innere Operator wird mit `_` verworfen und die Flags werden flach in die aeussere Liste eingefuegt:

  ```python
  elif tag == "dependencies":
      sub_flags, _ = _parse_flag_conditions(child)  # innerer Operator geht verloren
      flags.extend(sub_flags)
  ```

  Bei FOMOD-XML wie:
  ```xml
  <dependencies operator="And">
      <flagDependency flag="A" value="On"/>
      <dependencies operator="Or">
          <flagDependency flag="B" value="On"/>
          <flagDependency flag="C" value="On"/>
      </dependencies>
  </dependencies>
  ```
  Wuerde dies als `A AND B AND C` ausgewertet statt korrekt als `A AND (B OR C)`.

  In der Praxis verwenden die meisten FOMODs einfache Bedingungen, aber komplexe FOMODs (z.B. CBBE, ENB-Presets) koennten betroffen sein.

- **Fix:** `_parse_flag_conditions()` muesste eine Baumstruktur statt einer flachen Liste zurueckgeben, und `evaluate_conditions()` muesste rekursiv auswerten.


### [MITTEL] Redundanter Import -- FomodDialog wird direkt und via __init__.py importiert

- **Datei:** `/home/mob/Projekte/Anvil Organizer/anvil/mainwindow.py:53`
- **Problem:** `FomodDialog` wird in Zeile 53 direkt importiert:
  ```python
  from anvil.dialogs.fomod_dialog import FomodDialog
  ```
  Gleichzeitig wird es in `anvil/dialogs/__init__.py` (Zeile 6) re-exportiert. Das ist kein Fehler, aber inkonsistent mit den anderen Dialogen. In Zeile 55 (nicht im Diff sichtbar, aber im bestehenden Code) werden `QuickInstallDialog`, `QueryOverwriteDialog` und `OverwriteAction` aus `anvil.dialogs` importiert -- nicht direkt aus ihren Modulen.

  Der direkte Import in mainwindow.py macht den Re-Export in `__init__.py` fuer FomodDialog faktisch ueberfluessig (oder umgekehrt).

- **Fix:** Entweder:
  - (a) Import ueber `from anvil.dialogs import FomodDialog` (konsistent mit anderen Dialogen), ODER
  - (b) Den Re-Export in `__init__.py` entfernen (wenn sonst niemand `from anvil.dialogs import FomodDialog` braucht)

  Option (a) ist vorzuziehen fuer Konsistenz.


### [MITTEL] Keine Fehlermeldung bei fehlgeschlagenem FOMOD-Parsing

- **Datei:** `/home/mob/Projekte/Anvil Organizer/anvil/mainwindow.py:1244`
- **Problem:** Wenn `parse_fomod()` in Zeile 1244 `None` zurueckgibt (z.B. wegen XML-Fehler oder Encoding-Problem), faellt der Code still durch zum normalen Install-Pfad (Zeile 1276). Der Benutzer erfaehrt nicht, dass ein FOMOD erkannt aber nicht geparst werden konnte. Das Archiv wird dann als "normaler" Mod installiert, was bedeutet dass alle FOMOD-Dateien (inkl. der fomod/-Struktur selbst) im Mods-Ordner landen.

  MO2 zeigt in diesem Fall eine Warnung an ("Failed to parse FOMOD config").

- **Fix:** Warnung anzeigen wenn FOMOD erkannt aber nicht geparst wurde:
  ```python
  config = parse_fomod(fomod_xml)
  if config is None:
      QMessageBox.warning(
          self, tr("fomod.title"),
          tr("fomod.parse_error"),  # neuer tr()-Key noetig
      )
      # Fallthrough zum normalen Install
  ```


### [MITTEL] fomod_xml referenziert nach rmtree ein nicht mehr existierendes Path-Objekt

- **Datei:** `/home/mob/Projekte/Anvil Organizer/anvil/mainwindow.py:1260,1272`
- **Problem:** Dies ist eine Folge des KRITISCH-Bugs oben. Das `fomod_xml`-Path-Objekt (zurueckgegeben von `detect_fomod()`) zeigt nach `shutil.rmtree(temp_dir)` auf eine nicht mehr existierende Datei. `fomod_xml.parent` ist ein reiner Path-String-Verweis und wirft keinen Fehler, aber jede Dateisystem-Operation darauf schlaegt fehl.

  Im Fall von Zeile 1260 ist das Ergebnis: `parse_fomod_info()` gibt leeres Dict zurueck, `fomod_name_override` bleibt None, und der `config.module_name`-Fallback wird korrekt verwendet -- aber nur wenn `module_name` gesetzt UND nicht "FOMOD Package" ist.

  Im Fall von Zeile 1272 gibt es keinen module_name-Fallback, also bleibt `fomod_name_override` IMMER None fuer diesen Branch.

- **Fix:** Siehe KRITISCH-Finding oben.


### [NIEDRIG] Debug-print-Statements in Produktionscode

- **Datei:** `/home/mob/Projekte/Anvil Organizer/anvil/mainwindow.py:1243`
- **Problem:** `print(f"DEBUG _install_archives: FOMOD detected: {fomod_xml}", flush=True)` ist ein Debug-Statement. Das ist konsistent mit den anderen Debug-Prints in der Methode (Zeilen 1211, 1216, 1224, 1226, 1229), scheint also ein bewusstes Pattern zu sein. Trotzdem sollten diese irgendwann durch `debug.log()` ersetzt oder entfernt werden.

- **Fix:** Ersetzen durch `debug.log(f"FOMOD detected: {fomod_xml}")` oder entfernen vor Release.


### [NIEDRIG] collect_fomod_files Duplikaterkennung basiert auf Source statt Destination bei Ordnern

- **Datei:** `/home/mob/Projekte/Anvil Organizer/anvil/core/fomod_parser.py:414`
- **Problem:** Fuer Ordner wird `DIR:{f.source.lower()}` als Schluessel verwendet, statt `f.destination`. Wenn zwei verschiedene Ordner als Source denselben Namen haben aber unterschiedliche Destinations, wird nur einer installiert:
  ```python
  f1 = FomodFile(source='textures', destination='Data/textures', is_folder=True)
  f2 = FomodFile(source='textures', destination='Other/textures', is_folder=True)
  # f2 ueberschreibt f1 obwohl sie unterschiedliche Ziele haben
  ```

  In der Praxis ist dies selten, da die meisten FOMODs eindeutige Source-Namen verwenden.

- **Fix:** Schluessel auf `DIR:{f.destination.lower() or f.source.lower()}` aendern.


---

## Positiv-Befunde

1. **Import-Kette:** `FomodDialog` ist korrekt in `anvil/dialogs/__init__.py` exportiert (Zeile 6, 13) und wird in `mainwindow.py` korrekt importiert (Zeile 53). Alle fuenf Parser-Funktionen (`detect_fomod`, `parse_fomod`, `parse_fomod_info`, `collect_fomod_files`, `assemble_fomod_files`) werden korrekt importiert.

2. **Signal/Slot-Verbindungen:** Alle drei Button-Connects in `fomod_dialog.py` verwenden korrekt das `lambda checked=False:`-Pattern (Zeilen 167, 174). Der Cancel-Button verbindet direkt auf `self.reject` (Zeile 178) -- das ist korrekt, da `reject()` keinen Parameter erwartet und QPushButton.clicked(bool) ignoriert wird.

3. **Widget-Lifecycle:** `old.deleteLater()` wird korrekt fuer das alte Scroll-Widget aufgerufen (Zeile 235-237 in fomod_dialog.py). Der FomodDialog hat `parent=self` (mainwindow), was korrekte GC sicherstellt.

4. **Locale-Vollstaendigkeit:** Alle 12 FOMOD-tr()-Keys (title, step_of, back, next, install, cancel, none_option, required, recommended, not_usable, no_description, no_image) sind in allen 6 Sprachen (de, en, es, fr, it, pt) vorhanden und sinnvoll uebersetzt.

5. **Architektur-Integration:** Der FOMOD-Check wird korrekt zwischen Framework-Check (Schritt 2) und normalem Install (Schritt 4) eingefuegt. Framework-Mods haben Vorrang, was sinnvoll ist. Der bestehende Install-Flow wird nicht beeintraechtigt -- wenn kein FOMOD erkannt wird, laeuft der Code exakt wie vorher.

6. **Graceful Fallback bei FOMOD ohne Steps:** Der `elif`-Branch (Zeile 1265) behandelt FOMODs die nur required_files haben (keine install_steps). Diese werden direkt installiert ohne Dialog -- korrekt.

7. **Cancel-Handling:** Bei Dialog-Abbruch (`dlg.exec() != Accepted`) wird `temp_dir` korrekt aufgeraeumt und per `continue` zum naechsten Archiv gewechselt (Zeile 1248-1250).

8. **Name-Override-Logik:** Die Prioritaet ist sinnvoll: info.xml-Name > config.module_name > Archiv-Name. Der Override wird korrekt in die Varianten-Liste eingefuegt (Zeile 1280-1281).


---

## Zusammenfassung

| Schweregrad | Anzahl |
|-------------|--------|
| KRITISCH    | 1      |
| HOCH        | 2      |
| MITTEL      | 3      |
| NIEDRIG     | 2      |

Der kritischste Bug ist, dass `parse_fomod_info()` auf einem bereits geloeschten Verzeichnis aufgerufen wird. Das bedeutet, dass die FOMOD-Namens-Erkennung aus info.xml in der Praxis nie funktioniert. Dieser Bug tritt in beiden Branches auf (mit Steps und ohne Steps).

## Ergebnis
**NEEDS FIXES** -- mindestens der KRITISCH-Bug muss vor einem Commit behoben werden.
