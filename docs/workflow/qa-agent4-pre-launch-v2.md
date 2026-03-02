# QA Agent 4 — Regressions-Check + Akzeptanzkriterien
Datum: 2026-03-02

---

## Teil A: Regressions-Check

- [x] 1. closeEvent: `silent_purge()` OHNE skip_ba2 ✅ — Zeile 3128: `self._game_panel.silent_purge()` wird ohne Parameter aufgerufen, d.h. `skip_ba2=False` (Default). Voller BA2-Cleanup wird durchgefuehrt.

- [x] 2. Profil-Wechsel: `silent_purge()` OHNE skip_ba2 ✅ — Zeile 2272: `_on_profile_changed()` ruft `self._game_panel.silent_purge()` ohne Parameter auf. Voller BA2-Cleanup bei Profilwechsel.

- [x] 3. Instanz-Wechsel: `silent_purge()` OHNE skip_ba2 ✅ — Zeile 829: `_apply_instance()` ruft `self._game_panel.silent_purge()` ohne Parameter auf. Voller BA2-Cleanup bei Instanzwechsel.

- [x] 4. Keine neuen Imports ✅ — `git diff` zeigt keine neuen import-Statements in beiden Dateien. `pre_launch_deploy = Signal()` nutzt den bereits importierten `Signal`-Typ. `Qt.ConnectionType.UniqueConnection` nutzt den bereits importierten `Qt`-Typ.

- [x] 5. `python -m py_compile anvil/widgets/game_panel.py` ✅ — Kompilierung erfolgreich (Output: "OK")

- [x] 6. `python -m py_compile anvil/mainwindow.py` ✅ — Kompilierung erfolgreich (Output: "OK")

- [x] 7. Nur 2 Dateien veraendert ✅ — `git diff --stat` zeigt exakt:
  - `anvil/mainwindow.py | 25 ++++++----`
  - `anvil/widgets/game_panel.py | 113 ++++++++++++++++++++++++++------------------`
  - Keine weiteren Dateien.

**Regressions-Check: 7/7 Punkte**

---

## Teil B: Akzeptanzkriterien (20 Punkte)

### Launch-Pfade (Kriterien 1-3)

- [x] 1. GOG/Epic Pre-Launch Deploy ✅ — Code-Pfad korrekt:
  - `game_panel.py` Z.765: `self.pre_launch_deploy.emit()` wird VOR dem Non-Steam-Pfad aufgerufen (Z.804: `self.start_requested.emit(...)`)
  - `mainwindow.py` Z.1119-1127: `_pre_launch_deploy()` gibt "[PURGE] Pre-launch purge" + "[DEPLOY] Pre-launch full deploy (with BA2)" aus und ruft `silent_purge()` + `silent_deploy()` auf
  - Signal ist verbunden: Z.281-283 via `UniqueConnection`

- [x] 2. Steam-Launch Pre-Launch Deploy ✅ — Code-Pfad korrekt:
  - `game_panel.py` Z.765: `self.pre_launch_deploy.emit()` wird EINMAL aufgerufen, BEVOR die Steam-Pruefung (Z.767-784) erfolgt
  - Bei `is_steam` und `is_main_binary`: `_launch_via_steam(plugin)` wird NACH dem emit aufgerufen

- [x] 3. Proton-Launch Pre-Launch Deploy ✅ — Code-Pfad korrekt:
  - `game_panel.py` Z.765: `self.pre_launch_deploy.emit()` wird EINMAL aufgerufen, BEVOR die Steam-Pruefung
  - Bei `is_steam` und `not is_main_binary`: `_launch_via_proton(plugin, binary)` wird NACH dem emit aufgerufen

### Mehrfach-Klick-Schutz (Kriterien 4-6)

- [x] 4. Einmal-Klick = 1x Deploy ✅ — Code-Struktur korrekt:
  - `game_panel.py` Z.750-752: Guard `if self._is_launching: return` + `self._is_launching = True`
  - Z.765: Genau ein `self.pre_launch_deploy.emit()` pro Durchlauf
  - Z.805-807: `finally`-Block setzt `_is_launching = False`

- [x] 5. Doppelklick-Schutz ✅ — Code-Struktur korrekt:
  - Zweiter Klick trifft auf `self._is_launching = True` und gibt `return` zurueck (Z.750-751)
  - Zusaetzlich: Button ist disabled (Z.753: `self._start_btn.setEnabled(False)`)

- [x] 6. Button visuell deaktiviert ✅ — Code-Struktur korrekt:
  - Z.753: `self._start_btn.setEnabled(False)` — Button wird ausgegraut
  - Z.807: `self._start_btn.setEnabled(True)` im `finally`-Block — Button wird reaktiviert

### Redeploy-Timer-Sicherheit (Kriterien 7-8)

- [x] 7. Timer-Stop bei Pre-Launch ✅ — Code-Struktur korrekt:
  - `mainwindow.py` Z.1121: `self._redeploy_timer.stop()` als ERSTE Aktion in `_pre_launch_deploy()`
  - Danach folgt voller Deploy — kein Auto-Redeploy kann mehr feuern

- [x] 8. Timer-Stop bei Steam/Proton ✅ — Code-Struktur korrekt:
  - `pre_launch_deploy` Signal wird bei ALLEN Launch-Pfaden emittiert (Z.765 in game_panel.py)
  - `_pre_launch_deploy()` in mainwindow.py stoppt den Timer (Z.1121)
  - Das gilt fuer Steam, Proton UND Direct-Launch gleichermassen

### skip_ba2 bei Auto-Redeploy (Kriterien 9-11)

