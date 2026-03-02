# Feature: Nexus-Info abrufen (Query Info)
Datum: 2026-03-02

## User Stories

- Als User möchte ich für manuell installierte Mods (modid=0) die Nexus-Mod-ID eingeben können, damit die Mod-Metadaten (Name, Version, Autor, Beschreibung, URL) automatisch von Nexus geladen und in der meta.ini gespeichert werden.
- Als User möchte ich für Mods die bereits eine nexus_id > 0 haben, per Rechtsklick die Nexus-Info aktualisieren können, damit Änderungen auf Nexus (neue Version, Beschreibung) lokal übernommen werden.
- Als User möchte ich nach dem Abrufen der Nexus-Info den Menü-Eintrag "Nexus-Seite öffnen" nutzen können, der vorher ausgegraut war.

## Technische Planung

### Betroffene Dateien

| Datei | Änderung |
|-------|----------|
| `anvil/core/nexus_api.py` | Neue Methode `query_mod_info()` mit separatem Tag-Prefix `query_mod_info:` |
| `anvil/mainwindow.py` | Neuer Kontextmenü-Eintrag + Handler `_ctx_query_nexus_info()` + Tag-Routing in `_on_nexus_response()` |
| `anvil/widgets/game_panel.py` | Neues Signal `nexus_query_requested = Signal()` + Button unter Start-Button |
| `anvil/locales/de.json` | 6 neue i18n-Keys |
| `anvil/locales/en.json` | 6 neue i18n-Keys |
| `anvil/locales/es.json` | 6 neue i18n-Keys |
| `anvil/locales/fr.json` | 6 neue i18n-Keys |
| `anvil/locales/it.json` | 6 neue i18n-Keys |
| `anvil/locales/pt.json` | 6 neue i18n-Keys |

### Signal-Flow

**Szenario A: Mod hat nexus_id > 0 (Kontextmenü)**

```
User Rechtsklick auf Mod → "Nexus-Info abrufen"
  → _ctx_query_nexus_info(row)
  → entry = self._current_mod_entries[row]
  → self._pending_query_path = entry.install_path   # Path, NICHT row!
  → nexus_slug = GameNexusName || GameShortName
  → self._nexus_api.query_mod_info(nexus_slug, entry.nexus_id)
  → statusBar: tr("status.nexus_query_loading")
  → ...API-Response...
  → _on_nexus_response(tag="query_mod_info:{game}:{mod_id}", data={...})
  → write_meta_ini(self._pending_query_path, {modid, version, name, author, description, url})
  → _reload_mod_list()
  → statusBar: tr("status.nexus_query_success", name=data["name"])
```

**Szenario B: Mod hat nexus_id = 0 (manuelle ID-Eingabe)**

```
User Rechtsklick auf Mod → "Nexus-Info abrufen"
  → _ctx_query_nexus_info(row)
  → entry.nexus_id == 0
  → QInputDialog.getText(self, tr("dialog.nexus_query_title"), tr("dialog.nexus_query_prompt"))
  → User gibt Nexus-Mod-ID ein (z.B. "107658")
  → Validierung: int() > 0, sonst Abbruch
  → self._pending_query_path = entry.install_path
  → self._nexus_api.query_mod_info(nexus_slug, eingegebene_id)
  → statusBar: tr("status.nexus_query_loading")
  → ... (gleicher Response-Flow wie Szenario A)
```

**Szenario C: Button im GamePanel**

```
User klickt "Nexus-Info abrufen"-Button im GamePanel
  → GamePanel.nexus_query_requested.emit()
  → MainWindow._on_nexus_query_from_panel()
  → selected_rows = self._mod_list_view.get_selected_source_rows()
  → Falls keine/mehrere Selektion: statusBar-Warnung, return
  → _ctx_query_nexus_info(selected_rows[0])   # wiederverwendet
```

### Tag-Kollision vermeiden

Der bestehende `mod_info:` Tag-Prefix wird bereits für den NXM-Download-Flow genutzt. Ein neuer Prefix `query_mod_info:` ist zwingend nötig.

