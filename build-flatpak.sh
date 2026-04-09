#!/bin/bash
# Build Anvil Organizer as a Flatpak
#
# Prerequisites:
#   - Flatpak installed
#   - KDE runtime: flatpak install flathub org.kde.Platform//6.7 org.kde.Sdk//6.7
#
# Usage:
#   ./build-flatpak.sh           # Build and install locally
#   ./build-flatpak.sh --bundle  # Build and create .flatpak bundle file
#
set -euo pipefail

ensure_flatpak_builder() {
  if command -v flatpak-builder >/dev/null 2>&1; then
    return 0
  fi
  echo "flatpak-builder nicht gefunden, installiere..."
  if command -v pacman >/dev/null 2>&1; then
    sudo pacman -S --needed --noconfirm flatpak-builder
  elif command -v apt-get >/dev/null 2>&1; then
    sudo apt-get update -qq
    sudo DEBIAN_FRONTEND=noninteractive apt-get install -y flatpak-builder
  elif command -v dnf >/dev/null 2>&1; then
    sudo dnf install -y flatpak-builder
  elif command -v zypper >/dev/null 2>&1; then
    sudo zypper install -y flatpak-builder
  else
    echo "Paketmanager nicht erkannt. Bitte flatpak-builder manuell installieren." >&2
    exit 1
  fi
}

PROJECT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
MANIFEST="${PROJECT_DIR}/packaging/flatpak/com.github.Marc1326.AnvilOrganizer.yml"
BUILD_DIR="${PROJECT_DIR}/packaging/flatpak/build"
REPO_DIR="${PROJECT_DIR}/packaging/flatpak/repo"
BUNDLE_FILE="${PROJECT_DIR}/anvil-organizer.flatpak"
APP_ID="com.github.Marc1326.AnvilOrganizer"

BUNDLE_MODE=false
INSTALL_FLAG="--install"
[ "${1:-}" = "--bundle" ] && { INSTALL_FLAG=""; BUNDLE_MODE=true; }

cd "$PROJECT_DIR"

echo "========================================="
echo "  Anvil Organizer — Flatpak Build"
echo "========================================="
echo ""

ensure_flatpak_builder

flatpak-builder \
  --verbose \
  --user \
  --install-deps-from=flathub \
  --repo="${REPO_DIR}" \
  --force-clean \
  $INSTALL_FLAG \
  "${BUILD_DIR}" \
  "${MANIFEST}"

if [ "$BUNDLE_MODE" = true ]; then
  echo ""
  echo "=== .flatpak Bundle erstellen ==="
  flatpak build-bundle \
    "${REPO_DIR}" \
    "${BUNDLE_FILE}" \
    "${APP_ID}" \
    --runtime-repo=https://dl.flathub.org/repo/flathub.flatpakrepo
  echo ""
  echo "  Bundle: ${BUNDLE_FILE}"
  echo "  Install: flatpak install --user ${BUNDLE_FILE}"
else
  echo ""
  echo "========================================="
  echo "  Fertig! Starten mit:"
  echo "  flatpak run ${APP_ID}"
  echo "========================================="
fi
