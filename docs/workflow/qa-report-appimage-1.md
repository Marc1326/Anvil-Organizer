# QA Report -- AppImage Build fuer Anvil Organizer
Datum: 2026-02-25

## Checklisten-Pruefung

- [x] 1. PyInstaller Build erzeugt `dist/anvil-organizer/` ✅
  - Verzeichnis existiert mit 227 MB Inhalt
  - `dist/anvil-organizer/anvil-organizer` ist ein ELF 64-bit executable
  - `_internal/` enthaelt alle Data-Verzeichnisse (locales, styles, resources, assets, plugins)

- [ ] 2. Dark Theme beim direkten Start ❌ — NICHT GETESTET
  - Gemaess Auftrag wurde die App nicht gestartet (das war Aufgabe des Dev-Agents)
  - Code-Analyse: `anvil/styles/` ist korrekt im Bundle enthalten
  - ZU PRUEFEN durch manuellen Test

- [x] 3. AppDir-Struktur mit AppRun, .desktop, .png ✅
  - `build-appimage.sh` erstellt AppRun (Zeile 73-78, mit chmod +x)
  - `anvil-organizer.desktop` wird korrekt erstellt (Zeile 81-89)
  - Icon wird von `anvil/resources/logo.png` kopiert als `anvil-organizer.png` (Zeile 92)
  - AppDir wird nach Build aufgeraeumt (Zeile 124), was korrekt ist

- [x] 4. appimagetool erzeugt AppImage ohne Fehler ✅
  - `release/Anvil_Organizer-0.1.0-x86_64.AppImage` existiert (88 MB)
  - Dateityp: ELF 64-bit LSB pie executable, static-pie linked
  - Build-Skript hat Fehler-Pruefung (Zeile 115-118)

- [ ] 5. AppImage startet mit Dark Theme und Icons ❌ — NICHT GETESTET
  - Gemaess Auftrag nicht gestartet
  - Code-Analyse: Styles + Icons sind im Bundle enthalten
  - `_internal/anvil/styles/icons/` enthaelt alle erwarteten SVGs
  - `PySide6/QtSvg.abi3.so` und `libqsvg.so` Plugin sind vorhanden
  - ZU PRUEFEN durch manuellen Test

- [ ] 6. Game-Plugins werden geladen ❌ — NICHT GETESTET
  - Code-Analyse: `_internal/anvil/plugins/games/` enthaelt:
    `game_baldursgate3.py`, `game_cyberpunk2077.py`, `game_rdr2.py`, `game_witcher3.py`, `__init__.py`
  - Plugin-Dateien sind vorhanden, Laden muss manuell getestet werden

- [ ] 7. Uebersetzungen geladen ❌ — NICHT GETESTET
  - Code-Analyse: `_internal/anvil/locales/` enthaelt alle 6 Locale-Dateien:
    `de.json`, `en.json`, `es.json`, `fr.json`, `it.json`, `pt.json`
  - Dateien sind vorhanden, Laden muss manuell getestet werden

- [ ] 8. AppImage in `release/` mit plausibler Groesse (100-300 MB) ❌
  - Datei: `release/Anvil_Organizer-0.1.0-x86_64.AppImage`
  - Groesse: **88 MB** -- liegt UNTER dem erwarteten Bereich von 100-300 MB
  - Das `dist/anvil-organizer/` Verzeichnis hat 227 MB, also ist die Kompression stark
  - HINWEIS: 88 MB ist moeglicherweise noch akzeptabel, aber liegt formal unter der Grenze
  - ZU KLAEREN: Ist 88 MB akzeptabel oder deutet das auf fehlende Dateien hin?

- [x] 9. Kein Terminal-Fenster (--noconsole) ✅
  - `anvil-organizer.spec` Zeile 43: `console=False`
  - Das entspricht dem PyInstaller `--noconsole` Flag

- [x] 10. Build-Skript ist wiederholbar ✅
  - Zeile 51-53: Cleanup von `build/`, `dist/anvil-organizer/` und `AnvilOrganizer.AppDir/`
  - Vorherige Builds werden vollstaendig entfernt vor Neubau
  - `--noconfirm` Flag bei PyInstaller (Zeile 58) verhindert Rueckfragen

- [x] 11. Auto-Installation PyInstaller + appimagetool Download ✅
  - PyInstaller: Zeile 35-41 prueft via `pip show` und installiert bei Bedarf
  - appimagetool: Zeile 100-108 prueft ob `/tmp/appimagetool` existiert und laedt herunter

- [ ] 12. Hidden Import `lz4.block` deklariert ⚠️ TEILWEISE
  - `anvil-organizer.spec` Zeile 17-18: `'lz4'` und `'lz4.block'` sind deklariert
  - **ABER**: Im Build-Output (`dist/anvil-organizer/_internal/`) fehlen die lz4 .so-Dateien
  - Nur `lz4-4.4.5.dist-info/` ist vorhanden (Metadaten, keine Module)
  - Ursache vermutlich: lz4 ist fuer cpython-313 kompiliert, PyInstaller laeuft mit Python 3.14
  - Impact: `lspk_parser.py` nutzt try/except, daher kein Crash, aber BG3-PAK-Support fehlt
  - **Die Hidden-Import-Deklaration ist korrekt, aber PyInstaller packt das Modul nicht ein**

- [x] 13. Hidden Import `PySide6.QtSvg` deklariert ✅
  - `anvil-organizer.spec` Zeile 16: `'PySide6.QtSvg'` ist deklariert
  - Im Bundle vorhanden: `PySide6/QtSvg.abi3.so`, `libQt6Svg.so.6`, `libqsvg.so`

