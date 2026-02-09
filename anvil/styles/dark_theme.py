"""Theme-System — .qss Stylesheets laden und auflisten."""

from __future__ import annotations

from pathlib import Path


_STYLES_DIR = Path(__file__).parent
_DEFAULT_THEME = "Paper Dark"


def get_styles_dir() -> Path:
    """Return the directory containing .qss stylesheets."""
    return _STYLES_DIR


def list_themes() -> list[str]:
    """Return sorted list of available theme names (without .qss extension)."""
    names = []
    for qss in _STYLES_DIR.glob("*.qss"):
        names.append(qss.stem)
    return sorted(names)


def load_theme(name: str) -> str:
    """Load a theme by name. Returns the QSS content string.

    Relative url() paths (e.g. ./Paper/Dark/) are resolved to absolute
    paths so Qt can find SVG assets regardless of the CWD.
    """
    qss_file = _STYLES_DIR / f"{name}.qss"
    if not qss_file.is_file():
        qss_file = _STYLES_DIR / f"{_DEFAULT_THEME}.qss"
    if not qss_file.is_file():
        return ""
    content = qss_file.read_text(encoding="utf-8")
    # Replace relative url("./") with absolute path to styles dir
    abs_prefix = _STYLES_DIR.as_posix()
    content = content.replace('url("./', f'url("{abs_prefix}/')
    return content


def default_theme() -> str:
    """Return the default theme name."""
    return _DEFAULT_THEME


def get_stylesheet() -> str:
    """Read and return the default stylesheet (backward compat)."""
    return load_theme(_DEFAULT_THEME)
