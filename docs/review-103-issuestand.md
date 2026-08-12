# Review Issue #103 — Ist der Issue-Stand geloest?

Datum: 2026-08-08
Branch: `fix/issue-103` (Tip `08d8588`) + unversionierte Aenderung an `anvil/widgets/profile_bar.py`
Melder: Nuckinfutzcat — Bazzite, Anvil 1.6.1 als Flatpak, Steam + Heroic, Fallout 4 / Starfield / Skyrim

## Was der Branch enthaelt

| Commit | Inhalt |
|---|---|
| `8c8036b` | Verstaendlichere Meldung, wenn `plugins_txt_path()` `None` liefert |
| `ac740d6` | Profilanlage meldet Fehler statt still zu scheitern |
| `08d8588` | Mausrad scrollt die Profilleiste (Event-Filter) |
| unversioniert | Inline-Eingabefeld wird sichtbar gescrollt, `edit.show()`, Pos1/Ende, Breite 140 → 200; dazu `tests/test_profile_bar_inline_input.py` (unversioniert) |

Der Branch haengt **20 Commits hinter `main`** (Merge-Base `7a2c6f6` vom 30.07., `main` steht auf `49504b9` vom 07.08.). Alles was seither auf `main` am Deploy geaendert wurde (u. a. `33413b9` „Mods erst beim Spielstart ausrollen", `8768545` RED4ext) ist hier **nicht** enthalten.

Testlauf: `QT_QPA_PLATFORM=offscreen pytest tests/ -q` → **229 passed, 1 skipped**.

---

## Punkt 1 — „could not deploy mods" / „plugins.txt path not available"

### Ergebnis: **NICHT GELOEST**

Der Branch aendert ausschliesslich den **Meldungstext**. Die Ursache bleibt unangetastet, und der Spielstart bleibt blockiert.

### Belegte Ursachenkette

`anvil/widgets/game_panel.py:1319-1338` (`silent_deploy_fast`, identisch in `silent_deploy` ab Zeile 1241):

```python
result_path = writer.write()
if result_path is None:
    self._record_plugin_write_failure(result, writer)
```

`_record_plugin_write_failure` (Zeile 1108-1122) setzt `result.success = False`. Ein reiner
plugins.txt-Fehler kippt also das **gesamte Deploy-Ergebnis auf „fehlgeschlagen"**, obwohl die
Symlinks bereits gesetzt sind.

`anvil/mainwindow.py:2517-2531` (`_predeploy_for_launch`):

```python
deploy_result = self._game_panel.silent_deploy()
if deploy_result is not None and not getattr(deploy_result, "success", False):
    return False
```

`anvil/mainwindow.py:2536-2541` (`_on_start_game`):

```python
if not self._predeploy_for_launch("game_start"):
    QMessageBox.warning(self, tr("error.deploy_failed_title"),
                        tr("error.deploy_failed_message", details=""))
    return
```

→ genau der Satz des Melders: „The mods could not be deployed into the game. The game was not started."
**Und hier steht `details=""`** — die neue, verstaendliche Meldung aus `8c8036b` erreicht diesen Dialog
gar nicht. Der Melder sieht nach dem Fix an der wichtigsten Stelle **weniger** Information als vorher.

Zwei weitere Startwege brechen sogar **ganz ohne Dialog** ab:
- `anvil/mainwindow.py:1313` (`_run_proton_tool`) → `return` ohne Meldung
- `anvil/mainwindow.py:2570` (`_on_custom_start`) → `return` ohne Meldung

Verbessert wurde nur der Weg „Mod installieren → Auto-Redeploy" (`anvil/mainwindow.py:2292` und
`2305`), weil dort `details` aus `result.errors` gefuellt wird. Das erklaert, warum der Melder die
Meldung beim Mod-Installieren sah — dieser eine Text ist jetzt lesbar.

### Ursache A — Flatpak-Sandkasten blendet Flatpak-Steam aus (empirisch bewiesen)

`packaging/flatpak/com.github.Marc1326.AnvilOrganizer.yml:14` hat `--filesystem=home`.
Gemessen auf diesem Rechner mit dem installierten Anvil-Flatpak:

