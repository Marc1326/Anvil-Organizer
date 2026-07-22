# Re-Review R2 — Agent 2: Härtungs-Commit 5718e51

**Datum:** 2026-06-29
**Scope:** NUR Commit 5718e51 (`anvil/mainwindow.py`), switch_instance + Startup-Vereinfachung
**Modus:** Nur lesen, kein Code geändert.

---

## Verifikation der 5 Punkte

### 1. Profitieren ALLE Aufrufer von switch_instance vom Guard?
**JA — vollständig.** Der try/except sitzt jetzt IN switch_instance (Zeile 1116–1133),
umschließt den `_apply_instance(instance_name)`-Aufruf. Damit ist jeder externe Aufrufer
geschützt, egal über welchen Pfad:

- `mainwindow.py:616` `_on_manage_instances` → geschützt
- `mainwindow.py:777` `_on_settings` (Pfad-Reload nach Settings) → geschützt
- `mainwindow.py:999` `_check_first_start` (frisch erstellte Instanz via Wizard) → geschützt
- `mainwindow.py:1005` `_check_first_start` (Startup, current instance) → geschützt
- `anvil/widgets/toolbar.py:53` `_open_instance_manager` → geschützt (zusätzlicher Aufrufer,
  in Runde 1 nicht explizit erwähnt, aber durch den verlagerten Guard ebenfalls abgedeckt)

Der Startup-Block (1002–1007) wurde korrekt von seinem lokalen try/except befreit, da der
Schutz nun zentral in switch_instance liegt. Keine doppelte Fehlerbehandlung.

### 2. Ist das LOW (Traceback) jetzt drin?
**JA.** Zeile 1119 `import traceback`, Zeile 1124–1127 gibt `traceback.format_exc()` per
`print()` aus. Zusätzlich kompakte Meldung ins Log-Panel (Zeile 1120–1123). Damit ist der
volle Stacktrace für Diagnose verfügbar — das Runde-1-LOW ist erledigt.

### 3. except ruft self._apply_instance("") — sauber bzgl. Scope/Signalfluss, keine Propagation?
**Sauber.** Bewertung im Detail:
- `_apply_instance("")` → `load_instance("")` liefert leeres/None-`data` → der frühe
  Return-Zweig (Zeile 1149–1173) greift: voller "Kein Spiel"-Reset, State-Variablen genullt,
  Toolbar-Actions versteckt, `_status_bar.clear_instance()`. Das ist exakt der gewünschte
  Reset-Zustand.
- Der innere try/except (1129–1132) fängt ab, falls selbst dieser Reset scheitert, mit
  Fallback `_status_bar.clear_instance()`. Robust.
- KEINE Exception-Propagation nach außen: beide Pfade enden ohne re-raise; `return` (1133)
  verhindert, dass `set_current_instance` im Fehlerfall läuft. set_current_instance (1136)
  läuft NUR bei Erfolg — korrekt, verhindert .current auf kaputte Instanz (war der
  ursprüngliche Crash-Loop beim Start).
- Scope: `e` und `traceback` sind lokal im except-Block, kein Leak, keine GC-Falle.

### 4. local `import traceback` im except — ok?
**OK.** `traceback` ist Stdlib, der lokale Import im Fehlerpfad ist gängig und vermeidet
einen Top-Level-Import nur für den seltenen Fehlerfall. Kein Risiko (kann nicht
fehlschlagen). Stilistisch hätte ein Modul-Level-Import gepasst, aber kein Finding.

### 5. Erwartet ein Aufrufer, dass switch_instance bei Fehler eine Exception WIRFT? Regression?
**NEIN — keine Regression.** Geprüft:
- `switch_instance` hat Rückgabetyp `-> None` und gab nie einen sinnvollen Wert zurück.
- KEIN Aufrufer (616, 777, 999, 1005, toolbar.py:53) umschließt `switch_instance` mit
  try/except oder wertet einen Rückgabewert/Erfolg aus. Alle rufen es als
  Fire-and-Forget auf.
- Der EINZIGE Aufrufer, der vorher überhaupt eine Exception erwartete, war der alte
  Startup-Block (entfernt in genau diesem Diff) — dessen Logik (Log + clear_instance)
  ist jetzt im zentralen Guard nachgebildet (sogar erweitert um vollständigen Reset).
- Vorher konnte switch_instance an den interaktiven Stellen (616/777/999/toolbar) bei
  einer kaputten Instanz die App abschießen — das war der gemeldete Bug. Jetzt nicht mehr.
  Verhaltensänderung ist die beabsichtigte Härtung, keine ungewollte Regression.

---

## Architektur-/MO2-Check (Kurz)
Der Diff berührt KEINE Mod-Verwaltung, Deploy, modlist.txt, Installation, Separatoren oder
active_mods.json. Es ist reines UI-/Lifecycle-Error-Handling im MainWindow. Die 7
Architektur-Schutzregeln sind nicht betroffen. Kein MO2-Pendant relevant (MO2 hat kein
äquivalentes Instanz-Switching-Error-Handling; Anvil-spezifischer Lifecycle).

## Nebenbeobachtung (kein Finding, war schon vor dem Commit so)
- Doppelter `set_current_instance`-Aufruf für die Wizard-Erstinstanz: instance_wizard.py:633
  setzt current bei der ersten Instanz, danach setzt switch_instance(1136) es erneut.
  Idempotent, harmlos, NICHT durch diesen Diff verursacht → kein Finding.
- Der zusätzliche Reset in `_teardown_current_instance` (1101–1104: `_current_plugin`,
  `_current_game_path`, `_mod_index`) ist Teil des Diffs und konsistent mit dem
  `_apply_instance("")`-Reset. Korrekt, beseitigt halb-geladenen State sauber.

---

## ERGEBNIS

**ZERO FINDINGS.**

Begründung: Alle 5 Prüfpunkte sind sauber erfüllt. Der Guard schützt nachweislich alle
5 Aufrufer (inkl. toolbar.py:53), das Traceback-LOW aus Runde 1 ist behoben, der
except-Pfad ist korrekt gekapselt (kein Propagation, set_current_instance nur bei Erfolg),
der lokale traceback-Import ist unbedenklich, und kein Aufrufer erwartet eine geworfene
Exception → keine Regression. py_compile von anvil/mainwindow.py erfolgreich.

**READY FOR COMMIT** (Commit ist bereits gemacht — Re-Review bestätigt ihn).
