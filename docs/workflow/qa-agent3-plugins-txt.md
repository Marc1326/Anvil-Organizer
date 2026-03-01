# QA Agent 3 -- Live-Test: plugins.txt

**Datum:** 2026-03-01
**Tester:** QA Agent 3 (automatisiert)
**Getestete Instanz:** Fallout 4 (Steam/Proton)

---

## Plugins.txt Inhalt

Datei: `/mnt/gamingS/SteamLibrary/steamapps/compatdata/377160/pfx/drive_c/users/steamuser/AppData/Local/Fallout4/plugins.txt`

```
# This file is used by the game to keep track of your downloaded content.
# Please do not modify this file.
*Fallout4.esm
*DLCRobot.esm
*DLCworkshop01.esm
*DLCCoast.esm
*DLCworkshop02.esm
*DLCworkshop03.esm
*DLCNukaWorld.esm
*DLCUltraHighResolution.esm
*CBBE.esp
*ccBGSFO4044-HellfirePowerArmor.esl
*ccBGSFO4046-TesCan.esl
*ccBGSFO4096-AS_Enclave.esl
*ccBGSFO4110-WS_Enclave.esl
*ccBGSFO4115-X02.esl
*ccBGSFO4116-HeavyFlamer.esl
*ccFSVFO4007-Halloween.esl
*ccOTMFO4001-Remnants.esl
*ccSBJFO4003-Grenade.esl
*GCM.esp
*LooksMenu.esp
*Undressed_Character_Creation.esp
```

---

## Anzahl Eintraege

