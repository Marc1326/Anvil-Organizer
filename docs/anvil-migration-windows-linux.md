# Anvil Organizer — Migration Windows zu Linux

Erstellt: 2026-03-27

---

## Ziel

Den Wechsel von Windows (MO2/Vortex) zu Linux (Anvil/Amethyst) so einfach wie moeglich machen. Der User soll seine Mod-Setups nicht verlieren und nicht alles nochmal von Nexus runterladen muessen.

---

## Methode 1: Vollstaendige Migration (Externe Festplatte / USB-Stick)

### Schritt 1 — Windows-Tool (Portable .exe)

Ein kleines portables Tool das auf Windows laeuft und:

1. **MO2-Instanzen automatisch findet** (Registry, Standard-Pfade, AppData)
2. **Vortex-Daten findet** (DuckDB in AppData, Staging-Ordner)
3. Dem User zeigt welche Spiele/Instanzen gefunden wurden
4. **Alles auf eine externe Festplatte / USB-Stick kopiert** in einem definierten Format:

```
/ANVIL_MIGRATION/
  manifest.json          ← Welche Spiele, welcher Quell-Manager, Zeitstempel
  skyrim-se/
    modlist.txt           ← Load Order
    active_mods.json      ← Aktivierungsstatus
    categories.json       ← Kategorien (falls vorhanden)
    meta/                 ← meta.ini pro Mod (Nexus-IDs, Versionen)
      mod1.ini
      mod2.ini
    mods/                 ← Die eigentlichen Mod-Dateien (optional, gross!)
      mod1/
      mod2/
    plugins.txt           ← Plugin Load Order (Bethesda)
    downloads/            ← Original-Archive (optional)
  cyberpunk-2077/
    ...
```

### Schritt 2 — Linux-Tool (.AppImage)

Ein Anvil-Migrations-Tool (.AppImage) das auf Linux:

1. Externe Festplatte / USB-Stick erkennt
2. `manifest.json` liest und zeigt was vorhanden ist
3. Pro Spiel/Instanz importiert:
   - Erstellt Anvil-Instanz (`.anvil.ini`, Ordnerstruktur)
   - Kopiert Mod-Dateien nach `.mods/`
   - Konvertiert modlist.txt ins Anvil-Format
   - Uebernimmt meta.ini Dateien (Nexus-IDs, Versionen)
   - Importiert Kategorien
   - Setzt plugins.txt
4. **Vortex-Daten → Amethyst-Mod-Manager Format** (experimentell)
   - Amethyst: https://github.com/ChrisDKN/Amethyst-Mod-Manager
   - MUSS NOCH GEPRUEFT WERDEN ob das Format kompatibel ist!

### Vorteile
- Alle Mods, Load Order, Kategorien, Nexus-IDs werden uebernommen
- User muss nichts nochmal runterladen
- Funktioniert auch offline

### Nachteile
- Braucht viel Speicherplatz (Mods koennen 50-200 GB gross sein)
- USB-Stick ist langsam bei grossen Setups
- Windows-Tool muss entwickelt und getestet werden

---

## Methode 2: Leichtgewichtige Migration (Nur Metadaten)

### Schritt 1 — Windows oder manuell

Nur die wichtigsten Daten werden exportiert/kopiert:

- `modlist.txt` (Load Order)
- `meta.ini` Dateien (Nexus-IDs, Mod-Namen, Versionen)
- `plugins.txt` (Plugin Load Order)
- `categories.json` (falls vorhanden)

Das sind nur wenige KB — passt auf einen USB-Stick oder kann per E-Mail/Cloud geschickt werden.

### Schritt 2 — Anvil Import

Anvil liest die Metadaten und:

1. Erstellt die Instanz mit korrekter Ordnerstruktur
2. Erstellt leere Mod-Ordner mit meta.ini (Nexus-IDs vorhanden)
3. Zeigt eine **"Fehlende Mods" Liste** mit direkten Nexus-Links
4. User kann Mods einzeln oder per NXM-Handler runterladen
5. Mods landen automatisch in der richtigen Reihenfolge

### Vorteile
- Extrem schnell (nur wenige KB kopieren)
- Kein Windows-Tool noetig (User kopiert Dateien manuell)
- Funktioniert auch wenn der User die Mod-Dateien nicht mehr hat

### Nachteile
- Alle Mods muessen nochmal runtergeladen werden
- Bei grossen Setups (500+ Mods) dauert das Stunden
- Manche Mods sind von Nexus entfernt worden (Hidden/Deleted)

---

## Methode 3: Netzwerk-Migration (LAN)

### Konzept

1. **Windows-Tool** startet einen lokalen HTTP-Server
2. **Anvil auf Linux** verbindet sich per LAN (gleches Netzwerk)
3. Daten werden direkt ueber das Netzwerk uebertragen
4. Schneller als USB bei grossen Mod-Setups (Gigabit LAN = ~100 MB/s)

### Vorteile
- Kein USB-Stick / externe Festplatte noetig
- Schneller als USB 2.0/3.0 bei vielen kleinen Dateien
- Beide Rechner koennen gleichzeitig laufen

### Nachteile
- Beide Rechner muessen gleichzeitig an sein
- Netzwerk-Konfiguration kann fuer Einsteiger schwierig sein (Firewall etc.)
- Aufwaendiger zu entwickeln

---

## Offene Fragen

1. **Amethyst-Mod-Manager Kompatibilitaet** — Kann Vortex-Format in Amethyst importiert werden? Repo pruefen: https://github.com/ChrisDKN/Amethyst-Mod-Manager
2. **Vortex DuckDB auslesen** — Wie komplex ist das Format? Gibt es Community-Tools (Vortex→MO2) die wir wiederverwenden koennen?
3. **MO2 portable vs installed** — MO2 kann portable oder installiert sein, beide Varianten muessen gefunden werden
4. **Mod-Dateien Deduplizierung** — Wenn der User das gleiche Spiel auf beiden Systemen hat, koennte man nur fehlende Mods kopieren
5. **Steam Workshop Mods** — Werden die ueberhaupt von MO2/Vortex verwaltet? Oder separat?

---

## Priorisierung

| Methode | Aufwand | Nutzen | Prioritaet |
|---------|---------|--------|------------|
| Methode 2 (Metadaten) | Klein | Hoch | **1 — Zuerst** |
| Methode 1 (Vollstaendig) | Gross | Sehr hoch | **2 — Danach** |
| Methode 3 (Netzwerk) | Mittel | Mittel | **3 — Spaeter** |

Empfehlung: Mit Methode 2 starten (geringer Aufwand, sofort nutzbar), dann Methode 1 als "Premium-Migration" nachliefern.
