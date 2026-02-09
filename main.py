"""Entry Point Anvil Organizer."""

import sys
from PySide6.QtWidgets import QApplication
from anvil.mainwindow import MainWindow


def main():
    app = QApplication(sys.argv)
    app.setApplicationName("Anvil Organizer")
    app.setApplicationVersion("0.1.0")
    w = MainWindow()
    w.showMaximized()
    sys.exit(app.exec())


if __name__ == "__main__":
    main()
