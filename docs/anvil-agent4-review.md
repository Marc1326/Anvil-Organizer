# QA-Bericht 4 — Presets-Bereich: Übersetzungen und Oberfläche

Datum: 2026-08-12
Geprüft: nicht-committete Änderungen (Presets-Bereich)

## Ergebnis: NEEDS FIXES

Locale-Arbeit selbst ist einwandfrei (Schlüssel vollständig in 7 Sprachen,
Platzhalter korrekt, JSON valide, Formatierung unverändert, Stil passt zu den
Nachbar-Einträgen). Die Befunde betreffen die Anbindung an die Oberfläche.

## HIGH

### H1 — Bereichstitel läuft nicht durch tr(), Plural hartkodiert
`anvil/mainwindow.py` — `titel = f"{arten[0].name}s" if len(arten) == 1 else tr("label.presets")`

`arten[0].name` ist der Plugin-String `"ACU-Preset"`. Der Anwender sieht in allen
7 Sprachen „ACU-Presets", das angehängte `s` ist deutsch/englische Pluralbildung
und in fr/it/pt/ru falsch. Da nur Cyberpunk Presets kennt und genau eine Art
liefert, greift der `else`-Zweig nie — `label.presets` ist praktisch unsichtbar.

Präzedenzfall mit demselben Fehler: `tr("label.type_framework") + "s"` in
`mod_list.py`.

### H2 — Spaltenbreiten des Presets-Baums werden nie wiederhergestellt
`restore_preset_widths()` existiert, wird aber nirgends aufgerufen.
`_restore_layout` ruft nur `restore_framework_widths()`. `PersistentHeader`
stellt nichts von selbst her. Folge: gezogene Spalten sind nach Neustart weg.

### H3 — `flush_column_widths()` vergisst `_ph_presets`
Das gedebouncte Schreiben geht beim Schließen verloren. Zusammen mit H2 ist die
Breiten-Persistenz in beide Richtungen tot.

## MEDIUM

### M1 — `apply_theme_metrics()` ignoriert den Presets-Baum
Im modernen Theme werden Mod-Liste und Frameworks auf `Fixed` gesetzt mit einer
`Stretch`-Spalte. Der Presets-Baum bleibt ziehbar und hat keine Füllspalte —
rechts bleibt ein leerer Streifen. Bei Live-Theme-Wechsel passt er sich nicht an.

### M2 — Kontextmenü und Löschdialog sprechen von „Mod"
`_on_preset_context_menu` und `_remove_preset` verwenden `context.remove_mod`,
`dialog.remove_mod_title`, `dialog.remove_mod_single`. Der Bereich existiert
laut eigenem Kommentar gerade deshalb, weil Presets keine Mods sind.

## LOW

- **L1** `splitterMoved` behandelt nur den Framework-Bereich. Der Presets-Baum
  wird beim Zusammenziehen auf wenige Pixel gequetscht statt ausgeblendet.
- **L2** `beschriftung = {"female": …, "male": …}` nutzt Literale statt der
  Konstanten `FEMALE`/`MALE`, die in derselben Datei schon importiert sind.
- **L3** Kleinschreibung der Varianten-Werte — Geschmacksfrage, es gibt
  Präzedenzfälle in beide Richtungen. Kein Fehler.
- **L4** Kein Gegenstück zu `fw_all_installed` („alle aktiv"). Nur wenn gewünscht.

## INFO

- Gekürzte Namen ohne Tooltip: zwei Presets gleichen Namens in verschiedenen
  Varianten stehen zweimal als „Grace" da, unterscheidbar nur über die Spalte.
  Der Framework-Baum setzt allerdings ebenfalls keine Tooltips.
- ARCHITEKTUR.md beschreibt nur den Frameworks-Bereich. Der Presets-Bereich und
  die Regel „bleibt in `_current_mod_entries`, nur aus der Anzeige gefiltert"
  fehlen dort.

## Geprüft und in Ordnung

- Alle 10 `tr()`-Aufrufe im Diff lösen gegen `de.json` auf.
- `label`-Block hat in allen 7 Dateien 100 Schlüssel in identischer Reihenfolge.
- `set_title` existiert auf `CollapsibleSectionBar`.
- QSettings-Schlüssel `"presets"` kollidiert mit nichts.
- Der Splitter wird nicht persistiert — 2→3 Panes verursacht keine Migration.
- Delegate und Header liegen als Instanzvariablen, keine GC-Gefahr.
