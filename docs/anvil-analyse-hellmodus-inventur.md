# QA-Analyse — Inventur hartkodierter Farben für den Hell-Modus („Anvil Hell")

Datum: 2026-07-03
Ziel: Alle hartkodierten Farben finden, die im MODERNEN Hell-Theme falsch wirken (keine Token/Palette, kein Modern-Guard). NUR Analyse, kein Code geändert.

Methode: `grep` über `anvil/**/*.py` nach `setStyleSheet`, `#RRGGBB`, `QColor(`; jede relevante Fundstelle im Kontext gelesen; Guard-Prüfung gegen `_modern`, `is_modern_theme_active()`, `theme_color("panel2", "")`, `current_palette()`. Zusätzlich `anvil/styles/modern/anvil-modern.qss` und die SVG-Icons geprüft.

Token-Basis (aus `dark_theme.py`, Hell-Palette): `bg #f2f3f5`, `panel #ffffff`, `panel2 #e9ebee`, `line #d9dce1`, `txt #20242c`, `txt2 #5b6170`, `txt3 #9096a1`, `ok #2e8757`, `warn #9a7526`, `accent` (teal `#0e8a80`), `accent_text #0d1113`.

---

## Kategorie A — Wirkt modern, im Hell-Modus SICHTBAR FALSCH (MUSS gefixt werden)

### A1 — Toolbar-Icons nicht theme-fähig (HÖCHSTE Priorität)
- Datei: `anvil/widgets/toolbar.py:21-25` (`_icon()`), lädt `anvil/styles/icons/*.svg`
- Betroffen: `settings.svg`, `refresh.svg`, `plugin.svg`, `instances.svg`, `problems.svg`, `archives.svg`, `backup.svg`, `profiles.svg`, `sort.svg`, `tools.svg`, `check.svg`, `update.svg`, `help.svg`, `endorse.svg`, `proton.svg` …
- Farbe: Alle SVGs sind fest `fill:#d3d3d3` / `stroke:#d3d3d3` bzw. `stroke="#FFFFFF"` (backup.svg) — der „Paper Dark"-Icon-Satz. Werden per `QIcon(str(path))` roh geladen, KEINE Einfärbung nach Theme (QSS kann QIcon-SVG nicht umfärben).
- Problem Hell-Modus: Hellgraue Icons auf hellem Toolbar-Grund (`panel #ffffff` / `bg #f2f3f5`) → praktisch unsichtbar. Toolbar ist IMMER sichtbar → gravierend.
- Empfehlung: Icons zur Laufzeit nach `theme_color("txt2")` umfärben (QPainter-Tint / eigene IconEngine) oder — analog zu `modern/dark` + `modern/light` — einen dunklen Icon-Satz für Hell bereitstellen und in `toolbar._icon()` je nach `is_modern_theme_active()`/Hell wählen.

### A2 — Log-Bereich komplett fest dunkel
- Datei: `anvil/widgets/log_panel.py:45-215` (kein `theme_color`-Import, kein Guard)
- Farben: Header `background:#242424` (165), ScrollArea `background:#1a1a1a` (193/197/215), Handle `#3D3D3D`/`#006868` (202/207), Eintrags-Hover `#3D3D3D` (54), Nachrichtentext `#D3D3D3` (71), Zeitstempel `#555555` (83), Level-Badges (115-139).
- Betroffenes Widget: LogPanel (unten im Hauptfenster, per Bar aufklappbar).
- Problem Hell-Modus: Kompletter dunkler Panel-Block in heller UI; `#D3D3D3`/`#555555` Text auf dunklem Block bleibt dunkel-in-hell inkonsistent.
- Empfehlung: `panel`/`panel2`/`bg` für Hintergründe, `txt2` Nachrichten, `txt3` Zeitstempel, `line` Ränder, `hov` Hover, `accent` Handle-Hover.

### A3 — Kontextmenü Kategorie-Buttons (Rechtsklick Mod)
- Datei: `anvil/mainwindow.py:2915-2972` (`_show_mod_context_menu`, ungeguarded)
- Farben: zugewiesen `color:#00d4aa`; NICHT zugewiesen `color:#e0e0e0`; Hover `background:#2d2d2d`.
- Problem Hell-Modus: `#e0e0e0` (sehr helles Grau) auf hellem Menühintergrund → nahezu unsichtbar; dunkler `#2d2d2d`-Hover in heller UI.
- Empfehlung: `txt` (nicht zugewiesen), `accent` (zugewiesen), `hov` (Hover) — oder kein `setStyleSheet`, damit das QSS-Menü greift.