**Neue Methode in nexus_api.py:**
```python
def query_mod_info(self, game: str, mod_id: int) -> None:
    """Fetch mod metadata for Query Info feature.
    Uses separate tag prefix to avoid collision with NXM download flow.
    """
    self._get(f"/games/{game}/mods/{mod_id}.json",
              tag=f"query_mod_info:{game}:{mod_id}")
```

### Row-Verschiebung vermeiden

Zwischen API-Request und Response kann sich die Mod-Liste ändern. Deshalb wird `install_path` (Path-Objekt) zwischengespeichert, NICHT der Row-Index.

```python
self._pending_query_path: Path | None = None
```

### meta.ini Update (nach Response)

```python
write_meta_ini(self._pending_query_path, {
    "modid": str(data.get("mod_id", 0)),
    "version": data.get("version", ""),
    "newestVersion": data.get("version", ""),
    "name": data.get("name", ""),
    "author": data.get("author", ""),
    "description": data.get("summary", ""),
    "url": f"https://www.nexusmods.com/{nexus_slug}/mods/{data.get('mod_id', 0)}",
})
```

**Hinweis:** Nexus API liefert `summary` (Kurztext) und `description` (HTML-Langtext). Wir verwenden `summary` für meta.ini `description`, wie MO2.

### MO2-Vergleich

| Aspekt | MO2 | Anvil (geplant) |
|--------|-----|-----------------|
| Trigger | Kontextmenü "Query Info" | Kontextmenü "Nexus-Info abrufen" + GamePanel-Button |
| Ohne Nexus-ID | MD5-Hash-Suche + Datei-Auswahl-Dialog | Manuelle ID-Eingabe (einfacher, zuverlässiger) |
| Tag-Routing | Eigener Request-Typ `TYPE_MODINFO` | Separater Tag `query_mod_info:` |
| meta.ini Update | Direkt in ModInfo-Objekt + Speichern | `write_meta_ini()` + `_reload_mod_list()` |
| Batch-Query | Ja (alle Mods auf einmal) | Nein (einzeln, Rate-Limit-bewusst) |

**Bewusste Abweichung:** MO2 nutzt MD5-Hash-Suche als Fallback. Die Nexus v1 API bietet `/games/{game}/mods/md5_search/{hash}.json`, aber das erfordert den MD5-Hash der Original-Installationsdatei (Archiv), NICHT des entpackten Mod-Ordners. Da manuell installierte Mods das Archiv nicht mehr haben, ist MD5-Suche unpraktisch. Die manuelle ID-Eingabe ist zuverlässiger — der User kopiert die ID aus der Nexus-URL.

### Neue i18n-Keys

| Key | DE | EN |
|-----|----|----|
| `context.nexus_query` | "Nexus-Info abrufen" | "Query Nexus Info" |
| `dialog.nexus_query_title` | "Nexus Mod-ID eingeben" | "Enter Nexus Mod ID" |
| `dialog.nexus_query_prompt` | "Nexus Mod-ID (aus der URL, z.B. 107658):" | "Enter Nexus Mod ID (from URL, e.g. 107658):" |
| `status.nexus_query_loading` | "Lade Nexus-Info..." | "Loading Nexus info..." |
| `status.nexus_query_success` | "Nexus-Info aktualisiert: {name}" | "Nexus info updated: {name}" |
| `status.nexus_query_invalid_id` | "Ungültige Mod-ID eingegeben." | "Invalid Mod ID entered." |

(Alle 6 Keys müssen in allen 6 Locale-Dateien vorhanden sein: de, en, es, fr, it, pt)

## Abhängigkeiten

1. **Nexus API-Key muss gesetzt sein** — ohne Key werden alle API-Calls mit Fehler beantwortet
2. **Game-Plugin muss `GameNexusName` oder `GameShortName` liefern** — sonst kein gültiger API-Endpunkt
3. **`write_meta_ini()` existiert und funktioniert** — bereits getestet und stabil
4. **`_reload_mod_list()` existiert** — wird an 15+ Stellen genutzt
5. **`QInputDialog` für manuelle ID-Eingabe** — Qt Standard-Widget

## Risiken

