# Re-Review R2 — Agent 1 — Commit 5718e51 (switch_instance Härtung)

Datum: 2026-06-29
Scope: NUR Diff 5718e51 in anvil/mainwindow.py (switch_instance + _apply_instance Reset-Zweig).
Modus: nur lesen.

## Verifizierte Punkte

### 1. Ist das MEDIUM aus Runde 1 gelöst? — JA
- Frühere Schwäche: Startup-Guard machte im except nur `clear_instance()` (nur StatusBar-Label),
  kein voller "Kein Spiel"-Reset.
- Jetzt: except in switch_instance ruft `self._apply_instance("")` (mainwindow.py:1130).
- `load_instance("")` (instance_manager.py:270-285) baut `self._base / "" / ".anvil.ini"`
  = `~/.anvil-organizer/instances/.anvil.ini`. Diese Datei existiert real NICHT
  (geprüft: `ls` -> "nicht gefunden"; instances/ enthält nur Instanz-Unterordner).
  -> `ini.is_file()` False -> Rueckgabe `{}` (falsy).
- In `_apply_instance` greift damit `if not data` (mainwindow.py:1149) und fuehrt den
  VOLLEN Reset aus: Titel, GamePanel, clear_mods, alle State-Vars genullt
  (inkl. der in diesem Commit ergaenzten `_current_plugin`, `_current_game_path`,
  `_mod_index` auf mainwindow.py:1157-1159), alle Toolbar-Actions versteckt,
  Stack zurueck auf ModListView, active_count Update, StatusBar clear, ReShade disabled.
- FAZIT: MEDIUM ist sauber geloest — voller Reset statt nur Label.

### 2. Endlosrekursion / Reentrancy? — NEIN
- Der except ruft `_apply_instance("")`. Dieser Aufruf landet zwingend im
  `if not data`-Zweig (1149-1173), der mit `return` endet und KEIN `_apply_instance`
  und KEIN `switch_instance` erneut aufruft (per grep im Bereich 1149-1173 bestaetigt:
  "KEIN rekursiver Aufruf").
- Damit kein Stack-Wachstum, keine Schleife. Maximal eine zusaetzliche Aufrufebene.

### 3. set_current_instance bei Fehler zuverlaessig uebersprungen? — JA
- `set_current_instance` (mainwindow.py:1136) steht NACH dem try/except-Block.
- Im Fehlerpfad endet der except mit `return` (mainwindow.py:1133) -> Zeile 1136 wird
  nicht erreicht. `.current` zeigt also nicht auf die kaputte Instanz.
- Das ist exakt das gewuenschte Verhalten (Kommentar 1134-1135 deckt sich).

### 4. Neuer Bug / Edge Case durch diesen Diff? — KEINER gefunden
Geprueft:
- Innerer Fallback `clear_instance()` (1131-1132): setzt nur ein Label
  (status_bar.py:37-39), kann nicht werfen. Robust, selbst wenn `_apply_instance("")`
  teilweise durchlief und dann warf.
- Toolbar-Attribute (deploy_sep/action, proton_action, merger_*, loot_*) werden im
  Toolbar-Bau gesetzt (toolbar.py:134-171), existieren bevor switch_instance je
  aufrufbar ist -> kein AttributeError im Reset-Zweig.
- `_teardown_current_instance()` wird beim inneren `_apply_instance("")` NICHT erneut
  aufgerufen. Das ist unkritisch: der `if not data`-Zweig setzt nur Zustaende
  idempotent zurueck und ruft `clear_mods()`, ist nicht von frischem Teardown abhaengig.
- `import traceback` lokal im except (1119): unschoen aber funktional korrekt, kein Bug.
- `print(...)` (1124-1127) zusaetzlich zum Log-Panel: bewusst (Stderr-Traceback fuer
  AppImage-Debugging), kein Fehler.
- Startup-Pfad (start(), 999-1008 im Diff): try/except dort entfernt, weil
  switch_instance jetzt selbst kapselt — Verhalten fuer alle Aufrufer einheitlich,
  korrekt zentralisiert.

## Hinweis (kein Finding, nur Vollstaendigkeit)
- Theoretischer Edge Case: legte ein Nutzer manuell `instances/.anvil.ini` an, wuerde
  `load_instance("")` ein nicht-leeres dict liefern und der Reset wuerde in den
  Voll-Lade-Zweig laufen statt in den Reset-Zweig. Das ist kein durch diesen Commit
  eingefuehrter Regressionspfad (`_apply_instance("")` / leerer Name war auch vorher
  schon der Reset-Trigger, siehe start()-else-Zweig). Praktisch irrelevant, kein Fix noetig.

## Ergebnis
ZERO FINDINGS.
Begruendung: MEDIUM aus R1 ist behoben (voller Reset via _apply_instance("")),
keine Rekursion (Reset-Zweig ruft sich nicht selbst, endet mit return),
set_current_instance wird im Fehlerfall sicher per return uebersprungen,
und der Diff fuehrt keinen neuen Bug/Edge Case ein.

READY FOR COMMIT.
