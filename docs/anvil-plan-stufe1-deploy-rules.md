# Stufe 1: `deploy_rules.py` auf main bringen

Analyse zum Umbau, der die Pfadregeln aus `anvil/core/mod_deployer.py` in ein
neues Modul `anvil/core/deploy_rules.py` zieht. Vorlage ist der Branch
`feat/overlay-deploy` (Worktree `/home/mob/Projekte/anvil-overlay`). Der
Overlay-Deploy selbst ist **nicht** Teil dieser Stufe.

Festgehaltene Fakten vorweg:

- Merge-Base Branch/main: `e82a5c38`. Seitdem 37 Commits auf main
  (`git rev-list --count e82a5c38..main`), Spitze `d0b8a4e`.
- `git diff --stat e82a5c38..main -- anvil/core/mod_deployer.py`:
  634 Einfügungen, 21 Löschungen. Die Datei wuchs von 830 Zeilen
  (Merge-Base) auf 1443 Zeilen (main).
- Der Branch ändert an `mod_deployer.py` nur 88 Zeilen
  (`git diff --stat e82a5c38 feat/overlay-deploy`).
- Baseline heute verifiziert: `pytest tests -q` → **783 passed, 1 skipped**
  in 15,9 s. (Nur `tests/` aufrufen — ein nacktes `pytest` bricht an der
  Sammlung von `_dev/tests/test_instance.py` mit "modlist.txt missing".)

---

## 1. Was genau zieht der Branch heraus?

Quelle: `git show feat/overlay-deploy:anvil/core/deploy_rules.py` (127 Zeilen,
unverändert gegenüber dem Worktree-Stand). Zeilenangaben links beziehen sich
auf diese Datei, die Herkunftsspalte auf den Merge-Base-Stand
`git show e82a5c38:anvil/core/mod_deployer.py`.

### Konstanten

| Zeile | Name | Inhalt | Herkunft (Merge-Base) |
|---|---|---|---|
| 20 | `SKIP_FILES` | `{"meta.ini", "codes.txt", "fomod_choices.json"}` | `_SKIP_FILES`, Zeile 39 — identisch |
| 23 | `SKIP_DIRS` | `{"fomod"}` | `_SKIP_DIRS`, Zeile 42 — identisch |
| 27–31 | `SKIP_ROOT_EXTENSIONS` | Bilder/Doku/Thumbs-Endungen | `_SKIP_ROOT_EXTENSIONS`, Zeilen 46–50 — identisch |
| 34–39 | `ARCHIVE_KEEP_EXTENSIONS` | Plugins, Binaries, Configs, fertige Archive | `_BA2_SYMLINK_EXTENSIONS`, Zeilen 53–58 — identischer Inhalt, **umbenannt** |

### Funktionen

| Zeile | Signatur | Zweck | Herkunft |
|---|---|---|---|
| 42–50 | `is_metadata(src, mod_dir, rel) -> bool` | Fasst die drei Skip-Prüfungen zusammen | **Neu.** Entspricht den Inline-Prüfungen Merge-Base Zeilen 402–416 |
| 53–57 | `strip_root(rel) -> Path` | Entfernt führendes `root/` (RootBuilder-Muster) | Inline-Block Zeilen 425–426 — wörtlich |
| 60–74 | `goes_into_archive(rel, suffix, *, loose_paths, data_path) -> bool` | True, wenn der Archiv-Packer die Datei übernimmt; arbeitet auf dem Pfad **ohne** Data-Präfix | Inline-Block Zeilen 430–438 |
| 77–107 | `apply_data_path(rel, mod_name, *, data_path, is_direct, nest_under_mod_name, multi_folder_routes) -> Path` | Data-Präfix voranstellen, Ordner-Umleitungen, Nesting | Inline-Block Zeilen 445–465 |
| 110–127 | `target_rel(rel, mod_name, ...) -> Path` | `strip_root` + `apply_data_path` in einem Aufruf | **Neu** (Bequemlichkeit für Aufrufer ohne Archiv-Packen) |

