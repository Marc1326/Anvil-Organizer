# Feature-Spec: Witcher 3 — Menu Filelist Updater (#35)

**Status:** Geplant
**Datum:** 2026-06-28
**Betrifft:** The Witcher 3 (Next-Gen / 4.0+)
**Ersetzt:** den #35-Teil der kombinierten Spec `anvil-feature-witcher3-script-merger.md`
(Abschnitte 2b + 3b dort gingen vom **falschen** Filelist-Format aus — siehe §3).

---

## 1. Problem / Ziel

GitHub-Issue #35 (Marc1326, Label `enhancement`, `witcher3`):

> Seit dem Witcher-3-Next-Gen-Patch (4.0) müssen Mod-Menüs (XML-Dateien) in
> `dx11filelist.txt` und `dx12filelist.txt` registriert werden, damit ihre
> In-Game-Optionen erscheinen. Anvil soll deployte Mods nach Menü-XMLs scannen und die
> Filelists beim Deploy automatisch aktualisieren bzw. beim Purge zurücksetzen.

Referenz-Tool: Menu Filelist Updater (nexusmods.com/witcher3/mods/7171), Original-Quelle
`github.com/Aelto/tw3-menufilelist-updater`.

**Ziel:** Menü-Mods funktionieren in Anvil ohne externes Windows-Tool — vollständig
nativ in Python, automatisch beim Deploy/Purge.

---

## 2. VERIFIZIERTES Format (am realen Referenz-Code geprüft)

Eine echte Witcher-3-Installation war auf dem System nicht greifbar (Instanz-Pfad
`/mnt/gamingS/...` existiert nicht mehr). **Aber** der fremde Linux-Mod-Manager
**Amethyst** hat dieses Feature bereits nativ in Python implementiert:
`Amethyst-Mod-Manager-1.2.7/src/Utils/tw3_filelist.py` → `update_menu_filelists()`.
Das ist eine Python-Portierung des Aelto-Tools und damit die autoritative Quelle für
Format **und** Logik. Daraus verifiziert:

### 2.1 Speicherort
```
<game>/bin/config/r4game/user_config_matrix/pc/
    dx11filelist.txt   — Menü-XMLs für DX11
    dx12filelist.txt   — Menü-XMLs für DX12
```
→ entspricht exakt `game_witcher3.menu_config_path()` (Plugin `:138`, gibt genau diesen
`pc/`-Ordner zurück). **Kein neuer Plugin-Pfad nötig.**

### 2.2 Dateiformat — KEIN XML
Reine Textliste, **ein XML-Dateiname pro Zeile, jeweils mit Semikolon**:
```
audio.xml;
graphicsdx11.xml;
modSomeMenu.xml;
```
> ⚠️ Die alte kombinierte Spec nahm eine `<userConfig>`-XML-Struktur mit
> `<!-- ANVIL_MANAGED_START -->`-Marker-Blöcken an. **Das ist falsch.** Es gibt kein XML,
> keine Marker, kein Anhängen.

### 2.3 Logik = REGENERIEREN (nicht patchen)
Die Filelist wird **komplett neu aus dem Verzeichnis erzeugt**:
1. `pc/`-Ordner **flach** (`iterdir()`, *nicht* rekursiv) nach `*.xml` scannen.
2. Dateien mit Präfix `~` ignorieren (Backups/Temporär).
3. Alphabetisch sortieren.
4. **Vanilla-Grafik-Eintrag tauschen** (kritisches Detail!):
   - `graphicsdx11.xml` → **nur** in `dx11filelist.txt` (aus DX12-Liste ausschließen)
   - `graphics.xml` → **nur** in `dx12filelist.txt` (aus DX11-Liste ausschließen)
5. Jede Liste atomar schreiben (`name.xml;\n`-Zeilen via `.tmp`-Sibling + `replace()`).

→ **Idempotenz ist automatisch:** Da bei jedem Lauf die ganze Liste aus dem Ist-Zustand
des Ordners neu erzeugt wird, entstehen nie Duplikate. Marker-Blöcke sind überflüssig.

### 2.4 Still überspringen (kein Crash) wenn:
- `pc/`-Ordner fehlt (Pre-Next-Gen-Install),
- **weder** `dx11filelist.txt` **noch** `dx12filelist.txt` existiert (alte Spielversion
  braucht sie nicht — nicht ungefragt anlegen!),
- gar keine XMLs gefunden.

### 2.5 Purge / Zurücksetzen
**Kein Backup-aus-Datei nötig.** Anvil deployt Menü-XMLs als Symlinks in `pc/`. Nach
dem Purge (Symlinks entfernt) verbleiben nur die Vanilla-XMLs → ein erneutes
`update_menu_filelists()` regeneriert automatisch die Vanilla-Filelist. Restore =
einfach nach dem Purge nochmal regenerieren.

