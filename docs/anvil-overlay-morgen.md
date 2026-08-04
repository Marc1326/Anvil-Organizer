# Was morgen noch zu tun ist — Overlay-Deploy

Stand: 04.08.2026, Abend
Branch: `feat/overlay-deploy` im Worktree `/home/mob/Projekte/anvil-overlay`
Tests: 298 gruen, 1 uebersprungen

---

## Zuerst: der Spieldurchlauf zaehlt nicht

Cyberpunk lief heute mit Overlay bis ins Hauptmenue. **Das war trotzdem kein
Erfolg** — die Schichtreihenfolge war verdreht, bubblewrap versteht
`--overlay-src` umgekehrt zur Kernel-Option. Jede Mod, die eine vorhandene
Spieldatei ersetzt, war wirkungslos. Nachgemessen:

```
--overlay-src modschicht --overlay-src spiel  ->  VANILLA
--overlay-src spiel --overlay-src modschicht  ->  VON-DER-MOD
```

Behoben und mit einem Test abgesichert, der eine Datei in beide Schichten
legt und durch den echten Wrapper prueft. Der Durchlauf muss aber wiederholt
werden.

**Ablauf:**

1. Anvil schliessen, pruefen dass der Spielordner wieder bei 25 Eintraegen steht
2. Deploy in der Sandbox neu bauen
3. Steam beenden, Startoption auf den frischen Wrapper setzen, Steam starten
4. Cyberpunk starten
5. Pruefen: laedt CET (`~`), schreibt RED4ext nach `.overwrite`, bleibt der
   Spielordner bei 25 Eintraegen

**Achtung bei Schritt 3:** Cyberpunks Startoption enthaelt jetzt wieder

```
PROTON_LOG=1 WINEDLLOVERRIDES="winmm,version=n,b" %command%
```

Die darf nicht verlorengehen. Der Wrapper muss **davor** und der Rest
dahinter, also:

```
"<wrapper>" %command%
```

laesst die Umgebungsvariablen fallen. Richtig waere, sie im Wrapper zu setzen
oder die Zeile zu kombinieren — **das ist noch ungeklaert und muss vor dem
Test entschieden werden.**

---

## Offene Entscheidung: Spielstarts, die den Overlay umgehen

Der Mount haengt an der Steam-Startoption. Nicht abgedeckt sind:

- GOG- und Epic-Instanzen (kein Steam, keine Startoption)
- Zweitbinaries und `GameLaunchViaProton`
- eigene Programme aus dem Executables-Editor (xEdit, LOOT)
- `redMod.exe deploy` bei Cyberpunk

Diese sehen ein **unmodifiziertes** Spiel. Anvil meldet trotzdem Erfolg.

Zwei Wege:

- **A** — Anvil startet Proton selbst und haengt vorher ein. Deckt alles ab,
  kostet Steam-Overlay, Spielzeit und Controller-Profile.
- **B** — In der Oberflaeche klar sagen, dass der Overlay fuer diese Instanz
  bzw. diesen Start nicht greift, und den Schalter dort gar nicht anbieten.

Produktentscheidung, keine Korrektur. Muss Marc treffen.

---

## Restliche Befunde aus den drei Pruefberichten

Berichte liegen in `docs/anvil-overlay-review1.md` bis `review3.md`.
Abgearbeitet sind alle drei kritischen und die meisten hohen. Offen:

### Mittel

- `localconfig_files()` nimmt fest `~/.local/share/Steam` an. `~/.steam/steam`
  und Flatpak-Installationen fehlen. `steam_utils.find_steam_path()` existiert
  bereits und sollte benutzt werden.
- `_set_overlay_launch_option()` schreibt ohne Rueckfrage in **alle**
  gefundenen Steam-Konten. Es gibt kein Gegenstueck zum Entfernen, und die
  angelegte `.anvil-backup` wird nie wieder eingespielt.
- Startoption kann gesetzt werden, bevor je ein Deploy lief — dann zeigt sie
  auf einen Wrapper, den es nicht gibt, und Steam startet das Spiel gar nicht.
- Kein Vorab-Test, ob `.mods` und die Schicht auf demselben Dateisystem
  liegen. Sonst faellt jede Datei auf Kopieren zurueck: aus 0,23 s und null
  Bytes werden zweistellige Gigabyte pro Deploy.
