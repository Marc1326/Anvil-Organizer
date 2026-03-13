---
description: Startet den kompletten Workflow-Loop — Planer → Dev → 4x QA-Review → fertig oder zurück zu Dev. Erwartet eine Aufgabenbeschreibung als Argument.
---

STOP — Prüfe zuerst ob eine Aufgabe angegeben wurde.

Wenn "$ARGUMENTS" leer ist oder nur Whitespace enthält:
→ Frage Marc: "Was soll gebaut/gefixt werden?"
→ Starte den Workflow NICHT bis Marc geantwortet hat.

Wenn "$ARGUMENTS" eine Aufgabe enthält:
→ Dann starte den Workflow wie unten beschrieben.

---

Starte den Workflow-Agent aus `.claude/agents/workflow.md`.

Aufgabe: $ARGUMENTS

Der Workflow orchestriert automatisch:
1. **Planer** (`.claude/agents/planer.md`) → Analyse + Feature-Spec + Checkliste
2. **Dev** (`.claude/agents/frontend-dev.md` und/oder `.claude/agents/backend-dev.md`) → Implementierung
3. **4x QA-Review** (`.claude/agents/qa-pruefer.md`) → 4 parallele Agents, unabhängige Prüfung
4. **Entscheidung** → Alle ACCEPTED? → Commit-Meldung an Marc. Einer DENIED? → Zurück zu Schritt 2.

REGELN:
- Max 5 Loops, dann Statusmeldung an Marc
- Kommunikation über Dateien in `docs/workflow/`
- NIEMALS Marc zwischendurch fragen
- NIEMALS Cover-Bilder, Icons, redprelauncher, REDmod anfassen
- Sprache: DEUTSCH
- Vor dem ersten Code-Change: `git stash` als Sicherheitsnetz
