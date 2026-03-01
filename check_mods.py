from pathlib import Path
from anvil.core.instance_manager import InstanceManager

im = InstanceManager()
instances = im.list_instances()

for inst in instances:
    name = inst.get("name", inst) if isinstance(inst, dict) else str(inst)
    data = im.load_instance(name)
    if data and "Fallout" in data.get("game_name", ""):
        inst_path = im.instances_path() / name
        mods_dir = inst_path / ".mods"
        print(f"=== Fallout 4 Instanz: {name} ===")
        if mods_dir.is_dir():
            mods = sorted([d.name for d in mods_dir.iterdir() if d.is_dir()])
            print(f"{len(mods)} Mods installiert:\n")
            for m in mods:
                mod_path = mods_dir / m
                files = [f for f in mod_path.rglob("*") if f.is_file()]
                has_dll = any(f.suffix == ".dll" for f in files)
                has_esp = any(f.suffix in (".esp", ".esm", ".esl") for f in files)
                tags = []
                if has_dll:
                    tags.append("DLL")
                if has_esp:
                    tags.append("ESP/ESM")
                tag_str = " [" + ", ".join(tags) + "]" if tags else ""
                print(f"  {m} ({len(files)} files){tag_str}")
        else:
            print("Kein .mods Ordner gefunden")
        break