> *Optionaler Sicherheitsgurt:* Beim allerersten Lauf eine einmalige Kopie
> `dx11filelist.txt.anvil-bak` anlegen (falls noch nicht vorhanden), als Fallback bei
> kaputtem Ordnerzustand. Nicht zwingend — der Regenerate-Ansatz ist selbstheilend.

---

## 3. Ist-Zustand im Anvil-Code

| Ort | Status |
|-----|--------|
| `anvil/plugins/games/game_witcher3.py:138` `menu_config_path()` | **Vorhanden** — liefert genau `bin/config/r4game/user_config_matrix/pc`. Direkt nutzbar als `menu_dir`. |
| `anvil/widgets/game_panel.py:653` `silent_deploy()` | Post-Deploy-Hook-Reihe (BA2 `:668`, plugins.txt `:705`, Proton-Shims `:729`, DLL-Overrides `:745`). **Hier neuen Witcher-3-Hook ans Ende.** |
| `anvil/widgets/game_panel.py:748` `silent_deploy_fast()` | Quick-Redeploy — braucht denselben Hook. |
| `anvil/widgets/game_panel.py:769` `silent_purge()` | Nach `self._deployer.purge()` (`:773`) → Filelist regenerieren (ergibt Vanilla). |
| `dx11filelist`/`dx12filelist`/`filelist` im Code | **Keine Treffer** — komplett neu. |

**Fazit:** Ein neues Core-Modul + drei Hook-Aufrufe (Deploy, Fast-Deploy, Purge) +
i18n. Plugin-Pfad existiert bereits.

---

## 4. Lösung / Ansatz

### 4.1 Neues Core-Modul `anvil/core/witcher_filelist.py`
Funktion `update_menu_filelists(menu_dir: Path, log_fn=None) -> None`, die die in §2
verifizierte Logik nativ umsetzt (frisch geschrieben, nicht kopiert):
- Konstanten: `_DX11_FILE`, `_DX12_FILE`, `_DX11_VANILLA="graphicsdx11.xml"`,
  `_DX12_VANILLA="graphics.xml"`, `_IGNORE_PREFIX="~"`.
- Skip-Bedingungen aus §2.4.
- Flacher `*.xml`-Scan, sortiert, Vanilla-Swap, atomarer Write (`.tmp` + `replace`).
- Rückgabe einer kurzen Status-Zeile (für Log), IO-Fehler abfangen.

Bewusst **direkt auf `menu_dir`** statt auf `game_root` — Anvil hat über
`menu_config_path()` schon den fertigen Pfad; das Modul bleibt damit plugin-agnostisch
und testbar.

### 4.2 Hook-Helper in `game_panel.py`
Private Methode `_update_witcher3_filelists()`:
- Nur wenn `GameShortName == "witcher3"` und `menu_config_path()` vorhanden.
- Optionaler Schalter `QSettings("Witcher3/auto_filelist_update", True)` (analog
  `LOOT/auto_sort_on_deploy` `:722`).
- Ruft `update_menu_filelists(plugin.menu_config_path(), log_fn=print)`.

Aufgerufen am Ende von `silent_deploy()` (nach `:745`), in `silent_deploy_fast()` und
in `silent_purge()` (nach `:773`). In allen drei Fällen derselbe Helper — Deploy und
Purge unterscheiden sich nicht, weil beide nur den Ist-Zustand des `pc/`-Ordners
abbilden.

### 4.3 Optionaler Settings-Schalter
Checkbox „Menü-Filelists automatisch aktualisieren" — nur sinnvoll im Witcher-3-Kontext.
Kann in einer ersten Iteration entfallen (Default-an genügt); dann nur die tr-Keys für
Statusmeldungen.

---

## 5. Betroffene Dateien

| Datei | Änderung |
|-------|----------|
| `anvil/core/witcher_filelist.py` | **NEU** — `update_menu_filelists(menu_dir, log_fn)` (Scan, Vanilla-Swap, atomarer Write, Skip-Logik). |
| `anvil/widgets/game_panel.py` | `_update_witcher3_filelists()` ergänzen; Aufruf in `silent_deploy()` (nach `:745`), `silent_deploy_fast()` (`:748`), `silent_purge()` (nach `:773`). |
| `anvil/widgets/settings_dialog.py` | *Optional* — Checkbox `Witcher3/auto_filelist_update`. |
| `anvil/locales/{de,en,es,fr,it,pt,ru}.json` | 7 Dateien — `witcher_filelist.*`-Keys (§7). |

**Nicht ändern:** `mod_deployer.py` (game-agnostisch — Filelist läuft als Post-Hook im
`game_panel`, wie alle anderen Game-Spezifika). `game_witcher3.py` (Pfad existiert
bereits; höchstens ein dünner Convenience-Wrapper, optional). Script-Merger-Dateien
(anderes Feature, fertig).

---

## 6. Umsetzungsschritte

