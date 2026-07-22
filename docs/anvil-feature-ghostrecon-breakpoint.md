# Feature-Spec: Ghost Recon Breakpoint (AnvilNext / Forge)

Status: **Planung** — kein Code ohne GO von Marc.
Erstellt: 2026-07-20

## 1. Ausgangslage (verifiziert auf Platte, nicht geraten)

Beispiel-Mod: `AK 203 204 …` unter `/home/mob/Downloads/Mods/`.

- Drei Forge-Container-Ordner: `DataPC_extra_patch_01.forge/`, `DataPC_patch_01.forge/`,
  `DataPC_Resources_patch_01.forge/` — jeder voll mit nummerierten `.data`-Einträgen.
- Ein `DBContainerEntry` mit `1_-_ASR_AK12.GR_WeaponDBEntry` (Waffen-Datenbank-Definition).
- Binärformat, proprietär (Magic `33 aa fb 57 …`), keine losen/lesbaren Dateien.
- Das ist das **AnvilToolkit-Entpack-Layout**, fertig zum Reinjizieren in die echten
  `.forge`-Archive des Spiels (z. B. `DataPC.forge`, 1,1 GB).

Namensschema: `ASR`=Sturmgewehr, `AT`=Attachment, `WG`/`WI`=zwei parallele Geometrie-Sätze,
`SKEL`=Skeleton/Andockpunkte, `LOD0`=höchste Detailstufe, Zahl vorn = Slot-ID in der Forge.

### OR-Struktur der Waffe
Base (Receiver/Skeleton) + pro Slot mehrere **sich ausschließende** Varianten:
Lauf (Factory/Standard/Zenitco/Short) · Handguard (Std/Zenitco/CQC/Larue) ·
Magazin (SMALL/PMAG/LARGE) · Schaft (Factory/CoreCP/DS15/MOETR) ·
Laser (PERST-Factory/PERST-Zenitco/PEQ/NGAL) · Foregrip · Handstop · Torch · Dedal.
Der Mod liefert **alle** mit; der Ingame-Gunsmith zeigt sie zur Auswahl, pro Slot eine.

## 2. Warum das nicht in Anvils bestehende Deploy-Modelle passt

| Modell | Mechanik | Anvil heute |
|---|---|---|
| Skyrim/FO (Overlay) | lose Dateien symlinken, „last wins" | `mod_deployer.py` |
| BG3 (Container+Manifest) | ganze `.pak` ablegen + `modsettings.lsx` schreiben | `bg3_mod_handler.py` |
| **GRB (Archive-Inject)** | `.data` **in die Spiel-`.forge` reinschreiben** | **fehlt komplett** |

`mod_deployer.py` schreibt per Design **nie** echte Spieldateien (nur Symlinks in `.mods/`).
GRB braucht das Gegenteil → **eigener Injektor**, kein Symlink-Deploy.

## 3. Harte Anforderung von Marc: entfernbar OHNE das Spiel zu zerschießen

Das ist die zentrale Design-Vorgabe. Antwort = **deterministischer Rebuild statt inkrementellem Patchen**:

1. **Pristine-Backups.** Beim ersten Eingriff jede angefasste Original-Forge 1:1 sichern
   (`<instanz>/.anvil/grb_backups/`), mit SHA-256. Danach nie wieder anfassen.
2. **Apply = Rebuild aus (Backup + aktivem Mod-Set).** Nie Patch-auf-Patch. Der Zustand der
   Forge ist immer eine reine Funktion aus „Original + aktuell aktive Mods".
3. **Entfernen = Apply ohne diese Mod** → garantiert sauberer Zielzustand, keine Byte-Leichen.
4. **Standalone-Patch-Forge bevorzugen.** Falls die Engine `DataPC_extra_patch_XX.forge`
   additiv als Override lädt (SPIKE, siehe §6): Mod = eigene Zusatz-Forge → Entfernen = Datei löschen.
5. **WeaponDB-Container** (geteilt!) immer komplett neu bauen aus Backup + aktiven Einträgen —
   das ist der riskante Teil, der „das Spiel killen" kann, wenn man einzeln rauspatcht.
6. **Integritäts-Check nach Apply** + „Original wiederherstellen"-Button (Backups zurückkopieren
   → Spiel garantiert vanilla). Dieser Button muss IMMER funktionieren, auch nach Absturz.

## 4. Bausteine & Aufwand (T-Shirt-Größen)

| # | Baustein | Größe | Risiko |
|---|---|---|---|
| 0 | **Spike: Forge injizieren + entfernen + Spielstart beweisen** (§6) | **S–M** | **entscheidet alles** |
| 1 | Game-Plugin `game_ghostreconbreakpoint.py` (Pfade, Detect, Scan) | S | niedrig |
| 2 | **Forge read/write-Engine** (`.data` extrahieren + Archiv neu packen, Offsets/Kompression) | **XL** | **hoch** |
| 3 | WeaponDB-Container merge/rebuild (Einträge rein/raus, ID-Kollisionen) | L | hoch |
| 4 | Injektor + Backup/Rollback/Integritäts-System (§3) | M–L | mittel |
| 5 | Konflikt-Logik (zwei Mods → selbe Forge/DB → mergen) | M | mittel |
| 6 | Waffen-Baum-UI (OR-Slots anzeigen) — nice-to-have, nicht install-kritisch | M | niedrig |
| 7 | i18n (6 Sprachen), Settings, Plugin-Registrierung, Instanz-Config | S | niedrig |

