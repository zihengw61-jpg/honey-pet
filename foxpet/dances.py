"""Small, original dance routines driven by action progress rather than wall time."""

from dataclasses import dataclass
import math


DANCE_STYLES = {
    "heart": "爱心摇",
    "shuffle": "左右踩点",
    "swing": "甩手扭扭",
    "bounce": "活力蹦蹦",
}
DANCE_SECONDS = 6.0


@dataclass(frozen=True)
class DancePose:
    shift_x: float = 0.0
    bounce: float = 0.0
    angle: float = 0.0
    scale_x: float = 1.0
    scale_y: float = 1.0
    head_tilt: float = 0.0
    tail_angle: float = 0.0
    ear_motion: float = 0.0
    left_arm: float = 0.0
    right_arm: float = 0.0
    left_raise: float = 0.0
    right_raise: float = 0.0
    left_foot_x: float = 0.0
    right_foot_x: float = 0.0
    left_foot_y: float = 0.0
    right_foot_y: float = 0.0
    left_foot_angle: float = -3.0
    right_foot_angle: float = 3.0
    intensity: float = 0.0


def _smooth(value: float) -> float:
    value = max(0.0, min(1.0, value))
    return value * value * (3.0 - 2.0 * value)


def dance_pose(style: str, progress: float) -> DancePose:
    """Return a smooth pose, entering and leaving through the neutral pose.

    The routines use the familiar vocabulary of short-video dances: heart
    gestures, alternating steps, arm swings and little jumps. They are original
    animations and do not depend on a particular song or current trend.
    """
    if style not in DANCE_STYLES:
        raise ValueError(f"Unknown dance: {style}")
    progress = max(0.0, min(1.0, progress))
    envelope = _smooth(progress / 0.09) * _smooth((1.0 - progress) / 0.09)
    seconds = progress * DANCE_SECONDS
    beat = seconds * math.tau * (1.15 if style == "bounce" else 0.95)
    s, c = math.sin(beat), math.cos(beat)
    values = {}
    if style == "heart":
        values = dict(
            shift_x=6 * s, bounce=-3 * s * s, angle=3 * s,
            head_tilt=-5 * s, tail_angle=10 * math.sin(beat + 0.4),
            ear_motion=3 * s, left_arm=72 + 12 * math.sin(beat / 2),
            right_arm=72 - 12 * math.sin(beat / 2),
            left_raise=1, right_raise=1,
            left_foot_x=-2 * s, right_foot_x=-2 * s,
        )
    elif style == "shuffle":
        values = dict(
            shift_x=11 * s, bounce=-3 * (1 - math.cos(beat * 2)), angle=4 * s,
            head_tilt=-3 * s, tail_angle=11 * math.sin(beat + 0.8),
            ear_motion=2 * c, left_arm=-13 + 18 * s, right_arm=-13 - 18 * s,
            left_raise=0.15, right_raise=0.15,
            left_foot_x=-9 * s, right_foot_x=9 * s,
            left_foot_y=-9 * max(0, s), right_foot_y=-9 * max(0, -s),
            left_foot_angle=-13 * s, right_foot_angle=-13 * s,
        )
    elif style == "swing":
        values = dict(
            shift_x=8 * math.sin(beat / 2), bounce=-4 * s * s, angle=6 * s,
            head_tilt=-7 * s, tail_angle=15 * math.sin(beat + 1),
            ear_motion=4 * c, left_arm=52 * s, right_arm=-52 * s,
            left_raise=0.45 + 0.3 * c, right_raise=0.45 - 0.3 * c,
            left_foot_x=-4 * c, right_foot_x=4 * c,
            left_foot_y=-4 * max(0, s), right_foot_y=-4 * max(0, -s),
        )
    else:
        hop = s * s
        values = dict(
            bounce=-20 * hop, shift_x=3 * math.sin(beat / 2), angle=2 * s,
            scale_x=1 + 0.035 * math.cos(beat * 2),
            scale_y=1 - 0.035 * math.cos(beat * 2),
            head_tilt=3 * s, tail_angle=14 * s, ear_motion=5 * c,
            left_arm=-12 + 18 * s, right_arm=-12 - 18 * s,
            left_raise=0.8, right_raise=0.8,
            left_foot_x=-6 * hop, right_foot_x=6 * hop,
            left_foot_y=-3 * hop, right_foot_y=-3 * hop,
            left_foot_angle=-14 * hop, right_foot_angle=14 * hop,
        )
    # Blending every joint avoids popping when an action starts at any clock time.
    neutral = DancePose()
    blended = {
        name: getattr(neutral, name) + (value - getattr(neutral, name)) * envelope
        for name, value in values.items()
    }
    return DancePose(**blended, intensity=envelope)
