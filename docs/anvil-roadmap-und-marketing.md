# Anvil Organizer — Roadmap & Marketing

Erstellt: 2026-03-26

---

## Teil 1: Features die noch gebaut werden muessen

### HOCH — Wichtig fuer User

| # | Feature | Beschreibung | Status |
|---|---------|-------------|--------|
| 1 | **LOOT-Integration** | Automatische Plugin-Sortierung fuer Bethesda-Spiele (Skyrim, Fallout, Starfield). Ohne LOOT muss der User die Load-Order manuell sortieren — das macht niemand gern und fuehrt zu Crashes. | Nicht vorhanden (UI-Placeholder disabled) |
| 2 | **Nexus Collections Import** | Komplette Mod-Setups mit 1 Klick installieren. Nexus Collections sind kuratierte Modlisten die andere User teilen. Grosses Feature fuer Einsteiger. | Nicht vorhanden |
| 3 | **Locked Mods** | Mods mit `*` Prefix in modlist.txt die nicht deaktiviert werden koennen. Verhindert dass User versehentlich SKSE64 oder andere kritische Frameworks ausschalten. | Nicht vorhanden |
| 4 | **Mod-Update-Benachrichtigungen** | Automatischer Check ueber Nexus-API ob neuere Versionen verfuegbar sind. meta.ini hat bereits Version-Felder, aber es gibt keinen Auto-Check. | Teilweise (Daten in meta.ini, kein Auto-Check) |

### MITTEL — Nice to have

