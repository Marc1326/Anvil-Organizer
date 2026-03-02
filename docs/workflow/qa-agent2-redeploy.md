# QA Agent 2 Report: Deploy-Logik in game_panel.py

Datum: 2026-03-02

## Geprueft

| Nr | Pruefpunkt | Ergebnis |
|----|-----------|----------|
| 1  | Existiert `silent_deploy()`? Wie funktioniert es? | OK |
| 2  | Existiert `silent_purge()`? Wie funktioniert es? | OK |
| 3  | Werden beide korrekt aufgerufen? Von wo? | OK mit Anmerkung |
| 4  | Wird plugins.txt nach jedem Re-Deploy neu geschrieben? | OK |
| 5  | Wie interagiert Deploy mit dem Mod-Toggle? | OK |
| 6  | Gibt es Fehlerbehandlung bei Deploy-Fehlern? | TEILWEISE |

---

## 1. silent_deploy() -- Analyse

**Datei:** `anvil/widgets/game_panel.py:546-603`

### Was es tut (3 Schritte):

1. **Symlink-Deploy** (Zeile 549-550): Ruft `self._deployer.deploy()` auf, falls ein Deployer existiert. Der `ModDeployer.deploy()` liest die Mod-Liste, erstellt Symlinks fuer alle aktiven Mods, und gibt ein `DeployResult`-Objekt zurueck.

2. **BA2-Packing** (Zeile 553-587): Nur fuer Bethesda-Spiele mit `NeedsBa2Packing=True`. Wird nur ausgefuehrt wenn Deploy erfolgreich war (`result.success`). Erstellt BA2-Archive aus losen Dateien, aktualisiert INI-Eintraege und speichert Manifest-Info.

3. **plugins.txt schreiben** (Zeile 590-603): Nur fuer Bethesda-Spiele mit `has_plugins_txt()`. Erstellt eine neue `PluginsTxtWriter`-Instanz, ruft `writer.write()` auf, loggt Fehler bei `None`-Return, und aktualisiert den Plugins-Tab.

### Bewertung: KORREKT

Die Methode ist gut strukturiert und hat korrekte Guard-Conditions fuer alle drei Schritte.

---

## 2. silent_deploy_fast() -- Analyse (NEU im Diff)

**Datei:** `anvil/widgets/game_panel.py:605-624`

### Was es tut (2 Schritte):

1. **Symlink-Deploy** (Zeile 607-608): Wie `silent_deploy()`, aber der Rueckgabewert von `deploy()` wird IGNORIERT.
2. **plugins.txt schreiben** (Zeile 611-624): Identischer Code wie in `silent_deploy()`.

### Unterschied zu silent_deploy():
- **KEIN** BA2-Packing -- dies ist der Sinn der "fast"-Variante
- Deploy-Result wird nicht geprueft

### Bewertung: OK, aber siehe Finding [MEDIUM] #1

---

## 3. silent_purge() -- Analyse

**Datei:** `anvil/widgets/game_panel.py:626-655`

### Was es tut (3 Schritte):

1. **Symlink-Purge** (Zeile 628-629): Ruft `self._deployer.purge()` auf. Loescht alle in der Manifest-Datei erfassten Symlinks.
2. **BA2-Cleanup** (Zeile 632-642): Loescht generierte BA2-Archive und stellt die originale INI wieder her.
3. **plugins.txt loeschen** (Zeile 644-655): Loescht die plugins.txt und alle Case-Varianten.

### Bewertung: KORREKT

---

## 4. Aufrufstellen -- Vollstaendige Karte

### silent_purge() wird von 5 Stellen aufgerufen:

| Zeile (mainwindow.py) | Methode | Kontext |
|------------------------|---------|---------|
| 811 | `_apply_instance()` | Vor Instanz-Wechsel: alte Daten entfernen |
| 1096 | `_do_redeploy()` | Auto-Redeploy: erst purge, dann fast deploy |
| 1207 | `_on_start_game()` | Vor Spielstart: erst purge, dann full deploy |
| 2251 | `_on_profile_changed()` | Vor Profil-Wechsel: alte Daten entfernen |
| 3102 | `closeEvent()` | App schliesst: aufraeumen |

