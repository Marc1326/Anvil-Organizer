# Bugfix-Plan: Mod-Installation Starfield (und alle Games)

Stand: 17.04.2026

---

## Bug A — already_installed erkennt Wildcard-Pfade nicht
**Status: COMMITTED (1d62f10)**

`Path.exists()` behandelt Wildcards als Literal. Address Library mit
`Data/SFSE/Plugins/versionlib-*.bin` wurde nie als "bereits installiert" erkannt.

**Fix:** Neue Helper `_path_matches()` nutzt `Path.glob()` bei Wildcards.
Betrifft Address Library SKSE (Skyrim SE) und SFSE (Starfield).

---

## Bug B — _find_install_root doppelter Ordner bei Wildcards
**Status: OFFEN**

`mod_installer.py:370` — `rel.find("versionlib-*.bin")` sucht den Literal-String
mit `*`. Matcht nie. Fallback: gesamter Extract-Ordner als Root.

**Konsequenz:** Address Library landet als `<game>/Data/SFSE/SFSE/Plugins/*.bin`
(doppeltes SFSE). Auf Disk bestätigt: 38 Files im falschen Ordner.

**Fix:**
- Signatur `_find_install_root(temp_dir, patterns)` erweitern um
  `detect_installed` und `target` aus dem FrameworkMod
- Aus `detect_installed[0]` den Target-Prefix abziehen → erwarteter Suffix
  (z.B. `Plugins/versionlib-*.bin`)
- Im rglob nach File suchen dessen Pfad auf diesen Suffix matcht (fnmatch)
- Install-root = Pfad-Prefix vor dem Suffix
- Fallback: alter Code (literale Patterns) → bestehende Frameworks unverändert
- Aufrufer: `install_framework()` übergibt `framework` statt nur `framework.pattern`

**Betrifft:** Address Library SKSE + SFSE. Alle anderen Frameworks haben
literale Patterns und laufen im Fallback identisch weiter.

**Risiko:** Mittel. Signatur-Änderung + neue Logik. Unit-Tests zwingend.

**Disk-Bereinigung:** Nach dem Fix `<game>/Data/SFSE/SFSE/` manuell löschen.

---

## Bug C — Framework-Heuristik: Doppel-Dialog + "Nein = Mod weg"
**Status: OFFEN — das ist der kritischste Bug**

### Was passiert

`detect_possible_framework()` ist eine Score-Heuristik die rät ob ein Archiv
ein unbekanntes Framework sein könnte (DLL vorhanden, Config daneben, keine
ESP/ESM → Score ≥ 60 → Dialog "Ist das ein Framework?").

**Problem 1 — Doppel-Dialog:**
Die Heuristik läuft an ZWEI Stellen:
1. Pre-Filter `_try_install_as_framework` (mainwindow.py:2031)
2. Install-Loop `_install_archives` (mainwindow.py:2151)

Wenn der User beim Pre-Filter "Nein" klickt → Mod geht in den Install-Loop →
dort läuft die Heuristik NOCHMAL → Dialog NOCHMAL.

**Problem 2 — "Nein" = Mod weg:**
Im Install-Loop (Zeile 2193-2196) bei "Nein":
```python
# User declined — don't install, keep in downloads
shutil.rmtree(temp_dir, ignore_errors=True)
continue  # ← Mod wird KOMPLETT übersprungen, NICHT normal installiert!
```
Die Mod wird weder als Framework noch als normaler Mod installiert. Einfach weg.
Keine Fehlermeldung.

### Wer ist betroffen

JEDER DLL-only Mod ohne .esp/.esm/.ba2 bekommt Score ≥ 65:
- SFSE-Plugin-Mods (Starfield): Score 65
- F4SE-Plugin-Mods (Fallout 4): Score 65
- SKSE-Plugin-Mods (Skyrim SE): Score 65
- RED4ext-Plugin-Mods (Cyberpunk): Score 75
- ASI-Mods (RDR2): Score 75

Bei Cyberpunk ist das Problem weniger sichtbar weil dort 10 Frameworks
definiert sind — die meisten DLL-Mods werden vorher von `is_framework_mod()`
als BEKANNTES Framework erkannt und kommen nie bei der Heuristik an.

### Fix

Die Heuristik hat ihren Zweck (unbekannte Frameworks erkennen) und bleibt.
Aber sie darf nicht doppelt laufen und "Nein" darf nicht "Mod weg" bedeuten.

**Änderung 1:** Heuristik-Block aus `_try_install_as_framework` entfernen
(Zeile 2031-2075). Der Pre-Filter prüft dann NUR noch `is_framework_mod()`
(bekannte Frameworks aus dem Game-Plugin). Das eliminiert den Doppel-Dialog.

**Änderung 2:** In `_install_archives` bei "Nein" im Heuristik-Dialog
(Zeile 2193-2196): Statt `continue` den Code normal weiterlaufen lassen
(FOMOD-Check → Normal-Install). Die Mod wird dann als normaler Mod installiert.

**Ergebnis:**
- Bekannte Frameworks (Plugin-Liste) werden im Pre-Filter abgefangen → OK
- Unbekannte Frameworks → Heuristik-Dialog im Install-Loop → einmal
- "Ja" → Framework-Installation → OK
- "Nein" → normaler Mod-Install → OK (statt Mod weg)

**Risiko:** Gering. Kein neuer Code, nur Entfernung des Heuristik-Blocks
an einer Stelle und Änderung von `continue` zu Weiterverarbeitung.

---

## Bug D — Stummer Abbruch bei Extract-Fehler
**Status: OFFEN**

Wenn `extract_to_temp()` fehlschlägt (kaputtes Archiv, unvollständiger
Download, unbekanntes Format), macht der Code `continue` ohne jede
Rückmeldung an den User. Die Mod verschwindet stumm.

**Fix:** Bei `extract_to_temp() → None` eine sichtbare Meldung zeigen:
- Toast oder Statusbar: "Archiv konnte nicht entpackt werden: {name}"
- Betrifft `_try_install_as_framework` (Zeile 1988-1989) und
  `_install_archives` (Zeile 2096-2097)

**Risiko:** Minimal. Reine UI-Ergänzung, keine Logik-Änderung.

---

## Reihenfolge

1. **Bug C** (kritischster Bug — Mods verschwinden stumm)
2. **Bug D** (stummer Abbruch — Fehlermeldung ergänzen)
3. **Bug B** (doppelter Ordner — Signatur-Änderung + Unit-Tests)
4. Disk-Bereinigung `Data/SFSE/SFSE/` nach Bug B
