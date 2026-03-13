---
description: Startet 4 parallele Planer-Agents für Analyse, Architektur und Feature-Spec. Ändert KEINEN Code. Erwartet eine Aufgabenbeschreibung als Argument.
---

STOP — Prüfe zuerst ob eine Aufgabe angegeben wurde.

Wenn "$ARGUMENTS" leer ist oder nur Whitespace enthält:
→ Frage Marc: "Was soll geplant werden?"
→ Starte KEINE Agents bis Marc geantwortet hat.

Wenn "$ARGUMENTS" eine Aufgabe enthält:
→ Dann starte die 4 Agents wie unten beschrieben.

---

Aufgabe: $ARGUMENTS

Spawne **4 parallele Sub-Agents** aus `.claude/agents/planer.md`, jeder mit eigenem Fokus:

**Agent 1 — Anvil Code-Analyse:**
- Bestehenden Code in `anvil/` lesen (Read, Grep, Glob)
- Betroffene Dateien, Klassen, Funktionen identifizieren
- Signal/Slot-Flow nachverfolgen
- Findings nach `docs/workflow/planer-agent-1.md`

**Agent 2 — MO2-Referenz + Verwandte Funktionen:**
- MO2-Referenzcode lesen: `/home/mob/Projekte/mo2-referenz/`
- Verwandte Funktionen im Anvil-Code suchen
- Findings nach `docs/workflow/planer-agent-2.md`

**Agent 3 — Architektur & Risiken:**
- Architektur-Auswirkungen analysieren
- Signal/Slot-Verbindungen prüfen
- Wayland-Probleme, Qt-Antipatterns, GC-Gefahren
- Edge Cases sammeln
- Findings nach `docs/workflow/planer-agent-3.md`

**Agent 4 — Feature-Spec & Checkliste:**
- Liest die Reports von Agent 1-3
- Schreibt die finale Feature-Spec nach `docs/anvil-feature-[name].md`
- Erstellt Akzeptanz-Checkliste mit mindestens 8 testbaren Kriterien
- Format: "Wenn User X tut, passiert Y"
- Letzter Punkt IMMER: `restart.sh startet ohne Fehler`

REGELN:
- ALLE 4 Agents: NUR LESEN — niemals Code ändern
- Keine Rückfragen an Marc — selbst im Code nachschauen
- Agents 1-3 laufen parallel, Agent 4 wartet auf deren Ergebnisse
- Sprache: DEUTSCH
- NIEMALS Cover-Bilder, Icons, redprelauncher, REDmod anfassen