### A4 — Weißer Status-Text in Downloads-Tabelle
- Datei: `anvil/widgets/game_panel.py:3001` — `status_item.setForeground(QColor("#FFFFFF"))`
- Betroffen: Downloads-Tab, Status „Nicht installiert" nach Abschluss eines Downloads.
- Problem Hell-Modus: Weißer Text auf heller Tabellen-/Panel-Fläche → unsichtbar.
- Empfehlung: `theme_color("txt")` (Fehlerfall Zeile 3016 `#F44336` bleibt als B okay).

### A5 — Instanz-Dropdown Cover-Chip: Text folgt Theme, Chip bleibt dunkel
- Datei: `anvil/widgets/instance_dropdown.py:27,73-74`
- Farben: `_CHIP_COLORS = ["#3d4a52", …]` (dunkle Platzhalter), Text `p.setPen(QColor(theme_color("txt", "#E8E8E8")))`.
- Problem Hell-Modus: Chip-Fläche fest dunkel, aber `txt` ist im Hell `#20242c` (dunkel) → dunkler Text auf dunklem Chip = unlesbar. Titelleiste, hohe Sichtbarkeit.
- Empfehlung: Für Initialen fixe helle Farbe (`#FFFFFF`/`#E8E8E8`) verwenden — so wie es `instance_manager_dialog.py:94` bereits korrekt macht (`QColor(255,255,255,217)`). Inkonsistenz zwischen beiden Stellen.

### A6 — Filter-Kontextmenü fest dunkel
- Datei: `anvil/widgets/filter_chip.py:11-30` (`CONTEXT_MENU_STYLE`), angewandt in `anvil/widgets/filter_panel.py:341,373` (ungeguarded)
- Farben: `QMenu background:#2b2b2b`, Item `color:#e0e0e0`, selected `#4de0d0`/`#1a1a1a`, disabled `#666666`.
- Problem Hell-Modus: Dunkles Popup-Menü in heller UI (Rechtsklick auf Kategorie-Chip / leere Fläche).
- Empfehlung: Menü-Style tokenisieren (`panel`/`txt`/`accent`) oder im Hell weglassen (globales QSS greift).

### A7 — Mod-Detail-Dialog: Tab-Inhalte fest dunkel (Rahmen ist geguarded, Inhalt nicht)
- Datei: `anvil/dialogs/mod_detail_dialog.py`
- Dialograhmen ist geguarded (`1551/1556 if self._modern … else _MOD_DETAIL_DIALOG_STYLE`), ABER die `_build_*_tab`-Helfer setzen Farben unbedingt:
  - Pfadfelder `color:#808080; background:#1C1C1C` (586, 626, 629, 759, 797, 815, 818, 822) → dunkle Boxen in hellem Dialog
  - `primary_combo` `background:#2b2b2b; color:#e0e0e0` (1499ff)
  - Trennlinie `background:#3a3a3a` (1488), Label `color:#aaaaaa` (1494)
  - `_CATEGORY_CHIP_STYLE` (1329), `_CATEGORY_TAB_CONTEXT_MENU_STYLE` (1432)
- Problem Hell-Modus: Dunkle Eingabefelder/Combos/Trenner in ansonsten hellem Dialog; `#aaaaaa`/`#808080`-Texte teils kontrastarm.
- Empfehlung: In den Tab-Helfern `theme_color` verwenden bzw. Inline-Styles im Hell entfernen. (Konflikt-Tab win/lose-Labels bei 1186-1225 sind bereits per `_modern` geguarded — OK.)

### A8 — Backup-Dialog komplett fest dunkel
- Datei: `anvil/dialogs/backup_dialog.py:18-299` (kein `theme_color`, kein Guard)
- Farben: `#141414`/`#242424`/`#3D3D3D` bg, `#D3D3D3`/`#808080`/`#A0A0A0` Text, `#006868`/`#007878` Buttons, `#ff4444` Löschen.
- Erreichbarkeit modern: über Toolbar „Sicherung ▾" → Erstellen/Wiederherstellen (`toolbar.py:139-146`). Also im Hell-Modus sichtbar.
- Empfehlung: Karten/Buttons/Texte tokenisieren oder Dialog per `wrap_modal` + QSS-objectNames aufbauen.

