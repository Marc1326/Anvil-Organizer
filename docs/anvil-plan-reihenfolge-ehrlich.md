# Wenn die Reihenfolge nicht ankommt — Vorschlag

Stand: 13.08.2026
Anlass: Marcs Frage, ob eine Mod, die in Anvil oben steht, auch im Spiel
zuerst greift.

---

## Das Problem in einem Satz

Anwender gehen davon aus: **was in Anvil oben steht, gewinnt im Spiel.**
Das stimmt aber nur bei manchen Spielen — und Anvil sagt nirgends, wann
nicht.

Marcs Beispiel: Ein Modder schreibt „muss an erster Stelle stehen", weil
die Mod das Gameplay oder die Spielwelt verändert. Eine Body-Mod heißt
zufällig so, dass sie alphabetisch vorne landet. Dann gewinnt die
Body-Mod, und die Gameplay-Mod wirkt gar nicht oder nur halb — obwohl
sie in Anvil ganz oben steht.

---

## Was tatsächlich passiert (gemessen, nicht vermutet)

### Die Grundregel

Oben in der Liste = höchste Priorität. Der Deployer dreht die Liste
intern um (`anvil/core/mod_deployer.py:490`, `enabled_mods.reverse()`)
und arbeitet von der schwächsten zur stärksten Mod. Die letzte
überschreibt.

**Für lose Dateien gilt das bei jedem Spiel.** Bei gepackten Archiven
hängt es davon ab, ob Anvil sie durchnummeriert.

### Wer nummeriert, wer nicht

Geprüft über `GamePakLoadOrderDirs` in allen Spiel-Plugins:

| Spiel | Archive nummeriert | Reihenfolge kommt an |
|---|---|---|
| **Cyberpunk 2077** | ja, `archive/pc/mod` | **vollständig** |
| **Stalker 2** | ja, nur `Stalker2/Content/Paks/~mods` | dort ja, in `LogicMods` nein |
| Skyrim SE | nein | nur lose Dateien |
| Fallout 4 | nein | nur lose Dateien |
| Starfield | nein | nur lose Dateien |
| Witcher 3 | nein | nur lose Dateien |
| Stellar Blade | nein | nur lose Dateien |
| Baldur's Gate 3 | nein | nur lose Dateien |
| RDR 2 | nein | nur lose Dateien |
| Ghost Recon Breakpoint | nein | nur lose Dateien |

### Cyberpunk 2077 — hier ist es gelöst

```python
GamePakLoadOrderDirs = ["archive/pc/mod"]
GamePakLoadOrderFirstWins = True
```

REDengine liest `modlist.txt` **nicht**. Es entscheidet der Dateiname,
und die alphabetisch **erste** Datei gewinnt. Deshalb nummeriert Anvil
beim Ausrollen durch — und weil hier die erste gewinnt, bekommt die
oberste Mod die kleinste Zahl.

Am 13.08. am laufenden Spiel belegt:

```
001_00_FacePreset_RE9Grace_xBaebsae.archive          ← Platz 1 in Anvil
002_###-PreemFixes-Cloth.archive
009_00_Halvkyrie_UniqueEyes_Core_Default_V2.5.archive
```

365 Archive nummeriert, **keine einzige `.archive` ohne Nummer**, die
161 `.xl` unangetastet. Der ursprüngliche Name (`00_`, `###-`) steht
hinter der Nummer und entscheidet nichts mehr. Ein Modder kann seine
Datei `000_AAA_ZUERST.archive` nennen — Anvil setzt seine eigene Zahl
davor.

**Bei Cyberpunk stimmt Marcs Denkmodell also: oben = kommt zuerst an.**

### Bethesda — zwei getrennte Reihenfolgen

Das wird leicht verwechselt:

| Was | Woher | Folgt der Mod-Liste? |
|---|---|---|
| Lose Dateien (Texturen, Meshes, Skripte) | Deployer, letzte gewinnt | **ja** |
| Plugins (`.esp`/`.esm`/`.esl`) | `plugins.txt` im Proton-Prefix | **nein** |

Die `plugins.txt` schreibt `PluginsTxtWriter` aus **ihrer eigenen
Liste** — dem Plugins-Tab. Eine Mod in der Mod-Liste zu verschieben
ändert **nicht**, welcher `.esp` bei Datensatz-Konflikten gewinnt.

`.bsa`/`.ba2` werden über die zugehörige `.esp` geladen, nicht über den
Dateinamen — deshalb wird dort auch nichts nummeriert.

---

## Zwei Lücken

**1. Es gibt keine Ausnahme pro Mod.**
Gesucht nach `no_rename`, `skip_rename`, `keep_name` — nichts vorhanden.
Hängt eine Cyberpunk-Mod ihren Loader am exakten Dateinamen, wird sie
trotzdem umbenannt und findet sich nicht mehr. Dagegen kann der Anwender
heute nichts tun. **Das ist eine Lücke im laufenden Betrieb, nicht erst
bei künftigen Spielen.**

