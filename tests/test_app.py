"""Headless Qt checks for user input and recovering a hidden pet."""

import os

os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")

import pytest
from PySide6.QtCore import QPoint, QSettings, Qt
from PySide6.QtGui import QImage, QPainter
from PySide6.QtTest import QTest
from PySide6.QtWidgets import QApplication, QSystemTrayIcon

from foxpet.app import PetWindow
from foxpet.renderer import draw_scene


@pytest.fixture(scope="module")
def application():
    app = QApplication.instance() or QApplication([])
    original_interval = app.doubleClickInterval()
    app.setDoubleClickInterval(40)
    yield app
    app.setDoubleClickInterval(original_interval)


@pytest.fixture
def pet(application, tmp_path):
    settings = QSettings(str(tmp_path / "pet.ini"), QSettings.Format.IniFormat)
    window = PetWindow(settings=settings, tray_available=False)
    window.timer.stop()
    window.show()
    application.processEvents()
    yield window
    window._single_click.stop()
    window.timer.stop()
    window.tray.hide()
    window._quitting = True
    window.close()
    application.processEvents()


def make_visible(pet):
    pet.model.show()
    pet.model.advance(1.0)
    pet.model.message = ""
    pet.update_hit_mask()


def test_click_on_peeking_head_reveals_pet(pet, application):
    QTest.mouseClick(pet, Qt.MouseButton.LeftButton, pos=QPoint(150, 260))
    assert pet.model.presence == "peek"
    QTest.qWait(application.doubleClickInterval() + 30)
    assert pet.model.presence == "emerging"
    pet.model.advance(1.0)
    assert (pet.model.presence, pet.model.reveal) == ("out", 1.0)


def test_drag_moves_pet_without_turning_into_a_click(pet, application):
    make_visible(pet)
    before = pet.pos()
    start = QPoint(150, 180)
    end = start - QPoint(70, 90)

    QTest.mousePress(pet, Qt.MouseButton.LeftButton, pos=start)
    QTest.mouseMove(pet, end)
    QTest.mouseRelease(pet, Qt.MouseButton.LeftButton, pos=end)
    QTest.qWait(application.doubleClickInterval() + 30)

    assert pet.pos() != before
    assert pet.model.presence == "out"
    assert pet.model.behavior == "idle"


def test_double_click_dance_cancels_pending_single_click(pet, application):
    make_visible(pet)
    position = QPoint(150, 180)
    QTest.mouseClick(pet, Qt.MouseButton.LeftButton, pos=position)
    QTest.mouseDClick(pet, Qt.MouseButton.LeftButton, pos=position)
    QTest.mouseRelease(pet, Qt.MouseButton.LeftButton, pos=position)
    QTest.qWait(application.doubleClickInterval() + 30)
    assert pet.model.behavior == "dance"


def test_missing_tray_keeps_pet_accessible(pet):
    make_visible(pet)
    assert not pet.tray.isVisible()
    assert pet.hide_to_tray() is False
    assert pet.isVisible()
    pet.model.advance(1.0)
    assert (pet.model.presence, pet.model.reveal) == ("peek", 0.0)
    hide_action = next(action for action in pet.menu.actions()
                       if action.text() == "藏到右下角托盘")
    assert not hide_action.isEnabled()


def test_close_without_tray_returns_to_corner_instead_of_losing_pet(pet):
    make_visible(pet)
    pet.close()
    assert pet.isVisible()
    assert pet.model.presence == "retreating"
    pet.model.advance(1.0)
    assert pet.model.presence == "peek"


def test_summon_recovers_hidden_pet_and_uses_saved_nickname(pet):
    pet.nickname = "小可爱"
    pet.model.stash()
    pet.hide()
    pet.summon()
    assert pet.isVisible()
    assert pet.model.presence == "emerging"
    assert "小可爱" in pet.model.message
    pet.model.advance(1.0)
    assert pet.model.presence == "out"


