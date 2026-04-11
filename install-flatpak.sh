#!/bin/bash
# Anvil Organizer — Flatpak Installer/Updater
# Downloads the latest .flatpak bundle from GitHub and installs it
#
# Usage:
#   chmod +x install-flatpak.sh
#   ./install-flatpak.sh
#
# Or one-liner:
#   curl -sSL https://raw.githubusercontent.com/Marc1326/Anvil-Organizer/main/install-flatpak.sh | bash

set -e

REPO="Marc1326/Anvil-Organizer"
RELEASES_API_URL="https://api.github.com/repos/${REPO}/releases/latest"
APP_ID="com.github.Marc1326.AnvilOrganizer"
BUNDLE_NAME="anvil-organizer.flatpak"

echo "========================================"
echo "  Anvil Organizer — Flatpak Install"
echo "========================================"
echo ""

# ── Fetch latest release info ───────────────────────────────
echo "[..] Checking for latest version..."
if command -v curl &>/dev/null; then
    JSON="$(curl -sL "$RELEASES_API_URL")"
elif command -v wget &>/dev/null; then
    JSON="$(wget -qO- "$RELEASES_API_URL")"
else
    echo "ERROR: Neither curl nor wget found. Please install one of them."
    exit 1
fi

VERSION="$(echo "$JSON" | grep -o '"tag_name" *: *"[^"]*"' | sed 's/.*: *"v\{0,1\}\([^"]*\)"/\1/' | head -1)"
BUNDLE_URL="$(echo "$JSON" | grep -o '"browser_download_url" *: *"[^"]*\.flatpak"' | sed 's/.*: *"\([^"]*\)"/\1/' | head -1)"

if [ -z "$BUNDLE_URL" ]; then
    echo "ERROR: No .flatpak bundle found in the latest release."
    echo "The Flatpak build may still be in progress. Try again in a few minutes."
    exit 1
fi
echo "[OK] Latest version: ${VERSION}"

# ── Check if already installed ─────────────────────────────
CURRENT="$(flatpak info "$APP_ID" 2>/dev/null | grep -i version | head -1 | awk '{print $NF}' || true)"
if [ -n "$CURRENT" ]; then
    echo "[OK] Currently installed: ${CURRENT}"
fi

# ── Download .flatpak bundle ──────────────────────────────
TMPDIR="$(mktemp -d)"
trap 'rm -rf "$TMPDIR"' EXIT

echo "[..] Downloading ${BUNDLE_NAME}..."
if command -v curl &>/dev/null; then
    curl -L --progress-bar -o "$TMPDIR/$BUNDLE_NAME" "$BUNDLE_URL"
else
    wget --show-progress -O "$TMPDIR/$BUNDLE_NAME" "$BUNDLE_URL"
fi

# ── Install ────────────────────────────────────────────────
echo "[..] Installing Flatpak..."
flatpak install --user --noninteractive --or-update "$TMPDIR/$BUNDLE_NAME"

echo ""
echo "========================================"
echo "  Installation complete!"
echo "  Version: ${VERSION}"
echo ""
echo "  Launch: flatpak run ${APP_ID}"
echo "========================================"
