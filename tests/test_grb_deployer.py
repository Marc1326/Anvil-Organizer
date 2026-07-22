"""Tests for Ghost Recon Breakpoint profile deployment."""

from __future__ import annotations

import hashlib
import json
import struct
import tempfile
import unittest
import zlib
from pathlib import Path
from unittest import mock

from anvil.core.grb_forge import ForgeArchive


CFD_MAGIC = 0x1004FA9957FBAA33
ENTITY_BUILDER = zlib.crc32(b"EntityBuilder")


def _adler0(data: bytes) -> int:
    return zlib.adler32(data, 0) & 0xFFFFFFFF


def _cfd(raw: bytes) -> bytes:
    return b"".join(
        (
            struct.pack("<QhBHH", CFD_MAGIC, 3, 3, 32768, 32768),
            struct.pack("<i", 1),
            struct.pack("<ii", len(raw), len(raw)),
            struct.pack("<I", _adler0(raw)),
            raw,
        )
    )


def _data_container(class_id: int, extension: int, name: str) -> bytes:
    payload = (
        struct.pack("<IiI", extension, 13, len(name))
        + name.encode("ascii")
        + b"\0\0"
        + struct.pack("<QI", class_id, extension)
    )
    metadata = struct.pack("<HQIH", 1, class_id, len(payload), 0)
    return _cfd(metadata) + _cfd(payload)


def _info(length: int, extension: int, name: str, index: int, count: int) -> bytes:
    record = bytearray(192)
    struct.pack_into("<I", record, 0, length)
    identity = hashlib.sha256(
        struct.pack("<III", length, extension, index) + name.encode("latin-1")
    ).digest()[:12]
    record[4:16] = identity
    struct.pack_into("<I", record, 16, extension)
    struct.pack_into(
        "<I", record, 28, index + 1 if index + 1 < count else 0xFFFFFFFF
    )
    struct.pack_into("<I", record, 32, index - 1 if index else 0xFFFFFFFF)
    encoded = name.encode("latin-1")
    record[44 : 44 + len(encoded)] = encoded
    record[172:] = bytes.fromhex(
        "04 00 00 00 00 00 00 00 00 00 00 00 04 00 00 00 00 00 00 00"
    )
    return bytes(record)


def _forge(entries: list[tuple[int, int, str, bytes]]) -> bytes:
    header = bytearray(1094)
    header[:8] = b"scimitar"
    struct.pack_into("<I", header, 9, 27)
    struct.pack_into("<Q", header, 13, 1050)
    struct.pack_into("<I", header, 1050, len(entries))
    struct.pack_into("<I", header, 1054, 2)
    struct.pack_into("<I", header, 1082, 1)
    struct.pack_into("<q", header, 1086, 1094)

    fileset = bytearray(40)
    offset_table_at = 1094 + len(fileset)
    info_table_at = offset_table_at + len(entries) * 20
    payload_at = info_table_at + len(entries) * 192
    struct.pack_into(
        "<IIqqIIq",
        fileset,
        0,
        len(entries),
        2 if entries else 0,
        offset_table_at,
        -1,
        0,
        len(entries) - 1 if entries else 0xFFFFFFFF,
        info_table_at,
    )

    offsets = bytearray()
    infos = bytearray()
    payloads = bytearray()
    cursor = payload_at
    for index, (class_id, extension, name, payload) in enumerate(entries):
        offsets += struct.pack("<qQI", cursor, class_id, len(payload))
        infos += _info(len(payload), extension, name, index, len(entries))
        payloads += payload
        cursor += len(payload)
    return bytes(header + fileset + offsets + infos + payloads)


