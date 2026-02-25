#!/usr/bin/env python3
"""Test: InstanceManager — create, list, load, switch, delete."""

import sys
import tempfile
from pathlib import Path

# PySide6 required for QSettings
from PySide6.QtWidgets import QApplication

app = QApplication(sys.argv)

from anvil.core.instance_manager import InstanceManager
from anvil.plugins.plugin_loader import PluginLoader

# ── Setup: Use temp dir so we don't touch real data ──────────────────

tmp = Path(tempfile.mkdtemp(prefix="anvil_test_"))
print(f"=== Test-Verzeichnis: {tmp} ===\n")

im = InstanceManager(base_path=tmp / "instances")
print(f"InstanceManager: {im!r}")
print(f"instances_path:  {im.instances_path()}")

# ── Load plugins ─────────────────────────────────────────────────────

loader = PluginLoader()
loader.load_plugins()
print(f"\nPlugins geladen: {loader.plugin_count()}")
print(f"Installiert:     {loader.installed_count()}")

cyberpunk = loader.get_game("cyberpunk2077")
if cyberpunk is None:
    print("ERROR: Cyberpunk plugin nicht geladen!")
    sys.exit(1)

print(f"\nSpiel: {cyberpunk.GameName}")
print(f"  Installiert: {cyberpunk.isInstalled()}")
print(f"  Store:       {cyberpunk.detectedStore()}")
print(f"  Pfad:        {cyberpunk.gameDirectory()}")

# ── list_instances() — should be empty ───────────────────────────────

instances = im.list_instances()
print(f"\n=== list_instances() (vorher) ===")
print(f"  Anzahl: {len(instances)}")
assert len(instances) == 0, "Expected 0 instances initially"

# ── current_instance() — should be None ──────────────────────────────

current = im.current_instance()
print(f"\n=== current_instance() ===")
print(f"  Aktuell: {current}")
assert current is None, "Expected no current instance"

# ── create_instance() ────────────────────────────────────────────────

print(f"\n=== create_instance(cyberpunk) ===")
inst_path = im.create_instance(cyberpunk)
print(f"  Erstellt: {inst_path}")

# Check directories
expected_dirs = [".mods", ".downloads", ".profiles", ".overwrite"]
for d in expected_dirs:
    full = inst_path / d
    exists = full.is_dir()
    status = "OK" if exists else "FEHLT!"
    print(f"  {d:15} → {status}")
    assert exists, f"Directory {d} missing"

# Check .profiles/Default/modlist.txt
modlist = inst_path / ".profiles" / "Default" / "modlist.txt"
print(f"  modlist.txt     → {'OK' if modlist.is_file() else 'FEHLT!'}")
assert modlist.is_file(), "modlist.txt missing"
print(f"    Inhalt: {modlist.read_text(encoding='utf-8')[:50]!r}...")

# Check .anvil.ini
ini = inst_path / ".anvil.ini"
print(f"  .anvil.ini      → {'OK' if ini.is_file() else 'FEHLT!'}")
assert ini.is_file(), ".anvil.ini missing"

# ── list_instances() — should have 1 ────────────────────────────────

instances = im.list_instances()
print(f"\n=== list_instances() (nachher) ===")
print(f"  Anzahl: {len(instances)}")
assert len(instances) == 1, f"Expected 1 instance, got {len(instances)}"

inst = instances[0]
print(f"  Name:           {inst['name']}")
print(f"  game_name:      {inst.get('game_name', '?')}")
print(f"  game_short_name:{inst.get('game_short_name', '?')}")
print(f"  game_path:      {inst.get('game_path', '?')}")
print(f"  detected_store: {inst.get('detected_store', '?')}")
print(f"  selected_profile:{inst.get('selected_profile', '?')}")
print(f"  created:        {inst.get('created', '?')}")

assert inst["name"] == "Cyberpunk 2077"
assert inst.get("game_name") == "Cyberpunk 2077"
assert inst.get("game_short_name") == "cyberpunk2077"

# ── load_instance() ──────────────────────────────────────────────────

print(f"\n=== load_instance('Cyberpunk 2077') ===")
data = im.load_instance("Cyberpunk 2077")
for k, v in data.items():
    print(f"  {k}: {v}")

assert data.get("game_name") == "Cyberpunk 2077"
assert data.get("selected_profile") == "Default"

# ── set_current_instance() + current_instance() ─────────────────────

print(f"\n=== set_current_instance('Cyberpunk 2077') ===")
im.set_current_instance("Cyberpunk 2077")
current = im.current_instance()
print(f"  Aktuell: {current}")
assert current == "Cyberpunk 2077", f"Expected 'Cyberpunk 2077', got {current!r}"

# ── Duplicate instance should fail ───────────────────────────────────

print(f"\n=== Duplicate create (should fail) ===")
try:
    im.create_instance(cyberpunk)
    print("  ERROR: Should have raised FileExistsError!")
    sys.exit(1)
except FileExistsError as e:
    print(f"  Korrekt: {e}")

# ── delete_instance() ────────────────────────────────────────────────

print(f"\n=== delete_instance('Cyberpunk 2077') ===")
ok = im.delete_instance("Cyberpunk 2077")
print(f"  Gelöscht: {ok}")
assert ok, "Expected True"

instances = im.list_instances()
print(f"  Instanzen danach: {len(instances)}")
assert len(instances) == 0, "Expected 0 instances after delete"

# Current should be None after deleting the current instance
current = im.current_instance()
print(f"  Aktuell danach: {current}")
assert current is None, "Expected no current instance after delete"

# Directory should be gone
print(f"  Ordner existiert noch: {inst_path.is_dir()}")
assert not inst_path.is_dir(), "Instance directory should be deleted"

# ── Cleanup ──────────────────────────────────────────────────────────

import shutil
shutil.rmtree(tmp, ignore_errors=True)

print(f"\n{'='*50}")
print(f"ALLE TESTS BESTANDEN!")
print(f"{'='*50}")
