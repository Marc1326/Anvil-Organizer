#!/usr/bin/env bash
# auto-develop.sh — Anvil Organizer Multi-Agent Development Loop
# Adaptiert von TheMorpheus407/the-dmz
#
# Voraussetzungen:
#   - gh CLI installiert und authentifiziert
#   - claude CLI installiert
#   - Sauberes Git Working Tree
#
# Verwendung:
#   ./auto-develop.sh           # Alle offenen Issues
#   ./auto-develop.sh 42        # Nur Issue #42

set -euo pipefail

REPO_ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
LOGS_DIR="$REPO_ROOT/logs/issues"
MAX_REVIEW_LOOPS=3

RED='\033[0;31m'
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
BLUE='\033[0;34m'
NC='\033[0m'

log()     { echo -e "${BLUE}[auto-develop]${NC} $1"; }
success() { echo -e "${GREEN}[auto-develop]${NC} $1"; }
warn()    { echo -e "${YELLOW}[auto-develop]${NC} $1"; }
error()   { echo -e "${RED}[auto-develop]${NC} $1"; exit 1; }

check_prerequisites() {
    command -v gh     >/dev/null 2>&1 || error "gh CLI nicht gefunden."
    command -v claude >/dev/null 2>&1 || error "claude CLI nicht gefunden."
    [[ -z "$(git -C "$REPO_ROOT" status --porcelain)" ]] || \
        error "Working Tree nicht sauber. Bitte committen oder stashen."
    log "Voraussetzungen OK"
}

fetch_issue() {
    local issue_number="$1"
    local issue_dir="$LOGS_DIR/$issue_number"
    mkdir -p "$issue_dir"
    gh issue view "$issue_number" --json number,title,body,labels,comments \
        > "$issue_dir/issue.json"
    log "Issue #$issue_number: $(jq -r '.title' "$issue_dir/issue.json")"
}

run_research() {
    local issue_number="$1"
    local issue_dir="$LOGS_DIR/$issue_number"
    log "Research Agent läuft für Issue #$issue_number..."

    claude --print \
        --system-prompt "$(cat "$REPO_ROOT/.claude/agents/planer.md")" \
        "Lies SOUL.md, AGENTS.md, MEMORY.md, CLAUDE.md.

Analysiere dieses GitHub Issue für Anvil Organizer (Python/PySide6):
$(cat "$issue_dir/issue.json")

Schreibe research.md mit:
1. Zusammenfassung des Problems
2. Betroffene Python-Dateien (mit Pfaden)
3. Vermutete Ursache (Qt-Signal, Drag&Drop, State-Management?)
4. Lösungsansatz
5. Nebeneffekte / Risiken

Schreibe NUR die research.md, keinen Code." \
        > "$issue_dir/research.md"

    success "Research → $issue_dir/research.md"
}

run_implementation() {
    local issue_number="$1"
    local issue_dir="$LOGS_DIR/$issue_number"
    log "Implementer Agent läuft für Issue #$issue_number..."

    local branch_name="issue-${issue_number}-$(jq -r '.title | ascii_downcase | gsub("[^a-z0-9]+"; "-") | .[0:40]' "$issue_dir/issue.json")"
    git -C "$REPO_ROOT" checkout -b "$branch_name" 2>/dev/null || git -C "$REPO_ROOT" checkout "$branch_name"

    claude --print \
        "Lies SOUL.md, AGENTS.md, MEMORY.md, CLAUDE.md.

Issue: $(cat "$issue_dir/issue.json")
Research: $(cat "$issue_dir/research.md")

Implementiere die Lösung für Anvil Organizer (Python/PySide6). Dann:
1. Führe python -m py_compile auf alle geänderten Dateien aus
2. Führe ./restart.sh aus und prüfe das Log auf Fehler
3. Committe NICHT

Schreibe implementation.md: was geändert, wie gelöst, fehlende Tests." \
        > "$issue_dir/implementation.md"

    success "Implementation → $issue_dir/implementation.md"
}

