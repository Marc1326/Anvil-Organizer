"""Issue #103: with many profiles the inline input sat outside the strip.

The user pressed "+", the field was created and focused, but never came
into view - the button looked broken.  Three causes: a freshly inserted
widget is hidden and does not count towards the sizeHint, nothing
scrolled towards the field, and the deferred selection scrolled back
afterwards.
"""
import pytest
from PySide6.QtCore import QEvent, QEventLoop, QPoint, Qt, QTimer
from PySide6.QtGui import QKeyEvent
from PySide6.QtWidgets import QApplication, QWidget

from anvil.widgets.profile_bar import INLINE_INPUT_WIDTH, ProfileBar

MANY_PROFILES = ["Default"] + [f"Profile {i:02d}" for i in range(29)]
SOME_PROFILES = ["Default", "Vanilla", "ebbp", "Profile", "ebb", "Test2", "test"]
FEW_PROFILES = ["Default", "Vanilla", "Test"]


def _app() -> QApplication:
    return QApplication.instance() or QApplication([])


@pytest.fixture(autouse=True)
def _close_bars():
    """Jede gezeigte Leiste wieder schliessen.

    ProfileBar haengt sich anwendungsweit als Ereignisfilter ein; offene
    Fenster wirken sonst in die folgenden Tests hinein.
    """
    bars: list[ProfileBar] = []
    _bar.made = bars
    yield
    for bar in bars:
        bar.close()
        bar.deleteLater()
    _app().processEvents()


def _bar(profiles: list[str], modern: bool = True, width: int = 900) -> ProfileBar:
    app = _app()
    bar = ProfileBar()
    bar._plus_inline = modern  # only the modern theme limits the container
    bar.set_profiles(profiles, active=profiles[0])
    bar.resize(width, 60)
    bar.show()
    app.processEvents()
    _bar.made.append(bar)
    return bar


def _settle(milliseconds: int = 250) -> None:
    """Run a real event loop so the deferred timers actually fire."""
    loop = QEventLoop()
    QTimer.singleShot(milliseconds, loop.quit)
    loop.exec()


def _visible_width(bar: ProfileBar, field) -> int:
    """How much of *field* actually shows inside the scroll viewport."""
    viewport = bar._scroll_area.viewport()
    left = field.mapTo(viewport, field.rect().topLeft()).x()
    right = left + field.width()
    return max(0, min(right, viewport.width()) - max(left, 0))


def _key_event(key: Qt.Key, modifier=Qt.KeyboardModifier.NoModifier) -> QKeyEvent:
    return QKeyEvent(QEvent.Type.KeyPress, key, modifier)


# --- creating a profile -----------------------------------------------------

def test_inline_input_is_fully_visible_with_many_profiles() -> None:
    """The reporter's case: 30 profiles, the field was 0 px on screen."""
    bar = _bar(MANY_PROFILES)

    bar._start_inline_create()
    _app().processEvents()  # the reveal runs on the next cycle

    assert _visible_width(bar, bar._inline_input) == INLINE_INPUT_WIDTH


def test_inline_input_is_fully_visible_with_few_profiles() -> None:
    bar = _bar(FEW_PROFILES)

    bar._start_inline_create()
    _app().processEvents()

    assert _visible_width(bar, bar._inline_input) == INLINE_INPUT_WIDTH


def test_inline_input_is_visible_in_the_classic_theme_too() -> None:
    """Without the pill container the scroll area still has to follow."""
    bar = _bar(MANY_PROFILES, modern=False)

    bar._start_inline_create()
    _app().processEvents()

    assert _visible_width(bar, bar._inline_input) == INLINE_INPUT_WIDTH


def test_container_does_not_clip_the_new_field() -> None:
    """The container measured itself before the field had a size.

    Seven profiles is the other reported case: the strip still fits on
    screen, so the clipped container is the only thing cutting the field
    down - it showed 35 px of 140.
    """
    bar = _bar(SOME_PROFILES)

    bar._start_inline_create()
    _app().processEvents()

    edit = bar._inline_input
    right_edge = edit.mapTo(bar._tabs_widget, QPoint(0, 0)).x() + edit.width()
    assert bar._tab_container.maximumWidth() >= right_edge, (
        "the container was limited to a width that predates the field"
    )


