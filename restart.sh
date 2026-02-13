#!/bin/bash
pkill -f "python.*main.py" 2>/dev/null
sleep 0.3
find /home/mob/Projekte/Anvil\ Organizer/ -name "*.pyc" -delete 2>/dev/null
cd /home/mob/Projekte/Anvil\ Organizer/ && .venv/bin/python main.py
