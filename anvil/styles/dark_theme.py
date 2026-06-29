"""Theme-System — .qss Stylesheets laden und auflisten."""

from __future__ import annotations

import re
from pathlib import Path


from anvil.core.resource_path import get_anvil_base

_STYLES_DIR = get_anvil_base() / "styles"
_DEFAULT_THEME = "Paper Dark"

# Vom Benutzer anpassbare Farbrollen (Reihenfolge = Anzeige im Style-Tab).
COLOR_ROLES = [
    "background",
    "text",
    "accent",
    "list_background",
    "hover",
    "disabled_text",
]

# Default-Rollenfarben je Theme (aus den .qss extrahiert, paarweise verschieden).
# "1809 Dark Mode" nutzt eine transparente Basis und teilt sich Listen-/Hintergrund,
# daher 5 statt 6 Rollen. Hex exakt wie im QSS (Ersetzung läuft case-insensitiv).
# Hinweis: Es wird nur der exakte Rollen-Hex ersetzt; abgeleitete Schattierungen
# (z.B. hellere/dunklere Akzent-Varianten in Hover/Border) bleiben unverändert.
THEME_PALETTES: dict[str, dict[str, str]] = {
    "1809 Dark Mode": {
        "background": "#202020", "text": "#DEDEDE", "accent": "#0078D7",
        "hover": "#4D4D4D", "disabled_text": "#636363",
    },
    "Catppuccin Mocha": {
        "background": "#1E1E2E", "text": "#CDD6F4", "accent": "#CBA6F7",
        "list_background": "#181825", "hover": "#313244", "disabled_text": "#585B70",
    },
    "Cyberpunk": {
        "background": "#0A0A12", "text": "#E0E0E0", "accent": "#FCE300",
        "list_background": "#12121E", "hover": "#1A1A2E", "disabled_text": "#4A4A5A",
    },
    "Dracula": {
        "background": "#282A36", "text": "#F8F8F2", "accent": "#BD93F9",
        "list_background": "#21222C", "hover": "#44475A", "disabled_text": "#6272A4",
    },
    "Gruvbox Dark": {
        "background": "#282828", "text": "#EBDBB2", "accent": "#FE8019",
        "list_background": "#1D2021", "hover": "#3C3836", "disabled_text": "#665C54",
    },
    "Nord": {
        "background": "#2E3440", "text": "#D8DEE9", "accent": "#5E81AC",
        "list_background": "#3B4252", "hover": "#434C5E", "disabled_text": "#4C566A",
    },
    "One Dark": {
        "background": "#282C34", "text": "#ABB2BF", "accent": "#61AFEF",
        "list_background": "#21252B", "hover": "#2C313A", "disabled_text": "#5C6370",
    },
    "Paper Dark": {
        "background": "#242424", "text": "#D3D3D3", "accent": "#006868",
        "list_background": "#141414", "hover": "#3D3D3D", "disabled_text": "#808080",
    },
    "Solarized Dark": {
        "background": "#002B36", "text": "#93A1A1", "accent": "#268BD2",
        "list_background": "#073642", "hover": "#0A4A5A", "disabled_text": "#586E75",
    },
}

_HEX_RE = re.compile(r"^#(?:[0-9A-Fa-f]{3}|[0-9A-Fa-f]{6}|[0-9A-Fa-f]{8})$")


def _is_hex(value) -> bool:
    return bool(isinstance(value, str) and _HEX_RE.match(value))


def _norm_hex(value: str) -> str:
    """Vergleichsform: Großschreibung, #RGB zu #RRGGBB expandiert."""
    v = value.upper()
    if len(v) == 4:
        v = "#" + "".join(c * 2 for c in v[1:])
    return v


def get_styles_dir() -> Path:
    """Return the directory containing .qss stylesheets."""
    return _STYLES_DIR


def list_themes() -> list[str]:
    """Return sorted list of available theme names (without .qss extension)."""
    names = []
    for qss in _STYLES_DIR.glob("*.qss"):
        names.append(qss.stem)
    return sorted(names)


def default_palette(theme_name: str) -> dict[str, str]:
    """Default-Rollenfarben eines Themes als {role: '#RRGGBB'}. Leer wenn unbekannt."""
    return dict(THEME_PALETTES.get(theme_name, {}))


