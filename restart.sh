#!/bin/bash
pkill -f "python.*main.py" 2>/dev/null
sleep 0.3
cd /home/mob/Projekte/Anvil\ Organizer/ && nohup .venv/bin/python main.py >/dev/null 2>&1 &
