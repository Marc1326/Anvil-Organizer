# Changelog

## [Unveröffentlicht]

### Fixes
- **Mods mit Ordnern in gemischter Schreibweise werden nur noch halb geladen — das ist behoben.** Unter Windows sind `meshes` und `Meshes` derselbe Ordner, unter Linux zwei verschiedene. Brachte eine Mod beide Schreibweisen mit oder schrieben zwei Mods denselben Ordner unterschiedlich, lagen im Spiel zwei Ordner nebeneinander und die Hälfte der Dateien blieb unsichtbar. Anvil legt sie beim Ausrollen jetzt zusammen: Es zählt, was im Spielordner bereits liegt, sonst die Schreibweise der zuerst ausgerollten Mod. Das gilt für beide Wege, Symlink wie OverlayFS, und für jedes Spiel. In den Mod-Ordnern selbst wird nichts verändert — auch bereits installierte Mods sind damit repariert, ohne sie neu installieren zu müssen.
- **Bei FOMOD-Installern entschied nicht mehr die getroffene Auswahl.** Lieferten zwei Optionen dieselbe Datei in unterschiedlicher Schreibweise, landeten beide im Mod, und welche im Spiel galt, hing vom Zufall ab. Jetzt gewinnt wieder die Option mit der höheren Priorität — also das, was im Installationsdialog ausgewählt wurde.
- Ein Mod-Archiv mit `data/` statt `Data/` landete unter `Data/data/` und war damit wirkungslos. Betraf jedes Spiel mit eigenem Datenordner, unter anderem Skyrim, Fallout 4, Starfield, STALKER 2, Witcher 3 und Stellar Blade.
- **Die Konfliktanzeige übersah Überdeckungen**, wenn zwei Mods denselben Pfad unterschiedlich schrieben — sie meldete null Konflikte, obwohl eine Datei die andere verdrängte.
- Hinweis zu den beiden Punkten oben: Bringt eine Mod eine Datei mit, die im Spielordner schon in anderer Schreibweise als **echte Datei** liegt, wird sie jetzt übersprungen und als solche gemeldet, statt still in einem zweiten Ordner zu landen. Gefunden hätte das Spiel sie dort ohnehin nicht — nach dem Update taucht sie nur zum ersten Mal in der Übersprungen-Liste auf. Ein bereits gespaltener Spielordner wird beim nächsten vollständigen Aufräumen zusammengeführt.
- **OverlayFS funktioniert jetzt auch, wenn Anvil als Flatpak läuft.** Mount, Unmount und die polkit-Einrichtung werden über `flatpak-spawn` auf dem Host ausgeführt; die eingerichtete Passwort-frei-Regel greift dort genauso.

## [1.8.0] — 2026-08-14

### Neu
- **Mods lassen sich wahlweise per OverlayFS einbinden statt per Symlink** (Einstellungen → Experte). Das Overlay wird direkt über den Spielordner gelegt: Die Moddateien bleiben komplett außerhalb, die Originaldateien werden nie angerührt, und Steam-Updates oder -Reparaturen sehen ein sauberes Spielverzeichnis, sobald das Overlay abgehängt ist. Auf Wunsch richtet Anvil einmalig eine polkit-Regel ein, danach läuft das Einhängen ohne Passwortabfrage. Voraussetzung: Spielordner auf ext4, btrfs oder xfs. Ausführlich dokumentiert im Wiki — in allen sieben Sprachen.
- **Charakter-Presets haben einen eigenen Bereich** unter der Mod-Liste, so wie die Frameworks. Bei Cyberpunk heißt er „ACU-Presets"; Spiele ohne Presets zeigen ihn gar nicht. Ob etwas ein Preset ist, entscheidet der Inhalt und nicht der Trenner: Wer neben der Preset-Datei noch ein Archiv mitbringt, greift ins Spiel ein und bleibt eine gewöhnliche Mod.

### Änderungen
- Die Plugins für **Windrose** und den Windrose-Server sind entfernt. Für das Spiel gibt es keine Mods, damit war auch nichts zu verwalten.

