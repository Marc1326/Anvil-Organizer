# Feature: Nexus Endorsement Integration + Category Mapping
Datum: 2026-04-05

Konsolidierte Feature-Spec (Agent 4), basierend auf:
- Agent 1: Bestehender Code-Analyse (`docs/anvil-agent1-plan.md`)
- Agent 2: MO2-Referenz-Analyse (`docs/workflow/planer-agent-2-endorsement-catmap.md`)
- Agent 3: Architektur + Signal-Flow (`docs/anvil-agent3-plan.md`)

---

## User Stories

### Feature 1: Endorsement Integration

- Als User moechte ich nach der Installation einer Nexus-Mod gefragt werden, ob ich sie endorsen will, damit ich die Mod-Autoren direkt unterstuetzen kann.
- Als User moechte ich per Rechtsklick eine Mod endorsen oder das Endorsement entfernen koennen, damit ich meine Meinung jederzeit aendern kann.
- Als User moechte ich die Endorsement-Aufforderung global abschalten koennen, damit ich nicht bei jeder Installation gestoert werde.
- Als User moechte ich Mods nach Endorsement-Status filtern koennen, damit ich sehe welche Mods ich noch nicht endorsed habe.

### Feature 3: Category Mapping

- Als User moechte ich per Rechtsklick "Kategorie neu zuordnen (von Nexus)" waehlen koennen, damit meine Mods automatisch eine passende lokale Kategorie erhalten.
- Als User moechte ich "Kategorien automatisch zuweisen" fuer alle Mods ausfuehren koennen, damit ich nicht jede Mod einzeln zuordnen muss.
- Als User moechte ich, dass bestehende Kategorien NICHT ueberschrieben werden, damit meine manuelle Zuordnung erhalten bleibt.
- Als User moechte ich in den Einstellungen Category Mapping aktivieren/deaktivieren koennen.

---

## Technische Planung

### Betroffene Dateien

| Datei | Aenderung | Umfang |
|-------|-----------|--------|
| `anvil/core/nexus_api.py` | `_ApiPostWorker`, `_post()`, `endorse_mod()`, `abstain_mod()`, `get_game_categories()` | ~70 Zeilen |
| `anvil/core/mod_entry.py` | Neues Feld `endorsed: int = 3` + Parsing in `_build_entry()` | ~10 Zeilen |
| `anvil/core/nexus_categories.py` | **NEUE DATEI** — Cache + Mapping-Logik | ~120 Zeilen |
| `anvil/dialogs/endorsement_dialog.py` | **NEUE DATEI** — Endorsement-Prompt-Dialog | ~80 Zeilen |
| `anvil/widgets/mod_list.py` | `PROP_ENDORSED` + `PROP_HAS_NOTES` Filter in `filterAcceptsRow()` | ~10 Zeilen |
| `anvil/mainwindow.py` | Endorsement-Queue + Prompt-Trigger + Response-Handler + Kontextmenu aktivieren + Category-Zuordnungs-Logik + Nexus-Categories-Laden | ~150 Zeilen |
| `anvil/widgets/settings_dialog.py` | 2 Checkboxen aktivieren (Endorsement + Category Mapping) | ~15 Zeilen |
| `anvil/widgets/category_dialog.py` | Spalte "Nexus Kategorie" mit echten Namen befuellen | ~10 Zeilen |
| `anvil/locales/*.json` (7 Dateien) | ~15 neue Keys pro Datei | ~105 Zeilen gesamt |

### Neue Dateien

| Datei | Zweck |
|-------|-------|
| `anvil/dialogs/endorsement_dialog.py` | Modal-Dialog: "Mod endorsen? [Endorsen] [Spaeter] [Nie fuer diesen Mod]" |
| `anvil/core/nexus_categories.py` | `NexusCategoryCache` (JSON-Cache pro Instanz) + `map_nexus_to_anvil()` + `assign_nexus_categories()` |

---

## Signal-Flow

### Feature 1: Endorsement — Post-Install Prompt

