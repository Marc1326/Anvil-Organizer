"""Dark Theme — loads Paper Dark .qss stylesheet."""

from pathlib import Path


_QSS_FILE = Path(__file__).parent / "paper_dark.qss"


def get_stylesheet() -> str:
    """Read and return the Paper Dark QSS stylesheet."""
    return _QSS_FILE.read_text(encoding="utf-8")
