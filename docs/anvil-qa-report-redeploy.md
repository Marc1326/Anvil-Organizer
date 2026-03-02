# QA Report -- Auto-Redeploy bei Mod-Statusaenderung (Konsolidiert)

Datum: 2026-03-02
Konsolidiert von: QA Agent 4
Quellen: Agent 1 (mainwindow.py), Agent 2 (game_panel.py), Agent 3 (Live-Test)

---

## Executive Summary

Die Auto-Redeploy-Funktionalitaet ist **vollstaendig und korrekt implementiert**. Alle 25 Akzeptanzkriterien aus der Feature-Spezifikation wurden geprueft und bestanden. Der zentrale Debounce-Mechanismus (QTimer SingleShot 500ms) funktioniert korrekt, alle 8 spezifizierten Aufrufstellen sind korrekt verdrahtet, die Trennung zwischen Fast-Deploy (ohne BA2) und Full-Deploy (mit BA2 vor Game-Start) ist sauber umgesetzt, und alle i18n-Keys sind in allen 6 Locales vorhanden. Es wurden keine CRITICAL oder HIGH Findings identifiziert -- lediglich 3 MEDIUM und 4 LOW Findings, die Verbesserungsvorschlaege darstellen, aber keine funktionalen Blocker sind.

---

## Akzeptanz-Checkliste

### Toggle & Deploy

| Nr | Kriterium | Status | Beleg |
|----|-----------|--------|-------|
| AK-01 | Mod per Checkbox aktiviert + 500ms -> Symlinks existieren | **PASS** | Agent 1: Signal-Kette vollstaendig (Zeile 1030-1043). Agent 3: 14 Symlinks im Data-Verzeichnis verifiziert. |
| AK-02 | Mod deaktiviert + 500ms -> Symlinks entfernt | **PASS** | Agent 1: `entry.enabled = enabled` + `_write_current_modlist()` + `_schedule_redeploy()`. Purge entfernt alle Symlinks, Deploy erstellt nur fuer aktive Mods neue. |
| AK-03 | 5 Toggles in <500ms -> genau 1 Deploy-Zyklus | **PASS** | Agent 1: `QTimer.setSingleShot(True)` + `start()` resettet Timer. Agent 3: bestaetigt. |
| AK-04 | Timer-Reset bei erneutem Toggle innerhalb 500ms | **PASS** | Agent 1: Qt-Doku belegt: "start() on running timer resets countdown". Agent 3: bestaetigt. |

### Drag & Drop

| Nr | Kriterium | Status | Beleg |
|----|-----------|--------|-------|
| AK-05 | D&D-Verschiebung + 500ms -> Symlinks spiegeln neue Prioritaet | **PASS** | Agent 1: `_on_mods_reordered()` Zeile 1045-1073 -> `_schedule_redeploy()`. |

### Bulk-Operationen

| Nr | Kriterium | Status | Beleg |
|----|-----------|--------|-------|
| AK-06 | Kontextmenue "Alle aktivieren" + 500ms -> alle deployed | **PASS** | Agent 1: `_ctx_enable_selected()` Zeile 2484 -> `_schedule_redeploy()`. |
| AK-07 | Kontextmenue "Alle deaktivieren" + 500ms -> Symlinks entfernt | **PASS** | Agent 1: Gleiche Methode fuer Enable/Disable, gleicher Redeploy-Pfad. |

### Sofort-Aktionen

| Nr | Kriterium | Status | Beleg |
|----|-----------|--------|-------|
| AK-08 | Mod geloescht -> Symlinks SOFORT aktualisiert | **PASS** | Agent 1: `_ctx_remove_mods()` Zeile 2799 -> `_do_redeploy()` (direkt, kein Timer). |
| AK-09 | Mod umbenannt -> Symlinks zeigen auf neuen Ordnernamen | **PASS** | Agent 1: `_ctx_rename_mod()` Zeile 2731 -> `_do_redeploy()` (direkt). |
| AK-10 | Neue Mod installiert + 500ms -> Symlinks vorhanden | **PASS** | Agent 1: `_install_archives()` Zeile 1418 -> `_schedule_redeploy()`. |
| AK-11 | Mod reinstalliert -> Symlinks spiegeln neuen Stand | **PASS** | Agent 1: `_ctx_reinstall_mod()` Zeile 2767 -> `_do_redeploy()` (direkt). |
| AK-12 | Backup wiederhergestellt -> Symlinks konsistent | **PASS** | Agent 1: `_restore_backup()` Zeile 2144 -> `_do_redeploy()` (direkt). |

