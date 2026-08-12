# Dritte Prüfrunde — Anvil löscht Mods bei laufendem Spiel (Flatpak)

Datum: 2026-08-06
Prüfstand: uncommitted Änderungen auf `main` (d174cd6 + Arbeitsverzeichnis)
Installierter Flatpak: `com.github.Marc1326.AnvilOrganizer`, gebaut aus d174cd6 (**alter Code**)

Alle Aussagen unten sind durch ausgeführte Befehle belegt. Wo ein Beleg fehlt,
steht das ausdrücklich dabei.

---

## 0. Umgebung — gemessen, nicht angenommen

| Messung | Befehl / Ergebnis |
|---|---|
| PIDs in der Anvil-Sandbox sichtbar | `flatpak run --command=python3 …` → **2** (Host: 602) — Ursache des Vorfalls bestätigt |
| `org.freedesktop.Flatpak=talk` gesetzt | `flatpak info --show-permissions` → ja, ohne User-Override |
| Spielpfad Cyberpunk | `/mnt/Gaming/SteamLibrary/steamapps/common/Cyberpunk 2077` (aus `.anvil.ini`) |
| Steam läuft nativ, nicht als Flatpak | `pgrep -a steam` → `/home/mob/.local/share/Steam/…` |
| Testsuite | `300 passed, 1 skipped` |
| `py_compile` aller geänderten Dateien | OK |

### Host-Prozesssuche in der echten Sandbox

```
is_flatpak: True
PIDs sichtbar in Sandbox-/proc: 2
crash-recovery-Suche (game_path):  (None, True)  0.03s
Suche AppId 1091500:               (None, True)  0.02s
Suche steamwebhelper (Host läuft): (22491, True) 0.02s
lokal (sandbox-blind) steamwebhelper: None
```

Mit einem Stand-in auf dem Host, dessen Kommandozeile 1:1 der echten
Cyberpunk-Startzeile nachgebildet ist (Vorlage aus
`~/.local/share/Steam/logs/gameprocess_log.txt`):

```
reaper SteamLaunch AppId=1091500 -- '/mnt/Gaming/SteamLibrary/steamapps/common/Cyberpunk 2077/REDprelauncher.exe' '--launcher-skip'
```

```
crash-recovery (game_path):   (1437539, True)
watcher (Cyberpunk2077.exe):  Treffer  (Falsch-Positiv, s. u.)
REDprelauncher.exe:           (1437539, True)
```

Damit ist belegt: **Der Steam-Wrapper trägt den vollständigen Unix-Spielpfad in
seiner Kommandozeile**, die neue Crash-Recovery-Erkennung hat also eine reale
Grundlage.

Nebenbefund (wie in Runde 2): Der Host-Scan trifft **jede** Kommandozeile, die
den Suchbegriff enthält. Mein eigener Test-Shell-Prozess wurde als „Spiel"
erkannt, weil der Suchbegriff im Skripttext stand. Falsch-Positive gehen in die
sichere Richtung (nicht löschen).

---

## 1. Status der Runde-2-Befunde

| Nr. | Befund aus Runde 2 | Stand jetzt | Beleg |
|---|---|---|---|
| F-1 | `_crash_recovery_purge()` ungeschützt | **überwiegend behoben** — Guard über `find_game_process(None, game_path)`; Restloch ohne Manifest, siehe N-4 | Test A/B/C unten |
| F-2 | `_clear_watch_target()` entwertet die Nachprüfung | **halb behoben** — Clear entfällt, aber die Nachprüfung ist wirkungslos, siehe N-3 | Test t7/t8 |
| F-3 | Migration purgt bei UNKNOWN | **behoben** — `is_game_running()` vor jedem `silent_purge()` (`mainwindow.py:1047`, `:1131`) | Code |
| F-4 | REDmod-/GRB-Zweige ohne Sperre | **behoben** — `_confirm_start_while_running()` steht vor allen Zweigen (`game_panel.py:1956`) | Code |
| F-5 | Kein Ausweg bei Falsch-Treffer | **behoben für den Spielstart** — Dialog „Trotzdem starten"; für Tool-Start/Migration weiterhin nur Ablehnung | Code |
| F-6 | Watch-Ziel bleibt nach blindem Aufgeben stehen | **jetzt Absicht** (Kommentar `game_panel.py:2862`) | Code |
| F-7 | `game_state()` füllt den Zwischenspeicher nicht | **offen** (`game_panel.py:2807`) | Code |
| F-8 | Einzelner Fehltreffer beendet den Watcher | **behoben** — `_GAME_LOOKUP_GRACE` 60 s | Test t6 |
| F-9 | Kein Generationszähler | **eingeführt**, aber lückenhaft, siehe N-2 | Test t9 |
| F-10/F-11/F-12 | Kosmetik / Logstart / Manifest | unverändert bzw. erledigt | Code |