```
_install_archives()
    |
    v  (nach Update-Check-Queue, Zeile ~2204)
[Setting "Nexus/endorsement_enabled" aktiv?]
[API-Key vorhanden?]
[Plugin/Instanz geladen?]
    |  Ja
    v
[Iteriere ueber installierte Mods]
    ├── nexus_id > 0?
    ├── meta.ini endorsed in ("0", "3")?  (Undecided oder Unknown)
    └── → _endorsement_queue fuellen
    |
    v
QTimer.singleShot(500ms)
    |
    v
_show_next_endorsement_prompt()
    |
    v
EndorsementDialog (modal)
    ├── [Endorsen] → POST /games/{game}/mods/{id}/endorse.json
    │                 meta.ini: endorsed="1"
    │                 StatusBar: "Endorsed: {name}"
    │
    ├── [Spaeter]  → Nichts tun, endorsed bleibt unveraendert
    │                 Naechstes Mal wieder fragen
    │
    └── [Nie fuer diesen Mod] → POST /games/{game}/mods/{id}/abstain.json
                                  meta.ini: endorsed="2"
                                  Wird nicht wieder gefragt

    Checkbox "Nicht mehr fragen":
    → Setting "Nexus/endorsement_enabled" = False
    → Queue leeren, keine weiteren Prompts
```

### Feature 1: Endorsement — Kontextmenu

```
[Rechtsklick auf Mod]
    |
    v
Kontextmenu zeigt:
    ├── "Mod endorsen" (wenn endorsed != "1")
    │     → POST endorse.json
    │     → meta.ini: endorsed="1"
    │
    └── "Endorsement entfernen" (wenn endorsed == "1")
          → POST abstain.json
          → meta.ini: endorsed="2"
```

### Feature 1: Response-Handler

```
_on_nexus_response(tag, data)
    |
    ├── tag "endorse:{game}:{mod_id}"
    │     → Log: "Endorsement gesendet (Mod {mod_id})"
    │
    └── tag "abstain:{game}:{mod_id}"
          → Log: "Endorsement entfernt (Mod {mod_id})"

_on_nexus_error(tag, message)
    |
    ├── tag "endorse:..." oder "abstain:..."
    │     → Log: "Endorsement fehlgeschlagen: {message}"
    │     → StatusBar: Fehlermeldung
    └── Endorsed-Wert in meta.ini NICHT aendern bei Fehler
```

### Feature 3: Nexus-Kategorien laden (lazy, bei Instanz-Wechsel)

```
_apply_instance()
    |
    v
_load_nexus_categories()
    |
    ├── nexus_categories.json existiert und < 30 Tage alt?
    │     → Cache verwenden, KEIN API-Call
    │
    └── Nicht vorhanden oder abgelaufen?
          → nexus_api.get_game_categories(game_slug)
          → GET /v1/games/{game}.json
          |
          v
    _on_nexus_response(tag="game_categories:{game}", data)
          → data["categories"] extrahieren
          → NexusCategoryCache.save()
          → Log: "Nexus-Kategorien geladen: {count}"
```

### Feature 3: Einzelmod "Kategorie neu zuordnen"

```
[Rechtsklick → "Kategorie neu zuordnen (von Nexus)"]
    |
    v
_ctx_reassign_category(row)
    |
    ├── Mod hat nexusCategory in meta.ini?
    │     → Nein: StatusBar "Keine Nexus-Kategorie bekannt"
    │
    └── Ja: nexus_cat_id lesen (z.B. "5")
          |
          v
    assign_nexus_categories(mod_path, nexus_cat_id, cache, cat_mgr)
          |
          ├── 1. Nexus-ID → Nexus-Name (aus Cache)
          ├── 2. Nexus-Name → Anvil-Name (Fuzzy-Mapping)
          ├── 3. Anvil-Name → Anvil-ID (aus CategoryManager)
          ├── 4. MERGE: Nur hinzufuegen wenn nicht schon vorhanden
          └── 5. write_meta_ini(category=neue_ids)
          |
          v
    _reload_mod_list()
    StatusBar: "Kategorie zugeordnet: {category} fuer {name}"
```

### Feature 3: Batch "Kategorien automatisch zuweisen"

