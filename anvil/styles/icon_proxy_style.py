"""QProxyStyle der Standard-Icons durch Theme-Icons ersetzt.

Löst das Problem, dass QFileDialog-Toolbar-Icons bei dunklen
QSS-Themes unsichtbar werden, weil Qt die Standard-Pixmaps
durch leere ersetzt wenn ein Stylesheet aktiv ist.
"""

from PySide6.QtWidgets import QProxyStyle, QStyle
from PySide6.QtGui import QIcon


# Mapping: Qt StandardPixmap → freedesktop Icon-Name
_ICON_MAP = {
    QStyle.StandardPixmap.SP_ArrowBack: "go-previous",
    QStyle.StandardPixmap.SP_ArrowForward: "go-next",
    QStyle.StandardPixmap.SP_FileDialogToParent: "go-up",
    QStyle.StandardPixmap.SP_FileDialogNewFolder: "folder-new",
    QStyle.StandardPixmap.SP_FileDialogListView: "view-list-text",
    QStyle.StandardPixmap.SP_FileDialogDetailedView: "view-list-details",
    QStyle.StandardPixmap.SP_DialogOpenButton: "document-open",
    QStyle.StandardPixmap.SP_DialogSaveButton: "document-save",
    QStyle.StandardPixmap.SP_DialogCancelButton: "dialog-cancel",
    QStyle.StandardPixmap.SP_DialogCloseButton: "window-close",
    QStyle.StandardPixmap.SP_DirIcon: "folder",
    QStyle.StandardPixmap.SP_FileIcon: "text-x-generic",
    QStyle.StandardPixmap.SP_DirOpenIcon: "folder-open",
    QStyle.StandardPixmap.SP_ComputerIcon: "computer",
    QStyle.StandardPixmap.SP_DesktopIcon: "user-desktop",
    QStyle.StandardPixmap.SP_DriveFDIcon: "media-floppy",
    QStyle.StandardPixmap.SP_DriveHDIcon: "drive-harddisk",
    QStyle.StandardPixmap.SP_TrashIcon: "user-trash",
    QStyle.StandardPixmap.SP_DialogHelpButton: "help-contents",
}


class IconProxyStyle(QProxyStyle):
    """Ersetzt Standard-Icons durch Theme-Icons (breeze-dark kompatibel)."""

    def standardIcon(self, standard_pixmap, option=None, widget=None):
        icon_name = _ICON_MAP.get(standard_pixmap)
        if icon_name:
            icon = QIcon.fromTheme(icon_name)
            if not icon.isNull():
                return icon
        return super().standardIcon(standard_pixmap, option, widget)
