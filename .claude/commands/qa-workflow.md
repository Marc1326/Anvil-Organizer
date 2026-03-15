---
description: Startet den kompletten Workflow-Loop mit GitHub Issues — Issue erstellen → Planer → Dev → 4x Review → fertig oder Sub-Issue + zurück zu Dev. Erwartet eine Aufgabenbeschreibung als Argument.
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

Der Workflow orchestriert automatisch mit GitHub Issues:
1. **GitHub Issue** erstellen (oder bestehendes lesen wenn Issue-Nummer angegeben)
2. **Planer** (`.claude/agents/planer.md`) → Analyse + Feature-Spec + Checkliste → als Issue-Kommentar
3. **Dev** (`.claude/agents/frontend-dev.md` / `.claude/agents/backend-dev.md`) → Branch + Implementierung
4. **4x Review** (Codex x2 + Claude x2) → Unabhängige Prüfung gegen Checkliste
5. **Entscheidung:**
   - ALLE 4 ACCEPTED → Commit + PR erstellen → Marc informieren → nach Merge Issues schließen
   - Mind. 1 DENIED → Sub-Issue erstellen mit Findings → zurück zu Schritt 3
   - Loop bis ALLE Agents sich einig sind

REGELN:
- Max 10 Loops, dann Statusmeldung an Marc
- GitHub Issues als Tracker — kein Fix ohne Issue
- Kommunikation über Dateien in `docs/workflow/` + Issue-Kommentare
- NIEMALS Marc zwischendurch fragen
- NIEMALS Cover-Bilder, Icons, redprelauncher, REDmod anfassen
- Sprache: DEUTSCH
- Vor dem ersten Code-Change: `git stash` als Sicherheitsnetz