```
[Kontextmenu → "Alle Mods" → "Kategorien automatisch zuweisen"]
    |
    v
_ctx_auto_assign_categories()
    |
    ├── nexus_categories.json vorhanden?
    │     → Nein: API-Call + Warten (oder Fehlermeldung)
    │
    └── Ja: Iteriere ueber alle Mods
          |
          v
    Fuer jeden Mod mit nexusCategory in meta.ini:
        assign_nexus_categories(...)  → MERGE (nicht overwrite)
    |
    v
    _reload_mod_list()
    FilterPanel.set_categories(...)  → Neue Kategorien anzeigen
    StatusBar: "{X} Mods zugeordnet, {Y} uebersprungen"
```

---

## MO2-Vergleich

### Feature 1: Endorsement

| Aspekt | MO2 | Anvil (Geplant) |
|--------|-----|-----------------|
| Endorsement-Zustaende | 4 (True/False/Never/Unknown) | 4 (1/0/2/3) — identisch |
| Kontextmenu | Dynamisch je Status | Dynamisch je Status — uebernommen |
| Batch-Endorsement | Ja, alle ausgewaehlten | Nein — zu riskant wegen Rate-Limits |
| Flag-Icon "Not Endorsed" | Ja (nervt User) | Nein — bewusst ausgelassen |
| Auto-Prompt nach Install | NEIN (MO2 hat das NICHT) | JA — neues Feature fuer Anvil |
| Settings-Toggle | `endorsement_integration` | `Nexus/endorsement_enabled` |
| 15-Min Cooldown | Nur Warnung im Tooltip | Klare Fehlermeldung bei Fehler |

**Wichtig:** Der Auto-Prompt nach Installation ist ein Anvil-Eigenfeature, das MO2 nicht hat. MO2 bietet Endorsement nur ueber das Kontextmenu an.

### Feature 3: Category Mapping

| Aspekt | MO2 | Anvil (Geplant) |
|--------|-----|-----------------|
| Mapping-Strategie | `setPrimaryCategory()` — UEBERSCHREIBT stumm | MERGE — bestehende Kategorien bleiben |
| Remap-Verhalten | Setzt Primary ohne Warnung | Fuegt Kategorie hinzu, Primary bleibt |
| Import-Optionen | Merge/Overwrite/None Dialog | Immer Merge (Marcs Anforderung) |
| Speicher-Format | `nexuscatmap.dat` (Pipe-separiert) | `nexus_categories.json` (JSON-Cache) |
| Name-Matching | Feste Mapping-Tabelle pro Spiel | Fuzzy Name-Matching + Fallback |
| Unbekannte Kategorien | → 0 (nicht gemappt) | → Neue Anvil-Kategorie erstellen |
| Auto-Mapping bei Install | Ja (mit Dialog bei fehlender Zuordnung) | Nein (nur on-demand per Kontextmenu) |
| Cache-Dauer | Kein Expiry | 30 Tage, dann API-Refresh |

---

## Neue Klassen und Methoden (Signaturen)

### `anvil/core/nexus_api.py` — Erweiterungen

```python
class _ApiPostWorker(QThread):
    """Background thread fuer HTTP POST Requests."""
    finished = Signal(str, int, dict, bytes)  # (tag, status, headers, body)
    error = Signal(str, str)                  # (tag, error_message)
    def __init__(self, url: str, headers: dict, body: bytes, tag: str, parent=None): ...
    def run(self) -> None: ...

# Auf NexusAPI-Klasse:
def _post(self, path: str, body: dict, tag: str = "") -> None: ...
def endorse_mod(self, game: str, mod_id: int, version: str = "") -> None: ...
def abstain_mod(self, game: str, mod_id: int, version: str = "") -> None: ...
def get_game_categories(self, game: str) -> None: ...
```

Tag-Format:
- `endorse:{game}:{mod_id}` — POST Endorsement
- `abstain:{game}:{mod_id}` — POST Abstain
- `game_categories:{game}` — GET Game-Kategorien

### `anvil/dialogs/endorsement_dialog.py` — Neue Datei

```python
class EndorsementDialog(QDialog):
    """Endorsement-Prompt nach Mod-Installation.

    Layout:
        "Moechtest du {name} auf Nexus Mods endorsen?"
        [ Endorsen ] [ Spaeter ] [ Nie fuer diesen Mod ]
        [ ] Nicht mehr fragen
    """
    ENDORSE = 1
    LATER = 2
    NEVER = 3

    def __init__(self, mod_name: str, mod_id: int, parent=None): ...
    def dont_ask_again(self) -> bool: ...
```

