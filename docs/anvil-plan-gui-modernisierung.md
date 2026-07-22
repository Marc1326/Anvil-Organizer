# Plan: GUI-Modernisierung nach Design-Handoff („Anvil GUI modernisieren.zip")

Stand: 2026-07-02 (überarbeitet nach Marcs Antworten) · Branch: v2/modern-gui · Status: WARTET AUF GO

## Entscheidungen von Marc (2026-07-02)
1. Alte GUI muss bestehen bleiben; neue GUI wird als v2 neu gebaut. QML-Versuch von gestern löschen.
2. Keine rahmenlose Custom-Titlebar — bestätigt (Instanz-Dropdown + Glocke in die vorhandene obere Leiste).
3. Deploy-Button ist NUR für BG3 (im Code verifiziert: `toolbar.py:153`, standardmäßig unsichtbar, erscheint nur bei BG3 „dirty" via `_bg3_mark_dirty()` `mainwindow.py:6360`). Alle anderen Spiele deployen automatisch beim Aktivieren bzw. Spielstart. → Bleibt exakt so; keine Änderung am Verhalten.
4. Themes: Empfehlung angenommen — neues System (Dunkel/Hell + Akzent + Dichte) vorne, klassische Themes als eigener Bereich darunter.
5. Instanz-Trennung ist Kern-Identität (wie MO2): Wechsel = aktuelle Instanz vollständig schließen → neue öffnen. Das neue Instanz-Dropdown MUSS exakt diesen Mechanismus nutzen (siehe E7).

---

## 1. Ausgangslage

### Die Vorlage
`design_handoff_anvil_gui/` (aus der ZIP) enthält:
- `README.md` — **maßgeblich**: exakte Farb-Tokens (Dunkel + Hell), 3 Akzentfarben (Teal/Violett/Blau), Maße, Radien, Zeilenhöhen, Beschreibung aller 13 Screens
- `Anvil Prototyp.dc.html` + `support.js` — interaktiver HTML-Prototyp (nur Referenz)
- 9 Screenshots (nur für Layout-Kontrolle, **Farben NIE aus PNGs pipetten**)

**Zentrale Vorgabe der Vorlage:** Das Design soll **im bestehenden PySide6/Qt-Code nachgebaut werden** — mit `anvil/mainwindow.py`, `anvil/widgets/*`, QSS-Theming. Kein QML, keine Neuentwicklung.

### Der alte Versuch (zu verwerfen)
- `qml/` + `main_v2.py` (Commit `d6b883d` auf v2/modern-gui, plus uncommittete Änderungen an den QML-Dateien)
- QML-Neuentwicklung nach Screenshot → falscher Ansatz laut Vorlage, unvollständig, Farben gepipettet
- → wird entfernt (siehe Frage 1 an Marc: Dateien löschen / Branch-Umgang)

### Ist-Zustand des Codes (verifiziert durch Code-Analyse)
- **Widget-Struktur passt 1:1** zum Mapping-Vorschlag der Vorlage: `toolbar.py`, `profile_bar.py`, `mod_list.py`, `filter_panel.py`, `game_panel.py`, `status_bar.py`, `log_panel.py`, `instance_manager_dialog.py`, `instance_wizard.py`, `settings_dialog.py`, `toast.py` existieren alle.
- **Theme-System** (`anvil/styles/dark_theme.py`): lädt statische QSS-Dateien (9 Themes, alle dunkel), ersetzt per Regex 6 Farbrollen (Feature #18). **Kein helles Theme, keine Token-Platzhalter, keine Akzent-Varianten.**
- **~180 direkte `setStyleSheet()`-Aufrufe** in 25 Dateien mit hartkodierten Hex-Farben (Top: mod_detail_dialog 25, collection_import 18, export_import 17, backup_dialog 17, instance_wizard 14, profile_bar 13, log_panel 9).
- **Hartkodierte Farben in Paint-Code:** CheckboxDelegate (`mod_list.py:123-200`, grün `#4CAF50`), Separator-Fallback `#D3D3D3`, Frameworks-Label `mod_list.py:1109` (`#1a2a3a`), Deploy-Dirty `mainwindow.py:6364` (`#4DE0D0`), Log-Level-Farben.
- **BG3 nutzt die NORMALE Mod-Liste** (`mainwindow.py:6230-6241`, „Use normal mod list view — NOT the BG3-specific one"). Unterschiede nur: Deploy/LOOT/Merger/Proton-Buttons ausgeblendet, `.pak`-Drop, eigenes Profil-System. Die separate `BG3ModListView` (bg3_mod_list.py) ist Legacy und wird nicht aufgerufen.
- **Zeilenhöhe** Mod-Liste: fest `min-height: 24px` im QSS (alle Themes).
- **Icons:** SVG-Assets nur in Dunkel-Variante (`anvil/styles/Paper/Dark/`).

---

## 2. Grundsatz-Entscheidungen des Plans

### E0 — Alte GUI bleibt bestehen: Trennung über Versionen/Branches (Empfehlung)
- `main` = Anvil mit der **alten GUI**, bleibt unangetastet und weiter release-fähig (v1.x-Linie).
- `v2/modern-gui` = Anvil mit der **neuen GUI**: dort wird der bestehende Widget-Code umgebaut. Wird v2 fertig, ist das Anvil 2.0 — die alte GUI existiert weiterhin als v1 (Branch + Releases).
- Alternative (NICHT empfohlen): beide GUIs in EINER App umschaltbar. Das hieße doppelte Render-Pfade in fast jedem Widget und doppelte Pflege bei jedem künftigen Feature — dauerhaft teuer.

### E1 — Ansatz: Restyling des bestehenden Widget-Codes (kein QML)
Genau wie die Vorlage vorgibt. `main_v2.py` und `qml/` werden gelöscht (Marcs Entscheidung 1). Alle Funktionen bleiben — die Vorlage sagt explizit „ohne Funktionen zu entfernen".

### E2 — Zwei neue Themes: „Anvil Dunkel" (Standard) und „Anvil Hell"
- Aufgebaut **exakt** aus den Token-Tabellen im README (bg `#131519`, panel `#1a1d22`, panel2 `#20242a`, line `#2a2e35`, txt/txt2/txt3, hov, ok, warn; Hell-Set analog).
- 3 wählbare Akzentfarben (Teal Standard, Violett, Blau) mit „soft"-Varianten laut README.
- Die **bestehenden 9 Themes bleiben funktionsfähig** (kein Breaking Change am Regex-Override-System von #18).

### E3 — Token-System erweitern statt umbauen
`dark_theme.py` bekommt für die zwei neuen Themes ein Platzhalter-System (`{{token}}` in den neuen QSS-Dateien → Ersetzung beim Laden). Neue Rollen: `bg, panel, panel2, line, txt, txt2, txt3, hov, ok, warn, accent, accent_soft, accent_text`. Alte Themes laufen weiter über den bestehenden Hex-Regex-Mechanismus. Der Farbeditor aus #18 (Style-Tab) funktioniert für die neuen Themes über die neuen Rollen.

Zusätzlich kleiner Helper (`ThemeColors` o.ä.): aktuelle Palette zur Laufzeit abfragbar — damit Delegates/Paint-Code (Schalter, Separatoren, Badges, Log-Farben) beim Theme-Wechsel mitgehen. **Keine neuen `setStyleSheet()` in neuen Widgets** (CLAUDE.md-Regel) — neue Widgets bekommen objectNames und werden im QSS gestylt.

### E4 — BG3: identischer Aufbau, nur neue Optik (Marcs Vorgabe 5)
- **Kein struktureller Eingriff** in BG3. Da BG3 die normale Mod-Liste nutzt, erbt es das neue Design automatisch mit — gleiche Buttons, gleiches Verhalten wie jetzt.
- Die „BG3-Spezialansicht" aus der Vorlage (Screen 12: Autor-Spalte, Aktiv/Inaktiv-Bereiche) wird **NICHT** umgesetzt.
- `bg3_mod_list.py` und `bg3_mod_handler.py` werden **nicht angefasst** (BG3-Verbot). Theme-relevante Farb-Fixes passieren nur im **gemeinsamen** Code (mod_list.py-Delegates, mainwindow-Statuszeile), von dem BG3 profitiert, ohne dass sich Verhalten ändert.

### E5 — Vorlage ≠ vollständig: alles Bestehende bleibt, bekommt nur die neue Optik
Die Vorlage zeigt nur einen Teil (7 Toolbar-Textbuttons, 6 Settings-Tabs). Anvil hat real: 16+ Toolbar-Buttons (inkl. Deploy/LOOT/Script-Merger/Proton/Executables/Donate/Update), Menübar mit 4 Menüs, 9–10 Settings-Tabs, ~18 weitere Dialoge. Regel:
- **Nichts wird entfernt.**
- Buttons/Tabs, die die Vorlage nicht kennt, bleiben an ihrem Platz und erben Optik über QSS (Textbutton-Stil, Pills-Tabs).
- Der Deploy-Button ist ein reiner **BG3-Sonderfall** (nur sichtbar bei ungespeicherten BG3-Änderungen) und bleibt exakt wie er ist — nur seine Hervorhebungs-Farbe (`#4DE0D0`, `mainwindow.py:6364`) kommt künftig aus der Theme-Palette. Alle anderen Spiele deployen bereits automatisch (Mod-Aktivierung / Spielstart) — das entspricht schon der Vorlage („kein Deploy-Button").

### E7 — Instanzwechsel: bestehender Schließen→Öffnen-Mechanismus bleibt 1:1 (Kern-Identität, Marcs Punkt 5)
Der strikte Instanzwechsel ist bereits vollständig implementiert — `switch_instance()` (`mainwindow.py:1148`), 2-Phasen:
- **Phase 1 — Instanz schließen** (`_teardown_current_instance()`, `mainwindow.py:1079`): Timer stoppen, Async-Queues/REDmod abbrechen, modlist + BG3-Trenner + UI-State speichern, Frameworks locken, Deploy **purgen** (`silent_purge()`), Model leeren, **Filter + Suche zurücksetzen**, alle State-Variablen nullen.
- **Phase 2 — Instanz öffnen** (`_apply_instance()`, `mainwindow.py:1180`): neue Instanz komplett laden (Plugin, Pfade, Mods, Profile, Panels). `.current` wird erst nach Erfolg persistiert.

**Für die neue GUI gilt:** Das neue Instanz-Dropdown in der oberen Leiste implementiert KEINE eigene Wechsel-Logik — es ruft ausschließlich `switch_instance()` auf, exakt wie heute der Instanz-Manager (`mainwindow.py:647-648`). Das Instanzwechsel-Overlay (Vorlage Screen 3, „Kernverhalten") ist nur die **Visualisierung** dieser bestehenden Sequenz („Instanz X wird geschlossen … Instanz Y wird geöffnet …" + Toast). Auch die Einstellung „Instanzwechsel bestätigen" (Allgemein-Tab) wird vom Dropdown respektiert. Die Vorlage deckt sich hier exakt mit dem Code — sogar das Zurücksetzen von Suche/Filter beim Wechsel steht in beiden.

### E6 — Keine eigene rahmenlose Titelleiste (von Marc bestätigt)
Die Vorlage zeigt eine 46-px-Titelzeile mit Logo, Menütexten, mittigem Instanz-Dropdown und Glocke. Ein rahmenloses Fenster mit Custom-Titlebar ist unter Wayland (niri) riskant (Move/Resize, Server-Side-Decorations). **Entschieden:** Instanz-Dropdown (neu) + vorhandener Glocken-Button + Hell/Dunkel-Umschalter kommen in die bestehende Menü-/Toolbar-Zeile; System-Titelleiste bleibt.

---

## 3. Betroffene Dateien

### Neu
| Datei | Zweck |
|---|---|
| `anvil/styles/Anvil Dunkel.qss` | Neues Standard-Theme, Token-Platzhalter |
| `anvil/styles/Anvil Hell.qss` | Helles Theme, Token-Platzhalter |
| `anvil/widgets/toggle_switch.py` | Wiederverwendbarer Schiebeschalter (Widget + ItemDelegate für Mod-Liste), Farben aus Palette |
| `anvil/widgets/instance_dropdown.py` | Instanz-Dropdown (Cover-Chip, Name, Store·Profil, Liste + „Neue Instanz…"/„Instanz-Manager…") |
| `anvil/widgets/switch_overlay.py` | Instanzwechsel-Overlay (Spinner + Sequenz-Texte) |

### Geändert (Kern)
| Datei | Änderung |
|---|---|
| `anvil/styles/dark_theme.py` | Token-Rollen + `{{token}}`-Ersetzung für neue Themes, Akzent-/Dichte-Parameter, Palette-Helper |
| `anvil/mainwindow.py` | Instanz-Dropdown einhängen, Overlay beim `switch_instance()`, Deploy-Dirty-Farbe aus Palette, Aktiv-Badge „n / m" |
| `anvil/widgets/toolbar.py` | Textbutton-Optik (objectNames/QSS), „＋ Mod installieren" prominent, Reihenfolge laut Vorlage, Rest bleibt |
| `anvil/widgets/mod_list.py` | CheckboxDelegate → Schiebeschalter-Delegate, Drag-Griff ⠿, Separator-Optik (Farbbalken, panel2), Kategorie-Pills, Konflikt-Badges („△ gewinnt/verliert"), Frameworks-Label-Farbe aus Palette, Zeilendichte |
| `anvil/widgets/profile_bar.py` | Segment-Tabs-Optik (aktiv = Akzent), ＋-Button, hartkodierte Farben → QSS/Palette |
| `anvil/widgets/filter_panel.py` / `filter_chip.py` | Pill-Chips r=20, aktive Chips soft-Akzent, „Bearbeiten"-Link, „Filter zurücksetzen" |
| `anvil/widgets/game_panel.py` | Cover 120×160 r=9 (Bild oder Platzhalterfarbe+Kürzel), „▶ Starten" Akzent, Tab-Optik |
| `anvil/widgets/status_bar.py` | Format `Instanz | Plugin | Store | Profil` + „● Deploy"-Anzeige rechts |
| `anvil/widgets/log_panel.py` | Log-Level-Farben aus Palette (hell-tauglich) |
| `anvil/widgets/settings_dialog.py` | Style-Tab: Design-Karten Dunkel/Hell, Akzent-Swatches, Zeilendichte Kompakt(26)/Komfortabel(32); Tab-Optik als Pills |
| `anvil/widgets/instance_manager_dialog.py` | „Icon & Bild"-Bereich (Cover-Vorschau, Bild wählen, 6+2 Farbfelder, Zurücksetzen), Layout laut Screen 4 |
| `anvil/widgets/toast.py` | Optik laut Vorlage (Akzent-Rahmen, r=9, 180 ms) |
| `anvil/dialogs/fomod_dialog.py`, `mod_detail_dialog.py`, übrige Dialoge | Nur Optik: hartkodierte Farben → Palette, Schalter-Optik für Checkboxen |
| `anvil/locales/*.json` (alle 6) | Neue tr()-Keys (Akzentfarbe, Zeilendichte, Hell/Dunkel, Overlay-Texte, …) |

### Entfernt (nach GO / Frage 1)
- `qml/` (kompletter Ordner), `main_v2.py`, ZIP ggf. nach `docs/` bzw. `_dev/` verschieben

### NICHT angefasst
- `anvil/widgets/bg3_mod_list.py`, `anvil/plugins/games/bg3_mod_handler.py` (BG3-Verbot)
- Deploy-/Backend-Logik, modlist.txt-Format, Instanz-Mechanik — reines GUI-Projekt

---

## 4. Impact-Analyse

1. **Alle 9 Alt-Themes** müssen nach jedem Schritt weiter funktionieren (Regex-Override #18 bleibt unberührt; neue objectNames bekommen Fallback-Styles in den Alt-QSS nicht — dort greifen die generischen Widget-Regeln, d.h. neue Widgets sehen im Alt-Theme neutral aus, nicht kaputt).
2. **Schiebeschalter-Delegate** ersetzt den Kreis-Check im gemeinsamen Delegate → wirkt auf alle Spiele inkl. BG3. Verhalten (Klick = an/aus) bleibt identisch, nur Zeichnung ändert sich.
3. **Checkboxen in Einstellungen/FOMOD:** Umstellung auf Schalter-Optik über `QCheckBox::indicator`-Styling im neuen QSS (SVG-Grafiken AN/AUS) — kein Umbau jedes Dialogs nötig. Dialoge mit hartkodierten Farben werden schrittweise auf Palette umgestellt.
4. **Helles Theme:** größter Einzelaufwand sind die ~180 hartkodierten dunklen Farben und die nur dunkel vorhandenen SVG-Icons. Vorgehen: Icons für Hell-Variante zweitfarbig ablegen (`Paper/Light/` bzw. `Anvil/Light/`) oder beim Laden einfärben; hartkodierte Farben priorisiert im Hauptfenster, dann Dialoge.
5. **Wayland/niri:** keine rahmenlose Titelleiste (E6) → kein Fenster-Management-Risiko.
6. **i18n:** jeder neue String in **allen 6** Locale-Dateien, sonst Regressionen.
7. **Performance:** Schalter-Delegate zeichnet pro Zeile — gleiche Größenordnung wie bisheriger Kreis-Check, kein Risiko.

---

## 5. Umsetzung in Phasen (je Phase: `./restart.sh` + Log prüfen + Commit)

**Phase 0 — Aufräumen** (nach Frage 1): `qml/`, `main_v2.py` entfernen; Handoff-Ordner entpackt nach `_dev/design_handoff/` legen.

**Phase 1 — Theme-Fundament:** Token-System in `dark_theme.py`, `Anvil Dunkel.qss` + `Anvil Hell.qss` aus den README-Tabellen, Akzent-Mechanik (3 Farben), Zeilendichte-Parameter. Style-Tab: Design-Karten, Akzent-Swatches, Dichte-Umschalter. → App wirkt danach bereits weitgehend neu, weil fast alles QSS erbt.

**Phase 2 — Mod-Liste:** Schiebeschalter-Delegate, Drag-Griff ⠿, Separator-Zeilen (panel2 + Farbbalken 3×14 r=2), Kategorie-Pills, Konflikt-Badges, Spaltenkopf-Typografie, Frameworks-Leiste-Optik, Zebra/Dichte. Hartkodierte Farben in mod_list.py → Palette (BG3 erbt automatisch).

**Phase 3 — Leisten & Panels:** Toolbar (Textbuttons, „＋ Mod installieren", Aktiv-Badge), Profilleiste (Segment-Tabs + ＋), Filterpanel (Chips r=20, Bearbeiten-Link), Game-Panel (Cover, Starten, Tabs), Statusbar, Log-Leiste.

**Phase 4 — Instanz-UX:** Instanz-Dropdown (neu; ruft nur `switch_instance()` auf, siehe E7), Instanzwechsel-Overlay + Toast als Visualisierung der bestehenden Schließen→Öffnen-Sequenz, Instanz-Manager-Dialog (Icon & Bild, Farbfelder), Instanz-Assistent-Optik.

**Phase 5 — Dialoge:** FOMOD/„Mod installieren", Mod-Vorschau/-Details, Konflikt-Dialog-Optik, Kontextmenü-Optik, Kategorien/Profil-Dialoge; hartkodierte Farben der Dialoge → Palette.

**Phase 6 — Hell-Feinschliff & QA:** Icon-Varianten hell, restliche hartkodierte Farben, alle 6 Locales, Durchgang aller Spiele-Instanzen inkl. **BG3-Sichtprüfung** (gleiche Buttons, neue Optik), alle Alt-Themes gegentesten. Danach Review-Prozess laut CLAUDE.md (4 Agents).

---

## 6. Themes in v2 — Empfehlung (von Marc angenommen)

Marcs Bedenken: zwei parallele Anpass-Systeme (Dunkel/Hell + Akzent EINERSEITS, frei wählbare .qss-Themes ANDERERSEITS) könnten verwirren. Ihm selbst würde der Akzent-Wechsel reichen, User evtl. nicht.

**Empfehlung — beides behalten, aber klar getrennt präsentieren:**
- Der Style-Tab in v2 zeigt primär das neue System: Design-Karten **Dunkel/Hell** + **Akzentfarbe** (Teal/Violett/Blau) + **Zeilendichte**. Das ist der Standard-Weg für die meisten User.
- Darunter ein Bereich „**Klassische Themes**" mit dem bekannten Dropdown (Cyberpunk, Dracula, Nord, …). Wählt man ein klassisches Theme, sind Design-Karten/Akzent ausgegraut (gelten nur für Anvil Dunkel/Hell); der bestehende Farbeditor (#18) bleibt für klassische Themes erhalten.
- Kosten: nahezu null — der QSS-Lade-Mechanismus bleibt sowieso bestehen. Nichts geht verloren: Wer die alten Themes mag, behält sie; wer es einfach will, sieht zuerst nur Dunkel/Hell + Akzent.
- Falls die alten Themes in v2 zur Pflege-Last werden, kann man sie später entfernen — andersherum wäre es schwerer.

## 7. Offene Fragen an Marc (vor GO)

1. **Alte GUI bewahren — Interpretation bestätigen:** Reicht die Branch-/Versions-Trennung (E0: `main` = alte GUI bleibt unangetastet, `v2/modern-gui` = Umbau zur neuen GUI, später Anvil 2.0)? Oder willst du wirklich BEIDE GUIs in EINER App umschaltbar (deutlich mehr Aufwand, dauerhaft doppelte Pflege — nicht empfohlen)?
