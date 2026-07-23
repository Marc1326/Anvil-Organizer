import json
from pathlib import Path

from anvil.core.translator import Translator


LOCALES = Path(__file__).parents[1] / "anvil" / "locales"
LANGUAGES = ("de", "en", "es", "fr", "it", "pt", "ru")


def _leaf_strings(data: dict, prefix: str = ""):
    for key, value in data.items():
        full_key = f"{prefix}.{key}" if prefix else key
        if isinstance(value, dict):
            yield from _leaf_strings(value, full_key)
        elif isinstance(value, str) and not key.startswith("_"):
            yield full_key, value


def test_locale_files_do_not_contain_flat_dotted_keys() -> None:
    for language in LANGUAGES:
        data = json.loads((LOCALES / f"{language}.json").read_text(encoding="utf-8"))
        dotted = sorted(key for key in data if "." in key)
        assert dotted == [], f"{language}: flat translation keys: {dotted}"


def test_every_locale_string_is_resolved_by_translator() -> None:
    translator = Translator()
    translator._locales_dir = LOCALES
    for language in LANGUAGES:
        data = json.loads((LOCALES / f"{language}.json").read_text(encoding="utf-8"))
        translator.load(language)
        for key, expected in _leaf_strings(data):
            assert translator.t(key) == expected, f"{language}: {key}"
