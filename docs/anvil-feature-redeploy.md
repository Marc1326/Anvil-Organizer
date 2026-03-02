# Feature: Auto-Redeploy bei Mod-Statusaenderung

**Datum:** 2026-03-02
**Quellen:** Agent 1-3 Reports in `docs/workflow/`

---

## 1. Zusammenfassung

Wenn der User eine Mod aktiviert/deaktiviert, wird AUTOMATISCH ein Re-Deploy ausgefuehrt. Symlinks werden sofort aktualisiert, plugins.txt wird neu geschrieben. Der User muss Anvil NICHT neu starten.

---

## 2. Problembeschreibung

### Ist-Zustand

`silent_deploy()` / `silent_purge()` wird nur bei 3 Anlaessen aufgerufen:
1. Instanzwechsel (`_apply_instance()`, Zeilen 803/953)
2. Profilwechsel (`_on_profile_changed()`, Zeilen 2211/2213)
3. App schliessen (`closeEvent()`, Zeile 3057)

An **6 von 9 Stellen**, die den Mod-Status aendern, fehlt ein Re-Deploy.

### Kritische Luecken

| Nr | Methode | Datei:Zeile | Trigger | Problem |
|----|---------|-------------|---------|---------|
| 1 | `_on_mod_toggled()` | mainwindow.py:1022 | Checkbox-Klick | Disk aktualisiert, Symlinks unveraendert |
| 2 | `_on_mods_reordered()` | mainwindow.py:1036 | Drag & Drop | Reihenfolge geaendert, Symlinks in alter Reihenfolge |
| 3 | `_ctx_enable_selected()` | mainwindow.py:2430 | Kontextmenue Bulk-Enable/Disable | Disk aktualisiert, Symlinks unveraendert |
| 4 | `_ctx_remove_mods()` | mainwindow.py:2726 | Kontextmenue Mod entfernen | Mod-Ordner geloescht, Symlinks zeigen ins Leere |
| 5 | `_ctx_rename_mod()` | mainwindow.py:2655 | Kontextmenue Umbenennen | Ordner umbenannt, Symlinks zeigen auf alten Namen |

### Mittlere Luecken

| Nr | Methode | Datei:Zeile | Trigger | Problem |
|----|---------|-------------|---------|---------|
| 6 | `_install_archives()` | mainwindow.py:1194 | Mod-Installation | Neue Mod in modlist, aber nicht deployed |
| 7 | `_ctx_reinstall_mod()` | mainwindow.py:2693 | Mod-Reinstallation | Geaenderte Dateien nicht deployed |
| 8 | Backup-Restore | mainwindow.py:2105 | Backup wiederherstellen | Deployment veraltet |

---

## 3. Technische Planung

### Architektur: Zentraler Debounce-Timer

Statt an jeder Stelle direkt `silent_purge()` + `silent_deploy()` aufzurufen, wird ein **zentraler Debounce-Mechanismus** in `MainWindow` eingefuehrt.

**Warum Debounce:**
- User toggelt oft mehrere Mods in schneller Folge
- `deploy()` ist bei vielen Mods spuerbar (200-500ms bei 100 Mods, 1-3s bei 300+ Mods)
- Ohne Debounce: 10 schnelle Toggles = 10 purge+deploy Zyklen = UI-Freeze
- Mit 500ms Debounce: 10 schnelle Toggles = 1 purge+deploy Zyklus

### Zwei Trigger-Kategorien

**Kategorie A: Debounced (500ms QTimer)**
Fuer Aktionen die oft in schneller Folge passieren:
- `_on_mod_toggled()` -- Checkbox-Klick
- `_on_mods_reordered()` -- Drag & Drop
- `_ctx_enable_selected()` -- Bulk-Enable/Disable (beinhaltet `_ctx_enable_all()`)
- `_install_archives()` -- Mod-Installation

**Kategorie B: Sofort (kein Debounce)**
Fuer Aktionen die sofortige Konsistenz erfordern:
- `_ctx_remove_mods()` -- Mod geloescht, Symlinks zeigen ins Leere
- `_ctx_rename_mod()` -- Ordner umbenannt, Symlinks kaputt
- `_ctx_reinstall_mod()` -- Geaenderte Dateien sofort deployed
- Backup-Restore -- Kompletter Zustand aendert sich

### BA2-Sonderbehandlung

**Problem:** BA2-Packing (Bethesda-Spiele) ist SEHR teuer -- Wine/BSArch-Aufruf, mehrere Sekunden bis Minuten.

**Loesung:** Neue Methode `silent_deploy_fast()` in `GamePanel`:
- Fuehrt NUR `deployer.deploy()` (Symlinks) + `plugins.txt` Schreiben aus
- Ueberspringt BA2-Packing komplett
- BA2-Packing wird NUR vor Game-Start ausgefuehrt (im bestehenden `silent_deploy()`)

### Signal-Flow (Neu)