### Beleg zu F-1 (`_crash_recovery_purge`)

Mit gefälschtem Instanz-Verzeichnis in `/tmp` (keine Produktionsdaten berührt),
laufendem Stand-in-Prozess und ersetztem `ModDeployer`:

```
A) Manifest + laufendes Cyberpunk (Stand-in) : []                              ← kein Purge
   Log: [PURGE] TestInst: game may still be running — deployment kept
B) Manifest + unbenutzter Ordner             : ['purge', 'remove_orphaned_links']
C) KEIN Manifest + laufendes Cyberpunk       : ['remove_orphaned_links']       ← löscht trotzdem
```

---

## 2. Neue Befunde

### [HIGH] N-1 — Der Schutz beim App-Start hält nur genau diesen einen Moment

- Datei: `anvil/widgets/game_panel.py:2789-2794` (`game_state()`),
  `anvil/mainwindow.py:1580-1592`
- `_crash_recovery_purge()` erkennt jetzt korrekt, dass ein Spiel aus einer
  früheren Sitzung noch läuft, und lässt das Deployment liegen. Diese Erkenntnis
  wird aber **nirgends festgehalten**. Unmittelbar danach gilt wieder:
  `_watch_binary == "" and _watch_app_id is None` → `game_state()` liefert
  bedingungslos `GAME_STOPPED`.
- Belegt (Stand-in lief währenddessen):

```
Zustand nach Anvil-Neustart bei laufendem Spiel:
  game_state(): stopped | is_game_running(): False
  _do_redeploy  -> purge-Aufrufe: ['purge']
  closeEvent    -> purge-Aufrufe: ['purge']
  _unlock_ui(True) -> purge-Aufrufe: ['purge']
```

- Vollständiger Ablauf, der den gemeldeten Schaden erneut erzeugt:
  Spiel starten → Anvil schließen (Deployment bleibt, gewollt) →
  Anvil öffnen (Crash-Recovery schützt ✅) → **eine Mod an-/abschalten**
  (`_do_redeploy` → Purge) **oder Profil wechseln** (`:4743`) **oder Instanz
  wechseln** (`:1653`) **oder Anvil einfach wieder schließen** (`:7132`) → Mods weg,
  Spiel stürzt ab.
- Gleiches gilt, wenn der Nutzer das Spiel direkt über Steam startet, während
  Anvil offen ist und ein Deployment liegt.
- Fix-Vorschlag: `game_state()` bei fehlendem Watch-Ziel nicht hart `STOPPED`
  antworten lassen, sondern auf denselben Pfad-Check zurückfallen, den
  `_crash_recovery_purge()` benutzt (`find_game_process(None, str(self._current_game_path))`).
  Alternativ setzt `_crash_recovery_purge()` bei einem Treffer das Watch-Ziel
  der betroffenen Instanz.

### [HIGH] N-2 — `clear_watch_target()` zählt die Generation nicht hoch

- Datei: `anvil/widgets/game_panel.py:2767-2777`, `:2838-2846`
- `_watch_generation` wird nur in `_start_process_watcher()` erhöht. Nach
  `clear_watch_target()` läuft der alte Watcher-Thread weiter, hält sich für
  aktuell (`outdated()` ist False), ruft `lookup_game_pid()` auf — das liefert
  bei leerem Ziel `(None, True)` — liest das als „Spiel beendet" und feuert
  `game_stopped(True)`. `_unlock_ui(True)` prüft nach, bekommt ebenfalls
  `STOPPED` und **purgt**.