### Fixes
- **Beim Umsortieren per Drag & Drop rutschte alles ans Listenende, was gerade nicht angezeigt wurde** — gesperrte Frameworks und Presets. Sie standen danach unter dem letzten Trenner der Liste statt an ihrem Platz. Ausgeblendete Einträge behalten ihre Position jetzt.
- Ein neuer Trenner landete an der falschen Stelle, sobald oberhalb der Auswahl ausgeblendete Einträge lagen. Die Position wird jetzt über den Ordnernamen bestimmt statt über die Zeilennummer.
- **Mods konnten stillschweigend aus dem Spiel verschwinden.** Anvil merkt sich die Dateiliste jeder Mod, prüfte auf Änderungen aber nur den obersten Ordner. Wurde eine Datei eine Ebene tiefer umbenannt, hinzugefügt oder gelöscht, galt die Mod als unverändert — ausgerollt wurde die alte, nicht mehr vorhandene Datei. Die Mod fehlte im Spiel, im Log stand trotzdem null Fehler. Geprüft wird jetzt der ganze Ordnerbaum.
- Landet eine Mod nicht vollständig im Spiel, sagt Anvil das über die Benachrichtigungen. Der Spielstart wird dadurch nicht verhindert.
- Ein fehlender Mod-Ordner — etwa weil ein Laufwerk nicht eingehängt ist — wird gemeldet statt übersprungen.
- Eine beschädigte `.modindex.json` ließ die Konfliktanzeige abstürzen und konnte den Programmstart verhindern. Unbrauchbare Einträge werden jetzt beim Einlesen verworfen und neu eingelesen.
- **Anvil startete nicht mehr**, sobald es fremde Dateien im Spielordner fand. Eine Meldung mit unbekannter Dringlichkeitsstufe riss das Fenster mitten im Aufbau um. Betroffen war, wer Anvil bei laufendem Spiel geschlossen hat.

## [1.7.0] — 2026-08-06

### Neu
- **Stellar Blade wird unterstützt.** Das Spiel kennt vier Mod-Arten mit vier Zielen — gewöhnliche Pak-Mods, Logic-Mods, Filmsequenzen und Beschreibungen für das Custom Nanosuit System. Anvil verteilt sie jetzt einzeln statt alles in einen Ordner zu legen, wo drei der vier Arten wirkungslos bleiben.
- Blueprint-Mods sind am Dateinamen nicht zu erkennen. Anvil liest deshalb den Mount-Point aus der `.utoc`; `.pak` und `.ucas` folgen ihrem Inhaltsverzeichnis.
- UE4SS und das Custom Nanosuit System werden als Frameworks erkannt und ins Spielverzeichnis installiert.

### Änderungen
- **Mods werden erst beim Spielstart ausgerollt** und nach dem Beenden wieder entfernt. Vorher lagen sie dauerhaft im Spielverzeichnis, was Updates und Reparaturen über Steam gestört hat.
- Solange das Spiel läuft, räumt Anvil nicht mehr auf.

### Fixes
- **Downloads ohne Dateiendung** ließen sich nicht in die Mod-Liste ziehen. Nexus liefert über sein CDN Dateien aus, die nach ihrer UUID heißen; drei Stellen haben unabhängig voneinander nur die Endung geprüft und sie still verworfen. Jetzt entscheidet der Dateikopf.
- Bei denselben Dateien schlug Anvil Namen wie `c` oder `fbcf` vor, die im Install-Fenster wie ein leeres Feld aussehen. Der Name kommt jetzt aus der `.meta`.
- Frameworks, die ihre Zielstruktur selbst mitbringen, wurden unvollständig installiert — alles neben dem Zweig mit der Musterdatei fiel weg.
- `modindex` hat Mod-Ordner übersprungen, die als Verknüpfung angelegt waren.
- Meldungen zu den Proton-DLL-Overrides zeigten Platzhalter statt Werten, wodurch Schreibfehler an `user.reg` unauffindbar blieben.
- Cyberpunk: *Every Animation Redone* gilt wieder als gewöhnliche Mod.

