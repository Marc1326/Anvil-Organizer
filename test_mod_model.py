"""Tests für das Mod-Datenmodell: meta.ini, modlist.txt, scan_mods_directory."""

import shutil
import tempfile
from pathlib import Path

from anvil.core.mod_metadata import (
    read_meta_ini,
    write_meta_ini,
    create_default_meta_ini,
)
from anvil.core.mod_list_io import (
    read_modlist,
    write_modlist,
    add_mod_to_modlist,
    remove_mod_from_modlist,
)
from anvil.core.mod_entry import ModEntry, scan_mods_directory


def _setup_instance(tmp: Path) -> tuple[Path, Path]:
    """Create a minimal instance structure and return (instance_path, profile_path)."""
    instance = tmp / "TestInstance"
    mods = instance / ".mods"
    profile = instance / ".profiles" / "Default"

    mods.mkdir(parents=True)
    profile.mkdir(parents=True)

    return instance, profile


def _create_mod(mods_dir: Path, name: str, files: dict[str, str] | None = None):
    """Create a mod folder with optional dummy files."""
    mod_path = mods_dir / name
    mod_path.mkdir(parents=True, exist_ok=True)
    for fname, content in (files or {}).items():
        f = mod_path / fname
        f.parent.mkdir(parents=True, exist_ok=True)
        f.write_text(content, encoding="utf-8")
    return mod_path


def main():
    tmp = Path(tempfile.mkdtemp(prefix="anvil_test_mod_"))
    print(f"=== Test-Verzeichnis: {tmp} ===\n")

    try:
        _test_meta_ini(tmp)
        _test_modlist(tmp)
        _test_scan_mods(tmp)
        _test_edge_cases(tmp)
    finally:
        shutil.rmtree(tmp)

    print("\n" + "=" * 50)
    print("ALLE TESTS BESTANDEN!")
    print("=" * 50)


# ── meta.ini Tests ────────────────────────────────────────────────────


def _test_meta_ini(tmp: Path):
    print("=== meta.ini Tests ===")

    mod_path = tmp / "meta_test_mod"
    mod_path.mkdir(parents=True)

    # 1. read_meta_ini — kein meta.ini vorhanden
    data = read_meta_ini(mod_path)
    assert data == {}, f"Expected empty dict, got {data}"
    print("  read_meta_ini (nicht vorhanden) → {} OK")

    # 2. create_default_meta_ini
    create_default_meta_ini(mod_path, "Test Mod Display Name")
    ini = mod_path / "meta.ini"
    assert ini.is_file(), "meta.ini nicht erstellt"
    print(f"  create_default_meta_ini → Datei erstellt OK")

    # 3. read_meta_ini — mit Datei
    data = read_meta_ini(mod_path)
    assert data.get("name") == "Test Mod Display Name", f"name={data.get('name')}"
    assert data.get("modid") == "0", f"modid={data.get('modid')}"
    assert data.get("repository") == "Nexus", f"repository={data.get('repository')}"
    assert "installDate" in data, "installDate fehlt"
    print(f"  read_meta_ini → name={data['name']}, modid={data['modid']} OK")

    # 4. write_meta_ini — Update bestehend
    write_meta_ini(mod_path, {"version": "2.0", "author": "Tester"})
    data2 = read_meta_ini(mod_path)
    assert data2.get("version") == "2.0", f"version={data2.get('version')}"
    assert data2.get("author") == "Tester", f"author={data2.get('author')}"
    assert data2.get("name") == "Test Mod Display Name", "name überschrieben!"
    print(f"  write_meta_ini (Update) → version={data2['version']}, author={data2['author']} OK")

    print()


# ── modlist.txt Tests ─────────────────────────────────────────────────


