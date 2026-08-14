# Overlay-Deploy: Mount direkt auf den Spielordner

Stand: 14.08.2026 — produktiver Live-Test mit Cyberpunk 2077.

## Erkenntnisse des Tages (Live-Tests mit Cyberpunk 2077)

| Versuch | Ergebnis |
|---|---|
| Leeres Overlay auf den Spielordner, normaler Steam-Start | läuft |
| Overlay mit Frameworks (winmm/RED4ext) | läuft, RED4ext lädt |
| + Archive | läuft, Mods sichtbar |
| Vollständige Schicht mit alter `r6/config/settings/platform/pc/options.json` | Spiel beendet sich still |
| Dieselbe Schicht ohne den alten Settings-Override | **läuft, Mods laden** |
| Produktivstart Anvil → Steam → Spiel | 9/9 RED4ext-Plugins, 364 Archive und 31.301 redscript-Refs |
| Augenmod im Overlay | Colorful-Augen sichtbar; verbleibender Head-Fehler als Modkonflikt isoliert |

Die Abstürze kamen nicht vom Overlay-Mechanismus. Der konkrete Startkiller
war eine von `v2 UnlockFovImmersiveFirstPersonPatch` gelieferte
`options.json` in Version 136; das aktuelle Spiel erwartet Version 140.
Sie wird deshalb nur im Overlay-Staging ausgeschlossen. Der Symlink-Weg
bleibt unverändert. Das produktive Staging nutzt ansonsten dieselben Routen
wie der Symlink-Deployer — `test_overlay_matches_symlink.py` hält beide Wege
deckungsgleich.

Weitere Beobachtungen:

- pressure-vessel (Steam-Container) erbt den Mount problemlos — der
  Mount muss nur **vor** dem Spielstart stehen.
- Ein abgebrochener Lauf hinterlässt einen halben redscript-Cache in
  der Schreibschicht; der naechste Start liest ihn und scheitert.
  Das ist ein Spiel-Cache-Problem, kein Overlay-Problem.
- Mehrfach-Mounts auf denselben Ordner stapeln sich.  Der Helfer nimmt
  vor einem neuen Mount erst alle alten Schichten ab.
- Der Mount übersteht das Spielende — er wird erst beim Purge
  abgebaut (oder beim Wechsel auf Symlinks).
- Der direkte Kernel-Mount ist global und lebt nicht in einem kurzlebigen
  Spiel-Namespace. Nach zuverlässig erkanntem Spielende muss Anvil deshalb
  `silent_purge()` ausführen; drei Live-Tests bestätigten andernfalls einen
  weiter aktiven Mount.
- Wiederverwendete Overlay-Verzeichnisse können `trusted.overlay.origin`
  tragen und mit `ESTALE` scheitern. Der privilegierte Helfer entfernt das
  Attribut am Upper-Wurzelverzeichnis, leert das root-eigene Workdir und
  mountet mit `index=off`.
- Der visuelle Fehler „Colorful-Augen und Mund sichtbar, Kopf schwarz" war
  kein Overlay- oder Archiv-Reihenfolgefehler. Ursache war die aktivierte
  Option `UV body user - Unique eyes compatible`. Verifiziert funktioniert
  die Kombination aus Colorful, Unique Eyes Core V2.5 Default und
  VTK Vanilla HD Head; UV-Option und RE9 Grace waren dabei aus.

## Architektur

```text
deploy()                          purge()
   │                                 │
   ├─ Schicht bauen (Staging)       ├─ purge_mounts (pkexec)
   ├─ Manifest schreiben            │   ├─ umount (Stapel-sicher)
   ├─ mount.conf schreiben          │   └─ work/ aufräumen (root-eigen)
   ├─ Helferskript schreiben        ├─ Schicht löschen
   └─ mount (pkexec)                └─ Manifest + mount.conf löschen
        └─ Kernel-Overlay auf den Spielordner
           lowerdir = Schicht:Spielordner
           upperdir = .overwrite
```

- `anvil/core/overlay_mount.py` — Helferskript, pkexec-Aufruf,
  polkit-Einrichtung.  Kein bwrap, kein Namespace, kein Steam-Eingriff.
- `anvil/core/overlay_deployer.py` — Schnittstelle wie der
  Symlink-Deployer; mounted am Ende von deploy().
- `anvil/core/overlay_staging.py` — baut die Schicht mit den echten
  Deploy-Routen, dedupliziert kollidierende Archive und wendet ausschließlich
  für Overlay konfigurierte Pfadausschlüsse an.

## Archivpriorität

Cyberpunk lädt die Archive nach Dateinamen; die erzeugte `modlist.txt` wird
zwar geöffnet, entschied in drei Messläufen aber nicht über die Priorität.
Darum nummeriert das Staging ausschließlich `.archive`-Dateien unter
`archive/pc/mod`:

```text
000_...  höchste GUI-Priorität
001_...
002_...
```

Bei REDengine gewinnt das alphabetisch erste Archiv. Gleichnamige Archive
werden vor dem Nummerieren dedupliziert, damit nicht Gewinner und Verlierer
unter verschiedenen Namen gleichzeitig geladen werden. `.xl`-Dateien und
REDmod-Archive bleiben unbenannt.

## Rechte: pkexec und polkit

Der Mount braucht Root.  Standard: pkexec fragt einmal pro Deploy das
Passwort.  Der Knopf „Mount ohne Passwort einrichten" im Experte-Tab
installiert das Helferskript root-eigen nach
`/usr/local/libexec/anvil-overlay-mount` und eine polkit-Regel
(`/etc/polkit-1/rules.d/50-anvil-overlay.rules`), die genau dieses
Skript für genau diesen Nutzer freigibt.

Das Skript darf bewusst **nicht** im Home-Verzeichnis bleiben, wenn es
passwortfrei laufen soll: Ein Nutzer-eigenes Skript ließe sich
umschreiben und wäre ein offenes Root-Tor.

## Einstellungen: Tab „Experte"

- Auswahl pro Instanz: **Symlinks (Standard)** oder **Overlay
  (experimentell)** — mit kurzer Gegenüberstellung.
- Gespeichert bleibt `use_overlay` in der Instanz — die Oberfläche
  musste sonst nichts Neues lernen.
- Bei Problemen (kein Overlay im Kernel, kein pkexec) wird die Wahl
  gesperrt, aber nicht umgestellt.

## Wechsel zwischen den Wegen

- Overlay → Symlink: game_panel baut vor dem ersten Symlink-Deploy den
  Overlay-Mount ab (Manifest vorhanden → OverlayDeployer.purge()).
- Symlink → Overlay: OverlayDeployer._migrate_from_symlinks purgt den
  alten Symlink-Deploy, bevor die Schicht gebaut wird.

## Was bewusst entfallen ist

- Startwrapper + Steam-Startoption (overlay_launch.py) — der Mount
  wirkt systemweit, jeder Startweg sieht ihn.
- bwrap/User-Namespace — der Mount braucht Root statt Namespace-Tricks.