```
$ flatpak run --command=/bin/ls com.github.Marc1326.AnvilOrganizer -la /home/mob/.var/app/
drwxr-xr-x com.github.Marc1326.AnvilOrganizer      ← nur der eigene Ordner

$ flatpak run --command=python3 com.github.Marc1326.AnvilOrganizer -c "..."
/home/mob/.local/share/Steam                                          -> True
/home/mob/.steam/steam                                                -> True
/home/mob/.var/app/com.valvesoftware.Steam/.local/share/Steam         -> False   ← existiert auf dem Host!
/home/mob/snap/steam/common/.local/share/Steam                        -> False
find_steam_path() = /home/mob/.local/share/Steam
```

Auf dem Host existiert `/home/mob/.var/app/com.valvesoftware.Steam/.local/share/Steam` sehr wohl.
`--filesystem=home` schliesst fremde `~/.var/app/*` also aus. Auf diesem Rechner rettet das native
Steam die Erkennung; auf einem System mit **nur** Flatpak-Steam (Bazzite-Standard) liefert
`anvil/stores/steam_utils.py:85-93` `find_steam_path()` → `None`.

Folge: `anvil/plugins/base_game.py:313-344` `protonPrefix()` → `None` →
`anvil/plugins/games/game_fallout4.py:156-165` (analog `game_skyrimse.py:137`, `game_starfield.py:146`)
`plugins_txt_path()` → `None` → `anvil/core/plugins_txt_writer.py:260-268` schlaegt fehl.

Der Branch aendert weder das Manifest noch `find_steam_path()`. **Nicht geloest.**

### Ursache B — Heroic (GOG/Epic) hat grundsaetzlich keinen Prefix

`anvil/plugins/base_game.py:313-316`:

```python
def protonPrefix(self) -> Path | None:
    if self._detected_store != "steam":
        return None
```

Der Store kommt aus `instance.json` (`anvil/mainwindow.py:1727` `data.get("detected_store")` →
`plugin.setGamePath(game_path, store=store)` in Zeile 1746). Bei Heroic-Installationen ist das
`gog` oder `epic` — damit liefert `protonPrefix()` **immer** `None`, unabhaengig davon, ob ein
Wine-Prefix existiert. `findProtonRun()` (Zeile 360) hat dieselbe Sperre.

Ein manueller Ausweg fehlt: das Feld „Proton-Prefix" im Einstellungsdialog ist reine Anzeige —
`anvil/widgets/settings_dialog.py:918-920`, `self._pl_prefix.setReadOnly(True)`. Ein Suchlauf ueber
`WINEPREFIX|wine_prefix|path_prefix|compatdata|pfx` findet keine Stelle, an der ein Nicht-Steam-Prefix
konfiguriert oder ermittelt wird.

Der Branch aendert daran nichts. **Nicht geloest.**

### Was fuer Punkt 1 noetig waere

1. Ein fehlgeschlagener plugins.txt-Schreibvorgang darf das Deploy nicht auf `success = False` kippen und den Spielstart nicht blockieren — Warnung statt Abbruch (`game_panel.py:1108-1122`).
2. `details` in `mainwindow.py:2540` fuellen; die stillen `return` in Zeile 1313 und 2570 mit Meldung versehen.
3. Manifest um `--filesystem=~/.var/app/com.valvesoftware.Steam:ro` (bzw. `:rw`) ergaenzen — sonst ist Flatpak-Steam fuer Anvil-Flatpak unsichtbar.
4. Prefix-Pfad pro Instanz konfigurierbar machen, damit Heroic/GOG/Epic ueberhaupt eine Chance haben.

---

## Punkt 2 — „I can't seem to create a new profile"

### Ergebnis: **GELOEST** (mit einer Einschraenkung)

Zwei Ursachen, beide adressiert:

**a) Das „+" war bei ~30 Profilen ausserhalb des Sichtfensters.**
Im modernen Theme haengt der Knopf im scrollbaren Streifen: `anvil/widgets/profile_bar.py:615-616`
`if self._plus_inline: self._tabs_layout.addWidget(self._btn_add)`. Offscreen gemessen
(1000 px Fenster, 30 Profile, Theme „Anvil Dunkel"):

```
plus_inline: True   viewport: 430   strip: 2645
+ Button (start):  x=2615..2645  sicht=0..430     -> AUSSERHALB
+ Button (rechts): x=2615..2645  sicht=2215..2645 -> SICHTBAR
```

Da vorher nicht gescrollt werden konnte, war der Knopf faktisch unerreichbar. Mit dem Scroll-Fix
(Punkt 3) ist er erreichbar.

**b) Nach dem Klick sass das Eingabefeld ausserhalb des Bildes.**
Die unversionierte Aenderung (`edit.show()` in Zeile 735 + `_reveal_inline_input`, Zeile 749-767)
behebt das. Gemessen:

```
Inline-Feld: x=2615..2815  sicht=2385..2815 -> SICHTBAR
sichtbar: True  hasFocus: True
```

**c) Stille Fehlschlaege.** End-to-End nachgespielt mit `QTest.mouseClick` auf `_btn_add`:

```
nach Klick: Inline-Feld da? True
"Mein Profil" + Enter   -> bestaetigt: ['Mein Profil']
"Profil 05"   + Enter   -> abgelehnt: ['toast.profile_exists']
"a/b"         + Enter   -> abgelehnt: ['toast.profile_invalid_name']
```

Und `MainWindow._on_profile_created` gegen ein echtes Instanzverzeichnis gefahren:

```
A) gueltiger Name      -> Ordner angelegt, active_mods.json kopiert, Profil gewechselt, Toast "Profil 'Neu' erstellt"
B) "bad/name"          -> Toast "Profil konnte nicht erstellt werden: Ungueltiger Profilname...", Tab zurueckgerollt
C) keine Instanz aktiv -> Toast "... Keine Instanz aktiv."
D) .profiles auf 0555  -> Toast "... [Errno 13] Keine Berechtigung: .../ReadOnly", Tab zurueckgerollt, kein Ordner
```

Alle vier Signalwege sind verbunden (`anvil/mainwindow.py:260-262` verbindet
`profile_create_rejected` mit `_on_profile_create_rejected`).

**Einschraenkung:** Das „+" bleibt der **einzige** Weg, ein Profil anzulegen — ein Suchlauf ueber
`_start_inline_create` findet nur `profile_bar.py:419`. Bei vielen Profilen muss der Nutzer erst
scrollen, um den Knopf zu sehen. Funktional geloest, in der Auffindbarkeit weiterhin schwach.

---

## Punkt 3 — „I can't find a way to scroll through the profiles"

### Ergebnis: **GELOEST**

Ursache war korrekt erkannt: `ProfileBar.wheelEvent` wurde nie erreicht, weil das Rad-Event beim
Widget unter dem Zeiger landet und die `QScrollArea` es selbst verarbeitet.

`anvil/widgets/profile_bar.py:938-942` leitet Rad-Events jetzt im app-weiten Event-Filter
(installiert in Zeile 516) an die horizontale Bildlaufleiste weiter, abgesichert durch
`_is_own_scroll_target` (Zeile 523-535).

Nicht nur der Testaufruf, sondern **echte Events ueber `QApplication.sendEvent`** gemessen
(30 Profile, moderne Optik):

```
viewport: 430  strip: 2645  scrollbar range 0..2215
Rad ueber viewport: 0   -> 120
Rad ueber Tab:      120 -> 240
nach vielen Ticks:  2215 (= maximum)
Pos1: 0     Ende: 2215
```

Auch mit klassischem Theme (Streifen 2611 px, Sichtfenster 668 px) identisches Verhalten.
Waagerechte Raeder/Touchpads sind ueber `event.angleDelta().y() or event.angleDelta().x()`
(Zeile 562) abgedeckt. Pos1/Ende aus der unversionierten Aenderung (Zeile 537-556) greifen,
solange kein Eingabefeld offen ist.

Fremde Widgets loesen kein Scrollen aus — `_is_own_scroll_target` ist streng auf
`_tabs_widget`, `_tab_container`, `_scroll_area`, dessen Viewport und die Tabs begrenzt.

**Hinweis, kein Fehler:** Die Bildlaufleisten stehen auf `ScrollBarAlwaysOff`
(`profile_bar.py:363-364`), sichtbar sind nur die Fade-Kanten. Dass ueberhaupt gescrollt werden
kann, ist damit weiterhin schlecht erkennbar.

---

## Gesamturteil

| Punkt | Stand |
|---|---|
| 1 — Deploy / plugins.txt | **NICHT GELOEST** — nur der Meldungstext, und der erreicht den Startdialog nicht einmal |
| 2 — Profil anlegen | **GELOEST** |
| 3 — Profilleiste scrollen | **GELOEST** |

Der Issue traegt den Titel des Deploy-Fehlers. Punkt 1 ist der eigentliche Issue und ist offen.
Ein Schliessen von #103 auf Basis dieses Branches waere nicht gerechtfertigt.