| Risiko | Wahrscheinlichkeit | Mitigation |
|--------|-------------------|------------|
| Tag-Kollision mit `mod_info:` | Hoch (wenn nicht beachtet) | Separater Tag-Prefix `query_mod_info:` |
| Row-Verschiebung zwischen Request/Response | Mittel | `install_path` statt Row-Index speichern |
| Rate-Limit bei vielen Queries | Mittel | Kein Batch, einzeln, Statusbar-Warnung |
| Kein API-Key gesetzt | Mittel | Menüeintrag disabled wenn kein Key |
| Mod gelöscht zwischen Request/Response | Niedrig | Path-Existenz prüfen vor Write |
| Nexus-ID existiert nicht auf Nexus | Niedrig | Error-Handler zeigt Statusbar-Meldung |
| Zwei parallele Queries gleichzeitig | Niedrig | Nur eine Query gleichzeitig erlauben |

---

## ✅ Akzeptanz-Kriterien (ALLE müssen erfüllt sein)

- [ ] 1. Wenn User Rechtsklick auf eine Mod mit nexus_id > 0 macht, erscheint "Nexus-Info abrufen" im Kontextmenü und ist klickbar
- [ ] 2. Wenn User Rechtsklick auf eine Mod mit nexus_id = 0 macht, erscheint "Nexus-Info abrufen" im Kontextmenü und ist klickbar
- [ ] 3. Wenn User "Nexus-Info abrufen" bei Mod mit nexus_id > 0 klickt, wird die Nexus API mit Tag-Prefix `query_mod_info:` aufgerufen (NICHT `mod_info:`) und Statusbar zeigt "Lade Nexus-Info..."
- [ ] 4. Wenn User "Nexus-Info abrufen" bei Mod mit nexus_id = 0 klickt, öffnet sich ein Eingabe-Dialog mit Titel "Nexus Mod-ID eingeben"
- [ ] 5. Wenn User im ID-Dialog eine gültige Zahl eingibt (z.B. "107658") und OK klickt, wird die Nexus API mit dieser ID aufgerufen
- [ ] 6. Wenn User im ID-Dialog ungültigen Wert eingibt (leer, Buchstaben, 0, negativ), wird KEIN API-Call ausgelöst und Statusbar zeigt "Ungültige Mod-ID"
- [ ] 7. Wenn die Nexus API erfolgreich antwortet, wird meta.ini mit modid, version, newestVersion, name, author, description und url aktualisiert (via write_meta_ini)
- [ ] 8. Wenn die Nexus API erfolgreich antwortet, wird die Mod-Liste neu geladen und Statusbar zeigt "Nexus-Info aktualisiert: {name}"
- [ ] 9. Wenn User nach erfolgreichem Query Rechtsklick auf dieselbe Mod macht, ist "Nexus-Seite öffnen" jetzt aktiviert (nicht mehr ausgegraut)
- [ ] 10. Wenn kein Nexus API-Key gesetzt ist, ist "Nexus-Info abrufen" im Kontextmenü ausgegraut
- [ ] 11. Wenn die Nexus API Fehler zurückgibt (404, 429, Timeout), wird Statusbar-Fehler angezeigt und meta.ini NICHT verändert
- [ ] 12. Wenn User den GamePanel-Button "Nexus-Info abrufen" klickt und genau eine Mod selektiert ist, wird der Query für diese Mod gestartet
- [ ] 13. Wenn User den GamePanel-Button klickt und KEINE Mod selektiert ist, erscheint eine Statusbar-Meldung
- [ ] 14. Wenn User während eines laufenden Query die Mod-Liste umsortiert, wird trotzdem die richtige meta.ini aktualisiert (install_path statt Row-Index)
- [ ] 15. Wenn ein NXM-Download läuft und User gleichzeitig "Nexus-Info abrufen" nutzt, stören sich die Flows NICHT (getrennte Tag-Prefixes)
- [ ] 16. Alle 6 neuen i18n-Keys existieren in allen 6 Locale-Dateien (de, en, es, fr, it, pt)
- [ ] 17. restart.sh startet ohne Fehler