### Hat der Branch beim Herausziehen etwas verändert?

**Nein — im Symlink-Weg ist die Umstellung rein mechanisch.** Beleg durch
Zeilenvergleich Merge-Base gegen Branch-Funktionen:

- `strip_root` (deploy_rules.py:53–57) ist wörtlich der Inline-Code aus
  Merge-Base Zeile 425–426.
- `goes_into_archive` (deploy_rules.py:60–74) bildet die Bedingung
  `ext not in _BA2_SYMLINK_EXTENSIONS and not stays_loose` (Merge-Base
  Zeile 437) exakt ab: Keep-Endung → `False` (Zeile 72–73), sonst
  `not is_archive_loose_path(...)` (Zeile 74). Der Branch übergibt
  `src_file.suffix` unverändert; die Funktion kleinschreibt selbst
  (Zeile 72) — gleiches Ergebnis wie `src_file.suffix.lower()` im
  alten Code (Merge-Base Zeile 431).
- `apply_data_path` (deploy_rules.py:77–107) gegen Merge-Base Zeilen
  445–465: Reihenfolge identisch — erst Routen (Zeile 96–97 ↔ 450–455),
  dann "bereits präfixiert?" (Zeile 99–103 ↔ 457–461), dann Nesting
  (Zeile 105–107 ↔ 462–465). Der frühe Rücksprung
  `if not data_path or is_direct` (Zeile 91–92) entspricht dem alten
  Wächter `if self._data_path and not is_direct:` (Zeile 445).
- Die drei Skip-Prüfungen zieht der Branch im Deployer **nicht** auf
  `is_metadata` um — sie stehen dort weiter inline (Branch
  `mod_deployer.py:391–404`). `is_metadata` nutzt nur
  `overlay_staging.py:262, 279`.

Zwei **benennende** Änderungen, keine Verhaltensänderungen:

1. `_BA2_SYMLINK_EXTENSIONS` heißt jetzt `ARCHIVE_KEEP_EXTENSIONS` —
   der alte Name bleibt als Import-Alias erhalten
   (Branch `mod_deployer.py:36`).
2. Der Docstring des Moduls (Zeilen 1–11) nennt den Grund für die
   Zweiteilung: die Archiv-Prüfung gehört **zwischen** `strip_root` und
   `apply_data_path`, weil sie auf dem Pfad ohne Data-Präfix arbeitet.
   Im Symlink-Weg war das schon so; die Abweichung gab es nur im
   damals neuen Overlay-Weg.

### Was der Branch sonst noch anfasst — gehört NICHT zu Stufe 1

- `mod_deployer.py`: neue Methode `set_separator_deploy_paths`
  (Branch Zeile 112). Sie wird nur vom Overlay-Code benutzt
  (Branch `widgets/game_panel.py:1108–1119`, `overlay_deployer.py:213`,
  `overlay_staging.py:115`). Auf main existiert sie nicht (Suche nach
  `set_separator_deploy_paths` ohne Treffer). → **Stufe 2.**
- `ba2_packer.py`: `set_output_root()` / `_archive_base` (Branch-Diff,
  +23 Zeilen) — schreibt Archive in die Overlay-Schicht statt in den
  Spielordner. Reine Overlay-Unterstützung. → **Stufe 2.**
- `plugins_txt_writer.py`: `set_extra_scan_roots()`, `_data_dirs()`,
  `_plugin_file()` (Branch-Diff, +74/-22 Zeilen) — Plugin-Scan über
  zusätzliche Wurzeln. Reine Overlay-Unterstützung. → **Stufe 2.**

Fazit Abschnitt 1: Stufe 1 ist genau **eine neue Datei plus der
88-Zeilen-Umbau an `mod_deployer.py`**, ohne `set_separator_deploy_paths`
und ohne die beiden anderen Dateien.

---

## 2. Wer benutzt die Regeln heute? (Stand main)

Dieselbe Logik steht an mehreren Stellen. Trefferliste, jede Zeile
gelesen:

| Regel | Stelle auf main | Bemerkung |
|---|---|---|
| Skip-Dateien (`meta.ini` u.a.) | `anvil/core/mod_deployer.py:41` (`_SKIP_FILES`), angewendet Zeile 698 | Referenzmenge |
| dito | `anvil/core/character_presets.py:133` (`_NEBENSACHE`) | Kommentar Zeilen 129–132 verpflichtet auf Gleichstand mit `mod_deployer._SKIP_FILES`; Test hält beide gleich (siehe unten) |
| dito, Teilmenge | `anvil/core/ba2_packer.py:232` — inline `{"meta.ini", "codes.txt"}` | **ohne** `fomod_choices.json` — bewusst oder Lücke, unbelegt |
| dito, Teilmenge | `anvil/core/conflict_scanner.py:64` — `_INTERNAL_FILES = {"meta.ini"}` | nur `meta.ini`; dazu `_IGNORED_EXTENSIONS = {".txt"}` (Zeile 67) |
| Skip-Verzeichnisse (`fomod`) | `anvil/core/mod_deployer.py:44`, angewendet Zeilen 703–705 | kein zweiter Vorkommnis gefunden |
| Root-Endungen | `anvil/core/mod_deployer.py:48–52`, angewendet Zeile 711 | kein zweiter Vorkommnis gefunden |
| Keep-Endungen beim Packen | `anvil/core/mod_deployer.py:55–60` (`_BA2_SYMLINK_EXTENSIONS`), angewendet Zeile 744 | wertgleiches Duplikat: `anvil/core/ba2_packer.py:39–45` (`_SYMLINK_EXTENSIONS`) |
| `root/` strippen | `anvil/core/mod_deployer.py:731–733` | zweite, eigenständige Implementierung in `anvil/core/archive_packing.py:20` (innerhalb `normalized_mod_content_parts`, Zeilen 14–26, casefold-basiert) |
| Data-Präfix | `anvil/core/mod_deployer.py:761–783` (voranstellen) | Gegenstück in `anvil/core/archive_packing.py:23–25` (Präfix wieder **ab**ziehen, für die Loose-Pfad-Prüfung) |
| Ins-Archiv-Entscheidung | `anvil/core/mod_deployer.py:737–745` | gleiche Logik anders herum in `anvil/core/ba2_packer.py:91–104` (`_classify_file`: loose oder Keep-Endung → `"skip"`) |
| `GameDataPath` lesen | `anvil/core/plugins_txt_writer.py:351, 377, 400, 427` | liest das Data-Verzeichnis, bildet keine Deploy-Pfade — kein Umbau-Kandidat für Stufe 1 |
| `modindex.py` | — | keine Skip-/Präfix-Logik gefunden (Suche nach `meta.ini`, `fomod`, `root`, `data_path` ohne fachlichen Treffer) |

### Der Gleichheitstest für `_NEBENSACHE`

`tests/test_preset_bereich.py:642–647`:

```python
def test_nebensachen_passen_zum_deployer():
    from anvil.core.character_presets import _NEBENSACHE
    from anvil.core.mod_deployer import _SKIP_FILES
    assert _NEBENSACHE == set(_SKIP_FILES), (...)
```

Der Test importiert `_SKIP_FILES` **aus `mod_deployer`**. Nach dem Umbau
muss der Name dort weiter existieren — der Branch löst das über den
Import-Alias `SKIP_FILES as _SKIP_FILES` (Branch `mod_deployer.py:34`).
Wird Stufe 1 genauso gebaut, läuft der Test unverändert weiter. Würde
man den Alias weglassen, schlägt der Test sofort fehl — er ist damit
auch eine Schutzweiche gegen einen unvollständigen Umbau.

---

## 3. Der heutige `mod_deployer.py` — was seit dem Abzweig dazukam

Die drei umbaubetroffenen Inline-Blöcke selbst sind **unverändert**
(identisch zum Merge-Base, Zeilenvergleich siehe Abschnitt 1). Neu ist
alles **darum herum**:

| Zeilen (main) | Teil | Herkunft |
|---|---|---|
| 65–69 | `_PAK_EXTENSIONS`, `_PAK_ORDER_EXTENSIONS` | 63422b5 (Stellar Blade) |
| 72–85 | `strip_deploy_prefixes()` — Mod-Art-Ordner wie `~mods/` abziehen | 67ec2f1 |
| 109–116 | `has_deploy_anchor()` | 67ec2f1 |
| 119–150 | `unreal_mount_point()` | 67ec2f1 |
| 153–198 | `route_deploy_path()` — Zielverteilung nach Dateiart | 67ec2f1 |
| 201–224 | `pak_load_order_name()` — Zähler in den Dateinamen | 8179975 |
| 227–237 | `load_order_index()` — Spiegelung bei "erste Datei gewinnt" | 8179975 |
| 240–254 | `pak_order_allows()` — Umbenennen nur in freigegebenen Ordnern | ba95cf1 |
| 257–273 | `_luecke()`, `_index_rel_paths()` | 07e20c6-Ära (verschwundene Mods melden) |
| 290, 292 | `DeployResult.changed_sources` / `missing_sources` | dito |
| 513 | `zaehler_breite` | 8179975 |
| 680–729 | Cache-Lauf mit `fehlt`-Erkennung und `_luecke`-Aufruf (725) | 07e20c6 |
| 750–759 | **Zielverteilung**: `strip_deploy_prefixes` + `route_deploy_path` zwischen Archiv-Prüfung und Data-Präfix | 67ec2f1 |
| 785–802 | **Durchnummerierung**: `pak_order_allows` + `pak_load_order_name` mit `load_order_index` | 8179975 |
| 816–820 | `written_targets` — eigene Dateien dieses Laufs überschreiben dürfen | 8179975 |
| 969–970 | Aufrufe `_drop_superseded_numbered` + `_write_archive_load_order` | 8179975 / ba95cf1 |
| 1020–1077 | `_drop_superseded_numbered()` — schwächere Dublette wegräumen | 8179975 |
| 1079–ca. 1190 | `_write_archive_load_order()` — Ladeliste fürs Spiel schreiben | ba95cf1 |

### Beißen sich die neuen Teile mit dem Umbau?

Nur an **einer** Stelle, und die ist der entscheidende Punkt des Plans:

- Die Zielverteilung (Zeilen 750–759) steht auf main **zwischen** dem
  Archiv-Block (735–745) und dem Data-Präfix-Block (761–783). Auf dem
  Branch gab es sie noch nicht; `apply_data_path` ersetzt dort den
  Data-Präfix-Block direkt im Anschluss an die Archiv-Prüfung (Branch
  `mod_deployer.py:417–435`).
- Wer den Umbau Zeile für Zeile vom Branch abschreibt, ersetzt also
  einen Block, der auf main gar nicht mehr unmittelbar folgt — und
  riskiert, die Zeilen 750–759 mitzulöschen oder `apply_data_path`
  **vor** die Zielverteilung zu setzen. Beides ändert das Verhalten:
  die Verteilung arbeitet auf dem Pfad **ohne** Data-Präfix
  (`test_deploy_routes.py:26–31` bildet genau diese Reihenfolge nach).
- Die Durchnummerierung (785–802) läuft **nach** dem Data-Präfix auf
  dem fertigen `rel`. Sie bleibt unangetastet — aber sie ist der
  Beleg, dass `deploy_rules.target_rel()` (Branch Zeilen 110–127) den
  heutigen Deploy-Pfad **nicht vollständig** abbildet: Zielverteilung
  und Zähler fehlen darin. Für Stufe 1 egal (der Symlink-Weg ruft
  `target_rel` nicht), für Stufe 2 eine bekannte Lücke.
- Der `fehlt`-Pfad (Zeilen 695, 720–727) benutzt `rel` **vor** dem
  `root/`-Strip für die Meldung. Die Reihenfolge "Meldung vor
  `strip_root`" muss erhalten bleiben.

