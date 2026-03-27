# Feature: FOMOD Selection Memory
Datum: 2026-03-26
Issue: #68

## User Stories
- Als Modder moechte ich bei einer Mod-Reinstallation meine vorherigen FOMOD-Optionen automatisch vorausgewaehlt sehen, damit ich den Wizard nicht komplett neu durchklicken muss
- Als Modder moechte ich die gespeicherte Auswahl ueberschreiben koennen, falls ich andere Optionen waehlen will
- Als Modder moechte ich sehen welche Optionen beim letzten Mal gewaehlt wurden

## Technische Planung

### Betroffene Dateien
| Datei | Aenderung |
|-------|-----------|
| `anvil/core/fomod_parser.py` | Neue Funktion `save_fomod_choices()` und `load_fomod_choices()` |
| `anvil/dialogs/fomod_dialog.py` | `FomodDialog` akzeptiert `previous_choices` Parameter, zeigt vorherige Auswahl vorausgewaehlt |
| `anvil/mainwindow.py` | Bei FOMOD-Erkennung: choices laden, an Dialog uebergeben, nach Accept: choices speichern |
| `anvil/locales/*.json` (7 Dateien) | Neue tr()-Keys fuer "Vorherige Auswahl wiederhergestellt" etc. |

### Speicherformat

FOMOD-Choices werden als JSON-Datei pro Mod gespeichert:
`<instance>/.mods/<mod_name>/fomod_choices.json`

```json
{
    "fomod_module": "CBBE",
    "timestamp": "2026-03-26T15:00:00",
    "steps": {
        "0": {
            "0": [0, 2],
            "1": [1]
        },
        "1": {
            "0": [0]
        }
    },
    "flags": {
        "bodyType": "CBBE",
        "bodySlide": "true"
    }
}
```

Schluessel-Erklaerung:
- `steps`: `{step_index: {group_index: [plugin_indices]}}` — exakt die `_step_selections` Struktur des FomodDialog
- `flags`: Finale Flag-State nach Wizard-Durchlauf
- `fomod_module`: Modulname zum Abgleich (Sanity-Check)
- `timestamp`: Zeitpunkt der letzten Installation

### Signal-Flow

```
_install_archives() oder _ctx_reinstall_mod()
    |
    v
detect_fomod(temp_dir) → fomod_xml gefunden
    |
    v
parse_fomod(fomod_xml) → FomodConfig
    |
    v
load_fomod_choices(mod_path) → previous_choices (dict | None)
    |
    v
FomodDialog(config, temp_dir, previous_choices=previous_choices)
    |  → Dialog zeigt vorherige Auswahl vorausgewaehlt
    |  → User kann Auswahl aendern oder bestaetigen
    v
dlg.exec() == Accepted
    |
    v
save_fomod_choices(mod_path, config, dlg.step_selections(), dlg.flags())
    |
    v
collect_fomod_files() → assemble_fomod_files() → Installation
```

### MO2-Vergleich
MO2 speichert FOMOD-Choices NICHT explizit. Bei Reinstallation muss der User den Wizard komplett neu durchklicken. Dieses Feature ist eine Verbesserung gegenueber MO2.

## Verwandte Funktionen (geprueft)
- `_ctx_reinstall_mod()` → Ruft `_install_archives()` auf → gleicher FOMOD-Pfad
- `_install_archives()` → FOMOD-Check in Schritt 3 → hier wird der Dialog geoeffnet
- `mod_metadata.py` → meta.ini wird NICHT angefasst, separate fomod_choices.json
- `fomod_dialog.py` → `_step_selections` und `_build_radio_group`/`_build_checkbox_group` nutzen bereits `prev_sels` → das passt perfekt

## Implementierungsdetails

### 1. fomod_parser.py: Neue Funktionen

```python
def save_fomod_choices(mod_path: Path, config: FomodConfig,
                       step_selections: dict, flags: dict) -> None:
    """Speichere FOMOD-Wizard-Auswahl als JSON."""

def load_fomod_choices(mod_path: Path, config: FomodConfig) -> dict | None:
    """Lade gespeicherte FOMOD-Choices. None wenn nicht vorhanden oder inkompatibel."""
```

### 2. fomod_dialog.py: previous_choices Parameter

`FomodDialog.__init__()` bekommt optionalen `previous_choices` Parameter.
Wenn vorhanden, wird `self._step_selections` damit initialisiert.
Die `_show_step()` Methode nutzt bereits `prev_sels = self._step_selections.get(step_idx, {})`,
d.h. die vorherigen Auswahlen werden automatisch vorausgewaehlt.

### 3. mainwindow.py: Choices laden/speichern

Im FOMOD-Block von `_install_archives()`:
- VOR Dialog: `previous_choices = load_fomod_choices(dest_path, config)` wenn Reinstall
- NACH Dialog-Accept: `save_fomod_choices(dest_path, config, dlg.step_selections(), dlg.flags())`

Problem: Bei Erstinstallation existiert `dest_path` noch nicht.
Loesung: Choices werden nach der Installation gespeichert, wenn mod_path bekannt ist.

Bei Reinstallation existiert der Mod-Ordner bereits → Choices koennen vorher geladen werden.

### 4. Erkennung Reinstall vs. Erstinstallation

Ein Mod wird reinstalliert wenn:
- `_ctx_reinstall_mod()` aufgerufen wird (explizit), ODER
- `_install_archives()` einen Mod installiert und `dest.exists()` (Ordner existiert schon)

In beiden Faellen kann `fomod_choices.json` aus dem bestehenden Mod-Ordner geladen werden.

## Akzeptanz-Checkliste

- [ ] K1: Wenn User einen Mod mit FOMOD per Rechtsklick "Neu installieren" waehlt und fomod_choices.json existiert, zeigt der Wizard die vorherigen Optionen vorausgewaehlt an
- [ ] K2: Wenn User im FOMOD-Wizard auf "Installieren" klickt, wird fomod_choices.json im Mod-Ordner gespeichert mit steps, flags und timestamp
- [ ] K3: Wenn User einen FOMOD-Mod zum ersten Mal installiert (kein fomod_choices.json vorhanden), zeigt der Wizard die Standard-Auswahl (Required/Recommended) wie bisher
- [ ] K4: Wenn User bei Reinstallation die Auswahl aendert und installiert, wird fomod_choices.json mit der neuen Auswahl ueberschrieben
- [ ] K5: Wenn fomod_choices.json existiert aber der FOMOD-Config sich geaendert hat (andere Steps/Gruppen), wird die alte Auswahl ignoriert und der Wizard zeigt Standard-Auswahl
- [ ] K6: Wenn User den FOMOD-Wizard abbricht (Cancel), wird fomod_choices.json NICHT veraendert
- [ ] K7: Wenn User einen neuen Mod per Drag-and-Drop installiert und der Zielordner existiert (Duplikat → Replace), werden vorherige fomod_choices.json geladen und im Wizard vorausgewaehlt
- [ ] K8: fomod_choices.json enthaelt gueltige JSON-Struktur mit fomod_module, timestamp, steps und flags
- [ ] K9: Mehrstufige FOMOD-Wizards (mehrere Steps) speichern und laden Auswahlen fuer ALLE Steps korrekt
- [ ] K10: `./restart.sh` startet ohne Fehler