class GRBDeployerTests(unittest.TestCase):
    def test_deploy_rebuilds_from_pristine_backup_and_writes_manifest(self) -> None:
        try:
            from anvil.core.grb_deployer import GRBDeployer
        except ModuleNotFoundError:
            self.fail("GRBDeployer is not implemented")

        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            instance = root / "instance"
            game = root / "game"
            profile = instance / ".profiles" / "Default"
            mod_target = instance / ".mods" / "Weapon" / "DataPC_patch_01.forge"
            profile.mkdir(parents=True)
            mod_target.mkdir(parents=True)
            game.mkdir()

            original_payload = _data_container(0x111, ENTITY_BUILDER, "Original")
            original = _forge([(0x111, ENTITY_BUILDER, "Original", original_payload)])
            game_forge = game / "DataPC_patch_01.forge"
            game_forge.write_bytes(original)
            addition = _data_container(0x222, ENTITY_BUILDER, "Weapon")
            (mod_target / f"{ENTITY_BUILDER}_-_Weapon.data").write_bytes(addition)
            (profile / "active_mods.json").write_text(
                json.dumps(["Weapon"]), encoding="utf-8"
            )
            (instance / ".profiles" / "modlist.txt").write_text(
                "+Weapon\n", encoding="utf-8"
            )

            result = GRBDeployer(instance, game, "Default", process_root=root / "proc").deploy()

            self.assertTrue(result.success, result.errors)
            backup = instance / ".anvil" / "grb_backups" / game_forge.name
            self.assertEqual(backup.read_bytes(), original)
            deployed = ForgeArchive.read(game_forge)
            self.assertEqual(
                [entry.class_id for entry in deployed.entries], [0x111, 0x222]
            )
            manifest = json.loads(
                (instance / ".grb_deploy_manifest.json").read_text(encoding="utf-8")
            )
            self.assertEqual(manifest["active_mods"], ["Weapon"])
            self.assertEqual(manifest["archives"][0]["name"], game_forge.name)

    def test_deactivating_last_mod_restores_pristine_forge(self) -> None:
        from anvil.core.grb_deployer import GRBDeployer

        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            instance = root / "instance"
            game = root / "game"
            profile = instance / ".profiles" / "Default"
            mod_target = instance / ".mods" / "Weapon" / "DataPC_patch_01.forge"
            profile.mkdir(parents=True)
            mod_target.mkdir(parents=True)
            game.mkdir()

            original_payload = _data_container(0x111, ENTITY_BUILDER, "Original")
            original = _forge([(0x111, ENTITY_BUILDER, "Original", original_payload)])
            game_forge = game / "DataPC_patch_01.forge"
            game_forge.write_bytes(original)
            addition = _data_container(0x222, ENTITY_BUILDER, "Weapon")
            (mod_target / f"{ENTITY_BUILDER}_-_Weapon.data").write_bytes(addition)
            active_file = profile / "active_mods.json"
            active_file.write_text(json.dumps(["Weapon"]), encoding="utf-8")
            (instance / ".profiles" / "modlist.txt").write_text(
                "+Weapon\n", encoding="utf-8"
            )
            deployer = GRBDeployer(instance, game, "Default", process_root=root / "proc")
            self.assertTrue(deployer.deploy().success)
            self.assertNotEqual(game_forge.read_bytes(), original)

            active_file.write_text("[]", encoding="utf-8")
            result = deployer.deploy()

            self.assertTrue(result.success, result.errors)
            self.assertEqual(game_forge.read_bytes(), original)
            manifest = json.loads(
                (instance / ".grb_deploy_manifest.json").read_text(encoding="utf-8")
            )
            self.assertEqual(manifest["active_mods"], [])
            self.assertEqual(manifest["archives"], [])

    def test_staging_failure_does_not_partially_replace_other_forges(self) -> None:
        from anvil.core.grb_deployer import GRBDeployer

        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            instance = root / "instance"
            game = root / "game"
            profile = instance / ".profiles" / "Default"
            mod = instance / ".mods" / "Weapon"
            profile.mkdir(parents=True)
            game.mkdir()

            payload_a = _data_container(0x111, ENTITY_BUILDER, "OriginalA")
            original_a = _forge([(0x111, ENTITY_BUILDER, "OriginalA", payload_a)])
            forge_a = game / "A.forge"
            forge_a.write_bytes(original_a)
            forge_b = game / "B.forge"
            forge_b.write_bytes(b"not-a-forge")

            for target_name, class_id in (("A.forge", 0x222), ("B.forge", 0x333)):
                target = mod / target_name
                target.mkdir(parents=True)
                addition = _data_container(class_id, ENTITY_BUILDER, target_name)
                (target / f"{ENTITY_BUILDER}_-_{target_name}.data").write_bytes(
                    addition
                )
            (profile / "active_mods.json").write_text(
                json.dumps(["Weapon"]), encoding="utf-8"
            )
            (instance / ".profiles" / "modlist.txt").write_text(
                "+Weapon\n", encoding="utf-8"
            )

            result = GRBDeployer(instance, game, "Default", process_root=root / "proc").deploy()

            self.assertFalse(result.success)
            self.assertEqual(forge_a.read_bytes(), original_a)
            self.assertFalse((instance / ".grb_deploy_manifest.json").exists())

    def test_commit_failure_rolls_back_already_replaced_forge(self) -> None:
        import anvil.core.grb_deployer as grb_deployer
        from anvil.core.grb_deployer import GRBDeployer

        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            instance = root / "instance"
            game = root / "game"
            profile = instance / ".profiles" / "Default"
            mod = instance / ".mods" / "Weapon"
            profile.mkdir(parents=True)
            game.mkdir()
            originals: dict[str, bytes] = {}
            for index, target_name in enumerate(("A.forge", "B.forge"), start=1):
                payload = _data_container(index, ENTITY_BUILDER, target_name)
                original = _forge([(index, ENTITY_BUILDER, target_name, payload)])
                originals[target_name] = original
                (game / target_name).write_bytes(original)
                target = mod / target_name
                target.mkdir(parents=True)
                addition = _data_container(index + 10, ENTITY_BUILDER, target_name)
                (target / f"{ENTITY_BUILDER}_-_{target_name}.data").write_bytes(
                    addition
                )
            (profile / "active_mods.json").write_text(
                json.dumps(["Weapon"]), encoding="utf-8"
            )
            (instance / ".profiles" / "modlist.txt").write_text(
                "+Weapon\n", encoding="utf-8"
            )
            real_replace = grb_deployer.os.replace

            def fail_second_commit(source: str | Path, destination: str | Path) -> None:
                source_path = Path(source)
                destination_path = Path(destination)
                if source_path.name.endswith("B.forge.staged") and destination_path.name == "B.forge":
                    raise OSError("injected second commit failure")
                real_replace(source, destination)

            with mock.patch(
                "anvil.core.grb_deployer.os.replace", side_effect=fail_second_commit
            ):
                result = GRBDeployer(instance, game, "Default", process_root=root / "proc").deploy()

            self.assertFalse(result.success)
            for target_name, original in originals.items():
                self.assertEqual((game / target_name).read_bytes(), original)
            self.assertFalse((instance / ".grb_deploy_manifest.json").exists())

    def test_manifest_failure_rolls_back_committed_forge(self) -> None:
        from anvil.core.grb_deployer import GRBDeployer

        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            instance = root / "instance"
            game = root / "game"
            profile = instance / ".profiles" / "Default"
            mod_target = instance / ".mods" / "Weapon" / "A.forge"
            profile.mkdir(parents=True)
            mod_target.mkdir(parents=True)
            game.mkdir()
            payload = _data_container(1, ENTITY_BUILDER, "Original")
            original = _forge([(1, ENTITY_BUILDER, "Original", payload)])
            game_forge = game / "A.forge"
            game_forge.write_bytes(original)
            addition = _data_container(2, ENTITY_BUILDER, "Weapon")
            (mod_target / f"{ENTITY_BUILDER}_-_Weapon.data").write_bytes(addition)
            (profile / "active_mods.json").write_text(
                json.dumps(["Weapon"]), encoding="utf-8"
            )
            (instance / ".profiles" / "modlist.txt").write_text(
                "+Weapon\n", encoding="utf-8"
            )
            deployer = GRBDeployer(instance, game, "Default", process_root=root / "proc")

            with mock.patch.object(
                deployer, "_write_manifest", side_effect=OSError("manifest full")
            ):
                result = deployer.deploy()

            self.assertFalse(result.success)
            self.assertEqual(game_forge.read_bytes(), original)
            self.assertFalse((instance / ".grb_deploy_manifest.json").exists())

    def test_purge_restores_pristine_without_changing_active_profile(self) -> None:
        from anvil.core.grb_deployer import GRBDeployer

        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            instance = root / "instance"
            game = root / "game"
            profile = instance / ".profiles" / "Default"
            mod_target = instance / ".mods" / "Weapon" / "A.forge"
            profile.mkdir(parents=True)
            mod_target.mkdir(parents=True)
            game.mkdir()
            payload = _data_container(1, ENTITY_BUILDER, "Original")
            original = _forge([(1, ENTITY_BUILDER, "Original", payload)])
            game_forge = game / "A.forge"
            game_forge.write_bytes(original)
            addition = _data_container(2, ENTITY_BUILDER, "Weapon")
            (mod_target / f"{ENTITY_BUILDER}_-_Weapon.data").write_bytes(addition)
            active_file = profile / "active_mods.json"
            active_file.write_text(json.dumps(["Weapon"]), encoding="utf-8")
            (instance / ".profiles" / "modlist.txt").write_text(
                "+Weapon\n", encoding="utf-8"
            )
            deployer = GRBDeployer(instance, game, "Default", process_root=root / "proc")
            self.assertTrue(deployer.deploy().success)

            result = deployer.purge()

            self.assertTrue(result.success, result.errors)
            self.assertEqual(game_forge.read_bytes(), original)
            self.assertEqual(
                json.loads(active_file.read_text(encoding="utf-8")), ["Weapon"]
            )
            self.assertFalse(deployer.is_deployed())
            self.assertFalse((instance / ".grb_deploy_manifest.json").exists())

    def test_valid_but_tampered_pristine_backup_is_rejected(self) -> None:
        from anvil.core.grb_deployer import GRBDeployer

        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            instance = root / "instance"
            game = root / "game"
            profile = instance / ".profiles" / "Default"
            mod_target = instance / ".mods" / "Weapon" / "A.forge"
            profile.mkdir(parents=True)
            mod_target.mkdir(parents=True)
            game.mkdir()
            payload = _data_container(1, ENTITY_BUILDER, "Original")
            original = _forge([(1, ENTITY_BUILDER, "Original", payload)])
            game_forge = game / "A.forge"
            game_forge.write_bytes(original)
            addition = _data_container(2, ENTITY_BUILDER, "Weapon")
            (mod_target / f"{ENTITY_BUILDER}_-_Weapon.data").write_bytes(addition)
            (profile / "active_mods.json").write_text(
                json.dumps(["Weapon"]), encoding="utf-8"
            )
            (instance / ".profiles" / "modlist.txt").write_text(
                "+Weapon\n", encoding="utf-8"
            )
            deployer = GRBDeployer(instance, game, "Default", process_root=root / "proc")
            self.assertTrue(deployer.deploy().success)
            self.assertTrue(deployer.purge().success)
            self.assertEqual(game_forge.read_bytes(), original)

            tampered_payload = _data_container(9, ENTITY_BUILDER, "Tampered")
            tampered = _forge(
                [(9, ENTITY_BUILDER, "Tampered", tampered_payload)]
            )
            (deployer.backup_path / "A.forge").write_bytes(tampered)
            result = deployer.deploy()

            self.assertFalse(result.success)
            self.assertEqual(game_forge.read_bytes(), original)

    def test_purge_rejects_manifest_target_path_traversal(self) -> None:
        from anvil.core.grb_deployer import GRBDeployer

        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            instance = root / "instance"
            game = root / "game"
            instance.mkdir()
            game.mkdir()
            outside = root / "outside.forge"
            outside.write_bytes(b"sentinel")
            (instance / ".grb_deploy_manifest.json").write_text(
                json.dumps(
                    {
                        "version": 1,
                        "profile": "Default",
                        "active_mods": [],
                        "archives": [{"name": "../../outside.forge"}],
                    }
                ),
                encoding="utf-8",
            )

            result = GRBDeployer(instance, game, "Default", process_root=root / "proc").purge()

            self.assertFalse(result.success)
            self.assertTrue(
                any("invalid GRB Forge target name" in error for error in result.errors)
            )
            self.assertEqual(outside.read_bytes(), b"sentinel")

    def test_active_mod_name_cannot_escape_mods_directory(self) -> None:
        from anvil.core.grb_deployer import GRBDeployer

        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            instance = root / "instance"
            game = root / "game"
            profile = instance / ".profiles" / "Default"
            escaped_target = instance / "outside-mod" / "A.forge"
            profile.mkdir(parents=True)
            (instance / ".mods").mkdir()
            escaped_target.mkdir(parents=True)
            game.mkdir()
            payload = _data_container(1, ENTITY_BUILDER, "Original")
            original = _forge([(1, ENTITY_BUILDER, "Original", payload)])
            (game / "A.forge").write_bytes(original)
            addition = _data_container(2, ENTITY_BUILDER, "Escaped")
            (escaped_target / f"{ENTITY_BUILDER}_-_Escaped.data").write_bytes(
                addition
            )
            (profile / "active_mods.json").write_text(
                json.dumps(["../outside-mod"]), encoding="utf-8"
            )
            (instance / ".profiles" / "modlist.txt").write_text(
                "+../outside-mod\n", encoding="utf-8"
            )

            result = GRBDeployer(instance, game, "Default", process_root=root / "proc").deploy()

            self.assertFalse(result.success)
            self.assertTrue(any("invalid active mod name" in e for e in result.errors))
            self.assertEqual((game / "A.forge").read_bytes(), original)

    def test_embedded_extension_wins_over_anviltoolkit_filename_number(self) -> None:
        from anvil.core.grb_deployer import GRBDeployer

        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            instance = root / "instance"
            game = root / "game"
            profile = instance / ".profiles" / "Default"
            mod_target = instance / ".mods" / "Weapon" / "A.forge"
            profile.mkdir(parents=True)
            mod_target.mkdir(parents=True)
            game.mkdir()
            original_payload = _data_container(1, ENTITY_BUILDER, "Original")
            (game / "A.forge").write_bytes(
                _forge([(1, ENTITY_BUILDER, "Original", original_payload)])
            )
            addition = _data_container(2, ENTITY_BUILDER, "Weapon")
            (mod_target / "999_-_Weapon.data").write_bytes(addition)
            (profile / "active_mods.json").write_text(
                json.dumps(["Weapon"]), encoding="utf-8"
            )
            (instance / ".profiles" / "modlist.txt").write_text(
                "+Weapon\n", encoding="utf-8"
            )
            deployer = GRBDeployer(
                instance, game, "Default", process_root=root / "proc"
            )

            result = deployer.deploy()

            self.assertTrue(result.success, result.errors)
            archive = ForgeArchive.read(game / "A.forge")
            imported = next(entry for entry in archive.entries if entry.class_id == 2)
            self.assertEqual(imported.extension, ENTITY_BUILDER)
            self.assertEqual(imported.name, "Weapon")

    def test_deploy_refuses_while_real_grb_process_is_running(self) -> None:
        from anvil.core.grb_deployer import GRBDeployer

        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            instance = root / "instance"
            game = root / "game"
            proc_root = root / "proc"
            instance.mkdir()
            game.mkdir()
            (proc_root / "1234").mkdir(parents=True)
            (proc_root / "1234" / "comm").write_text(
                "GRB_vulkan.exe\n", encoding="utf-8"
            )
            deployer = GRBDeployer(
                instance, game, "Default", process_root=proc_root
            )

            result = deployer.deploy()

            self.assertFalse(result.success)
            self.assertTrue(any("game process is running" in e for e in result.errors))
            self.assertFalse(deployer.is_deployed())

    def test_game_start_during_staging_blocks_commit(self) -> None:
        from anvil.core.grb_deployer import GRBDeployer

        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            instance = root / "instance"
            game = root / "game"
            profile = instance / ".profiles" / "Default"
            mod_target = instance / ".mods" / "Weapon" / "A.forge"
            profile.mkdir(parents=True)
            mod_target.mkdir(parents=True)
            game.mkdir()
            payload = _data_container(1, ENTITY_BUILDER, "Original")
            original = _forge([(1, ENTITY_BUILDER, "Original", payload)])
            game_forge = game / "A.forge"
            game_forge.write_bytes(original)
            addition = _data_container(2, ENTITY_BUILDER, "Weapon")
            (mod_target / f"{ENTITY_BUILDER}_-_Weapon.data").write_bytes(addition)
            (profile / "active_mods.json").write_text(
                json.dumps(["Weapon"]), encoding="utf-8"
            )
            (instance / ".profiles" / "modlist.txt").write_text(
                "+Weapon\n", encoding="utf-8"
            )
            deployer = GRBDeployer(
                instance, game, "Default", process_root=root / "proc"
            )

            with mock.patch.object(
                deployer, "_game_process_running", side_effect=[False, True]
            ):
                result = deployer.deploy()

            self.assertFalse(result.success)
            self.assertEqual(game_forge.read_bytes(), original)
            self.assertFalse(deployer.is_deployed())


if __name__ == "__main__":
    unittest.main()