```
User toggelt Mod-Checkbox
    |
    v
ModListModel.setData() -> emittiert mod_toggled(row, enabled)
    |
    v
MainWindow._on_mod_toggled(row, enabled)
    |-- entry.enabled = enabled
    |-- _write_current_modlist()       (Disk: modlist.txt + active_mods.json)
    |-- _update_active_count()
    |-- _schedule_redeploy()           ** NEU **
    |
    v
_schedule_redeploy()
    |-- self._redeploy_timer.start()   (Reset auf 500ms)
    |-- self.statusBar().showMessage(tr("status.deploying"), 0)
    |
    v
[500ms vergehen ohne weitere Aenderung]
    |
    v
QTimer.timeout -> _do_redeploy()
    |-- self._game_panel.silent_purge()
    |-- self._game_panel.silent_deploy_fast()    ** OHNE BA2 **
    |-- self.statusBar().showMessage(tr("status.deployed"), 3000)
```

```
User loescht Mod (Kontextmenue)
    |
    v
MainWindow._ctx_remove_mods()
    |-- Mod-Ordner loeschen
    |-- modlist.txt aktualisieren
    |-- _reload_mod_list()
    |-- _do_redeploy()                 ** SOFORT, kein Debounce **
```

```
User startet Spiel (Run-Button)
    |
    v
MainWindow._on_start_game()
    |-- self._game_panel.silent_purge()     ** NEU: Vor Start full deploy **
    |-- self._game_panel.silent_deploy()    ** MIT BA2-Packing **
    |-- QProcess.startDetached(binary_path)
```

---

## 4. Betroffene Dateien

| Datei | Aenderung | Aufwand |
|-------|-----------|---------|
| `anvil/mainwindow.py` | Neuer QTimer, `_schedule_redeploy()`, `_do_redeploy()`, Aufrufe an 8 Stellen, BA2-Deploy vor Game-Start | HOCH |
| `anvil/widgets/game_panel.py` | Neue Methode `silent_deploy_fast()` (Symlinks + plugins.txt, ohne BA2) | MITTEL |
| `anvil/locales/de.json` | Neue Keys: `status.deploying`, `status.deployed`, `status.deploy_skipped` | NIEDRIG |
| `anvil/locales/en.json` | Neue Keys (3 Stueck) | NIEDRIG |
| `anvil/locales/es.json` | Neue Keys (3 Stueck) | NIEDRIG |
| `anvil/locales/fr.json` | Neue Keys (3 Stueck) | NIEDRIG |
| `anvil/locales/it.json` | Neue Keys (3 Stueck) | NIEDRIG |
| `anvil/locales/pt.json` | Neue Keys (3 Stueck) | NIEDRIG |

---

## 5. Implementierungsplan

**Schritt 1: `silent_deploy_fast()` in GamePanel**
- Neue Methode in `anvil/widgets/game_panel.py`
- Kopie von `silent_deploy()`, aber OHNE den BA2-Packing-Block
- Behaelt: `deployer.deploy()` + `plugins.txt` Schreiben + `_refresh_plugins_tab()`

**Schritt 2: Debounce-Timer in MainWindow**
- In `MainWindow.__init__()`:
  ```python
  self._redeploy_timer = QTimer()
  self._redeploy_timer.setSingleShot(True)
  self._redeploy_timer.setInterval(500)
  self._redeploy_timer.timeout.connect(self._do_redeploy)
  ```

**Schritt 3: Hilfsmethoden**
- `_schedule_redeploy()`: Timer starten + StatusBar "Deploying..."
- `_do_redeploy()`: `silent_purge()` + `silent_deploy_fast()` + StatusBar "Deployed"
- Guard: Wenn kein Deployer/keine Instanz aktiv, nichts tun

**Schritt 4: Debounced-Aufrufe einfuegen (Kategorie A)**
- `_on_mod_toggled()` (Zeile ~1034): `self._schedule_redeploy()`
- `_on_mods_reordered()` (Zeile ~1063): `self._schedule_redeploy()`
- `_ctx_enable_selected()` (Zeile ~2443): `self._schedule_redeploy()`
- `_install_archives()` (Zeile ~1362): `self._schedule_redeploy()`

**Schritt 5: Sofort-Aufrufe einfuegen (Kategorie B)**
- `_ctx_remove_mods()` (nach `_reload_mod_list()`): `self._do_redeploy()`
- `_ctx_rename_mod()` (nach `_reload_mod_list()`): `self._do_redeploy()`
- `_ctx_reinstall_mod()`: `self._do_redeploy()`
- Backup-Restore (nach `_reload_mod_list()`): `self._do_redeploy()`

**Schritt 6: BA2 Full-Deploy vor Game-Start**
- In `_on_start_game()`: VOR `QProcess.startDetached()`:
  ```python
  self._game_panel.silent_purge()
  self._game_panel.silent_deploy()  # MIT BA2
  ```