### silent_deploy() wird von 3 Stellen aufgerufen:

| Zeile (mainwindow.py) | Methode | Kontext |
|------------------------|---------|---------|
| 961 | `_apply_instance()` | Nach Instanz-Laden: Mods deployen (mit BA2) |
| 1209 | `_on_start_game()` | Vor Spielstart: Full Deploy (mit BA2) |
| 2253 | `_on_profile_changed()` | Nach Profil-Wechsel: Mods deployen (mit BA2) |

### silent_deploy_fast() wird von 1 Stelle aufgerufen:

| Zeile (mainwindow.py) | Methode | Kontext |
|------------------------|---------|---------|
| 1098 | `_do_redeploy()` | Auto-Redeploy nach Mod-Toggle (ohne BA2) |

### _do_redeploy() (direkt, ohne Debounce-Timer) wird von 4 Stellen aufgerufen:

| Zeile (mainwindow.py) | Methode | Kontext |
|------------------------|---------|---------|
| 1098 | via `_redeploy_timer.timeout` | Debounce-Timer nach 500ms |
| 2144 | `_on_backup_restored()` | Nach Backup-Wiederherstellung |
| 2731 | `_ctx_rename_mod()` | Nach Mod-Umbenennung |
| 2767 | `_ctx_reinstall_mod()` | Nach Mod-Reinstallation |
| 2799 | `_ctx_remove_mods()` | Nach Mod-Loeschung |

### _schedule_redeploy() (via Debounce-Timer) wird von 4 Stellen aufgerufen:

| Zeile (mainwindow.py) | Methode | Kontext |
|------------------------|---------|---------|
| 1043 | `_on_mod_toggled()` | Mod Checkbox getoggelt |
| 1073 | `_on_mods_reordered()` | Mods per Drag&Drop umsortiert |
| 1418 | nach `_install_archives()` | Neue Mods installiert |
| 2484 | `_ctx_enable_selected()` | Kontextmenu: Mods aktivieren/deaktivieren |

### Bewertung: VOLLSTAENDIG und KORREKT

Das Muster ist sauber:
- **Sofortige Operationen** (Rename, Remove, Reinstall, Backup) -> `_do_redeploy()` direkt
- **Benutzer-Interaktionen** (Toggle, Reorder, Install) -> `_schedule_redeploy()` mit 500ms Debounce
- **Strukturelle Wechsel** (Instanz, Profil) -> `silent_purge()` + `set_instance_path()` + `silent_deploy()`
- **Spielstart** -> `silent_purge()` + `silent_deploy()` (full, mit BA2)
- **App-Close** -> nur `silent_purge()`

---

## 5. plugins.txt nach Re-Deploy

### Befund: JA, korrekt

- `silent_deploy()` Zeile 590-603: Schreibt plugins.txt und ruft `_refresh_plugins_tab()` auf
- `silent_deploy_fast()` Zeile 611-624: Schreibt plugins.txt und ruft `_refresh_plugins_tab()` auf
- `silent_purge()` Zeile 644-655: Loescht plugins.txt (aber ruft `_refresh_plugins_tab()` NICHT auf)

Bei jedem Re-Deploy-Zyklus (`silent_purge()` + `silent_deploy_fast()`) wird also:
1. Die alte plugins.txt geloescht (via purge)
2. Eine neue plugins.txt geschrieben (via deploy_fast)
3. Der Plugins-Tab aktualisiert (via `_refresh_plugins_tab()` in deploy_fast)

### Bewertung: KORREKT

---

## 6. Interaktion mit Mod-Toggle