### A9 — Überschreiben-Abfrage fest dunkel
- Datei: `anvil/dialogs/query_overwrite_dialog.py:18-53` — `_STYLE` (`QDialog background:#1C1C1C; color:#D3D3D3` …) unbedingt via `setStyleSheet(_STYLE)`.
- Erreichbarkeit modern: Bei Datei-Konflikt während Installation.
- Empfehlung: `_STYLE` nur klassisch anwenden (Guard wie in `quick_install_dialog`), modern QSS greifen lassen.

### A10 — Collection/Export-Import-Dialoge komplett fest dunkel
- Dateien:
  - `anvil/dialogs/collection_export_dialog.py:40-240` (`#2B2B2B`/`#1a1a1a`/`#D3D3D3`/`#A0A0A0`/`#006868`, kein Guard)
  - `anvil/dialogs/collection_import_dialog.py:33-299` (analog, plus `#4a2020`/`#ff8888` Warnungen)
  - `anvil/dialogs/export_import_dialog.py:19-271` (`#242424`/`#1a1a1a`/`#3D3D3D`/`#006868`, Karten/Tabs, kein Guard)
- Problem Hell-Modus: Ganze Dialoge bleiben dunkel.
- Empfehlung: Guard + Tokenisierung oder `wrap_modal`.

### A11 (nachrangig) — Weitere ungeguardete Dialoge/Boxen
- `anvil/widgets/executables_dialog.py:22-40` — `_EXEC_DIALOG_STYLE` fest dunkel, unbedingt. (In der Toolbar nur `if not modern` verlinkt — Erreichbarkeit im Hell prüfen; falls über anderes Menü erreichbar → A, sonst C.)
- `anvil/widgets/donate_dialog.py:98,119,164` — `color:#ccc` / `color:#888` Texte + `background:#2a2a2a`-Box: kontrastarm/dunkel auf hell. Niedrige Sichtbarkeit.

---

## Kategorie B — Wirkt modern, aber vermutlich unauffällig (eigene Badge-/Neutralfarbe)

- `anvil/widgets/mod_list.py`
  - `_SEP_BAR_DEFAULT = "#6f63b8"` (33) — violetter Separator-Balken (Handoff), dekorativer Akzent, auf hell sichtbar.
  - `SeparatorMarkingScrollBar._DEFAULT_COLOR = "#4FC3F7"` (52) — Scrollbar-Marker, eigene Farbe.
  - `group_color`-Fallback `"#4FC3F7"` (373/375) — Gruppen-Farbbalken, user-definiert.
  - Schalter-Knopf `QColor("#FFFFFF")` (260) — laut Handoff immer weiß; im AUS-Zustand (Track = `line #d9dce1`) minimal kontrastarm, sonst ok.
- `anvil/widgets/game_panel.py`
  - Cover-Pfeil-Overlay `rgba(0,0,0,150)` + `#FFF` (187-190) — Badge auf Cover-Bild.
  - Cover-Chip mit Initialen `#FFFFFF` auf `_instance_cover_color` (620/623) — eigene Chip-Farbe.
  - `#F44336` Download-Fehler (3016), Gold-Sterne (`mainwindow.py` 2994/3032 `#FFD700`).
