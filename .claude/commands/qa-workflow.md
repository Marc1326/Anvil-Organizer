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

## ⚠️ Terminierungs-Invariante (nicht verhandelbar)
Der Workflow darf NUR enden, wenn **maschinenprüfbar** gilt:
```bash
ACCEPTED=$(grep -l "^ACCEPTED" docs/workflow/qa-agent-*.md | wc -l)
DENIED=$(grep -l "^DENIED" docs/workflow/qa-agent-*.md | wc -l)
REPORTS=$(ls docs/workflow/qa-agent-*.md 2>/dev/null | wc -l)
VERIFY=$(head -1 docs/workflow/final-verify-*.md 2>/dev/null | tail -1)
# DONE nur wenn: ACCEPTED=4, DENIED=0, REPORTS=4, VERIFY=BUG_GONE
# ODER: iteration.count >= 10 → UNRESOLVED
```
Selbst-Einschätzung „ist ok" ist ungültig. Graufälle („ACCEPTED mit Vorbehalt") zählen als DENIED.

## Workflow-Ablauf

**Initialisierung:** `rm -f docs/workflow/iteration.count docs/workflow/qa-agent-*.md docs/workflow/final-verify-*.md docs/workflow/dev-handoff-*.md`

1. **GitHub Issue** erstellen (oder bestehendes lesen wenn Issue-Nummer angegeben)
2. **Planer** (`.claude/agents/planer.md`) → Analyse + Feature-Spec + Checkliste → als Issue-Kommentar
3. **Dev** (`.claude/agents/frontend-dev.md` / `.claude/agents/backend-dev.md`) → Branch + Implementierung
   - Bei Iteration N>1: Dev arbeitet **ausschließlich** gegen `docs/workflow/dev-handoff-(N-1).md`
4. **Alte Reports löschen:** `rm -f docs/workflow/qa-agent-*.md docs/workflow/final-verify-*.md`
5. **4x Review** parallel — jeder Agent schreibt Report mit erster Zeile `ACCEPTED` oder `DENIED`
6. **Final-Verify** — Bug noch reproduzierbar? → `docs/workflow/final-verify-N.md` erste Zeile `BUG_GONE` oder `BUG_STILL_THERE`
7. **Entscheidung (maschinell):**
   - `ACCEPTED=4 && DENIED=0 && REPORTS=4 && VERIFY=BUG_GONE` → **DONE**: Commit + PR → Marc informieren
   - sonst → Iteration hochzählen, `dev-handoff-N.md` mit allen DENIED-Findings schreiben, zurück zu Schritt 3
8. **Abbruch** wenn `iteration.count ≥ 10`: Status `UNRESOLVED`, Issue bleibt OFFEN, Marc wird benachrichtigt

## Regeln
- Iteration-Counter in `docs/workflow/iteration.count` persistieren — nicht im Speicher
- GitHub Issues als Tracker — kein Fix ohne Issue
- Kommunikation über Dateien in `docs/workflow/` + Issue-Kommentare
- NIEMALS Marc zwischendurch fragen (außer bei Abbruch nach 10 Iterationen)
- NIEMALS Cover-Bilder, Icons, redprelauncher, REDmod anfassen
- Sprache: DEUTSCH
- Vor dem ersten Code-Change: `git stash` als Sicherheitsnetz
- Fehlender/abgestürzter Agent-Report = DENIED, Agent neu starten
