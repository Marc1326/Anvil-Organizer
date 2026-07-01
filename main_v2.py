#!/usr/bin/env python3
"""Anvil Organizer v2 - QML modern GUI"""

import sys
import os
from pathlib import Path

from PySide6.QtGui import QGuiApplication
from PySide6.QtQml import QQmlApplicationEngine
from PySide6.QtCore import QUrl


def main() -> int:
    os.environ.setdefault("QT_QUICK_CONTROLS_STYLE", "Basic")

    app = QGuiApplication(sys.argv)
    app.setApplicationName("Anvil Organizer")
    app.setApplicationVersion("2.0.0")
    app.setOrganizationName("AnvilOrganizer")

    engine = QQmlApplicationEngine()

    qml_main = Path(__file__).parent / "qml" / "main.qml"

    if not qml_main.exists():
        print(f"ERROR: QML file not found: {qml_main}", file=sys.stderr)
        return 1

    engine.load(QUrl.fromLocalFile(str(qml_main)))

    if not engine.rootObjects():
        print("ERROR: Failed to load QML application", file=sys.stderr)
        return 1

    return app.exec()


if __name__ == "__main__":
    sys.exit(main())
