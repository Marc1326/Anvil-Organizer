# Checkliste: ReShade Wizard (Issue #71)
Datum: 2026-03-26

## Akzeptanz-Kriterien

- [ ] **AK-01:** Wenn User "Werkzeuge > ReShade Wizard" klickt, oeffnet sich ein Dialog mit dem ReShade-Wizard, der den aktuellen Status anzeigt (installiert/nicht installiert)
- [ ] **AK-02:** Wenn kein ReShade installiert ist, zeigt Seite 1 einen roten Indikator und bietet Felder fuer DLL-Pfad und API-Auswahl (DX9/DX10-11/DX12/OpenGL als Dropdown)
- [ ] **AK-03:** Wenn User auf "ReShade herunterladen" klickt, oeffnet sich reshade.me im Standard-Browser
- [ ] **AK-04:** Wenn User eine ReShade-DLL auswaehlt (ueber Datei-Dialog), wird der Pfad im Wizard angezeigt und validiert (Datei muss existieren und .dll Endung haben)
- [ ] **AK-05:** Wenn User "Installieren" klickt mit gueltigem DLL-Pfad und API, wird die DLL ins Game-Root kopiert (mit korrektem Namen: dxgi.dll/d3d9.dll/opengl32.dll) und eine ReShade.ini erstellt
- [ ] **AK-06:** Wenn ReShade erfolgreich installiert wurde, zeigt Seite 1 einen gruenen Indikator und die installierten Details (API, DLL-Name)
- [ ] **AK-07:** Wenn User "Deinstallieren" klickt, werden die ReShade-DLL und ReShade.ini aus dem Game-Root entfernt und der Status wechselt auf "nicht installiert"
- [ ] **AK-08:** Wenn User auf der Preset-Seite "Hinzufuegen" klickt, oeffnet sich ein Datei-Dialog (.ini/.txt Filter) und das gewaehlte Preset wird ins Game-Root kopiert
- [ ] **AK-09:** Wenn User ein Preset in der Liste auswaehlt und "Aktivieren" klickt, wird das Preset in ReShade.ini als PresetPath gesetzt
- [ ] **AK-10:** Wenn User ein Preset auswaehlt und "Entfernen" klickt, wird die Preset-Datei aus dem Game-Root geloescht und aus der Liste entfernt
- [ ] **AK-11:** Wenn keine Instanz geladen ist (kein game_path), ist der Menuepunkt "ReShade Wizard" ausgegraut
- [ ] **AK-12:** Wenn User den Wizard schliesst und erneut oeffnet, werden die gespeicherten Einstellungen (DLL-Pfad, API) aus .anvil.ini geladen
- [ ] **AK-13:** Alle Wizard-Texte sind in allen 7 Locale-Dateien (de, en, es, fr, it, pt, ru) vorhanden
- [ ] **AK-14:** `restart.sh` startet ohne Fehler
