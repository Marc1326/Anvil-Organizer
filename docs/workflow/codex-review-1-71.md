# Code-Review 1 — ReShade Wizard (Issue #71)
Datum: 2026-03-26
Reviewer: Codex-Agent 1

## Geprueft
- anvil/core/reshade_manager.py (NEU)
- anvil/dialogs/reshade_wizard.py (NEU)
- anvil/mainwindow.py (GEAENDERT)
- anvil/widgets/toolbar.py (GEAENDERT)
- 7x Locale-Dateien (GEAENDERT)

## Findings

### F-01: QPushButton.clicked sendet bool — Lambda in toolbar.py
- **Datei:** anvil/widgets/toolbar.py, Zeile mit `lambda: _call_win("_on_reshade_wizard")`
- **Schwere:** Niedrig
- **Problem:** Qt `QPushButton.clicked` sendet einen `bool`-Parameter (checked). Die Lambda-Funktion ignoriert diesen implizit, was in Python funktioniert aber unsauber ist.
- **Bewertung:** Bestehendes Pattern im Code — alle anderen toolbar-Lambdas machen das gleich. KEIN Fix noetig.

### F-02: configparser aendert ReShade.ini Formatierung
- **Datei:** anvil/core/reshade_manager.py, Zeile 255
- **Schwere:** Niedrig
- **Problem:** Python's configparser schreibt die INI in einem leicht anderen Format als ReShade erwartet (Leerzeichen um "=", Lowercase keys). ReShade toleriert beides.
- **Bewertung:** Akzeptabel. ReShade ist tolerant gegenueber Formatierung.

### F-03: detect_installed() prueft DX11 und DX12 auf gleiche DLL
- **Datei:** anvil/core/reshade_manager.py, Zeile 59
- **Schwere:** Info
- **Problem:** DX11 und DX12 nutzen beide dxgi.dll. detect_installed() gibt bei Vorhandensein von dxgi.dll immer "dx11" zurueck, auch wenn DX12 gemeint war.
- **Bewertung:** Akzeptabel. Die API-Erkennung ist ohnehin nicht eindeutig ueber die DLL allein. Der User kann die korrekte API im Wizard waehlen.

## Ergebnis: ACCEPTED

Keine blockierenden Findings. Der Code ist sauber, gut dokumentiert, folgt dem bestehenden Anvil-Pattern und hat keine Bugs.
