"""Interaction and timing contracts for the desktop pet's animation state."""

import math
import random

import pytest

from foxpet.model import PetModel, REACTION_SECONDS, clamp_position


def fully_visible(**kwargs):
    return PetModel(presence="out", reveal=1.0, rng=random.Random(3), **kwargs)


def test_default_pet_is_peeking_and_click_reveals_it():
    pet = PetModel()
    assert pet.display_state == "peek"
    assert pet.reveal == 0.0

    pet.show()
    assert pet.display_state == "emerge"
    pet.advance(0.1)
    assert 0.0 < pet.reveal < 1.0
    pet.advance(2.0)

    assert pet.presence == "out"
    assert pet.reveal == 1.0
    assert pet.behavior == "wave"


def test_rapid_transition_reversals_do_not_jump():
    pet = PetModel()
    pet.show()
    pet.advance(0.22)
    partial_reveal = pet.reveal

    pet.peek()
    assert pet.reveal == partial_reveal
    pet.advance(0.13)
    partial_hide = pet.reveal
    assert 0.0 < partial_hide < partial_reveal

    pet.show()
    assert pet.reveal == partial_hide
    pet.advance(0.13)
    assert partial_hide < pet.reveal < 1.0

    pet.peek()
    pet.advance(2.0)
    assert pet.presence == "peek"
    assert pet.reveal == 0.0

    pet.show()
    pet.advance(2.0)
    assert pet.presence == "out"
    assert pet.reveal == 1.0


@pytest.mark.parametrize("frame_seconds", [0.68, 3.0, 10.0])
def test_transition_reaches_exact_endpoints_on_long_frames(frame_seconds):
    pet = PetModel()
    pet.show()
    pet.advance(frame_seconds)
    assert (pet.presence, pet.reveal) == ("out", 1.0)

    pet.peek()
    pet.advance(frame_seconds)
    assert (pet.presence, pet.reveal) == ("peek", 0.0)


@pytest.mark.parametrize("initial_presence", ["peek", "out", "tray"])
@pytest.mark.parametrize("reaction", ["happy", "feed", "dance", "wave"])
def test_reactions_reveal_the_pet_and_finish(initial_presence, reaction):
    pet = PetModel(
        presence=initial_presence,
        reveal=1.0 if initial_presence == "out" else 0.0,
        rng=random.Random(1),
    )
    pet.react(reaction)
    assert pet.behavior == reaction
    pet.advance(0.7)
    assert (pet.presence, pet.reveal) == ("out", 1.0)
    assert pet.behavior == reaction

    pet.advance(REACTION_SECONDS[reaction])
    assert pet.behavior == "idle"


def test_tray_stops_animation_and_can_return_to_peek():
    pet = fully_visible()
    pet.say("你好")
    pet.stash()
    elapsed = pet.time_s
    pet.advance(120.0)
    assert pet.presence == "tray"
    assert pet.time_s == elapsed
    assert pet.message == ""

    pet.peek()
    assert (pet.presence, pet.reveal) == ("peek", 0.0)


def test_sleep_persists_until_an_interaction_wakes_pet():
    pet = fully_visible()
    pet.react("sleep")
    pet.advance(120.0)
    assert (pet.presence, pet.behavior) == ("out", "sleep")

    pet.react("happy")
    assert pet.behavior == "happy"
    pet.advance(REACTION_SECONDS["happy"])
    assert pet.behavior == "idle"


def test_drag_finishes_reveal_and_is_not_interrupted_by_idle_timer():
    pet = PetModel()
    pet.show()
    pet.advance(0.1)
    pet.begin_drag()
    assert (pet.presence, pet.reveal, pet.behavior) == ("out", 1.0, "drag")

    pet.advance(120.0)
    assert (pet.presence, pet.reveal, pet.behavior) == ("out", 1.0, "drag")
    pet.end_drag()
    assert (pet.presence, pet.behavior) == ("out", "idle")
    pet.advance(1.0)
    assert pet.presence == "out"


def test_pause_freezes_behavior_but_allows_show_and_hide():
    pet = PetModel(paused=True)
    pet.show()
    pet.say("你好", seconds=1.0)
    pet.advance(2.0)
    assert (pet.presence, pet.reveal) == ("out", 1.0)
    assert pet.behavior == "wave"
    assert pet.time_s == 0.0
    assert pet.behavior_elapsed == 0.0
    assert pet.message == ""

    pet.peek()
    pet.advance(2.0)
    assert (pet.presence, pet.reveal) == ("peek", 0.0)


def test_auto_peek_waits_for_deadline_and_user_activity_resets_it():
    pet = fully_visible(next_idle_action=math.inf)
    pet.advance(44.9)
    assert pet.presence == "out"
    pet.react("happy")
    pet.advance(44.9)
    assert pet.presence == "out"
    pet.advance(0.11)
    assert pet.presence == "retreating"
    pet.advance(1.0)
    assert (pet.presence, pet.reveal) == ("peek", 0.0)


def test_auto_peek_can_be_disabled():
    pet = fully_visible(auto_peek=False)
    pet.advance(120.0)
    assert pet.presence == "out"


@pytest.mark.parametrize("dt", [-0.001, -1.0, math.inf, -math.inf, math.nan])
@pytest.mark.parametrize("presence", ["peek", "tray"])
def test_invalid_frame_time_is_rejected_even_while_hidden(dt, presence):
    pet = PetModel(presence=presence)
    with pytest.raises(ValueError, match="finite and nonnegative"):
        pet.advance(dt)


def test_zero_frame_time_does_not_move_animation():
    pet = PetModel()
    pet.show()
    pet.advance(0.1)
    before = (pet.reveal, pet.time_s, pet.behavior_elapsed)
    pet.advance(0.0)
    assert (pet.reveal, pet.time_s, pet.behavior_elapsed) == before


def test_unknown_reaction_does_not_change_presence():
    pet = PetModel()
    with pytest.raises(ValueError, match="Unknown reaction"):
        pet.react("unknown")
    assert (pet.presence, pet.reveal) == ("peek", 0.0)


@pytest.mark.parametrize(
    ("position", "bounds", "expected"),
    [
        ((50, 60), (0, 0, 1920, 1080), (50, 60)),
        ((-20, -30), (0, 0, 1920, 1080), (0, 0)),
        ((1910, 1070), (0, 0, 1920, 1080), (1620, 780)),
        ((-1600, -700), (-1920, -1080, 1920, 1080), (-1600, -700)),
        ((100, 100), (-1920, -1080, 1920, 1080), (-300, -300)),
        ((-2500, -2000), (-1920, -1080, 1920, 1080), (-1920, -1080)),
        ((500, 500), (-20, -30, 100, 80), (-20, -30)),
    ],
)
def test_window_position_is_clamped_to_available_screen(position, bounds, expected):
    assert clamp_position(*position, 300, 300, bounds) == expected