- `anvil/widgets/notification_panel.py` — Badge `#D9534F` + weiß (56/62), Severity `#5BC0DE/#E5C07B/#E06C75` (22-24), Platzhalter `#808080` (102).
- `anvil/widgets/toast.py:20` — `background:#006868` + weiß (eigenes Toast-Badge; feste Alt-Teal statt Akzent-Token, aber lesbar).
- `anvil/widgets/switch_overlay.py:76` — `QColor(8,10,12,158)` dunkler Dimm-Backdrop (bewusst dunkel, analog Modal-Backdrop).
- `anvil/core/icon_manager.py:24-50` — `placeholder_game_icon`/`placeholder_banner` dunkle Platzhalter-Kacheln (Cover-Ersatz).
- `anvil/styles/modern/anvil-modern.qss:499,667,891,967` — `color:#0d1113`/`#0f1113` als Text auf `background:{{accent}}` (createBtn/switchBtn/setOkBtn/densBtn). Entspricht dem `accent_text`-Token → in beiden Themes lesbar; kosmetisch besser `{{accent_text}}`.
- `anvil/widgets/settings_dialog.py` — Hinweistexte `#808080` (181/904), Diagnose/Status-Farben `#98C379/#E5C07B/#E06C75/#888888` (1429-1455) und `#30b050/#e04040` (1168/1171), Legende-Swatches (439-444), HTML-Link `#4FC3F7` (1352). Grün/Gelb/Blau pastellig → auf Weiß teils grenzwertig kontrastarm, aber niedrige Sichtbarkeit (Einstellungen/Diagnose).
- `anvil/dialogs/mod_detail_dialog.py` — diverse `#808080`-Zähler/Info-Labels (713/899/941/1178/1255).
- `anvil/widgets/plugin_creator_dialog.py:81` — `background:#242424` Bild-Vorschau-Box (Dev-Tool).
- `anvil/dialogs/reshade_wizard.py:241/246` — grün/rot Status-Text.
- `anvil/widgets/script_merger_dialog.py:66-70` — Status-Dots (#888888/#FFD700/#FF4444/#44BB44/#444444), Witcher-spezifisch.
- `anvil/widgets/collapsible_bar.py:96-100` — `add_action_button` fest dunkel (`#2a4a5a`/`#ddd`/`#3a6a7a`), aber TOTER Code (nirgends aufgerufen) → latent.

---

## Kategorie C — Nur klassische Themes, unkritisch (else-Zweige hinter Modern-Guard)

- `anvil/widgets/profile_bar.py:59-190,202-225` — alle klassischen else-Zweige der Style-Funktionen (`_button_style`, `_tab_style_*`, `_tab_container_style`, `_inline_input_style`) hinter `if _modern():`.
- `anvil/widgets/mod_list.py` — `_COLOR_ON/_COLOR_OFF/_COLOR_SEP` (148-150), `_paint_circle` `#FFFFFF` (274), Frameworks-Bar Klassik-Style (1328-1329).
- `anvil/models/mod_list_model.py` — `_highlight_color/_conflict_win_color/_conflict_lose_color` (142/147/148) + else-Zweige `#3a1414`/`#143a14` (422/426), alles nur wenn `not modern`.
- `anvil/widgets/game_panel.py` — `_game_btn_style()` else (117-119).
- `anvil/mainwindow.py:327` — Log-Bar Klassik-Style (Bar wählt via `apply_theme_metrics` selbst).
- `anvil/widgets/instance_manager_dialog.py:135-174` — `_DIALOG_STYLE` (Guard 204 `if not self._modern`).
- `anvil/widgets/instance_wizard.py:131-188` — `_WIZARD_STYLE` (Guard 232), sowie klassische else-Zweige (300-303 etc.).
- `anvil/dialogs/quick_install_dialog.py:29-64` — `_STYLE` (Guard 117/123, modern via `_setup_modern`).
- `anvil/widgets/settings_dialog.py` — diverse klassische else-Zweige der geguardeten Blöcke.
- `anvil/widgets/collapsible_bar.py:83-85` — Klassik-Zweig in `apply_theme_metrics`.

---

## Kategorie D — Paint-Code nutzt bereits Palette/Token, OK

- `anvil/widgets/mod_list.py` — `theme_color`-Nutzung in `_paint_switch`/`_paint_separator_modern`/Badges/Text (188/236/250/252/396/466/497/500/503/562/565/1508), transparente Highlight-Palette (945).
- `anvil/models/mod_list_model.py` — `_tinted(theme_color(...))` und `theme_color` in `BackgroundRole`/`ForegroundRole` (366/399/403/408/418), Separator-Custom-Color mit Alpha.
- `anvil/widgets/game_panel.py` — `_game_btn_style()` modern (108-127), `pix.fill(theme_color(...))` (173/636/857), Listen-Farben (1393/2485/2503/2532/2533/2542/2963).
- `anvil/widgets/status_bar.py:42` — `theme_color("ok")` Deploy-Label; sonst nur Padding.
- `anvil/widgets/profile_bar.py` — alle modern-Zweige (theme_color) + `background: transparent` (360/365) + Paint (246/250/252/399).
- `anvil/widgets/instance_manager_dialog.py:37-119,574-576` — `_theme_qcolor(...)` Paint, weiße Initialen auf dunklem Cover (94) korrekt.
- `anvil/widgets/instance_wizard.py:60-112` — `_wiz_color(...)` Paint (theme-aware).
- `anvil/widgets/settings_dialog.py:62-69` — Paint-Helfer mit expliziter dark/hell-Fallunterscheidung.
- `anvil/widgets/switch_overlay.py:79` — `theme_color("accent")`.
- `anvil/styles/modern/anvil-modern.qss` — alle übrigen Farben laufen über `{{token}}`; `rgba(8,10,12,0.55)` (984) ist der bewusst dunkle Modal-Backdrop (Ausnahme).
- `anvil/styles/modern/{light,dark}/*.svg` — `check.svg`/`down.svg`/`switch-*.svg` haben getrennte Hell-/Dunkel-Varianten (Hell: `stroke #0d1113` bzw. `#5b6170`) → korrekt.

---

## Zusammenfassung

### Anzahl Fundstellen pro Kategorie (grobe Schätzung, viele Zeilen je Datei)
- Kategorie A (MUSS gefixt): ~14 Bereiche/Dateien, zusammen ~120-150 einzelne Farbstellen. Schwerpunkte: Toolbar-Icons, Log-Panel, 2 Kontextmenüs, Downloads-Status, Instanz-Chip, Mod-Detail-Tabs, 5 volldunkle Dialoge.
- Kategorie B (unauffällig): ~30 Stellen (Badges, Neutralgraus, Status-/Severity-Farben, dekorative Balken, QSS-accent_text).
- Kategorie C (nur klassisch): ~90 Stellen (else-Zweige der geguardeten Style-Funktionen/Dialoge).
- Kategorie D (Palette-basiert, OK): ~120+ Stellen.

Roh-Zähler zur Einordnung: `setStyleSheet` 188×, `#RRGGBB` 491× (ohne `dark_theme.py`), `QColor(` 103×.

### Die 10 wichtigsten Dateien für den Fix (sortiert nach Nutzer-Sichtbarkeit)
1. `anvil/widgets/toolbar.py` (+ `anvil/styles/icons/*.svg`) — Toolbar-Icons theme-fähig machen. Immer sichtbar, höchste Priorität.
2. `anvil/widgets/log_panel.py` — kompletter Log-Block auf Tokens.
3. `anvil/mainwindow.py` (2915-2972) — Kategorie-Kontextmenü (Rechtsklick jede Mod).
4. `anvil/widgets/game_panel.py` (3001) — weißer Downloads-Status → `txt`.
5. `anvil/widgets/instance_dropdown.py` (73-74) — Chip-Initialen fix hell statt `txt`.
6. `anvil/widgets/filter_chip.py` + `anvil/widgets/filter_panel.py` (341/373) — Filter-Kontextmenü.
7. `anvil/dialogs/mod_detail_dialog.py` — Tab-Inhalts-Helfer tokenisieren.
8. `anvil/dialogs/backup_dialog.py` — Guard + Tokenisierung (modern über Toolbar erreichbar).
9. `anvil/dialogs/query_overwrite_dialog.py` — `_STYLE` nur klassisch (Install-Konflikt).
10. `anvil/dialogs/collection_export_dialog.py` + `collection_import_dialog.py` + `export_import_dialog.py` — Guard + Tokenisierung.

### Wichtigste strukturelle Erkenntnis
Kein Deploy-/modlist-/Mod-Verwaltungs-Code betroffen (MO2-Vergleich nicht einschlägig). Die A-Findings sind reine Theming-Lücken: (a) Toolbar-Icons ohne Theme-Einfärbung, (b) mehrere Dialoge/Bereiche komplett ohne Modern-Guard fest dunkel, (c) einzelne unbedingte `QColor`/`setStyleSheet` in ansonsten geguardetem Code. Das Muster „Rahmen geguarded, Inhalt hartkodiert" (Mod-Detail) und „Text folgt Theme, Fläche fest dunkel" (Instanz-Chip) sind die tückischsten Fälle.

## Ergebnis
NEEDS FIXES — Kategorie A muss vor einer Hell-Modus-Freigabe behoben werden.
