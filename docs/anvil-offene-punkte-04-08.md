# Offene Punkte — Stand 04.08.2026

Branch: `fix/modindex-skips-symlinked-mods` (3 Commits gepusht, kein PR/MR angelegt)
Arbeitsverzeichnis sauber bis auf `001Bericht/` (gehört zu Fundus, bewusst nicht committet)
Tests: 218 grün, 1 übersprungen

---

## 1. Vanilla-Backup — NICHT gebaut, größter Punkt

**Was fehlt:** Anvil sichert überschriebene Originaldateien nicht und kann sie beim
Purge nicht zurückspielen.

**Wo:** `anvil/core/mod_deployer.py`, Zeile 474–481

```python
if target.exists() and not target.is_symlink():
    if is_direct:
        pass          # Frameworks dürfen echte Dateien überschreiben
    else:
        result.skipped_real_files.append(str(rel))
        continue
```

Der `pass`-Zweig überschreibt ohne Netz. Nach dem Purge bleibt die
Framework-Fassung liegen, das Original ist weg.

**Auswirkung gemessen:** Beim letzten Deploy wurden 1442 Dateien neu angelegt,
**1 überschrieben** — `options.json` von `v2 UnlockFovImmersiveFirstPersonPatch`.
Deshalb kommt diese Mod nur zur Hälfte an.

**Vorschlag:**
- Vor dem Überschreiben Original nach `.vanilla_backup/<relpath>` in der Instanz kopieren
- Pfad im Manifest vermerken (`backup: true`)
- Purge spielt zurück, bevor er die Datei entfernt
- Der `skipped_real_files`-Zweig kann dann entfallen → auch normale Mods dürfen überschreiben

**Aufwand:** ca. 60–80 Zeilen im Deployer + Tests. Braucht GO.

---

## 2. JB TPP — Original und Fork beide aktiv

Beide Mods liefern identische Dateien, das Original gewinnt (höhere Priorität).
Der Fork (`.mods/JB TPP Fork` → `/home/mob/Projekte/JPP-Anpassung/mod`) ist ein
Symlink auf das pausierte Fork-Projekt.

**Vorschlag:** Fork in der Mod-Liste deaktivieren, solange das Projekt ruht.
Kein Code nötig, nur ein Klick — sag Bescheid ob ich es machen soll.

---

## 3. Data-Reiter — gebaut, nie angeschaut

Der Reiter zeigt jetzt beides: den echten Spielordner und die virtuelle Sicht
("was würde ausgerollt"). Funktioniert laut Tests, du hast es visuell nie geprüft.

**Vorschlag:** Anvil starten, Reiter aufmachen, Screenshot. 2 Minuten.

---

## 4. Issue #20 — Nexus Options, 3 von 5 erledigt

Offen:
- Endorsement-Automatik (Mod nach X Tagen automatisch bewerten)
- Cache leeren (Button in den Nexus-Einstellungen)

**Aufwand:** klein, beides je ~30 Zeilen.

---

## 5. Merge-Request / PR nicht angelegt

Die drei Commits vom 03.08. liegen auf dem Branch, sind gepusht, aber es gibt
keinen PR. Entweder PR anlegen oder direkt nach `main` mergen — deine
Entscheidung.

---

## 6. Review-Agents (Definition of Done)

Die vier Review-Agents aus CLAUDE.md sind für den Deploy-Umbau nicht gelaufen.
Laufen nur auf ausdrückliche Anweisung.

---

## Reihenfolge-Vorschlag

1. Punkt 5 (PR/Merge) — schnell, macht den Tisch sauber
2. Punkt 2 (Fork deaktivieren) — ein Klick
3. Punkt 1 (Vanilla-Backup) — der eigentliche Brocken
4. Punkt 3 (Data-Reiter prüfen) — nebenbei beim Testen
5. Punkt 4 (Issue #20) — wenn Luft ist
