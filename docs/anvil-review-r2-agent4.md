# QA Re-Review (Runde 2) — Instanz-Pfad-Crash Härtung

Datum: 2026-06-29
Scope: `git diff 53f3435 -- anvil/` (38ba7ba Crash-Abfang + 5718e51 Härtung), Schwerpunkt 5718e51
Reviewer: qa-pruefer Agent 4 (Re-Review, fokussiert)

## Gelesene Referenzen
- docs/anvil-bugfix-instance-pfad-crash.md (Plan + Akzeptanzkriterien)
- anvil/mainwindow.py (switch_instance 1106-1136, _apply_instance 1138-1329, _teardown 1037-1104, _check_first_start 980-1012)
- anvil/core/download_manager.py (set_downloads_dir)
- anvil/core/instance_manager.py (load_instance 270-285)
- anvil/widgets/toast.py (Toast.__init__)
- anvil/main.py (Startup-Reihenfolge)
- CLAUDE.md (Architektur-Regeln)

---

## Frage 1 — LOW-MEDIUM-Finding aus Runde 1 vollständig gelöst?

**JA — vollständig gelöst.**

Runde-1-Finding war: Startup-Guard ohne vollen Reset + nur am Startup.

- **Alle Aufrufer geschützt:** Der try/except sitzt jetzt INNERHALB von
  `switch_instance` (mainwindow.py:1116-1133). Damit sind ALLE Aufrufer abgedeckt:
  - :616 `_on_manage_instances` (Instanz-Wechsel über Dialog)
  - :777 `_on_nexus_settings` (Reload nach Settings-Änderung)
  - :999 Wizard-Pfad (neue Instanz)
  - :1005 Startup (`_check_first_start`)
  Der frühere, nur am Startup wirksame Guard (:1003-1005 alt) wurde entfernt — korrekt,
  da die Absicherung jetzt zentral in switch_instance liegt.
- **Voller Reset:** Im except wird `_apply_instance("")` aufgerufen
  (mainwindow.py:1130). `load_instance("")` liefert `{}` (instance_manager.py:280-281,
  da `base/""/".anvil.ini"` kein File ist) → der vollständige "Kein Spiel"-Reset-Zweig
  `if not data:` (mainwindow.py:1149-1173) läuft sauber durch: Titel, Game-Panel,
  Mod-Liste, alle `_current_*`-Member, Toolbar-Actions, Statusbar. Das ist deutlich
  mehr als der alte Startup-Guard (nur `_status_bar.clear_instance()`).
- **Doppelte Absicherung:** Schlägt sogar `_apply_instance("")` fehl, fällt es auf
  `_status_bar.clear_instance()` zurück (mainwindow.py:1131-1132). Kein endlos-rekursiver
  Crash möglich.
- **Traceback ins Log:** `print(traceback.format_exc())` (mainwindow.py:1124-1127)
  zusätzlich zur User-Meldung im Log-Panel (:1120-1123).

## Frage 2 — Gesamter Fix löst das gemeldete Problem weiterhin vollständig? Neuer ungeschützter Crashpunkt?

**JA, Crash-Kette weiterhin vollständig abgedeckt. KEIN neuer ungeschützter Crashpunkt.**

Crash-Kette (laut Plan): `_apply_instance` → `set_downloads_dir` → `path.mkdir()` →
PermissionError/OSError → propagiert hoch → App-Crash.

- **Ebene 1 (Wurzel):** download_manager.py:156-162 fängt `OSError` (Oberklasse von
  PermissionError, FileNotFoundError) sauber ab, merkt den Pfad trotzdem, loggt. Damit
  crasht der ursprüngliche Auslöser nicht mehr.
- **Ebene 2 (Catch-all):** Selbst wenn an anderer Stelle in `_apply_instance` eine
  Exception fliegt (z. B. fehlendes Laufwerk bei einem anderen mkdir wie
  profiles_dir.mkdir :1285 oder resolve_path), fängt der neue try/except in
  switch_instance (:1116-1133) ALLES ab (`except Exception`). Härtung ist also
  breiter als nur der mkdir-Fall.
- **Bug B (.current vor Laden):** Reihenfolge ist korrekt umgedreht —
  `set_current_instance` (:1136) wird NUR nach erfolgreichem `_apply_instance` und
  NICHT im except-Pfad erreicht (return :1133 davor). Eine kaputte Instanz wird also
  nie als `.current` persistiert → App startet beim nächsten Mal sauber.

