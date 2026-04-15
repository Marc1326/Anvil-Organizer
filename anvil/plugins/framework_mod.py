"""Framework mod data class for Anvil Organizer.

Framework mods are special mods that must be installed directly into the
game directory (not into a mods folder).  Examples: Script Extenders,
CET, RED4ext.

This module provides the FrameworkMod dataclass used by game plugins
to declare their known framework mods for detection and information.
Actual installation is handled elsewhere (mod_deployer).
"""

from __future__ import annotations

from dataclasses import dataclass, field


@dataclass
class FrameworkMod:
    """Describes a framework mod that installs into the game directory.

    Attributes:
        name:             Display name (e.g. "Cyber Engine Tweaks").
        pattern:          File patterns to recognize this mod in an archive.
                          Matched case-insensitively against archive contents.
        target:           Target folder relative to game directory
                          ("" = game root, "bin/" = bin subfolder).
        description:      Short description of what this mod does.
        detect_installed: File path(s) relative to game directory to check
                          if this framework is already installed.
        required_by:      Mod types that depend on this framework (for warnings).
    """

    name: str
    pattern: list[str]
    target: str
    description: str
    detect_installed: list[str]
    required_by: list[str] = field(default_factory=list)
    nexus_id: int = 0
    essential: bool = False