Keine Beißstelle: `_write_archive_load_order`, `_drop_superseded_numbered`
und `written_targets` arbeiten auf Manifest-Einträgen bzw. fertigen
Zielen — weit hinter dem umgebauten Bereich.

---

## 4. Der konkrete Umbauplan

Grundsatz: jeder Schritt endet mit grüner Suite (`pytest tests -q`,
heute 783 passed / 1 skipped). Die Schritte 0–5 sind einzeln
commitbar.

### Schritt 0 — Schutztests für die ungeschützten Regeln (vor dem Umbau)

Neue Datei, z. B. `tests/test_deploy_regeln.py`. Jeder Test fährt
`ModDeployer.deploy()` über eine Mini-Mod und prüft das Ziel. Fälle
(Begründung in Abschnitt 5):

1. `meta.ini` im Mod-Ordner → landet nicht im Spiel.
2. `fomod/installer.xml` → landet nicht im Spiel.
3. `readme.txt` und `vorschau.png` in der Mod-Wurzel → landen nicht
   im Spiel; `textures/readme.txt` → landet im Spiel.
4. `root/meshes/x.nif` → Symlink auf `<Spiel>/meshes/x.nif`.
5. Mod mit `Data/meshes/x.nif` bei `data_path="Data"` → landet unter
   `Data/meshes/x.nif`, nicht `Data/Data/...`.
6. Optional: Routen wie Witcher 3 (`multi_folder_routes={"mods": "Mods"}`):
   `mods/foo/x.dll` → `Mods/foo/x.dll`.

Diese Tests müssen gegen den **unveränderten** main grün sein — sie
dokumentieren Ist-Verhalten, kein Wunschverhalten.

### Schritt 1 — `anvil/core/deploy_rules.py` anlegen

Den Branch-Stand **wörtlich** übernehmen
(`git show feat/overlay-deploy:anvil/core/deploy_rules.py`, 127 Zeilen).
Keine Anpassung nötig: die drei abgebildeten Inline-Blöcke sind auf main
unverändert (Abschnitt 1 und 3). Suite läuft danach unverändert — die
Datei hat noch keine Aufrufer.

### Schritt 2 — Import und Konstanten in `mod_deployer.py`

- Zeile 34 (`from anvil.core.archive_packing import
  is_archive_loose_path`) entfällt — nach Schritt 4 gibt es keinen
  direkten Aufruf mehr (einzige Stelle heute: Zeile 739).
- Dafür der Branch-Import (Branch `mod_deployer.py:32–39`):

  ```python
  from anvil.core.deploy_rules import (
      SKIP_DIRS as _SKIP_DIRS,
      SKIP_FILES as _SKIP_FILES,
      SKIP_ROOT_EXTENSIONS as _SKIP_ROOT_EXTENSIONS,
      ARCHIVE_KEEP_EXTENSIONS as _BA2_SYMLINK_EXTENSIONS,
      apply_data_path,
      goes_into_archive,
      strip_root,
  )
  ```

- Zeilen 40–60 (die vier Konstanten mit Kommentaren) löschen.
- Die Aliase sind Pflicht: `test_preset_bereich.py:644` importiert
  `_SKIP_FILES` aus `mod_deployer`.

Suite danach grün (die Inline-Blöcke benutzen die Aliase bereits unter
denselben Namen).

### Schritt 3 — `root/`-Strip ersetzen

Zeilen 731–733

```python
                if rel.parts and rel.parts[0].lower() == "root":
                    rel = Path(*rel.parts[1:]) if len(rel.parts) > 1 else rel
```

→ `rel = strip_root(rel)` (mit dem Kommentar aus dem Branch).
**Nicht** die Zeilen 720–727 (`fehlt`-Meldung) mit anfassen — sie stehen
absichtlich davor.

### Schritt 4 — Archiv-Prüfung ersetzen

Zeilen 735–745 →

