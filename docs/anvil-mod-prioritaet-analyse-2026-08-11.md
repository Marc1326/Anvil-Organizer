# Anvil: Analyse Mod-Reihenfolge & Priorität

**Datum:** 2026-08-11
**Status:** Nur Untersuchung – es wurde **kein Code geändert**.

---

## 1. Kernanforderung (wichtigste Regel)

> **Der Benutzer legt die Mod-Reihenfolge selbst fest. Anvil muss exakt diese
> Reihenfolge speichern und beim Deployment umsetzen.**

Für Anvils Mod-Liste soll systemweit gelten:

- **Oberste Mod = höchste Dateipriorität = gewinnt jeden Dateikonflikt.**
- Die vom Benutzer angelegte Reihenfolge bleibt nach Neustart und Profilwechsel erhalten.
- Anvil darf sie nicht unbemerkt umdrehen oder automatisch verändern.
- Automatische Bethesda-Sortierung betrifft nur `.esm/.esp/.esl` und darf die
  Mod-Dateireihenfolge nicht ersetzen.
- Konfliktanzeige und reales Spielergebnis müssen genau dieselbe Gewinner-Mod zeigen.

Beispiel:

```text
Mod A   ← höchste Priorität
Mod B
Mod C   ← niedrigste Priorität
```

Wenn alle drei dieselbe Datei oder dieselbe interne Ressource verändern, muss
**Mod A** im Spiel wirksam sein – unabhängig davon, ob Anvil Mods als lose
Dateien verlinkt, kopiert, in BA2-Archive packt, über REDmod verarbeitet, als
BG3-PAKs registriert, als Unreal-PAKs bereitstellt oder in Forge-Archive einbaut.

---

## 2. Vorbild MO2

MO2 trennt zwei Reihenfolgen – genau dieses Verhalten braucht Anvil ebenfalls:

- **Linke Seite: Mod-Priorität** – bestimmt, welche Mod-Dateien gewinnen
  (Texturen, Meshes, Skripte, Konfigurationen, Archive).
- **Rechte Seite: Plugin-Ladereihenfolge** – bestimmt die Reihenfolge von
  `.esm/.esp/.esl` unter Beachtung von Master-Abhängigkeiten.

Beide Reihenfolgen sind getrennt, aber beide werden zuverlässig umgesetzt.
Keine der beiden Listen darf nur eine optische Sortierung sein.

---

## 3. Was bereits richtig funktioniert

### 3.1 Normale lose Dateien / Symlinks

- `modlist.txt` speichert die Reihenfolge unverändert (erste Mod = höchste Priorität).
- Der normale Deployer (`anvil/core/mod_deployer.py`) dreht die Liste intern um:
  niedrigste Mod zuerst, oberste Mod zuletzt → **die oberste Mod gewinnt den Dateikonflikt**.
- Ausgeführter Praxistest mit zwei Mods und identischer Zieldatei bestätigte:
  GUI `TOP` über `BOTTOM` → tatsächlich ausgerollte Datei stammt von `TOP`.

### 3.2 Manuelles Verschieben normaler Mods

Drag-and-drop-Kette funktioniert:

1. Qt-Modell verschiebt die Zeile (`anvil/models/mod_list_model.py`).
2. Signal `mods_reordered` wird ausgelöst.
3. `MainWindow._on_mods_reordered()` übernimmt die sichtbare Reihenfolge.
4. Reihenfolge wird in `.profiles/modlist.txt` gespeichert.
5. Redeploy wird eingeplant.

Auch deaktivierte Mods behalten ihre Position. Aktivierung und Priorität sind
korrekt getrennt: `modlist.txt` = Reihenfolge, `active_mods.json` = Aktivierung pro Profil.

### 3.3 Ghost Recon Breakpoint

`anvil/core/grb_deployer.py` verarbeitet die aktive Liste umgedreht
(`reversed(active_mods)`) → bei gleicher Forge-Ressourcen-ID gewinnt die oberste Mod. **Korrekt.**

### 3.4 Eingebaute Bethesda-Plugin-Sortierung

Für **Skyrim SE und Fallout 4** besitzt Anvil eine eigene native Pluginverwaltung:

- eigener Plugin-Tab, manuelles Verschieben möglich,
- TES4-Header werden nativ gelesen, `MAST`-Abhängigkeiten berücksichtigt,
- offizielle Hauptplugins und Creation-Club-Inhalte bleiben in zulässiger Reihenfolge,
- fehlende Master und Zyklen werden erkannt,
- automatische Sortierung (optional beim Deployment),
- Schreiben der Profil- und spielrelevanten `plugins.txt`.

Die (manuell oder automatisch) erzeugte Plugin-Reihenfolge wird **wirklich
umgesetzt** – sie ist nicht nur optisch.

Relevant: `anvil/core/plugin_sorter.py`, `anvil/core/plugins_txt.py`,
`anvil/widgets/game_panel.py`, `tests/test_plugin_load_order.py`.

Hinweis: **Starfield** hat `plugins.txt`-Unterstützung, aber
`SupportsNativePluginSorting = False`.

**Grenze:** Diese App sortiert **Plugins**, nicht die Dateien der Mods in der
linken Mod-Liste. Sie ersetzt nicht die Mod-Dateipriorität.

---

## 4. Bestätigte Probleme

### 4.1 Konfliktanzeige ist umgekehrt (bestätigter Fehler)

- `ConflictScanner` (`anvil/core/conflict_scanner.py`) erwartet
  „niedrigste Priorität zuerst“ und bestimmt den Gewinner mit `owners[-1]`.
- `MainWindow._run_conflict_scan()` übergibt aber die GUI-Reihenfolge
  („höchste Priorität zuerst“) unverändert.
- Ergebnis: Reales Deployment → `TOP` gewinnt; Scanner meldet → `BOTTOM` gewinnt.

Betroffene Anzeigen:

- Konfliktsymbole in der Mod-Liste,
- „Überschreibt / Wird überschrieben“,
- Konfliktdetails, Diagnose-Tab,
- virtuelle Dateiansicht im Data-Tab,
- BG3-Konfliktanzeige.

### 4.2 BG3: eigener Weg über `modsettings.lsx`, aber „oben gewinnt“ nicht abgesichert

BG3 hat einen eigenen Mechanismus: `modsettings.lsx → ModOrder`
(`GustavDev` bleibt als Basismodul vorne).

- Anvil schreibt die aktive Reihenfolge **1:1** in `bg3_modstate.json` und
  `modsettings.lsx` (getestet: GUI `BOTTOM, TOP` → `ModOrder: Gustav, BOTTOM, TOP`).
- Es gibt **keine Umrechnung** auf „oberste Mod gewinnt“ – keine Umkehrung wie
  beim normalen Deployer.
- Anvils eigener ConflictScanner behandelt die letzte Mod als Gewinner → nach
  dieser Semantik würde `BOTTOM` gewinnen, nicht `TOP`.
- Für die endgültige Engine-Bestätigung wäre ein echter In-Game-Test mit zwei
  kollidierenden BG3-PAKs nötig. Bereits jetzt ist klar: Es fehlt ein
  eindeutiger Adapter „Anvil oben gewinnt“ → BG3-`ModOrder`.

**Inaktive BG3-Mods:**

- Beim Reorder werden nur aktive UUIDs an `reorder_mods()` übergeben.
- Inaktive Mods lassen sich optisch verschieben, ihre Position wird aber nicht
  dauerhaft gespeichert → nach Reload erscheinen sie wieder an alter Position.
- Damit ist „alle Mods von Hand verschiebbar und genau so bleiben sie“ für BG3
  **nicht erfüllt**.

**BG3 Data Overrides:**

- Gehören nicht zu `ModOrder`; ihre sichtbare Position steuert weder
  Installations- noch Überschreibungsreihenfolge.

### 4.3 Bethesda-BA2: Prioritätsrichtung nicht bewiesen

- Skyrim SE / Fallout 4 packen lose Dateien pro Mod in eigene Archive
  (`anvil/core/ba2_packer.py`) und hängen sie in Modlisten-Reihenfolge an
  `sResourceArchiveList2` in der jeweiligen Custom-INI.
- Die Anvil-Reihenfolge wird weitergegeben, aber es fehlt ein getesteter Vertrag:
  „oberste Mod = gewinnendes BA2/BSA im Spiel“.
- Keine erkennbare explizite Übersetzung (Umkehrung o. ä.) wie beim Symlink-Deployer.
- **Offen und sicherheitsrelevant** – muss anhand der realen Bethesda-Archiv-
  Mount-Semantik geprüft und per Regressionstest festgeschrieben werden.