### Flow:
```
User klickt Checkbox
  -> ModListModel.setData() emittiert mod_toggled(row, enabled)
  -> MainWindow._on_mod_toggled(row, enabled)     [Zeile 1030]
     |-- entry.enabled = enabled                    [Status-Update]
     |-- _write_current_modlist()                   [Persistieren auf Disk]
     |-- _update_active_count()                     [UI-Update]
     |-- _schedule_redeploy()                       [500ms Debounce-Timer]
                                                    
Nach 500ms (oder sofort bei erneutem Toggle: Timer Reset):
  -> MainWindow._do_redeploy()                     [Zeile 1090]
     |-- _redeploy_timer.stop()
     |-- silent_purge()
     |-- silent_deploy_fast()                       [Ohne BA2!]
     |-- statusBar "Mods deployed"
```

### Bewertung: KORREKT

Der Debounce-Mechanismus ist sauber implementiert:
- `QTimer.setSingleShot(True)` + `setInterval(500)` verhindert exzessives Redeploying bei schnellem Toggle
- Jeder neue Toggle-Aufruf resettet den Timer (`start()` auf einem laufenden SingleShot-Timer resettet ihn)
- Der Timer wird bei Instanz-Wechsel, Spielstart und App-Close gestoppt (Race-Condition-Schutz)

---

## 7. Fehlerbehandlung

### silent_deploy():
- `deployer.deploy()` Rueckgabewert wird geprueft -- BA2-Block nur bei `result.success` (Zeile 557)
- `writer.write()` Rueckgabewert wird geprueft -- Log-Warnung bei `None` (Zeile 601-602)
- **Keine Exception-Behandlung** um den gesamten Block

### silent_deploy_fast():
- `deployer.deploy()` Rueckgabewert wird **IGNORIERT** (Zeile 608)
- `writer.write()` Rueckgabewert wird geprueft (Zeile 622-623)
- **Keine Exception-Behandlung** um den gesamten Block

### silent_purge():
- `deployer.purge()` Rueckgabewert wird **IGNORIERT** (Zeile 629)
- `packer.cleanup_ba2s()` und `packer.restore_ini()` -- keine Fehlerbehandlung sichtbar
- `writer.remove()` Rueckgabewert wird **IGNORIERT** (Zeile 655)
- **Keine Exception-Behandlung** um den gesamten Block

### _do_redeploy():
- Keine Try/Except um `silent_purge()` + `silent_deploy_fast()` (Zeile 1096-1098)
- Wenn einer der Aufrufe eine unbehandelte Exception wirft, bleibt die Statusbar auf "Deploying..." stehen

### _on_start_game():
- Keine Try/Except um `silent_purge()` + `silent_deploy()` (Zeile 1207-1209)
- Das Spiel wird trotzdem gestartet (QProcess.startDetached nach dem Deploy-Block)

---

## Findings

### [MEDIUM] #1: silent_deploy_fast() ignoriert Deploy-Result

- **Datei:** `anvil/widgets/game_panel.py:607-608`
- **Problem:** `silent_deploy_fast()` ignoriert den Rueckgabewert von `self._deployer.deploy()`. Im Gegensatz zu `silent_deploy()` (Zeile 548-550), wo `result` gespeichert und fuer die BA2-Entscheidung verwendet wird, wird hier der Return-Wert verworfen. Das bedeutet: Wenn der Deploy fehlschlaegt, wird trotzdem plugins.txt geschrieben (moeglicherweise mit falschen/veralteten Daten) und der Plugins-Tab aktualisiert.
- **Fix:** `result = self._deployer.deploy()` speichern und plugins.txt-Block nur bei `result.success` ausfuehren. Alternativ mindestens loggen wenn `result.success == False`.

### [MEDIUM] #2: silent_purge() ignoriert alle Rueckgabewerte

- **Datei:** `anvil/widgets/game_panel.py:628-655`
- **Problem:** Weder `deployer.purge()`, noch `packer.cleanup_ba2s()`, noch `writer.remove()` werden auf Fehler geprueft. Wenn der Purge fehlschlaegt (z.B. Manifest nicht lesbar), wird trotzdem BA2-Cleanup und plugins.txt-Loeschung versucht. Das ist unkritisch solange jeder Schritt unabhaengig ist, aber ein Log-Eintrag bei Fehlern waere hilfreich fuer Debugging.
- **Fix:** `result = self._deployer.purge()` speichern und bei `not result.success` eine Warnung loggen.

