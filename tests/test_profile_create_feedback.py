"""Issue #103: creating a profile must never fail silently.

The profile bar used to drop invalid or duplicate names without a word,
and MainWindow returned early on several error paths.  The user saw
nothing happen and had no way to tell why.
"""
import json
from pathlib import Path

from anvil.core.profile_name import is_valid_profile_name

LOCALES = Path(__file__).resolve().parent.parent / "anvil" / "locales"
LANGUAGES = ["de", "en", "fr", "es", "it", "pt", "ru"]
NEW_KEYS = [
    "profile_invalid_name",
    "profile_exists",
    "profile_no_instance",
    "profile_create_failed",
]


def _toast_block(language: str) -> dict:
    data = json.loads((LOCALES / f"{language}.json").read_text(encoding="utf-8"))
    return data["toast"]


def test_feedback_messages_exist_in_every_language() -> None:
    for language in LANGUAGES:
        toast = _toast_block(language)
        for key in NEW_KEYS:
            assert key in toast, f"{language}.json misses toast.{key}"
            assert toast[key].strip(), f"{language}.json has an empty toast.{key}"


def test_placeholders_are_consistent_across_languages() -> None:
    for language in LANGUAGES:
        toast = _toast_block(language)
        assert "{name}" in toast["profile_exists"], language
        assert "{error}" in toast["profile_create_failed"], language
        # These two are plain sentences; a stray placeholder would raise
        # at format() time.
        assert "{" not in toast["profile_invalid_name"], language
        assert "{" not in toast["profile_no_instance"], language


def test_messages_format_without_error() -> None:
    for language in LANGUAGES:
        toast = _toast_block(language)
        assert "Test" in toast["profile_exists"].format(name="Test")
        assert "boom" in toast["profile_create_failed"].format(error="boom")


def test_rejected_names_are_the_ones_the_bar_reports() -> None:
    # The bar strips the input before validating, so mirror that here:
    # whatever survives the strip must be what decides the outcome, and
    # the "invalid name" message must therefore always be truthful.
    def as_the_bar_sees_it(raw: str) -> bool:
        return is_valid_profile_name(raw.strip())

    for bad in ["", "   ", ".", "..", "a/b", "a\\b", "\t"]:
        assert not as_the_bar_sees_it(bad), f"{bad!r} should be rejected"

    # Surrounding whitespace is trimmed, not rejected.
    for good in ["Vanilla", "Test 2", "mein-profil", " lead", "trail "]:
        assert as_the_bar_sees_it(good), f"{good!r} should be accepted"


def test_profile_bar_emits_a_rejection_signal() -> None:
    """The bar must expose the signal MainWindow connects to."""
    from anvil.widgets.profile_bar import ProfileBar

    assert hasattr(ProfileBar, "profile_create_rejected")


def test_the_rejection_carries_the_name_the_message_needs() -> None:
    """Without it the toast reads a literal '{name}' back to the user."""
    from PySide6.QtWidgets import QApplication

    from anvil.core.translator import tr
    from anvil.widgets.profile_bar import ProfileBar

    QApplication.instance() or QApplication([])
    bar = ProfileBar()
    bar.set_profiles(["Default", "Vanilla"], active="Default")
    seen = []
    bar.profile_create_rejected.connect(lambda key, name: seen.append((key, name)))

    bar._start_inline_create()
    bar._inline_input.setText("Vanilla")  # duplicate
    bar._finish_inline_create(bar._inline_input)

    assert seen, "the bar stayed silent about the duplicate"
    key, name = seen[-1]
    assert name == "Vanilla"
    message = tr(key, name=name)
    assert "Vanilla" in message
    assert "{" not in message, f"placeholder left unfilled: {message!r}"
