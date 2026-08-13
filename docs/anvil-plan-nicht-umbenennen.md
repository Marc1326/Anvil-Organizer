# Ausnahme pro Mod: „Dateinamen nicht ändern"

Stand: 13.08.2026
Anlass: Punkt 2 aus `docs/anvil-plan-reihenfolge-ehrlich.md` (Zeilen 133–144).
Nur Analyse und Planung — es wurde kein Code geändert.

Vorbemerkung zur Abgrenzung: Der parallele Punkt „Anvil sagt nie, wenn die
Reihenfolge nicht ankommt" (Anzeige, `docs/anvil-plan-reihenfolge-ehrlich.md:107-110`)
wird hier **nicht** angefasst. Ebenso wenig verwechselt werden darf dieser
Plan mit `docs/anvil-kimi-punkt2-plan.md` — das ist ein anderes „Punkt 2"
(Konflikte innerhalb von Archiven anzeigen).

---

## 0. Gegenprobe: Gibt es die Ausnahme wirklich noch nicht?

Gesucht wurde über das gesamte Repository, ohne Groß-/Kleinschreibung:

```
no_rename | skip_rename | keep_name | keep_filename | "nicht umbenennen"
```

Treffer (vollständig):

| Datei:Zeile | Inhalt |
|---|---|
| `docs/anvil-plan-reihenfolge-ehrlich.md:101` | die Feststellung selbst |
| `anvil/widgets/profile_bar.py:840` | `return  # Default-Profil nicht umbenennen` — Profile, nicht Mods |
| `anvil/plugins/games/game_stellarblade.py:56` | Kommentar `# Nicht umbenennen. Die Mod-Autoren verbieten es ausdruecklich` — Spiel-Ebene, nicht Mod-Ebene |

**Ergebnis: Es gibt heute keinen Merker pro Mod.** Die Nummerierung ist
Alles-oder-nichts pro Spiel und Ordner. Bestätigt.

---

## 1. Wo wird umbenannt?

### 1.1 `pak_order_allows()` — vollständig

`anvil/core/mod_deployer.py:240-254`:

```python
def pak_order_allows(rel: Path, dirs: list[str]) -> bool:
    """True, wenn fuer den Zielordner von *rel* umbenannt werden darf.

    Ohne Angabe gilt keine Begrenzung. Sonst muss die Datei unterhalb
    eines freigegebenen Ordners liegen -- LogicMods, CNS und die Loader
    suchen ihre Dateien am Namen und bleiben so unangetastet.
    """
    if not dirs:
        return True
    pfad = str(rel).replace("\\", "/").lower()
    for eintrag in dirs:
        ordner = str(eintrag).replace("\\", "/").strip("/").lower()
        if ordner and pfad.startswith(ordner + "/"):
            return True
    return False
```

Wichtig für die Planung: **Die Funktion kennt nur den relativen Zielpfad.**
Kein Mod-Name, kein `self`. Sie ist ein reines Prädikat auf dem Pfad und
wird auch direkt aus Tests heraus aufgerufen
(`tests/test_archiv_ladereihenfolge.py:83-88`,
`tests/test_pak_load_order_dirs.py:48-56`).

### 1.2 `load_order_index()` — vollständig

`anvil/core/mod_deployer.py:227-237`:

```python
def load_order_index(load_index: int, gesamt: int, first_wins: bool) -> int:
    """Zaehler fuer eine Mod, je nachdem welche Datei gewinnt.

    Der Deploy laeuft von der niedrigsten zur hoechsten Prioritaet, also
    ist ``load_index`` 0 die schwaechste Mod. Gewinnt die alphabetisch
    letzte Datei (Unreal), passt das direkt. Gewinnt die erste
    (REDengine), muss gespiegelt werden.
    """
    if not first_wins:
        return load_index
    return max(gesamt - 1 - load_index, 0)
```

Auch hier: kein Mod-Name, nur Zahlen.

### 1.3 Die Stelle, an der der Zähler tatsächlich gesetzt wird

`anvil/core/mod_deployer.py:785-802`, innerhalb der Datei-Schleife der
Mod-Schleife:

```python
                rel_ohne_zaehler = ""
                if self._pak_load_order_prefix or self._pak_load_order_dirs:
                    if pak_order_allows(rel, self._pak_load_order_dirs):
                        vorher = rel
                        rel = pak_load_order_name(
                            rel,
                            load_order_index(
                                load_index, len(enabled_mods),
                                self._pak_load_order_first_wins,
                            ),
                            self._pak_load_order_extensions,
                            zaehler_breite,
                        )
                        if rel != vorher:
                            rel_ohne_zaehler = str(vorher)
```

Das eigentliche Voranstellen passiert in `pak_load_order_name()`
(`anvil/core/mod_deployer.py:201-224`), konkret Zeile 224:

```python
    return rel.with_name(f"{index:0{breite}d}_{rel.name}")
```

Zeile 222-223 schützt fremde Endungen: liegt der Suffix nicht in der
Freigabeliste, kommt `rel` unverändert zurück (deshalb bleiben `.xl`
unberührt, `tests/test_archiv_ladereihenfolge.py:48-51`).

### 1.4 Umgebung dieser Stelle — was dort bereits verfügbar ist

| Was | Datei:Zeile | Bemerkung |
|---|---|---|
| Mod-Schleife | `anvil/core/mod_deployer.py:515` | `for load_index, (mod_name, _priority) in enumerate(enabled_mods):` |
| `enabled_mods` umgedreht | `anvil/core/mod_deployer.py:490` | `enabled_mods.reverse()` — Index 0 ist danach die schwächste Mod |
| Zählerbreite | `anvil/core/mod_deployer.py:513` | `zaehler_breite = max(3, len(str(max(len(enabled_mods) - 1, 0))))` |
| Zielpfad steht fest | `anvil/core/mod_deployer.py:809` | `target = deploy_base / rel` |

