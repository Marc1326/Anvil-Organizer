"""Issue #103: the profile bar must be scrollable with many profiles.

The bar already had a QScrollArea, a wheelEvent and fade edges, but the
wheel event never arrived: it is delivered to the widget under the
cursor (a tab or the scroll area's viewport), and QScrollArea consumes
it internally.  With ~30 profiles the strip was effectively unusable.
"""
from PySide6.QtCore import QPoint, QPointF, Qt
from PySide6.QtGui import QWheelEvent
from PySide6.QtWidgets import QApplication

from anvil.widgets.profile_bar import ProfileBar

MANY_PROFILES = [f"Profile {i:02d}" for i in range(30)]


def _app() -> QApplication:
    return QApplication.instance() or QApplication([])


def _wheel_event(delta: int = -120) -> QWheelEvent:
    return QWheelEvent(
        QPointF(10, 10),
        QPointF(10, 10),
        QPoint(0, 0),
        QPoint(0, delta),
        Qt.MouseButton.NoButton,
        Qt.KeyboardModifier.NoModifier,
        Qt.ScrollPhase.NoScrollPhase,
        False,
    )


def _bar_with_many_profiles() -> ProfileBar:
    _app()
    bar = ProfileBar()
    bar.set_profiles(MANY_PROFILES, active=MANY_PROFILES[0])
    bar.resize(400, 44)  # narrower than the strip needs
    bar._tabs_widget.adjustSize()
    return bar


def test_wheel_over_the_viewport_scrolls_the_strip() -> None:
    bar = _bar_with_many_profiles()
    scrollbar = bar._scroll_area.horizontalScrollBar()
    scrollbar.setRange(0, 1000)  # strip is wider than the view
    scrollbar.setValue(0)

    handled = bar.eventFilter(bar._scroll_area.viewport(), _wheel_event())

    assert handled is True, "wheel over the viewport must be handled by the bar"
    assert scrollbar.value() > 0, "the strip did not scroll"


def test_wheel_over_a_tab_scrolls_the_strip() -> None:
    bar = _bar_with_many_profiles()
    scrollbar = bar._scroll_area.horizontalScrollBar()
    scrollbar.setRange(0, 1000)
    scrollbar.setValue(0)

    assert bar._tabs, "expected tabs to exist"
    handled = bar.eventFilter(bar._tabs[0], _wheel_event())

    assert handled is True
    assert scrollbar.value() > 0


def test_wheel_scrolls_back_on_the_opposite_direction() -> None:
    bar = _bar_with_many_profiles()
    scrollbar = bar._scroll_area.horizontalScrollBar()
    scrollbar.setRange(0, 1000)
    scrollbar.setValue(500)

    bar.eventFilter(bar._scroll_area.viewport(), _wheel_event(delta=120))

    assert scrollbar.value() < 500


def test_unrelated_widgets_do_not_scroll_the_bar() -> None:
    """The filter also runs application-wide, so it must stay strict."""
    from PySide6.QtWidgets import QWidget

    bar = _bar_with_many_profiles()
    scrollbar = bar._scroll_area.horizontalScrollBar()
    scrollbar.setRange(0, 1000)
    scrollbar.setValue(0)

    stranger = QWidget()
    bar.eventFilter(stranger, _wheel_event())

    assert scrollbar.value() == 0, "a foreign widget must not scroll the bar"


def test_horizontal_wheel_is_also_accepted() -> None:
    """Touchpads and tilt wheels report on the x axis."""
    bar = _bar_with_many_profiles()
    scrollbar = bar._scroll_area.horizontalScrollBar()
    scrollbar.setRange(0, 1000)
    scrollbar.setValue(0)

    event = QWheelEvent(
        QPointF(10, 10),
        QPointF(10, 10),
        QPoint(0, 0),
        QPoint(-120, 0),  # x instead of y
        Qt.MouseButton.NoButton,
        Qt.KeyboardModifier.NoModifier,
        Qt.ScrollPhase.NoScrollPhase,
        False,
    )
    bar.eventFilter(bar._scroll_area.viewport(), event)

    assert scrollbar.value() > 0