## [1.0.8] — 2026-03-14

### Fixes
- **Multi-Mod DnD aus Download-Tab:** Beim Ziehen von mehreren Mods gleichzeitig (z.B. 5 Stück) landeten ab dem 3. Mod alle im falschen Separator. Ursache: `insert_at` verwies auf veraltete Source-Model-Zeilen. Fix: Jeder Mod wird jetzt direkt nach dem vorherigen eingefügt.
- **DnD aus Download-Tab (Single):** Mods landeten im falschen Separator, weil Direct-Install Mods den Index verschoben haben. Position wird jetzt korrekt über den Ordnernamen aufgelöst.
- **Mod-Löschung:** Gelöschte Mods wurden nicht aus der globalen modlist.txt entfernt — tote Einträge sammelten sich an. Jetzt wird der Eintrag korrekt aus `.profiles/modlist.txt` entfernt.
- **Index-Mismatch bei Context-Menu:** 15+ Funktionen (Löschen, Umbenennen, Aktivieren, Backup, Nexus, Kategorien) griffen bei DirectInstall-Mods auf den falschen Mod zu. Alle verwenden jetzt sicheren Name-Lookup statt Index-Zugriff.
- **Suche findet Mods in eingeklappten Separatoren:** Wenn ein Separator eingeklappt war, wurden seine Mods auch von der Suche ignoriert. Jetzt werden bei aktiver Suche/Filter alle Mods durchsucht — unabhängig vom Separator-Status.

## [1.0.7] — 2026-03-13

### Fixes
- **Kritisch: modlist.txt Migration verschiebt Mods bei jedem Start** — `migrate_modlist_order()` hat bei jedem Anvil-Start die Mod-Reihenfolge verschoben, wenn der Header noch v1 war aber die Daten bereits im v2-Format vorlagen. Jede Mod-Gruppe rutschte um einen Separator nach unten. Die Reordering-Logik wurde komplett entfernt — die Migration aktualisiert jetzt nur noch den Header.
- Legacy `write_modlist()` schreibt jetzt ebenfalls den v2-Header, damit keine Funktion mehr den alten v1-Header erzeugt.

## [1.0.6] — 2026-03-09

### Fixes
- Separator verschwindet bei Multi-Select DnD: Wenn mehrere Mods gleichzeitig in einen Separator gezogen wurden, verschwand der Separator. Gefixt.
- Mods verschwinden nach Neustart: Neu installierte Mods waren nach einem Neustart nicht mehr sichtbar (falsches Name-Matching). Gefixt.
- Mod-Toggle und Reorder: Checkbox-Toggle und Drag & Drop nutzen jetzt den eindeutigen Ordnernamen statt Display-Namen (verhindert Datenverlust bei doppelten Namen).

### Visuelles
- Ordner-Icon bei Separatoren in der Kategorie-Spalte entfernt
- Ja/Nein-Icons in Bestätigungsdialogen entfernt (Paper Dark & 1809 Dark Mode Theme)

### modlist.txt Format-Korrektur
- Die globale modlist.txt wurde bisher invertiert geschrieben (Separator stand nach seinen Mods statt davor). Format korrigiert und automatische Migration beim ersten Start.
- Bestehende Dateien werden gesichert (modlist.txt.bak) bevor die Migration durchgeführt wird.

## [1.0.5] — 2026-03-08

### Fixes
- Separator-Drag & Drop: Trenner lässt sich wieder per DnD verschieben ohne sich zu schließen
- Separator-Klick: Gesamte Zeile öffnet/schließt Trenner (nicht nur Dreieck)
- Mehrfachauswahl DnD: Mehrere Mods gleichzeitig per Drag & Drop verschieben
- Kontextmenü "In Trenner verschieben": Rechtsklick → ausgewählte Mods in Trenner verschieben
- Kategorie-Spalte: Kein Ordner-Icon mehr bei Trennern
- Dialoge: Keine Icons mehr in Ja/Nein/Ok Buttons

## [1.0.0] — 2026-02-xx
- Erste öffentliche Version