**Damit ist die Kernfrage aus Aufgabe 3 beantwortet: `mod_name` ist an der
Nummerierungsstelle bereits im Gültigkeitsbereich** (Schleifenvariable aus
Zeile 515). `pak_order_allows()` selbst muss den Namen also gar nicht
kennen — die Abfrage kann davorstehen.

### 1.5 Betroffene Ordner und Endungen

| Schalter | Definition | Cyberpunk 2077 | STALKER 2 | Rest |
|---|---|---|---|---|
| `GamePakLoadOrderPrefix` | `anvil/plugins/base_game.py:149` (`False`) | nicht gesetzt | `False` (`game_stalker2.py:55`) | `False` |
| `GamePakLoadOrderDirs` | `anvil/plugins/base_game.py:151` (`[]`) | `["archive/pc/mod"]` (`game_cyberpunk2077.py:78`) | `["Stalker2/Content/Paks/~mods"]` (`game_stalker2.py:61`) | leer |
| `GamePakLoadOrderExtensions` | `anvil/plugins/base_game.py:159` (`[]`) | `[".archive"]` (`game_cyberpunk2077.py:79`) | leer → Pak-Endungen | leer |
| `GamePakLoadOrderFirstWins` | `anvil/plugins/base_game.py:165` (`False`) | `True` (`game_cyberpunk2077.py:82`) | `False` | `False` |

Leere `GamePakLoadOrderExtensions` bedeutet: es gelten die Pak-Endungen
(`anvil/core/mod_deployer.py:221`, Konstante `_PAK_ORDER_EXTENSIONS`).

Die Warnung im Code, die diesen ganzen Plan auslöst, steht in
`anvil/plugins/base_game.py:143-157`:

> Achtung: viele Mod-Autoren verbieten das Umbenennen ausdruecklich --
> Loader suchen ihre Dateien am Namen. Nur einschalten, wenn geprueft.

und

> Ordner wie ``LogicMods``, ``CNS`` oder ``Binaries/Win64`` gehoeren nicht
> hinein: dort suchen die Loader ihre Dateien am Namen und finden sie mit
> Zaehler nicht mehr.

### 1.6 Manifest — wird der Originalname mitgeschrieben?

**Ja, geprüft und bestätigt.** Der Bericht vom 12.08. stimmt.

Der Schlüssel heißt `unnumbered` und wird an drei Stellen gesetzt, je
einmal pro Deploy-Art:

| Datei:Zeile | Deploy-Art |
|---|---|
| `anvil/core/mod_deployer.py:902-903` | Framework-Kopie mit Reverse-Sync |
| `anvil/core/mod_deployer.py:923-924` | `copy` / `shim_copy` |
| `anvil/core/mod_deployer.py:943-944` | `symlink` |

Jeweils:

```python
                        if rel_ohne_zaehler:
                            entry_data["unnumbered"] = rel_ohne_zaehler
```

Gesetzt wird er nur, wenn tatsächlich umbenannt wurde
(`anvil/core/mod_deployer.py:801`) — die Begründung steht als Kommentar
darüber (`:798-800`): eine fremde Datei kann selbst mit `00_` beginnen,
am Dateinamen ließe es sich nicht sicher unterscheiden.

Gelesen wird er an genau einer Stelle: `_drop_superseded_numbered()`,
`anvil/core/mod_deployer.py:1044`:

```python
            schluessel = str(eintrag.get("unnumbered", "")).lower()
            if not schluessel:
                continue
```

Zweck dieser Funktion (`anvil/core/mod_deployer.py:1020-1077`): Ohne
Zähler überschrieb die höhere Mod die gleichnamige Datei der niedrigeren —
es lag genau eine Datei da. Mit Zähler heißen beide anders und lägen beide
da. Die Funktion räumt die schwächere weg.

Ins Manifest geschrieben wird das Ganze in
`anvil/core/mod_deployer.py:969-988` (`symlinks` → `manifest["symlinks"]`).

---

## 2. Wo könnte der Merker liegen?

### 2.1 Bewertung der drei Wege

| Kriterium | (a) `meta.ini` der Mod | (b) Liste in `.anvil.ini` | (c) `categories.json` / neue Datei |
|---|---|---|---|
| Übersteht Umbenennen der Mod | **ja** — die Datei liegt im Mod-Ordner und wandert mit | nein — Liste enthält Ordnernamen, die dann ins Leere zeigen | nein, gleiches Problem |
| Übersteht Neuinstallation der Mod | **nein** (siehe 2.2) | ja | ja |
| Übersteht Umzug der Instanz | **ja** — relativ zum Mod-Ordner | nur wenn nichts absolut gespeichert wird | ja |
| Im Dateisystem sichtbar | **ja** — `.mods/<Mod>/meta.ini`, mit Texteditor lesbar | ja, aber weit weg von der Mod | teils |
| Bestehendes Vorbild vorhanden | **ja** (`color`, `deploy_path`, `properties`, `category`) | Instanzdaten, aber keine Pro-Mod-Listen | `categories.json` ist eine Kategorien-Definition, keine Zuordnung |
| Wandert bei Collection-Export mit | nein (siehe 2.3) | nein | nein |

### 2.2 Der eine echte Nachteil von (a)

Bei „Mod neu installieren" wird der Ordner ersetzt. `mod_installer.py:252-259`
verschiebt das entpackte Archiv nach `.mods/<Ordner>` und ruft dann
`create_default_meta_ini(dest, display)` (`anvil/core/mod_installer.py:259`).
`write_meta_ini()` mergt zwar auf eine vorhandene Datei
(`anvil/core/mod_metadata.py:90-94`) — nur ist bei einer echten
Neuinstallation die alte Datei mit dem alten Ordner weg.

