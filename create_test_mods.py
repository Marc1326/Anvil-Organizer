"""Erstellt 3 Test-Mods in der Cyberpunk 2077 Instanz zum Testen der Mod-Liste."""

from pathlib import Path

from anvil.core.mod_metadata import create_default_meta_ini, write_meta_ini
from anvil.core.mod_list_io import write_modlist

INSTANCE = Path.home() / ".anvil-organizer" / "instances" / "Cyberpunk 2077"
MODS_DIR = INSTANCE / ".mods"
PROFILE = INSTANCE / ".profiles" / "Default"

MODS = [
    {
        "folder": "Cyber Engine Tweaks",
        "meta": {
            "name": "Cyber Engine Tweaks",
            "version": "1.32.2",
            "author": "yamashi",
            "category": "Utilities",
            "modid": "107",
        },
        "files": {
            "bin/x64/plugins/cyber_engine_tweaks.asi": "dummy",
            "bin/x64/plugins/cyber_engine_tweaks/config.json": '{"key": "value"}',
        },
        "enabled": True,
    },
    {
        "folder": "Better Loot",
        "meta": {
            "name": "Better Loot",
            "version": "2.1.0",
            "author": "RMK",
            "category": "Gameplay",
            "modid": "2134",
        },
        "files": {
            "r6/scripts/better_loot.reds": "// redscript mod",
        },
        "enabled": True,
    },
    {
        "folder": "HD Reworked",
        "meta": {
            "name": "HD Reworked Project",
            "version": "0.8",
            "author": "HalkHogan",
            "category": "Visuals",
            "modid": "999",
        },
        "files": {
            "archive/pc/mod/hd_reworked.archive": "x" * 5000,
        },
        "enabled": False,
    },
]


def main():
    MODS_DIR.mkdir(parents=True, exist_ok=True)
    PROFILE.mkdir(parents=True, exist_ok=True)

    for mod in MODS:
        mod_path = MODS_DIR / mod["folder"]
        mod_path.mkdir(parents=True, exist_ok=True)

        # Dummy-Dateien erstellen
        for rel_path, content in mod["files"].items():
            f = mod_path / rel_path
            f.parent.mkdir(parents=True, exist_ok=True)
            f.write_text(content, encoding="utf-8")

        # meta.ini
        create_default_meta_ini(mod_path, mod["meta"]["name"])
        write_meta_ini(mod_path, mod["meta"])

        print(f"  Erstellt: {mod['folder']}")

    # modlist.txt schreiben
    modlist = [(m["folder"], m["enabled"]) for m in MODS]
    write_modlist(PROFILE, modlist)
    print(f"\n  modlist.txt: {modlist}")

    print(f"\nFertig! 3 Test-Mods unter {MODS_DIR}")


if __name__ == "__main__":
    main()
