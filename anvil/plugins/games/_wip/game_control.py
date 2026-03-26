"""Control game plugin for Anvil Organizer — auto-generated from MO2.

Control von Remedy Entertainment. Mods werden direkt ins
Spielverzeichnis platziert. Das Spiel hat DX11 und DX12 Versionen.

Features:
  - Store-Erkennung (Steam, GOG)
  - Nexus-Mods-Integration

TODO:
  - DX11/DX12 Executable-Auswahl
  - DLL forced loads (iphlpapi.dll, xinput1_4.dll)
"""

from __future__ import annotations

from anvil.plugins.base_game import BaseGame


class ControlGame(BaseGame):
    """Control support plugin."""

    Tested = False

    # -- Plugin-Metadaten ---------------------------------------------------

    Name = "Control Support Plugin"
    Author = "Anvil Organizer Team"
    Version = "1.0.0"

    # -- Spiel-Attribute ----------------------------------------------------

    GameName = "Control"
    GameShortName = "control"
    GameBinary = "Control.exe"
    GameDataPath = ""

    GameSteamId = 870780
    GameGogId = 2049187585

    GameNexusId = 2936
    GameNexusName = "control"

    # -- Executables --------------------------------------------------------

    def executables(self) -> list[dict[str, str]]:
        """Executables fuer Control (Launcher, DX11, DX12)."""
        return [
            {"name": "Control (Launcher)", "binary": "Control.exe"},
            {"name": "Control DX11", "binary": "Control_DX11.exe"},
            {"name": "Control DX12", "binary": "Control_DX12.exe"},
        ]