### BA2 / Bethesda

| Nr | Kriterium | Status | Beleg |
|----|-----------|--------|-------|
| AK-13 | Mod-Toggle -> KEIN BA2-Packing | **PASS** | Agent 2: `silent_deploy_fast()` Zeile 605-624 enthaelt keinen BA2-Code. Agent 1: bestaetigt. |
| AK-14 | Run-Button -> Full Deploy MIT BA2 vor Spielstart | **PASS** | Agent 1: `_on_start_game()` Zeile 1203-1209 ruft `silent_deploy()` (mit BA2). Agent 3: BA2-Log beim Start verifiziert. |
| AK-15 | Mod-Toggle + 500ms -> plugins.txt aktualisiert | **PASS** | Agent 2: `silent_deploy_fast()` schreibt plugins.txt via PluginsTxtWriter. Agent 3: plugins.txt im Proton-Prefix verifiziert. |

### UI-Feedback

| Nr | Kriterium | Status | Beleg |
|----|-----------|--------|-------|
| AK-16 | Toggle -> StatusBar zeigt sofort "Deploying..." | **PASS** | Agent 1: `_schedule_redeploy()` Zeile 1087 -> `showMessage(tr("status.deploying"), 0)`. |
| AK-17 | Deploy fertig -> StatusBar zeigt 3s "Mods deployed" | **PASS** | Agent 1: `_do_redeploy()` Zeile 1099 -> `showMessage(tr("status.deployed"), 3000)`. |

### Safety Guards

| Nr | Kriterium | Status | Beleg |
|----|-----------|--------|-------|
| AK-18 | Toggle + <500ms Instanzwechsel -> Timer gestoppt | **PASS** | Agent 1: `_apply_instance()` Zeile 809 -> `_redeploy_timer.stop()`. Agent 3: bestaetigt. |
| AK-19 | Toggle + <500ms Profilwechsel -> Timer gestoppt | **PASS** | Agent 1: `_on_profile_changed()` Zeile 2250 -> `_redeploy_timer.stop()`. Agent 3: bestaetigt. |
| AK-20 | Toggle + <500ms App-Close -> Timer gestoppt + Purge | **PASS** | Agent 1: `closeEvent()` Zeile 3100 -> `_redeploy_timer.stop()` + `silent_purge()`. |
| AK-21 | Keine Instanz -> kein Fehler | **PASS** | Agent 1: Guard `if not self._current_instance_path: return` in beiden Methoden. |
| AK-23 | Instanz-/Profilwechsel -> kein Doppel-Deploy | **PASS** | Agent 1: Timer-Stop + eigener purge/deploy-Zyklus, kein debounced Redeploy. Agent 3: bestaetigt. |

### Allgemein

| Nr | Kriterium | Status | Beleg |
|----|-----------|--------|-------|
| AK-22 | 3 i18n-Keys in allen 6 Locales | **PASS** | Agent 1: Alle Keys verifiziert. Agent 3: Inhalte in allen 6 Sprachen geprueft und aufgelistet. |
| AK-24 | [PURGE] und [DEPLOY] Tags in Konsole | **PASS** | Agent 1: Zeilen 1095-1097 in `_do_redeploy()`. Agent 3: Startup-Log zeigt Tags. |
| AK-25 | App startet ohne Fehler | **PASS** | Agent 3: Live-Test, keine Tracebacks, keine NameError/ImportError/AttributeError. Nur bekannte QTabBar-Warnungen. |

### Ergebnis: 25/25 Punkte erfuellt

---

## Findings Uebersicht

### [MEDIUM] #1: silent_deploy_fast() ignoriert Deploy-Result

