# Problem-Verifikation — "umbenannte Datei wird nicht mehr ausgerollt"

Datum: 2026-08-12
Geprüfter Stand: `git diff HEAD` (nicht committet) — `anvil/core/modindex.py`, `anvil/core/mod_deployer.py`
Rolle: Prüfung des PROBLEMS, nicht des Codes

## Vorbemerkung zu den Pflichtquellen

- Architektur-Doku gelesen: `/home/mob/Projekte/anvil-wiki/dev-notes/ARCHITEKTUR.md` (244 Zeilen).
- MO2-Referenz **nicht verfügbar**: `/home/mob/Projekte/mo2-referenz/` existiert auf diesem Rechner nicht mehr
  (bewusst entfernt, siehe "MO2-Bereinigung"). Ein Zeilenvergleich mit `usvfsconnector.cpp` war deshalb
  nicht möglich. Inhaltlich ist der Punkt hier auch neutral: MO2 hat keinen Datei-Cache dieser Art,
  USVFS liest den Mod-Baum bei jedem Start neu. Der Cache ist eine reine Anvil-Eigenheit — damit ist
  auch der Fehler eine reine Anvil-Eigenheit.
- Die echte Instanz von Marc wurde **nur gelesen**. Alle Schreibvorgänge liefen in einem Wegwerf-Ordner
  unter `/tmp/.../scratchpad/welt/`.

---

## 1. Messung an der echten Installation (nur lesend)

Ordner: `~/.anvil-organizer/instances/Cyberpunk 2077/.mods/FemV - RE9 Grace/`

Auf der Platte liegt: `archive/pc/mod/zz_FacePreset_RE9Grace_xBaebsae.archive`
In `.modindex.json` (version 1) steht: `archive/pc/mod/00_FacePreset_RE9Grace_xBaebsae.archive`

Gegenprobe der Erkennungslogik am echten Ordner:

```
alte Logik (nur Wurzel-mtime): 1786444133.7012582
neue Logik (_fingerprint)    : 1786513424.9531202
im Cache gespeichert         : 1786444133.7012582
alte Logik erkennt Änderung  : False
neue Logik erkennt Änderung  : True
```

Damit ist die Ursache belegt und nicht nur plausibel: die Zeit des Mod-Wurzelordners hat sich beim
Umbenennen in `archive/pc/mod/` nicht verändert. Der Index hielt die Mod für unverändert, auch über
Neustarts hinweg. Der Deployer nahm die alte Dateiliste, fand `00_...` nicht, sprang mit `continue`
weiter — und meldete am Ende `0 errors`.

---

## 2. Frage 1: Würde die Mod jetzt ausgerollt?

**Ja — in beiden Varianten.** Nachgestellt mit einem Wegwerf-Skript
(`/tmp/claude-1000/.../scratchpad/repro.py`, drei Mods, die betroffene an Position 3):

| Fall | Ablauf | Ergebnis |
|------|--------|----------|
| 1 | Umbenennen bei laufendem Anvil, Index im Speicher veraltet | Datei landet im Spiel (`True`), `stale_index_mods=['FemV - RE9 Grace']`, 3 Symlinks |
| 2 | Anvil neu gestartet, `.modindex.json` von Platte | `rebuild()` erkennt die Änderung über den Fingerabdruck, Index enthält direkt `zz_...`, Datei landet im Spiel |

Zwei voneinander unabhängige Absicherungen greifen:

1. `_fingerprint()` in `modindex.py` nimmt die jüngste Zeit **aller Unterordner** statt nur der Wurzel.
   Der Neustart-Fall ist damit erledigt.
2. Der Deployer prüft vor dem Verlinken, ob jede Datei aus dem Index wirklich existiert, und liest bei
   Bedarf einmal frisch ein (`mod_deployer.py:596-612`). Der Laufzeit-Fall ist damit erledigt.

Zusätzlich wurde `_CACHE_VERSION` auf 2 gesetzt — Marcs vorhandener version-1-Cache wird beim ersten
Start verworfen und komplett neu aufgebaut. Ohne diesen Schritt wäre der falsche Eintrag geblieben.

Laufzeitkosten an Marcs echten 536 Mods gemessen (warmer Verzeichnis-Cache):
`0,003 s` alt gegen `0,047 s` neu. Unkritisch.

**Frage 1: gelöst.**

---

## 3. Frage 2: Merkt der Nutzer es, wenn doch etwas fehlt?

### Weg von `missing_sources`

`mod_deployer.py:885-891` hängt bei `missing_sources` einen Eintrag an `result.errors`, und
`result.errors` setzt `result.success = False` (Zeile 899-900). Von dort:

- `game_panel.silent_deploy()` reicht das Result unverändert zurück.
- `mainwindow._predeploy_for_launch()` (~3276-3291) schreibt die Fehler nach `self._last_deploy_errors`
  und gibt `False` zurück.