### 4.4 Cyberpunk 2077 / REDmod

- Identische lose Zielpfade: normaler Deployer → oberste Mod gewinnt. **Abgesichert.**
- REDmod-Mods werden als eigene Verzeichnisse nach `game_root/mods/` ausgerollt;
  danach entscheidet `redMod.exe` über interne Ressourcenkonflikte.
- Anvil übergibt derzeit keine eigene REDmod-Prioritätsdatei → interne
  REDmod-Konflikte sind **nicht durch die linke Liste garantiert**.

### 4.5 Unreal-PAK-Spiele

- Optionale Präfix-Nummerierung (`GamePakLoadOrderPrefix`, z. B. `000_Mod.pak`)
  existiert, ist aber standardmäßig deaktiviert (u. a. Stellar Blade, Stalker 2,
  weil Loader Originaldateinamen erwarten).
- Gleicher Ziel-Dateiname → normaler Deployer löst den Konflikt korrekt.
- Verschiedene PAK-Namen mit intern kollidierenden Ressourcen → Engine/Mount-
  Reihenfolge entscheidet, nicht die Anvil-Liste. **Keine systemweite Garantie.**

---

## 5. Warum das gefährlich ist

Eine falsche Reihenfolge kann verursachen:

- Kompatibilitätspatches werden von der ursprünglichen Mod überschrieben,
- ältere Dateien gewinnen gegen neuere Versionen,
- Texturen/Meshes/Skripte aus unterschiedlichen Mod-Versionen kombiniert,
- Framework-Dateien (ArchiveXL, TweakXL, RED4ext, CET) werden durch Add-ons ersetzt,
- Plugin-Master in falscher Reihenfolge,
- falsche Gewinner-Anzeige in der GUI,
- im Extremfall: kaputte Spielstände, fehlende Objekte, schwer reproduzierbare Abstürze.

Die Reihenfolge muss deshalb **deterministisch** sein.

---

## 6. Teststand

- **107 relevante vorhandene Tests ausgeführt – alle bestanden**
  (u. a. `test_pak_load_order.py`, `test_deploy_on_launch.py`, `test_grb_deployer.py`,
  `test_deploy_routes.py`, `test_custom_deployer_paths.py`, `test_plugin_load_order.py`).
- Zusätzlich eigene temporäre Read-only-Prüfungen: Qt-DnD + Signal,
  `modlist.txt`-Persistierung, realer Zwei-Mod-Dateikonflikt, Scanner-Gewinner,
  BG3-State- und `modsettings.lsx`-Reihenfolge.
- Grüne Tests beweisen hier nicht die Anforderung: Es fehlen systemweite
  Vertragstests „oben steht → gewinnt in Anzeige, Deployment und Spiel-Backend“.

---

## 7. Betroffene Dateien (bei späterer Korrektur)

**Zentrale Prioritätslogik:**

- `anvil/core/mod_list_io.py`
- `anvil/core/mod_deployer.py`
- `anvil/core/conflict_scanner.py`
- `anvil/models/mod_list_model.py`
- `anvil/mainwindow.py`

**BG3:**

- `anvil/core/bg3_mod_installer.py`
- `anvil/plugins/games/bg3_mod_handler.py`
- BG3-Zustands-/Load-order-Tests (derzeit kein dedizierter Test vorhanden)

**Bethesda:**

- `anvil/core/plugin_sorter.py`
- `anvil/core/plugins_txt.py`
- `anvil/core/ba2_packer.py`
- `anvil/widgets/game_panel.py`
- Tests für BA2/BSA-Archivpriorität

**Weitere Deployment-Modelle:**

- REDmod-Deployment
- Unreal-PAK-Mount-Reihenfolge
- GRB (als bereits korrektes Referenzbeispiel)

---

## 8. Lösungsvorschlag

Verbindlicher interner Vertrag:

> **Jede Anvil-Mod-Reihenfolge wird intern und auf Platte als
> „höchste Priorität zuerst“ gespeichert.**

Jeder Verbraucher übersetzt ausdrücklich:

| Bereich | Benötigtes Verhalten |
|---|---|
| GUI | unverändert |
| `modlist.txt` | unverändert |
| normale Symlink-Ausrollung | umdrehen |
| ConflictScanner | umdrehen oder auf „erster gewinnt“ umstellen |
| GRB | weiterhin passend umdrehen (bereits korrekt) |
| BG3 `ModOrder` | nach bestätigter Engine-Semantik übersetzen |
| Bethesda-Archive | nach bestätigter Mount-Semantik übersetzen |
| Plugin-Sortierung | eigenes Bethesda-System beibehalten |
| REDmod | explizite Prioritätsstrategie entwickeln |
| Unreal-PAKs | spielabhängiger Adapter |

**Akzeptanztests:** Zwei Mods `TOP`/`BOTTOM` mit identischer Ressource:

1. `TOP` oben → bleibt nach Neustart erhalten,
2. Konfliktanzeige nennt `TOP` als Gewinner,
3. Deployment verwendet `TOP`,
4. Spiel-Backend verwendet `TOP`,
5. nach Verschieben von `BOTTOM` nach oben gewinnt `BOTTOM`,
6. deaktivierte Mods behalten ihre Position,
7. Profilwechsel stellt die Reihenfolge wieder her,
8. Speicherfehler verändert nicht nur die GUI,
9. vor Spielstart wird der gespeicherte Stand ausgerollt.

Bethesda zusätzlich getrennt: Dateikonflikt (Mod-Liste), BA2/BSA-Konflikt,
Plugin-Record-Konflikt, Master-Abhängigkeit, manuelle + automatische Plugin-Reihenfolge.

---

## 9. Kommunikation an bestehende Nutzer beim Update

Wenn die Prioritätslogik korrigiert wird, kann sich für bestehende
Installationen die tatsächlich geladene Reihenfolge ändern. Vorschlag:

1. **Einmal-Warndialog beim ersten Start nach Update** (nicht still überspringbar):
   „Mod-Prioritäten wurden korrigiert: Oberste Mod = höchste Priorität = gewinnt
   Konflikte. Deine Reihenfolge wurde übernommen, aber geladene Dateien können
   sich geändert haben. Bitte Reihenfolge prüfen und neu ausrollen.“
   Checkbox „Nicht mehr anzeigen“, Versionsvermerk.
2. **Automatisches Backup vor der Umstellung**:
   `.profiles/backup-vor-prioritaetsfix/` mit `modlist.txt`, `active_mods.json`,
   `plugins.txt`, `modsettings.lsx` (BG3). Im Dialog auf den Pfad hinweisen.
3. **Button „Jetzt Konflikte prüfen“** im Anschluss – startet den korrigierten
   ConflictScanner, damit der User die tatsächlichen Gewinner sieht.
4. **Changelog / Release Notes** als ⚠ Breaking Change markieren.
5. **Keine stille Migration:** Gespeicherte Reihenfolgen werden nicht heimlich
   umgedreht – nur die Interpretation wird korrigiert. Der User behält die Kontrolle.

---

## 10. Abschließendes Ergebnis

Anvil hat eine gute Grundlage:

- Mod-Reihenfolge wird gespeichert und manuell verschoben (normale Mods).
- Normale Symlink-Ausrollung setzt „oben gewinnt“ korrekt um.
- GRB setzt es korrekt um.
- Native Bethesda-Plugin-Sortierung wird tatsächlich angewendet.

Aber das Verhalten ist **nicht systemweit einheitlich**:

| Bereich | Status |
|---|---|
| Normale lose Dateien | ✅ richtig |
| GRB | ✅ richtig |
| Konfliktanzeige | ❌ bestätigt falsch herum |
| BG3 aktive Reihenfolge | ⚠ wird gespeichert, Prioritätsrichtung nicht abgesichert |
| BG3 inaktive Mods | ❌ Verschiebung nicht dauerhaft |
| BG3 Data Overrides | ❌ Listenposition steuert Deployment nicht |
| Bethesda BA2/BSA | ⚠ Richtung nicht bewiesen |
| REDmod interne Konflikte | ⚠ nicht durch linke Liste garantiert |
| Unreal-PAKs | ⚠ GUI-Reihenfolge kann wirkungslos sein |

Zielarchitektur (wie MO2):

> **Linke Mod-Liste kontrolliert zuverlässig alle Dateikonflikte.
> Eingebaute Plugin-Liste kontrolliert zuverlässig die Plugin-/Record-Reihenfolge.
> Der Benutzer legt beide Reihenfolgen selbst fest – Anvil setzt sie exakt um.**