### [MEDIUM] #3: _do_redeploy() hat keine Exception-Behandlung

- **Datei:** `anvil/mainwindow.py:1090-1099`
- **Problem:** Wenn `silent_purge()` oder `silent_deploy_fast()` eine unbehandelte Exception werfen, bleibt die Statusbar auf `tr("status.deploying")` (Timeout 0 = permanent) stehen. Der Benutzer sieht dauerhaft "Wird bereitgestellt..." ohne dass etwas passiert.
- **Fix:** Try/Except um den Block, im Except-Fall `self.statusBar().showMessage(tr("status.deploy_failed"), 5000)` setzen. Der Key `status.deploy_failed` existiert bereits in allen 6 Locale-Dateien.

### [LOW] #1: silent_purge() ruft _refresh_plugins_tab() NICHT auf

- **Datei:** `anvil/widgets/game_panel.py:626-655`
- **Problem:** Nach dem Loeschen der plugins.txt in `silent_purge()` wird der Plugins-Tab nicht aktualisiert. Aktuell kein praktisches Problem, da nach jedem Purge entweder ein Deploy (das den Tab aktualisiert) oder ein App-Close folgt. Aber wenn in Zukunft ein "Purge-only"-Button eingefuehrt wird, wuerden veraltete Daten im Plugins-Tab stehen bleiben.
- **Fix:** Optional: `self._refresh_plugins_tab()` am Ende von `silent_purge()` aufrufen, oder `self._plugins_tree.clear()`.

### [LOW] #2: Unbenutzter Uebersetzungs-Key "status.deploy_skipped"

- **Datei:** Alle 6 Locale-Dateien (de/en/es/fr/it/pt.json), Zeile 438
- **Problem:** Der Key `status.deploy_skipped` wurde in allen Locale-Dateien hinzugefuegt, wird aber nirgends im Python-Code referenziert. Kein Fehler, aber toter Code.
- **Fix:** Entweder entfernen oder an der passenden Stelle einbauen (z.B. in `_schedule_redeploy()` wenn `_current_instance_path` fehlt).

### [LOW] #3: Code-Duplizierung zwischen silent_deploy() und silent_deploy_fast()

- **Datei:** `anvil/widgets/game_panel.py:590-603` vs `611-624`
- **Problem:** Der plugins.txt-Block (6 Bedingungen + Writer-Erstellung + write() + Fehlerlog + _refresh_plugins_tab) ist in beiden Methoden identisch. Bei zukuenftigen Aenderungen muss die Aenderung an ZWEI Stellen vorgenommen werden.
- **Fix:** Extrahiere den plugins.txt-Block in eine private Hilfsmethode `_write_plugins_txt()`.

---

## Gesamtbewertung

Die Deploy-Logik ist **funktional korrekt und gut strukturiert**. Das Debounce-Pattern fuer Auto-Redeploy nach Mod-Toggle ist sauber implementiert. Die Unterscheidung zwischen `silent_deploy()` (full, mit BA2) und `silent_deploy_fast()` (quick, ohne BA2) ist sinnvoll und korrekt an den Aufrufstellen eingesetzt.

Die Hauptkritikpunkte sind:
1. Fehlende Fehlerbehandlung in `_do_redeploy()` koennte zu einer permanent steckenden Statusbar fuehren
2. `silent_deploy_fast()` ignoriert den Deploy-Ergebnis-Status
3. Code-Duplizierung im plugins.txt-Block

Keiner dieser Punkte ist CRITICAL. Die Funktionalitaet ist gegeben.

## Ergebnis: READY FOR COMMIT (mit empfohlenen Verbesserungen)

Die 3 MEDIUM-Findings sind Verbesserungsvorschlaege, keine Blocker. Die Kernlogik (Purge/Deploy/Debounce/plugins.txt) funktioniert korrekt.