def test_field_fits_the_longest_placeholder_of_any_language() -> None:
    """Spanish is the widest one; 140 px cut it off."""
    import json
    from pathlib import Path as _Path

    bar = _bar(FEW_PROFILES)
    bar._start_inline_create()
    edit = bar._inline_input

    locales = _Path(__file__).parents[1] / "anvil" / "locales"
    widest = max(
        edit.fontMetrics().horizontalAdvance(
            json.loads(f.read_text(encoding="utf-8"))
            .get("placeholder", {}).get("profile_name", ""))
        for f in locales.glob("*.json"))

    assert edit.width() >= widest + 26, (
        f"the longest placeholder needs {widest + 26} px"
    )


def test_reveal_ignores_a_field_that_was_already_dismissed() -> None:
    """The reveal is deferred, so the field may be gone by the time it runs."""
    bar = _bar(MANY_PROFILES)
    bar._start_inline_create()
    edit = bar._inline_input
    bar._cancel_inline_create(edit)
    scrollbar = bar._scroll_area.horizontalScrollBar()
    scrollbar.setValue(0)

    bar._reveal_input(edit)  # must not raise, must not scroll

    assert scrollbar.value() == 0


def test_a_field_off_to_the_left_is_recovered_by_its_left_edge() -> None:
    """The rename field sits mid-strip, so it can end up left of the view."""
    bar = _bar(MANY_PROFILES)
    _settle()
    bar._start_inline_rename(bar._tabs[3])
    _app().processEvents()
    edit = bar._rename_input
    scrollbar = bar._scroll_area.horizontalScrollBar()
    left = edit.mapTo(bar._tabs_widget, QPoint(0, 0)).x()
    scrollbar.setValue(left + 200)  # scrolled past it
    assert _visible_width(bar, edit) < edit.width()

    bar._reveal_input(edit)

    assert scrollbar.value() == left, "the left edge was not brought back"
    assert _visible_width(bar, edit) == edit.width()


# --- the deferred scrolls that used to undo the reveal ----------------------

def test_the_deferred_selection_does_not_scroll_the_field_away() -> None:
    """set_profiles() schedules a select 100 ms later; it used to win."""
    bar = _bar(MANY_PROFILES)
    bar.set_profiles(MANY_PROFILES, active=MANY_PROFILES[0])
    bar._start_inline_create()
    _app().processEvents()

    _settle()  # let _delayed_select run

    assert _visible_width(bar, bar._inline_input) == INLINE_INPUT_WIDTH


def test_a_pending_tab_click_does_not_scroll_the_field_away() -> None:
    """Clicking a tab and hitting "+" straight after used to undo it."""
    bar = _bar(MANY_PROFILES)
    bar._on_tab_clicked(MANY_PROFILES[-1])  # starts the click timer
    bar._start_inline_create()
    _app().processEvents()

    _settle()

    assert _visible_width(bar, bar._inline_input) == INLINE_INPUT_WIDTH


def test_selecting_a_profile_does_not_scroll_the_field_away() -> None:
    """_scroll_to_tab has to stand down while an input is open."""
    bar = _bar(MANY_PROFILES)
    bar._start_inline_create()
    _app().processEvents()
    before = bar._scroll_area.horizontalScrollBar().value()

    bar._select_profile(MANY_PROFILES[0], animate=False)

    assert bar._scroll_area.horizontalScrollBar().value() == before
    assert _visible_width(bar, bar._inline_input) == INLINE_INPUT_WIDTH


def test_reloading_the_profiles_drops_an_open_field() -> None:
    """Otherwise the field survives without a layout slot and "+" goes dead."""
    bar = _bar(MANY_PROFILES)
    bar._start_inline_create()
    _app().processEvents()

    edit = bar._inline_input

    bar.set_profiles(MANY_PROFILES, active=MANY_PROFILES[0])

    assert bar._inline_input is None
    assert edit.parent() is None, "the old field is still hanging in the strip"
    bar._start_inline_create()
    assert bar._inline_input is not None, '"+" stopped working'


# --- renaming a profile -----------------------------------------------------

def test_rename_field_is_fully_visible_on_a_far_out_tab() -> None:
    """Same defect as creating, on the double-click path."""
    bar = _bar(MANY_PROFILES)
    _settle()  # let the initial selection settle first

    bar._start_inline_rename(bar._tabs[25])
    _app().processEvents()

    assert _visible_width(bar, bar._rename_input) == bar._rename_input.width()


def test_rename_field_uses_the_shared_minimum_width() -> None:
    bar = _bar(MANY_PROFILES)

    bar._start_inline_rename(bar._tabs[3])

    assert bar._rename_input.width() >= INLINE_INPUT_WIDTH