**Das trifft `color` und `deploy_path` heute genauso.** Es ist also kein
neues Problem, sondern das bestehende Verhalten. Wer eine Mod neu
installiert, setzt den Merker erneut. Für einen Merker, den man ohnehin
nur nach einer beobachteten Fehlfunktion setzt, ist das vertretbar.

### 2.3 Collection-Export nimmt den Merker nicht mit

`anvil/core/collection_io.py:180` liest zwar die komplette `meta.ini`
(`read_meta_ini`), übernimmt daraus aber nur ausgewählte Felder
(`:184-209`: `modid`, `name`, `category`, Separator-Farbe …). Der neue
Schlüssel würde **nicht** exportiert.

Bewertung: **kein Fix in diesem Schritt.** Eine Collection beschreibt
fremde Mod-Zusammenstellungen; ob dort eine Datei umbenannt werden darf,
hängt am eigenen Spiel-Setup. Wird als bewusste Auslassung dokumentiert.

### 2.4 Das Vorbild `deploy_path`, Station für Station

| Station | Datei:Zeile | Was passiert |
|---|---|---|
| Schreiben | `anvil/mainwindow.py:5266` | `write_meta_ini(entry.install_path, {"deploy_path": chosen_path})` |
| Zurücksetzen | `anvil/mainwindow.py:5299` | `write_meta_ini(entry.install_path, {"deploy_path": ""})` |
| Speicherformat | `anvil/core/mod_metadata.py:96-107` | alles außer `name/author/description/url/installDate` landet in `[General]` |
| Lesen | `anvil/core/mod_entry.py:175-177` | `raw_deploy = meta.get("deploy_path", "")` |
| Feld im Datensatz | `anvil/core/mod_entry.py:72-73` | `deploy_path: str = ""` |
| Übergabe an den Datensatz | `anvil/core/mod_entry.py:205` | `deploy_path=sep_deploy_path` |
| In die Anzeige | `anvil/models/mod_list_model.py:121` | `deploy_path=getattr(entry, "deploy_path", "")` |
| Anzeige (Tooltip) | `anvil/models/mod_list_model.py:398-399` | `return f"Deploy → {r.deploy_path}"` |
| Einsammeln fürs Deploy | `anvil/mainwindow.py:2143-2149` | `_sync_separator_deploy_paths()` |
| Weitergabe ans Panel | `anvil/widgets/game_panel.py:1139-1149` | `set_separator_deploy_paths()`, aktualisiert auch einen bestehenden Deployer |
| In den Deployer | `anvil/widgets/game_panel.py:3283` | `separator_deploy_paths=self._separator_deploy_paths` |
| Verwendung im Deploy | `anvil/core/mod_deployer.py:805-807` | `sep_path = self._separator_deploy_paths.get(mod_separator, "")` |

**Empfehlung: Weg (a), exakt diesem Muster folgen.** Es gibt keinen Grund,
etwas Neues zu erfinden — der Merker gehört inhaltlich zur Mod, nicht zur
Instanz, und `deploy_path` löst dasselbe Problem (pro Eintrag gespeicherte
Deploy-Sonderregel) bereits vollständig durch.

Schlüsselname: **`keep_file_names`** (snake_case wie `deploy_path`).
Werte: `"1"` = ausgenommen, `""` oder fehlend = normal.

---

## 3. Wie kommt der Merker zum Deployer?

### 3.1 Was der Deployer heute bekommt

`ModDeployer.deploy()` liest selbst:

- `global_order = read_global_modlist(self._profiles_dir)` — `anvil/core/mod_deployer.py:448`
- `active_mods = read_active_mods(self._profile_path)` — `anvil/core/mod_deployer.py:449`

Alles darüber hinaus wird ihm **von außen gegeben**, entweder über den
Konstruktor (`anvil/core/mod_deployer.py:308-334`) oder über einen Setter.

Es gibt bereits genau den passenden Setter-Vorbildfall — mengenbasiert,
kleingeschrieben, aus dem GamePanel gefüttert:

`anvil/core/mod_deployer.py:368-374`:

```python
    def set_skipped_mods(self, names) -> None:
        """Mod folders to leave out of the next deploy. ..."""
        self._skipped_mods = {str(n).lower() for n in names}
```

Gefüttert wird er in `anvil/widgets/game_panel.py:1195-1224`
(`_refresh_skipped_mods`), Aufruf des Setters in `:1201` und `:1224`.

### 3.2 Vorgeschlagener Weg, Station für Station

| Nr. | Station | Datei:Zeile (heute) | Was neu dazukommt |
|---|---|---|---|
| 1 | Mod-Ordner | `.mods/<Mod>/meta.ini` | `[General]` → `keep_file_names=1` |
| 2 | Lesen | `anvil/core/mod_entry.py:120` (`meta = read_meta_ini(mod_path)`) | Auswertung analog `:172-177`, aber für **Nicht**-Separatoren |
| 3 | Datensatz | `anvil/core/mod_entry.py:73` | neues Feld `keep_file_names: bool = False` |
| 4 | Übergabe | `anvil/core/mod_entry.py:187-209` (`return ModEntry(...)`) | `keep_file_names=…` ergänzen |
| 5 | Einsammeln | `anvil/mainwindow.py:2143` (`_sync_separator_deploy_paths`) | Schwester-Methode `_sync_keep_file_name_mods()`, aufgerufen an denselben Stellen: `:2065`, `:3660`, `:5948` |
| 6 | Panel | `anvil/widgets/game_panel.py:1139` | Schwester-Methode `set_keep_file_name_mods(names)`, füllt Feld **und** aktualisiert einen bestehenden Deployer (Vorbild `:1148-1149`) |
| 7 | Deployer-Bau | `anvil/widgets/game_panel.py:3283` | zusätzlicher Konstruktor-Parameter, damit der Merker einen Deployer-Neubau überlebt |
| 8 | Deployer-Feld | `anvil/core/mod_deployer.py:366` | `self._keep_file_name_mods: set[str] = set()`, kleingeschrieben wie `_skipped_mods` (`:374`) |
| 9 | Wirkung | `anvil/core/mod_deployer.py:786` | Bedingung erweitern (siehe 3.3) |

