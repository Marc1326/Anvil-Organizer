#!/bin/bash
# ──────────────────────────────────────────────────────────────
# Anvil Organizer — Install Script
# Creates venv, installs dependencies, creates desktop entry
# ──────────────────────────────────────────────────────────────

set -e

SCRIPT_DIR="$(cd "$(dirname "$0")" && pwd)"
VENV_DIR="$SCRIPT_DIR/.venv"
DESKTOP_FILE="$HOME/.local/share/applications/anvil-organizer.desktop"
ICON_SRC="$SCRIPT_DIR/anvil/resources/logo.png"
ICON_DIR="$HOME/.local/share/icons/hicolor/256x256/apps"
ICON_DEST="$ICON_DIR/anvil-organizer.png"

echo "╔══════════════════════════════════════════╗"
echo "║       Anvil Organizer — Installer        ║"
echo "╚══════════════════════════════════════════╝"
echo ""

# ── Check Python ──────────────────────────────────────────────
PYTHON=""
for cmd in python3.14 python3.13 python3.12 python3.11 python3; do
    if command -v "$cmd" &>/dev/null; then
        version=$("$cmd" -c "import sys; print(f'{sys.version_info.major}.{sys.version_info.minor}')")
        major=$(echo "$version" | cut -d. -f1)
        minor=$(echo "$version" | cut -d. -f2)
        if [ "$major" -ge 3 ] && [ "$minor" -ge 11 ]; then
            PYTHON="$cmd"
            break
        fi
    fi
done

if [ -z "$PYTHON" ]; then
    echo "❌ Python 3.11+ nicht gefunden!"
    echo "   Bitte installiere Python 3.11 oder neuer."
    exit 1
fi
echo "✓ Python gefunden: $PYTHON ($($PYTHON --version))"

# ── Create venv ───────────────────────────────────────────────
if [ ! -d "$VENV_DIR" ]; then
    echo "→ Erstelle virtuelle Umgebung..."
    "$PYTHON" -m venv "$VENV_DIR"
    echo "✓ venv erstellt"
else
    echo "✓ venv existiert bereits"
fi

# ── Install dependencies ──────────────────────────────────────
echo "→ Installiere Abhängigkeiten..."
"$VENV_DIR/bin/pip" install --upgrade pip -q
"$VENV_DIR/bin/pip" install -r "$SCRIPT_DIR/requirements.txt" -q
echo "✓ Abhängigkeiten installiert"

# ── Install icon ──────────────────────────────────────────────
if [ -f "$ICON_SRC" ]; then
    mkdir -p "$ICON_DIR"
    cp "$ICON_SRC" "$ICON_DEST"
    echo "✓ Icon installiert"
fi

# ── Create desktop entry ─────────────────────────────────────
mkdir -p "$(dirname "$DESKTOP_FILE")"
cat > "$DESKTOP_FILE" << EOF
[Desktop Entry]
Name=Anvil Organizer
Comment=Linux Mod Manager inspired by Mod Organizer 2
Exec="$VENV_DIR/bin/python" "$SCRIPT_DIR/main.py" %u
Icon=anvil-organizer
Terminal=false
Type=Application
Categories=Game;Utility;
MimeType=x-scheme-handler/nxm;
Keywords=mod;modding;gaming;steam;proton;
StartupWMClass=anvil-organizer
EOF
echo "✓ Desktop-Eintrag erstellt"

# ── Update desktop database ───────────────────────────────────
if command -v update-desktop-database &>/dev/null; then
    update-desktop-database "$HOME/.local/share/applications" 2>/dev/null || true
fi

echo ""
echo "════════════════════════════════════════════"
echo "  ✅ Installation abgeschlossen!"
echo ""
echo "  Starten mit:"
echo "    • App-Menü → Anvil Organizer"
echo "    • Terminal: $VENV_DIR/bin/python $SCRIPT_DIR/main.py"
echo "════════════════════════════════════════════"