### Grobe Einschätzung
- **Hülle allein** (Plugin + Bibliothek/Scan + Baum-UI + Backup-Gerüst, Bausteine 1/4/6/7):
  überschaubar, ca. **1–2 Wochen**.
- **Der Elefant** ist Baustein 2 (+3): die Forge-Schreib-Engine für ein proprietäres Binärformat.
  - Nativ in Python nachbauen: realistisch **viele Wochen** und ehrlich **ergebnisoffen**
    (v. a. die Kompression der `.data`-Einträge — Schreibpfad ist evtl. nicht voll geknackt).
  - AnvilToolkit ist **Windows/.NET (WPF-GUI)** — keine Linux-CLI. Delegation nur via
    Wine/Proton/mono, headless unklar → Machbarkeit ist selbst ein Rechercheposten.
- **Fazit Größe:** Klein, WENN nur Bibliothek/UI. Groß bis unbegrenzt WEGEN des Packers —
  und der Packer ist das ganze Spiel. Ohne funktionierenden Schreib-/Entfern-Pfad ist der Rest wertlos.

## 5. Umsetzungs-Phasen

- **Phase 0 — De-Risk-Spike (PFLICHT zuerst).** Manuell auf Marcs Rechner den kompletten Loop
  beweisen: AK-Mod in eine Kopie der Spiel-Forge injizieren → GRB starten → Waffe da? →
  entfernen → GRB startet wieder vanilla? Ergebnis: geht das auf Linux überhaupt scriptbar?
  **Gate:** Nur wenn dieser Loop reproduzierbar ist, lohnt sich der Rest.
- **Phase 1 — Plugin + Bibliothek.** Detect, Scan, Waffen-Baum anzeigen. Noch kein Schreiben.
- **Phase 2 — Injektor + Backup/Rollback.** Nach dem in Phase 0 bewiesenen Verfahren.
- **Phase 3 — Konflikte + WeaponDB-Merge.** Mehrere Mods gleichzeitig.
- **Phase 4 — Feinschliff, i18n, Diagnose-Integration.**

## 6. Offene Fragen (SPIKE, müssen VOR Baustein 2 geklärt sein)

1. Lädt die GRB-Engine zusätzliche `DataPC_extra_patch_XX.forge` **additiv** (dann sichere
   Datei-Löschung möglich) — oder muss zwingend in bestehende Forges gemergt werden?
2. Ist der Forge-**Schreibpfad** (inkl. Kompression) auf Linux reproduzierbar — nativ oder Tool?
3. Braucht jede neue Waffe zwingend einen Eintrag im geteilten `GR_WeaponDBEntry`-Container?
   (Vermutlich ja → Baustein 3 ist Pflicht, nicht optional.)
4. GRB läuft via Proton — wo genau liegen die echten Forges pro Store (Steam/Ubisoft/Epic)?
5. Rechtliches/Distribution: dürfen wir ein Fremd-Tool bündeln, oder nur „vorhanden voraussetzen"?

## 7. Akzeptanz-Checkliste

- [ ] Phase-0-Spike beweist: injizieren → starten → Waffe funktioniert.
- [ ] Phase-0-Spike beweist: entfernen → Spiel startet weiter, vanilla-identisch (SHA-256 == Backup).
- [ ] `game_ghostreconbreakpoint.py` erkennt Installation + Store, liest Pfade aus Instanz-Config.
- [ ] Bibliothek zeigt den Waffen-Baum mit OR-Slots.
- [ ] Apply ist idempotent (2× apply == 1× apply, gleiche Bytes).
- [ ] „Mod entfernen" hinterlässt keine Byte-Leichen (Rebuild-Verifikation).
- [ ] „Original wiederherstellen" stellt garantiert vanilla her — auch nach Absturz mitten im Apply.
- [ ] Integritäts-Check nach jedem Apply.
- [ ] Zwei sich überschneidende Mods werden korrekt gemergt (kein Überschreiben).
- [ ] tr()-Keys in allen 6 Locale-Dateien.
- [ ] `./restart.sh` startet fehlerfrei.
- [ ] Keine hardcoded Pfade, kein `setStyleSheet()`, keine MO2-Erwähnungen.

## 8. Empfehlung

Erst **Phase 0** freigeben (reiner Spike, wenig Aufwand, kein Anvil-Code). Er beantwortet die
einzige Frage, die zählt: Ist das Injizieren+Entfernen auf Linux überhaupt sicher machbar?
Fällt der Spike negativ aus, sparen wir uns die XL-Investition. Fällt er positiv aus, ist der
Rest normales Plugin-Handwerk auf der bewährten Architektur.
