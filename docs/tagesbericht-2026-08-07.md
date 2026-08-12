# Was am 07.08.2026 herauskam

Ausgangspunkt war ein Bildschirmvideo: V's Arme sind in der Ego-Sicht verdreht und
überstreckt. Die Suche danach hat drei echte Anvil-Fehler freigelegt, die mit dem
Armbug nichts zu tun hatten — und am Ende eine belastbare Antwort darauf, warum die
dafür gedachten Mods das Problem nicht lösen können.

---

## 1. Behobene Anvil-Fehler

### RED4ext-Plugins wurden verlinkt statt kopiert — Commit `8768545`

Anvil legt Symlinks im Spielordner an. Für native DLLs geht das unter Proton schief:
Der Windows-DLL-Loader bekommt über einen Symlink keine gültige PE-Struktur, RED4ext
meldet `unsupported API version` und lädt das Plugin nicht.

Bisher half nur, dass die großen Frameworks **namentlich** in `GameDirectInstallMods`
stehen und deshalb kopiert werden. Jede andere Mod mit RED4ext-Plugin fiel durch.
Jetzt steht `red4ext/plugins` in `GameCopyDeployPaths` — die Regel hängt am Zielpfad
statt am Mod-Namen.

⚠️ **Wichtig für die Bewertung:** Dieser Fix war *nicht* die Ursache des ACU-Problems.
Nach dem Fix lag die DLL als echte Datei im Spielordner und wurde **trotzdem**
abgelehnt. Der Fix ist richtig, aber er hat das Problem nicht gelöst, für das er
gebaut wurde.

### Der Framework-Dialog verschwieg die Folge der Ablehnung — Commit `8768545`

„Als Framework installieren?" — bei Ablehnung wird die Mod normal installiert und
verlinkt. Das stand nirgends, also war „Abbrechen" die scheinbar vorsichtige Wahl.
Jetzt steht ein Hinweis im Dialog, übersetzt in **alle sieben** Locales (de, en, es,
fr, it, pt, **ru** — ru fehlt in der Checkliste in CLAUDE.md, existiert aber).

### Framework-Updates überlebten das Aufräumen nicht — Commit `49504b9`

Der gravierendste Fund. Ein Framework wird **direkt in den Spielordner** installiert,
nicht nach `.mods/`. Lief seither kein Deploy, kannte `.mods/` die neue Fassung nicht
— und der Purge nach Spielende löschte das Update. Der nächste Start rollte die alte
Version wieder aus, ohne dass irgendetwas fehlschlug.

Genau so ist Marcs **RED4ext-Update von 1.30.0 auf 1.29.1 zurückgefallen**, unbemerkt.

Der Deploy hatte für diesen Fall längst einen Reverse-Sync, das Aufräumen nicht.
Jetzt sichert der Purge eine neuere Datei zurück nach `.mods/`, bevor er sie entfernt.
Zwei Tests dazu, gegengeprüft: ohne den Fix schlagen sie fehl.

### Nebenbei — Commit `46aa6ca`

- `build-flatpak.sh` suchte nur ein natives `flatpak-builder` und wollte es sonst per
  `sudo` nachinstallieren. Auf diesem System ist der Builder selbst ein Flatpak, also
  lief das Skript in eine Passwortabfrage. Es findet jetzt `org.flatpak.Builder`.
- `packaging/flatpak/repo/` lag mit **4278 Dateien** im Git und änderte sich bei jedem
  Build. Enttrackt — `git status` ging von über 4000 auf 16 Zeilen zurück.

**Testlage:** 318 Tests grün, 1 übersprungen.

---

## 2. Am System repariert

| | |
|---|---|
| RED4ext | von 1.29.1 auf **1.30.0** gebracht, in `.mods/` **und** im Spielordner; alte Fassung gesichert unter `~/anvil-backup-red4ext-1.29.1/` |
| ACU - Character Customization | als normale Mod neu installiert; die verwaisten Framework-Einträge in `framework_state.json` und `plugins/games/game_cyberpunk2077.json` entfernt |
| `release/` | 36 alte AppImages gelöscht, 3,1 GB frei |

---

## 3. Erkenntnisse über das Setup

**Flatpak und Projekt teilen sich die Daten.** In
`~/.var/app/com.github.Marc1326.AnvilOrganizer/config/AnvilOrganizer/InstanceManager.conf`
steht `base_dir=/home/mob/.anvil-organizer` — es gibt keine getrennten Instanzdaten.
Deshalb liefen am 05./06.08. laut `activity.log` v1.5.2, v1.6.1 und v1.7.0 auf
demselben Bestand.

**`flatpak update` baut nichts.** Der Anvil-Flatpak kommt aus einem lokalen Repo im
Projektordner (`packaging/flatpak/repo`, 128 MB). Ohne vorherigen Build meldet das
Update „nichts zu tun" — und das stimmt sogar, es ist nur nicht das, was man erwartet.
**Merksatz: eine Codeänderung wirkt bei Marc erst nach `./build-flatpak.sh`.**