- `_UNSUPPORTED_UPPER` ist eine Sperrliste, die Meldung nennt eine
  Positivliste. `ntfs3`, `exfat` und `fuseblk` rutschen durch und scheitern
  erst beim Mount. Ausserdem wird nicht geprueft, ob Schreibschicht und
  Arbeitsverzeichnis auf demselben Dateisystem liegen — der Kernel verlangt es.
- `diagnostics._overlay_status()` entscheidet allein an der Existenz des
  Manifests. Nach dem Zurueckschalten meldet die Diagnose dauerhaft "overlay".
- Der Overlay-Schalter erscheint auch bei Spielen mit eigenem Deployer, wo er
  wirkungslos bleibt.
- Zieht eine Instanz um (Basisverzeichnis-Migration, Umbenennen), zeigt die
  Startoption ins Leere. Nichts in Anvil weist darauf hin.

### Klein

- `start-sandbox.sh` hat `/home/mob/anvil-overlay-data` und `.venv/bin/python`
  fest verdrahtet, dazu Kommentare mit Benutzernamen. **Gehoert nicht in einen
  Merge** — entweder ueber Umgebungsvariablen loesen oder nach `tools/`
  verschieben und aussen vor lassen.
- Die neuen deutschen Texte in `de.json` schreiben "daruebergelegt",
  "erfuellt", "laeuft" statt Umlauten. Der Rest der Datei nutzt echte Umlaute.
- `overlay.requirements_ok` und `overlay.launch_option_hint` sind in allen
  sieben Sprachen definiert, werden aber von keiner Codestelle gelesen.
- `mount.conf` trennt mit `|` und `:` ohne Maskierung. Ein Pfad mit diesen
  Zeichen laesst die Zeile still zerfallen.
- `start.log` waechst unbegrenzt.
- `_tune_for_overlay()` verbindet ueber Methodennamen als Zeichenketten.
  Umbenennen bricht still — genau so ist der tote ReShade-Setter unbemerkt
  geblieben. Besser: ein schmales Protocol.
- `filesystem_of()` entschluesselt nur `\040`, nicht `\011`, `\012`, `\134`.

---

## Was heute liegengeblieben ist, weil Marc es nicht wollte

- **Nicht mit dem Hauptprojekt verknuepfen.** Kein Merge, kein Cherry-Pick,
  kein Rebase. Der Worktree bleibt fuer sich.
- **Cache-Reste im Spielordner** (`final.redscripts.modded`,
  `r6/cache/modded/`, alte `red4ext/plugins/`) wurden nicht angefasst. Der
  Versuch wurde abgebrochen, weil Anvil zu dem Zeitpunkt ein aktives
  Symlink-Deployment ausgerollt hatte. Nur bei geschlossenem Anvil und ohne
  Deployment sinnvoll.

---

## Was heute schiefging und nicht nochmal passieren darf

**Marcs Cyberpunk-Startoption wurde geloescht.** Der Blockanker in
`set_launch_options` war nicht auf den App-Block begrenzt, und dieselbe
Kennung steht fuenfmal in `localconfig.vdf`. Beim ersten Lesen wurde die
Lizenzangabe erwischt, daraufhin faelschlich "keine Startoptionen gesetzt"
gemeldet und spaeter der echte Wert ueberschrieben.

Behoben: der Pfad wird jetzt Abschnitt fuer Abschnitt abgestiegen
(`UserLocalConfigStore/Software/Valve/Steam/apps`), gearbeitet wird nur
innerhalb des gefundenen Blocks. Vier Tests decken den Fall ab, dazu eine
Pruefung gegen die echte Datei.

Der Wert wurde von Marc von Hand wieder eingetragen und verifiziert.

**Regel daraus:** an fremden Konfigurationsdateien nichts schreiben, ohne
vorher den Ist-Zustand zu sichern **und** die geschriebene Stelle
gegenzulesen.

---

## Reihenfolge fuer morgen

1. Startoptionen-Frage klaeren (Wrapper + `WINEDLLOVERRIDES` zusammen)
2. Spieldurchlauf wiederholen, diesmal mit korrekter Schichtreihenfolge
3. Entscheidung zu GOG/Epic/Zweitbinaries
4. Mittlere Befunde abarbeiten
5. Erst danach ueberlegen, ob und wie zusammengefuehrt wird