def test_tray_activation_recovers_hidden_pet(pet):
    pet.model.stash()
    pet.hide()
    pet.tray.activated.emit(QSystemTrayIcon.ActivationReason.Trigger)
    assert pet.isVisible()
    assert pet.model.presence == "emerging"


@pytest.mark.parametrize("revealed", [False, True])
def test_window_mask_leaves_transparent_corners_clickable(pet, revealed):
    if revealed:
        make_visible(pet)
    pet.model.message = ""
    pet.update_hit_mask()
    mask = pet.mask()
    assert pet.rect().contains(mask.boundingRect())
    assert not mask.isEmpty()
    for point in (QPoint(0, 0), QPoint(pet.width() - 1, 0),
                  QPoint(0, pet.height() - 1), QPoint(pet.width() - 1, pet.height() - 1)):
        assert not mask.contains(point)


def test_size_change_keeps_pet_in_available_screen(pet):
    make_visible(pet)
    pet.move(100000, 100000)
    pet.set_pet_size(1.2)
    area = QApplication.primaryScreen().availableGeometry()
    assert area.contains(pet.geometry())
    assert pet.width() == 360
    assert pet.height() == 384


def test_user_preferences_are_saved(pet):
    pet.toggle_auto_peek(False)
    pet.toggle_pause(True)
    pet.set_pet_size(0.8)
    pet.settings.sync()
    reopened = QSettings(pet.settings.fileName(), QSettings.Format.IniFormat)
    assert reopened.value("auto_peek", type=bool) is False
    assert reopened.value("paused", type=bool) is True
    assert reopened.value("scale", type=float) == 0.8


@pytest.mark.parametrize("ratio", [1.0, 2.0])
@pytest.mark.parametrize(
    ("behavior", "time_s", "reveal"),
    [("wave", 0.21, 1.0), ("dance", 0.65, 1.0),
     ("happy", 1.23, 1.0), ("sleep", 0.4, 1.0), ("peek", 0.7, 0.0)],
)
def test_animated_artwork_is_never_clipped_by_window_mask(
    pet, monkeypatch, ratio, behavior, time_s, reveal,
):
    """Moving paws, tilted ears, and faint effects remain visible/clickable."""
    monkeypatch.setattr(pet, "devicePixelRatioF", lambda: ratio)
    pet.model.presence = "peek" if behavior == "peek" else "out"
    pet.model.behavior = "idle" if behavior == "peek" else behavior
    pet.model.time_s = time_s
    pet.model.reveal = reveal
    pet.model.message = ""
    pet.update_hit_mask()
    assert pet._frame.devicePixelRatio() == ratio
    assert pet._frame.width() == round(pet.width() * ratio)
    assert pet._frame.height() == round(pet.height() * ratio)

    # Render independently: a fixed neutral silhouette must not crop any part
    # of the actual animation, including physical pixels on a Retina display.
    artwork = QImage(round(pet.width() * ratio), round(pet.height() * ratio),
                     QImage.Format.Format_ARGB32_Premultiplied)
    artwork.setDevicePixelRatio(ratio)
    artwork.fill(Qt.GlobalColor.transparent)
    painter = QPainter(artwork)
    draw_scene(painter, pet.width(), pet.height(), pet.model.display_state,
               time_s, pet.model.progress, reveal)
    painter.end()

    mask = pet.mask()
    assert pet.rect().contains(mask.boundingRect())
    outside = []
    visible_pixels = 0
    for y in range(artwork.height()):
        for x in range(artwork.width()):
            if artwork.pixelColor(x, y).alpha():
                visible_pixels += 1
                logical = QPoint(int(x / ratio), int(y / ratio))
                if not mask.contains(logical):
                    outside.append((x, y))
    assert visible_pixels > 1000
    assert not outside, f"Window mask clips {len(outside)} painted pixels; first: {outside[:5]}"
