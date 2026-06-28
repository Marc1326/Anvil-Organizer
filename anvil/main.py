"""Entry Point Anvil Organizer."""

import os
import sys
from pathlib import Path

# Native Datei-Dialoge über XDG Desktop Portal — MUSS vor Qt-Imports stehen
# Funktioniert mit allen DEs: KDE/Dolphin, GNOME/Nautilus, Cinnamon/Nemo, XFCE/Thunar
os.environ.setdefault("QT_QPA_PLATFORMTHEME", "xdgdesktopportal")

# AppImage/PyInstaller bundelt OpenSSL mit einem fest einkompilierten Default-Cert-Pfad,
# der auf manchen Distros (Void, CachyOS, …) ins Leere zeigt → CERTIFICATE_VERIFY_FAILED.
# Bekannte System-Bundles abklappern und SSL_CERT_FILE setzen, falls leer.
if sys.platform.startswith("linux") and "SSL_CERT_FILE" not in os.environ:
    for _cert in (
        "/etc/ssl/certs/ca-certificates.crt",       # Debian, Ubuntu, Arch, CachyOS, Void
        "/etc/pki/tls/certs/ca-bundle.crt",         # Fedora, RHEL, CentOS
        "/etc/ssl/cert.pem",                        # Alpine
        "/var/lib/ca-certificates/ca-bundle.pem",   # openSUSE
    ):
        if os.path.isfile(_cert):
            os.environ["SSL_CERT_FILE"] = _cert
            os.environ.setdefault("REQUESTS_CA_BUNDLE", _cert)
            break

# Daten-Verzeichnis anlegen bevor irgendwas darauf zugreift —
# sonst scheitert QLocalServer.listen() in single_instance und Anvil exited stumm.
(Path.home() / ".anvil-organizer").mkdir(parents=True, exist_ok=True)

from PySide6.QtWidgets import QApplication
from PySide6.QtCore import QLocale, QSettings, QTranslator, QLibraryInfo
from PySide6.QtGui import QIcon

from anvil.mainwindow import MainWindow
from anvil.core.translator import Translator
from anvil.core.single_instance import SingleInstance
from anvil.core.nxm_handler import get_nxm_arg
from anvil.core.activity_log import log_action
from anvil.version import APP_VERSION


def _init_translator():
    """Initialisiert den Translator mit der gespeicherten Sprache."""
    config_path = Path.home() / ".config" / "AnvilOrganizer" / "AnvilOrganizer.conf"
    settings = QSettings(str(config_path), QSettings.Format.IniFormat)
    system_lang = QLocale.system().name()[:2]
    available = {"de", "en", "es", "fr", "it", "pt", "ru"}
    default_lang = system_lang if system_lang in available else "en"
    saved_lang = settings.value("General/language", default_lang)
    translator = Translator.instance()
    translator.load(saved_lang)


def main():
    log_action("START", f"Anvil v{APP_VERSION}")

    def _excepthook(exc_type, exc_value, exc_tb):
        import traceback
        msg = f"{exc_type.__name__}: {exc_value}"
        log_action("ERROR", msg)
        sys.__excepthook__(exc_type, exc_value, exc_tb)
    sys.excepthook = _excepthook

    app = QApplication(sys.argv)
    app.aboutToQuit.connect(lambda: log_action("EXIT", ""))
    app.setApplicationName("Anvil Organizer")
    app.setApplicationVersion(APP_VERSION)
    app.setDesktopFileName("com.github.Marc1326.AnvilOrganizer")

    # Icon-Theme für sichtbare Dialog-Icons (dark + light kompatibel)
    if not QIcon.themeName():
        QIcon.setThemeName("breeze-dark")
    QIcon.setFallbackThemeName("breeze-dark")

    # ProxyStyle: Standard-Icons durch Theme-Icons ersetzen (QFileDialog etc.)
    from anvil.styles.icon_proxy_style import IconProxyStyle
    app.setStyle(IconProxyStyle(app.style()))

    # ── Single-instance check ────────────────────────────────
    single = SingleInstance(app)
    if not single.try_lock():
        # Another instance is running — forward any nxm:// URL (mod or collection)
        raw_nxm = get_nxm_arg()
        if raw_nxm:
            if not SingleInstance.send_message(raw_nxm):
                print(
                    "[Anvil] IPC failed: could not forward NXM link to running instance",
                    file=sys.stderr,
                )
        sys.stdout.flush()
        sys.stderr.flush()
        # os._exit vermeidet einen Qt-Teardown-Crash im kurzlebigen Forwarder-Prozess
        os._exit(0)

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
