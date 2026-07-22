# QA Review — i18n / Übersetzungen — Agent 3
Commit: 38ba7ba — "fix: kein Absturz mehr wenn Spiel-/Downloads-Pfad fehlt"
Key: toast.game_path_missing
Datum: 2026-06-29

## Prüfumfang
Nur i18n-Anteile des Bugfix. Nur gelesen, kein Code geändert.

## Ergebnis je Prüfpunkt

### 1. Key in ALLEN 7 Locales vorhanden? — OK
Per `json.load` real eingelesen. `toast.game_path_missing` ist in de, en, es, fr, it, pt, ru vorhanden (alle Zeile 527, im Objekt "toast").

### 2. Richtiges Eltern-Objekt "toast"? — OK
In allen 7 Dateien liegt der Key verschachtelt unter dem Objekt "toast".
Kein Top-Level-Key mit Punkt im Namen ("toast.game_path_missing" als Flat-Key) — explizit geprüft, in keiner Datei vorhanden.

### 3. Alle 7 JSON valide/parsebar? — OK
Alle 7 Dateien parsen fehlerfrei. Duplicate-Key-Scan via object_pairs_hook: keine doppelten Keys.

### 4. Korrekter Aufruf im Code? — OK
anvil/mainwindow.py:1194 → `Toast(self, tr("toast.game_path_missing"))`.
- Key-String identisch mit JSON-Pfad, kein Tippfehler.
- `Toast` importiert (mainwindow.py:49), `tr` importiert (mainwindow.py:86).
- translator.tr (translator.py:80/108) splittet bei "." und löst verschachtelt auf → "toast.game_path_missing" wird korrekt aufgelöst. Fallback: EN, dann Key selbst.
- Kein Roh-Key (kein f-String, keine Formatvariablen nötig — der Text hat keine Platzhalter).
- Guard `if game_path is None and game_path_str:` (Zeile 1193) ist plausibel; `game_path_str` ist in Scope (Zeile 1167).

### 5. Übersetzungen inhaltlich plausibel? — überwiegend OK, 2x LOW
Inhaltlich korrekt und in der jeweils richtigen Sprache, kein Copy-Paste-Fehler:
- de: "Spielpfad nicht gefunden — bitte in den Einstellungen anpassen."
- en: "Game path not found — please update it in settings."
- es: "No se encontró la ruta del juego — ajústala en los ajustes."
- fr: "Chemin du jeu introuvable — modifiez-le dans les paramètres."
- it: "Percorso del gioco non trovato — modificalo nelle impostazioni."
- pt: "Caminho do jogo não encontrado — ajuste-o nas configurações."
- ru: "Путь к игре не найден — измените его в настройках."

### 6. Andere Keys versehentlich verändert/verschoben? — OK
`git show` Diff: pro Datei nur (a) Komma an "delete_error" angehängt und (b) eine neue Zeile eingefügt. Keine anderen Keys verschoben, gelöscht oder verändert.

## Findings

### [LOW] Terminologie-Inkonsistenz "settings" — Spanisch (es)
- Datei: anvil/locales/es.json:527
- Problem: Neuer Text verweist auf "los ajustes", aber das Einstellungs-Menü der App heißt durchgehend "Configuración" (es.json /menu/settings = "Configuración...", /dialog/settings_title = "Configuración"). Nutzer sucht im Menü nach "Configuración", der Toast sagt "ajustes".
- Fix (Empfehlung): "...ajústala en la configuración." für Konsistenz mit dem Menünamen.
- Schweregrad: kosmetisch, blockiert nichts.

### [LOW] Terminologie-Inkonsistenz "settings" — Portugiesisch (pt)
- Datei: anvil/locales/pt.json:527
- Problem: Neuer Text verweist auf "nas configurações" (eher BR-PT), aber das Einstellungs-Menü heißt "Definições" (pt.json /menu/settings = "Definições...", /dialog/settings_title = "Definições", EU-PT). Inkonsistente Begriffswahl gegenüber dem Menünamen.
- Fix (Empfehlung): "...ajuste-o nas definições." passend zum Menünamen "Definições".
- Schweregrad: kosmetisch. Hinweis: pt.json ist generell gemischt (fw_detect nutzt "Configuracoes"), daher nur LOW.

## Fazit
i18n-Anteil ist technisch sauber: Key vollständig in allen 7 Locales, korrekt unter "toast" verschachtelt, alle Dateien valide, korrekter tr()-Aufruf ohne Tippfehler, keine Kollateralschäden an anderen Keys. Nur zwei LOW-Terminologie-Hinweise (es/pt). Keine CRITICAL/HIGH/MEDIUM Findings.

READY FOR COMMIT (mit 2 optionalen LOW-Verbesserungen)
