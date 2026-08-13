#!/bin/bash
# Startet Anvil aus diesem Repo (Branch overlay-einbau) mit der
# Sandbox-Konfiguration und dem Sandbox-Basisverzeichnis.
#
# Beruehrt NICHT:
#   /home/mob/.config/AnvilOrganizer     (echte Einstellungen)
#   /home/mob/.anvil-organizer           (echte Instanzen)
set -u

REPO="$(cd "$(dirname "$0")" && pwd)"
DATA="/home/mob/anvil-overlay-data"

export XDG_CONFIG_HOME="$DATA/config"
export XDG_DATA_HOME="$DATA/share"
export XDG_CACHE_HOME="$DATA/cache"

mkdir -p "$XDG_CONFIG_HOME/AnvilOrganizer" "$XDG_DATA_HOME" "$XDG_CACHE_HOME" "$DATA/base"

CONF="$XDG_CONFIG_HOME/AnvilOrganizer/AnvilOrganizer.conf"
if ! grep -q '^base_dir=' "$CONF" 2>/dev/null; then
    printf '[%%General]\nbase_dir=%s\n' "$DATA/base" > "$CONF"
    echo "Basisverzeichnis gesetzt: $DATA/base"
fi

echo "Repo:            $REPO"
echo "Konfiguration:   $XDG_CONFIG_HOME"
echo "Basisverzeichnis: $DATA/base"
echo

cd "$REPO"
.venv/bin/python -u main.py 2>&1 | tee "$DATA/sandbox-debug.log"