- Belegt:

```
Watcher läuft, game_state: running
>>> Nutzer wählt 'Trotzdem starten' -> clear_watch_target()
    generation: 1                       (unverändert)
[WATCHER] game process gone
[LAUNCH] game stopped — cleaning up
Nach 3 s Deploy-Zeit -> purge-Aufrufe: ['purge']
```

- Praktische Folge: Genau im Zeitfenster zwischen „Trotzdem starten" und dem
  Start des neuen Watchers läuft der Vorab-Purge und der Vorab-Deploy. Der alte
  Watcher pollt in dieser Zeit (Intervall 5 s) und löscht das **frisch
  ausgerollte** Deployment wieder. Ein Deploy mit vielen Mods dauert
  regelmäßig länger als 5 s.
- Betrifft auch `_on_unlock_clicked()` → „Ja" (`mainwindow.py:2754`), dort
  allerdings harmlos, weil ohnehin schon gepurgt wurde.
- Fix-Vorschlag: `clear_watch_target()` erhöht `_watch_generation`.

### [HIGH] N-3 — Der 120-Sekunden-Timeout löscht weiterhin, die „Nachprüfung" ist wirkungslos

- Datei: `anvil/widgets/game_panel.py:2757` (`_GAME_APPEAR_TIMEOUT`), `:2872-2884`
- Der Timeout-Zweig ruft `clear_watch_target()` nicht mehr auf — insoweit ist
  F-2 erledigt. Die Nachprüfung in `_unlock_ui()` findet aber **Millisekunden
  nach der letzten Watcher-Messung** statt und liefert deshalb praktisch immer
  dieselbe Antwort. Ein Spiel, das erst nach dem Zeitlimit erscheint, wird nicht
  gerettet.
- Belegt (Appear-Timeout auf 2 s gesetzt, Spiel erscheint nach 4 s):

```
[WATCHER] game process never appeared
[LAUNCH] game stopped — cleaning up
  purge-Aufrufe: ['purge']
  watch_binary: ''   game_state: stopped
```

  Gegenprobe, dass die Nachprüfung technisch funktioniert (Treffer exakt beim
  Nachprüf-Aufruf):

```
[WATCHER] game process never appeared
[LAUNCH] unlock requested, but the game is still running — keeping the deployment
  purge=[]
```

- Risiko im Alltag: `_launch_via_steam()` startet den Watcher **sofort** nach
  `steam -applaunch` (`game_panel.py:2606`). Muss Steam erst hochfahren, ein
  Proton-Prefix anlegen oder Shader vorbereiten, kann bis zum ersten Prozess mit
  `SteamAppId=` mehr als 120 s vergehen — das ist genau die Situation
  „während das Spiel gerade startete" aus der Meldung.
- Fix-Vorschlag: Im Timeout-Zweig `game_stopped.emit(False)` senden (UI
  entsperren, Deployment liegen lassen) oder das Zeitlimit deutlich anheben
  und die Nachprüfung zeitlich versetzen.

### [MEDIUM] N-4 — Crash-Recovery prüft nur, wenn ein Manifest da ist

- Datei: `anvil/mainwindow.py:1583-1592`
- Der Schutz hängt an `has_manifest`. Fehlt das Manifest, läuft
  `remove_orphaned_links()` ungeprüft und löscht **jeden** Symlink im
  Spielverzeichnis, der nach `.mods/` zeigt (`mod_deployer.py:940`).
- Belegt: Fall C oben — `['remove_orphaned_links']` trotz laufendem Prozess.
- Reale Relevanz: Von den zehn Instanzen im Basisverzeichnis hat aktuell genau
  **eine** ein `.deploy_manifest.json` (Starfield). Cyberpunk hat keins.
  Ein abgebrochener Deploy, ein fehlgeschlagener Purge oder ein Bestand aus
  einer älteren Version reicht also, damit der Schutz nicht greift.