def _test_modlist(tmp: Path):
    print("=== modlist.txt Tests ===")

    profile = tmp / "profile_test"
    profile.mkdir(parents=True)

    # 1. read_modlist — keine Datei
    result = read_modlist(profile)
    assert result == [], f"Expected [], got {result}"
    print("  read_modlist (nicht vorhanden) → [] OK")

    # 2. write_modlist
    mods = [
        ("ModA", True),
        ("ModB", False),
        ("ModC", True),
    ]
    write_modlist(profile, mods)
    modlist = profile / "modlist.txt"
    assert modlist.is_file(), "modlist.txt nicht erstellt"
    content = modlist.read_text(encoding="utf-8")
    assert "+ModA" in content
    assert "-ModB" in content
    assert "+ModC" in content
    assert content.startswith("# Managed by Anvil Organizer")
    print(f"  write_modlist → 3 Einträge geschrieben OK")

    # 3. read_modlist — liest geschriebene Datei
    result = read_modlist(profile)
    assert len(result) == 3, f"Expected 3, got {len(result)}"
    assert result[0] == ("ModA", True)
    assert result[1] == ("ModB", False)
    assert result[2] == ("ModC", True)
    print(f"  read_modlist → {result} OK")

    # 4. add_mod_to_modlist
    add_mod_to_modlist(profile, "ModD", enabled=True)
    result = read_modlist(profile)
    assert len(result) == 4
    assert result[3] == ("ModD", True)
    print(f"  add_mod_to_modlist → ModD hinzugefügt OK")

    # 5. add_mod_to_modlist — Duplikat
    add_mod_to_modlist(profile, "ModA", enabled=False)
    result = read_modlist(profile)
    assert len(result) == 4, "Duplikat hinzugefügt!"
    assert result[0] == ("ModA", True), "ModA Status geändert!"
    print(f"  add_mod_to_modlist (Duplikat) → ignoriert OK")

    # 6. remove_mod_from_modlist
    remove_mod_from_modlist(profile, "ModB")
    result = read_modlist(profile)
    assert len(result) == 3
    names = [n for n, _ in result]
    assert "ModB" not in names
    print(f"  remove_mod_from_modlist → ModB entfernt OK")

    # 7. remove_mod_from_modlist — nicht vorhanden
    remove_mod_from_modlist(profile, "NonExistent")
    result = read_modlist(profile)
    assert len(result) == 3, "Liste geändert bei Entfernen von nicht vorhandenem Mod!"
    print(f"  remove_mod_from_modlist (nicht vorhanden) → keine Änderung OK")

    print()


# ── scan_mods_directory Tests ─────────────────────────────────────────


def _test_scan_mods(tmp: Path):
    print("=== scan_mods_directory Tests ===")

    instance, profile = _setup_instance(tmp)
    mods_dir = instance / ".mods"

    # Erstelle 3 Mod-Ordner mit Dummy-Dateien
    _create_mod(mods_dir, "SkyUI", {
        "interface/skyui.swf": "dummy",
        "interface/skyui_cfg.txt": "config data here",
    })
    _create_mod(mods_dir, "SKSE64", {
        "skse64_loader.exe": "x" * 1000,
        "Data/skse64.dll": "y" * 5000,
    })
    _create_mod(mods_dir, "Unofficial Patch", {
        "Unofficial.esp": "z" * 200,
    })

    # meta.ini für SkyUI
    create_default_meta_ini(mods_dir / "SkyUI", "SkyUI")
    write_meta_ini(mods_dir / "SkyUI", {
        "version": "5.2",
        "category": "UI",
        "author": "schlangster",
        "modid": "3863",
    })

    # modlist.txt: SkyUI aktiv, SKSE64 aktiv, Unofficial Patch inaktiv
    write_modlist(profile, [
        ("SkyUI", True),
        ("SKSE64", True),
        ("Unofficial Patch", False),
    ])

    # Scan
    entries = scan_mods_directory(instance, profile)

    assert len(entries) == 3, f"Expected 3, got {len(entries)}"
    print(f"  Anzahl Mods: {len(entries)} OK")

    # Reihenfolge = modlist.txt Reihenfolge
    assert entries[0].name == "SkyUI"
    assert entries[1].name == "SKSE64"
    assert entries[2].name == "Unofficial Patch"
    print(f"  Reihenfolge: {[e.name for e in entries]} OK")

    # Prioritäten
    assert entries[0].priority == 0
    assert entries[1].priority == 1
    assert entries[2].priority == 2
    print(f"  Prioritäten: {[e.priority for e in entries]} OK")

    # Enabled/Disabled
    assert entries[0].enabled is True
    assert entries[1].enabled is True
    assert entries[2].enabled is False
    print(f"  Enabled: {[e.enabled for e in entries]} OK")

    # Meta-Daten für SkyUI
    skyui = entries[0]
    assert skyui.display_name == "SkyUI", f"display_name={skyui.display_name}"
    assert skyui.version == "5.2", f"version={skyui.version}"
    assert skyui.category == "UI", f"category={skyui.category}"
    assert skyui.author == "schlangster", f"author={skyui.author}"
    assert skyui.nexus_id == 3863, f"nexus_id={skyui.nexus_id}"
    print(f"  SkyUI Metadaten: name={skyui.display_name}, v={skyui.version}, "
          f"cat={skyui.category}, author={skyui.author}, nexus={skyui.nexus_id} OK")

    # Dateizählung
    assert skyui.file_count == 3, f"SkyUI files={skyui.file_count}"  # 2 files + meta.ini
    assert skyui.total_size > 0
    print(f"  SkyUI Dateien: {skyui.file_count}, Größe: {skyui.total_size} B OK")

    skse = entries[1]
    assert skse.file_count == 2, f"SKSE64 files={skse.file_count}"
    assert skse.total_size == 6000, f"SKSE64 size={skse.total_size}"
    print(f"  SKSE64 Dateien: {skse.file_count}, Größe: {skse.total_size} B OK")

    # install_path gesetzt
    assert skyui.install_path == mods_dir / "SkyUI"
    print(f"  install_path gesetzt: OK")

    # SKSE64 hat keine meta.ini → display_name leer
    assert skse.display_name == ""
    assert skse.version == ""
    print(f"  SKSE64 ohne meta.ini → leere Felder OK")

    print()