```python
                if self._needs_ba2_packing and goes_into_archive(
                    rel,
                    src_file.suffix,
                    loose_paths=self._ba2_loose_paths,
                    data_path=self._data_path,
                ):
                    continue
```

(so auf dem Branch, Zeilen 417–423).

### Schritt 5 — Data-Präfix-Block ersetzen

Zeilen 761–783 →

```python
                rel = apply_data_path(
                    rel,
                    mod_name,
                    data_path=self._data_path,
                    is_direct=is_direct,
                    nest_under_mod_name=self._nest_under_mod_name,
                    multi_folder_routes=self._multi_folder_routes,
                )
```

(so auf dem Branch, Zeilen 428–435). **Achtung:** die Zeilen 750–759
(Zielverteilung) und 785–802 (Durchnummerierung) bleiben exakt wo sie
sind — vor bzw. nach diesem Block. Das ist der einzige inhaltliche
Unterschied zum Branch-Diff.

### Was bewusst NICHT getan wird

- `ba2_packer.py` und `plugins_txt_writer.py` bleiben unangetastet. Die
  Branch-Änderungen dort sind Overlay-Infrastruktur (Abschnitt 1),
  keine Regel-Verschiebung. Die wertgleichen Konstanten-Duplikate
  (`ba2_packer.py:39–45`, `:232`) sind Stoff für eine spätere
  Aufräum-Stufe, nicht für Stufe 1 — Minimalprinzip.
- `set_separator_deploy_paths` wird nicht übernommen (Overlay-API).
- Die Inline-Skip-Prüfungen (Zeilen 697–712) bleiben inline wie auf dem
  Branch; ein Umstellen auf `is_metadata` wäre eine Verhaltens- wie
  Umfangs-Ausweitung ohne Nutzen für Stufe 1.
- `strip_deploy_prefixes`, `has_deploy_anchor`, `route_deploy_path`,
  `pak_load_order_name`, `load_order_index`, `pak_order_allows` bleiben
  in `mod_deployer.py` — der Branch zieht sie nicht heraus, also gehören
  sie nicht zu dieser Stufe.

---

## 5. Wie wird bewiesen, dass nichts kaputt ist?

Erfolgskriterium: die vorhandenen Tests bleiben **unverändert** grün
(heute: 783 passed, 1 skipped). Darunter muss jede verschobene Regel
durch mindestens einen Test abgedeckt sein — wo das fehlt, liefert
Schritt 0 den Test vorab.

### Abdeckung und Mutationsproben je Regel

