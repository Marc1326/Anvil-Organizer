---
description: Startet 4 parallele QA-Prüfer für Code-Review und funktionale Tests. Ändert KEINEN Code. Erwartet eine Aufgabenbeschreibung als Argument.
---

STOP — Prüfe zuerst ob eine Aufgabe angegeben wurde.

Wenn "$ARGUMENTS" leer ist oder nur Whitespace enthält:
→ Frage Marc: "Was soll geprüft werden?"
→ Starte KEINE Agents bis Marc geantwortet hat.

Wenn "$ARGUMENTS" eine Aufgabe enthält:
→ Dann starte die 4 Agents wie unten beschrieben.

---

Aufgabe: $ARGUMENTS

Spawne **4 parallele Sub-Agents**, jeder prüft unabhängig:

**Agent 1 — Code-Review (aus `.claude/agents/qa-pruefer.md`):**
- `git diff` lesen, alle geänderten Dateien prüfen
- Python: Logikfehler, None-Zugriffe, fehlende Exception-Handling
- Qt: Fehlende Parents, Widget-Leaks, Signal/Slot-Probleme
- Findings nach `docs/workflow/qa-agent-1.md`
- Erste Zeile: `ACCEPTED` oder `DENIED`

**Agent 2 — Issue-Verifikation:**
- Ist der ursprüngliche Bug wirklich gefixt?
- Wurde NUR das Minimum geändert?
- Findings nach `docs/workflow/qa-agent-2.md`
- Erste Zeile: `ACCEPTED` oder `DENIED`

**Agent 3 — Funktionaler Test:**
- `pkill -f "python.*main.py" && sleep 1` dann `./restart.sh` ausführen
- Prüfe Terminal-Output auf Fehler, Tracebacks, Warnungen
- Findings nach `docs/workflow/qa-agent-3.md`
- Erste Zeile: `ACCEPTED` oder `DENIED`

**Agent 4 — Checklisten-Abgleich + UI-Prüfung:**
- Akzeptanz-Checkliste lesen (aus `docs/workflow/checkliste.md` oder `docs/anvil-feature-*.md`)
- JEDEN Punkt einzeln prüfen: ✅ oder ❌
- Feature nur UI ohne Backend-Logik? → ❌
- QSettings gespeichert aber nirgends gelesen? → ❌
- Interne IDs/Pfade im UI sichtbar statt aufgelöst? → ❌
- Test-Daten im Code oder in Config-Dateien? → ❌
- Hardcodierte Farben statt QSS-Variablen? → ❌
- Findings nach `docs/workflow/qa-agent-4.md`
- Erste Zeile: `ACCEPTED` oder `DENIED`

REGELN:
- ALLE 4 Agents: NUR LESEN — niemals Code ändern
- Alle 4 müssen `ACCEPTED` haben — sonst NEEDS FIXES
- Jeder Agent prüft UNABHÄNGIG — liest NICHT die Reports der anderen
- Sprache: DEUTSCH
- NIEMALS Cover-Bilder, Icons, redprelauncher, REDmod anfassen

Nach Abschluss aller 4 Agents: Zusammenfassung schreiben nach `docs/workflow/qa-summary.md`
- Alle 4 ACCEPTED → READY FOR COMMIT
- Mindestens 1 DENIED → NEEDS FIXES mit Liste der Probleme
