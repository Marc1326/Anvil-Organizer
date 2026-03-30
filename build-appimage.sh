#!/bin/bash
# ──────────────────────────────────────────────────────────────
# Anvil Organizer — AppImage Build Script
# Builds a portable AppImage from the Python/PySide6 project
# ──────────────────────────────────────────────────────────────

set -e

SCRIPT_DIR="$(cd "$(dirname "$0")" && pwd)"
VENV_DIR="$SCRIPT_DIR/.venv"
SPEC_FILE="$SCRIPT_DIR/anvil-organizer.spec"
DIST_DIR="$SCRIPT_DIR/dist/anvil-organizer"
APPDIR="$SCRIPT_DIR/AnvilOrganizer.AppDir"
RELEASE_DIR="$SCRIPT_DIR/release"
APPIMAGETOOL="/tmp/appimagetool"

VERSION="1.2.6"
APPIMAGE_NAME="Anvil_Organizer-${VERSION}-x86_64.AppImage"

echo "========================================"
echo "  Anvil Organizer — AppImage Builder"
echo "  Version: $VERSION"
echo "========================================"
echo ""

# ── Check venv ───────────────────────────────────────────────
if [ ! -d "$VENV_DIR" ]; then
    echo "ERROR: Virtual environment not found at $VENV_DIR"
    echo "       Run install.sh first."
    exit 1
fi
echo "[OK] Virtual environment found"

# ── Install PyInstaller if needed ────────────────────────────
if ! "$VENV_DIR/bin/pip" show pyinstaller &>/dev/null; then
    echo "[..] Installing PyInstaller..."
    "$VENV_DIR/bin/pip" install pyinstaller -q
    echo "[OK] PyInstaller installed"
else
    echo "[OK] PyInstaller already installed"
fi

# ── Check spec file ──────────────────────────────────────────
if [ ! -f "$SPEC_FILE" ]; then
    echo "ERROR: Spec file not found at $SPEC_FILE"
    exit 1
fi
echo "[OK] Spec file found"

# ── Clean previous build ─────────────────────────────────────
echo "[..] Cleaning previous build artifacts..."
rm -rf "$SCRIPT_DIR/build" "$DIST_DIR" "$APPDIR"
echo "[OK] Clean"

# ── PyInstaller Build ────────────────────────────────────────
echo "[..] Running PyInstaller build..."
cd "$SCRIPT_DIR"
"$VENV_DIR/bin/pyinstaller" "$SPEC_FILE" --noconfirm 2>&1 | tail -5
echo "[OK] PyInstaller build complete"

# ── Verify dist ──────────────────────────────────────────────
if [ ! -x "$DIST_DIR/anvil-organizer" ]; then
    echo "ERROR: Build output not found at $DIST_DIR/anvil-organizer"
    exit 1
fi
echo "[OK] Binary built: $DIST_DIR/anvil-organizer"

# ── Create AppDir ────────────────────────────────────────────
echo "[..] Creating AppDir structure..."
mkdir -p "$APPDIR/usr/bin"

# AppRun
cat > "$APPDIR/AppRun" << 'APPRUN_EOF'
#!/bin/bash
HERE="$(dirname "$(readlink -f "${0}")")"
exec "${HERE}/usr/bin/anvil-organizer" "$@"
APPRUN_EOF
chmod +x "$APPDIR/AppRun"

# Desktop entry
cat > "$APPDIR/anvil-organizer.desktop" << DESKTOP_EOF
[Desktop Entry]
Name=Anvil Organizer
Exec=anvil-organizer
Icon=anvil-organizer
Type=Application
Categories=Game;Utility;
Comment=Native Linux Mod Manager
DESKTOP_EOF

# Icon
cp "$SCRIPT_DIR/anvil/resources/logo.png" "$APPDIR/anvil-organizer.png"

# Copy dist contents
cp -a "$DIST_DIR"/* "$APPDIR/usr/bin/"

echo "[OK] AppDir created"

# ── Download appimagetool if needed ──────────────────────────
if [ ! -x "$APPIMAGETOOL" ]; then
    echo "[..] Downloading appimagetool..."
    wget -q "https://github.com/AppImage/appimagetool/releases/download/continuous/appimagetool-x86_64.AppImage" \
        -O "$APPIMAGETOOL"
    chmod +x "$APPIMAGETOOL"
    echo "[OK] appimagetool downloaded"
else
    echo "[OK] appimagetool already available"
fi

# ── Build AppImage ───────────────────────────────────────────
echo "[..] Building AppImage..."
mkdir -p "$RELEASE_DIR"
ARCH=x86_64 "$APPIMAGETOOL" "$APPDIR" "$RELEASE_DIR/$APPIMAGE_NAME" 2>&1 | tail -5

if [ ! -f "$RELEASE_DIR/$APPIMAGE_NAME" ]; then
    echo "ERROR: AppImage build failed!"
    exit 1
fi

SIZE=$(du -h "$RELEASE_DIR/$APPIMAGE_NAME" | cut -f1)
echo "[OK] AppImage built: $RELEASE_DIR/$APPIMAGE_NAME ($SIZE)"

# ── Cleanup (optional — keep AppDir for debugging) ───────────
rm -rf "$APPDIR"
echo "[OK] AppDir cleaned up"

echo ""
echo "========================================"
echo "  Build complete!"
echo "  AppImage: release/$APPIMAGE_NAME"
echo "  Size: $SIZE"
echo "========================================"
