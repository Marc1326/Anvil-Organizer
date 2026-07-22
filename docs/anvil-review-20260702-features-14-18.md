# QA Review — Features #14 (Benachrichtigungen) und #18 (Theme-Farben)
Datum: 2026-07-02
Prüfer: qa-pruefer
Commits: e70c157 (Benachrichtigungen), cd1c004 (Theme-Farben anpassbar)

Vor dem Review gelesen: `/home/mob/Projekte/anvil-wiki/dev-notes/ARCHITEKTUR.md`.
MO2-Vergleich: Beide Features (Session-Benachrichtigungen, Theme-Rollenfarben) sind
reine UI/Präsentations-Features ohne MO2-Äquivalent. Sie berühren KEINE Mod-Verwaltung,
kein Deploy, keine modlist.txt, kein active_mods.json, keine .mods/-Struktur, keine
Frameworks. Die 7 Architektur-Regeln sind damit nicht betroffen (keine Verletzung).

## Geprüfte Dateien
- anvil/core/notification_center.py
- anvil/widgets/notification_panel.py
- anvil/widgets/toolbar.py (Glocken-Button)
- anvil/styles/dark_theme.py, anvil/styles/__init__.py
- anvil/widgets/settings_dialog.py (Theme-Farben-Abschnitt)
- anvil/mainwindow.py (Verdrahtung: Zeilen 41, 74, 171-172, 427-432, 565-566, 808, 7355-7386)

## Positiv verifiziert
- Alle 20 verwendeten tr()-Keys in ALLEN 7 Locales (de/en/es/fr/it/pt/ru) vorhanden.
- Alle Dateien py_compile-sauber; keine fehlenden Imports (QFrame, QPixmap, QColorDialog ok).
- Signal-Signaturen passen: download_finished/error = Signal(int,str) → Slots (int,str);
  currentTextChanged(str) → _on_theme_changed(str); clicked(bool) → Lambdas mit checked=False.
- MainWindow._settings() (Z.6101) und SettingsDialog._settings() (Z.1273) nutzen den
  IDENTISCHEN Pfad → gespeicherte Overrides werden beim Start (Z.171-172) korrekt gelesen.
- Feature funktional vollständig: Overrides werden gespeichert UND gelesen UND via
  _apply_overrides → setStyleSheet angewendet (Startup Z.172, nach OK Z.808).
- Kein setStyleSheet() in neuen Widgets: Badge per QPainter, Swatch per QPixmap — bewusst
  und im Code begründet dokumentiert.
- download_manager wird nur EINMAL erzeugt (game_panel.py:384, einzige Zuweisung Z.274),
  daher bleibt die in __init__ verdrahtete Notification-Anbindung über Instanzwechsel gültig
  (kein Stale-Reference-Bug).
- NotificationCenter(self) und NotificationPanel(parent=win) haben Parents → kein GC/Leak;
  Panel nutzt WA_DeleteOnClose.

## Findings

### 1. [MITTEL] Ungespeicherte Farb-Overrides gehen bei Theme-Wechsel im Dialog verloren
- Datei: anvil/widgets/settings_dialog.py:1292-1296 (_on_theme_changed) i.V.m. 219, 1414
- Problem: Ändert der Nutzer Rollenfarben (nur im Speicher `_color_overrides`), wechselt
  dann im Combo das Theme und wieder zurück, überschreibt `_on_theme_changed` die
  in-memory Overrides via `load_overrides(...)`. Die noch nicht mit OK bestätigten
  Änderungen des ersten Themes sind danach unwiderruflich weg — auch nach Rückkehr zum
  Theme und OK. Stiller Datenverlust in der Bearbeitungssitzung.
- Fix: In-Memory-Edits pro Theme in einem Dict cachen (z.B. `{theme: overrides}`) und beim
  Zurückwechseln daraus wiederherstellen, statt bei jedem Wechsel frisch aus QSettings zu laden.

### 2. [NIEDRIG] Dauerhaft deaktivierter Menüeintrag "Benachrichtigungen..." (tote UI)
- Datei: anvil/mainwindow.py:565-566
- Problem: Im Ansicht-Menü liegt `menu.notifications` mit `setEnabled(False)`. Das reale
  Feature ist der Glocken-Button in der Toolbar; der Menüeintrag tut nie etwas und wirkt
  wie ein unfertiger Platzhalter.
- Fix: Entweder mit dem Öffnen des Notification-Panels verdrahten oder entfernen.

### 3. [NIEDRIG] Panel aktualisiert sich nicht bei neuen Meldungen während es offen ist
- Datei: anvil/widgets/notification_panel.py:67-95, 124-131
- Problem: NotificationPanel verbindet sich nicht mit `center.changed`. Trifft während des
  geöffneten Panels eine neue Meldung ein (z.B. Download fertig), bleibt die Liste veraltet.
- Fix: `center.changed` mit `_refresh` verbinden (und beim Schließen trennen, da
  WA_DeleteOnClose).

### 4. [NIEDRIG] NotificationCenter wächst unbegrenzt
- Datei: anvil/core/notification_center.py:34-42 (add)
- Problem: Kein Limit für `_items`. In einer langen Sitzung mit vielen Downloads/Update-
  Checks wächst die Liste unbeschränkt (geringer, aber unnötiger Speicherverbrauch).
- Fix: Auf sinnvolle Obergrenze deckeln (z.B. letzte 100 Einträge behalten).

### 5. [INFO] _apply_overrides ersetzt nur exakte Default-Hex-Tokens
- Datei: anvil/styles/dark_theme.py:101-124
- Problem/Anmerkung: Es wird ausschließlich der exakte Rollen-Hex ersetzt; abgeleitete
  Schattierungen (Hover-/Border-Gradienten) bleiben unverändert, und derselbe Hex an anderer
  Stelle im QSS würde mit-ersetzt. Verlässt sich zudem darauf, dass Palettenfarben paarweise
  verschieden sind. Beides ist im Code als bewusste Einschränkung dokumentiert — kein Bug,
  nur zur Kenntnis. Der Single-Pass-Ersatz per Alternation ist korrekt und verhindert
  Ketten-Ersetzungen; das Negative-Lookahead schützt vor Teiltreffern bei 8-stelligen Hex.

## Ergebnis
NEEDS FIXES (nur MITTEL/NIEDRIG — keine CRITICAL/HIGH, kein Crash-Risiko,
keine Architektur-Regel-Verletzung). Finding #1 sollte vor Release behoben werden;
#2-#4 sind Politur.
