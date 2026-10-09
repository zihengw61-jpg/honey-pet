"""Dance selection and scheduling never override deliberate user interactions."""

from dataclasses import astuple
import math
import random

import pytest

from foxpet.dances import DANCE_SECONDS, DANCE_STYLES, DancePose, dance_pose
from foxpet.model import PetModel


def visible(**kwargs):
    return PetModel(presence="out", reveal=1.0, rng=random.Random(9), **kwargs)


def test_all_explicit_routines_expose_their_own_render_state():
    pet = visible()
    for style in DANCE_STYLES:
        pet.start_dance(style)
        assert pet.behavior == "dance"
        assert pet.display_state == f"dance_{style}"
        assert pet.progress == 0.0
        pet.advance(DANCE_SECONDS)
        assert pet.behavior == "idle"


def test_random_dances_do_not_repeat_and_reach_every_routine():
    pet = visible()
    selected = set()
    previous = pet.dance_style
    for _ in range(100):
        pet.react("dance")
        assert pet.dance_style != previous
        selected.add(pet.dance_style)
        previous = pet.dance_style
    assert selected == set(DANCE_STYLES)


def test_invalid_dance_does_not_reveal_or_mutate_pet():
    pet = PetModel()
    before = (pet.presence, pet.behavior, pet.dance_style, pet.dance_countdown)
    with pytest.raises(ValueError, match="Unknown dance"):
        pet.start_dance("unknown")
    assert (pet.presence, pet.behavior, pet.dance_style, pet.dance_countdown) == before


def test_peeking_pet_emerges_dances_for_full_duration_and_returns():
    pet = PetModel(rng=random.Random(1), dance_countdown=1.0)
    pet.advance(0.99)
    assert pet.presence == "peek"
    pet.advance(0.01)
    assert pet.presence == "emerging"
    assert pet.behavior == "dance"
    assert pet.dance_return_to_peek
    assert pet.progress == 0.0  # Reveal progress, with action clock still at zero.
    pet.advance(pet.transition_duration / 2)
    assert pet.behavior_elapsed == 0.0
    pet.advance(pet.transition_duration / 2)
    assert (pet.presence, pet.behavior_elapsed) == ("out", 0.0)
    pet.advance(DANCE_SECONDS - 0.01)
    assert pet.behavior == "dance"
    pet.advance(0.02)
    assert pet.presence == "retreating"
    pet.advance(pet.transition_duration)
    assert (pet.presence, pet.reveal) == ("peek", 0.0)
    assert 45 <= pet.dance_countdown <= 90


def test_visible_pet_stays_visible_after_spontaneous_dance():
    pet = visible(auto_peek=False, dance_countdown=0.1)
    pet.advance(0.1)
    assert pet.display_state.startswith("dance_")
    assert not pet.dance_return_to_peek
    pet.advance(DANCE_SECONDS)
    assert (pet.presence, pet.behavior) == ("out", "idle")


@pytest.mark.parametrize("blocked", ["paused", "sleep", "drag", "tray"])
def test_schedule_freezes_in_states_that_should_stay_quiet(blocked):
    pet = visible(dance_countdown=1.0)
    if blocked == "paused":
        pet.paused = True
    elif blocked == "tray":
        pet.presence = "tray"
    else:
        pet.behavior = blocked
    pet.advance(120.0)
    assert pet.dance_countdown == 1.0
    assert pet.behavior != "dance"


def test_disabling_spontaneous_dancing_keeps_peeking_pet_quiet():
    pet = PetModel(auto_dance=False, dance_countdown=0.1)
    pet.advance(120.0)
    assert (pet.presence, pet.behavior, pet.dance_countdown) == ("peek", "idle", 0.1)
    pet.start_dance("heart")
    assert pet.behavior == "dance"  # Manual routines remain available.


def test_pending_automatic_dance_waits_for_an_existing_reaction():
    pet = visible(behavior="happy", dance_countdown=0.1)
    pet.advance(0.2)
    assert pet.behavior == "happy"
    assert pet.dance_countdown == 0.0
    pet.advance(2.7)
    assert pet.behavior == "dance"