- `_on_start_game()` ruft `_report_predeploy_failure()` → **QMessageBox** mit
  `error.deploy_failed_title` / `error.deploy_failed_message`.

Auf dem Startweg käme die Meldung also tatsächlich beim Nutzer an — inklusive Abbruch des Spielstarts.

### Aber: `missing_sources` wird praktisch nie gefüllt

Das ist der wichtigste Befund dieser Prüfung. Der Zweig, der `missing_sources` füllt, liegt **hinter**
dem Neuscan. Der Neuscan (`_scan_mod` → `_walk_files`) nimmt nur Einträge auf, für die
`entry.is_file(follow_symlinks=True)` gilt. Nach dem Neuscan kann `not src_file.is_file()` deshalb nur
noch zutreffen, wenn die Datei in den Mikrosekunden zwischen Scan und Schleife verschwindet.

Gemessen (Fall 3 des Skripts): Datei **gelöscht** statt umbenannt, Mod bleibt aktiv.

```
[DEPLOY] Dateiliste war veraltet, neu eingelesen: FemV - RE9 Grace
[DEPLOY] Result: 2 symlinks, 0 copies, 0 errors
-> missing_sources : []
-> success         : True
-> links_created   : 2   (die Mod hat 0 Dateien beigesteuert)
```

Der Kommentar im Code sagt "Eine fehlende Quelldatei darf nicht als Erfolg durchgehen" — genau das
passiert hier aber. Die aktive Mod steuert null Dateien bei, es gibt keine Meldung, keinen Fehler,
kein Dialogfenster. Der Nutzer merkt es nicht.

Der zugehörige Test `tests/test_modindex_aktualitaet.py::test_wirklich_fehlende_quelldatei_ist_ein_fehler`
heißt zwar "ist ein Fehler", prüft aber weder `missing_sources` noch `success`. Er dokumentiert damit
das Gegenteil dessen, was sein Name behauptet.

### Weg von `stale_index_mods`

Nur `print()` auf stdout (`mod_deployer.py:875-880`). Kein `_dlog`, kein GUI-Element, keine
Benachrichtigung. Unter Flatpak — Marcs primärer Installationsweg — sieht er das nicht. Als reine
Diagnose ist das vertretbar, als Warnung nicht sichtbar.

### Deploy-Wege ganz ohne Ergebnisauswertung

`silent_deploy()` wird an fünf Stellen gerufen. Das Result wird nur auf dem Startweg und beim
Aufräum-Deploy ausgewertet:

| Stelle | Result ausgewertet? |
|--------|---------------------|
| `mainwindow.py:2728` (Leftover-Aufräumen mit keep-deployed) | ja, QMessageBox |
| `mainwindow.py:3041` (Vorab-Deploy vor Spielstart) | ja, QMessageBox |
| `mainwindow.py:3274` (keep-deployed eingeschaltet) | **nein** |
| `mainwindow.py:5339` (Profilwechsel bei keep-deployed) | **nein** |
| `mainwindow.py:7764` (Anvil wird beendet, keep-deployed) | **nein** |
| `game_panel.py:2059` (REDmod-Vorlauf) | **nein** |

Auf den drei keep-deployed-Wegen sowie beim REDmod-Vorlauf bleibt jeder Deploy-Fehler unsichtbar —
und keep-deployed ist bei Marc genau der Modus, in dem er das Spiel auch ohne Anvil startet.

### Sprache der Meldung

Die neue Fehlerzeile ist deutsch hartkodiert:
`f"{len(...)} Quelldatei(en) fehlen, z.B. {...}"`. Sie wird als `{details}` in den übersetzten Dialog
`error.deploy_failed_message` eingesetzt. In den anderen sechs Sprachen erscheint dann deutscher Text
in einem englischen/französischen/… Dialog. Alle übrigen Deployer-Fehler sind englisch
(`"No enabled mods found."`, `"write manifest: ..."`) — die Zeile ist also auch in sich uneinheitlich.

**Frage 2: nur zur Hälfte gelöst.** Der Meldeweg existiert und funktioniert, aber der Auslöser wird im
realistischen Fall nicht erreicht, und auf den keep-deployed-Wegen führt er ohnehin ins Leere.

---

## 4. Frage 3: Verbleibende stille Ausfälle im Deploy-Weg

Alle vier gemessen, nicht nur gelesen.

### [HOCH] Mod verliert ihre Dateien → `success: True`, keine Meldung
`mod_deployer.py:605-612`. Nach dem Neuscan ist die Liste leer, die Schleife läuft nicht, nichts wird
gemeldet. Gemessen in Fall 3. Tritt real auf, wenn Marc eine Datei außerhalb von Anvil löscht oder
wegschiebt.
Sinnvolle Abhilfe: vergleichen, ob eine Mod nach dem Neuscan **weniger** Dateien hat als der Index
vorher kannte — der Delta-Betrag gehört in `missing_sources`. Alternativ: eine Mod, die im Deploy null
verwertbare Dateien beisteuert, obwohl sie aktiv ist und kein Separator ist, in eine eigene Warnliste
schreiben.

