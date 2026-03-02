# Agent 3: Settings Dialog Analysis (settings_dialog.py)

## Nexus-Tab Übersicht

Der Nexus-Tab befindet sich in `anvil/widgets/settings_dialog.py`, Zeilen 395-517 (Tab-Aufbau) plus Zeilen 519-532 (API-Init) plus Zeilen 928-1062 (Helper-Methoden).

Der Tab hat ein `QScrollArea`-Layout und ist in **4 GroupBoxen** gegliedert:

1. **Nexus-Konto** (`konto_grp`) — Zeilen 404-432
2. **Nexus-Verbindung** (`verb_grp`) — Zeilen 434-465
3. **Optionen** (`opt_grp`) — Zeilen 467-490
4. **Server** (`server_grp`) — Zeilen 492-512

---

## Vorhandene Widgets

### GroupBox 1: Nexus-Konto
| Widget | Typ | Ref | ReadOnly | Funktion |
|--------|-----|-----|----------|----------|
| User ID | `QLineEdit` | `self._nx_uid` | Ja | Zeigt user_id nach Validierung |
| Name | `QLineEdit` | `self._nx_name` | Ja | Zeigt Nexus-Benutzername |
| Konto | `QLineEdit` | `self._nx_account` | Ja | Zeigt "Premium"/"Supporter"/"Standard" |
| Tägliche Anfragen | `QLineEdit` | `self._nx_daily` | Ja | Zeigt x-rl-daily-remaining |
| Stündliche Anfragen | `QLineEdit` | `self._nx_hourly` | Ja | Zeigt x-rl-hourly-remaining |

### GroupBox 2: Nexus-Verbindung
| Widget | Typ | Ref | Enabled | Funktion |
|--------|-----|-----|---------|----------|
| "Verbinde zu Nexus" | `QPushButton` | `self._btn_connect` | **DISABLED** | SSO-Login starten |
| "API-Schlüssel manuell eingeben" | `QPushButton` | `self._btn_api_key` | **DISABLED** | Manueller Key-Input |
| "Trennen" | `QPushButton` | `self._btn_disconnect` | **DISABLED** | Key löschen + Reset |
| Status-Label | `QLabel` | `self._nx_status_label` | — | "Nicht verbunden." / "Verbunden" |
| Log-Liste | `QListWidget` | `self._nx_log` | — | SSO/Validierungs-Fortschritt |

### GroupBox 3: Optionen (alle DISABLED)
| Widget | Typ | Funktion |
|--------|-----|----------|
| Endorsement Integration | `QCheckBox` | Placeholder |
| Mod-Tracking | `QCheckBox` | Placeholder |
| Kategorie-Mapping | `QCheckBox` | Placeholder |
| API-Zähler ausblenden | `QCheckBox` | Placeholder |
| NXM-Links verknüpfen | `QPushButton` | Backend vorhanden, Button disabled |
| Cache leeren | `QPushButton` | Placeholder |

### GroupBox 4: Server (alle DISABLED)
| Widget | Typ | Funktion |
|--------|-----|----------|
| Known Servers | `QListWidget` | Statische Liste (Amsterdam, Prague, etc.) |
| Preferred Servers | `QListWidget` | Statisch "Nexus CDN (58.45 MB/s)" |

---

## Funktionaler Status

### AKTIV und FUNKTIONAL:
- `self._nx_status_label` — Zeigt Verbindungsstatus
- `self._nx_log` — Log-Liste zeigt SSO/Validierungsnachrichten
- `self._nx_uid`, `self._nx_name`, `self._nx_account` — Werden bei Validierung befüllt
- `self._nx_daily`, `self._nx_hourly` — Werden bei Rate-Limit-Updates befüllt
- **NexusAPI-Instanz** — Vollständig verbunden mit Signals
- **NexusSSOLogin** — Wird on-demand erstellt, voll funktional

### AKTIV aber DISABLED (alle 3 Buttons):
```python
self._btn_connect.clicked.connect(self._nx_connect_sso)   # Signal VERBUNDEN
_disabled(self._btn_connect)                                # aber DISABLED

self._btn_api_key.clicked.connect(self._nx_enter_api_key)  # Signal VERBUNDEN
_disabled(self._btn_api_key)                                # aber DISABLED

self._btn_disconnect.clicked.connect(self._nx_disconnect)  # Signal VERBUNDEN
_disabled(self._btn_disconnect)                              # aber DISABLED
```

**Kritischer Befund:** Die Signal-Verbindungen sind VORHANDEN, die Backend-Methoden sind VOLLSTÄNDIG IMPLEMENTIERT, aber die Buttons können nicht geklickt werden.