- [x] 14. Kein bestehendes Python-File unter `anvil/` veraendert ✅
  - `git diff -- anvil/` ist LEER
  - Nur neue Dateien hinzugefuegt: `build-appimage.sh`, `anvil-organizer.spec`
  - Geaenderte Dateien: `.gitignore`, `pyproject.toml`
  - `pyproject.toml`: Nur Autorenname geaendert ("Marc" -> "Nathuk")

- [x] 15. `_dev/restart.sh` startet ohne Fehler ✅ (Code-Pruefung)
  - Datei existiert und ist unveraendert (`git diff -- _dev/restart.sh` ist leer)
  - Keine Abhaengigkeiten zu Build-Artefakten
  - Nutzt `.venv/bin/python main.py` direkt, nicht das AppImage

## Zusaetzliche Findings

### [HIGH] `.gitignore` blockiert `anvil-organizer.spec`
- Datei: `/home/mob/Projekte/Anvil Organizer/.gitignore:12`
- Problem: `*.spec` in `.gitignore` verhindert, dass `anvil-organizer.spec` eingecheckt wird
- `git ls-files --others --ignored --exclude-standard -- anvil-organizer.spec` bestaetigt: Datei wird ignoriert
- Das Build-Skript benoetigt diese Datei (Zeile 11, 44-47)
- Nach einem frischen `git clone` fehlt die Spec-Datei und der Build schlaegt fehl
- Fix: `*.spec` durch spezifischere Eintraege ersetzen, oder `!anvil-organizer.spec` als Ausnahme hinzufuegen

### [MEDIUM] lz4-Module fehlen im Bundle trotz Hidden Import
- Datei: `/home/mob/Projekte/Anvil Organizer/anvil-organizer.spec:17-18`
- Problem: `lz4` und `lz4.block` sind als Hidden Imports deklariert, aber PyInstaller hat die C-Extension-Module nicht gepackt
- In `.venv/lib/python3.14/site-packages/lz4/` sind die .so Dateien fuer cpython-313 kompiliert
- PyInstaller laeuft mit Python 3.14, kann die cpython-313 .so nicht zuordnen
- Impact: BG3-PAK-Support funktioniert nicht im AppImage (Fallback auf `_HAS_LZ4 = False`)
- Fix: lz4 fuer die korrekte Python-Version neu kompilieren (`pip install --force-reinstall lz4`)

### [LOW] AppImage-Groesse unter erwartetem Bereich
- Datei: `/home/mob/Projekte/Anvil Organizer/release/Anvil_Organizer-0.1.0-x86_64.AppImage`
- Problem: 88 MB statt erwartet 100-300 MB
- Moeglicherweise korrekt (starke Kompression von 227 MB dist auf 88 MB)
- Moeglicherweise fehlen Dateien (z.B. lz4, siehe oben)
- ZU KLAEREN mit Marc

### [LOW] `pyproject.toml` Autorenname geaendert
- Datei: `/home/mob/Projekte/Anvil Organizer/pyproject.toml:13`
- Aenderung: `{name = "Marc"}` -> `{name = "Nathuk"}`
- Nicht Build-relevant, aber moeglicherweise unbeabsichtigt oder bewusst gewollt
- ZU KLAEREN mit Marc

## Zusammenfassung

| Kriterium | Status | Anmerkung |
|-----------|--------|-----------|
| 1. PyInstaller Build | ✅ | dist/ existiert mit Binary |
| 2. Dark Theme (direkt) | ⏸️ | Nicht getestet (Auftrag) |
| 3. AppDir-Struktur | ✅ | AppRun + .desktop + .png |
| 4. appimagetool | ✅ | AppImage erzeugt |
| 5. AppImage Dark Theme | ⏸️ | Nicht getestet (Auftrag) |
| 6. Game-Plugins | ⏸️ | Dateien vorhanden, nicht getestet |
| 7. Uebersetzungen | ⏸️ | Dateien vorhanden, nicht getestet |
| 8. Groesse 100-300 MB | ❌ | 88 MB -- unter Grenze |
| 9. --noconsole | ✅ | console=False in Spec |
| 10. Wiederholbar | ✅ | Cleanup-Logik vorhanden |
| 11. Auto-Install | ✅ | PyInstaller + appimagetool |
| 12. lz4.block HI | ⚠️ | Deklariert, aber nicht im Bundle |
| 13. PySide6.QtSvg HI | ✅ | Deklariert und im Bundle |
| 14. Keine anvil/ Aenderung | ✅ | git diff leer |
| 15. restart.sh | ✅ | Unveraendert, funktional |

## Ergebnis: 8/15 Punkte sicher erfuellt, 4 nicht testbar (Auftrag), 3 Probleme

### Blocker fuer READY FOR COMMIT:
1. **[HIGH]** `*.spec` in `.gitignore` verhindert Einchecken der Spec-Datei
2. **[MEDIUM]** lz4-Module fehlen im Bundle (BG3-Support im AppImage nicht funktional)
3. **[LOW]** AppImage-Groesse 88 MB unter der Spezifikation (100-300 MB)

## Ergebnis: NEEDS FIXES

Die Punkte 2, 5, 6, 7 konnten gemaess Auftrag nicht manuell getestet werden,
die Code-Analyse zeigt aber dass die benoetigten Dateien im Bundle vorhanden sind.

Die drei identifizierten Probleme muessen vor dem Commit geklaert/behoben werden:
1. `.gitignore` muss `anvil-organizer.spec` erlauben (Ausnahme-Regel hinzufuegen)
2. lz4 Python-Version-Mismatch muss behoben werden
3. AppImage-Groesse sollte mit Marc abgestimmt werden (88 MB vs. 100-300 MB Spezifikation)
