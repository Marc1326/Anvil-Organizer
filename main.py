"""Entry Point Anvil Organizer."""

import sys
from pathlib import Path

from PySide6.QtWidgets import QApplication
from PySide6.QtCore import QSettings, QTranslator, QLibraryInfo

from anvil.mainwindow import MainWindow
from anvil.core.translator import Translator
from anvil.core.single_instance import SingleInstance
from anvil.core.nxm_handler import check_cli_for_nxm


def _init_translator():
    """Initialisiert den Translator mit der gespeicherten Sprache."""
    config_path = Path.home() / ".config" / "AnvilOrganizer" / "AnvilOrganizer.conf"
    settings = QSettings(str(config_path), QSettings.Format.IniFormat)
    saved_lang = settings.value("General/language", "de")
    translator = Translator.instance()
    translator.load(saved_lang)


def main():
    app = QApplication(sys.argv)
    app.setApplicationName("Anvil Organizer")
    app.setApplicationVersion("0.2.0")

    # ── Single-instance check ────────────────────────────────
    single = SingleInstance(app)
    if not single.try_lock():
        # Another instance is running — forward nxm:// URL if present
        nxm_link = check_cli_for_nxm()
        if nxm_link:
            if not SingleInstance.send_message(nxm_link.raw_url):
                print(
                    "[Anvil] IPC failed: could not forward NXM link to running instance",
                    file=sys.stderr,
                )
        sys.exit(0)

    # Translator mit gespeicherter Sprache initialisieren
    _init_translator()

    # Qt-eigene Übersetzungen laden (für About Qt, Datei-Dialoge, etc.)
    lang = Translator.instance().current_language
    qt_translator = QTranslator(app)
    translations_path = QLibraryInfo.path(QLibraryInfo.LibraryPath.TranslationsPath)
    if qt_translator.load(f"qtbase_{lang}", translations_path):
        app.installTranslator(qt_translator)

    w = MainWindow()

    # Connect IPC → MainWindow for nxm:// forwarding
    single.message_received.connect(w.handle_nxm_url)

    w.showMaximized()
    sys.exit(app.exec())


if __name__ == "__main__":
    main()