# ── Edge Cases ────────────────────────────────────────────────────────


def _test_edge_cases(tmp: Path):
    print("=== Edge Cases ===")

    instance, profile = _setup_instance(tmp / "edge")
    mods_dir = instance / ".mods"

    # Mod auf Disk aber NICHT in modlist.txt → wird am Ende angefügt
    _create_mod(mods_dir, "NewMod", {"data.txt": "content"})
    _create_mod(mods_dir, "OldMod", {"old.txt": "old content"})

    write_modlist(profile, [("OldMod", True)])

    entries = scan_mods_directory(instance, profile)
    assert len(entries) == 2, f"Expected 2, got {len(entries)}"
    assert entries[0].name == "OldMod", "OldMod sollte zuerst kommen (aus modlist)"
    assert entries[1].name == "NewMod", "NewMod sollte am Ende stehen (neu)"
    assert entries[1].enabled is True, "Neue Mods sollten aktiviert sein"
    print(f"  Neuer Mod (nicht in modlist) → am Ende angefügt: OK")

    # Mod in modlist.txt aber NICHT auf Disk → wird ignoriert
    write_modlist(profile, [
        ("OldMod", True),
        ("DeletedMod", True),
        ("NewMod", False),
    ])
    entries = scan_mods_directory(instance, profile)
    assert len(entries) == 2, f"Expected 2 (DeletedMod ignoriert), got {len(entries)}"
    names = [e.name for e in entries]
    assert "DeletedMod" not in names
    print(f"  Gelöschter Mod (nicht auf Disk) → ignoriert: OK")

    # Leerer .mods/ Ordner + leere modlist.txt
    instance2, profile2 = _setup_instance(tmp / "empty")
    entries = scan_mods_directory(instance2, profile2)
    assert len(entries) == 0
    print(f"  Leere Instanz → 0 Mods: OK")

    # Kaputte meta.ini
    instance3, profile3 = _setup_instance(tmp / "broken")
    mods_dir3 = instance3 / ".mods"
    mod_broken = _create_mod(mods_dir3, "BrokenMod", {"data.esp": "mod"})
    (mod_broken / "meta.ini").write_text("[Broken\nno=value\n[[[", encoding="utf-8")

    write_modlist(profile3, [("BrokenMod", True)])
    entries = scan_mods_directory(instance3, profile3)
    assert len(entries) == 1
    assert entries[0].name == "BrokenMod"
    assert entries[0].display_name == ""  # meta.ini kaputt → leere Felder
    print(f"  Kaputte meta.ini → Mod trotzdem geladen, leere Felder: OK")

    print()


if __name__ == "__main__":
    main()