- Fix-Vorschlag: Die Prozessprüfung vor **beide** Operationen ziehen, nicht nur
  vor `purge()`.

### [MEDIUM] N-5 — Kein „Trotzdem"-Ausweg außerhalb des Spielstarts

- Datei: `anvil/mainwindow.py:2599-2610`, `:1317`, `:2677`, `:1016`, `:1081`
- Proton-Tools, eigene Programme und die Storage-/Basis-Migration lehnen bei
  `GAME_RUNNING` bzw. `is_game_running()` hart ab. Der neue Dialog hängt nur am
  Spielstart-Knopf (`game_panel.py:1929`).
- Ein dauerhaftes Aussperren entsteht dadurch **nicht**: das Watch-Ziel überlebt
  keinen Anvil-Neustart, danach ist alles wieder frei. Innerhalb einer Sitzung
  ist der einzige Ausweg aber der Spielstart-Dialog (der `clear_watch_target()`
  aufruft) oder der Entsperren-Knopf, den es nur bei aktiver UI-Sperre gibt.
- Der `custom`-Zweig in `_on_start_clicked()` (`game_panel.py:1942-1950`) kehrt
  vor `_confirm_start_while_running()` zurück; die Absicherung übernimmt dort
  `_predeploy_for_launch()` — sicher, aber ohne Ausweg.

### [MEDIUM] N-6 — Zwei Löschwege im Spielverzeichnis ganz ohne Prüfung

| Stelle | Was passiert |
|---|---|
| `mainwindow.py:8007-8017` (Framework deinstallieren) | `target.unlink()` / `shutil.rmtree(target)` direkt unter `game_path` — kein „Spiel läuft"-Check |
| `mainwindow.py:6457` (`_ctx_remove_mods`) | `shutil.rmtree(mod_path)` löscht die **Quelle** der aktiven Symlinks |

Beide sind während der UI-Sperre nicht erreichbar, wohl aber nach
„Entsperren → Nein", also genau in dem Zustand, den der Fix neu geschaffen hat
(UI frei, Deployment liegt, Spiel läuft weiter).

### [LOW] N-7 — `game_state()` legt sein eigenes Ergebnis nicht ab

`game_panel.py:2807` ruft `lookup_game_pid()` und gibt das Ergebnis direkt
zurück, ohne `_note_game_state()`. Solange der Watcher läuft, füllt der den
Zwischenspeicher alle 5 s; ist der Watcher beendet, kostet jede Abfrage
(`_do_redeploy`, `closeEvent`, Profilwechsel …) einen eigenen Host-Prozess auf
dem GUI-Thread — bis zu `_HOST_SCAN_TIMEOUT` = 3 s Blockade.

### [LOW] N-8 — Dauerhaft kaputter Host-Scan heißt: nie wieder aufräumen

`find_game_process()` liefert bei fehlendem `flatpak-spawn` `(None, False)`.
Dann liefert `is_game_running()` immer True und `_crash_recovery_purge()`
überspringt jede Instanz mit Manifest. Sicher, aber das Spielverzeichnis wird
nie wieder sauber, ohne dass der Nutzer erfährt warum (nur eine Zeile im Log).

### [INFO] N-9 — Übersetzungen

`dialog.unlock_purge_title`, `dialog.unlock_purge_text`,
`dialog.start_while_running_text` und `error.game_already_running` sind in
**allen sieben** Locales vorhanden und übersetzt (geprüft mit `json.load`).
`storage.error_game_running` ist in es/fr/it/pt/ru weiterhin englisch —
vorbestehend, nicht durch diese Änderung verursacht.

---

## 3. Antworten auf die gestellten Fragen

### Frage 1 — Inventur aller Wege, auf denen Dateien im Spielverzeichnis verschwinden

