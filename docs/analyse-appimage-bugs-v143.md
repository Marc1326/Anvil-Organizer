# Analyse: AppImage v1.4.3 Bugs (CachyOS)

**Datum:** 2026-04-09  
**Quelle:** GitHub Issue von User + eigene Tests  
**Getestet auf:** CachyOS, AppImage v1.4.3 (release/Anvil_Organizer-1.4.3-x86_64.AppImage)

---

## 1. Gemeldete Bugs (User-Report)

| # | Bug | User-Beschreibung |
|---|-----|-------------------|
| A | Folder actions tun nichts | Klick auf Ordner-Icon (Downloads, Mods, Profiles) → keine Reaktion |
| B | Profile switching reagiert nicht | Profil-Wechsel auf MO2-Profil "default" → unresponsive |
| C | Custom path setup crasht | Setup → Custom Path setzen → SIGSEGV |
| D | Screenshot crasht | Screenshot-Versuch → `eventFilter` KeyboardInterrupt + SIGSEGV |
| E | Nexus API funktioniert nicht | *(von Marc beim eigenen Test gefunden)* |
| F | LOOT wird nicht erkannt | *(von Marc beim eigenen Test gefunden)* — rot "nicht gefunden" im LOOT-Tab |

### User-Fehlermeldungen

**Folder/Profile:**
```
/bin/sh: symbol lookup error: /bin/sh: undefined symbol: rl_trim_arg_from_keyseq
```

**Custom path:**
```
fish: Job 1, '~/Applications/Anvil_Organizer-…' terminated by signal SIGSEGV (Address boundary error)
```

**Screenshot:**
```
Error calling Python override of QMainWindow::eventFilter(): Traceback (most recent call last):
  File "anvil/mainwindow.py", line 909, in eventFilter
KeyboardInterrupt
fish: Job 1, '~/Applications/Anvil_Organizer-…' terminated by signal SIGSEGV (Address boundary error)
```

---

## 2. Was wir gefunden haben — bestätigte Anvil-Bugs

### Root Cause: LD_LIBRARY_PATH-Pollution durch PyInstaller

PyInstaller setzt beim Start `LD_LIBRARY_PATH` auf das `_internal/`-Verzeichnis des Bundles. Alle Kind-Prozesse (subprocess, xdg-open, flatpak, etc.) erben diese Umgebung und laden die **gebündelten** Libs statt der System-Libs.

**Beweis 1** — Laufendes AppImage v1.4.3 inspiziert:
```
$ cat /proc/<PID>/environ | tr '\0' '\n' | grep LD_LIBRARY
LD_LIBRARY_PATH=/tmp/.mount_Anvil_bdeIjP/usr/bin/_internal
```

**Beweis 2** — xdg-open mit dieser Umgebung getestet:
```bash
$ LD_LIBRARY_PATH=/tmp/.mount_Anvil_bdeIjP/usr/bin/_internal xdg-open /tmp
/bin/sh: symbol lookup error: /bin/sh: undefined symbol: rl_trim_arg_from_keyseq
Exit: 127
```
→ **Exakt der Fehler des Users, reproduziert auf Marcs System.**

**Beweis 3** — flatpak mit dieser Umgebung getestet:
```bash
$ LD_LIBRARY_PATH="$INTERNAL" flatpak info io.github.loot.loot
flatpak: .../libcrypto.so.3: version `OPENSSL_3.4.0' not found (required by /usr/lib/libostree-1.so.1)
flatpak: .../libssl.so.3: version `OPENSSL_3.2.0' not found (required by /usr/lib/libcurl.so.4)
Exit: 1
```

**Beweis 4** — Gebündelte readline ist ÄLTER als System-readline:
```
AppImage:  md5 7059c230...  335936 bytes (gebaut 07.04.)
System:    md5 2971602d...  388120 bytes (readline 8.3.003)
```

### Betroffene gebündelte Libs

- `libreadline.so.8` — crasht `/bin/sh` (bash) wegen ABI-Inkompatibilität
- `libcrypto.so.3` — alte OpenSSL, fehlt `OPENSSL_3.4.0` Symbol
- `libssl.so.3` — alte OpenSSL, fehlt `OPENSSL_3.2.0` und `OPENSSL_3.5.0`

### Bestätigte Bugs

**Bug A (Folder actions) — ANVIL-BUG, REPRODUZIERT:**
`subprocess.Popen(["xdg-open", ...])` in `mainwindow.py` (~20 Stellen, Zeilen 3330-3441) erbt LD_LIBRARY_PATH → xdg-open startet `/bin/sh` → bash lädt falsche libreadline → symbol lookup error.

**Bug E (Nexus API) — ANVIL-BUG, REPRODUZIERT:**
Log zeigt `keyring: failed to load API key: No module named 'keyring'`. Das Modul `keyring` fehlt in `hiddenimports` der `anvil-organizer.spec`. Ohne keyring kann der API-Key nicht geladen werden.

**Bug F (LOOT nicht erkannt) — ANVIL-BUG, REPRODUZIERT:**
`find_loot_binary()` in `loot_runner.py:18` → Schritt 3 ruft `subprocess.run(["flatpak", "info", ...])` → flatpak crasht an alter libcrypto/libssl → returncode 1 → "nicht gefunden".

### Weitere betroffene subprocess-Stellen (alle ohne env-Cleanup)

- `anvil/dialogs/mod_detail_dialog.py` — 4x xdg-open
- `anvil/widgets/settings_dialog.py` — 2x xdg-open
- `anvil/widgets/game_panel.py` — xdg-open + Proton/Wine-Aufrufe
- `anvil/core/update_checker.py` — git + xdg-open
- `anvil/core/nxm_handler.py` — xdesktop-open Registrierung
- `anvil/core/mod_installer.py` — 7z/unrar Aufrufe
- `anvil/core/ba2_packer.py` — Wine/BSArch (hat env=, aber ohne Cleanup)
- `anvil/core/loot/loot_runner.py` — QProcess für LOOT