Warum sowohl Setter als auch Konstruktor-Parameter: `set_instance_path()`
baut den Deployer neu (`anvil/widgets/game_panel.py:3300-3303`), und
`_sync_separator_deploy_paths()` läuft in `mainwindow.py:2065`
**danach**. Bei anderen Reihenfolgen (Profilwechsel) rettet der
Konstruktor-Parameter den Zustand. Genau so ist `separator_deploy_paths`
heute gelöst.

### 3.3 Die eine Zeile im Deployer

Heute (`anvil/core/mod_deployer.py:786-787`):

```python
                if self._pak_load_order_prefix or self._pak_load_order_dirs:
                    if pak_order_allows(rel, self._pak_load_order_dirs):
```

Vorgeschlagen: eine vorgeschaltete Bedingung mit `mod_name` aus der
Schleife von `:515`. `pak_order_allows()` bleibt unverändert — sie ist ein
reines Pfad-Prädikat und wird von drei Tests direkt aufgerufen
(`tests/test_archiv_ladereihenfolge.py:83`, `tests/test_pak_load_order_dirs.py:48,53`).
Eine Signaturänderung würde diese Tests brechen, ohne Nutzen.

Nebeneffekt, der automatisch stimmt: Bleibt `rel` unverändert, wird auch
`rel_ohne_zaehler` nicht gesetzt (`:801`) — der Manifest-Eintrag der
ausgenommenen Mod bekommt also **kein** `unnumbered`, und
`_drop_superseded_numbered()` überspringt ihn (`:1044-1046`). Ihre Datei
wird nie weggeräumt. Das ist das gewünschte Verhalten.

### 3.4 Folgen, die im Auge behalten werden müssen

**(A) Zwei Dateien statt einer bei Namensgleichheit.**
Hat die ausgenommene Mod eine `Foo.archive` und eine andere Mod ebenfalls
eine `Foo.archive`, so liegen nach dem Deploy `Foo.archive` **und**
`007_Foo.archive` im Ordner — beide werden geladen. Vor der Nummerierung
lag dort genau eine Datei. `_drop_superseded_numbered()` kann das nicht
verhindern, weil der Eintrag ohne `unnumbered` gar nicht betrachtet wird
(`anvil/core/mod_deployer.py:1044-1046`). Das ist der Preis der Ausnahme
und gehört in den Warntext.

**(B) Die Position der ausgenommenen Mod in der Liste wirkt nicht mehr.**
Ihr Archiv sortiert an der Stelle ein, die sein eigener Name vorgibt.
Alle nummerierten Dateien beginnen mit einer Ziffer; ein Name, der mit
einem Buchstaben beginnt, landet dahinter, ein Name mit Sonderzeichen
davor — der Bericht nennt ein reales Beispiel
(`docs/anvil-plan-reihenfolge-ehrlich.md:69`: `002_###-PreemFixes-Cloth.archive`,
also ursprünglich `###-…`). Genau deshalb braucht der Eintrag in der Liste
eine sichtbare Kennzeichnung.

**(C) `_write_archive_load_order()` braucht keinen Fix.**
`anvil/core/mod_deployer.py:1110-1120` filtert nur nach `deploy_base`,
`type`, Endung `.archive` und Zielordner — der Name spielt keine Rolle.
Die ausgenommene Datei landet mit ihrem Originalnamen an ihrer
Prioritätsstelle in der Liste. Da Cyberpunk diese Liste ohnehin ignoriert
(ausdrücklich vermerkt in `anvil/plugins/games/game_cyberpunk2077.py:68-71`),
ist das folgenlos, aber korrekt.

**(D) `purge()` braucht keinen Fix.** Aufgeräumt wird über die
`link`-Werte im Manifest, nicht über den Namen.

**(E) STALKER 2 profitiert automatisch mit.** Das Spiel hat
`GamePakLoadOrderDirs` gesetzt (`anvil/plugins/games/game_stalker2.py:61`).
Der Merker wirkt dort ohne weitere Freigabe — es wird **kein** neues Spiel
eingeschaltet, nur eine bestehende Nummerierung pro Mod abschaltbar.
Zusatznutzen: die drei Dateien eines Unreal-Gespanns (`.pak`/`.ucas`/`.utoc`)
werden gemeinsam ausgenommen, weil die Entscheidung auf Mod-Ebene fällt.
Der bestehende Test dazu ist `tests/test_pak_load_order_dirs.py:59` und
`:109`.

---

## 4. Bedienung

### 4.1 Wo genau einhängen

Der Kontextmenü-Aufbau liegt in `anvil/mainwindow.py` ab etwa `:4790`
(Menü) bis `:5079` (Auswertung). Die beiden genannten Vorbilder:

| Vorbild | Aufbau | Auswertung | Ausführung |
|---|---|---|---|
| Trennerfarbe wählen | `anvil/mainwindow.py:4988` | `:5059-5060` | `_ctx_select_separator_color`, `:5180` ff. |
| Deploy-Pfad setzen | `anvil/mainwindow.py:4992` | `:5063-5064` | `_ctx_set_deploy_path`, `:5248-5287` |

Beide hängen im Block `if single and _ctx_entry:` unter
`if _sep_entry.is_separator:` (`anvil/mainwindow.py:4984-4994`) — also
ausdrücklich **nur für Separatoren**.