- **Datei:** `/home/mob/Projekte/Anvil Organizer/anvil/widgets/game_panel.py:607-608`
- **Gefunden von:** Agent 2
- **Problem:** `silent_deploy_fast()` verwirft den Rueckgabewert von `self._deployer.deploy()`. Im Gegensatz zu `silent_deploy()` (wo `result.success` geprueft wird) wird hier bei einem fehlgeschlagenen Deploy trotzdem plugins.txt geschrieben und der Plugins-Tab aktualisiert. Wenn der Deploy fehlschlaegt, koennte eine inkonsistente plugins.txt entstehen.
- **Fix:** `result = self._deployer.deploy()` speichern und den plugins.txt-Block nur bei `result.success` ausfuehren, oder mindestens eine Log-Warnung ausgeben.

### [MEDIUM] #2: silent_purge() ignoriert alle Rueckgabewerte

- **Datei:** `/home/mob/Projekte/Anvil Organizer/anvil/widgets/game_panel.py:628-655`
- **Gefunden von:** Agent 2
- **Problem:** Weder `deployer.purge()`, noch `packer.cleanup_ba2s()`, noch `writer.remove()` werden auf Fehler geprueft. Wenn einer dieser Schritte fehlschlaegt, wird kein Log-Eintrag erzeugt. Fuer Debugging-Zwecke waere eine Fehlerprotokollierung hilfreich.
- **Fix:** Rueckgabewerte speichern und bei Fehler eine Warnung loggen.

### [MEDIUM] #3: _do_redeploy() hat keine Exception-Behandlung

- **Datei:** `/home/mob/Projekte/Anvil Organizer/anvil/mainwindow.py:1090-1099`
- **Gefunden von:** Agent 2
- **Problem:** Wenn `silent_purge()` oder `silent_deploy_fast()` eine unbehandelte Exception werfen, bleibt die StatusBar permanent auf "Wird bereitgestellt..." stehen (Timeout 0 = unendlich). Der Benutzer sieht dauerhaft eine falsche Statusmeldung.
- **Fix:** Try/Except um den Block, im Except-Fall `statusBar().showMessage(tr("status.deploy_failed"), 5000)` setzen. Laut Agent 2 existiert der Key `status.deploy_failed` bereits in den Locale-Dateien.

### [LOW] #1: Unbenutzter i18n-Key `status.deploy_skipped`

- **Datei:** Alle 6 Locale-Dateien (de/en/es/fr/it/pt.json), jeweils Zeile 438
- **Gefunden von:** Agent 1, Agent 2, Agent 3 (alle drei)
- **Problem:** Der Key `status.deploy_skipped` wurde in allen 6 Locale-Dateien angelegt, wird aber nirgends im Python-Code via `tr("status.deploy_skipped")` aufgerufen. Die Guard-Klauseln in `_schedule_redeploy()` und `_do_redeploy()` machen ein fruehes `return` ohne StatusBar-Meldung.
- **Fix:** Entweder den Key in `_schedule_redeploy()` vor dem `return` verwenden, oder als "fuer spaetere Nutzung reserviert" dokumentieren, oder aus den Locale-Dateien entfernen.

### [LOW] #2: Redundanter Purge-Aufruf in _do_redeploy()

- **Datei:** `/home/mob/Projekte/Anvil Organizer/anvil/mainwindow.py:1096` + `/home/mob/Projekte/Anvil Organizer/anvil/core/mod_deployer.py:123-125`
- **Gefunden von:** Agent 1
- **Problem:** `_do_redeploy()` ruft `silent_purge()` auf, danach `silent_deploy_fast()` -> `deployer.deploy()`. Innerhalb von `deployer.deploy()` steht ein weiterer `if self.is_deployed(): purge_result = self.purge()` Check. Da die erste Purge das Manifest bereits loescht, ist der zweite Check ein No-Op -- aber es entsteht eine unnoetige Dateisystem-Pruefung.
- **Fix:** Kein Fix noetig. Der externe Purge ist defensiv und schadet nicht. Nur bei Performance-Optimierung relevant.

### [LOW] #3: Code-Duplizierung zwischen silent_deploy() und silent_deploy_fast()

- **Datei:** `/home/mob/Projekte/Anvil Organizer/anvil/widgets/game_panel.py:590-603` vs `611-624`
- **Gefunden von:** Agent 2
- **Problem:** Der plugins.txt-Block (Bedingungspruefung + Writer-Erstellung + write() + Fehlerlog + `_refresh_plugins_tab()`) ist in beiden Methoden identisch dupliziert. Bei zukuenftigen Aenderungen muss die Aenderung an ZWEI Stellen vorgenommen werden.
- **Fix:** Den plugins.txt-Block in eine private Hilfsmethode `_write_plugins_txt()` extrahieren.

