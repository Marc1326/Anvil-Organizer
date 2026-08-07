"""Tests for the Ghost Recon Breakpoint game plugin."""

from __future__ import annotations

import tempfile
import unittest
from pathlib import Path
from types import SimpleNamespace
from typing import Any
from unittest import mock

from anvil.plugins.base_game import BaseGame
from anvil.plugins.games.game_ghostreconbreakpoint import (
    GhostReconBreakpointGame,
)
from anvil.plugins.plugin_loader import PluginLoader
from anvil.widgets.game_panel import GamePanel


class GhostReconBreakpointPluginTests(unittest.TestCase):
    def test_metadata_and_executable(self) -> None:
        plugin = GhostReconBreakpointGame()

        self.assertEqual(plugin.GameShortName, "ghostreconbreakpoint")
        self.assertEqual(plugin.GameSteamId, 2231380)
        self.assertEqual(plugin.GameBinary, "GRB.exe")
        self.assertTrue(plugin.RequiresForgeDeployment)
        self.assertFalse(plugin.Tested)
        self.assertEqual(
            plugin.executables(),
            [{"name": "Ghost Recon Breakpoint", "binary": "GRB.exe"}],
        )

    def test_installation_requires_binary_and_regular_forge(self) -> None:
        plugin = GhostReconBreakpointGame()
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            self.assertFalse(plugin.looksValid(root))

            (root / "GRB.exe").write_bytes(b"binary")
            self.assertFalse(plugin.looksValid(root))

            (root / "DataPC_patch_01.forge").mkdir()
            self.assertFalse(plugin.looksValid(root))

            (root / "DataPC.forge").write_bytes(b"forge")
            self.assertTrue(plugin.looksValid(root))

    def test_rejects_binary_directory_and_external_symlinks(self) -> None:
        plugin = GhostReconBreakpointGame()
        with tempfile.TemporaryDirectory() as tmp:
            base = Path(tmp)
            root = base / "game"
            outside = base / "outside"
            root.mkdir()
            outside.mkdir()
            (root / "GRB.exe").mkdir()
            (root / "DataPC.forge").write_bytes(b"forge")
            self.assertFalse(plugin.looksValid(root))

            (root / "GRB.exe").rmdir()
            external_binary = outside / "GRB.exe"
            external_forge = outside / "DataPC.forge"
            external_binary.write_bytes(b"binary")
            external_forge.write_bytes(b"forge")
            (root / "GRB.exe").symlink_to(external_binary)
            (root / "DataPC.forge").unlink()
            (root / "DataPC.forge").symlink_to(external_forge)

            self.assertFalse(plugin.looksValid(root))
            plugin.setGamePath(root)
            self.assertEqual(plugin.forgeFiles(), [])

    def test_steam_detection_and_forge_scan(self) -> None:
        plugin = GhostReconBreakpointGame()
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            (root / "GRB.exe").write_bytes(b"binary")
            second = root / "DataPC_patch_01.forge"
            first = root / "DataPC.forge"
            second.write_bytes(b"second")
            first.write_bytes(b"first")
            (root / "DataPC_fake.forge").mkdir()

            detected = plugin.detectGame({"2231380": root}, {}, {})

            self.assertTrue(detected)
            self.assertEqual(plugin.detectedStore(), "steam")
            self.assertEqual(plugin.gameDirectory(), root)
            self.assertEqual(plugin.forgeFiles(), [first, second])

    def test_manual_path_supports_ubisoft_connect_installation(self) -> None:
        plugin = GhostReconBreakpointGame()
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            (root / "GRB.exe").write_bytes(b"binary")
            (root / "DataPC.forge").write_bytes(b"forge")

            self.assertTrue(plugin.looksValid(root))
            plugin.setGamePath(root)

            self.assertTrue(plugin.isInstalled())
            self.assertEqual(plugin.gameDirectory(), root)
            self.assertIsNone(plugin.detectedStore())

    def test_plugin_creates_native_grb_deployer(self) -> None:
        from anvil.core.grb_deployer import GRBDeployer

        plugin = GhostReconBreakpointGame()
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            instance = root / "instance"
            game = root / "game"
            deployer = plugin.create_deployer(instance, game, "Default")

            self.assertIsInstance(deployer, GRBDeployer)
            self.assertEqual(deployer.instance_path, instance)
            self.assertEqual(deployer.game_path, game)
            self.assertEqual(deployer.profile_name, "Default")

    def test_game_panel_prefers_plugin_deployer_factory(self) -> None:
        from anvil.core.grb_deployer import GRBDeployer

        plugin = GhostReconBreakpointGame()
        panel: Any = SimpleNamespace(_current_plugin=plugin)
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            deployer = GamePanel._create_deployer(
                panel, root / "instance", root / "game", "Default"
            )

            self.assertIsInstance(deployer, GRBDeployer)

    def test_forge_deployment_entrypoints_use_grb_deployer(self) -> None:
        plugin = GhostReconBreakpointGame()
        calls: list[str] = []

        class GRBDeployment:
            def deploy(self):
                calls.append("deploy")
                return SimpleNamespace(success=True, errors=[])

            def purge(self):
                calls.append("purge")
                return SimpleNamespace(success=True, errors=[])

        panel: Any = SimpleNamespace(
            _current_plugin=plugin,
            _deployer=GRBDeployment(),
        )

        first = GamePanel.silent_deploy(panel)
        second = GamePanel.silent_deploy_fast(panel)
        third = GamePanel.silent_purge(panel)

        self.assertTrue(first.success)
        self.assertTrue(second.success)
        self.assertTrue(third.success)
        self.assertEqual(calls, ["deploy", "deploy", "purge"])

    def test_failed_grb_deploy_blocks_steam_launch(self) -> None:
        plugin = GhostReconBreakpointGame()
        launched: list[tuple[object, str, bool]] = []
        panel: Any = SimpleNamespace(
            _selected_exe_index=0,
            _executables=[{"binary": "GRB.exe"}],
            _current_plugin=plugin,
            silent_deploy=lambda: SimpleNamespace(
                success=False, errors=["injected deploy failure"]
            ),
            _needs_redmod_deploy=lambda _plugin: False,
            confirm_start_while_running=lambda: True,
            _do_launch=lambda game, binary, steam: launched.append(
                (game, binary, steam)
            ),
        )

        with mock.patch("anvil.widgets.game_panel.QMessageBox.warning") as warning:
            GamePanel._on_start_clicked(panel)

        self.assertEqual(launched, [])
        warning.assert_called_once()

    def test_builtin_plugin_loader_discovers_grb(self) -> None:
        loader = PluginLoader()
        games_directory = (
            Path(__file__).resolve().parents[1] / "anvil" / "plugins" / "games"
        )

        loader._scan_directory(games_directory)

        plugin = loader.get_game("ghostreconbreakpoint")
        self.assertIsNotNone(plugin)
        assert plugin is not None
        self.assertIsInstance(plugin, BaseGame)
        self.assertEqual(plugin.__class__.__name__, "GhostReconBreakpointGame")
        self.assertEqual(plugin.GameSteamId, 2231380)


if __name__ == "__main__":
    unittest.main()