### Backend vollständig implementiert:
| Methode | Zeilen | Status |
|---------|--------|--------|
| `_nx_connect_sso()` | 937-950 | Vollständig, startet NexusSSOLogin |
| `_nx_on_sso_state()` | 952-962 | Vollständig, State-to-Log |
| `_nx_on_sso_key()` | 964-971 | Vollständig, speichert Key + validiert |
| `_nx_enter_api_key()` | 973-988 | Vollständig, InputDialog + Validierung |
| `_nx_disconnect()` | 990-1008 | Vollständig, Key löschen + UI reset |
| `_nx_on_validated()` | 1010-1026 | Vollständig, User-Info anzeigen |
| `_nx_on_error()` | 1028-1033 | Vollständig, Fehler anzeigen |
| `_nx_on_rate_limit()` | 1035-1044 | Vollständig, Rate-Limits + MainWindow-Sync |
| `_nx_log_add()` | 930-935 | Vollständig, Log-Widget befüllen |
| `_nx_register_nxm_handler()` | 1046-1061 | Vollständig, Desktop-Integration |

---

## API-Key Speicherung (QSettings)

### QSettings-Pfad:
```
~/.config/AnvilOrganizer/AnvilOrganizer.conf (INI-Format, Klartext)
```

### QSettings-Key: `nexus/api_key`
- **Laden:** Zeile 525: `saved_key = settings.value("nexus/api_key", "")`
- **Speichern (SSO):** Zeile 969: `settings.setValue("nexus/api_key", api_key)`
- **Speichern (Manual):** Zeile 985: `settings.setValue("nexus/api_key", key.strip())`
- **Löschen:** Zeile 998: `settings.remove("nexus/api_key")`

### Lade-Flow beim Öffnen des Dialogs:
```python
saved_key = settings.value("nexus/api_key", "")
if saved_key:
    self._nexus_api.set_api_key(saved_key)
    self._nx_log_add("API-Schlüssel überprüfen...")
    self._nexus_api.validate_key()
else:
    self._nx_log_add(tr("status.not_connected"))
```

---

## Verbindungen zu Nexus-Klassen

### NexusAPI Signal-Verbindungen:
| Signal | Slot |
|--------|------|
| `user_validated(dict)` | `_nx_on_validated()` |
| `request_error(str, str)` | `_nx_on_error()` |
| `rate_limit_updated(int, int)` | `_nx_on_rate_limit()` |

### NexusSSOLogin Signal-Verbindungen (on-demand):
| Signal | Slot |
|--------|------|
| `state_changed(int, str)` | `_nx_on_sso_state()` |
| `key_changed(str)` | `_nx_on_sso_key()` |

### MainWindow-Sync (duck-typed, Zeilen 1041-1044):
```python
parent = self.parent()
if parent and hasattr(parent, "_update_api_status"):
    parent._update_api_status(daily, hourly)
```

---

## Fehlende Verbindungen

### 1. Buttons müssen aktiviert werden
Alle 3 Kernbuttons sind disabled. `_disabled()` muss entfernt werden.

### 2. Dynamische Button-States fehlen
MO2-Verhalten:
- Nicht verbunden: Connect + API-Key aktiv, Disconnect disabled
- Verbunden: Connect + API-Key disabled, Disconnect aktiv
- SSO läuft: Connect zeigt "Abbrechen", API-Key disabled

### 3. Kein API-Key-Sync zwischen SettingsDialog und MainWindow
- Wenn im SettingsDialog ein neuer Key gesetzt wird, läuft die Validierung nur in der Dialog-Instanz
- MainWindow liest den Key nach `accept()` aus QSettings — aber was bei "Abbrechen"?

### 4. `_disabled()` setzt auch Tooltip
`_disabled()` setzt `setToolTip(tr("settings.coming_soon"))` — muss ebenfalls zurückgesetzt werden.

---

## Empfehlungen

### Minimale Änderungen für SSO-Flow-Aktivierung:

1. **Buttons aktivieren** — `_disabled()` von `_btn_connect`, `_btn_api_key`, `_btn_disconnect` entfernen
2. **Dynamische Button-States** — `_nx_update_button_states()` Methode einbauen
3. **NXM-Handler-Button** — Ebenfalls aktivieren, Implementierung ist komplett
4. **Tooltip entfernen** — `_disabled()` setzt "Coming Soon" Tooltip

### Vergleich mit anderen Tabs:

| Tab | Disabled-Anteil |
|-----|-----------------|
| Allgemein | ~10% |
| Style | ~60% |
| Mod Liste | 0% |
| Pfade | ~10% |
| **Nexus** | **~80%** |
| Plugins | ~5% |
| Workarounds | 100% (auskommentiert) |
| Diagnose | 100% (auskommentiert) |

**Fazit:** Der Nexus-Tab hat den höchsten Anteil an disabled Widgets trotz vollständig implementiertem Backend. Die Aktivierung erfordert nur das Entfernen von `_disabled()` bei den 3 Kern-Buttons plus eine dynamische State-Verwaltung.
