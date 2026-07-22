"""Regression tests for extensionless Nexus CDN downloads."""

from __future__ import annotations

import configparser
import shutil
import tempfile
import unittest
import zipfile
from pathlib import Path
from typing import Any

from anvil.core.download_manager import DownloadTask
from anvil.core.mod_installer import ModInstaller
from anvil.widgets.game_panel import GamePanel


class ExtensionlessDownloadTests(unittest.TestCase):
    def _create_uuid_zip(self, root: Path) -> Path:
        archive = root / "b23a7c55-1627-46b8-b54f-c2809cd730a3"
        with zipfile.ZipFile(archive, "w") as bundle:
            bundle.writestr("DataPC_patch_01.forge/weapon.data", b"payload")

        metadata = configparser.ConfigParser()
        metadata["General"] = {
            "gameName": "ghostreconbreakpoint",
            "modID": "1973",
            "fileID": "5014",
            "name": "NL545 vol. 2",
            "version": "1",
            "installed": "false",
            "removed": "false",
        }
        with Path(str(archive) + ".meta").open("w", encoding="utf-8") as stream:
            metadata.write(stream)
        return archive

    def test_download_scan_keeps_extensionless_zip_and_uses_meta_name(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            archive = self._create_uuid_zip(root)

            panel: Any = None
            results = GamePanel._scan_archives(panel, root)

            self.assertEqual(len(results), 1)
            self.assertEqual(results[0][0], "NL545 vol. 2")
            self.assertEqual(results[0][3], archive)

    def test_active_download_prefers_nexus_mod_name_over_uuid(self) -> None:
        task = DownloadTask(
            download_id=1,
            url="https://cf-files.nexusmods.com/cdn/b2/uuid",
            file_name="b23a7c55-1627-46b8-b54f-c2809cd730a3",
            save_path=Path("b23a7c55-1627-46b8-b54f-c2809cd730a3"),
            mod_name="NL545 vol. 2",
        )

        self.assertEqual(task.display_name(), "NL545 vol. 2")
        task.mod_name = ""
        self.assertEqual(task.display_name(), task.file_name)

    def test_installer_extracts_extensionless_zip_by_content(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            archive = self._create_uuid_zip(root)
            instance = root / "instance"
            installer = ModInstaller(instance)

            extracted = installer.extract_to_temp(archive)

            self.assertIsNotNone(extracted)
            assert extracted is not None
            self.addCleanup(shutil.rmtree, extracted, True)
            payloads = list(extracted.rglob("weapon.data"))
            self.assertEqual(len(payloads), 1)
            self.assertEqual(payloads[0].read_bytes(), b"payload")


if __name__ == "__main__":
    unittest.main()