| # | Weg | Guard | Bewertung |
|---|---|---|---|
| 1 | `_predeploy_for_launch` → `silent_purge` (`:2610`) | `game_state()==RUNNING` → Abbruch | ✅ |
| 2 | `_do_redeploy` (`:2333`) | `_game_running or is_game_running()` | ✅ — wirkungslos nach Neustart (N-1) |
| 3 | `_teardown_current_instance` (`:1653`) | dito | ✅ — dito |
| 4 | Profilwechsel (`:4743`) | dito | ✅ — dito |
| 5 | `closeEvent` (`:7132`) | dito | ✅ — dito |
| 6 | `_unlock_ui` → `_purge_after_game` (`:2773`) | `stopped` **und** `is_game_running()` | ✅ — dito, plus N-2/N-3 |
| 7 | `_on_unlock_clicked` → „Ja" (`:2753`) | ausdrückliche Nutzerentscheidung | ✅ gewollt |
| 8 | Storage-Migration (`:1047`, `:1131`) | `is_game_running()` vor jedem Purge | ✅ |
| 9 | `_crash_recovery_purge` → `purge()` (`:1602`) | Pfad-Suche im Host-`/proc` | ✅ belegt |
| 10 | `_crash_recovery_purge` → `remove_orphaned_links()` (`:1603`) | **nur wenn Manifest da** | ❌ N-4 |
| 11 | `ModDeployer.deploy()` purgt intern (`mod_deployer.py:331`) | erbt den Guard des Aufrufers | ⚠️ jeder Deploy ist auch ein Purge |
| 12 | GRB-Forge-Zweig `silent_deploy()` (`game_panel.py:1974`) | `_confirm_start_while_running()` davor | ✅ |
| 13 | REDmod-Zweig `silent_deploy()` (`game_panel.py:1990`) | dito | ✅ |
| 14 | Framework deinstallieren (`mainwindow.py:8007`) | **keiner** | ❌ N-6 |
| 15 | `_ctx_remove_mods` → `rmtree` der Quelle (`:6457`) | UI-Sperre (umgehbar) | ⚠️ N-6 |
| 16 | `plugins_txt_writer` löscht Case-Varianten (`:99`) | erbt Deploy/Purge-Kontext | ⚠️ nicht separat geprüft |

### Frage 2 — Ablauf des gemeldeten Vorfalls

**Start 1 → Beenden → Start 2 → Start 3** (Anvil bleibt offen)

| Schritt | Ablauf | Ergebnis |
|---|---|---|
| Start 1 | `_confirm_start_while_running` (kein Ziel → still) → `_predeploy_hook` → Purge + Deploy → Steam → `game_started` → UI-Sperre → Watcher | ✅ |
| Watcher | sucht bis 120 s, danach Polling alle 5 s | ✅ solange das Spiel binnen 120 s erscheint (**sonst N-3**) |
| Beenden | `pid=None, reliable` → `game_stopped(True)` → `_unlock_ui` prüft nach → Purge + `clear_watch_target` | ✅ |
| Start 2 / Start 3 | Ziel leer → `STOPPED` → Purge (No-Op) + Deploy → Start | ✅ |
| Mod umschalten, während das Spiel läuft | `_do_redeploy` → `is_game_running()` True → „leftover kept" | ✅ |

**Spiel läuft → Anvil beenden → Anvil neu starten**

| Schritt | Ablauf | Ergebnis |
|---|---|---|
| Anvil beenden | `closeEvent` → `_game_running` True → Deployment bleibt | ✅ |
| Anvil neu starten | `_crash_recovery_purge` findet den Spielpfad in der Host-Kommandozeile → „deployment kept" | ✅ **belegt**, sofern ein Manifest existiert (**sonst N-4**) |
| Danach: Mod umschalten / Profil wechseln / Instanz wechseln / Anvil erneut schließen | `is_game_running()` → False (Ziel leer) → **Purge** | ❌ **N-1 — der Vorfall wiederholt sich** |

### Frage 3 — Kann sich der Nutzer aussperren?

- **Spielstart:** Nein. Bei `UNKNOWN` wird gestartet, bei `RUNNING` fragt der
  neue Dialog. „Trotzdem starten" räumt das Ziel weg.
- **Proton-Tools / eigene Programme:** Innerhalb der Sitzung blockiert, kein
  eigener Ausweg (N-5). Nach einem Anvil-Neustart wieder frei.