Der neue Eintrag gehört genau gegenteilig: **nur für Nicht-Separatoren**.
Vorgeschlagene Einhängestelle: unmittelbar vor `menu.addSeparator()` in
`anvil/mainwindow.py:4947`, also im Block der Mod-Aktionen neben
„Preset einsortieren" (`:4939-4945`) — dort steht bereits eine
Bedingung, die nur bei einer einzelnen, passenden Mod greift.

### 4.2 Umschalter statt zwei Einträge

`deploy_path` nutzt zwei Menüpunkte (setzen / zurücksetzen). Für einen
reinen Ja/Nein-Merker ist eine abhakbare Aktion besser, und dafür gibt es
im selben Menü bereits ein Vorbild — die eigenen Eigenschaften,
`anvil/mainwindow.py:4849-4854`:

```python
                    act_p.setCheckable(True)
                    act_p.setChecked(prop["id"] in _assigned_props)
                    act_p.triggered.connect(
                        lambda checked, pid=prop["id"], r=selected_rows[0]:
                        self._toggle_property(r, pid))
```

Zu beachten (bekannte Falle aus `CLAUDE.md`): `triggered` liefert einen
`bool` — das `checked=` im Lambda ist Pflicht. Und: Bei `triggered.connect`
läuft der Slot **vor** dem Zurückkehren aus `menu.exec()`; die
darauffolgende `elif`-Kette (`:5015-5079`) darf den Fall nicht ein zweites
Mal behandeln.

Der zugehörige Slot folgt `_toggle_property` (`anvil/mainwindow.py:6750-6769`):
Eintrag holen über `_entry_for_row` (`:2130-2141`), Feld setzen,
`write_meta_ini`, Anzeige aktualisieren.

Mehrfachauswahl: `_toggle_property` arbeitet nur auf `selected_rows[0]`.
Für den Merker ist Mehrfachauswahl sinnvoll (mehrere Mods eines Autors auf
einmal), aber nicht zwingend. Vorschlag: **auf alle ausgewählten
Nicht-Separator-Zeilen anwenden**, Zielzustand = Gegenteil des Zustands
der zuerst angeklickten Zeile.

### 4.3 Nur bei Spielen, die überhaupt nummerieren?

**Ja.** Begründung:

1. Bei allen anderen Spielen hätte der Merker **keinerlei Wirkung** — die
   Prüfung in `anvil/core/mod_deployer.py:786` läuft dort gar nicht erst
   an, weil `GamePakLoadOrderPrefix` `False` und `GamePakLoadOrderDirs`
   leer ist (`anvil/plugins/base_game.py:149,151`). Ein Menüpunkt, der
   nichts tut, ist eine Falle.
2. Es sind heute genau zwei Spiele betroffen (Cyberpunk 2077, STALKER 2) —
   bei allen anderen wäre das Menü unnötig länger.

Prüfbedingung in `mainwindow.py` (das Plugin liegt dort als
`self._current_plugin`, `anvil/mainwindow.py:435`, gesetzt in `:1827`):

```
bool(getattr(plugin, "GamePakLoadOrderDirs", []))
    or getattr(plugin, "GamePakLoadOrderPrefix", False)
```

Das ist dieselbe Bedingung, die der Deployer in `:786` auswertet — sie
muss identisch bleiben, sonst zeigt das Menü etwas anderes an, als
tatsächlich passiert.

### 4.4 Wie sieht man es in der Liste?

Vorbild `is_foreign`:

| Zweck | Datei:Zeile |
|---|---|
| Feld im Datensatz | `anvil/core/mod_entry.py:62` |
| Feld in der Zeile (`__slots__`) | `anvil/models/mod_list_model.py:59` |
| Übernahme aus dem Datensatz | `anvil/models/mod_list_model.py:122` |
| Tooltip auf der Namensspalte | `anvil/models/mod_list_model.py:393-394` → `tr("foreign.tooltip")` |
| Hintergrundfarbe der Zeile | `anvil/models/mod_list_model.py:437-440` |

Vorschlag, bewusst zurückhaltend:

1. **Tooltip auf `COL_NAME`** — genau wie `is_foreign` (`:393`) und
   `has_stray_preset` (`:395-396`). Text nennt beide Folgen aus 3.4:
   Position wirkt nicht, Datei kann doppelt vorliegen.
2. **Kein eigener Zeilen-Hintergrund.** Die drei vorhandenen Einfärbungen
   (Fehler `:427`, Framework `:431`, fremd `:437`) sind bereits belegt;
   eine vierte Farbe macht die Liste unruhig, und der Merker ist eine
   Ausnahme für wenige Mods.
3. **Zeichen in der Spalte `COL_MARKERS`.** Diese Spalte existiert
   (`anvil/models/mod_list_model.py:42`, `COL_MARKERS`), wird angezeigt
   (`:314-315`) und ist heute **immer leer**: `mod_entry_to_row` setzt
   `markers=""` (`:108`), und im gesamten Produktivcode wird das Feld
   nirgends befüllt (geprüft über `\.markers|markers=` in `anvil/**/*.py`:
   nur `mod_list_model.py:61,65,108,230,315` und ein unbeteiligter Treffer
   in `character_presets.py:101,110`). Die Spalte ist also frei und genau
   für solche Kennzeichnungen gedacht — inklusive Sammelanzeige auf
   eingeklappten Trennern (`:335-337`, `_any_child_has_markers`) und
   Sortierung (`:230`).

---

## 5. Spec

### 5.1 User Stories

- Als Anwender möchte ich eine einzelne Mod von der Durchnummerierung
  ausnehmen, damit ihr Loader sie am unveränderten Dateinamen findet.
- Als Anwender möchte ich in der Mod-Liste erkennen, welche Mods
  ausgenommen sind, damit ich weiß, warum ihre Position dort nichts
  bewirkt.
- Als Anwender möchte ich den Merker jederzeit zurücknehmen können.
- Als Anwender möchte ich diesen Menüpunkt nicht sehen, wenn mein Spiel
  gar nicht nummeriert.