def _apply_overrides(content: str, name: str, overrides: dict[str, str]) -> str:
    """Ersetzt die Default-Rollenfarben durch die Overrides — in EINEM Durchlauf.

    Einzeldurchlauf per Alternation, damit eine bereits ersetzte Farbe nicht von
    einer weiteren Rolle erneut getroffen wird (Ketten-Ersetzung vermeiden).
    """
    palette = THEME_PALETTES.get(name, {})
    if not palette:
        return content
    repl: dict[str, str] = {}
    for role, default_hex in palette.items():
        new_hex = overrides.get(role)
        if _is_hex(new_hex) and _norm_hex(new_hex) != _norm_hex(default_hex):
            repl[_norm_hex(default_hex)] = new_hex
    if not repl:
        return content
    # Längere Tokens zuerst, damit kein kürzeres Präfix vorgreift.
    defaults = sorted(
        (dh for dh in palette.values() if _norm_hex(dh) in repl),
        key=len, reverse=True,
    )
    pattern = "(?:" + "|".join(re.escape(dh) for dh in defaults) + r")(?![0-9A-Fa-f])"
    return re.sub(pattern, lambda m: repl[_norm_hex(m.group(0))], content,
                  flags=re.IGNORECASE)


def load_theme(name: str, overrides: dict[str, str] | None = None) -> str:
    """Load a theme by name. Returns the QSS content string.

    Relative url() paths (e.g. ./Paper/Dark/) are resolved to absolute
    paths so Qt can find SVG assets regardless of the CWD.

    Mit ``overrides`` (``{role: '#RRGGBB'}``) werden die Default-Rollenfarben
    des Themes ersetzt. Ohne Overrides identisch zum bisherigen Verhalten.
    """
    qss_file = _STYLES_DIR / f"{name}.qss"
    if not qss_file.is_file():
        qss_file = _STYLES_DIR / f"{_DEFAULT_THEME}.qss"
        name = _DEFAULT_THEME
    if not qss_file.is_file():
        return ""
    content = qss_file.read_text(encoding="utf-8")
    # Replace relative url("./") with absolute path to styles dir
    abs_prefix = _STYLES_DIR.as_posix()
    content = content.replace('url("./', f'url("{abs_prefix}/')
    if overrides:
        content = _apply_overrides(content, name, overrides)
    return content


def apply_theme(target, theme_name: str, overrides: dict[str, str] | None = None) -> str:
    """Lädt das Theme (mit optionalen Overrides) und setzt es zentral auf ``target``.

    ``target`` ist die QApplication ODER das MainWindow — beide haben setStyleSheet.
    Gibt das gesetzte QSS zurück.
    """
    qss = load_theme(theme_name, overrides)
    target.setStyleSheet(qss)
    return qss


_OVERRIDE_PREFIX = "style/overrides"


def _theme_slug(theme_name: str) -> str:
    """QSettings-tauglicher Schlüssel aus dem Theme-Namen (Leerzeichen → _)."""
    slug = re.sub(r"[^0-9A-Za-z]+", "_", theme_name or "").strip("_")
    return slug or "theme"


def load_overrides(settings, theme_name: str) -> dict[str, str]:
    """Liest gespeicherte Farb-Overrides eines Themes aus QSettings.

    ``settings`` ist ein QSettings-artiges Objekt. Liefert nur gültige Hex-Werte.
    """
    slug = _theme_slug(theme_name)
    result: dict[str, str] = {}
    for role in COLOR_ROLES:
        val = settings.value(f"{_OVERRIDE_PREFIX}/{slug}/{role}", "", type=str)
        if _is_hex(val):
            result[role] = val
    return result


def save_overrides(settings, theme_name: str, overrides: dict[str, str]) -> None:
    """Speichert Farb-Overrides eines Themes pro Rolle; entfernt ungültige/leere."""
    slug = _theme_slug(theme_name)
    for role in COLOR_ROLES:
        key = f"{_OVERRIDE_PREFIX}/{slug}/{role}"
        new_hex = overrides.get(role) if overrides else None
        if _is_hex(new_hex):
            settings.setValue(key, new_hex)
        else:
            settings.remove(key)


def default_theme() -> str:
    """Return the default theme name."""
    return _DEFAULT_THEME


def get_stylesheet() -> str:
    """Read and return the default stylesheet (backward compat)."""
    return load_theme(_DEFAULT_THEME)
