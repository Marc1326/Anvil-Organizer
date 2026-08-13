# Overlay-Deploy: Mount direkt auf den Spielordner

Stand: 13.08.2026 (Abend) — ersetzt den Startwrapper-Ansatz.

## Erkenntnisse des Tages (Live-Tests mit Cyberpunk 2077)

| Versuch | Ergebnis |
|---|---|
| Leeres Overlay auf den Spielordner, normaler Steam-Start | läuft |
| Overlay mit Frameworks (winmm/RED4ext) | läuft, RED4ext lädt |
| + Archive (321) | läuft, Mods sichtbar |
| + falsch geroutete Dateien (r6/config/settings-Override, Root-Müll) | Spiel beendet sich still |
| Sauber geroutete Schicht aus den echten Mods | **läuft, Mods laden** |

Die Abstürze kamen nie vom Overlay-Mechanismus, sondern von einer
Test-Schicht, die Dateien an Orte legte, wo das Spiel sie nicht
erwartet.  Das produktive Staging (overlay_staging.py) nutzt dieselben
Routen wie der Symlink-Deployer — der Vergleichstest
test_overlay_matches_symlink.py haelt beide Wege deckungsgleich.

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
- `anvil/core/overlay_staging.py` — unverändert, baut die Schicht mit
  den echten Deploy-Routen.

## Rechte: pkexec und polkit

Der Mount braucht Root.  Standard: pkexec fragt einmal pro Deploy das
Passwort.  Der Knopf „Mount ohne Passwort einrichten" im Experte-Tab
installiert das Helferskript root-eigen nach
`/usr/local/libexec/anvil-overlay-mount` und eine polkit-Regel
(`/etc/polkit-1/rules.d/50-anvil-overlay.rules`), die genau dieses
Skript für genau diesen Nutzer freigibt.

Das Skript darf bewusst **nicht** im Home-Verzeichnis bleiben, wenn es
passwortfrei laufen soll: Ein Nutzer-eigenes Skript liesse sich
umschreiben und waere ein offenes Root-Tor.

## Einstellungen: Tab „Experte"

- Auswahl pro Instanz: **Symlinks (Standard)** oder **Overlay
  (experimentell)** — mit kurzer Gegenüberstellung.
- Gespeichert bleibt `use_overlay` in der Instanz — die Oberflaeche
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