**Eine tickende Bombe steht noch:** In `.profiles/Vanilla/` liegt ein altes
`modlist.txt` vom 17. März mit 29 Zeilen. Fehlt einmal das globale
`.profiles/modlist.txt`, migriert Anvil daraus (`mod_list_io.py:465`) — und von 350
aktiven Mods blieben 27 übrig.

---

## 4. WolvenKit läuft unter Linux

Bericht 7.5 sagt „kein natives Linux-Build". Das gilt der **GUI**. Das CLI ist ein
.NET-Global-Tool und läuft:

```bash
export PATH="$HOME/.dotnet/tools:$PATH"
export DOTNET_ROLL_FORWARD=LatestMajor      # Tool will .NET 8, System hat 10
cp77tools archiveinfo <archiv-oder-ordner> -l < /dev/null
```

Ohne `< /dev/null` wartet es auf Eingaben und hängt. Installiert ist
`wolvenkit.cli 8.20.0`, der Befehl heißt **`cp77tools`**. Ob **Packen** ohne die
Windows-Oodle-DLL geht, ist ungeprüft — **Lesen geht**, und das ändert die
Analysemöglichkeiten grundlegend: echte Dateinamen statt Hashes.

---

## 5. Der eigentliche Befund zum Armbug

Ausführlich in `JPP-Anpassung/docs/befund-2026-08-07-animationsmods.md`.

**Keine der drei Animations-Mods enthält eine einzige Workspot-Animation.**
Suche nach `workspot|scene|mirror|interaction|sitting|vending`: **0 Treffer** in allen
dreien. Sie liefern Waffen-Animationen und Rigs.

Damit ist belegt, was vorher Annahme war: Die T-Pose am Spiegel **kann** von diesen
Mods nicht behoben werden. JBs Ausweichen (Fix 12) ist der einzige verfügbare Weg,
nicht nur der bequemste.

**Aber die drei streiten sich um 27 Dateien, darunter das Skelett.** Ladereihenfolge
ist ASCII, die zuerst geladene gewinnt:

```
Okayyyyy2.archive        TPP Melee Combat        ← gewinnt ALLES
Okayyyyy44444.archive    TPP Pistol Combat
okayyyyy3333.archive     Every Animation Redone  ← 251 Dateien, verliert alles Geteilte
```

Umkämpft sind `player_woman_skeleton.rig`, `woman_base.rig`,
`woman_base_deformations.rig` und `player_woman_base_deformations.rig`.

**`TPP Melee Combat` bestimmt derzeit allein V's Skelett** — und stand laut Bericht
18.4 am 02.08. noch **nicht** im aktiven Profil. Das ist der einzige belegte
Unterschied zwischen „lief früher besser" und heute; an JB selbst hat sich in der Zeit
nichts geändert.

Im Gesamtsetup (326 aktive Archive, 9976 Dateien) gibt es **544 Konflikte**. Dabei
aufgefallen: `player_woman_skeleton - copy (2).rig` und `- copy (3).rig` — versehentlich
mitgepackte Kopien in einer fremden Mod.

---

## 6. Zum Stand von JB

- **Fix 12 funktioniert jetzt.** Das Log zeigt sauberes Hin und Zurück, mehrfach.
  Das hat vorher nie geklappt.
- **Aber der Rückweg kommt zu früh.** `IsActorInWorkspot` flackert; um 14:11:31 meldet
  es „vorbei", das Video zeigt bei 14:11:35 V am Spiegel mit verdrehten Armen, um
  14:11:37 meldet es wieder „Workspot beginnt".
- **Fix 14 ist eingespielt, aber nicht die Lösung.** Er beruhte darauf, dass der
  kaputte Zustand im Spielstand eingebrannt sei — der Bug tritt aber auch im frischen
  Spielstand auf. Die Ungereimtheiten, die er behebt, sind echt; Schaden richtet er
  nachweislich keinen an. **Nicht committet.**

---

## 7. Offen

1. **Der Test:** `TPP Melee Combat` abhaken → Pistol Combat gewinnt die Rigs wie
   früher → Prolog, Spiegel, Arme ansehen. Eine Änderung, klares Ergebnis.
2. **Pixelfehler beim Schießen** — im Video nicht gefunden, Zeitstelle fehlt.
3. **Kommen alle Archive im Spiel an?** Nicht abschließend belegt: Anvil löscht das
   Deploy-Manifest beim Aufräumen. Beim nächsten Spielstart in 10 Sekunden prüfbar.
4. **Framework-Liste aufräumen** — JB steht dort, ist aber keins. Ohne Wirkung auf den
   Deploy (`direct_patterns` kennt es nicht), aber unsauber.
5. Legacy-`modlist.txt` entschärfen.
