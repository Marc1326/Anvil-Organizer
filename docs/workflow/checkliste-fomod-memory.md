# Checkliste: FOMOD Selection Memory (Issue #68)
Datum: 2026-03-26

## Akzeptanz-Kriterien

- [ ] K1: Wenn User einen Mod mit FOMOD per Rechtsklick "Neu installieren" waehlt und fomod_choices.json existiert, zeigt der Wizard die vorherigen Optionen vorausgewaehlt an
- [ ] K2: Wenn User im FOMOD-Wizard auf "Installieren" klickt, wird fomod_choices.json im Mod-Ordner gespeichert mit steps, flags und timestamp
- [ ] K3: Wenn User einen FOMOD-Mod zum ersten Mal installiert (kein fomod_choices.json vorhanden), zeigt der Wizard die Standard-Auswahl (Required/Recommended) wie bisher
- [ ] K4: Wenn User bei Reinstallation die Auswahl aendert und installiert, wird fomod_choices.json mit der neuen Auswahl ueberschrieben
- [ ] K5: Wenn fomod_choices.json existiert aber der FOMOD-Config sich geaendert hat (andere Steps/Gruppen), wird die alte Auswahl ignoriert und der Wizard zeigt Standard-Auswahl
- [ ] K6: Wenn User den FOMOD-Wizard abbricht (Cancel), wird fomod_choices.json NICHT veraendert
- [ ] K7: Wenn User einen neuen Mod per Drag-and-Drop installiert und der Zielordner existiert (Duplikat -> Replace), werden vorherige fomod_choices.json geladen und im Wizard vorausgewaehlt
- [ ] K8: fomod_choices.json enthaelt gueltige JSON-Struktur mit fomod_module, timestamp, steps und flags
- [ ] K9: Mehrstufige FOMOD-Wizards (mehrere Steps) speichern und laden Auswahlen fuer ALLE Steps korrekt
- [ ] K10: `./restart.sh` startet ohne Fehler