| Regel | Deckender Test | Mutationsprobe | Befund |
|---|---|---|---|
| `SKIP_FILES`-**Menge** | `tests/test_preset_bereich.py:642–647` | Eintrag aus der Menge entfernen → Gleichheitstest rot | **geschützt** (nur die Menge) |
| `SKIP_FILES`-**Anwendung** (Zeile 698) | — | `continue` bei `meta.ini` entfernen → bleibt grün, Datei landet still im Spiel | **ungeschützt** → Schritt 0, Fall 1 |
| `SKIP_DIRS` (Zeilen 703–705) | — | `"fomod"` in `"fomod2"` ändern → kein Test wird rot (Suche nach `fomod` in `tests/` ohne fachlichen Treffer) | **ungeschützt** → Schritt 0, Fall 2 |
| `SKIP_ROOT_EXTENSIONS` (Zeile 711) | — | `".txt"` entfernen → kein Test rot; `tests/test_deploy_routes.py:134` prüft nur `route_deploy_path`, nicht den Skip | **ungeschützt** → Schritt 0, Fall 3 |
| `strip_root` im Deploy (Zeilen 731–733) | — (nur die Schwester-Logik in `archive_packing` ist getestet: `tests/test_bodyslide_deployment.py:109–119`) | Strip löschen → `root/`-Mods landen unter `root/` im Spiel, kein Test rot | **ungeschützt** → Schritt 0, Fall 4 |
| `goes_into_archive`: Keep-Endungen | `tests/test_bodyslide_deployment.py:46–78` (`.esp` bleibt Symlink, `.nif` nicht im Spiel) | Keep-Prüfung entfernen → `plugin.is_symlink()` (Zeile 69) rot | **geschützt** |
| `goes_into_archive`: Loose-Pfade | `tests/test_bodyslide_deployment.py:46–78`, `:109–119` | Loose-Prüfung negieren → Zeilen 60–67 rot | **geschützt** |
| `apply_data_path`: Präfix | `tests/test_bodyslide_deployment.py:60–63, 190`; `tests/test_pak_load_order.py:75–83, 111` | Präfix-Ast entfernen → mehrere Tests rot | **geschützt** |
| `apply_data_path`: "bereits präfixiert" (Zeilen 775–779) | — | `relative_to`-Prüfung entfernen → `Data/Data/...`, kein Test rot | **ungeschützt** → Schritt 0, Fall 5 |
| `apply_data_path`: `multi_folder_routes` (Zeilen 766–773) | — (Witcher 3 hat keinen Routen-Test; Suche nach `witcher` in `tests/` trifft nur `test_character_presets.py`) | Routen-Ast entfernen → kein Test rot | **ungeschützt** → Schritt 0, Fall 6 |
| `apply_data_path`: `nest_under_mod_name` (Zeilen 780–781) | — | Ast entfernen → kein Test rot | **ungeschützt**, produktiv aber **tot**: kein Spiel-Plugin setzt `GameNestModsUnderName = True` (Suche ohne Treffer; `game_witcher3.py:60` setzt explizit `False`; `game_panel.py:3248` liest per `getattr(..., False)`) |
| `is_metadata`, `target_rel` (neu, ungenutzt auf main) | — | entfällt — auf main ohne Aufrufer, erst Stufe 2 nutzt sie (`overlay_staging.py:262, 279, 282, 285` auf dem Branch) | keine Probe nötig |

### Die neuen main-Teile (werden nicht verschoben, müssen aber grün bleiben)

- Durchnummerierung: `tests/test_pak_load_order.py` (9 Tests),
  `tests/test_pak_load_order_dirs.py` (11), `tests/test_archiv_ladereihenfolge.py`,
  `tests/test_cyberpunk_archive_routing.py`, `tests/test_redengine_archive.py`,
  `tests/test_ba2_reihenfolge.py`.
- Zielverteilung: `tests/test_deploy_routes.py` (25),
  `tests/test_cyberpunk_r6_routing.py`, `tests/test_stalker2_routes.py`.
- Archiv-Ladeliste: `tests/test_archive_load_order.py` (11),
  `tests/test_archive_load_order_wiring.py`.

Diese Dateien sind der Nachweis, dass die Nachbarblöcke (750–759,
785–802) beim Umbau unversehrt bleiben.

---

## 6. Risiken

1. **Reihenfolge Zielverteilung ↔ Data-Präfix** (Hauptrisiko). Der
   Branch-Diff kennt die Zeilen 750–759 nicht. Wird `apply_data_path`
   versehentlich vor die Verteilung gesetzt oder diese gelöscht, routen
   Stellar-Blade-/Cyberpunk-Mods falsch — `tests/test_deploy_routes.py`
   bildet die Reihenfolge nur als Einzelfunktionen nach
   (`test_deploy_routes.py:26–31`), ein vollständiger Deploy-Test mit
   `data_path` **und** Routen existiert nicht. Schritt 0, Fall 6,
   schließt genau diese Lücke.
2. **Stille Skip-Regressionen.** Drei der vier Skip-Regeln und
   `strip_root` haben heute keinen End-to-End-Test (Abschnitt 5). Ein
   Tippfehler beim Umbau (falsches Alias, verschluckte Zeile) bliebe
   unsichtbar. Ohne Schritt 0 wäre der Umbau für diese Regeln reine
   Hoffnung.
3. **Duplikate laufen weiter auseinander.** `ba2_packer.py:232` lässt
   `fomod_choices.json` durch, `conflict_scanner.py:64` kennt nur
   `meta.ini`. Stufe 1 ändert daran nichts — gut für den Umfang, aber
   die dritte Kopie der Menge bleibt bestehen und ist weiterhin nicht
   testgesichert.