### `anvil/core/nexus_categories.py` — Neue Datei

```python
# Vordefiniertes Name-Mapping (Nexus-Kategoriename → Anvil-Kategoriename)
_NEXUS_TO_ANVIL: dict[str, str] = {
    "animations": "Animations",
    "animation": "Animations",
    "armour": "Armor & Clothing",
    "armor": "Armor & Clothing",
    "clothing": "Armor & Clothing",
    "audio": "Audio",
    "sound": "Audio",
    "bug fixes": "Bug Fixes",
    "patches": "Patches",
    "gameplay": "Gameplay",
    "graphics": "Graphics",
    "hair": "Hair & Face",
    "face": "Hair & Face",
    "items": "Items",
    "weapons": "Weapons",
    "miscellaneous": "Miscellaneous",
    "models and textures": "Models & Textures",
    "models & textures": "Models & Textures",
    "textures": "Models & Textures",
    "npc": "NPC",
    "companions": "NPC",
    "overhauls": "Overhauls",
    "player homes": "Player Homes",
    "user interface": "UI",
    "ui": "UI",
    "utilities": "Utilities",
    # ... weitere spiel-spezifische Mappings
}

class NexusCategoryCache:
    """Cached Nexus-Kategorien pro Instanz (nexus_categories.json)."""
    FILENAME = "nexus_categories.json"
    MAX_AGE_DAYS = 30

    def __init__(self, instance_path: Path): ...
    def load(self) -> bool: ...
    def save(self, game_slug: str, categories: list[dict]) -> None: ...
    def is_expired(self) -> bool: ...
    def get_categories(self) -> list[dict]: ...
    def find_nexus_category(self, nexus_cat_id: int) -> str: ...

def map_nexus_to_anvil(nexus_name: str) -> str | None: ...

def assign_nexus_categories(
    mod_path: Path,
    nexus_cat_id: int,
    nexus_cache: NexusCategoryCache,
    category_manager: CategoryManager,
) -> list[int]:
    """Weist Anvil-Kategorie zu, MERGED mit bestehenden (ueberschreibt nie)."""
    ...
```

### `anvil/mainwindow.py` — Neue Methoden

```python
# Endorsement
def _show_next_endorsement_prompt(self) -> None: ...
def _ctx_endorse_mod(self, row: int) -> None: ...
def _ctx_remove_endorsement(self, row: int) -> None: ...

# Category Mapping
def _load_nexus_categories(self) -> None: ...
def _ctx_reassign_category(self, row: int) -> None: ...
def _ctx_auto_assign_categories(self) -> None: ...
```

### `anvil/core/mod_entry.py` — Feld-Erweiterung

```python
@dataclass
class ModEntry:
    # ... bestehende Felder ...
    endorsed: int = 3  # 0=Undecided, 1=Endorsed, 2=Abstained, 3=Unknown
```

### `anvil/widgets/mod_list.py` — Filter-Fix (Bug)

```python
# In filterAcceptsRow(): PROP_ENDORSED und PROP_HAS_NOTES importieren
# und in der Property-Filter-Logik ergaenzen:
from anvil.widgets.filter_panel import (
    PROP_ENABLED, PROP_DISABLED, PROP_ENDORSED, PROP_HAS_NOTES,
    PROP_HAS_CATEGORY, PROP_NO_CATEGORY, PROP_CONFLICT_WIN, PROP_CONFLICT_LOSE,
)

# Endorsed-Filter:
if PROP_ENDORSED in self._filter_prop_ids and entry.endorsed == 1:
    match = True

# Has-Notes-Filter (sofern notes-Feld vorhanden):
if PROP_HAS_NOTES in self._filter_prop_ids and getattr(entry, "notes", ""):
    match = True
```

---

## Neue Locale-Keys (alle 7 Sprachen)

Die folgenden Keys muessen in allen 7 Locale-Dateien ergaenzt werden.
Bestehende Keys (context.remove_endorsement, filter.prop_endorsed, etc.) bleiben unveraendert.