### 5.2 Betroffene Dateien und Funktionen

| Datei | Funktion / Stelle | Änderung |
|---|---|---|
| `anvil/core/mod_entry.py` | Datensatz `ModEntry`, bei `:62-73` | neues Feld `keep_file_names: bool = False` |
| `anvil/core/mod_entry.py` | `_build_entry`, `:168-177` und `:187-209` | Schlüssel aus `meta.ini` lesen, für Nicht-Separatoren; ans Ergebnis durchreichen |
| `anvil/core/mod_deployer.py` | `ModDeployer.__init__`, `:308-366` | Parameter + Feld `_keep_file_name_mods` (kleingeschrieben, Vorbild `:374`) |
| `anvil/core/mod_deployer.py` | neuer Setter neben `set_skipped_mods`, `:368` | `set_keep_file_name_mods(names)` |
| `anvil/core/mod_deployer.py` | `deploy()`, `:786` | Bedingung um den Merker erweitern; `mod_name` stammt aus `:515` |
| `anvil/widgets/game_panel.py` | neben `set_separator_deploy_paths`, `:1139-1149` | `set_keep_file_name_mods(names)`, aktualisiert auch einen laufenden Deployer |
| `anvil/widgets/game_panel.py` | `_create_deployer`, `:3269-3294` | neuer Konstruktor-Parameter |
| `anvil/mainwindow.py` | neben `_sync_separator_deploy_paths`, `:2143-2149` | `_sync_keep_file_name_mods()` |
| `anvil/mainwindow.py` | Aufrufstellen `:2065`, `:3660`, `:5948` | Schwester-Aufruf ergänzen |
| `anvil/mainwindow.py` | Kontextmenü, vor `:4947` | abhakbarer Eintrag, nur Nicht-Separator, nur bei nummerierenden Spielen |
| `anvil/mainwindow.py` | neuer Slot bei `:6750` ff. | `_toggle_keep_file_names(rows)` — `meta.ini` schreiben, Zeile aktualisieren, Log-Eintrag |
| `anvil/models/mod_list_model.py` | `ModRow.__slots__` `:59`, `__init__` `:61` | Feld `keep_file_names` |
| `anvil/models/mod_list_model.py` | `mod_entry_to_row` `:104-124` | Feld übernehmen, `markers` befüllen |
| `anvil/models/mod_list_model.py` | Tooltip-Block `:391-399` | Tooltip auf `COL_NAME` |
| `anvil/locales/*.json` (**7 Dateien**) | — | neue `tr()`-Schlüssel |

**Ausdrücklich nicht angefasst:** `pak_order_allows()`
(`anvil/core/mod_deployer.py:240`), `load_order_index()` (`:227`),
`pak_load_order_name()` (`:201`), `_drop_superseded_numbered()` (`:1020`),
`_write_archive_load_order()` (`:1079`), alle Spiel-Plugins.

### 5.3 Datenfluss

```
.mods/<Mod>/meta.ini  [General] keep_file_names=1
        │  read_meta_ini()          anvil/core/mod_metadata.py:33
        ▼
ModEntry.keep_file_names            anvil/core/mod_entry.py:_build_entry
        │
        ├──▶ mod_entry_to_row()     anvil/models/mod_list_model.py:104
        │        └──▶ ModRow → Tooltip (:393-Block) + COL_MARKERS (:314)
        │
        └──▶ MainWindow._sync_keep_file_name_mods()     (Vorbild :2143)
                 └──▶ GamePanel.set_keep_file_name_mods()  (Vorbild :1139)
                          ├──▶ Feld im Panel  ──▶ _create_deployer() (:3269)
                          └──▶ Deployer._keep_file_name_mods (laufend)
                                   └──▶ deploy(), Bedingung bei :786
                                            └──▶ Datei behält ihren Namen
                                            └──▶ kein "unnumbered" (:801)
                                                     └──▶ von
                                                          _drop_superseded_numbered
                                                          übersprungen (:1044)
```

### 5.4 Neue `tr()`-Schlüssel

Locale-Dateien wurden **gezählt**: `anvil/locales/` enthält
`de.json`, `en.json`, `es.json`, `fr.json`, `it.json`, `pt.json`,
`ru.json` — **7 Dateien**, nicht 6.

| Schlüssel | Ort in der JSON | Deutscher Text (Vorschlag) |
|---|---|---|
| `context.keep_file_names` | `context`-Block, bei `de.json:135` | „Dateinamen nicht ändern" |
| `tooltip.keep_file_names` | `tooltip`-Block, bei `de.json:341` | „Anvil lässt die Dateinamen dieser Mod unverändert.\nIhre Position in der Liste wirkt dadurch nicht mehr, und eine gleichnamige Datei einer anderen Mod kann zusätzlich im Spiel liegen." |
| `log.keep_file_names_on` | Log-Block | „{name}: Dateinamen bleiben unverändert" |
| `log.keep_file_names_off` | Log-Block | „{name}: Dateinamen werden wieder durchnummeriert" |

Der Marker-Text in `COL_MARKERS` sollte **nicht** übersetzt werden
(einzelnes Zeichen), sonst wandert er zwischen den Sprachen.

### 5.5 Tests

**Was die Nummerierung heute abdeckt:**

| Datei | Umfang |
|---|---|
| `tests/test_archiv_ladereihenfolge.py` (213 Z.) | Richtung (`:21-38`), Benennung (`:43-76`), Ordnerbegrenzung (`:81-88`), Plugin-Schalter (`:93-111`), `_drop_superseded_numbered` (`:133-212`) |
| `tests/test_pak_load_order_dirs.py` | `pak_order_allows` (`:47-56`), Unreal-Gespann (`:59`, `:109`), echter Deploy-Durchlauf (`:77-142`), STALKER 2 (`:144-177`), Stellar Blade aus (`:178-183`) |
| `tests/test_archive_load_order_wiring.py` | Verkabelung Plugin → Panel → Deployer (`:22-35`, `:129-134`), Wirkung am echten Deploy (`:72-123`) |
| `tests/test_pak_load_order.py` | Plugin-Vorgaben (`:121`, `:128`) |
| `tests/test_deploy_routes.py:211`, `tests/test_stalker2_routes.py:77` | Randnutzung der Schalter |

