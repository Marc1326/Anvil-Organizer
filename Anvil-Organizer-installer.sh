#!/bin/bash
# Anvil Organizer — Installer
# Downloads the latest AppImage, icon, and creates a .desktop entry
#
# Usage:
#   chmod +x Anvil-Organizer-installer.sh
#   ./Anvil-Organizer-installer.sh
#
# Or one-liner:
#   curl -sSL https://raw.githubusercontent.com/Marc1326/Anvil-Organizer/main/Anvil-Organizer-installer.sh | bash

set -e

REPO="Marc1326/Anvil-Organizer"
RELEASES_API_URL="https://api.github.com/repos/${REPO}/releases/latest"
ICON_URL="https://raw.githubusercontent.com/${REPO}/main/anvil/resources/logo.png"

APPLICATIONS_DIR="${HOME}/Applications"
XDG_DATA="${XDG_DATA_HOME:-$HOME/.local/share}"
ICONS_DIR="${XDG_DATA}/icons"
DESKTOP_DIR="${XDG_DATA}/applications"

APPIMAGE_NAME="Anvil_Organizer-x86_64.AppImage"
ICON_NAME="anvil-organizer.png"
DESKTOP_NAME="anvil-organizer.desktop"

echo "========================================"
echo "  Anvil Organizer — Installer"
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
APPIMAGE_URL="$(echo "$JSON" | grep -o '"browser_download_url" *: *"[^"]*\.AppImage"' | sed 's/.*: *"\([^"]*\)"/\1/' | head -1)"

if [ -z "$APPIMAGE_URL" ]; then
    echo "ERROR: Could not find an AppImage in the latest release."
    exit 1
fi
echo "[OK] Latest version: ${VERSION}"

# ── Create directories ──────────────────────────────────────
mkdir -p "$APPLICATIONS_DIR" "$ICONS_DIR" "$DESKTOP_DIR"

# ── Download AppImage ───────────────────────────────────────
echo "[..] Downloading AppImage..."
if command -v curl &>/dev/null; then
    curl -L --progress-bar -o "$APPLICATIONS_DIR/$APPIMAGE_NAME" "$APPIMAGE_URL"
else
    wget --show-progress -O "$APPLICATIONS_DIR/$APPIMAGE_NAME" "$APPIMAGE_URL"
fi
chmod +x "$APPLICATIONS_DIR/$APPIMAGE_NAME"
echo "[OK] AppImage installed: $APPLICATIONS_DIR/$APPIMAGE_NAME"

# ── Download icon ───────────────────────────────────────────
echo "[..] Downloading icon..."
if command -v curl &>/dev/null; then
    curl -sL -o "$ICONS_DIR/$ICON_NAME" "$ICON_URL"
else
    wget -q -O "$ICONS_DIR/$ICON_NAME" "$ICON_URL"
fi
echo "[OK] Icon installed: $ICONS_DIR/$ICON_NAME"

# ── Create .desktop entry ──────────────────────────────────
cat > "$DESKTOP_DIR/$DESKTOP_NAME" << EOF
[Desktop Entry]
Type=Application
Name=Anvil Organizer
GenericName=Mod Manager
Comment=Native Linux Mod Manager
Exec=env APPIMAGE_EXTRACT_AND_RUN=1 ${APPLICATIONS_DIR}/${APPIMAGE_NAME} %u
Icon=${ICONS_DIR}/${ICON_NAME}
Terminal=false
Categories=Game;Utility;
Keywords=mod;modding;gaming;steam;proton;nexus;
StartupWMClass=anvil-organizer
MimeType=x-scheme-handler/nxm;
EOF

echo "[OK] Desktop entry created: $DESKTOP_DIR/$DESKTOP_NAME"

# ── Register NXM handler ───────────────────────────────────
if command -v xdg-mime &>/dev/null; then
    xdg-mime default "$DESKTOP_NAME" x-scheme-handler/nxm 2>/dev/null || true
    echo "[OK] NXM link handler registered"
fi

# ── Update desktop database ────────────────────────────────
if command -v update-desktop-database &>/dev/null; then
    update-desktop-database "$DESKTOP_DIR" 2>/dev/null || true
fi

echo ""
echo "========================================"
echo "  Installation complete!"
echo "  Version: ${VERSION}"
echo ""
echo "  Launch from your application menu"
echo "  or run: ${APPLICATIONS_DIR}/${APPIMAGE_NAME}"
echo "========================================"
