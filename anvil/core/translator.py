"""Übersetzungssystem für Anvil Organizer.

Verwendung:
    from anvil.core.translator import tr

    # Einfacher String
    label.setText(tr("menu.file"))  # → "Datei"

    # Mit Variablen
    status.setText(tr("status.mods_loaded", count=50, active=30))
    # → "50 Mods geladen (30 aktiv)"
"""

import json
from pathlib import Path
from typing import Any


class Translator:
    """Singleton-Klasse für Übersetzungen."""

    _instance: "Translator | None" = None

    def __init__(self):
        self._current_lang = "de"
        self._strings: dict[str, Any] = {}
        self._fallback: dict[str, Any] = {}
        from anvil.core.resource_path import get_anvil_base
        self._locales_dir = get_anvil_base() / "locales"

        # Lade Standard-Sprache
        self._load_language(self._current_lang)

        # Lade Fallback (Englisch)
        if self._current_lang != "en":
            self._fallback = self._load_json("en")

    @classmethod
    def instance(cls) -> "Translator":
        """Gibt die Singleton-Instanz zurück."""
        if cls._instance is None:
            cls._instance = cls()
        return cls._instance

    def _load_json(self, lang: str) -> dict[str, Any]:
        """Lädt eine Sprachdatei."""
        path = self._locales_dir / f"{lang}.json"
        if not path.exists():
            return {}
        try:
            with open(path, "r", encoding="utf-8") as f:
                return json.load(f)
        except (json.JSONDecodeError, OSError):
            return {}

    def _load_language(self, lang: str) -> None:
        """Lädt die angegebene Sprache."""
        self._strings = self._load_json(lang)
        self._current_lang = lang

    def load(self, lang: str) -> None:
        """Wechselt die Sprache (erfordert App-Neustart für volle Wirkung)."""
        self._load_language(lang)
        if lang != "en":
            self._fallback = self._load_json("en")
        else:
            self._fallback = {}

    def t(self, key: str, **kwargs) -> str:
        """Übersetzt einen Key.

        Args:
            key: Punkt-separierter Key (z.B. "menu.file")
            **kwargs: Variablen für String-Formatierung

        Returns:
            Übersetzter String oder Key falls nicht gefunden
        """
        # Key aufteilen: "menu.file" → ["menu", "file"]
        parts = key.split(".")

        # In aktueller Sprache suchen
        value = self._get_nested(self._strings, parts)

        # Fallback auf Englisch
        if value is None:
            value = self._get_nested(self._fallback, parts)

        # Fallback auf Key selbst
        if value is None:
            return key

        # Variablen einsetzen
        if kwargs:
            try:
                return value.format(**kwargs)
            except (KeyError, ValueError):
                return value

        return value

    def _get_nested(self, d: dict, parts: list[str]) -> str | None:
        """Holt einen verschachtelten Wert aus einem Dict."""
        current = d
        for part in parts:
            if not isinstance(current, dict):
                return None
            current = current.get(part)
            if current is None:
                return None
        return current if isinstance(current, str) else None

    @property
    def current_language(self) -> str:
        """Gibt die aktuelle Sprache zurück."""
        return self._current_lang

    def available_languages(self) -> list[tuple[str, str]]:
        """Gibt verfügbare Sprachen zurück als [(code, name), ...]."""
        languages = []
        if self._locales_dir.exists():
            for f in sorted(self._locales_dir.glob("*.json")):
                code = f.stem
                # Sprachname aus der Datei selbst holen
                data = self._load_json(code)
                name = data.get("_language_name", code.upper())
                languages.append((code, name))
        return languages if languages else [("de", "Deutsch"), ("en", "English")]


# Globale Instanz für einfachen Import
def tr(key: str, **kwargs) -> str:
    """Shortcut für Translator.instance().t(key, **kwargs)."""
    return Translator.instance().t(key, **kwargs)