### Endorsement-Dialog
| Key | DE | EN |
|-----|----|----|
| `endorsement_dialog.title` | Mod endorsen? | Endorse mod? |
| `endorsement_dialog.text` | Moechtest du "{name}" auf Nexus Mods endorsen? | Would you like to endorse "{name}" on Nexus Mods? |
| `endorsement_dialog.endorse` | Endorsen | Endorse |
| `endorsement_dialog.later` | Spaeter | Later |
| `endorsement_dialog.never` | Nie fuer diesen Mod | Never for this mod |
| `endorsement_dialog.dont_ask` | Nicht mehr fragen | Don't ask again |

### Kontextmenu
| Key | DE | EN |
|-----|----|----|
| `context.endorse_mod` | Mod endorsen | Endorse mod |

### Status- und Log-Meldungen
| Key | DE | EN |
|-----|----|----|
| `status.endorsed_mod` | Endorsed: {name} | Endorsed: {name} |
| `status.endorsement_removed` | Endorsement entfernt: {name} | Endorsement removed: {name} |
| `status.categories_assigned` | Kategorien zugeordnet: {count} Mods aktualisiert | Categories assigned: {count} mods updated |
| `status.category_assigned_single` | Kategorie zugeordnet: {category} fuer {name} | Category assigned: {category} for {name} |
| `status.no_nexus_category` | Keine Nexus-Kategorie bekannt. Zuerst 'Nexus-Info abrufen'. | No Nexus category known. Run 'Query Nexus Info' first. |
| `status.nexus_categories_loaded` | Nexus-Kategorien geladen: {count} Kategorien | Nexus categories loaded: {count} categories |
| `log.endorsement_success` | Endorsement gesendet (Mod {mod_id}) | Endorsement sent (Mod {mod_id}) |
| `log.abstain_success` | Endorsement entfernt (Mod {mod_id}) | Endorsement removed (Mod {mod_id}) |
| `log.endorsement_error` | Endorsement fehlgeschlagen: {message} | Endorsement failed: {message} |

---

## Risiken und Edge Cases

### Feature 1: Endorsement

| Risiko | Wahrscheinlichkeit | Mitigation |
|--------|---------------------|------------|
| Nexus 403 "Too early to endorse" (Mod muss heruntergeladen worden sein) | Mittel | Fehler abfangen, Meldung anzeigen, endorsed bleibt "0" |
| Rate-Limit bei vielen Installationen | Niedrig (kein Batch) | Queue mit 500ms Delay zwischen Dialogen |
| User schliesst Dialog mit X | Niedrig | `QDialog.Rejected` = "Spaeter" |
| Mod hat keine Nexus-ID (manuell installiert) | Haeufig | Nur Mods mit `nexus_id > 0` in Queue |
| meta.ini hat kein endorsed-Feld (alte Mods) | Haeufig | Default "3" → Prompt erscheint |
| endorsed-Wert bei API-Fehler prematurely geschrieben | Mittel | meta.ini VOR API-Call schreiben (optimistisch), bei Fehler zuruecksetzen ODER meta.ini NACH API-Antwort schreiben (konservativ) |
| Race Condition: API-Response nach Instanz-Wechsel | Niedrig | Tags enthalten game_slug — bei Mismatch verwerfen |

**Empfehlung:** meta.ini optimistisch VOR dem API-Call aktualisieren (wie bei Update-Check-Pattern), damit der User sofort visuelles Feedback bekommt. Bei API-Fehler: Log-Eintrag + StatusBar-Meldung, aber meta.ini-Wert bleibt (User kann per Kontextmenu aendern).

### Feature 3: Category Mapping

| Risiko | Wahrscheinlichkeit | Mitigation |
|--------|---------------------|------------|
| Nexus-Kategorie hat kein Anvil-Mapping | Mittel | Nexus-Kategoriename als neue Anvil-Kategorie erstellen |
| Mod hat nexusCategory=0 | Haeufig | Ueberspringen, bestehende Kategorien beibehalten |
| Game API-Response hat unerwartetes Format | Niedrig | Defensiv parsen, bei Fehler Cache nicht aktualisieren |
| nexus_categories.json korrupt | Niedrig | JSONDecodeError abfangen, neu laden |
| Batch-Zuordnung dauert lange (500+ Mods) | Mittel | Kein API-Call noetig (nur Cache + meta.ini), Fortschrittsanzeige |
| Mehrere Anvil-Kategorien fuer eine Nexus-Kategorie | Niedrig | Erstes Match aus Mapping-Tabelle gewinnt |

