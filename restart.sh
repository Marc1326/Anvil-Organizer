#!/bin/bash
pkill -f "python main.py" 2>/dev/null
sleep 0.5
cd ~/Projekte/Anvil\ Organizer
source .venv/bin/activate
python -u main.py 2>&1 | tee debug.log
