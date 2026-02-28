# Feature: BA2-Packer Wine-Umstellung

**Datum:** 2026-02-28
**Status:** QA-Analyse abgeschlossen, wartet auf GO
**Betroffene Datei:** `anvil/core/ba2_packer.py` (Hauptumbau), `anvil/widgets/game_panel.py` (kosmetisch)

---

## Problem

`ba2_packer.py` nutzt Proton zum Ausführen von BSArch.exe. Proton verschluckt stdout/stderr und erstellt keine BA2-Dateien. Wine funktioniert nachweislich korrekt.

---

## Analyse-Ergebnisse (4 parallele QA-Agents)

### Agent 1: `_get_proton_env()` und `_run_bsarch()`

**Aktueller Zustand `_get_proton_env()` (Zeile 153-172):**
- Ruft `self._plugin.findProtonRun()` auf
- Baut Proton-Env: `STEAM_COMPAT_DATA_PATH`, `STEAM_COMPAT_CLIENT_INSTALL_PATH`, `SteamAppId`
- Gibt `(proton_script, env)` zurück

**Aktueller Zustand `_run_bsarch()` (Zeile 243-251):**
```python
cmd = [str(proton_script), "run", str(bsarch), "pack", str(source_dir), str(output_ba2), f"-{fmt}", "-mt"]
```

**Änderung `_get_wine_env()`:**
- `protonPrefix()` aus `base_game.py` (Zeile 227-258) liefert WINEPREFIX-Pfad — existiert bereits!
- `shutil.which("wine")` findet Wine-Binary — `shutil` ist bereits importiert (Zeile 21)
- Env: nur `WINEPREFIX` + optional `WINEDEBUG=-all`
- Proton-Variablen entfallen komplett

**Änderung `_run_bsarch()`:**
```python
cmd = [wine_bin, bsarch_win, "pack", source_win, output_win, f"-{fmt}", "-mt"]
```

**Betroffene Signaturen:**
| Methode | Alt | Neu |
|---------|-----|-----|
| `_run_bsarch()` | `proton_script: Path, env: dict` | `wine_bin: str, env: dict` |
| `pack_mod()` | `proton_script: Path, env: dict` | `wine_bin: str, env: dict` |
| `pack_all_mods()` | Ruft `_get_proton_env()` | Ruft `_get_wine_env()` |

---

### Agent 2: Pfad-Konvertierung (KRITISCH)

**Kernproblem:** Proton konvertiert Linux-Pfade automatisch zu Windows-Pfaden. Wine tut das NICHT.

**3 Pfade müssen konvertiert werden:**

| Pfad | Linux | Wine-Windows |
|------|-------|-------------|
| BSArch.exe | `/home/mob/.local/share/anvil-organizer/tools/BSArch.exe` | `Z:\home\mob\.local\share\anvil-organizer\tools\BSArch.exe` |
| source_dir | `/home/mob/.anvil-organizer/instances/Fallout4/.ba2_staging/ModName/general` | `Z:\home\mob\.anvil-organizer\instances\Fallout4\.ba2_staging\ModName\general` |
| output_ba2 | `/mnt/gamingS/.../Fallout 4/Data/anvil_ModName.ba2` | `Z:\mnt\gamingS\...\Fallout 4\Data\anvil_ModName.ba2` |

**Empfohlene Methode: `winepath -w` (robust)**
```python
def _to_wine_path(self, linux_path: Path, env: dict) -> str:
    result = subprocess.run(
        ["winepath", "-w", str(linux_path)],
        capture_output=True, text=True, timeout=5, env=env
    )
    return result.stdout.strip()
```
- Berücksichtigt individuelle Drive-Mappings und Wine-Prefix-Konfiguration
- Funktioniert mit Leerzeichen, Umlauten, /mnt/ Mount-Points

**Alternative: Manuelle Konvertierung (einfacher, aber fragil)**
```python
def _to_wine_path(self, linux_path: Path) -> str:
    return "Z:" + str(linux_path).replace("/", "\\")
```

**Sonderfälle:**
- Leerzeichen ("Fallout 4"): Kein Problem — `subprocess.run()` mit Liste ist sicher
- Umlaute: `winepath -w` konvertiert UTF-8 korrekt
- `/mnt/gamingS/`: Über `Z:\mnt\gamingS\...` erreichbar (Z: mappt Linux-Root `/`)

---

### Agent 3: `is_available()` und `find_bsarch()`

**`find_bsarch()` (Zeile 117-149): KEINE Änderung nötig**
- Sucht BSArch.exe auf dem Dateisystem (4 Suchpfade)
- Komplett unabhängig von Proton/Wine

