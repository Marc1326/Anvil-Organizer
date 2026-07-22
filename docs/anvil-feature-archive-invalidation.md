# Feature-Spec: Archive Invalidation (#15)

**Status:** Geplant (verifiziert gegen echten Code am 2026-06-28)
**Issue:** #15 „Feature: Automatic Archive Invalidation in Settings" (Labels: `disabled-feature`, `enhancement`)
**Betrifft:** Skyrim SE, Fallout 4 (Bethesda Creation Engine)

---

## 1. Problem / Ziel

**Issue-Wortlaut (#15):** „The automatic archive invalidation option in settings is
disabled." — UI-Element in den Settings vorhanden, aber deaktiviert, kein Backend.

Bethesda-Engines (Skyrim SE, Fallout 4) laden Spiel-Assets primär aus den
gepackten Archiven (`.bsa` / `.ba2`). Lose Dateien im `Data`-Ordner (Texturen,
Meshes, Scripts) greifen nur dann zuverlässig, wenn „Archive Invalidation" aktiv
ist. Ohne sie kann das Archiv die lose Mod-Datei überschatten (typisches Symptom:
Mod installiert, aber im Spiel ohne Wirkung).

Gesteuert wird das über zwei Einträge in der Custom-INI (verifiziert gegen die
Vortex-Referenz `extensions/gamebryo-archive-invalidation`, siehe §3):
`[Archive] bInvalidateOlderFiles=1` und `sResourceDataDirsFinal=` (leer).

**Ziel:** Die in den Settings vorhandene, aber deaktivierte Checkbox
„Automatische Archiv-Invalidierung" funktionsfähig machen:
- Aktivieren → INI-Einträge idempotent in die Custom-INI schreiben (vorhandene
  Nutzer-/BA2-Werte respektieren).
- Deaktivieren/Purge → exakt diese von Anvil gesetzten Einträge zurücknehmen.
- Wert pro Instanz persistieren — über das **bereits existierende** Flag
  `auto_archive` (siehe §2.6, kein neuer Key nötig).

**Abgrenzung:** Dies ist **nicht** das BA2-Packing (`ba2_packer.py`). Packing
erzeugt eigene `anvil_*.ba2`-Archive und registriert sie via `sResourceArchiveList2`.
Archive Invalidation regelt die umgekehrte Richtung: dass **lose** Dateien Vorrang
bekommen. Beide schreiben in dieselbe Custom-INI und dieselbe `[Archive]`-Section,
aber **andere Keys** → Reihenfolge/Backup beachten (siehe §3 und §8).

---

## 2. Phasen-Rückgrat (Bau-Reihenfolge nach steigendem Risiko)

| # | Phase | Inhalt | Risiko | Testbar nach Phase? |
|---|-------|--------|--------|---------------------|
| 1 | Persistenz-Lücke schließen | `save_instance()` um `auto_archive`-Branch ergänzen (analog `local_inis`); Default-Lesen aus `idata["auto_archive"]` | sehr niedrig | Ja — Wert überlebt Settings-Speichern + Neu-Öffnen |
| 2 | Plugin-Attribute | `SupportsArchiveInvalidation`, `ArchiveInvalidationIniFile`, `ArchiveInvalidationSection`, `ArchiveInvalidationEntries` in `base_game.py` (Default aus/leer), in Skyrim SE + FO4 setzen | sehr niedrig | Ja — `py_compile`, Attribute am Plugin abfragbar |
| 3 | INI-Modul | `archive_invalidation.py` mit `ini_path/is_supported/enable/disable` nach `ba2_packer`-Muster (ConfigParser, `optionxform=str`, cp1252, eigenes Backup) | mittel | Ja — Unit-artiger Test auf Dummy-INI: enable/disable idempotent |
| 4 | UI-Verdrahtung Settings | Checkbox `settings_dialog.py:147` echt machen, Laden aus `idata`, Speichern in `accept()` | niedrig | Ja — Checkbox aktiv, Zustand persistiert |
| 5 | Deploy-/Purge-Hook | `enable()` in `silent_deploy()`, `disable()` in `silent_purge()`, gated durch Instanz-Flag + `SupportsArchiveInvalidation` | mittel | Ja — Deploy schreibt INI, Purge nimmt zurück |
| 6 | Profil-Dialog (optional) | `profile_dialog.py:83-85` aktivieren oder read-only spiegeln (offene Frage 2) | niedrig | Ja — Checkbox-Zustand korrekt |
| 7 | i18n | neue Desc-Keys in alle 7 Locales | sehr niedrig | Ja — App startet, kein fehlender Key |

> Reihenfolge bewusst: zuerst die unsichtbaren Daten-/Persistenz-Schichten (1-3),
> dann erst die sichtbare UI (4) und der Deploy-Eingriff (5), der echte Dateien
> auf der Platte verändert (höchstes Risiko, daher spät und nach Test des Moduls).

---

## 3. Ist-Zustand im Code (nur verifizierte Anker)

### 3.1 Wo ist die Funktion deaktiviert?

| Ort | Datei:Zeile | Verifizierter Zustand |
|-----|-------------|-----------------------|
| Settings-Dialog, Gruppe „Profil-Standardeinstellungen" | `anvil/widgets/settings_dialog.py:147` | `prof_layout.addWidget(_disabled(QCheckBox(tr("settings.auto_archive_invalidation"))))` — Checkbox ohne `self._`-Referenz, dauerhaft disabled, kein Save |
| `_disabled`-Helper | `anvil/widgets/settings_dialog.py:73` | innere Funktion, setzt `setEnabled(False)` + Tooltip `tr("settings.coming_soon")` |
| Profil-Auswahl-Dialog | `anvil/widgets/profile_dialog.py:83-85` | `cb_archive = QCheckBox(tr("label.auto_archive_invalidation"))` / `setChecked(True)` / `setEnabled(False)` — lokale Variable, kein Save |

### 3.2 TEILWEISE BEREITS GEBAUT — Instanz-Assistent (wichtig!)

Es existiert bereits eine **funktionierende, persistierte** Archive-Invalidation-
Checkbox im Instanz-Assistenten:

- `anvil/widgets/instance_wizard.py:369-375` — `self._auto_archive_cb = QCheckBox(tr("wizard.auto_archive"))` plus Beschriftung `wizard.auto_archive_desc`.
- `anvil/widgets/instance_wizard.py:596` — `auto_archive = self._auto_archive_cb.isChecked()`.
- `anvil/widgets/instance_wizard.py:617` — wird als `auto_archive=auto_archive` an die Instanz-Erstellung durchgereicht.
- `anvil/core/instance_manager.py:88` (`create_instance`-Signatur) und `:373` (`write_instance`-Signatur) nehmen `auto_archive: bool = False` an.
- `anvil/core/instance_manager.py:392` — `s.setValue("auto_archive", auto_archive)` schreibt in die `[General]`-Gruppe der `.anvil.ini`.

→ Der **Persistenz-Key heißt `auto_archive`** (General-Gruppe), nicht
`auto_archive_invalidation`. Beim Laden wird er automatisch übernommen, weil
`_read_ini()` ALLE Keys der General-Gruppe in das `idata`-Dict liest
(`instance_manager.py:411-414`). D.h. `idata["auto_archive"]` ist nach Laden
verfügbar.

Was FEHLT: (a) das Backend, das dieses Flag liest und INI-Einträge schreibt;
(b) der Persist-Branch in `save_instance()` (siehe 3.6); (c) die echten Checkboxen
in Settings/Profil-Dialog. Die UI im Assistenten ist also gebaut, aber „läuft ins
Leere", weil niemand das Flag auswertet.

### 3.3 INI-Muster als Referenz (`ba2_packer.py`)

`anvil/core/ba2_packer.py` enthält ein vollständiges, idempotentes INI-Muster:

- `from configparser import ConfigParser` (`ba2_packer.py:23`).
- `update_ini()` (`ba2_packer.py:531`) und `restore_ini()` (`ba2_packer.py:595`).
- `config.optionxform = str` → Key-Casing bleibt erhalten (`:560`, `:629`).
- Encoding **`cp1252`** beim Lesen und Schreiben (`:563`, `:587`, `:631`, `:647`).
- Backup vor Änderung nach `<inifile>.anvil_backup` via `shutil.copy2` (`:553-555`).
  Hinweis: dieser Backup wird bei JEDEM `update_ini`-Aufruf überschrieben, nicht
  nur einmalig (`:554-555`).
- Idempotenter Merge: nur den eigenen Key anfassen, andere Keys/Sections behalten
  (`:567-583`).

Dieses Muster ist die Vorlage für das neue Modul (gleiches Encoding, gleiche
Backup-Strategie, gleiche Merge-Logik) — aber mit **eigenem** Backup-Suffix
(`.anvil_ai_backup`), damit BA2 und Archive Invalidation sich nicht die Sicherung
überschreiben.

### 3.4 Documents-/Proton-Pfad-Auflösung

- `BaseGame.protonPrefix()` — `anvil/plugins/base_game.py:295`.
- `BaseGame.gameDocumentsDirectory()` — `anvil/plugins/base_game.py:429` — löst
  `prefix / self._WIN_DOCUMENTS` auf, prüft `path.is_dir()` (`:437-444`).
- `_WIN_DOCUMENTS`-Default leer in `base_game.py:177`.
- Skyrim SE: `anvil/plugins/games/game_skyrimse.py:106` → `drive_c/users/steamuser/Documents/My Games/Skyrim Special Edition`.
- Fallout 4: `anvil/plugins/games/game_fallout4.py:100` (`_WIN_DOCUMENTS`); FO4 überschreibt zusätzlich `gameDocumentsDirectory()` explizit ab `game_fallout4.py:123`.
- `BaseGame.ba2_ini_path()` — `base_game.py:473`. **Achtung:** gated durch
  `if not self.NeedsBa2Packing or not self.Ba2IniFile: return None` (`:475`) →
  **nicht direkt wiederverwendbar**, wenn BA2-Packing aus ist. Das neue Modul muss
  den Pfad selbst aus `gameDocumentsDirectory() / ArchiveInvalidationIniFile`
  bilden.

### 3.5 INI-Dateien / Custom-INI je Spiel

- Skyrim SE: `iniFiles()` → `["Skyrim.ini", "SkyrimPrefs.ini", "SkyrimCustom.ini"]` (`game_skyrimse.py:301`); Custom-INI = `SkyrimCustom.ini` (`Ba2IniFile`, `game_skyrimse.py:95`).
- Fallout 4: `iniFiles()` → `["Fallout4.ini", "Fallout4Prefs.ini", "Fallout4Custom.ini"]` (`game_fallout4.py:268`); Custom-INI = `Fallout4Custom.ini` (`Ba2IniFile`, `game_fallout4.py:86`).
- Bestehende BA2-Attribute (Vorbild): `Ba2IniSection` (`base_game.py:166`), `Ba2IniKey` (`:169`), `Ba2IniFile` (`:172`). Skyrim/FO4 setzen `Ba2IniKey = "sResourceArchiveList2"` (`game_skyrimse.py:94`, `game_fallout4.py:85`).

> Die `*Custom.ini` ist der vorgesehene Override-Ort und wird vom Launcher nicht
> überschrieben. Daher schreibt Anvil dorthin (wie BA2).

### 3.6 Persistenz-Flow (Settings)

- Laden beim Öffnen, Vorbild: `self._idata.get("local_inis", "true")` (Checkbox-Erzeugung `settings_dialog.py:139`, `setChecked()` `:140-141`), analog `local_saves` (`:143-145`).
- `SettingsDialog.accept()` — `anvil/widgets/settings_dialog.py:1050`. Instanz-Schalter:
  `idata["local_inis"] = self._cb_local_inis.isChecked()` / `idata["local_saves"] = ...`
  / `self._instance_manager.save_instance(cur, idata)` (`:1121-1123`).
- **LÜCKE:** `InstanceManager.save_instance()` persistiert aktuell NUR
  `selected_profile`, `game_path`, `local_inis`, `local_saves`
  (`instance_manager.py:300-309`). Es gibt **keinen** Branch für `auto_archive`.
  → Muss ergänzt werden, sonst geht der in den Settings gesetzte Wert beim
  Speichern verloren (der Assistent schreibt ihn nur einmal bei Erstellung).

### 3.7 Deploy-/Purge-Einhängepunkte (`game_panel.py`)

- `silent_deploy()` — `anvil/widgets/game_panel.py:653`. BA2-Block ab `:668`,
  `packer.update_ini(ba2_names)` bei `:693`. Danach `plugins.txt`-Write ab `:705`.
  → Natürlicher Punkt, um Archive Invalidation **anzuwenden** (nach dem BA2-Block,
  z.B. vor/neben dem plugins.txt-Write).
- `silent_purge()` — `anvil/widgets/game_panel.py:769`. BA2-Block ab `:776`,
  `packer.cleanup_ba2s()` / `packer.restore_ini()` bei `:785-786`. Danach
  plugins.txt-Entfernung ab `:788`.
  → Punkt, um Archive Invalidation **zurückzunehmen**.

> Hinweis: Es gibt zusätzlich `silent_deploy_fast()` (`:748`), das KEIN BA2/INI
> anfasst (nur plugins.txt). Archive-Invalidation-Hook gehört NUR in den vollen
> `silent_deploy()`/`silent_purge()`-Pfad, nicht in die Fast-Variante.

---

## 4. Lösung / Ansatz

### 4.1 Genaue INI-Einträge (verifiziert gegen Vortex-Referenz)

Beide Spiele (Creation Engine), Section `[Archive]` in der jeweiligen `*Custom.ini`:

```
[Archive]
bInvalidateOlderFiles=1
sResourceDataDirsFinal=
```

Quelle der Verifikation (Pfad relativ zu `/home/mob/Projekte/`, **nicht** zum Anvil-Arbeitsverzeichnis):
`/home/mob/Projekte/Fremd-Mod Manager/Vortex/Vortex-master/extensions/gamebryo-archive-invalidation/src/index.ts:89-90`
setzt exakt `iniFile.data.Archive.bInvalidateOlderFiles = 1` und
`sResourceDataDirsFinal = ""`. Das in der Bethesda-Community etablierte Paar.

- `bInvalidateOlderFiles=1` — weist die Engine an, lose Dateien zu bevorzugen.
- `sResourceDataDirsFinal=` — leerer Wert; hebt die „nur aus Archiv"-Einschränkung
  für die Default-Unterordner auf.

> Beide Keys liegen in derselben `[Archive]`-Section wie der BA2-Key
> `sResourceArchiveList2`, sind aber **andere Keys**. Der `ConfigParser`-Merge
> behält die jeweils anderen Keys bei. Niemals die ganze Section ersetzen.

### 4.2 Plugin-Attribute (datengetrieben, keine hardcoded Pfade)

Neue Klassen-Attribute auf `BaseGame` (Defaults leer/aus), analog zu den
`Ba2*`-Attributen:

```python
SupportsArchiveInvalidation: bool = False
ArchiveInvalidationIniFile: str = ""        # z.B. "SkyrimCustom.ini"
ArchiveInvalidationSection: str = "Archive"
ArchiveInvalidationEntries: dict[str, str] = {}   # {"bInvalidateOlderFiles": "1", "sResourceDataDirsFinal": ""}
```

In `game_skyrimse.py` / `game_fallout4.py`:

```python
SupportsArchiveInvalidation = True
ArchiveInvalidationIniFile = "SkyrimCustom.ini"   # bzw. "Fallout4Custom.ini"
ArchiveInvalidationSection = "Archive"
ArchiveInvalidationEntries = {
    "bInvalidateOlderFiles": "1",
    "sResourceDataDirsFinal": "",
}
```

> `ArchiveInvalidationIniFile` zeigt absichtlich auf dieselbe Custom-INI wie
> `Ba2IniFile`. Pfad: `gameDocumentsDirectory() / ArchiveInvalidationIniFile`
> (eigener Resolver, weil `ba2_ini_path()` auf `NeedsBa2Packing` gated ist).

### 4.3 Neues Modul `anvil/core/archive_invalidation.py`

Eigene Klasse `ArchiveInvalidator`, semantisch getrennt von `ba2_packer`, aber
mit denselben Konventionen (`ConfigParser`, `optionxform=str`, `cp1252`), eigenes
Backup `.anvil_ai_backup`:

```python
class ArchiveInvalidator:
    def __init__(self, game_plugin): ...
    def ini_path(self) -> Path | None:
        # gameDocumentsDirectory() / plugin.ArchiveInvalidationIniFile, sonst None
    def is_supported(self) -> bool:
        # plugin.SupportsArchiveInvalidation and ini_path() is not None
    def enable(self) -> bool:
        # idempotent: Backup einmalig (nur wenn keins existiert), Section anlegen
        #   falls fehlt; je Key aus ArchiveInvalidationEntries: setzen/überschreiben.
        #   Alle übrigen Keys (inkl. sResourceArchiveList2) unberührt lassen.
    def disable(self) -> bool:
        # nimmt NUR die von Anvil gesetzten Keys zurück: Restore aus
        #   .anvil_ai_backup, sonst gezieltes Entfernen genau dieser Keys;
        #   leere Section danach entfernen.
```

**Idempotenz & Schonung:**
- Backup nach `<inifile>.anvil_ai_backup` nur, wenn noch keins existiert
  (Verbesserung gegenüber `ba2_packer`, das jedes Mal überschreibt) → mehrfaches
  `enable` zerstört kein Original.
- `enable` fasst ausschließlich die Keys aus `ArchiveInvalidationEntries` an.
- `disable` restauriert aus `.anvil_ai_backup`; ohne Backup nur Key-genau
  entfernen (Fallback wie `ba2_packer.restore_ini`). Immer frisch von Disk lesen.

### 4.4 Persistenz (Phase 1 — zuerst!)

`instance_manager.save_instance()` um einen Branch erweitern (analog `local_inis`,
direkt nach `instance_manager.py:308`):

```python
if "auto_archive" in data:
    s.setValue("auto_archive", data["auto_archive"])
```

So überlebt der in den Settings gesetzte Wert das Speichern. Laden funktioniert
bereits über `_read_ini()` (`idata["auto_archive"]`).

### 4.5 UI-Verdrahtung

`settings_dialog.py`:
- Zeile 147 ersetzen durch eine echte, referenzierte Checkbox:
  `self._cb_archive_inval = QCheckBox(tr("settings.auto_archive_invalidation"))`,
  Checked aus `str(self._idata.get("auto_archive", "false")).lower() in ("true","1")`
  (analog `local_inis`: Erzeugung `:139`, `setChecked()` `:140-141`). **Nicht** mehr `_disabled(...)`.
- In `accept()` nach `:1122`:
  `idata["auto_archive"] = self._cb_archive_inval.isChecked()`.

`profile_dialog.py:83-85`: `cb_archive` entweder aktivieren + an Instanz-Config
binden, oder read-only auf `idata["auto_archive"]` spiegeln (offene Frage 2).

`game_panel.py`:
- In `silent_deploy()` nach dem BA2-Block (nach `:697`/vor `:705`): wenn
  Instanz-Flag `auto_archive` true UND `plugin.SupportsArchiveInvalidation`, dann
  `ArchiveInvalidator(plugin).enable()`. Instanz-Flag aus
  `instance_manager.load_instance(...)["auto_archive"]` lesen (kein neuer Key).
- In `silent_purge()` nach `restore_ini()` (`:786`):
  `ArchiveInvalidator(plugin).disable()` (immer, damit Purge sauber zurücknimmt).

---

## 5. Betroffene Dateien

| Datei | Art | Änderung |
|-------|-----|----------|
| `anvil/core/archive_invalidation.py` | **NEU** | `ArchiveInvalidator` (enable/disable/ini_path/is_supported), idempotent, cp1252, Backup `.anvil_ai_backup` |
| `anvil/core/instance_manager.py` | Edit | `save_instance()` um `auto_archive`-Branch (nach `:308`) |
| `anvil/plugins/base_game.py` | Edit | Neue Attribute `SupportsArchiveInvalidation`, `ArchiveInvalidationIniFile`, `ArchiveInvalidationSection`, `ArchiveInvalidationEntries` (Default aus/leer) |
| `anvil/plugins/games/game_skyrimse.py` | Edit | Attribute setzen (`SkyrimCustom.ini`, `[Archive]`, Entries) |
| `anvil/plugins/games/game_fallout4.py` | Edit | Attribute setzen (`Fallout4Custom.ini`, `[Archive]`, Entries) |
| `anvil/widgets/settings_dialog.py` | Edit | Checkbox echt machen (`:147`), Laden aus `idata["auto_archive"]`, Speichern in `accept()` (`:1122`) |
| `anvil/widgets/profile_dialog.py` | Edit | `cb_archive` (`:83-85`) aktivieren oder read-only spiegeln |
| `anvil/widgets/game_panel.py` | Edit | `enable()` in `silent_deploy()` (nach `:697`), `disable()` in `silent_purge()` (nach `:786`) |
| `anvil/locales/{de,en,es,fr,it,pt,ru}.json` (7×) | Edit | neuer Desc-Key (§7); `settings.auto_archive_invalidation` existiert bereits |

---

## 6. Umsetzungsschritte (entlang Phasen-Rückgrat §2)

1. **Persistenz:** `save_instance()`-Branch für `auto_archive` ergänzen.
   `py_compile`. Test: Wert überlebt Speichern.
2. **Plugin-Attribute** in `base_game.py` (Defaults aus/leer) und in
   `game_skyrimse.py` + `game_fallout4.py` setzen. `py_compile`.
3. **Modul `archive_invalidation.py`** nach `ba2_packer`-Muster schreiben
   (ConfigParser, `optionxform=str`, cp1252, `.anvil_ai_backup`, Backup nur einmal,
   nur eigene Keys). Eigene Pfad-Auflösung via `gameDocumentsDirectory()`.
4. **Settings-Dialog:** Checkbox referenzierbar machen, Default aus
   `idata["auto_archive"]`, Speichern in `accept()`.
5. **game_panel:** `enable()` im vollen Deploy-Pfad (gated durch Instanz-Flag +
   `SupportsArchiveInvalidation`), `disable()` im Purge-Pfad. NICHT in
   `silent_deploy_fast()`.
6. **Profil-Dialog:** `cb_archive` aktivieren oder read-only spiegeln (offene
   Frage 2).
7. **i18n:** neuer Desc-Key in allen 7 Locales.
8. **`./restart.sh`** ausführen, Log auf Tracebacks/NameError/ImportError prüfen.
   Manuell: Skyrim-SE-Instanz, Checkbox an → Deploy → `SkyrimCustom.ini` prüfen;
   Checkbox aus / Purge → Einträge weg, restliche Werte intakt.
9. **DoD-Review:** 4 parallele Review-Agents (Bugs, Signal/Scope,
   Architektur/Referenz, Issue-Erfüllung) — erst committen, wenn alle ohne Findings.

---

## 7. i18n (tr-Keys, 7 Locales: de, en, es, fr, it, pt, ru)

**Bereits vorhanden** (nichts zu tun):
- `settings.auto_archive_invalidation` (de.json:679 etc.)
- `label.auto_archive_invalidation` (de.json:357 etc.)
- `wizard.auto_archive` + `wizard.auto_archive_desc` (de.json:931-932 etc.)
- `settings.coming_soon` (de.json:807)

**Neu hinzuzufügen in allen 7 Locales** (Namespace `settings`):

| Key | DE (Vorschlag) | Zweck |
|-----|----------------|-------|
| `settings.auto_archive_invalidation_desc` | „Lose Mod-Dateien erhalten Vorrang vor den gepackten Spiel-Archiven (BSA/BA2)." | Tooltip/Hinweis an der jetzt aktiven Checkbox |

> Bei der nun aktiven Settings-Checkbox darf NICHT mehr `_disabled(...)` verwendet
> werden → der `coming_soon`-Tooltip entfällt dort automatisch.
> Vorbild für einen Desc-Key in der Wizard-Gruppe ist `local_inis_desc`
> (de.json:928). CLAUDE.md nennt 6 Locales, real existieren 7 inkl. `ru.json`
> → alle 7 pflegen.

---

## 8. Akzeptanzkriterien

- [ ] Checkbox „Automatische Archiv-Invalidierung" in den Settings ist **aktiv**
      (nicht mehr `_disabled`), Zustand wird pro Instanz über `auto_archive`
      gespeichert und beim erneuten Öffnen korrekt geladen.
- [ ] `save_instance()` persistiert `auto_archive` (Wert überlebt
      Settings-Speichern, nicht nur Instanz-Erstellung).
- [ ] Bei aktivem Flag + Skyrim-SE-Deploy stehen in `SkyrimCustom.ini` unter
      `[Archive]`: `bInvalidateOlderFiles=1` und `sResourceDataDirsFinal=` (leer).
      Analog Fallout 4 in `Fallout4Custom.ini`.
- [ ] **Idempotent:** Zweimaliges Aktivieren/Deployen erzeugt keine doppelten
      Einträge und kein zerstörtes Backup (Backup nur einmal angelegt).
- [ ] **Werte-Schonung:** Vorhandene andere Keys in `[Archive]` (z.B.
      `sResourceArchiveList2` vom BA2-Packing) und Nutzer-eigene Einträge bleiben
      beim Aktivieren erhalten.
- [ ] Deaktivieren/Purge nimmt **nur** die von Anvil gesetzten Keys zurück
      (Restore aus `.anvil_ai_backup`, sonst gezieltes Entfernen); restliche INI
      unverändert.
- [ ] Bei Nicht-Bethesda-Spielen (`SupportsArchiveInvalidation = False`) passiert
      nichts; kein Crash, kein INI-Zugriff. Auch `silent_deploy_fast()` fasst keine
      INI an.
- [ ] `ini_path()` liefert `None`, wenn der Proton-Prefix/Documents-Pfad nicht
      existiert → `enable()/disable()` sind no-op und loggen sauber, kein Crash.
- [ ] Encoding der geschriebenen INI ist `cp1252`, Key-Casing bleibt erhalten.
- [ ] Neuer Desc-Key in allen 7 Locales vorhanden (de, en, es, fr, it, pt, ru).
- [ ] `./restart.sh` startet ohne Traceback / NameError / ImportError.
- [ ] `python -m py_compile` für alle geänderten Dateien erfolgreich.

---

## 9. Aufwand / Risiko

**Aufwand:** Gering–mittel. Das idempotente INI-Muster existiert bereits
(`ba2_packer.py`) und wird übernommen; Pfadauflösung (`gameDocumentsDirectory`),
Deploy-/Purge-Hooks und ein bereits persistiertes Flag (`auto_archive`) sind
vorhanden. Hauptarbeit: neues Modul (~120 Zeilen), `save_instance`-Branch,
4 kleine UI-/Plugin-Edits, 1 neuer Locale-Key × 7. Schätzung: 1 Arbeitssitzung.

**Risiken:**
1. **Geteilte `[Archive]`-Section / Custom-INI mit BA2-Packing.** Beide Features
   schreiben in dieselbe Datei/Section, mit getrennten Backups (`.anvil_backup`
   vs. `.anvil_ai_backup`). Risiko: bei verschachteltem enable/disable +
   BA2-update/restore könnte ein Datei-Restore das jeweils andere Feature
   überschreiben. **Mitigation:** Nie die ganze Section ersetzen, immer frisch
   von Disk mergen, nur eigene Keys anfassen; `disable` defensiv Key-genau, nicht
   Datei-genau (Backup-Restore nur als Fallback).
2. **Wirksamkeit auf Creation Engine.** Die Vortex-Referenz ordnet diese Keys der
   `gamebryo`-Familie zu (ältere Engine). Für Skyrim SE / FO4 ist die praktische
   Wirkung von `bInvalidateOlderFiles` umstritten; `sResourceDataDirsFinal=` ist
   der wirksamere Teil. Die Keys schaden nicht. **Mitigation:** beide Keys setzen
   und am echten Skyrim-SE-Setup gegentesten (offene Frage 1).
3. **Documents-Pfad nicht auflösbar** (Proton-Prefix existiert noch nicht, Spiel
   nie gestartet). `ini_path()` → `None` → `enable()` muss no-op sein und sauber
   loggen, nicht crashen.
4. **Falsche-Key-Falle (vermieden):** Erster Spec-Entwurf nahm einen neuen Key
   `auto_archive_invalidation` an. Real heißt das persistierte Flag `auto_archive`
   (General-Gruppe), bereits vom Assistenten geschrieben — kein neuer Key, sonst
   zwei konkurrierende Wahrheiten.
5. **CLAUDE.md spricht von 6 Locales, real 7** (`ru.json`). Falle: `ru` vergessen.

**Offene Fragen an Marc (nummeriert):**
1. Soll ich die genaue Wirksamkeit (`bInvalidateOlderFiles` vs.
   `sResourceDataDirsFinal=`) vor der Umsetzung an deinem echten Skyrim-SE-
   Proton-Setup verifizieren, oder reicht das etablierte Eintrags-Paar (Vortex)?
2. Soll die Checkbox im Profil-Auswahl-Dialog (`profile_dialog.py:83`) funktional
   gemacht werden, oder nur die in den Settings, und die Profil-Checkbox spiegelt
   read-only? (Ich empfehle: pro **Instanz** über `auto_archive` als einzige
   Quelle der Wahrheit; Profil-Dialog read-only.)
3. Soll die bereits funktionierende Assistenten-Checkbox (`wizard.auto_archive`)
   denselben `auto_archive`-Wert vorbelegen und mit der Settings-Checkbox
   konsistent bleiben (empfohlen)?
