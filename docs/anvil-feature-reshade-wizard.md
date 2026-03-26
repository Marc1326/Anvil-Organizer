# Feature: ReShade Wizard
Datum: 2026-03-26
Issue: #71

## Beschreibung
Gefuehrte Installation von ReShade mit Preset-Auswahl. Der Wizard konfiguriert ReShade fuer das aktive Spiel, verwaltet Presets und ermoeglicht Installation/Deinstallation.

## User Stories
- Als Modder moechte ich ReShade per Wizard konfigurieren, damit ich nicht manuell DLLs kopieren muss
- Als Modder moechte ich aus vorhandenen Presets waehlen und neue hinzufuegen koennen
- Als Modder moechte ich ReShade wieder deinstallieren koennen
- Als Modder moechte ich sehen ob ReShade aktuell installiert ist

## Technische Planung

### Hintergrund: Was ist ReShade?
ReShade ist ein Post-Processing-Injector fuer Games. Er besteht aus:
1. **DLL-Datei** — wird neben die Game-EXE gelegt (je nach Render-API: `dxgi.dll`, `d3d9.dll`, `d3d11.dll`, `opengl32.dll`)
2. **ReShade.ini** — Konfigurationsdatei mit Pfaden zu Shader-Ordnern und aktivem Preset
3. **Presets** (.ini/.txt) — Konfigurationsdateien die bestimmte Shader-Einstellungen definieren
4. **Shader-Ordner** — Ordner mit .fx/.fxh Shader-Dateien (z.B. reshade-shaders/)

ReShade wird ins **Game-Root** deployed (nicht ins Data-Verzeichnis).

### Render-APIs und DLL-Namen
| API | DLL-Name | Typische Spiele |
|-----|----------|-----------------|
| DirectX 9 | d3d9.dll | Aeltere Spiele |
| DirectX 10/11 | dxgi.dll | Die meisten modernen Spiele |
| DirectX 12 | dxgi.dll | Neuere Spiele (Cyberpunk, Starfield) |
| OpenGL | opengl32.dll | Minecraft, aeltere Spiele |
| Vulkan | (nicht als DLL, wird global installiert) | Nicht unterstuetzt im Wizard |

### Betroffene Dateien

| Datei | Aenderung |
|-------|-----------|
| `anvil/dialogs/reshade_wizard.py` | **NEU** — Wizard-Dialog (QDialog mit QStackedWidget) |
| `anvil/core/reshade_manager.py` | **NEU** — Backend-Logik: detect, install, uninstall, presets |
| `anvil/mainwindow.py` | Menuepunkt unter "Werkzeuge" + Handler-Methode |
| `anvil/widgets/toolbar.py` | Optional: Tools-Menue Eintrag |
| `anvil/locales/de.json` | Neue i18n-Keys |
| `anvil/locales/en.json` | Neue i18n-Keys |
| `anvil/locales/es.json` | Neue i18n-Keys |
| `anvil/locales/fr.json` | Neue i18n-Keys |
| `anvil/locales/it.json` | Neue i18n-Keys |
| `anvil/locales/pt.json` | Neue i18n-Keys |
| `anvil/locales/ru.json` | Neue i18n-Keys |

### Architektur

#### reshade_manager.py (Core-Logik)
```python
class ReshadeManager:
    """Verwaltet ReShade-Installation fuer eine Game-Instanz."""

    def __init__(self, game_path: Path, game_binary: str):
        """
        game_path: Pfad zum Game-Root
        game_binary: Relativer Pfad zur Game-EXE (z.B. 'bin/x64/Cyberpunk2077.exe')
        """

    # Erkennung
    def detect_installed(self) -> dict | None:
        """Prueft ob ReShade installiert ist. Gibt Info-Dict oder None zurueck."""

    def detect_api(self) -> str:
        """Erkennt die Render-API anhand der Game-EXE oder liest aus gespeicherter Config."""

    # Installation
    def install(self, reshade_dll: Path, api: str, preset: Path | None = None) -> bool:
        """Kopiert ReShade-DLL + erzeugt ReShade.ini."""

    def uninstall(self) -> bool:
        """Entfernt ReShade-DLL + ReShade.ini + ggf. Shader-Cache."""

    # Presets
    def list_presets(self) -> list[Path]:
        """Findet alle .ini/.txt Preset-Dateien im Game-Root."""

    def get_active_preset(self) -> str | None:
        """Liest das aktive Preset aus ReShade.ini."""

    def set_active_preset(self, preset_path: str) -> bool:
        """Setzt das aktive Preset in ReShade.ini."""

    def add_preset(self, source: Path) -> Path:
        """Kopiert ein Preset ins Game-Root."""

    def remove_preset(self, preset: Path) -> bool:
        """Entfernt ein Preset."""
```

