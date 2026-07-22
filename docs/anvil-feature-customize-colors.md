# Feature-Spec: Farben anpassen/zurücksetzen (#18)
**Status:** Geplant (verifiziert gegen echten Code 2026-06-28)
**Datum:** 2026-06-28

---

## 1. Problem / Ziel

GitHub-Issue #18 (Titel: *"Feature: Customize/Reset Colors in Settings Style Tab"*,
Labels: `disabled-feature`, `enhancement`):

> The color customization and reset functionality in the settings style tab is disabled.
>
> **Expected Behavior:**
> - Customize theme colors individually (background, text, accent, etc.)
> - Color picker for each customizable color
> - Reset button restores default colors of the selected theme
> - Real-time preview of color changes
>
> **Status:** UI elements present in style tab but disabled — no functionality implemented.

Im Style-Tab der Einstellungen existieren UI-Elemente (Farb-Tabelle, "Text"-Buttons,
"Farben zurücksetzen"-Button), die per `_disabled(...)` deaktiviert sind. Dahinter gibt es
keine Logik. **Grep-Verifikation:** Es existiert KEIN Teil-Code (`apply_theme`,
`default_palette`, `COLOR_ROLES`, `THEME_PALETTES`, `_color_overrides`, `style/overrides`
kommen nirgends in `anvil/` vor). Das Feature ist vollständig ungebaut — nur die deaktivierte
UI ist vorhanden.

**Ziel dieser Spec:** Die Farbanpassung funktionsfähig machen — über eine
**Theme-Variablen-Schicht**, die als Override ins zentrale QSS einfließt, OHNE
per-Widget `setStyleSheet()` (Projektregel).

**Wichtige Abgrenzung — zwei verschiedene "Farben" im Style-Tab:**
1. **Theme-Rollenfarben** (Hintergrund, Text, Akzent, …) — das eigentliche Ziel des
   Issues ("background, text, accent, etc."). Diese leben aktuell hardcoded in den
   `.qss`-Dateien.
