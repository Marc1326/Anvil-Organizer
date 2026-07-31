"""Issue #103: a missing Proton prefix must produce an actionable message.

Without a prefix ``plugins_txt_path()`` returns ``None`` and the writer
used to hand the raw string "plugins.txt path is unavailable" straight
to the user, which gives no clue that launching the game once creates
the prefix.  The writer now supplies a translation key alongside the
internal text, and the UI resolves it.
"""
from pathlib import Path

from anvil.core.plugins_txt_writer import PluginEntry, PluginsTxtWriter

PREFIX_KEY = "game_panel.plugins_no_prefix"


class _NoPrefixGame:
    """Game whose Proton prefix does not exist yet (never launched)."""

    PRIMARY_PLUGINS = ["Skyrim.esm"]
    GameDataPath = "Data"

    def plugins_txt_path(self) -> Path | None:
        return None


class _ReadyGame(_NoPrefixGame):
    def __init__(self, target: Path) -> None:
        self._target = target

    def plugins_txt_path(self) -> Path | None:
        return self._target


def test_missing_prefix_reports_translation_key(tmp_path: Path) -> None:
    writer = PluginsTxtWriter(
        _NoPrefixGame(), tmp_path / "game", tmp_path / "instance"
    )

    assert writer.write_entries([PluginEntry(name="Skyrim.esm", active=True)]) is None
    assert writer.last_error_key == PREFIX_KEY
    assert "Proton prefix" in writer.last_error


def test_error_key_is_cleared_on_a_different_failure(tmp_path: Path) -> None:
    writer = PluginsTxtWriter(
        _NoPrefixGame(), tmp_path / "game", tmp_path / "instance"
    )
    writer.write_entries([PluginEntry(name="Skyrim.esm", active=True)])
    assert writer.last_error_key == PREFIX_KEY

    # An unrelated failure must not keep the stale prefix key around.
    assert writer.write_entries([]) is None
    assert writer.last_error_key == ""
    assert "empty plugin state" in writer.last_error


def test_successful_write_reports_no_error_key(tmp_path: Path) -> None:
    target = tmp_path / "prefix" / "plugins.txt"
    writer = PluginsTxtWriter(
        _ReadyGame(target), tmp_path / "game", tmp_path / "instance"
    )

    assert writer.write_entries([PluginEntry(name="Skyrim.esm", active=True)]) is not None
    assert writer.last_error_key == ""
    assert target.is_file()


def test_ui_resolves_the_key_into_an_actionable_message() -> None:
    from anvil.core.translator import tr
    from anvil.widgets.game_panel import localized_write_error

    message = localized_write_error("plugins.txt path is unavailable", PREFIX_KEY)

    assert "plugins.txt path is unavailable" not in message
    assert tr(PREFIX_KEY) in message
    # The "run the game once" hint is what actually unblocks the user.
    assert tr("game_panel.proton_not_found") in message


def test_ui_passes_through_text_without_a_key() -> None:
    from anvil.widgets.game_panel import localized_write_error

    assert localized_write_error("some other failure", "") == "some other failure"