**Schritt 7: Pendenden Timer bei Wechsel stoppen**
- In `_apply_instance()` (vor purge): `self._redeploy_timer.stop()`
- In `_on_profile_changed()` (vor purge): `self._redeploy_timer.stop()`
- In `closeEvent()` (vor purge): `self._redeploy_timer.stop()`

**Schritt 8: i18n-Keys hinzufuegen**
- In allen 6 Locale-Dateien:
  - `status.deploying`: "Deploying..." / "Wird bereitgestellt..."
  - `status.deployed`: "Mods deployed" / "Mods bereitgestellt"
  - `status.deploy_skipped`: "Deploy skipped (no instance)" / "Deploy uebersprungen"

---

## 6. Risiken

| Risiko | Wahrscheinlichkeit | Mitigation |
|--------|-------------------|------------|
| UI-Freeze bei 300+ Mods | Mittel | Debounce reduziert Haeufigkeit; langfristig Worker-Thread |
| BA2-Packing fehlt nach Toggle | Niedrig | Full Deploy vor Game-Start stellt Konsistenz her |
| Pendender Timer bei Instanzwechsel | Niedrig | Timer-Stop vor Instanz/Profil-Wechsel |
| Race Condition bei schnellen Toggles | Sehr Niedrig | Synchrone Ausfuehrung im Main-Thread schuetzt davor |

---

## 7. Akzeptanz-Checkliste

### Toggle & Deploy
- [ ] **AK-01:** Mod per Checkbox aktiviert + 500ms gewartet -> Symlinks fuer diese Mod existieren im Spielverzeichnis
- [ ] **AK-02:** Aktive Mod per Checkbox deaktiviert + 500ms gewartet -> Symlinks entfernt
- [ ] **AK-03:** 5 Mods in <500ms getoggelt -> genau EIN purge+deploy-Zyklus (Log pruefen)
- [ ] **AK-04:** Mod A toggelt, 400ms warten, Mod B toggelt -> Timer Reset, Deploy erst 500ms nach Mod B

### Drag & Drop
- [ ] **AK-05:** Mod per D&D verschoben + 500ms gewartet -> Symlinks spiegeln neue Prioritaetsreihenfolge

### Bulk-Operationen
- [ ] **AK-06:** Mehrere Mods selektiert -> Kontextmenue "Alle aktivieren" + 500ms -> alle deployed
- [ ] **AK-07:** Mehrere Mods selektiert -> Kontextmenue "Alle deaktivieren" + 500ms -> Symlinks entfernt

### Sofort-Aktionen
- [ ] **AK-08:** Mod per Kontextmenue geloescht -> Symlinks SOFORT aktualisiert, keine verwaisten Links
- [ ] **AK-09:** Mod umbenannt -> Symlinks zeigen auf neuen Ordnernamen
- [ ] **AK-10:** Neue Mod installiert + 500ms -> Symlinks vorhanden (wenn aktiv)
- [ ] **AK-11:** Mod reinstalliert -> Symlinks spiegeln neuen Dateistand
- [ ] **AK-12:** Backup wiederhergestellt -> Symlinks entsprechen wiederhergestelltem Zustand

### BA2 / Bethesda
- [ ] **AK-13:** Bethesda-Spiel: Mod toggelt -> KEIN BA2-Packing (kein Wine/BSArch im Log)
- [ ] **AK-14:** Bethesda-Spiel: Run-Button -> VOR Spielstart vollstaendiges Deploy MIT BA2-Packing
- [ ] **AK-15:** Bethesda-Spiel: Mod mit ESP/ESM toggelt + 500ms -> plugins.txt im Proton-Prefix aktualisiert

### UI-Feedback
- [ ] **AK-16:** Mod toggelt -> StatusBar zeigt sofort "Deploying..." / "Wird bereitgestellt..."
- [ ] **AK-17:** Deploy abgeschlossen -> StatusBar zeigt 3s lang "Mods deployed" / "Mods bereitgestellt"

### Safety Guards
- [ ] **AK-18:** Mod toggelt + <500ms Instanzwechsel -> Timer gestoppt, kein Deploy auf alter Instanz
- [ ] **AK-19:** Mod toggelt + <500ms Profilwechsel -> Timer gestoppt
- [ ] **AK-20:** Mod toggelt + <500ms App schliessen -> Timer gestoppt, `silent_purge()` raeumt auf
- [ ] **AK-21:** Keine Instanz geladen -> `_schedule_redeploy()` / `_do_redeploy()` wirft keinen Fehler
- [ ] **AK-23:** Instanz-/Profilwechsel fuehrt NICHT zu doppeltem Deploy

### Allgemein
- [ ] **AK-22:** i18n-Keys `status.deploying`, `status.deployed`, `status.deploy_skipped` in allen 6 Locales
- [ ] **AK-24:** Deploy-Vorgaenge geben `[DEPLOY]` und `[PURGE]` in der Konsole aus
- [ ] **AK-25:** `./restart.sh` startet ohne Fehler
