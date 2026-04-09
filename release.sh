#!/bin/bash
# Release-Script für Anvil Organizer
# Usage: ./release.sh 1.4.5
#
# Macht automatisch:
# 1. Version-Bump in allen Dateien
# 2. Commit + Push
# 3. Git Tag + Push → triggert GitHub Actions
# 4. GitHub Actions bauen AppImage, .deb, RPM, Snap und erstellen das Release

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
echo "[1/3] Version-Bump auf $VERSION ..."

# anvil/version.py
sed -i "s/^APP_VERSION = .*/APP_VERSION = \"${VERSION}\"/" anvil/version.py

# pyproject.toml
sed -i "s/^version = .*/version = \"${VERSION}\"/" pyproject.toml

# build-appimage.sh
sed -i "s/^VERSION=.*/VERSION=\"${VERSION}\"/" build-appimage.sh

# packaging/rpm/anvil-organizer.spec
sed -i "s/^Version:.*/Version:        ${VERSION}/" packaging/rpm/anvil-organizer.spec

# packaging/snap/snapcraft.yaml
sed -i "s/^version:.*/version: '${VERSION}'/" packaging/snap/snapcraft.yaml

echo "  ✓ anvil/version.py"
echo "  ✓ pyproject.toml"
echo "  ✓ build-appimage.sh"
echo "  ✓ packaging/rpm/anvil-organizer.spec"
echo "  ✓ packaging/snap/snapcraft.yaml"

# --- 2. Commit + Push ---
echo ""
echo "[2/3] Commit + Push ..."
git add anvil/version.py pyproject.toml build-appimage.sh \
    packaging/rpm/anvil-organizer.spec packaging/snap/snapcraft.yaml
git commit -m "$TAG"
git push origin main

echo "  ✓ Commit gepusht"

# --- 3. Tag + Push ---
echo ""
echo "[3/3] Tag $TAG erstellen + pushen ..."
git tag "$TAG"
git push origin "$TAG"

echo "  ✓ Tag $TAG gepusht"

echo ""
echo "========================================="
echo "  Release $TAG gestartet!"
echo ""
echo "  GitHub Actions bauen jetzt:"
echo "    • AppImage + .deb  (appimage.yml)"
echo "    • RPM              (rpm.yml)"
echo "    • Snap             (snap.yml)"
echo "    • Flatpak          (flatpak.yml)"
echo ""
echo "  Status: gh run list"
echo "  Release: https://github.com/Marc1326/Anvil-Organizer/releases/tag/$TAG"
echo "========================================="