#### reshade_wizard.py (Dialog)
QDialog mit QStackedWidget, 4 Seiten:

**Seite 1 — Status & API-Auswahl:**
- Zeigt ob ReShade aktuell installiert ist (gruener/roter Indikator)
- Zeigt erkannte Render-API (mit Override-Moeglichkeit)
- Pfad zur ReShade-DLL (User muss ReShade separat herunterladen)
- "ReShade herunterladen" Link-Button zu reshade.me

**Seite 2 — Installation/Deinstallation:**
- Wenn nicht installiert: "Installieren" Button
- Wenn installiert: "Deinstallieren" Button + Info (installierte Version/API)
- Fortschritts-Anzeige

**Seite 3 — Preset-Verwaltung:**
- Liste aller vorhandenen Presets
- Aktives Preset hervorgehoben
- "Preset hinzufuegen" (Datei-Dialog)
- "Preset entfernen"
- "Preset aktivieren"

**Seite 4 — Shader-Ordner (optional):**
- Zeigt konfigurierte Shader-Ordner aus ReShade.ini
- Moeglichkeit Shader-Ordner hinzuzufuegen/zu entfernen

### Signal-Flow
```
User oeffnet Wizard (Menu/Toolbar)
    → MainWindow._on_reshade_wizard()
    → ReshadeWizard(game_path, game_binary, parent)
        → ReshadeManager.detect_installed()
        → Zeigt Status auf Seite 1

User waehlt DLL + API → klickt "Installieren"
    → ReshadeManager.install(dll, api)
    → Status-Update auf Seite 1

User klickt "Deinstallieren"
    → ReshadeManager.uninstall()
    → Status-Update auf Seite 1

User verwaltet Presets auf Seite 3
    → ReshadeManager.add_preset() / remove_preset() / set_active_preset()
    → Preset-Liste wird aktualisiert
```

### MO2-Vergleich
MO2 hat **keinen** integrierten ReShade Wizard. Es gibt ein 3rd-Party Plugin "Root Builder" das Root-Dateien managed, aber keine spezifische ReShade-Unterstuetzung. Anvil waere hier ein Vorreiter.

### Wiederverwendung bestehender Code
- **FrameworkMod-Pattern:** ReShade ist kein Framework im Sinne von Anvil (kein automatischer Detect beim Mod-Install). Aber das Deploy-Konzept (Dateien direkt ins Game-Root kopieren) ist aehnlich.
- **ModDeployer:** Der Deployer handled direkte Kopien bereits (`copy_deploy_paths`). ReShade-Dateien sollten aber **unabhaengig** vom Deploy-Zyklus verwaltet werden (sie sollen beim Purge nicht entfernt werden).
- **Instance Wizard (Stil-Vorlage):** Der bestehende `CreateInstanceWizard` nutzt QStackedWidget + Navigation — gleiches Pattern fuer den ReShade Wizard.
- **SettingsDialog (QDialog-Pattern):** Standard-Dialog-Muster mit Tabs/Pages.

### Speicherung
ReShade-Config wird pro Instanz in `.anvil.ini` gespeichert:
```ini
[ReShade]
installed=true
api=dx11
dll_source=/home/user/ReShade/ReShade64.dll
active_preset=MyPreset.ini
```

## Verwandte Funktionen (geprueft)
- `FrameworkMod` → NICHT betroffen (ReShade ist kein Framework, wird separat verwaltet)
- `ModDeployer` → NICHT betroffen (ReShade ist unabhaengig vom Deploy-Zyklus)
- `GamePanel` → NICHT betroffen (kein neuer Tab noetig)
- `BaseGame` → NICHT betroffen (keine Aenderung an Game-Plugins)
- `InstanceManager.save_instance()` → MUSS ERWEITERT werden fuer ReShade-Sektion

## Akzeptanz-Checkliste

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