### [HOCH] Mod steht gar nicht im Index → still nichts ausgerollt
`get_file_list()` gibt für unbekannte Mods `[]` zurück. `any(not f.is_file() for f in [])` ist `False`,
also gibt es keinen Neuscan, keine Meldung, keinen Fehler. Gemessen in Fall 4:
`im Spiel angekommen: False`, `success: True`, `links_created: 2` statt 3.
Erreichbar, wenn der Index den Mod-Ordner nie erfasst hat (`os.scandir`-Fehler im Rebuild, Rebuild vor
dem Anlegen des Ordners, oder — theoretisch — `_fingerprint()` liefert `0.0` und der neue Wächter
`if not current_mtime: continue` überspringt die Mod).
Abhilfe: statt `any(not f.is_file())` prüfen, ob die Liste leer ist **obwohl** der Mod-Ordner Inhalt
hat, und dann ebenfalls neu einlesen.

### [MITTEL] Echte Spieldatei liegt im Weg → nur stdout
Gemessen in Fall 5: `skipped_real_files: ['archive/pc/mod/00_...archive']`, dabei `success: True`,
`errors: []`. Ausgabe nur per `print()` in `game_panel.py:1282-1287`. Das ist der klassische Weg, auf
dem eine aktive Mod dauerhaft unsichtbar bleibt (einmal von Hand ins Spiel kopiert — ab da wird die
verwaltete Mod für immer übersprungen). Vom gemeldeten Problem nicht berührt, aber dieselbe
Fehlerklasse.

### [NIEDRIG] Aktive Mod ohne Ordner / ohne modlist-Eintrag
`mod_deployer.py:396-399` nimmt nur Namen auf, die in `modlist.txt` **und** in `active_mods.json`
stehen; `mod_deployer.py:457` überspringt Mods ohne Ordner kommentarlos. Beides ohne Meldung.

---

## 5. Nebenbefunde

- **[MITTEL] Testlücke:** `test_wirklich_fehlende_quelldatei_ist_ein_fehler` prüft die Behauptung
  seines Namens nicht. `assert ergebnis.missing_sources` und `assert not ergebnis.success` würden
  heute fehlschlagen.
- **[MITTEL] `missing_sources` ist faktisch toter Code** — nur über ein Zeitfenster von Mikrosekunden
  erreichbar. Der Nutzen der neuen `DeployResult`-Felder steht und fällt mit Punkt 4.1.
- **[NIEDRIG] Spielstart wird abgebrochen**, sobald `missing_sources` doch einmal greift (`success=False`
  → `return False` → kein Start). Bei einer einzigen verschwundenen Datei ist das hart. Marc sollte
  entscheiden, ob das eine Warnung mit Weiter-Option sein soll.
- **[NIEDRIG] `_fingerprint()` bei mtime `0.0`:** `if not current_mtime: continue` behandelt einen
  echten Zeitstempel 0 wie einen Fehler. Praktisch unerreichbar, aber `is None`-artige Prüfung wäre
  sauberer.
- **Architektur-Regeln:** keine Verletzung. Es wird weiterhin nur verlinkt bzw. über
  `GameCopyDeployPaths` kopiert, `.mods/` wird nicht umgebaut, Frameworks bleiben außen vor,
  `active_mods.json`/modlist-Logik unangetastet, nur globale API. Der Eingriff sitzt allein in der
  Frage, **welche Dateiliste** der Deployer benutzt — die Deploy-Mechanik selbst ist unberührt.
- **Tests:** `pytest -k "deploy or modindex or index"` → 165 grün, 1 rot.
  Der rote Test `test_predeploy_launch.py::test_appid_match_stops_at_the_value_boundary` kollidiert mit
  einem echten laufenden Steam-Prozess (`AppId=1091500`, Cyberpunk läuft gerade auf dem Rechner) und hat
  nichts mit dieser Änderung zu tun.

---

## Ergebnis

**Das gemeldete Problem ist gelöst — der Schutz davor ist es nicht.**

- Frage 1 (Mod wird ausgerollt): ✅ belegt, an der echten Instanz gemessen und im Wegwerf-Ordner
  in beiden Varianten nachgestellt.
- Frage 2 (Nutzer merkt es): ❌ Meldeweg vorhanden, Auslöser im realistischen Fall unerreichbar,
  auf drei von sechs Deploy-Wegen ohnehin ohne Wirkung.
- Frage 3 (verbleibende stille Ausfälle): ❌ mindestens zwei erreichbare Wege gemessen, auf denen eine
  aktive Mod ohne jede Meldung nicht im Spiel landet.

**NEEDS FIXES**