**2. Anvil sagt nie, wenn die Reihenfolge nicht ankommt.**
Bei Stellar Blade sieht die Prioritäts-Spalte genauso aus wie bei
Cyberpunk — nur dass sie dort für Archive nichts bewirkt. Kein Hinweis,
kein Tooltip, nichts.

---

## Drei Wege, aufsteigend nach Risiko

### 1. Ehrlich sein — kein Risiko, größter Nutzen

Anvil weiß pro Spiel, ob nummeriert wird. Wo nicht, soll die Liste das
**sagen** statt so zu tun. Zum Beispiel als Tooltip auf der Spalte
„Priorität" oder als Zeile unter der Liste:

> Bei diesem Spiel entscheidet die Reihenfolge nur über lose Dateien.
> Gepackte Archive lädt das Spiel nach eigenem Verfahren.

Bei Spielen mit begrenzter Freigabe (Stalker 2) zusätzlich, **welche**
Ordner betroffen sind.

Das löst das eigentliche Problem: **die falsche Erwartung.** Niemand
rätselt mehr, warum eine Mod trotz Platz 1 nicht wirkt.

**Aufwand:** klein. Reine Anzeige, kein Eingriff in den Deploy-Weg.

### 2. Ausnahme pro Mod — kleines Risiko, aber nötig

Kontextmenü → **„Dateinamen nicht ändern"**. Anvil überspringt die Mod
bei der Nummerierung und zeigt das in der Liste an — damit ist auch
klar, dass ihre Position für diese Mod nicht greift.

Ohne das ist die Nummerierung ein Alles-oder-nichts. Zickt eine Mod,
bleibt nur, sie ganz abzuschalten.

**Aufwand:** klein bis mittel. Ein Merker in der `meta.ini`, eine Abfrage
in `pak_order_allows()`, ein Menüeintrag, eine Anzeige.

### 3. Nummerierung für weitere Spiele — höchstes Risiko

Technisch ein Dreizeiler pro Spiel. Aber im Code steht ausdrücklich
(`anvil/plugins/base_game.py:145-149`):

> Achtung: viele Mod-Autoren verbieten das Umbenennen ausdrücklich —
> Loader suchen ihre Dateien am Namen. Nur einschalten, wenn geprüft.

Deshalb hat Stalker 2 nur `~mods` freigegeben und **nicht** `LogicMods`
oder `Binaries/Win64`.

Das muss **pro Spiel und pro Ordner** an einem echten Spielstart geprüft
werden, nicht am Schreibtisch. Für Spiele, die nicht installiert sind,
geht es gar nicht.

---

## Empfehlung

**Punkt 1 und 2 bauen. Punkt 3 nur für Spiele, die Marc wirklich starten
kann — mit seinem Spieldurchlauf als Beweis, so wie am 12./13.08. bei
Cyberpunk.**

Begründung:

- Punkt 1 macht Anvil **ehrlich**. Das ist der Kern von Marcs Frage.
- Punkt 2 gibt ein Werkzeug in die Hand, wenn eine Mod zickt — und
  schließt eine Lücke, die heute schon offen ist.
- Beide fassen den Deploy-Weg nur an einer Stelle an
  (`pak_order_allows`) und ändern für bestehende Instanzen nichts.
- Punkt 3 ohne Spieltest wäre geraten. Genau davor warnt der Code.

---

## Was ausdrücklich NICHT gemacht werden soll

- Nummerierung pauschal für alle Spiele einschalten.
- Ordner wie `LogicMods`, `CNS` oder `Binaries/Win64` freigeben.
- Die `.xl`-Dateien mitbenennen. Gemessen am 12.08.: nur 47 von 85 `.xl`
  heißen wie ihr Archiv, 38 nicht — und die funktionieren. ArchiveXL
  verlangt keine Namensgleichheit.
- Die Bethesda-Plugin-Reihenfolge an die Mod-Liste koppeln. Das sind
  bewusst zwei verschiedene Dinge.

---

## Offene Fragen an Marc

1. Punkt 1 und 2 bauen — ja?
2. Reihenfolge: erst diese beiden, oder erst OverlayFS Stufe 1?
3. Falls Punkt 3 für ein Spiel: welches, und kannst du es starten?

### Aus dem OverlayFS-Plan, noch offen

4. **Startoption:** Wrapper und `WINEDLLOVERRIDES` müssen in eine Zeile.
   Vorschlag: die Variablen in den Wrapper schreiben, dann bleibt die
   Startoption einzeilig. Betrifft Marcs Steam-Konfiguration — dort ist
   am 04.08. schon einmal die Startoption verlorengegangen.
5. **GOG/Epic/Zweitbinaries/xEdit/redMod:** Der Overlay hängt an der
   Steam-Startoption und greift dort nicht. Weg A (Anvil startet Proton
   selbst, kostet Steam-Overlay, Spielzeit und Controller-Profile) oder
   Weg B (Oberfläche sagt ehrlich, dass es dort nicht greift)?
   Empfehlung: **B**.