| # | Feature | Beschreibung | Status |
|---|---------|-------------|--------|
| 5 | **Root Folder Builder** | Mods die ins Game-Root muessen (ENB, ReShade, DLL-Replacer) automatisch korrekt deployen. Aktuell muessen solche Mods manuell installiert werden. | Nicht vorhanden |
| 6 | **CLI-Interface** | Kommandozeilen-Modus fuer Batch-Automation, Headless-Server, Steam Deck ohne Desktop-Modus. z.B. `anvil deploy --instance "Skyrim SE"` | Nicht vorhanden |
| 7 | **Bundle/Group Mods** | Zusammenhaengende Mods gruppieren (z.B. "Texture Pack + Patch + Compatibility"). Visuelle Gruppierung in der Modliste. | Nicht vorhanden |
| 8 | **Custom Deploy Paths pro Separator** | Verschiedene Mod-Gruppen in verschiedene Zielordner deployen. Aktuell nur globale Pfade + Multi-Folder-Routes. | Nicht vorhanden |
| 9 | **FOMOD Selection Memory** | Bei Reinstall eines Mods die gleichen FOMOD-Optionen automatisch wiederherstellen statt den Wizard nochmal durchlaufen zu muessen. | Nicht vorhanden |
| 10 | **Nativer Script Merger (Witcher 3)** | Erkennt Script-Konflikte zwischen Witcher-3-Mods und merged sie automatisch. Ersetzt das externe Tool SM-FAE. | Geplant (Issue #61, QA-Review abgeschlossen) |
| 11 | **modindex.bin Caching** | Dateilisten aller Mods cachen fuer schnelleren Filemap-Rebuild. Wichtig bei grossen Mod-Setups (100+ Mods). | Nicht vorhanden |
| 12 | **Collection/Modpack Export+Import** | Eigene Mod-Setups als Paket exportieren und teilen. Andere User koennen sie importieren. | Nicht vorhanden |

### NIEDRIG — Extras

| # | Feature | Beschreibung | Status |
|---|---------|-------------|--------|
| 13 | **ReShade Wizard** | Gefuehrte Installation von ReShade mit Preset-Auswahl. | Nicht vorhanden |
| 14 | **BSA/BA2 Browser** | Archiv-Inhalte ansehen ohne zu entpacken. Anvil kann BA2 packen, aber nicht browsen. | Nicht vorhanden |
| 15 | **Multi-threaded Deployment** | Parallele Datei-Operationen beim Deploy. Aktuell sequentiell, aber Symlinks sind eh schnell. | Nicht vorhanden (niedrige Prioritaet) |
| 16 | **INI-Editor (erweitert)** | Vorhanden als einfacher Text-Editor, koennte aber Syntax-Highlighting und bekannte Keys mit Beschreibungen anbieten. | Basis vorhanden |

### Migration-Tool (Zukunftsprojekt)

| # | Feature | Beschreibung |
|---|---------|-------------|
| 17 | **MO2 → Anvil Import** | Windows MO2-Instanzen nach Anvil importieren. Formate sind fast identisch (modlist.txt, meta.ini, Staging-Ordner). Hybrid-Methode: Metadaten immer, Mod-Dateien optional. |
| 18 | **Vortex → Anvil Import** | Schwieriger wegen DuckDB-Datenbank. Eventuell ueber bestehende Vortex→MO2 Community-Tools als Zwischenschritt. |
| 19 | **Netzwerk-Migration** | Windows-Tool startet lokalen Server, Linux-Tool verbindet sich per LAN. Schneller als USB. |

---

## Teil 2: Marketing — Anvil bekannter machen

### Erledigt

| # | Massnahme | Status |
|---|-----------|--------|
| 1 | GitHub Description gesetzt | Erledigt (2026-03-26) |
| 2 | GitHub Topics/Tags (10 Stueck) | Erledigt (2026-03-26) |
| 3 | GitHub Homepage-Link zur Website | Erledigt (2026-03-26) |
| 4 | Website erstellt (GitHub Pages) | Erledigt |
| 5 | Linux YouTuber angeschrieben | Laufend |
| 6 | Domain anvil-organizer.org registriert | Warte auf Freischaltung |
| 7 | NexusMods Seite (Cyberpunk 2077) | Erledigt |
| 8 | Social Preview Image | Erledigt (2026-03-26) |
| 9 | Dynamische Badges in README | Erledigt (2026-03-26) |
| 10 | Feature-Vergleichstabelle in README | Erledigt (2026-03-26) |
| 11 | Issue Templates (.github/ISSUE_TEMPLATE/) | Erledigt (2026-03-26) |
| 12 | CONTRIBUTING.md | Erledigt (2026-03-26) |
| 13 | CODE_OF_CONDUCT.md | Erledigt (2026-03-26) |
| 14 | "good first issue" Labels | Erledigt (2026-03-26) |
| 15 | Issues aufgeraeumt (Labels gesetzt) | Erledigt (2026-03-26) |

### Reddit-Kampagne (groesster Einzeleffekt)

| # | Subreddit | Mitglieder | Warum |
|---|-----------|-----------|-------|
| 16 | **r/linux_gaming** | ~850k | DER Ort fuer Linux-Gaming-Tools. Amethyst hat hier wahrscheinlich seine Stars geholt. |
| 17 | **r/SteamDeck** | ~700k | Steam Deck User brauchen native Linux-Tools. |
| 18 | **r/skyrimmods** | ~350k | Proton Shims fuer SKSE64 sind einzigartig — das interessiert hier jeden. |
| 19 | **r/fo4mods** | ~100k | F4SE Proton Shim. |
| 20 | **r/cyberpunkgame** | ~800k | REDmod + CET Support. |
| 21 | **r/BaldursGate3** | ~1.5M | Auto-Deploy + modsettings.lsx. |

**Post-Tipps:**
- Titel mit konkretem Nutzen: "I built a native Linux mod manager with SKSE64 Proton support — no more Wine workarounds"
- GIF/Video > Screenshots > nur Text
- Feature-Vergleich im Post einbetten
- "Open Source, GPL-3.0" erwaehnen
- Link zur Website + GitHub
- Am Wochenende posten (mehr Traffic)

### Plattformen

| # | Plattform | Aufwand | Effekt | Beschreibung |
|---|-----------|---------|--------|-------------|
| 22 | **AlternativeTo** | 10 Min | HOCH | Als Alternative zu MO2 + Vortex eintragen. Wird oft bei Google gefunden. |
| 23 | **NexusMods breiter listen** | 30 Min | HOCH | Aktuell nur unter Cyberpunk. Auch unter Skyrim SE, Fallout 4, Starfield, Witcher 3 listen. Oder unter site-weite "Modding Tools" Kategorie. |
| 24 | **Linux Gaming Wiki** | 15 Min | MITTEL | linux-gaming.kwindu.eu — Referenz fuer Linux-Gamer. |
| 25 | **ProtonDB Kommentare** | 20 Min | MITTEL | Bei Skyrim SE, FO4, Starfield, Cyberpunk: "Use Anvil Organizer for native SKSE64/F4SE support". |
| 26 | **AUR-Paket** (PKGBUILD) | 1 Std | HOCH | Arch/CachyOS/Manjaro User installieren bevorzugt aus dem AUR. |
| 27 | **Flathub Submission** | 2-3 Std | SEHR HOCH | Universelle Linux-Distribution. Jede Distro kann Flatpaks installieren. |

### Content-Erstellung

| # | Massnahme | Aufwand | Effekt | Beschreibung |
|---|-----------|---------|--------|-------------|
| 28 | **Demo-GIF** (15 Sek) | 1 Std | HOCH | In README einbetten. Zeigt Drag&Drop, Deploy, Game-Launch. Bewegtbild ueberzeugt mehr als Screenshots. |
| 29 | **Mehr Screenshots** im Website-Carousel | 20 Min | MITTEL | Cyberpunk, BG3, Instance Manager, Settings dazu. Aktuell nur 2 Bilder. |
| 30 | **Steam Deck Tutorial** | 1 Std | HOCH | Schritt-fuer-Schritt Anleitung: Anvil auf Steam Deck installieren. Blog-Post oder Wiki-Seite. |
| 31 | **YouTube Demo-Video** (2-3 Min) | 2 Std | HOCH | Eigenes Video oder Zusammenarbeit mit Linux-YouTubern. |

### Domain-Umstellung (wenn anvil-organizer.org aktiv)

| # | Schritt | Beschreibung |
|---|---------|-------------|
| 32 | CNAME-Record setzen | Domain auf GitHub Pages zeigen lassen |
| 33 | GitHub Homepage-Link aendern | Von github.io auf anvil-organizer.org |
| 34 | Alle externen Links aktualisieren | NexusMods, Reddit-Posts, AlternativeTo |
| 35 | HTTPS erzwingen | GitHub Pages > Enforce HTTPS |

---

## Der USP (Unique Selling Point)

Was Anvil hat und KEIN anderer Linux Mod Manager:

> **Nativer Proton Script Extender Support — SKSE64, F4SE und SFSE funktionieren out-of-the-box ueber Proxy-DLL-Injection. Kein Wine-Workaround, kein manuelles Kopieren.**

Das ist der Killer-Feature fuer jeden Skyrim/Fallout/Starfield-Spieler auf Linux. DAS muss in jeden Reddit-Titel, jede Beschreibung, jede Vergleichstabelle.

---

## Priorisierte Reihenfolge

1. Social Preview Image + Badges + Vergleichstabelle (README)
2. Domain-Umstellung wenn freigeschaltet
3. Reddit-Post auf r/linux_gaming
4. AlternativeTo + NexusMods breiter listen
5. AUR-Paket
6. LOOT-Integration (Feature)
7. Locked Mods (Feature)
8. Flathub
9. Nexus Collections (Feature)
10. Migration-Tool (Zukunft)