---

## 3. Nicht reproduzierbar / unklar

**Bug B (Profile switching):**
Der Code-Pfad `_on_profile_changed()` (mainwindow.py:3611) nutzt **keine** Subprocesses direkt. File-I/O + `silent_deploy()`. Bei Marc funktioniert Profil-Wechsel im AppImage problemlos. Möglich dass der User den `rl_trim_arg_from_keyseq`-Fehler im Terminal einem Profil-Wechsel zuschreibt, obwohl er von einem vorherigen xdg-open stammt.

**Bug C (Custom path SIGSEGV):**
`QFileDialog.getExistingDirectory()` (settings_dialog.py:334). Bei Marc getestet (Video ~17s, Settings → Pfade-Tab) — kein Crash. Möglicherweise User-spezifisch (Wayland vs X11, andere GTK-Version, GPU-Treiber).

**Bug D (Screenshot SIGSEGV):**
**Es gibt keine Screenshot-Funktion in Anvil.** Kein Menü-Eintrag, kein Locale-String, kein Keyboard-Handler. Der User hat das System-Screenshot-Tool (Spectacle/PrintScreen auf KDE/CachyOS) benutzt. Der eventFilter-Traceback zeigt `KeyboardInterrupt` — entweder:
- User hat Ctrl+C im Terminal gedrückt
- PrintScreen-Key-Event trifft auf instabilen App-Zustand
- PySide6 kann Python-Exception während C++→Python Callback nicht sauber abfangen → SIGSEGV

**Kein Anvil-Bug.**

---

## 4. Warum Marc die Bugs A-D nicht reproduzieren kann

Marc und der User laufen beide auf CachyOS mit zeitnahen Updates — die Systeme sollten quasi identisch sein. ABER: Die gebündelten Libs im AppImage sind vom **Build-Zeitpunkt** (07.04.) und Marc hat sein System seitdem aktualisiert. Die **aktuelle** dist/ hat identische Libs wie das System (md5 stimmt überein), aber das **released** AppImage v1.4.3 hat ältere Libs.

Bei Marcs eigenem AppImage-Test (Video):
- Instanz-Wechsel, Profil-Wechsel, Pfade-Tab → funktioniert alles
- LOOT-Erkennung → rot, nicht gefunden (Bug F bestätigt)
- Nexus API → funktioniert nicht (Bug E bestätigt)
- Folder-Button (xdg-open) → **müsste** eigentlich auch scheitern (da LD_LIBRARY_PATH pollution bewiesen), aber im Video nicht explizit als fehlgeschlagen sichtbar

Der LD_LIBRARY_PATH-Fehler bei xdg-open ist **reproduzierbar** wenn man die Umgebung des laufenden AppImage simuliert. Dass Marc im UI-Test keinen Unterschied bemerkt hat, könnte daran liegen, dass `subprocess.Popen` nicht blockiert und der Fehler nur im Terminal erscheint (kein UI-Feedback).

---

## 5. Lösungsansatz

### Fix 1: Subprocess-Environment bereinigen (KRITISCH)

Neue Utility `anvil/core/subprocess_env.py`:
```python
def clean_subprocess_env() -> dict:
    """Return env dict with LD_LIBRARY_PATH restored to pre-PyInstaller state."""
    env = os.environ.copy()
    orig = os.environ.get("LD_LIBRARY_PATH_ORIG")
    if orig is not None:
        env["LD_LIBRARY_PATH"] = orig
    elif "LD_LIBRARY_PATH" in env:
        del env["LD_LIBRARY_PATH"]
    return env
```

Anwenden auf ALLE `subprocess.Popen/run`-Aufrufe die System-Tools starten (xdg-open, flatpak, git, 7z, etc.).

### Fix 2: keyring in PyInstaller-Bundle (Nexus API)

`anvil-organizer.spec` → `hiddenimports` erweitern:
```python
hiddenimports=[
    ...
    'keyring',
    'keyring.backends',
]
```

### Fix 3: QFileDialog SIGSEGV (optional/defensiv)

Wenn `getattr(sys, "frozen", False)`: `QFileDialog.Option.DontUseNativeDialog` setzen. Verhindert dass der native Dialog System-Libs über LD_LIBRARY_PATH lädt. Nicht reproduziert, daher optional.

### Betroffene Dateien

- `anvil/core/subprocess_env.py` — **NEU**
- `anvil-organizer.spec` — hiddenimports ergänzen
- `anvil/mainwindow.py` — ~20 Stellen (xdg-open)
- `anvil/dialogs/mod_detail_dialog.py` — 4 Stellen
- `anvil/widgets/settings_dialog.py` — 2 Stellen
- `anvil/widgets/game_panel.py` — mehrere Stellen
- `anvil/core/update_checker.py` — subprocess Aufrufe
- `anvil/core/nxm_handler.py` — subprocess Aufrufe
- `anvil/core/mod_installer.py` — 7z/unrar
- `anvil/core/ba2_packer.py` — Wine env erweitern
- `anvil/core/loot/loot_runner.py` — QProcess + find_loot_binary

---

## 6. Zusätzliches User-Feedback

Der User erwähnt auch dass Anvil Ordner mit Punkt-Prefix erstellt (`.mods`, `.profiles`, `.downloads`) und er lieber MO2-kompatible Namen ohne Punkt hätte. Separates Thema, nicht Teil dieses Bugfixes.