### [LOW] #4: silent_purge() ruft _refresh_plugins_tab() NICHT auf

- **Datei:** `/home/mob/Projekte/Anvil Organizer/anvil/widgets/game_panel.py:626-655`
- **Gefunden von:** Agent 2
- **Problem:** Nach dem Loeschen der plugins.txt in `silent_purge()` wird der Plugins-Tab nicht aktualisiert. Aktuell kein praktisches Problem, da nach jedem Purge entweder ein Deploy (das den Tab aktualisiert) oder ein App-Close folgt. Aber bei einem zukuenftigen "Purge-only"-Feature wuerden veraltete Daten im Tab stehen bleiben.
- **Fix:** Optional: `self._refresh_plugins_tab()` am Ende von `silent_purge()` aufrufen.

---

## Zusaetzliche Beobachtungen (nicht in der Checkliste)

### [INFO] Doppelter Aufruf-Pfad bei _ctx_reinstall_mod

- **Gefunden von:** Agent 3
- `_install_archives()` (Zeile 1418) ruft `_schedule_redeploy()` auf, danach ruft `_ctx_reinstall_mod` zusaetzlich `_do_redeploy()` auf. Da `_do_redeploy()` den Timer sofort stoppt (Zeile 1092), entsteht kein doppeltes Deploy. Der Code-Flow ist aber unnoetig komplex: Timer wird gestartet, sofort gestoppt, dann synchron deployed. Kein funktionaler Fehler.

### [INFO] BA2-Packing-Fehler bei 2 Mods

- **Gefunden von:** Agent 3
- Mentats - F4SE und Lacy Underwear (Installer) haben BA2-Packing-Fehler beim generellen Archiv. Dies ist ein vorbestehendes Problem und wurde NICHT durch das Redeploy-Feature verursacht.

### [INFO] Diskrepanz active_mods.json vs modlist.txt

- **Gefunden von:** Agent 3
- `LooksMenu v1-7-0` ist in modlist.txt als aktiv (`+`) markiert, aber NICHT in active_mods.json gelistet. Vorbestehendes Problem, nicht durch Redeploy verursacht.

---

## Empfehlungen (priorisiert)

1. **(MEDIUM, empfohlen)** Exception-Behandlung in `_do_redeploy()` einfuegen, um eine permanent steckende StatusBar zu verhindern. Ein einfaches Try/Except mit Fehler-Statusmeldung reicht aus.

2. **(MEDIUM, empfohlen)** Deploy-Result in `silent_deploy_fast()` pruefen und bei Fehler loggen, damit fehlgeschlagene Deploys nicht unbemerkt bleiben.

3. **(MEDIUM, optional)** Purge-Result in `silent_purge()` loggen fuer bessere Fehlertransparenz.

4. **(LOW, optional)** Ungenutzten Key `status.deploy_skipped` entweder verwenden oder entfernen.

5. **(LOW, optional)** plugins.txt-Block in eine Hilfsmethode `_write_plugins_txt()` extrahieren, um Code-Duplizierung zu vermeiden.

**Hinweis:** Alle 5 Empfehlungen sind Verbesserungsvorschlaege fuer Robustheit und Wartbarkeit. Keiner davon ist ein funktionaler Blocker.

---

## Verdict

### READY FOR COMMIT

**Begruendung:**
- Alle 25/25 Akzeptanzkriterien sind erfuellt
- Keine CRITICAL oder HIGH Findings
- Die 3 MEDIUM Findings betreffen Fehlerbehandlung und Logging, nicht die Kernfunktionalitaet
- Die 4 LOW Findings betreffen Code-Hygiene und toten Code
- Der Live-Test (Agent 3) hat die korrekte Funktion im realen Dateisystem bestaetigt: 14 Symlinks, korrektes Deploy-Manifest, korrekte plugins.txt
- Die App startet fehlerfrei

Die Redeploy-Funktionalitaet ist produktionsreif. Die MEDIUM-Empfehlungen koennen in einem separaten Cleanup-Commit nachgezogen werden.