---

## Verwandte Funktionen (geprueft)

| Funktion | Gleicher Fix noetig? | Begruendung |
|----------|---------------------|-------------|
| `PROP_HAS_NOTES` Filter in mod_list.py | JA | Fehlt genauso wie PROP_ENDORSED im filterAcceptsRow — gleicher Bug |
| Endorsement-Parsing Duplikat (Zeile 4839 vs 4906) | JA (Refactoring) | Identische Logik an 2 Stellen — sollte in Hilfsfunktion extrahiert werden |
| nexusCategory-Parsing Duplikat (Zeile 4858 vs 4926) | JA (Refactoring) | Gleiches Problem wie Endorsement-Parsing |
| `category_dialog.py` Spalte 4 "Nexus Kategorie" | JA | Zeigt nur "-" — sollte echte Nexus-Kategorienamen anzeigen wenn Cache vorhanden |
| Toolbar "endorse.svg" Button | NEIN | Ist ein "Support/Donate" Button, kein Endorsement-Button — unabhaengig |

---

## Implementierungs-Reihenfolge

### Phase 1: Shared Infrastructure
1. `nexus_api.py`: `_ApiPostWorker` + `_post()` Methode
2. `mod_entry.py`: `endorsed: int = 3` Feld + Parsing in `_build_entry()`
3. `mod_list.py`: `PROP_ENDORSED` + `PROP_HAS_NOTES` Filter-Fix

### Phase 2: Endorsement Integration
1. `endorsement_dialog.py`: Neuer Dialog (neue Datei)
2. `nexus_api.py`: `endorse_mod()` + `abstain_mod()`
3. `mainwindow.py`: Endorsement-Queue + `_show_next_endorsement_prompt()`
4. `mainwindow.py`: Kontextmenu "Endorsen" / "Endorsement entfernen" aktivieren
5. `mainwindow.py`: Response-Handler fuer `endorse:` und `abstain:` Tags
6. `settings_dialog.py`: Endorsement-Checkbox aktivieren
7. Locale-Dateien: Endorsement-Keys

### Phase 3: Category Mapping
1. `nexus_categories.py`: Cache + Mapping-Logik (neue Datei)
2. `nexus_api.py`: `get_game_categories()`
3. `mainwindow.py`: `_load_nexus_categories()` + Response-Handler
4. `mainwindow.py`: `_ctx_reassign_category()` + `_ctx_auto_assign_categories()`
5. `mainwindow.py`: Kontextmenu-Eintraege aktivieren
6. `category_dialog.py`: Spalte 4 mit Nexus-Namen befuellen
7. `settings_dialog.py`: Category-Mapping-Checkbox aktivieren
8. Locale-Dateien: Category-Keys

Phase 2 und Phase 3 sind unabhaengig voneinander und koennen parallel implementiert werden. Beide haengen von Phase 1 ab (POST-Support + ModEntry-Erweiterung).

---

## Akzeptanz-Checkliste

### Feature 1: Endorsement Integration