| Metrik | Erwartet | Tatsaechlich | Status |
|--------|----------|--------------|--------|
| PRIMARY_PLUGINS (ESMs) | 8 | 8 | OK |
| Mod-ESPs (deployed) | 4 | 4 (CBBE, GCM, LooksMenu, Undressed_Character_Creation) | OK |
| Creation Club ESLs | 9 | 9 | OK |
| **Gesamt Plugin-Eintraege** | **mindestens 12** | **21** | OK |
| Header-Zeilen (# Kommentare) | 2 | 2 | OK |
| **Gesamt Zeilen** | - | **23** | OK |

**Hinweis:** Die Aufgabenstellung erwartete 12 Eintraege. Tatsaechlich sind es 21, weil 9 Creation Club ESLs ebenfalls im Data-Verzeichnis liegen und korrekt erfasst werden. Das ist KORREKTES Verhalten -- alle Plugin-Dateien im Data/ werden aufgenommen.

---

## Format-Pruefung

| Kriterium | Ergebnis | Status |
|-----------|----------|--------|
| Jede Plugin-Zeile beginnt mit `*` | 21/21 Zeilen mit `*`-Prefix | OK |
| Zeilenenden: CRLF (`\r\n`) | Alle 23 Zeilen haben CRLF | OK |
| Encoding: UTF-8 (ohne BOM) | ASCII-kompatibel, kein BOM | OK |
| Dateiname: `plugins.txt` (Kleinbuchstaben) | Korrekt, keine Case-Variante vorhanden | OK |
| Sortierung: PRIMARY zuerst | Positionen 1-8 = PRIMARY_PLUGINS in korrekter Reihenfolge | OK |
| Sortierung: Remaining alphabetisch | ESLs und ESPs alphabetisch nach Primary | OK |

---

## Konsolen-Output

### Erster Test (ohne PYTHONUNBUFFERED)

Die `[PluginsTxtWriter]`-Meldung war NICHT sichtbar, weil `print()` ohne `flush=True` den Output im Puffer haelt und durch `timeout` abgeschnitten wird.

### Zweiter Test (mit PYTHONUNBUFFERED=1)

```
[PluginsTxtWriter] Wrote 21 plugins to /mnt/gamingS/.../Fallout4/plugins.txt
```

Meldung kommt **zweimal** pro App-Start (zwei deploy-Zyklen). Das ist erwartet -- die App deployt bei Initialisierung und beim Fensterladen.

### Dritter Test (venv-Python wie restart.sh)

```
[PluginsTxtWriter] Wrote 21 plugins to /mnt/gamingS/.../Fallout4/plugins.txt
```

Identisches Ergebnis. App startet fehlerfrei.

---

## Fehler/Warnings

| Typ | Meldung | Bewertung |
|-----|---------|-----------|
| Warning | `QTabBar does not have a property named "alignment"` (10x) | BEKANNT -- ignorieren (siehe CLAUDE.md) |
| BA2-Fehler | `[BA2] Done: 4 mods packed, 5 archives created, 2 errors` | NICHT Teil der plugins.txt-Pruefung. Betrifft Mentats-F4SE und Lacy Underwear general BA2. |
| Traceback | KEINE | OK |
| NameError | KEINE | OK |
| ImportError | KEINE | OK |
| AttributeError | KEINE | OK |

---

## Checklisten-Pruefung (Akzeptanz-Kriterien)

- [x] Kriterium 1: Case-Varianten-Bereinigung -- `_remove_case_variants()` ist in `write()` implementiert (Zeile 144 in plugins_txt_writer.py). Wird VOR dem Schreiben aufgerufen. Im Live-Test: Keine `Plugins.txt` (gross-P) mehr im Verzeichnis nach App-Start.
- [x] Kriterium 2: plugins.txt enthaelt 21 Eintraege (8 PRIMARY + 4 Mod-ESPs + 9 CC-ESLs) -- deutlich mehr als die geforderten 12.
- [x] Kriterium 3: Alle 9 Creation Club ESLs sind in plugins.txt aufgefuehrt (ccBGSFO4044, ccBGSFO4046, ccBGSFO4096, ccBGSFO4110, ccBGSFO4115, ccBGSFO4116, ccFSVFO4007, ccOTMFO4001, ccSBJFO4003).
- [x] Kriterium 4: `remove()` ruft `_remove_case_variants()` auf (Zeile 167), BEVOR die eigentliche Datei geloescht wird. Alle Case-Varianten werden entfernt.
- [x] Kriterium 5: `scan_plugins()` hat drei differenzierte Fehlermeldungen: "Data directory not found" (Zeile 78), "No plugin files found" (Zeile 95), OSError-Details (Zeile 91).
- [x] Kriterium 6: In `silent_deploy()` (game_panel.py Zeile 601-602) wird `result_path` geprueft und bei `None` eine Warnung mit `flush=True` ausgegeben.
- [x] Kriterium 7: `write()` gibt bei Erfolg die Anzahl und den Pfad aus (Zeile 154): `[PluginsTxtWriter] Wrote 21 plugins to ...`. Im Live-Test verifiziert.
- [x] Kriterium 8: `os.makedirs(txt_path.parent, exist_ok=True)` in Zeile 141 erstellt fehlende Verzeichnisse automatisch.
- [x] Kriterium 9: Nicht-Bethesda-Spiele sind nicht betroffen. `PRIMARY_PLUGINS` ist in `base_game.py` als leere Liste definiert (Zeile 109). `has_plugins_txt()` gibt `False` zurueck wenn `PRIMARY_PLUGINS` leer ist (Zeile 363). Nur `game_fallout4.py` setzt `PRIMARY_PLUGINS`. Die Guards in `silent_deploy()` und `silent_purge()` pruefen `has_plugins_txt()` bevor sie den Writer aufrufen.
- [x] Kriterium 10: App startet ohne Fehler. `_dev/restart.sh` existiert (nicht im Root, sondern in `_dev/`). Exit code 124 = timeout (kein Crash). Keine Tracebacks im Log.

**Ergebnis: 10/10 Punkte erfuellt**

---

## Zusaetzliche Findings (nicht Teil der Checkliste)

### [LOW] print() ohne flush in plugins_txt_writer.py

- **Datei:** `/home/mob/Projekte/Anvil Organizer/anvil/core/plugins_txt_writer.py`, Zeilen 60, 78, 91, 95, 132, 137, 154, 170, 173
- **Problem:** Alle `print()`-Aufrufe in `plugins_txt_writer.py` verwenden KEIN `flush=True`. Im Gegensatz dazu verwenden die BA2-Meldungen und die GamePanel-Warnung (Zeile 602) `flush=True`. Bei einem harten Prozess-Abbruch (z.B. `timeout`, `kill`) koennten die PluginsTxtWriter-Meldungen verloren gehen.
- **Auswirkung:** Rein kosmetisch. Die Meldungen erscheinen nicht im Log wenn die App per timeout beendet wird, was das Debugging erschwert.
- **Fix:** `flush=True` zu allen `print()`-Aufrufen in `plugins_txt_writer.py` hinzufuegen.

### [LOW] Doppelter Deploy beim App-Start

- **Beobachtung:** Die `[PluginsTxtWriter] Wrote 21 plugins` Meldung erscheint ZWEIMAL pro App-Start. Die gesamte Deploy-Sequenz (DEPLOY + BA2 + PluginsTxtWriter) laeuft doppelt.
- **Auswirkung:** Performance. Das BA2-Packing ist aufwaendig und laeuft unnoetig zweimal.
- **Vermutung:** Wahrscheinlich wird `silent_deploy()` sowohl bei Initialisierung als auch beim Window-Show-Event aufgerufen. Koennte durch einen Guard (z.B. `_deployed`-Flag) verhindert werden.

---

## Fazit

Die plugins.txt-Funktionalitaet arbeitet **einwandfrei**. Alle 10 Akzeptanz-Kriterien sind erfuellt:

1. Case-Varianten werden bereinigt
2. 21 Plugin-Eintraege werden korrekt geschrieben (uebertrifft die geforderten 12)
3. Creation Club ESLs werden erkannt
4. Purge entfernt alle Case-Varianten
5. Diagnostik-Logging ist differenziert
6. Fehler-Handling mit Log-Warnung vorhanden
7. Erfolgs-Logging mit Anzahl und Pfad
8. Verzeichnis-Erstellung automatisch
9. Nicht-Bethesda-Spiele nicht betroffen
10. App startet ohne Fehler

**Status: READY FOR COMMIT**