run_review() {
    local issue_number="$1"
    local review_number="$2"
    local review_type="$3"
    local issue_dir="$LOGS_DIR/$issue_number"
    local review_file="$issue_dir/review-${review_number}.md"
    log "Reviewer $review_number ($review_type)..."

    local focus
    if [[ "$review_type" == "correctness" ]]; then
        focus="Du bist Reviewer A. Prüfe KORREKTHEIT: Python-Syntax, Qt-Signale, Drag&Drop-Logic, keine hardcoded Pfade, keine setStyleSheet() in neuen Widgets."
    else
        focus="Du bist Reviewer B. Prüfe ISSUE-ABDECKUNG: vollständig gelöst? tr()-Keys in allen 6 Sprachen? ./restart.sh ohne Fehler?"
    fi

    claude --print \
        --system-prompt "$(cat "$REPO_ROOT/.claude/agents/qa-pruefer.md")" \
        "$focus

Issue: $(cat "$issue_dir/issue.json")
Research: $(cat "$issue_dir/research.md")
Implementation: $(cat "$issue_dir/implementation.md")

Code-Änderungen:
$(git -C "$REPO_ROOT" diff HEAD)

ERSTE ZEILE muss 'ACCEPTED' oder 'DENIED' sein.
Schreibe Findings in $review_file." \
        > "$review_file"

    head -1 "$review_file" | tr -d '[:space:]'
}

run_implementation_with_feedback() {
    local issue_number="$1"
    local issue_dir="$LOGS_DIR/$issue_number"

    claude --print \
        "Die vorherige Implementation wurde abgelehnt. Überarbeite:

Issue: $(cat "$issue_dir/issue.json")
Research: $(cat "$issue_dir/research.md")
Vorherige Implementation: $(cat "$issue_dir/implementation.md")
Review A: $(cat "$issue_dir/review-1.md")
Review B: $(cat "$issue_dir/review-2.md")

Führe danach python -m py_compile und ./restart.sh aus. Committe NICHT." \
        >> "$issue_dir/implementation.md"
}

process_issue() {
    local issue_number="$1"
    log "========================================="
    log "Verarbeite Issue #$issue_number"
    log "========================================="

    fetch_issue "$issue_number"
    run_research "$issue_number"
    run_implementation "$issue_number"

    local loop=0
    while [[ $loop -lt $MAX_REVIEW_LOOPS ]]; do
        loop=$((loop + 1))
        log "Review-Loop $loop/$MAX_REVIEW_LOOPS"

        local verdict_a verdict_b
        verdict_a=$(run_review "$issue_number" "1" "correctness")
        verdict_b=$(run_review "$issue_number" "2" "coverage")

        log "Reviewer A: $verdict_a"
        log "Reviewer B: $verdict_b"

        if [[ "$verdict_a" == "ACCEPTED" && "$verdict_b" == "ACCEPTED" ]]; then
            success "Beide Reviewer: ACCEPTED"
            local commit_msg="Issue #${issue_number}: $(jq -r '.title' "$LOGS_DIR/$issue_number/issue.json")"
            git -C "$REPO_ROOT" add -A
            git -C "$REPO_ROOT" commit -m "$commit_msg"
            git -C "$REPO_ROOT" push origin HEAD
            gh issue close "$issue_number" --comment "Implementiert: $(git -C "$REPO_ROOT" rev-parse HEAD)"
            success "Issue #$issue_number abgeschlossen!"
            return 0
        else
            warn "DENIED — überarbeite..."
            run_implementation_with_feedback "$issue_number"
        fi
    done

    error "Issue #$issue_number nach $MAX_REVIEW_LOOPS Loops nicht gelöst."
}

main() {
    cd "$REPO_ROOT"
    check_prerequisites

    if [[ $# -eq 1 ]]; then
        process_issue "$1"
    else
        log "Verarbeite alle offenen Issues..."
        local issues
        issues=$(gh issue list --state open --json number --jq '.[].number')
        [[ -n "$issues" ]] || { success "Keine offenen Issues."; exit 0; }
        while IFS= read -r issue_number; do
            process_issue "$issue_number"
        done <<< "$issues"
        success "Alle Issues verarbeitet!"
    fi
}

main "$@"