- **Profil-/Instanzwechsel:** immer möglich, es wird nur nicht gepurgt.
- **Migration:** blockiert, solange `is_game_running()` True ist — also auch bei
  `UNKNOWN`. Ausweg: Anvil neu starten. Zwischenzustand beachten: der Check
  liegt **nach** `switch_instance(name)`, ein Abbruch lässt Anvil auf einer
  anderen Instanz stehen.
- **App beenden:** immer möglich.
- **Entsperren:** immer möglich, beide Wege vorhanden.

**Ergebnis: kein dauerhaftes Aussperren** — das Watch-Ziel überlebt keinen
Neustart. Dieselbe Eigenschaft ist zugleich die Ursache von N-1.

### Frage 4 — Der Dialog „Trotzdem starten"

Text (de): *„Es sieht so aus, als würde noch ein Spiel laufen.\n\nTrotzdem
starten? Anvil räumt dabei den Spielordner auf — ein noch laufendes Spiel
stürzt ab."*

Was danach passiert, Schritt für Schritt (`game_panel.py:1925-1927` → `:1997`):

1. `clear_watch_target()` — Ziel weg, `game_state()` antwortet ab jetzt `STOPPED`.
2. `_predeploy_hook("game_start")` → `_predeploy_for_launch` → **`silent_purge()`**
   (alle Symlinks weg) → `silent_deploy()` (alles neu).
3. `_do_launch()` → `steam -applaunch …`.

Bewertung:

- **Der Warntext ist inhaltlich korrekt und deutlich.** Er benennt sowohl das
  Aufräumen als auch die Folge (Absturz). Gleiches gilt für den
  Entsperren-Dialog.
- **Aber:** Läuft tatsächlich noch ein Spiel, wird es mit hoher
  Wahrscheinlichkeit beschädigt/abstürzen — der Purge entfernt die Dateien,
  die es gerade offen hat. Das ist so gewollt und angesagt.
- **Zusätzlicher, nicht angesagter Schaden:** Durch N-2 kann der alte Watcher
  nach dem Deploy erneut aufräumen. Dann startet das Spiel ohne Mods,
  obwohl der Nutzer das Gegenteil erwartet. Das steht in keinem Dialogtext.
- Nicht verifiziert (Spiel wurde nicht gestartet): wie Steam auf ein zweites
  `-applaunch` bei bereits laufendem Spiel reagiert. Möglich ist, dass gar
  nichts startet und der Nutzer nur den Purge+Deploy bekommt.

---

## 4. Ergebnis

**NEEDS FIXES**

Was jetzt nachweislich hält:
- Die Prozesssuche läuft auf dem Host und funktioniert in der echten Sandbox.
- Die vier ursprünglich gemeldeten `silent_purge()`-Pfade sind abgesichert.
- Der App-Start räumt nicht mehr unter einem laufenden Spiel auf (mit Manifest).
- REDmod-/GRB-Startzweige und die Migration sind abgedeckt.
- Der Nutzer kann sich nicht dauerhaft aussperren.

Was den gemeldeten Schaden weiterhin erzeugen kann:
1. **N-1 (HIGH)** — Nach einem Anvil-Neustart bei laufendem Spiel ist Anvil
   wieder blind; Mod-Umschalten, Profil-/Instanzwechsel und das nächste
   Schließen purgen. Belegt.
2. **N-2 (HIGH)** — `clear_watch_target()` ohne Generationswechsel lässt den
   alten Watcher das frisch ausgerollte Deployment wieder löschen. Belegt.
3. **N-3 (HIGH)** — Der 120-Sekunden-Timeout purgt weiterhin; die Nachprüfung
   in `_unlock_ui` misst faktisch denselben Moment noch einmal. Belegt.
4. **N-4 (MEDIUM)** — Ohne Manifest fegt `remove_orphaned_links()` beim App-Start
   ungeprüft durch. Belegt. Betrifft aktuell neun von zehn Instanzen.

N-5 bis N-9 sind Nacharbeit.
