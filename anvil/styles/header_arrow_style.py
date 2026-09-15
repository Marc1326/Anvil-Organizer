"""Sortierpfeil im modernen Design direkt neben dem Spaltentitel.

Modern haben die Spaltenköpfe keine Trennlinien. Am rechten Spaltenrand
stand der Pfeil näher am Titel der Nachbarspalte als am eigenen.
"""

from PySide6.QtCore import QRect, Qt
from PySide6.QtGui import QFont, QFontMetrics
from PySide6.QtWidgets import QHeaderView, QProxyStyle, QStyle, QStyleOptionHeader

from anvil.styles.dark_theme import theme_color

# Innenabstand wie QHeaderView::section in anvil-modern.qss
_PADDING = 5
_ARROW = 10
_GAP = 6
# bleibt rechts vom Pfeil frei -- in knappen Spalten stuende er sonst so nah
# am Titel der Nachbarspalte wie am eigenen
_MARGIN = 9
# Ist eine Spalte schmaler (selbst gezogen), rueckt der Pfeil hoechstens bis an
# seine alte Stelle am Rand, bevor er auf den Titel rutscht
_EDGE = 2


def _modern_active() -> bool:
    return bool(theme_color("panel2", ""))


def header_title_font(header: QHeaderView) -> QFont:
    """Schrift, in der die Spaltentitel gezeichnet werden."""
    header.ensurePolished()
    font = QFont(header.font())
    if _modern_active():
        # wie QHeaderView::section in anvil-modern.qss
        font.setPixelSize(10)
        font.setWeight(QFont.Weight.DemiBold)
    return font


def title_arrow_width(text_width: int, alignment) -> int:
    """Kleinste Spaltenbreite, in der Titel und Pfeil modern nebeneinander passen."""
    if alignment & Qt.AlignmentFlag.AlignHCenter:
        # Der Titel bleibt mittig, rechts daneben braucht der Pfeil Platz
        return text_width + 2 * (_GAP + _ARROW + _MARGIN)
    return text_width + _PADDING + _GAP + _ARROW + _MARGIN


def _arrow_left(rect: QRect, text_width: int, alignment) -> int:
    inner = rect.width() - 2 * _PADDING
    left = rect.x() + _PADDING
    if alignment & Qt.AlignmentFlag.AlignRight:
        # Hinter dem Titel wäre kein Platz mehr -- der Pfeil steht davor
        return max(left + inner - text_width - _GAP - _ARROW, rect.x() + _EDGE)
    if alignment & Qt.AlignmentFlag.AlignHCenter:
        left += (inner - text_width) // 2
    return min(left + text_width + _GAP, rect.x() + rect.width() - _EDGE - _ARROW)


class HeaderArrowStyle(QProxyStyle):
    """Setzt den Sortierpfeil modern neben den Titel statt an den Spaltenrand."""

    def subElementRect(self, element, option, widget=None):
        if (element == QStyle.SubElement.SE_HeaderArrow
                and _modern_active()
                and isinstance(widget, QHeaderView)
                and isinstance(option, QStyleOptionHeader)
                and option.orientation == Qt.Orientation.Horizontal
                and option.direction == Qt.LayoutDirection.LeftToRight):
            rect = option.rect
            text_width = QFontMetrics(header_title_font(widget)).horizontalAdvance(option.text)
            x = _arrow_left(rect, text_width, option.textAlignment)
            return QRect(x, rect.y() + (rect.height() - _ARROW) // 2, _ARROW, _ARROW)
        return super().subElementRect(element, option, widget)


def apply_header_arrow_style(headers) -> None:
    """Modern den Pfeil-Stil an die Köpfe hängen, klassisch wieder abnehmen."""
    modern = _modern_active()
    for header in headers:
        if header.testAttribute(Qt.WidgetAttribute.WA_SetStyle) == modern:
            continue
        if not modern:
            header.setStyle(None)
            continue
        style = header.findChild(HeaderArrowStyle, "",
                                 Qt.FindChildOption.FindDirectChildrenOnly)
        if style is None:
            style = HeaderArrowStyle()
            # Kind des Kopfes: stirbt der Stil vor dem Kopf, stürzt das Zeichnen ab
            style.setParent(header)
        header.setStyle(style)