Geprüfte potenzielle neue Crashpunkte durch die Umstrukturierung:
- `_apply_instance("")` im except: durch inneren try/except abgesichert. OK.
- `Toast(self, ...)` bei game_path-missing (:1205): vorbestehend (bereits in 38ba7ba),
  KEINE Regression durch 5718e51. `Toast` ist ein etabliertes Widget; `tr` (:86) und
  `Toast` (:49) korrekt importiert.
- `_log_panel`/`_status_bar` im except-Pfad: beide vor `_check_first_start` (:397)
  initialisiert (:288, :306) → kein AttributeError beim Startup-Fehler.
- Startup-Reihenfolge: `_check_first_start` läuft in `__init__` (:397) VOR
  `w.showMaximized()` (main.py:110). Das betrifft nur die Toast-Position bei noch
  nicht maximiertem Fenster (vorbestehend, kein Crash) — kein durch diesen Commit
  eingeführtes Problem.

## Frage 3 — Architektur-Regeln (CLAUDE.md)

**Eingehalten.**

- **Hardcoded Pfade:** keine. download_manager nimmt den Pfad weiter aus der
  Instanz-Config entgegen; mainwindow nutzt `resolve_path` mit `%INSTANCE_DIR%`.
  Das `/mnt/gamingS` im Plan-Doc ist nur Doku, nicht im Code.
- **setStyleSheet in neuem Widget:** keine neuen Widgets im Diff. Alle setStyleSheet-
  Treffer (mainwindow.py:149, 2653+, 6175; toast.py:26) sind vorbestehend und außerhalb
  des Diffs. Regelkonform.
- **MO2/ModOrganizer-Erwähnung:** keine im geänderten Code.
- **tr()-Keys in allen Locales:** `toast.game_path_missing` in allen 7 Locale-Dateien
  ergänzt (de, en, es, fr, it, pt, ru) — Diff bestätigt alle 7.
- Mod-Verwaltung/Deploy/modlist.txt nicht berührt → 7-Punkte-Mod-Architektur nicht
  betroffen.

## Frage 4 — Akzeptanzkriterien aus docs/anvil-bugfix-instance-pfad-crash.md

- [x] Wechsel auf Instanz mit fehlendem Laufwerk → Warnung statt Crash, App bedienbar.
      → download_manager fängt OSError; switch_instance fängt Catch-all; Toast-Warnung.
- [x] App startet auch wenn `.current` auf kaputte Instanz zeigt.
      → Startup ruft switch_instance (:1005), das den Fehler kapselt und auf
      "Kein Spiel" zurücksetzt.
- [x] Spielpfad in Einstellungen änderbar → Instanz lädt trotzdem (game_path None →
      nur Toast :1204-1205, kein early-return; Instanz wird voll geladen).
- [x] `.current` erst nach erfolgreichem Laden geschrieben (:1136 nach try, return im
      except :1133 davor).
- [x] Neue tr-Keys in allen 7 Locales, kein Roh-Key (Diff bestätigt).
- [x] Kein setStyleSheet in neuen Widgets; keine hardcoded Pfade.
- [ ] `./restart.sh` startet fehlerfrei → NICHT in diesem Read-only-Review ausgeführt
      (kein Laufzeit-Test im Scope). Statische Prüfung: Imports vorhanden
      (traceback lokal importiert :1119, Toast :49, tr :86), Syntax plausibel.
      Empfehlung an den Workflow: `./restart.sh` einmal real bestätigen.

Zuvor offene Härtungspunkte aus Runde 1 (voller Reset + alle Aufrufer) sind erfüllt.

---

## Ergebnis

ZERO FINDINGS.

Begründung: Das LOW-MEDIUM-Finding aus Runde 1 ist vollständig adressiert (zentraler
Guard in switch_instance schützt alle Aufrufer, voller "Kein Spiel"-Reset via
`_apply_instance("")` mit doppelter Absicherung, Traceback ins Log). Die Crash-Kette
ist auf zwei Ebenen abgedeckt (OSError an der Wurzel + Catch-all). Die Umstrukturierung
führt keinen neuen ungeschützten Crashpunkt ein; alle im except verwendeten Member sind
vor dem ersten möglichen Fehler initialisiert. Architektur-Regeln eingehalten,
Akzeptanzkriterien erfüllt — einzig der Laufzeit-Check `./restart.sh` ist außerhalb
dieses Read-only-Reviews und sollte vom Workflow noch real bestätigt werden (kein Bug,
nur nicht im Review-Scope ausgeführt).

READY FOR COMMIT
