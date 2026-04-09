#!/bin/bash
# Release-Script für Anvil Organizer
# Usage: ./release.sh 1.4.5
#
# Macht automatisch:
# 1. Version-Bump in allen Dateien
# 2. Commit + Push
# 3. Git Tag + Push → triggert GitHub Actions
# 4. Wartet bis alle Builds fertig sind
# 5. Publiziert das Draft-Release → triggert Flatpak-Build

set -euo pipefail

if [ $# -ne 1 ]; then
    echo "Usage: ./release.sh <VERSION>"
    echo "Beispiel: ./release.sh 1.4.5"
    exit 1
fi

VERSION="$1"
TAG="v${VERSION}"

# Prüfen ob wir im richtigen Verzeichnis sind
if [ ! -f "anvil/version.py" ]; then
    echo "Fehler: anvil/version.py nicht gefunden. Bitte aus dem Projekt-Root ausführen."
    exit 1
fi

# Prüfen ob Tag schon existiert
if git rev-parse "$TAG" >/dev/null 2>&1; then
    echo "Fehler: Tag $TAG existiert bereits!"
    exit 1
fi

# Prüfen ob es uncommitted changes gibt
if [ -n "$(git diff --cached --name-only)" ]; then
    echo "Fehler: Es gibt staged changes. Bitte zuerst committen oder resetten."
    exit 1
fi

echo "========================================="
echo "  Anvil Organizer Release $TAG"
echo "========================================="
echo ""

# --- 1. Version-Bump ---
echo "[1/5] Version-Bump auf $VERSION ..."

sed -i "s/^APP_VERSION = .*/APP_VERSION = \"${VERSION}\"/" anvil/version.py
sed -i "s/^version = .*/version = \"${VERSION}\"/" pyproject.toml
sed -i "s/^VERSION=.*/VERSION=\"${VERSION}\"/" build-appimage.sh
sed -i "s/^Version:.*/Version:        ${VERSION}/" packaging/rpm/anvil-organizer.spec
sed -i "s/^version:.*/version: '${VERSION}'/" packaging/snap/snapcraft.yaml

echo "  ✓ anvil/version.py"
echo "  ✓ pyproject.toml"
echo "  ✓ build-appimage.sh"
echo "  ✓ packaging/rpm/anvil-organizer.spec"
echo "  ✓ packaging/snap/snapcraft.yaml"

# --- 2. Commit + Push ---
echo ""
echo "[2/5] Commit + Push ..."
git add anvil/version.py pyproject.toml build-appimage.sh \
    packaging/rpm/anvil-organizer.spec packaging/snap/snapcraft.yaml
git commit -m "$TAG"
git push origin main
echo "  ✓ Commit gepusht"

# --- 3. Tag + Push ---
echo ""
echo "[3/5] Tag $TAG erstellen + pushen ..."
git tag "$TAG"
git push origin "$TAG"
echo "  ✓ Tag gepusht — GitHub Actions gestartet"

# --- 4. Warten auf Builds ---
echo ""
echo "[4/5] Warte auf GitHub Actions ..."
echo "  Workflows: Build AppImage, Build .rpm Package, Build & Publish Snap"
echo ""

# Warte bis alle 3 Workflows für diesen Tag gestartet sind
sleep 10

WORKFLOWS=("Build AppImage" "Build .rpm Package" "Build & Publish Snap")
ALL_DONE=false

while [ "$ALL_DONE" = false ]; do
    ALL_DONE=true
    for WF in "${WORKFLOWS[@]}"; do
        STATUS=$(gh run list --workflow="$WF" --limit 1 --json status,headBranch \
            --jq ".[0] | select(.headBranch==\"$TAG\") | .status" 2>/dev/null || echo "unknown")

        if [ "$STATUS" = "completed" ]; then
            # Prüfe ob erfolgreich
            CONCLUSION=$(gh run list --workflow="$WF" --limit 1 --json conclusion,headBranch \
                --jq ".[0] | select(.headBranch==\"$TAG\") | .conclusion" 2>/dev/null || echo "unknown")
            if [ "$CONCLUSION" = "success" ]; then
                echo "  ✓ $WF"
            else
                echo "  ✗ $WF (fehlgeschlagen)"
            fi
        elif [ "$STATUS" = "in_progress" ] || [ "$STATUS" = "queued" ] || [ "$STATUS" = "waiting" ]; then
            echo "  ⏳ $WF ($STATUS)"
            ALL_DONE=false
        else
            echo "  ? $WF (Status: $STATUS)"
            ALL_DONE=false
        fi
    done

    if [ "$ALL_DONE" = false ]; then
        sleep 30
        echo ""
    fi
done

echo ""

# --- 5. Release publizieren ---
echo "[5/5] Draft-Release publizieren ..."
gh release edit "$TAG" --draft=false
echo "  ✓ Release $TAG ist live!"
echo "  → Flatpak-Build wird jetzt automatisch gestartet"

echo ""
echo "========================================="
echo "  Release $TAG abgeschlossen!"
echo ""
echo "  Assets:"
gh release view "$TAG" --json assets --jq '.assets[].name' 2>/dev/null | sed 's/^/    • /'
echo ""
echo "  https://github.com/Marc1326/Anvil-Organizer/releases/tag/$TAG"
echo "========================================="
