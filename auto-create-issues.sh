#!/usr/bin/env bash
# auto-create-issues.sh — Anvil Organizer
# Legt die bekannten v0.3.0 Bugs als GitHub Issues an.
# Voraussetzung: gh CLI installiert + authentifiziert
#
# Verwendung: ./auto-create-issues.sh

set -e

GREEN='\033[0;32m'
YELLOW='\033[1;33m'
RED='\033[0;31m'
NC='\033[0m'

echo -e "${YELLOW}📋 Anvil Organizer — GitHub Issues anlegen${NC}"
echo ""

if ! command -v gh &>/dev/null; then
  echo -e "${RED}❌ gh CLI nicht gefunden.${NC}"
  exit 1
fi

if ! gh auth status &>/dev/null; then
  echo -e "${RED}❌ gh nicht authentifiziert. Ausführen: gh auth login${NC}"
  exit 1
fi

EXISTING=$(gh issue list --label bug --json title --jq '.[].title' 2>/dev/null || echo "")

create_issue_if_not_exists() {
  local title="$1"
  local body="$2"
  if echo "$EXISTING" | grep -qF "$title"; then
    echo -e "${YELLOW}⏭️  Existiert bereits: $title${NC}"
  else
    gh issue create --title "$title" --body "$body" --label bug
    echo -e "${GREEN}✅ Erstellt: $title${NC}"
  fi
}

create_issue_if_not_exists \
  "Bug: Mod aus Download-Tab in Separator installiert unten statt im Separator" \
  "## Problem
Wenn ein Mod aus dem Download-Tab per Drag & Drop in einen Separator gezogen wird,
wird er am Ende der Liste installiert statt innerhalb des Separators.

## Definition of Done
- [ ] Mod wird korrekt innerhalb des Ziel-Separators installiert
- [ ] ./restart.sh startet ohne Fehler"

create_issue_if_not_exists \
  "Bug: Deaktivierter Mod zeigt noch Konflikte an" \
  "## Problem
Mods die deaktiviert sind sollten keine Konflikte anzeigen —
deaktivierte Mods sind nicht aktiv und können keine Konflikte verursachen.

## Definition of Done
- [ ] Deaktivierte Mods zeigen keine Konflikt-Markierungen
- [ ] ./restart.sh startet ohne Fehler"

create_issue_if_not_exists \
  "Bug: Download-Tab versteckt bereits installierte Mods nicht vollständig" \
  "## Problem
Im Download-Tab werden Mods angezeigt die bereits installiert sind.
Bereits installierte Mods sollen ausgeblendet oder klar markiert werden.

## Definition of Done
- [ ] Bereits installierte Mods werden im Download-Tab ausgeblendet/markiert
- [ ] ./restart.sh startet ohne Fehler"

create_issue_if_not_exists \
  "Bug: NXM-Download öffnet neue Anvil-Instanz statt vorhandene zu nutzen" \
  "## Problem
Wenn ein NXM-Link geklickt wird während Anvil bereits läuft,
wird eine zweite Anvil-Instanz geöffnet statt den Download in der vorhandenen zu starten.

## Definition of Done
- [ ] NXM-Links werden von der laufenden Instanz verarbeitet
- [ ] Keine zweite Instanz wird geöffnet
- [ ] ./restart.sh startet ohne Fehler"

create_issue_if_not_exists \
  "Bug: Mod aktiviert sich sofort nach Installation statt deaktiviert zu bleiben" \
  "## Problem
Nach der Installation eines Mods wird dieser sofort aktiviert.
Neue Mods sollen standardmäßig deaktiviert installiert werden.

## Definition of Done
- [ ] Neu installierte Mods sind standardmäßig deaktiviert
- [ ] ./restart.sh startet ohne Fehler"

echo ""
echo -e "${GREEN}✅ Fertig.${NC}"
echo -e "Issues anzeigen: ${YELLOW}gh issue list --label bug${NC}"
echo -e "Workflow starten: ${YELLOW}./auto-develop.sh${NC}"
