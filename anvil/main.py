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

from PySide6.QtWidgets import QApplication, QDialog
from PySide6.QtCore import QLocale, QSettings, QTranslator, QLibraryInfo
from PySide6.QtGui import QIcon

from anvil.core.base_dir import (
    anvil_base_paths,
    configure_base_dir,
    configured_base_is_custom,
    legacy_base_dir,
    resolve_base_dir,
    top_level_settings,
)
from anvil.core.translator import Translator
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


def _ensure_base_directory(app: QApplication) -> bool:
    settings = top_level_settings()
    from anvil.core.base_migration import pending_base_migration

    if pending_base_migration(settings) is not None:
        from anvil.widgets.base_migration_dialog import BaseMigrationProgressDialog

        migration_dialog = BaseMigrationProgressDialog(None, settings=settings)
        if migration_dialog.start() != QDialog.DialogCode.Accepted:
            return False

    configured = resolve_base_dir(settings)
    custom = configured_base_is_custom(settings)
    first_run = not settings.contains("General/base_dir") and not legacy_base_dir().exists()
    recovery = custom and not configured.is_dir()

    if not first_run and not recovery:
        configure_base_dir(
            configured if custom else legacy_base_dir(),
            settings=settings,
            create=True,
        )
        return True

    from anvil.widgets.base_dir_setup_dialog import BaseDirSetupDialog

    dialog = BaseDirSetupDialog(
        None,
        settings=settings,
        recovery=recovery,
        missing_path=configured if recovery else None,
    )
    return dialog.exec() == QDialog.DialogCode.Accepted


def main():
    app = QApplication(sys.argv)
    app.setApplicationName("Anvil Organizer")
    app.setApplicationVersion(APP_VERSION)
    app.setDesktopFileName("com.github.Marc1326.AnvilOrganizer")

    # Translator muss vor dem First-Run-/Recovery-Dialog bereit sein.
    _init_translator()

    # Icon-Theme für sichtbare Dialog-Icons (dark + light kompatibel)
    if not QIcon.themeName():
        QIcon.setThemeName("breeze-dark")
    QIcon.setFallbackThemeName("breeze-dark")

    # ProxyStyle: Standard-Icons durch Theme-Icons ersetzen (QFileDialog etc.)
    from anvil.styles.icon_proxy_style import IconProxyStyle
    app.setStyle(IconProxyStyle(app.style()))

    if not _ensure_base_directory(app):
        return 0

    # Basisabhängige Module erst nach Auswahl bzw. Recovery importieren.
    from anvil.mainwindow import MainWindow
    from anvil.core.activity_log import log_action
    from anvil.core.desktop_shortcut import get_launch_instance_arg
    from anvil.core.nxm_handler import get_nxm_arg
    from anvil.core.single_instance import SingleInstance

    log_action("START", f"Anvil v{APP_VERSION}")

    def _excepthook(exc_type, exc_value, exc_tb):
        msg = f"{exc_type.__name__}: {exc_value}"
        log_action("ERROR", msg)
        sys.__excepthook__(exc_type, exc_value, exc_tb)

    sys.excepthook = _excepthook
    app.aboutToQuit.connect(lambda: log_action("EXIT", ""))

    # ── Single-instance check ────────────────────────────────
    single = SingleInstance(app)
    if not single.try_lock():
        # Another instance is running — forward nxm:// URL or shortcut launch request
        raw_nxm = get_nxm_arg()
        launch_inst = get_launch_instance_arg()
        if raw_nxm:
            if not SingleInstance.send_message(raw_nxm):
                print(
                    "[Anvil] IPC failed: could not forward NXM link to running instance",
                    file=sys.stderr,
                )
        elif launch_inst:
            if not SingleInstance.send_message(f"anvil-launch:{launch_inst}"):
                print(
                    "[Anvil] IPC failed: could not forward launch request to running instance",
                    file=sys.stderr,
                )
        sys.stdout.flush()
        sys.stderr.flush()
        # os._exit vermeidet einen Qt-Teardown-Crash im kurzlebigen Forwarder-Prozess
        os._exit(0)

    # Qt-eigene Übersetzungen laden (für About Qt, Datei-Dialoge, etc.)
    lang = Translator.instance().current_language
    qt_translator = QTranslator(app)
    translations_path = QLibraryInfo.path(QLibraryInfo.LibraryPath.TranslationsPath)
    if qt_translator.load(f"qtbase_{lang}", translations_path):
        app.installTranslator(qt_translator)

    w = MainWindow()

    # Connect IPC → MainWindow (nxm:// forwarding + shortcut launch requests)
    single.message_received.connect(w.handle_ipc_message)

    w.showMaximized()
    exit_code = app.exec()
    # Auf manchen Distros segfaultet der Qt/xcb-Teardown in libxkbcommon (#90, #86).
    # closeEvent hat zu diesem Zeitpunkt bereits gepurged und den UI-State gespeichert,
    # daher den Prozess hart beenden statt den crashenden Python/Qt-Teardown zu durchlaufen.
    sys.stdout.flush()
    sys.stderr.flush()
    os._exit(exit_code)


if __name__ == "__main__":
    main()