def test_container_does_not_clip_the_rename_field() -> None:
    """Same hidden-widget trap as on the create path."""
    bar = _bar(MANY_PROFILES)

    bar._start_inline_rename(bar._tabs[25])
    _app().processEvents()

    assert bar._tab_container.maximumWidth() < 16777215, (
        "the container was never measured - the Qt default is still in place"
    )
    edit = bar._rename_input
    right_edge = edit.mapTo(bar._tabs_widget, QPoint(0, 0)).x() + edit.width()
    assert bar._tab_container.maximumWidth() >= right_edge


def test_container_shrinks_back_after_renaming() -> None:
    """Otherwise an empty dark strip stays behind the tabs."""
    bar = _bar(FEW_PROFILES)
    bar._update_container_width()
    before = bar._tab_container.maximumWidth()

    bar._start_inline_rename(bar._tabs[1])
    _app().processEvents()
    bar._cancel_inline_rename(bar._rename_input, bar._tabs[1])
    _app().processEvents()

    assert bar._tab_container.maximumWidth() == before


def test_container_shrinks_back_after_confirming_a_rename() -> None:
    bar = _bar(FEW_PROFILES)
    bar._update_container_width()
    before = bar._tab_container.maximumWidth()

    tab = bar._tabs[1]
    bar._start_inline_rename(tab)
    bar._rename_input.setText("Kurz")
    bar._finish_inline_rename(bar._rename_input, tab, "Vanilla")
    _app().processEvents()

    assert bar._tab_container.maximumWidth() == bar._tabs_widget.sizeHint().width() + 8


def test_the_renamed_tab_stays_in_view() -> None:
    """The user works on one tab - that one has to stay on screen."""
    bar = _bar(MANY_PROFILES)
    _settle()
    tab = bar._tabs[25]
    bar._start_inline_rename(tab)
    _app().processEvents()

    bar._rename_input.setText("Umbenannt")
    bar._finish_inline_rename(bar._rename_input, tab, MANY_PROFILES[25])
    _app().processEvents()

    assert _visible_width(bar, tab) == tab.width()


def test_a_long_new_name_stays_fully_in_view() -> None:
    """The renamed tab can end up wider than the 200 px field."""
    bar = _bar(MANY_PROFILES)
    _settle()
    tab = bar._tabs[25]
    bar._start_inline_rename(tab)
    _app().processEvents()

    bar._rename_input.setText("Ultra Realismus Grafikpaket 2026")
    bar._finish_inline_rename(bar._rename_input, tab, MANY_PROFILES[25])
    _app().processEvents()

    assert tab.width() > INLINE_INPUT_WIDTH, "the tab should outgrow the field"
    assert _visible_width(bar, tab) == tab.width()


def test_the_renamed_tab_stays_in_view_after_cancelling() -> None:
    bar = _bar(MANY_PROFILES)
    _settle()
    tab = bar._tabs[25]
    bar._start_inline_rename(tab)
    _app().processEvents()

    bar._cancel_inline_rename(bar._rename_input, tab)
    _app().processEvents()

    assert _visible_width(bar, tab) == tab.width()


# --- what happens after the field closes ------------------------------------

def test_cancelling_puts_the_view_back_where_it_was() -> None:
    """Whatever the user had scrolled to must survive the detour."""
    bar = _bar(MANY_PROFILES)
    _settle()
    scrollbar = bar._scroll_area.horizontalScrollBar()
    scrollbar.setValue(700)  # somewhere the user chose
    bar._start_inline_create()
    _app().processEvents()
    assert scrollbar.value() != 700, "the reveal should have moved the view"

    bar._cancel_inline_create(bar._inline_input)
    _app().processEvents()

    assert scrollbar.value() == 700


def test_resizing_keeps_an_open_field_in_view() -> None:
    bar = _bar(MANY_PROFILES)
    bar._start_inline_create()
    _app().processEvents()

    for width in (700, 600, 500):
        bar.resize(width, 60)
        _app().processEvents()
        assert _visible_width(bar, bar._inline_input) == INLINE_INPUT_WIDTH, (
            f"lost the field at {width} px"
        )