**Neu, Vorschlag `tests/test_dateinamen_ausnahme.py`:**

| Nr. | Test | Mutationsprobe — welche Änderung macht ihn rot |
|---|---|---|
| T1 | Mod mit Merker: ihre `.archive` liegt nach dem Deploy **ohne** Zählerpräfix im Spielordner | Bedingung in `mod_deployer.py:786` wieder auf den alten Stand → Datei heißt `00x_…` → rot |
| T2 | Mod **ohne** Merker im selben Lauf: bekommt weiterhin ihren Zähler | Merker versehentlich global statt pro Mod ausgewertet → beide unbenannt → rot |
| T3 | Manifest-Eintrag der ausgenommenen Mod enthält **kein** `unnumbered` | `rel_ohne_zaehler` unabhängig von `rel != vorher` gesetzt (`:801`) → Schlüssel da → rot |
| T4 | `_drop_superseded_numbered` löscht die ausgenommene Datei nicht, auch wenn eine nummerierte gleichen Ursprungsnamens danebenliegt | `continue` bei leerem `unnumbered` entfernt (`:1045-1046`) → Datei weg → rot |
| T5 | `meta.ini` Rundlauf: schreiben → `scan_mods_directory` → `ModEntry.keep_file_names is True` | Auswertung in `mod_entry.py` nur im Separator-Zweig (`:171`) → `False` → rot |
| T6 | Merker mit Wert `""` / fehlend / `"0"` → `keep_file_names is False` | Prüfung auf reine Vorhandenheit statt Wert → `True` → rot |
| T7 | Ordner der Mod umbenannt (`meta.ini` wandert mit): Merker weiterhin aktiv | Merker in `.anvil.ini` statt `meta.ini` abgelegt → rot |
| T8 | STALKER-2-Gespann: ausgenommene Mod behält `.pak`, `.ucas` **und** `.utoc` unbenannt | Merker pro Datei statt pro Mod ausgewertet → nur eine Endung betroffen → rot |
| T9 | Spiel ohne Nummerierung (Fallout 4): Merker ändert nichts, kein Fehler | neue Bedingung vor die Prüfung `if self._pak_load_order_prefix or …` gezogen → Ausnahmeweg läuft immer → rot |
| T10 | Verkabelung: `game_panel.py` reicht die Menge an den Deployer weiter (Textprüfung wie `tests/test_archive_load_order_wiring.py:29`) | Konstruktor-Parameter beim Deployer-Neubau vergessen → rot |
| T11 | Alle 7 Locale-Dateien enthalten die neuen Schlüssel | eine Sprache vergessen → rot |

Bestehende Tests, die **grün bleiben müssen** (Regression):
`tests/test_archiv_ladereihenfolge.py` vollständig,
`tests/test_pak_load_order_dirs.py` vollständig,
`tests/test_archive_load_order_wiring.py` vollständig.

---

## 6. Akzeptanz-Checkliste

- [ ] 1. Wenn der Anwender bei Cyberpunk 2077 auf eine Mod rechtsklickt,
      erscheint der abhakbare Eintrag „Dateinamen nicht ändern"; klickt er
      auf einen Trenner, erscheint er nicht.
- [ ] 2. Wenn der Anwender bei einem Spiel ohne Nummerierung (z. B.
      Fallout 4, Skyrim SE) auf eine Mod rechtsklickt, fehlt der Eintrag
      vollständig.
- [ ] 3. Wenn der Anwender den Eintrag anhakt, steht danach in
      `.mods/<Mod>/meta.ini` unter `[General]` die Zeile
      `keep_file_names = 1`.
- [ ] 4. Wenn der Anwender den Eintrag wieder abhakt, ist der Wert leer
      und die Mod wird beim nächsten Deploy wieder nummeriert.
- [ ] 5. Wenn der Anwender das Kontextmenü erneut öffnet, ist der Haken
      beim gesetzten Merker sichtbar gesetzt.
- [ ] 6. Wenn der Anwender nach dem Setzen ausrollt, liegt die `.archive`
      dieser Mod **ohne** Zifferpräfix im Spielordner, während die
      Archive aller anderen aktiven Mods weiterhin `000_`, `001_` … tragen.
- [ ] 7. Wenn der Anwender den Merker wieder entfernt und erneut ausrollt,
      trägt die Datei wieder ein Zifferpräfix.
- [ ] 8. Wenn der Anwender mit der Maus über den Namen einer ausgenommenen
      Mod fährt, erscheint ein Tooltip, der nennt: Dateinamen bleiben
      unverändert, Position in der Liste wirkt nicht mehr.
- [ ] 9. Wenn eine Mod ausgenommen ist, zeigt ihre Zeile in der Spalte
      „Markierungen" eine Kennzeichnung; bei allen anderen Mods bleibt die
      Spalte leer.
- [ ] 10. Wenn der Anwender den Mod-Ordner in Anvil umbenennt und dann
      ausrollt, ist die Mod immer noch ausgenommen.
- [ ] 11. Wenn der Anwender den Merker setzt, erscheint eine Zeile im
      Log-Bereich mit dem Mod-Namen.
- [ ] 12. Wenn der Anwender mehrere Mods auswählt und den Eintrag anklickt,
      wird der Merker bei allen ausgewählten Nicht-Trenner-Zeilen gesetzt.
