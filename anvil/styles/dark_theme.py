"""Theme-System — .qss Stylesheets laden und auflisten."""

from __future__ import annotations

import re
from pathlib import Path


from anvil.core.resource_path import get_anvil_base

_STYLES_DIR = get_anvil_base() / "styles"
_DEFAULT_THEME = "Anvil Dunkel"
_FALLBACK_CLASSIC_THEME = "Paper Dark"

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

# ── Moderne Themes (GUI v2) ─────────────────────────────────────────────
# Token-basierte Themes nach dem Design-Handoff (_dev/design_handoff/README.md).
# Farbwerte stammen EXAKT aus den Token-Tabellen dort — nie aus Screenshots.
MODERN_THEME_DARK = "Anvil Dunkel"
MODERN_THEME_LIGHT = "Anvil Hell"
MODERN_THEMES = [MODERN_THEME_DARK, MODERN_THEME_LIGHT]
MODERN_DEFAULT_ACCENT = "teal"
MODERN_DEFAULT_DENSITY = "compact"

# Basis-Tokens je Theme (ohne Akzent — der kommt aus MODERN_ACCENTS).
MODERN_BASE: dict[str, dict[str, str]] = {
    MODERN_THEME_DARK: {
        "bg": "#131519", "panel": "#1a1d22", "panel2": "#20242a",
        "line": "#2a2e35", "txt": "#e7e9ed", "txt2": "#9aa1ac",
        "txt3": "#666d78", "hov": "rgba(255,255,255,0.05)",
        "ok": "#4cae7d", "warn": "#b8923f", "accent_text": "#0d1113",
        "chrome": "#1a1d22",
    },
    MODERN_THEME_LIGHT: {
        "bg": "#dcdee3", "panel": "#eceef1", "panel2": "#d3d6dc",
        "line": "#c2c6cd", "txt": "#20242c", "txt2": "#5b6170",
        "txt3": "#9096a1", "hov": "rgba(20,30,50,0.05)",
        "ok": "#2e8757", "warn": "#9a7526", "accent_text": "#0d1113",
        "chrome": "#d3d6dc",
    },
}

# Akzentfarben: {accent_key: {theme: (accent, accent_soft)}}
MODERN_ACCENTS: dict[str, dict[str, tuple[str, str]]] = {
    "teal": {
        MODERN_THEME_DARK: ("#33b3a8", "rgba(51,179,168,0.16)"),
        MODERN_THEME_LIGHT: ("#0e8a80", "rgba(14,138,128,0.13)"),
    },
    "violet": {
        MODERN_THEME_DARK: ("#8b7cf6", "rgba(139,124,246,0.16)"),
        MODERN_THEME_LIGHT: ("#6a58e6", "rgba(106,88,230,0.12)"),
    },
    "blue": {
        MODERN_THEME_DARK: ("#6f92e8", "rgba(111,146,232,0.16)"),
        MODERN_THEME_LIGHT: ("#3f63c7", "rgba(63,99,199,0.12)"),
    },
}

# Zeilendichte der Mod-Liste (Handoff: Kompakt 26 px, Komfortabel 32 px).
MODERN_ROW_HEIGHTS: dict[str, str] = {"compact": "26", "comfy": "32"}

# Zur Laufzeit aktive Palette — für Delegates/Paint-Code, der nicht über QSS
# gestylt werden kann. Wird bei jedem load_theme() aktualisiert.
_current_palette: dict[str, str] = {}


def is_modern_theme(name: str) -> bool:
    return name in MODERN_THEMES


def current_palette() -> dict[str, str]:
    """Aktive Farb-Tokens des zuletzt geladenen Themes (Kopie)."""
    return dict(_current_palette)


def theme_color(role: str, fallback: str = "#000000") -> str:
    """Einzelnen Farb-Token der aktiven Palette abfragen."""
    return _current_palette.get(role, fallback)


def _shade(hex_color: str, factor: float) -> str:
    """Hellt (factor>0) bzw. dunkelt (factor<0) eine #RRGGBB-Farbe ab."""
    h = hex_color.lstrip("#")
    r, g, b = (int(h[i:i + 2], 16) for i in (0, 2, 4))
    if factor >= 0:
        r, g, b = (round(c + (255 - c) * factor) for c in (r, g, b))
    else:
        r, g, b = (round(c * (1 + factor)) for c in (r, g, b))
    return f"#{r:02x}{g:02x}{b:02x}"