@pytest.mark.parametrize("interaction", ["show", "happy", "feed", "sleep", "dance", "drag", "peek", "stash"])
def test_manual_interaction_cancels_automatic_return(interaction):
    pet = PetModel(dance_countdown=0.1)
    pet.advance(0.1)
    pet.advance(pet.transition_duration)
    assert pet.dance_return_to_peek
    if interaction == "drag":
        pet.begin_drag()
    elif interaction in ("show", "peek", "stash"):
        getattr(pet, interaction)()
    else:
        pet.react(interaction)
    assert not pet.dance_return_to_peek
    pet.auto_dance = False
    pet.advance(8.0)
    expected = "peek" if interaction == "peek" else "tray" if interaction == "stash" else "out"
    assert pet.presence == expected


def test_initial_and_rescheduled_delays_are_occasional():
    pet = PetModel(rng=random.Random(42))
    assert 45 <= pet.dance_countdown <= 90
    for _ in range(10):
        pet.react("happy")
        assert 45 <= pet.dance_countdown <= 90


@pytest.mark.parametrize("style", DANCE_STYLES)
def test_routines_start_and_finish_at_neutral_pose_with_finite_joints(style):
    assert dance_pose(style, 0.0) == DancePose()
    assert dance_pose(style, 1.0) == DancePose()
    for frame in range(121):
        assert all(math.isfinite(value) for value in astuple(dance_pose(style, frame / 120)))


def test_routines_have_distinct_body_hand_and_foot_trajectories():
    paths = {}
    for style in DANCE_STYLES:
        paths[style] = tuple(
            (pose.bounce, pose.shift_x, pose.left_arm, pose.right_arm, pose.left_foot_y, pose.right_foot_y)
            for pose in (dance_pose(style, progress) for progress in (0.22, 0.38, 0.57))
        )
    assert len(set(paths.values())) == len(DANCE_STYLES)


def test_smooth_entry_and_exit_do_not_jump_between_frames():
    for style in DANCE_STYLES:
        for a, b in ((0, 0.001), (0.999, 1)):
            first, second = astuple(dance_pose(style, a)), astuple(dance_pose(style, b))
            assert max(abs(x - y) for x, y in zip(first, second)) < 0.04


@pytest.mark.parametrize("style", DANCE_STYLES)
def test_dancing_hands_feet_and_faint_effects_fit_the_high_dpi_hit_mask(style, tmp_path, monkeypatch):
    """The clickable window includes every painted physical pixel of each dance."""
    import os
    os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")
    from PySide6.QtCore import QPoint, QSettings, Qt
    from PySide6.QtGui import QImage, QPainter
    from PySide6.QtWidgets import QApplication
    from foxpet.app import PetWindow
    from foxpet.renderer import draw_scene

    app = QApplication.instance() or QApplication([])
    pet = PetWindow(settings=QSettings(str(tmp_path / "pet.ini"), QSettings.Format.IniFormat),
                    tray_available=False)
    pet.timer.stop()
    pet.call_timer.stop()
    try:
        monkeypatch.setattr(pet, "devicePixelRatioF", lambda: 2.0)
        pet.model.presence, pet.model.reveal = "out", 1.0
        pet.model.start_dance(style)
        pet.model.behavior_elapsed = DANCE_SECONDS * 0.37
        pet.model.time_s = 123.0
        pet.model.message = ""
        pet.update_hit_mask()
        artwork = QImage(pet.width() * 2, pet.height() * 2,
                         QImage.Format.Format_ARGB32_Premultiplied)
        artwork.setDevicePixelRatio(2.0)
        artwork.fill(Qt.GlobalColor.transparent)
        painter = QPainter(artwork)
        draw_scene(painter, pet.width(), pet.height(), pet.model.display_state,
                   pet.model.time_s, pet.model.progress, pet.model.reveal)
        painter.end()
        mask = pet.mask()
        visible_pixels = 0
        for y in range(artwork.height()):
            for x in range(artwork.width()):
                if artwork.pixelColor(x, y).alpha():
                    visible_pixels += 1
                    assert mask.contains(QPoint(x // 2, y // 2)), (style, x, y)
        assert visible_pixels > 1000
    finally:
        pet._single_click.stop()
        pet.tray.hide()
        pet._quitting = True
        pet.close()
        app.processEvents()
