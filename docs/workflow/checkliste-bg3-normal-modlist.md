# Checkliste: BG3 auf normales ModListView umstellen
Datum: 2026-03-23
Issue: #59

## Feature-Spec

### Ziel
BG3 soll das normale ModListView + ModListModel benutzen (wie Cyberpunk, Starfield etc.)
statt sein eigenes BG3ModListView. Dadurch erhaelt BG3 automatisch: Separatoren, volles
Kontextmenue, Doppelklick, Profile, Enable/Disable All, Export CSV, Backup/Restore, Kategorien.

### Architektur
- **Bridge-Pattern**: BG3-Mods aus `bg3_modstate.json` werden in `ModEntry`-Objekte konvertiert
- **Weichen-Pattern**: In bestehenden Handlern (_on_mod_toggled, _on_mods_reordered, etc.)
  wird per `if self._bg3_installer is not None:` zum BG3-spezifischen Code verzweigt
- **Separator-Speicherung**: In bg3_modstate.json als spezielle Eintraege (is_separator: true)
- **Extras-Sektion**: Bleibt als QTreeWidget unterhalb des normalen ModListView

### Betroffene Dateien
| Datei | Aenderung |
|-------|-----------|
| `anvil/mainwindow.py` | Bridge-Code, Weichen, _apply_bg3_instance umbau |
| `anvil/widgets/bg3_mod_list.py` | Wird nicht mehr fuer Mod-Liste benutzt, nur Extras-Teil bleibt |

### Signal-Flow (BG3 mit normalem ModListView)
```
User klickt Checkbox
  -> ModListModel.mod_toggled(row, enabled)
  -> MainWindow._on_mod_toggled(row, enabled)
     -> BG3-Weiche: _bg3_installer.activate_mod(uuid) / deactivate_mod(uuid)
     -> _bg3_reload_mod_list() -> konvertiert zu ModEntry -> Model update

User zieht Mod per DnD
  -> ModListModel.mods_reordered()
  -> MainWindow._on_mods_reordered()
     -> BG3-Weiche: uuid_order aus Model extrahieren
     -> _bg3_installer.reorder_mods(uuid_order)

User erstellt Separator
  -> _ctx_create_separator()
     -> BG3-Weiche: Separator in bg3_modstate.json speichern (nicht .mods/)
     -> _bg3_reload_mod_list()
```

### NICHT aendern (Absolute Verbote)
- `anvil/core/bg3_mod_installer.py`
- `anvil/plugins/games/game_baldursgate3.py`
- `anvil/plugins/games/bg3_mod_handler.py`
- `anvil/core/base_game.py`
- `anvil/core/mod_deployer.py`
- `anvil/models/mod_list_model.py` (andere Games nutzen das!)
- `anvil/widgets/mod_list.py` (andere Games nutzen das!)

---

## Akzeptanz-Checkliste

### Grundfunktionen
- [ ] 1. Wenn User eine BG3-Instanz laedt, zeigt das normale ModListView die BG3-Mods an (gleiche Spalten wie Cyberpunk: Checkbox, Name, Konflikte, Markierungen, Kategorie, Version, Prioritaet)
- [ ] 2. Wenn User die Checkbox eines BG3-Mods klickt, wird activate_mod/deactivate_mod aufgerufen und modsettings.lsx automatisch geschrieben (Auto-Deploy)
- [ ] 3. Wenn User einen BG3-Mod per DnD verschiebt, wird reorder_mods aufgerufen und modsettings.lsx automatisch geschrieben
- [ ] 4. Wenn User auf einen BG3-Mod doppelklickt, oeffnet sich der ModDetailDialog mit Mod-Infos
- [ ] 5. Wenn User Rechtsklick auf einen BG3-Mod macht, erscheint das volle Kontextmenue (Enable/Disable, Uninstall, Visit Nexus, Info, Alle Mods Submenu etc.)

### Separatoren
- [ ] 6. Wenn User Rechtsklick -> "Trenner erstellen" waehlt, wird ein Separator im ModListView erstellt
- [ ] 7. Separatoren werden in bg3_modstate.json gespeichert (als Eintraege mit is_separator: true)
- [ ] 8. Beim Deploy (modsettings.lsx schreiben) werden Separatoren uebersprungen — nur echte Mods landen in der LSX

### Profile
- [ ] 9. Wenn User ein neues Profil erstellt, wird die BG3-Modliste fuer das neue Profil kopiert
- [ ] 10. Wenn User das Profil wechselt, werden die BG3-Mods fuer das neue Profil geladen (Checkbox-State aus Profil)
- [ ] 11. Wenn User ein Profil loescht, wird die BG3-Modliste korrekt neu geladen

### UI-Elemente
- [ ] 12. Wenn BG3-Instanz aktiv ist, bleibt der Deploy-Button versteckt (Auto-Deploy)
- [ ] 13. Wenn BG3-Instanz aktiv ist, zeigt der Zaehler "X / Y" (aktive/total Mods ohne Separatoren)
- [ ] 14. Wenn BG3-Instanz aktiv ist, bleibt die Extras-Sektion (Frameworks + Data-Overrides) sichtbar unterhalb der Mod-Liste
- [ ] 15. Wenn User "Alle aktivieren" / "Alle deaktivieren" klickt, werden alle BG3-Mods aktiviert/deaktiviert via BG3-Installer

### Integration
- [ ] 16. Wenn User eine Mod-Datei (.pak/.zip/.rar/.7z) auf die Mod-Liste zieht, wird sie ueber den BG3-Installer installiert
- [ ] 17. Wenn User eine nicht-BG3 Instanz laedt (z.B. Cyberpunk), funktioniert ALLES wie vorher — kein Unterschied
- [ ] 18. Wenn User die Suchleiste benutzt, werden BG3-Mods gefiltert (wie bei normalen Games)

### Datei-Integritaet
- [ ] 19. bg3_mod_installer.py ist NICHT veraendert (git diff zeigt keine Aenderungen)
- [ ] 20. game_baldursgate3.py ist NICHT veraendert
- [ ] 21. bg3_mod_handler.py ist NICHT veraendert
- [ ] 22. mod_list_model.py ist NICHT veraendert
- [ ] 23. mod_list.py (Widget) ist NICHT veraendert
- [ ] 24. base_game.py ist NICHT veraendert
- [ ] 25. mod_deployer.py ist NICHT veraendert

### Start
- [ ] 26. `.venv/bin/python main.py` startet ohne Fehler (kein Traceback, kein ImportError, kein NameError)