def test_switching_windows_keeps_the_half_typed_name() -> None:
    """Alt-tabbing away must not throw the input away."""
    from PySide6.QtGui import QFocusEvent

    bar = _bar(MANY_PROFILES)
    bar._start_inline_create()
    _app().processEvents()
    bar._inline_input.setText("halb getippt")

    bar._inline_input.focusOutEvent(
        QFocusEvent(QEvent.Type.FocusOut, Qt.FocusReason.ActiveWindowFocusReason))
    _app().processEvents()

    assert bar._inline_input is not None, "the field was dropped"
    assert bar._inline_input.text() == "halb getippt"


def test_clicking_elsewhere_still_closes_the_field() -> None:
    """The window-switch exception must not disable the normal dismissal."""
    from PySide6.QtGui import QFocusEvent

    bar = _bar(MANY_PROFILES)
    bar._start_inline_create()
    _app().processEvents()

    bar._inline_input.focusOutEvent(
        QFocusEvent(QEvent.Type.FocusOut, Qt.FocusReason.MouseFocusReason))
    _app().processEvents()

    assert bar._inline_input is None


# --- Home / End -------------------------------------------------------------

def test_end_key_jumps_to_the_last_profile() -> None:
    bar = _bar(MANY_PROFILES)
    scrollbar = bar._scroll_area.horizontalScrollBar()
    scrollbar.setValue(0)

    handled = bar.eventFilter(bar._tabs[0], _key_event(Qt.Key.Key_End))

    assert handled is True
    assert scrollbar.value() == scrollbar.maximum()


def test_home_key_jumps_to_the_first_profile() -> None:
    bar = _bar(MANY_PROFILES)
    scrollbar = bar._scroll_area.horizontalScrollBar()
    scrollbar.setValue(scrollbar.maximum())

    handled = bar.eventFilter(bar._tabs[0], _key_event(Qt.Key.Key_Home))

    assert handled is True
    assert scrollbar.value() == scrollbar.minimum()


def test_the_keypad_variants_work_too() -> None:
    """Qt marks numpad Home/End with KeypadModifier."""
    bar = _bar(MANY_PROFILES)
    scrollbar = bar._scroll_area.horizontalScrollBar()
    scrollbar.setValue(0)

    handled = bar.eventFilter(
        bar._tabs[0],
        _key_event(Qt.Key.Key_End, Qt.KeyboardModifier.KeypadModifier),
    )

    assert handled is True
    assert scrollbar.value() == scrollbar.maximum()


def test_scroll_keys_are_left_alone_while_typing_a_name() -> None:
    """Home/End belong to the text as long as an input is open."""
    bar = _bar(MANY_PROFILES)
    bar._start_inline_create()
    _app().processEvents()
    scrollbar = bar._scroll_area.horizontalScrollBar()
    position = scrollbar.value()

    handled = bar.eventFilter(bar._tabs[0], _key_event(Qt.Key.Key_Home))

    assert handled is False
    assert scrollbar.value() == position


def test_scroll_keys_with_a_modifier_are_passed_on() -> None:
    bar = _bar(MANY_PROFILES)
    scrollbar = bar._scroll_area.horizontalScrollBar()
    scrollbar.setValue(0)

    handled = bar.eventFilter(
        bar._tabs[0],
        _key_event(Qt.Key.Key_End, Qt.KeyboardModifier.ControlModifier),
    )

    assert handled is False
    assert scrollbar.value() == 0


def test_the_wheel_works_over_the_add_button_too() -> None:
    """It sits between the tabs and the edge - a natural place to scroll."""
    from PySide6.QtCore import QPointF
    from PySide6.QtGui import QWheelEvent

    bar = _bar(MANY_PROFILES)
    scrollbar = bar._scroll_area.horizontalScrollBar()
    scrollbar.setValue(0)

    event = QWheelEvent(
        QPointF(10, 10), QPointF(10, 10), QPoint(0, 0), QPoint(0, -120),
        Qt.MouseButton.NoButton, Qt.KeyboardModifier.NoModifier,
        Qt.ScrollPhase.NoScrollPhase, False)
    handled = bar.eventFilter(bar._btn_add, event)

    assert handled is True
    assert scrollbar.value() > 0


def test_unrelated_widgets_do_not_trigger_the_scroll_keys() -> None:
    """The filter runs application-wide, so it has to stay strict."""
    bar = _bar(MANY_PROFILES)
    scrollbar = bar._scroll_area.horizontalScrollBar()
    scrollbar.setValue(0)

    stranger = QWidget()
    handled = bar.eventFilter(stranger, _key_event(Qt.Key.Key_End))

    assert handled is False
    assert scrollbar.value() == 0