**`is_available()` (Zeile 275-277): MUSS geändert werden**
```python
# Alt:
return self.find_bsarch() is not None and self._get_proton_env() is not None
# Neu:
return self.find_bsarch() is not None and self._get_wine_env() is not None
```

**`findProtonRun()` in base_game.py: KEINE Änderung**
- Wird weiterhin für Game-Launch via Proton gebraucht
- Wird nicht mehr von BA2Packer aufgerufen

---

### Agent 4: `game_panel.py` Aufrufer

**Ergebnis: game_panel.py braucht KEINE funktionalen Änderungen.**

Die öffentliche API von BA2Packer bleibt identisch:
- `BA2Packer(plugin, instance_path)` — Konstruktor unverändert
- `is_available()` — Boolean, Signatur identisch
- `pack_all_mods(enabled)` — Parameter und Rückgabetyp identisch
- `cleanup_ba2s()` — Proton-unabhängig
- `restore_ini()` — Proton-unabhängig

**Einzige kosmetische Änderung:**
```python
# Zeile 584: "Proton" → "Wine"
"[BA2] BSArch or Proton not available — ..."
→
"[BA2] BSArch or Wine not available — ..."
```

**Andere Dateien mit BA2Packer-Referenzen:**
| Datei | Änderung nötig? |
|-------|----------------|
| `anvil/core/mod_deployer.py` | NEIN (nur Kommentar, Zeile 408-411) |
| `anvil/plugins/base_game.py` | NEIN (`findProtonRun()` bleibt für Game-Launch) |
| `anvil/plugins/games/game_fallout4.py` | NEIN (Ba2Format/Ba2TextureFormat unverändert) |

---

## Änderungsplan

### Datei: `anvil/core/ba2_packer.py`

| # | Zeile | Was | Änderung |
|---|-------|-----|----------|
| 1 | 1 | Modul-Docstring | "via Proton" → "via Wine" |
| 2 | 100 | Klassen-Docstring | "via Proton" → "via Wine" |
| 3 | 153-172 | `_get_proton_env()` | Ersetzen durch `_get_wine_env()` mit WINEPREFIX |
| 4 | NEU | `_to_wine_path()` | Neue Hilfsmethode für Pfad-Konvertierung |
| 5 | 223-271 | `_run_bsarch()` | Parameter + Kommando + Pfad-Konvertierung |
| 6 | 275-277 | `is_available()` | Wine statt Proton prüfen |
| 7 | 279-284 | `pack_mod()` Signatur | `proton_script` → `wine_bin` |
| 8 | 355-465 | `pack_all_mods()` | `_get_proton_env()` → `_get_wine_env()`, Fehlermeldungen |

### Datei: `anvil/widgets/game_panel.py`

| # | Zeile | Was | Änderung |
|---|-------|-----|----------|
| 1 | 584 | Log-Meldung | "Proton" → "Wine" |

### Geschätzter Umfang: ~40-50 Zeilen

---

## Risiken

| Risiko | Schwere | Wahrscheinlichkeit | Mitigation |
|--------|---------|--------------------|----|
| Linux-Pfade nicht konvertiert | HOCH | 100% wenn vergessen | `_to_wine_path()` für alle 3 Pfade verwenden |
| Wine nicht installiert | MITTEL | Gering | `shutil.which("wine")` prüft, klare Fehlermeldung |
| WINEPREFIX existiert nicht | MITTEL | Gering | `protonPrefix()` gibt `None` zurück → sauber abfangen |
| /mnt/ Mount nicht sichtbar in Wine | NIEDRIG | Sehr gering | Z: mappt gesamtes Linux-Root `/` |
| Leerzeichen/Umlaute in Pfaden | NIEDRIG | Sehr gering | subprocess.run mit Liste + winepath |
| Wine-Version inkompatibel | NIEDRIG | Gering | System-Wine ist stabiler als Proton-Wine für CLI |

---

## Entscheidungen offen

1. **Pfad-Konvertierung:** `winepath -w` (robust) oder manuell `Z:` + replace (einfach)?
2. **Wine-Binary:** Nur System-Wine (`shutil.which("wine")`) oder auch Fallback auf Proton-Wine (`<proton_dir>/files/bin/wine64`)?
3. **WINEPREFIX:** Proton-Prefix wiederverwenden (`compatdata/<id>/pfx`) oder Wine-Default (`~/.wine`)?

**Empfehlung:** `winepath -w` + System-Wine + Proton-Prefix wiederverwenden