def modern_palette(name: str, accent: str | None = None) -> dict[str, str]:
    """Vollständige Token-Palette eines modernen Themes inkl. Akzent."""
    base = dict(MODERN_BASE[name])
    acc_map = MODERN_ACCENTS.get(accent or "", MODERN_ACCENTS[MODERN_DEFAULT_ACCENT])
    accent_hex, accent_soft = acc_map[name]
    base["accent"] = accent_hex
    base["accent_soft"] = accent_soft
    # Hover-/Pressed-Varianten des Akzents (im Handoff nicht definiert — abgeleitet)
    lighten = name == MODERN_THEME_DARK
    base["accent_hover"] = _shade(accent_hex, 0.12 if lighten else -0.12)
    base["accent_pressed"] = _shade(accent_hex, -0.15 if lighten else -0.25)
    return base


def style_prefs(settings) -> tuple[str, str]:
    """Liest (accent, density) aus QSettings — mit Defaults."""
    accent = settings.value("style/accent", MODERN_DEFAULT_ACCENT, type=str)
    if accent not in MODERN_ACCENTS:
        accent = MODERN_DEFAULT_ACCENT
    density = settings.value("style/density", MODERN_DEFAULT_DENSITY, type=str)
    if density not in MODERN_ROW_HEIGHTS:
        density = MODERN_DEFAULT_DENSITY
    return accent, density


def _load_modern_theme(name: str, accent: str | None, density: str | None) -> str:
    """Lädt das Modern-Template und ersetzt alle {{token}}-Platzhalter."""
    global _current_palette
    template = _STYLES_DIR / "modern" / "anvil-modern.qss"
    if not template.is_file():
        return ""
    palette = modern_palette(name, accent)
    icons_dir = _STYLES_DIR / "modern" / (
        "dark" if name == MODERN_THEME_DARK else "light")
    tokens = dict(palette)
    tokens["row_height"] = MODERN_ROW_HEIGHTS.get(
        density or "", MODERN_ROW_HEIGHTS[MODERN_DEFAULT_DENSITY])
    tokens["icons"] = icons_dir.as_posix()
    content = template.read_text(encoding="utf-8")
    for key, value in tokens.items():
        content = content.replace("{{" + key + "}}", value)
    # row_height mit in die Laufzeit-Palette — Delegates brauchen die Dichte
    _current_palette = dict(palette)
    _current_palette["row_height"] = tokens["row_height"]
    return content


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


def load_theme(name: str, overrides: dict[str, str] | None = None,
               accent: str | None = None, density: str | None = None) -> str:
    """Load a theme by name. Returns the QSS content string.

    Relative url() paths (e.g. ./Paper/Dark/) are resolved to absolute
    paths so Qt can find SVG assets regardless of the CWD.

    Mit ``overrides`` (``{role: '#RRGGBB'}``) werden die Default-Rollenfarben
    klassischer Themes ersetzt. ``accent``/``density`` gelten nur für die
    modernen Themes (Anvil Dunkel/Hell) und werden sonst ignoriert.
    """
    global _current_palette
    if is_modern_theme(name):
        content = _load_modern_theme(name, accent, density)
        if content:
            return content
        name = _FALLBACK_CLASSIC_THEME  # Template fehlt — klassischer Fallback
    qss_file = _STYLES_DIR / f"{name}.qss"
    if not qss_file.is_file():
        qss_file = _STYLES_DIR / f"{_FALLBACK_CLASSIC_THEME}.qss"
        name = _FALLBACK_CLASSIC_THEME
    if not qss_file.is_file():
        return ""
    content = qss_file.read_text(encoding="utf-8")
    # Replace relative url("./") with absolute path to styles dir
    abs_prefix = _STYLES_DIR.as_posix()
    content = content.replace('url("./', f'url("{abs_prefix}/')
    if overrides:
        content = _apply_overrides(content, name, overrides)
    # Laufzeit-Palette auch für klassische Themes bereitstellen (6 Rollen)
    palette = dict(THEME_PALETTES.get(name, {}))
    if overrides:
        palette.update({r: v for r, v in overrides.items() if _is_hex(v)})
    _current_palette = palette
    return content


def apply_theme(target, theme_name: str, overrides: dict[str, str] | None = None,
                accent: str | None = None, density: str | None = None) -> str:
    """Lädt das Theme (mit optionalen Overrides) und setzt es zentral auf ``target``.

    ``target`` ist die QApplication ODER das MainWindow — beide haben setStyleSheet.
    Gibt das gesetzte QSS zurück.
    """
    qss = load_theme(theme_name, overrides, accent=accent, density=density)
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