- [ ] 13. Wenn ausgerollt wurde, enthält der Manifest-Eintrag der
      ausgenommenen Datei in `.deploy_manifest.json` **keinen** Schlüssel
      `unnumbered`.
- [ ] 14. Wenn die ausgenommene Mod eine Datei liefert, deren Name auch
      eine nummerierte Mod liefert, wird die ausgenommene Datei beim
      Ausrollen **nicht** gelöscht.
- [ ] 15. Wenn danach aufgeräumt wird (`purge`), ist die ausgenommene
      Datei wieder aus dem Spielordner verschwunden.
- [ ] 16. Wenn bei STALKER 2 eine Mod mit `.pak`/`.ucas`/`.utoc`
      ausgenommen wird, behalten alle drei Dateien ihren Namen.
- [ ] 17. Alle neuen `tr()`-Schlüssel liegen in **allen 7** Locale-Dateien
      (`de`, `en`, `es`, `fr`, `it`, `pt`, `ru`); die App zeigt in keiner
      Sprache einen rohen Schlüsselnamen.
- [ ] 18. Die bestehenden Tests `tests/test_archiv_ladereihenfolge.py`,
      `tests/test_pak_load_order_dirs.py` und
      `tests/test_archive_load_order_wiring.py` laufen unverändert grün.
- [ ] 19. Die neuen Tests aus 5.5 (T1–T11) laufen grün, und jede
      Mutationsprobe aus der Tabelle macht den zugehörigen Test rot.
- [ ] 20. Kein Spiel-Plugin wurde geändert: `GamePakLoadOrderDirs`,
      `GamePakLoadOrderPrefix`, `GamePakLoadOrderExtensions` und
      `GamePakLoadOrderFirstWins` haben in allen Plugins dieselben Werte
      wie vorher.
- [ ] 21. `./restart.sh` startet ohne Fehler (kein Traceback, kein
      `NameError`, `ImportError` oder `AttributeError` im Log).

---

## 7. Was ausdrücklich nicht getan wird

- **Keine Nummerierung für weitere Spiele einschalten.** Die Werte in
  `anvil/plugins/games/*.py` bleiben unverändert (Kriterium 20). Der
  Merker kann nur ausschalten, nie einschalten.
- **Die `.xl`-Dateien bleiben unberührt.** Sie werden heute schon durch
  `pak_load_order_name()` `:222-223` geschützt und sind durch
  `tests/test_archiv_ladereihenfolge.py:48-51` abgesichert. Gemessen:
  38 von 85 heißen anders als ihr Archiv und funktionieren
  (`docs/anvil-plan-reihenfolge-ehrlich.md:183-186`).
- **Kein BG3-Code.** `anvil/models/bg3_mod_list_model.py`,
  `anvil/core/lspk_parser.py` und der BG3-Deploy-Weg werden nicht
  angefasst (Projektregel).
- **Kein Eingriff in die Anzeige „Reihenfolge kommt nicht an"** — daran
  arbeitet jemand anderes; hier wurde nur gelesen.
- **Kein Cover-Bild, kein Icon, kein `redprelauncher`, kein REDmod.**
- **`pak_order_allows()` bekommt keinen neuen Parameter.** Drei Tests
  rufen sie direkt auf; die Ausnahme gehört auf Mod-Ebene, nicht in ein
  Pfad-Prädikat.
- **Collections tragen den Merker nicht mit** (siehe 2.3) — bewusste
  Auslassung, kein Versehen.

---

## UNSICHER

- **Wie REDengine tatsächlich sortiert.** Der Bericht sagt „alphabetisch,
  die erste gewinnt" und stützt sich auf drei Spielstarts
  (`anvil/plugins/base_game.py:170-172`,
  `docs/anvil-plan-reihenfolge-ehrlich.md:62-77`). Ob dabei streng nach
  ASCII sortiert wird (also Sonderzeichen wie `#` **vor** Ziffern), habe
  ich **nicht** gemessen. Die Folgerung in 3.4 (B) — dass eine
  ausgenommene Datei je nach Anfangszeichen vor oder hinter allen
  nummerierten landen kann — ist deshalb plausibel, aber nicht belegt.
- **Ob ein Loader wirklich am exakten Dateinamen hängt.** Die Warnung im
  Code (`anvil/plugins/base_game.py:146-148`) ist die einzige Quelle im
  Repository. Ein konkreter Fall einer Cyberpunk-Mod, die durch die
  Nummerierung kaputtgeht, ist nirgends dokumentiert — der Merker ist
  Vorsorge, kein gemessener Schaden.
- **Ob der Zeilen-Hintergrund doch besser wäre als die Markierungsspalte.**
  Das ist eine Geschmacksfrage für Marc, kein Code-Befund. Die Spalte
  `COL_MARKERS` ist belegbar leer (Beleg in 4.4), aber ob sie beim
  Anwender überhaupt eingeblendet ist, hängt an gespeicherten
  Spaltenbreiten, die ich nicht geprüft habe.
- **Ob `_sync_separator_deploy_paths()` an genau drei Stellen gerufen wird.**
  Gefunden: `anvil/mainwindow.py:2065`, `:3660`, `:5948`. Ob es weitere
  Wege in den Deploy gibt, die keinen dieser Punkte passieren (etwa
  Profilwechsel), habe ich nicht vollständig verfolgt — deshalb der
  Vorschlag, den Merker **zusätzlich** über den Konstruktor zu übergeben.
- **Verhalten bei „Mod neu installieren".** Dass die `meta.ini` dabei
  verlorengeht, folgere ich aus `anvil/core/mod_installer.py:252-259`
  (`shutil.move` + `create_default_meta_ini`). Den Ablauf von
  `_ctx_reinstall_mod` (`anvil/mainwindow.py:5039`) habe ich nicht Zeile
  für Zeile durchgelesen.