4. **Für den Nutzer spürbar wäre:** Bilder/Readmes tauchen plötzlich im
   Spielordner auf (Regel 3), FOMOD-Mods tragen ihren Installer-Ordner
   ins Spiel (Regel 2), RootBuilder-Mods landen unter einem falschen
   `root/`-Ordner und wirken nicht mehr (Regel 4), Bethesda-Mods
   verdoppeln ihr `Data/` (Fall 5) oder Witcher-3-Mods liegen flach in
   `Mods/` statt geroutet (Fall 6). Alles still — das Spiel startet,
   die Mod wirkt nur nicht.
5. **`is_metadata` driftet ab Tag eins ab.** Die Funktion fasst die drei
   Skip-Regeln zusammen, der Symlink-Weg benutzt sie aber nicht (Branch
   lässt die Prüfungen inline). Ändert später jemand nur eine Seite,
   merkt es kein Test — der Gleichheitstest deckt nur `_SKIP_FILES`,
   nicht `SKIP_DIRS`/`SKIP_ROOT_EXTENSIONS`. Beim Merge von Stufe 2
   prüfen, ob der Symlink-Weg dann auf `is_metadata` umstellt.
6. **`apply_data_path` ist nicht der ganze Pfad.** Wer in Stufe 2
   `target_rel` als "die" Zielrechnung liest, verliert Zielverteilung
   und Durchnummerierung (Abschnitt 3). In `deploy_rules.py` gehört —
   spätestens mit Stufe 2 — ein Hinweis-Kommentar darüber.

---

## UNSICHER

- **Commit-Zuordnung einzelner neuer Teile:** `route_deploy_path` und
  die Verteilung stammen laut `git log -S` aus 67ec2f1,
  `load_order_index` aus 8179975, `_write_archive_load_order` laut
  `git log -S` aus ba95cf1 ("Absturz beim Start behoben") — ein
  überraschender Commit-Name für diese Funktion; ob sie dort neu
  entstand oder nur umbenannt/verschoben wurde, habe ich nicht
  weiter aufgelöst. Für den Plan ohne Belang.
- **`ba2_packer.py:232` ohne `fomod_choices.json`:** ob bewusst oder
  übersehen, steht nirgends; es gibt keinen Kommentar und keinen Test,
  der den Unterschied festnagelt.
- **`conflict_scanner.py:64` nur `{"meta.ini"}`:** der Kommentar
  ("always internal to Anvil") begründet die kleinere Menge nicht;
  Absicht unbelegt.
- **`nest_under_mod_name` tot?** Kein Plugin setzt
  `GameNestModsUnderName = True` (Suche in `anvil/`, keine Treffer;
  Witcher 3 setzt explizit `False`). Ob ältere Stände oder externe
  Plugins den Ast je benutzten, habe ich nicht geprüft.
- **Worktree-Gleichstand:** `git status` im Worktree
  `/home/mob/Projekte/anvil-overlay` zeigt für `deploy_rules.py` und
  `mod_deployer.py` keine uncommitteten Änderungen; gelesen wurde der
  committed Branch-Stand. Andere Dateien des Worktrees habe ich nur
  per `grep` gesichtet, nicht vollständig.
- **Warum `_dev/tests` die Sammlung bricht:** "modlist.txt missing" bei
  nacktem `pytest`; es gibt offenbar keine `testpaths`-Konfiguration
  (kein Treffer in `pyproject.toml`, keine `pytest.ini`/`setup.cfg`/
  `tox.ini` gefunden). Für den Plan reicht: immer `pytest tests -q`.
- **Ob `strip_root` im echten Betrieb je feuert:** kein Spiel-Plugin
  deklariert ein RootBuilder-Muster sichtbar; die Regel ist generisch.
  Welche Mods/Spiele tatsächlich `root/`-Archive liefern, habe ich
  nicht untersucht.