- [x] 9. Auto-Redeploy ohne BA2-Cleanup ✅ — Code-Struktur korrekt:
  - `mainwindow.py` Z.1114: `self._game_panel.silent_purge(skip_ba2=True)`
  - `game_panel.py` Z.638-639: `if skip_ba2: return` — BA2-Cleanup wird uebersprungen, kein "[BA2] INI restored"

- [x] 10. Auto-Redeploy ohne BA2-Packing ✅ — Code-Struktur korrekt:
  - `mainwindow.py` Z.1116: `self._game_panel.silent_deploy_fast()` — kein BA2-Packing
  - Z.1115: Print-Ausgabe "[DEPLOY] Auto-redeploy: deploying mods (fast, no BA2)"

- [x] 11. Pre-Launch nach Auto-Redeploy mit BA2 ✅ — Code-Struktur korrekt:
  - `mainwindow.py` Z.1125: `self._game_panel.silent_purge()` (ohne skip_ba2 = voller BA2-Cleanup)
  - Z.1127: `self._game_panel.silent_deploy()` (voller Deploy MIT BA2-Packing)

### Regression: Voller Deploy (Kriterien 12-15)

- [x] 12. BA2-Packing bei Bethesda-Games ✅ — Code-Struktur korrekt:
  - `_pre_launch_deploy()` ruft `silent_deploy()` auf (Z.1127), welche bei `NeedsBa2Packing`-Games BA2-Packing ausfuehrt
  - `silent_purge()` ohne skip_ba2 reinigt vorher die alten BA2s

- [x] 13. Profil-Wechsel mit vollem Deploy ✅ — Code-Struktur korrekt:
  - `mainwindow.py` Z.2272: `self._game_panel.silent_purge()` (OHNE skip_ba2 = voller BA2-Cleanup)
  - Z.2274: `self._game_panel.silent_deploy()` (voller Deploy MIT BA2-Packing)

- [x] 14. Instanz-Wechsel mit vollem Deploy ✅ — Code-Struktur korrekt:
  - `mainwindow.py` Z.829: `self._game_panel.silent_purge()` (OHNE skip_ba2 = voller BA2-Cleanup)
  - Danach wird die neue Instanz geladen und automatisch deployed

- [x] 15. App-Close mit vollem Purge ✅ — Code-Struktur korrekt:
  - `mainwindow.py` Z.3128: `self._game_panel.silent_purge()` (OHNE skip_ba2 = voller BA2-Cleanup)
  - BA2-Cleanup inkl. "[BA2] INI restored" wird ausgefuehrt

### Signal-Integritaet (Kriterien 16-17)

- [x] 16. UniqueConnection ✅ — Code-Struktur korrekt:
  - `mainwindow.py` Z.281-283: `Qt.ConnectionType.UniqueConnection` verhindert doppelte Verbindungen
  - Auch bei wiederholtem connect() wird nur 1x der Slot aufgerufen

- [x] 17. _on_start_game ohne eigenen Deploy ✅ — Code-Struktur korrekt:
  - `mainwindow.py` Z.1229-1241: `_on_start_game()` enthaelt NUR noch `QProcess.startDetached()` + Statusbar-Meldung
  - KEIN `silent_purge()`, KEIN `silent_deploy()`, KEIN `_redeploy_timer.stop()`
  - Deploy wird ausschliesslich durch `pre_launch_deploy` Signal gesteuert

### Code-Qualitaet (Kriterien 18-20)

- [x] 18. py_compile game_panel.py ✅ — Erfolgreich ausgefuehrt, Output: "OK"

- [x] 19. py_compile mainwindow.py ✅ — Erfolgreich ausgefuehrt, Output: "OK"

- [x] 20. App-Start ohne Fehler ✅ — `python main.py` startet erfolgreich:
  - Nur bekannte QTabBar "alignment" Warnings (laut CLAUDE.md ignorierbar)
  - Kein Traceback, kein NameError, kein ImportError, kein AttributeError
  - BA2-Packing laeuft korrekt durch (6 Mods gepackt)
  - Deploy erfolgreich: "18 symlinks, 0 copies, 0 errors"

**Akzeptanzkriterien: 20/20 Punkte**

---

## Zusaetzliche Befunde

### Keine CRITICAL/HIGH Bugs gefunden

Die Implementierung folgt exakt der Spec. Alle Code-Pfade sind korrekt.

### [LOW] Hinweis: skip_ba2 ueberspringt auch plugins.txt-Cleanup
- Datei: `/home/mob/Projekte/Anvil Organizer/anvil/widgets/game_panel.py` Zeile 638-639
- Beobachtung: `if skip_ba2: return` beendet die Methode VOR dem plugins.txt-Cleanup-Block (Z.654+). Das ist beabsichtigt (bei Auto-Redeploy soll plugins.txt nicht geloescht werden, da `silent_deploy_fast()` sie neu schreibt), aber der Parametername `skip_ba2` ist etwas irrefuehrend, da auch plugins.txt uebersprungen wird. **Kein Bug, nur Namensgebung.**

---

## Zusammenfassung aller silent_purge()-Aufrufe

| Aufrufer | Zeile | skip_ba2 | BA2-Cleanup | Korrekt? |
|----------|-------|----------|-------------|----------|
| `closeEvent()` | mainwindow.py:3128 | False (default) | JA | ✅ |
| `_on_profile_changed()` | mainwindow.py:2272 | False (default) | JA | ✅ |
| `_apply_instance()` | mainwindow.py:829 | False (default) | JA | ✅ |
| `_do_redeploy()` | mainwindow.py:1114 | **True** | NEIN | ✅ |
| `_pre_launch_deploy()` | mainwindow.py:1125 | False (default) | JA | ✅ |

---

## Ergebnis

| Bereich | Punkte |
|---------|--------|
| Regressions-Check | **7/7** |
| Akzeptanzkriterien | **20/20** |
| **Gesamt** | **27/27** |

## READY FOR COMMIT