1. **Core-Modul** `witcher_filelist.py` schreiben (§4.1) — die §2-Logik 1:1 nativ.
2. **Hook-Helper** `_update_witcher3_filelists()` in `game_panel.py` (witcher3-Guard +
   QSettings-Schalter).
3. **Verdrahten:** Aufruf in `silent_deploy()`, `silent_deploy_fast()`, `silent_purge()`.
4. **i18n:** `witcher_filelist.*`-Keys in ALLE 7 Locales (gleiche Key-Anzahl).
5. *(Optional)* Settings-Checkbox `Witcher3/auto_filelist_update`.
6. `python -m py_compile` auf geänderte Dateien.
7. `./restart.sh`, Log auf Traceback/NameError/ImportError prüfen.
8. **Test (soweit ohne Spiel möglich):** Mit einem Test-`pc/`-Ordner + Dummy-`.xml` +
   leeren `dx11/dx12filelist.txt` → Deploy-Hook → Inhalt prüfen (Semikolon-Zeilen,
   Vanilla-Swap korrekt, keine Duplikate bei Wiederholung); Ordner ohne Filelists →
   wird übersprungen.

---

## 7. i18n (tr-Keys, 7 Locales de/en/es/fr/it/pt/ru)

| Key | DE (Referenz) |
|-----|---------------|
| `witcher_filelist.updated` | „Menü-Filelists aktualisiert ({dx11} DX11 / {dx12} DX12)" |
| `witcher_filelist.skipped` | „Keine Next-Gen-Filelists gefunden — übersprungen" |
| `witcher_filelist.error` | „Filelist-Update fehlgeschlagen: {error}" |
| `settings.witcher3_filelist_label` *(falls Schalter)* | „Menü-Filelists automatisch aktualisieren" |
| `settings.witcher3_filelist_tooltip` *(falls Schalter)* | „Registriert Menü-XMLs deployter Mods in dx11/dx12filelist.txt (Witcher 3 Next-Gen)." |

**Pflicht:** Jeder Key in allen 7 Dateien.

---

## 8. Akzeptanzkriterien

- [ ] **AK-01:** Nach Deploy einer Menü-Mod stehen deren `.xml` in `dx11filelist.txt`
      **und** `dx12filelist.txt`, je als `name.xml;`-Zeile.
- [ ] **AK-02:** `graphicsdx11.xml` erscheint nur in DX11, `graphics.xml` nur in DX12.
- [ ] **AK-03:** Erneuter Deploy erzeugt KEINE Duplikate (Regenerate aus Ordnerzustand).
- [ ] **AK-04:** Dateien mit `~`-Präfix werden ignoriert.
- [ ] **AK-05:** Fehlt der `pc/`-Ordner ODER beide Filelists → still übersprungen, kein
      Crash, keine Datei wird neu angelegt.
- [ ] **AK-06:** Purge → Symlinks weg → Regenerate ergibt die Vanilla-Filelist (nur
      Vanilla-XMLs gelistet).
- [ ] **AK-07:** Schreiben ist atomar (`.tmp` + `replace`) — Abbruch korrumpiert die
      Filelist nicht.
- [ ] **AK-08:** Format bleibt vom Spiel ladbar (Semikolon-Zeilen, UTF-8, je eine pro XML).
- [ ] **AK-09:** *(falls Schalter)* `Witcher3/auto_filelist_update` greift an/aus.
- [ ] **AK-10:** Hook läuft NUR bei `GameShortName == "witcher3"`, andere Games unberührt.
- [ ] **AK-11:** Alle `witcher_filelist.*`-Keys in allen 7 Locales.
- [ ] **AK-12:** `python -m py_compile` sauber; `./restart.sh` ohne Traceback.

---

## 9. Aufwand / Risiko

**Aufwand:** **niedrig** (deutlich geringer als die alte Spec mit „mittel" annahm —
Format & Logik sind jetzt verifiziert, nicht mehr offen). Kern ist ~90 Zeilen Python +
drei Einzeiler-Hooks + 7 Locales.

**Risiko:** **niedrig**:
- Format-Unbekannte (das einzige echte Risiko der alten Spec) ist durch die
  Amethyst-Referenz **beseitigt** — kein XML, kein Marker, einfache Semikolon-Liste.
- Regenerate-Ansatz ist selbstheilend → keine Backup/Restore-Fragilität, keine
  Idempotenz-Sonderfälle.
- Einziger Restprüfpunkt: am echten Spiel verifizieren, dass Anvils Symlink-Deploy die
  Menü-XMLs tatsächlich flach in `pc/` ablegt (nicht in Unterordnern) — sonst sieht
  `iterdir()` sie nicht. Beim ersten Test mit echter Mod gegenprüfen.

**Out-of-scope:** `dx12user.settings`-Merging (eigenes TW3-Thema, nicht Teil von #35);
`input.xml`-Merge (gehört zum Script Merger / separat).