- [ ] 1. Wenn User eine Mod mit Nexus-ID installiert und Setting "Endorsement Integration" aktiv ist, erscheint nach der Installation ein Dialog mit den Optionen "Endorsen", "Spaeter" und "Nie fuer diesen Mod"
- [ ] 2. Wenn User im Endorsement-Dialog "Endorsen" waehlt, wird ein POST an `/v1/games/{game}/mods/{id}/endorse.json` gesendet und meta.ini wird auf endorsed="1" gesetzt
- [ ] 3. Wenn User im Endorsement-Dialog "Spaeter" waehlt, wird nichts gespeichert und beim naechsten Installieren derselben Mod erneut gefragt
- [ ] 4. Wenn User im Endorsement-Dialog "Nie fuer diesen Mod" waehlt, wird ein POST an abstain.json gesendet, meta.ini auf endorsed="2" gesetzt und bei dieser Mod nie wieder gefragt
- [ ] 5. Wenn User die Checkbox "Nicht mehr fragen" aktiviert, wird das Setting "Nexus/endorsement_enabled" auf False gesetzt und es erscheinen keine weiteren Endorsement-Dialoge mehr
- [ ] 6. Wenn User eine manuell installierte Mod (ohne Nexus-ID) installiert, erscheint kein Endorsement-Dialog
- [ ] 7. Wenn User eine bereits endorsed Mod (endorsed="1") reinstalliert, erscheint kein Endorsement-Dialog
- [ ] 8. Wenn User per Rechtsklick auf eine nicht-endorsed Mod "Mod endorsen" waehlt, wird POST endorse.json gesendet und meta.ini aktualisiert
- [ ] 9. Wenn User per Rechtsklick auf eine endorsed Mod "Endorsement entfernen" waehlt, wird POST abstain.json gesendet und meta.ini aktualisiert
- [ ] 10. Wenn die Nexus API einen Fehler zurueckgibt (z.B. 403), wird eine Fehlermeldung in StatusBar und Log angezeigt
- [ ] 11. Wenn User den Filter-Chip "Endorsed" im FilterPanel aktiviert, werden nur Mods mit endorsed=1 angezeigt
- [ ] 12. Wenn User in Settings die Checkbox "Endorsement Integration" deaktiviert, erscheinen nach der Installation keine Endorsement-Dialoge mehr

### Feature 3: Category Mapping

- [ ] 13. Wenn User per Rechtsklick auf eine Mod "Kategorie neu zuordnen (von Nexus)" waehlt und die Mod eine nexusCategory hat, wird die passende Anvil-Kategorie HINZUGEFUEGT (nicht ueberschrieben)
- [ ] 14. Wenn User "Kategorie neu zuordnen" waehlt und die Mod keine nexusCategory hat, erscheint eine Meldung "Keine Nexus-Kategorie bekannt. Zuerst Nexus-Info abrufen"
- [ ] 15. Wenn User "Kategorie neu zuordnen" waehlt und die Mod die gemappte Kategorie bereits hat, aendert sich nichts (keine Duplikate)
- [ ] 16. Wenn User per Kontextmenu → "Alle Mods" → "Kategorien automatisch zuweisen" waehlt, werden alle Mods mit nexusCategory zugeordnet und die StatusBar zeigt "{X} Mods aktualisiert"
- [ ] 17. Wenn User eine Mod mit manuell gesetzter Kategorie "Gameplay" hat und "Kategorie zuordnen" waehlt wobei Nexus "Armor" mapped, hat die Mod danach BEIDE Kategorien ("Gameplay" + "Armor & Clothing")
- [ ] 18. Wenn eine Nexus-Kategorie keiner bestehenden Anvil-Kategorie zugeordnet werden kann, wird eine neue Anvil-Kategorie mit dem Nexus-Kategorienamen erstellt
- [ ] 19. Wenn User in Settings die Checkbox "Nexus-Kategoriezuordnungen" aktiviert hat und eine Instanz geladen wird, werden Nexus-Kategorien im Hintergrund gecached (nexus_categories.json)
- [ ] 20. Wenn der Nexus-Kategorien-Cache aelter als 30 Tage ist, wird bei Instanzwechsel ein neuer API-Call gesendet
- [ ] 21. Wenn im CategoryDialog die Spalte "Nexus Kategorie" angezeigt wird, steht dort der echte Nexus-Kategoriename statt nur "-"

### Allgemein

- [ ] 22. Wenn kein API-Key gesetzt ist, sind alle Endorsement- und Category-Mapping-Kontextmenu-Eintraege ausgegraut
- [ ] 23. Wenn User beide Features gleichzeitig nutzt (Endorsement + Category Mapping), gibt es keine Konflikte oder Race Conditions
- [ ] 24. Alle 7 Locale-Dateien (de, en, es, fr, it, pt, ru) enthalten die neuen Keys ohne fehlende Eintraege
- [ ] 25. `./restart.sh` startet ohne Fehler