2. **Konflikt-Highlight-Farben** (die bestehende 6-Zeilen-Tabelle: "Wird überschrieben
   (lose Dateien)" usw.). Diese sind aktuell **rein dekorativ** — die Hex-Werte stehen
   nur im Settings-Dialog und werden **nirgends** in der Modliste tatsächlich als Brush
   verwendet (siehe §2). Sie an die echte Konflikt-Darstellung zu koppeln ist ein
   separates, größeres Feature.

→ **Diese Spec liefert primär die Theme-Rollenfarben-Anpassung** (Issue-Kern). Die
bestehende Konflikt-Farbtabelle bleibt zunächst unverändert (Phase 2 / Folge-Issue).

---

## 2. Phasen-Rückgrat (Bau-Reihenfolge nach steigendem Risiko)

Reihenfolge so gewählt, dass nach jeder Phase ein lauffähiger, testbarer Zwischenstand
existiert. Risiko steigt von oben nach unten.

| # | Phase | Inhalt | Risiko | Testbar nach Phase? |
|---|---|---|---|---|
| 1 | i18n-Keys | 3 neue tr-Keys (`theme_colors`, `color_change`, `color_pick_title`) + 6 Rollen-Labels in alle 7 Locales eintragen | niedrig | Ja — App startet, Keys lösen auf (`tr()` gibt sonst den Key zurück) |
| 2 | Default-Paletten | `COLOR_ROLES` + `THEME_PALETTES` (9 Themes × Rollen-Hex) in `dark_theme.py`; reine Daten, noch ohne Verdrahtung | niedrig | Ja — Import-Test, `default_palette(name)` per REPL prüfbar |
| 3 | Override-fähiges `load_theme` | `load_theme(name, overrides=None)`: Hex-Such-/Ersetz-Logik; `overrides=None` → identisch zu heute | mittel | Ja — Rückwärtskompatibilität: alte Aufrufer unverändert; `load_theme(t, {…})` liefert ersetzten String |
| 4 | Zentrale `apply_theme()` + Start | `apply_theme(target, name, overrides)`; `mainwindow.py:149` darauf umstellen, Overrides aus QSettings laden | mittel | Ja — `./restart.sh`: Start-Theme + Icons weiterhin korrekt |
| 5 | UI: GroupBox "Theme-Farben" | Neue GroupBox mit Zeilen (Label + Swatch via `QPalette` + "Ändern…"); Swatches zeigen aktuelle Palette | mittel | Ja — Tab zeigt Sektion, Swatches korrekt gefärbt |
| 6 | Picker + Live-Preview | `QColorDialog`-Import, `_on_pick_color(role)`, Live-Preview via `apply_theme(app, …)` | mittel | Ja — Farbe ändern → sofortige Vorschau |
| 7 | Reset-Button aktivieren | `_disabled(...)` an Zeile 234 entfernen, `clicked.connect`, `_on_reset_colors()` | mittel | Ja — Reset stellt Theme-Defaults wieder her |
| 8 | Persistenz + Abbrechen + Theme-Wechsel | `accept()` speichert Overrides pro Theme; `reject()` revertet auch Overrides; `_on_theme_changed` handhabt Overrides | hoch | Ja — OK→Neustart persistent; Abbrechen revertet; Theme-Wechsel sauber |

---

## 3. Ist-Zustand im Code (NUR verifizierte Anker)

### Theme-System — `anvil/styles/dark_theme.py`

| Zeile | Beschreibung |
|---|---|
| 11 | `_DEFAULT_THEME = "Paper Dark"` |
| 19-24 | `list_themes()` — liest `*.qss`-Stems aus `anvil/styles/` |
| 27-42 | `load_theme(name)` — lädt QSS-Text, ersetzt nur relative `url("./` durch absolute Pfade. **Keine Variablen/Platzhalter-Ersetzung.** |
| 45-47 | `default_theme()` → `"Paper Dark"` |
| 50-52 | `get_stylesheet()` — Backward-Compat-Wrapper auf `load_theme(_DEFAULT_THEME)` |

`anvil/styles/__init__.py` (3 Zeilen): exportiert **nur** `get_stylesheet`.

**Kritisch (verifiziert):** Die 9 QSS-Dateien enthalten **hardcoded Hex-Farben**. Es gibt
**keine** Variablen-/Token-Schicht. `load_theme()` macht nur die URL-Pfad-Ersetzung.

**Farb-Rollen pro Theme** (verifiziert per Hex-Frequenz an `Paper Dark.qss`):
`#141414` (Listen-/dunkler Hintergrund ×28), `#242424` (Haupt-Hintergrund ×26),
`#3d3d3d` (Hover ×22), `#006868` (Akzent/Selection ×19), `#d3d3d3` (Text ×7),
`#808080` (disabled-Text ×2). Die 9 Themes folgen demselben Muster mit anderen Werten.
Theme-Liste (verifiziert): `1809 Dark Mode`, `Catppuccin Mocha`, `Cyberpunk`, `Dracula`,
`Gruvbox Dark`, `Nord`, `One Dark`, `Paper Dark`, `Solarized Dark`.

### Theme-Anwendung (Inkonsistenz Start vs. Preview)

| Datei | Zeile | Beschreibung |
|---|---|---|
| `anvil/main.py` | 64 | `app = QApplication(sys.argv)` — **kein** globales `app.setStyleSheet()` beim Start |
| `anvil/main.py` | 76-77 | `IconProxyStyle` wird gesetzt (`app.setStyle(...)`) |
| `anvil/mainwindow.py` | 41 | importiert `load_theme, default_theme` aus `dark_theme` |
| `anvil/mainwindow.py` | 148 | `saved_theme = self._settings().value("style/theme", default_theme())` |
| `anvil/mainwindow.py` | 149 | Theme auf **`self` (MainWindow)**: `self.setStyleSheet(load_theme(saved_theme))` |
| `anvil/widgets/settings_dialog.py` | 1021-1026 | `_on_theme_changed` → Live-Preview auf **`app` (QApplication)**: `app.setStyleSheet(qss)` |
| `anvil/widgets/settings_dialog.py` | 1148-1158 | `reject()` → revert Preview auf `_previous_theme` (ebenfalls `app.setStyleSheet`) |

→ **Inkonsistenz:** Start setzt auf das MainWindow, Preview auf die QApplication. Visuell
funktioniert beides (App-StyleSheet kaskadiert), ist aber uneinheitlich. Diese Spec
**vereinheitlicht** auf eine zentrale `apply_theme(...)`-Funktion (§4).

### Style-Tab — `anvil/widgets/settings_dialog.py` (verifiziert)

| Zeile | Element | Status |
|---|---|---|
| 73-76 | `def _disabled(w)` — Helper: `setEnabled(False)` **+** `setToolTip(tr("settings.coming_soon"))` | aktiv (Helper) |
| 187-204 | `stil_grp` / `self._stil_combo` (Theme-Auswahl) + "Erkunden"-Button | **funktioniert** |
| 199 | `self._stil_combo.currentTextChanged.connect(self._on_theme_changed)` | funktioniert (Preview) |
| 205-231 | `farben_grp` / `color_table` (`QTableWidget(6, 4)`) — Konflikt-Highlight-Farben | dekorativ |
| 215-222 | `_rows` = 6 Tupel `(tr-Label, bg_hex)` mit den Konflikt-Hex | nur Anzeige |
| 225 | `color_table.setCellWidget(row, 1, _disabled(QPushButton(tr("settings.color_text"))))` | **DEAKTIVIERT** |
| 228 | `bg_item.setBackground(QColor(bg_hex))` | nur Anzeige |
| 234 | `reset_row.addWidget(_disabled(QPushButton(tr("settings.reset_colors"))))` | **DEAKTIVIERT** |

Die Konflikt-Hex-Werte in `_rows` (215-222, verifiziert): `#2d5a2d`, `#5a2020`, `#006868`,
`#5a2020`, `#4a2d5a`, `#1a3a5a` — **`#5a2020` kommt doppelt vor** (Zeile 217 *und* 219).
Grep über `anvil/**/*.py`: Diese Hex werden **nicht** in der Modliste/Rendering als
`setBackground`/`QBrush` verwendet → die Tabelle ist aktuell ohne Wirkung.

### Persistenz / Hilfsfunktionen (verifiziert)
- `_settings()` (Zeile 1000-1002) → `QSettings(~/.config/AnvilOrganizer/AnvilOrganizer.conf, IniFormat)`
- Theme-Name wird bereits gespeichert: `settings.setValue("style/theme", …)` (Zeile 1053, in `accept()` ab 1050)
- `reject()` (1148-1158) revertet Preview auf `_previous_theme`
- Imports (Zeile 10-37): `QColor, QFont` (Zeile 36) und `QSettings` (Zeile 37) vorhanden;
  **`QColorDialog` ist NICHT importiert** (muss ergänzt werden)
- `tr` / `Translator` werden in **Zeile 43** importiert (`from anvil.core.translator import Translator, tr`)
- Locale-JSON: `settings`-Objekt ist **verschachtelt** (nested dict); Keys liegen unter
  `settings.*` (verifiziert: `settings.colors` = "Farben", `settings.coming_soon` = "Noch
  nicht verfügbar"). Hinweis: einzelne andere Top-Level-Keys sind flach (z. B. `label.filter`),
  die hier relevanten `settings.*`-Keys sind jedoch genestet.

---

## 4. Lösung / Ansatz

**Leitprinzip (Projektregel):** KEIN `setStyleSheet()` pro Widget. Stattdessen eine
zentrale **Theme-Variablen-Schicht**: Benutzer-Overrides werden in das geladene
QSS hineingerechnet, und das fertige QSS wird **einmal** zentral gesetzt.

### 4.1 Theme-Override-Schicht in `dark_theme.py`

Pro Theme wird eine kleine Menge **Farbrollen** definiert, die der User überschreiben darf.
Da die QSS-Dateien hardcoded Hex-Werte haben (keine Tokens), nutzen wir den robusten
Ansatz: **Such-/Ersetz-Mapping** der Default-Rollen-Hex auf die Override-Hex.

Neue Funktionen in `anvil/styles/dark_theme.py`:

```
COLOR_ROLES = ["background", "text", "accent", "list_background", "hover", "disabled_text"]

def default_palette(theme_name) -> dict[str, str]:
    # Liefert die Default-Rollenfarben des Themes aus THEME_PALETTES als {role: "#RRGGBB"}.

def load_theme(name, overrides: dict[str, str] | None = None) -> str:
    # Lädt QSS wie bisher (url-Ersetzung) UND ersetzt — falls overrides gesetzt —
    # jeden Default-Rollen-Hex case-insensitiv durch den Override-Hex.
    # overrides=None / leeres dict → unverändertes Default-Theme (Rückwärtskompatibilität).
```

- `THEME_PALETTES`: explizites Dict `{theme_name: {role: default_hex}}` für die 9 Themes
  (verlässlicher als Heuristik; einmalig aus den `.qss` per Hex-Frequenz extrahiert, siehe §6).
- Ersetzung: `content.replace(default_hex, override_hex)`, beide Schreibweisen
  (`#abc123`/`#ABC123`) abdecken — nur für die definierten Rollen, nicht blind alle Hex.

### 4.2 Zentrale Anwendung — `apply_theme()`

```
def apply_theme(target, theme_name, overrides=None):
    qss = load_theme(theme_name, overrides)
    target.setStyleSheet(qss)   # target = QApplication ODER MainWindow
```

- `mainwindow.py:149` → nutzt `apply_theme(self, saved_theme, overrides)` mit gespeicherten
  Overrides (aus QSettings).
- `settings_dialog._on_theme_changed` / Preview → nutzt `apply_theme(app, …)`.

### 4.3 UI im Style-Tab

Die **Konflikt-Farbtabelle bleibt** unverändert (Phase 2). Neu kommt eine **zweite
GroupBox "Theme-Farben"** mit einer Zeile pro `COLOR_ROLE`:

- Label (tr-Key) + Farb-Swatch (`QFrame`, Hintergrund via `QPalette`/`setAutoFillBackground`,
  **NICHT** `setStyleSheet`) + Button "Ändern…".
- Klick → `QColorDialog.getColor(initial, self, title)`.
- Bei gültiger Auswahl: Override im internen Dict `self._color_overrides[role] = hex`
  speichern, Swatch aktualisieren, **Live-Preview** via `apply_theme(app, theme, overrides)`.
- **Reset-Button** (bisher disabled, Zeile 234): leert `self._color_overrides`, setzt
  Swatches auf `default_palette(theme)`, Preview zurück auf reines Theme.
- Theme-Wechsel im Combo: Overrides **verwerfen** + Swatches auf neue Defaults (offene Frage 1).

**Swatch ohne setStyleSheet:** `QFrame` + `setAutoFillBackground(True)` +
`palette.setColor(QPalette.Window, QColor(hex))` + `setPalette(...)`.

### 4.4 Persistenz (QSettings)

- Pro Theme getrennt: Key-Schema `style/overrides/<theme>/<role> = "#RRGGBB"`.
- `accept()` (ab 1050): `self._color_overrides` für das aktuelle Theme nach QSettings schreiben.
- Start (`mainwindow:148-149`): Overrides des gespeicherten Themes laden → `apply_theme`.
- Reset: `settings.remove("style/overrides/<theme>")`.
- `reject()` (1148-1158) erweitern: auch Override-Preview auf gespeicherten Zustand zurück.

### 4.5 Phase 2 / Folge-Issue (NICHT in dieser Spec)
- Konflikt-Highlight-Farbtabelle an die echte Modliste-Konfliktdarstellung koppeln
  (Brushes in der Modliste). Aktuell ungenutzt → separates Issue.

---

## 5. Betroffene Dateien

| Datei | Art der Änderung |
|---|---|
| `anvil/styles/dark_theme.py` | `COLOR_ROLES`, `THEME_PALETTES`, `default_palette()`, `load_theme(overrides=…)`, `apply_theme()` ergänzen |
| `anvil/styles/__init__.py` | ggf. `apply_theme`/`default_palette` re-exportieren |
| `anvil/widgets/settings_dialog.py` | GroupBox "Theme-Farben"; Reset-Button (Z. 234) aktivieren; `_color_overrides`-State; `_on_pick_color`, `_on_reset_colors`; `accept()`/`reject()`/`_on_theme_changed` anpassen; `QColorDialog`-Import |
| `anvil/mainwindow.py` | Zeile 148-149: `apply_theme(self, …, overrides)` statt direktem `setStyleSheet`; Overrides aus QSettings laden |
| `anvil/locales/{de,en,es,fr,it,pt,ru}.json` (7 Dateien) | neue tr-Keys (§7) |

---

## 6. Umsetzungsschritte (folgt dem Phasen-Rückgrat §2)

1. **i18n zuerst (Phase 1):** 3 neue Keys + 6 Rollen-Labels in alle 7 Locale-JSONs unter
   `settings.*` (§7). App startet, Keys lösen auf.
2. **Default-Paletten (Phase 2):** Aus jeder der 9 `.qss`-Dateien die Rollen-Hex per
   Hex-Frequenz ermitteln und als `THEME_PALETTES` in `dark_theme.py` hinterlegen;
   `COLOR_ROLES` + `default_palette()` ergänzen. **Vor Implementierung prüfen, dass die 6
   Rollen-Hex pro Theme paarweise verschieden sind** (sonst trifft ein Override mehrere
   Rollen — Rolle für das Theme weglassen oder gezielter ersetzen).
3. **`load_theme(name, overrides=None)` (Phase 3):** Override-Ersetzung; ohne `overrides`
   identisches Verhalten wie heute (Rückwärtskompatibilität — bestehende Aufrufer
   `mainwindow:149`, `settings_dialog:1023/1151`, `get_stylesheet`).
4. **`apply_theme()` + Start (Phase 4):** `apply_theme(target, name, overrides=None)`;
   `mainwindow.py:148-149` darauf umstellen, Overrides aus QSettings laden.
5. **UI-State + GroupBox (Phase 5):** `self._color_overrides: dict[str,str]` aus QSettings
   für das aktuelle Theme initialisieren; GroupBox "Theme-Farben" (Label + Swatch via
   `QPalette` + "Ändern…").
6. **Picker + Preview (Phase 6):** `QColorDialog` importieren; `_on_pick_color(role)` →
   Live-Preview via `apply_theme(app, …)`.
7. **Reset aktivieren (Phase 7):** Zeile 234 `_disabled(...)` entfernen, `clicked.connect`,
   `_on_reset_colors()`.
8. **Persistenz/Abbrechen/Theme-Wechsel (Phase 8):** `accept()` speichern, `reject()`
   Preview+Overrides revert, `_on_theme_changed` Overrides handhaben.
9. **Test:** `./restart.sh`, Log auf Tracebacks/NameError/ImportError prüfen; Farbe ändern →
   Live-Preview; Reset → Default; OK → Neustart → Persistenz; Abbrechen → revert.

---

## 7. i18n (tr-Keys, 7 Locales)

Locales: `anvil/locales/{de,en,es,fr,it,pt,ru}.json` (verschachtelt, unter `settings`).
**Bereits vorhanden (verifiziert):** `settings.colors` ("Farben"), `settings.reset_colors`
("Farben zurücksetzen"), `settings.color_text`, `settings.color_text_button`,
`settings.color_background`, `settings.color_description`, `settings.color_icons`,
`settings.tab_style`, `settings.coming_soon`. **Neu** benötigt:

| tr-Key | de (Beispiel) |
|---|---|
| `settings.theme_colors` | "Theme-Farben" |
| `settings.color_role_background` | "Hintergrund" |
| `settings.color_role_text` | "Text" |
| `settings.color_role_accent` | "Akzent" |
| `settings.color_role_list_background` | "Listen-Hintergrund" |
| `settings.color_role_hover` | "Hover" |
| `settings.color_role_disabled_text` | "Deaktivierter Text" |
| `settings.color_change` | "Ändern…" |
| `settings.color_pick_title` | "Farbe wählen" |
| `settings.colors_reset_done` | "Farben auf Theme-Standard zurückgesetzt." |

Alle Keys in **allen 7** Sprachen eintragen (de, en, es, fr, it, pt, ru). Bei Unsicherheit
einen sinnvollen Wert pro Sprache setzen (Translator gibt sonst den rohen Key zurück).

---

## 8. Akzeptanzkriterien

- [ ] Style-Tab zeigt eine neue Sektion "Theme-Farben" mit je einem Eintrag pro Rolle
      (Hintergrund, Text, Akzent, Listen-Hintergrund, Hover, deaktivierter Text).
- [ ] Jeder Eintrag hat einen Farb-Swatch (zeigt aktuelle Farbe) + "Ändern…"-Button.
- [ ] Klick auf "Ändern…" öffnet `QColorDialog` mit der aktuellen Farbe vorausgewählt.
- [ ] Farbauswahl aktualisiert Swatch **und** zeigt sofortige Live-Vorschau (Echtzeit, ohne Neustart).
- [ ] "Farben zurücksetzen" ist **aktiviert** (Zeile 234 nicht mehr `_disabled`) und stellt
      die Default-Farben des aktuell gewählten Themes wieder her (UI + Preview).
- [ ] OK speichert Overrides pro Theme in QSettings (`style/overrides/<theme>/<role>`); nach
      Neustart sind sie aktiv.
- [ ] Abbrechen verwirft Overrides **und** Theme-Preview (zurück zum vorherigen Stand).
- [ ] Theme-Wechsel im Combo handhabt Overrides definiert (verwerfen → Defaults des neuen Themes).
- [ ] **KEIN** per-Widget `setStyleSheet()` in neuem Code (Swatch via `QPalette`); QSS
      wird zentral via `apply_theme()` gesetzt.
- [ ] Ohne gespeicherte Overrides verhält sich `load_theme()` exakt wie zuvor
      (Rückwärtskompatibilität — bestehende Aufrufer unverändert lauffähig).
- [ ] `apply_theme()` vereinheitlicht Start (MainWindow) und Preview (QApplication); Start-Theme
      + Icons (`IconProxyStyle`) bleiben korrekt.
- [ ] Alle neuen tr-Keys in allen 7 Locale-Dateien vorhanden.
- [ ] `python -m py_compile` der geänderten Dateien fehlerfrei; `./restart.sh` startet ohne
      Traceback/NameError/ImportError.

---

## 9. Aufwand / Risiko

**Aufwand:** Mittel (~1 Arbeitstag).
- `dark_theme.py`-Erweiterung + `THEME_PALETTES` extrahieren: ~2-3 h (Sorgfalt beim Hex-Mapping).
- Settings-Dialog-UI + Handler: ~3 h.
- mainwindow-Vereinheitlichung + Persistenz: ~1 h.
- i18n (7 Locales, 10 Keys): ~1 h.

**Risiko:** Mittel.
- **Hex-Ersetzung als Override-Mechanismus** ist robust, solange eine Rollenfarbe nicht
  zufällig identisch mit einer anderen ist (z. B. Akzent == Text). Bei Kollision würde ein
  Override beide treffen. → Pro Theme prüfen, dass die 6 Rollen-Hex paarweise verschieden
  sind; bei Kollision die Rolle weglassen oder gezielter ersetzen. (Bei `Paper Dark`
  verifiziert paarweise verschieden: `#141414/#242424/#3d3d3d/#006868/#d3d3d3/#808080`.)
- **Vereinheitlichung Start vs. Preview** (`self` vs. `app`) berührt funktionierenden
  Code (mainwindow:149) → sorgfältig testen, dass Start-Theme + Icons weiter korrekt sind.
- **Konflikt-Highlight-Tabelle bleibt ungenutzt** (Phase 2) — im Issue ggf. kommentieren,
  dass die generischen Theme-Farben umgesetzt sind und die Konflikt-Farb-Kopplung als
  Folge-Issue geführt wird.

**Offene Fragen an Marc:**
1. Theme-Wechsel bei aktiven Overrides: Overrides **verwerfen** (Vorschlag) oder pro Theme
   getrennt behalten und beim Zurückwechseln wiederherstellen?
2. Soll die bestehende **Konflikt-Highlight-Farbtabelle** in diesem Schritt auch
   persistent/zurücksetzbar werden (nur Speicherung, noch keine Modliste-Kopplung), oder
   komplett auf Phase 2 verschieben?
3. Genügen die 6 vorgeschlagenen Farbrollen, oder sollen weitere anpassbar sein (z. B.
   Border, Selection-Text)?
