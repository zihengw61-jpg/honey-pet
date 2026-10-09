"""Time based animation and interaction state, independent of the GUI."""

from __future__ import annotations

from dataclasses import dataclass, field
import math
import random

from .dances import DANCE_SECONDS, DANCE_STYLES

REACTION_SECONDS = {"happy": 2.8, "feed": 3.4, "dance": DANCE_SECONDS, "wave": 2.6}


def clamp_position(x, y, width, height, bounds):
    """Clamp in logical screen coordinates, including negative monitor origins."""
    left, top, area_width, area_height = bounds
    return (max(left, min(x, left + max(0, area_width - width))),
            max(top, min(y, top + max(0, area_height - height))))


@dataclass
class PetModel:
    presence: str = "peek"
    behavior: str = "idle"
    reveal: float = 0.0
    time_s: float = 0.0
    behavior_elapsed: float = 0.0
    message: str = ""
    message_remaining: float = 0.0
    paused: bool = False
    auto_peek: bool = True
    auto_dance: bool = True
    dance_style: str = "heart"
    dance_countdown: float | None = None
    dance_return_to_peek: bool = False
    idle_elapsed: float = 0.0
    rng: random.Random = field(default_factory=random.Random)
    transition_start: float = 0.0
    transition_target: float = 0.0
    transition_elapsed: float = 0.0
    transition_duration: float = 0.68
    next_idle_action: float = 14.0

    def __post_init__(self):
        if self.dance_countdown is None:
            self._schedule_dance()

    def _schedule_dance(self):
        self.dance_countdown = self.rng.uniform(45.0, 90.0)

    def _manual_interaction(self):
        self.dance_return_to_peek = False
        self._schedule_dance()

    @property
    def display_state(self):
        behavior = f"dance_{self.dance_style}" if self.behavior == "dance" else self.behavior
        return {"peek": "peek", "emerging": "emerge", "retreating": "hide"}.get(
            self.presence, behavior)

    @property
    def progress(self):
        if self.presence in ("emerging", "retreating"):
            return min(1.0, self.transition_elapsed / self.transition_duration)
        return min(1.0, self.behavior_elapsed / REACTION_SECONDS.get(self.behavior, 4.0))

    def say(self, text, seconds=3.4):
        self.message = text
        self.message_remaining = seconds

    def _transition(self, target):
        self.transition_start = self.reveal
        self.transition_target = target
        self.transition_elapsed = 0.0
        self.presence = "emerging" if target else "retreating"
        self.idle_elapsed = 0.0

    def show(self):
        self._manual_interaction()
        if self.presence == "tray":
            self.reveal = 0.0
        if self.reveal < 1.0 or self.presence == "retreating":
            self._transition(1.0)
        else:
            self.presence = "out"
        self.behavior = "wave"
        self.behavior_elapsed = 0.0
        self.idle_elapsed = 0.0

    def peek(self):
        self._manual_interaction()
        if self.presence == "tray":
            self.presence, self.reveal = "peek", 0.0
        elif self.reveal > 0.0:
            self._transition(0.0)
        else:
            self.presence = "peek"
        self.behavior = "idle"
        self.behavior_elapsed = 0.0
        self.message = ""
        self.message_remaining = 0.0

    def stash(self):
        self._manual_interaction()
        self.presence = "tray"
        self.message = ""

    def start_dance(self, style=None):
        """Start a chosen routine, or pick a different one from the last dance."""
        if style is not None and style not in DANCE_STYLES:
            raise ValueError(f"Unknown dance: {style}")
        if style is None:
            style = self.rng.choice([key for key in DANCE_STYLES if key != self.dance_style])
        self._manual_interaction()
        if self.presence != "out":
            self.show()
        self.dance_style = style
        self.behavior = "dance"
        self.behavior_elapsed = 0.0
        self.idle_elapsed = 0.0
        self.next_idle_action = self.rng.uniform(12.0, 20.0)

    def react(self, kind):
        if kind not in (*REACTION_SECONDS, "sleep", "idle"):
            raise ValueError(f"Unknown reaction: {kind}")
        if kind == "dance":
            self.start_dance()
            return
        self._manual_interaction()
        if self.presence != "out":
            self.show()
        self.behavior = kind
        self.behavior_elapsed = 0.0
        self.idle_elapsed = 0.0
        self.next_idle_action = self.rng.uniform(12.0, 20.0)

    def begin_drag(self):
        self._manual_interaction()
        # Finish a reveal before moving so the held pet is always fully visible.
        self.presence, self.reveal = "out", 1.0
        self.behavior = "drag"
        self.behavior_elapsed = 0.0
        self.idle_elapsed = 0.0
        self.say("轻轻抱着我呀", 2.0)

    def end_drag(self):
        self._manual_interaction()
        self.behavior = "idle"
        self.behavior_elapsed = 0.0
        self.idle_elapsed = 0.0

    def advance(self, dt):
        if not math.isfinite(dt) or dt < 0:
            raise ValueError("dt must be finite and nonnegative")
        if self.presence == "tray":
            return
        action_dt = dt
        if self.presence in ("emerging", "retreating"):
            if self.behavior == "dance":
                # The six-second routine starts once the little fox has emerged.
                action_dt = max(0.0, dt - max(0.0, self.transition_duration - self.transition_elapsed))
            self.transition_elapsed += dt
            t = min(1.0, self.transition_elapsed / self.transition_duration)
            smooth = t * t * (3.0 - 2.0 * t)
            self.reveal = self.transition_start + (self.transition_target - self.transition_start) * smooth
            if t == 1.0:
                self.reveal = self.transition_target
                self.presence = "out" if self.reveal else "peek"
        self.message_remaining = max(0.0, self.message_remaining - dt)
        if not self.message_remaining:
            self.message = ""
        if self.paused:
            return
        self.time_s += dt
        self.behavior_elapsed += action_dt
        if self.behavior in REACTION_SECONDS and self.behavior_elapsed >= REACTION_SECONDS[self.behavior]:
            return_to_peek = self.behavior == "dance" and self.dance_return_to_peek
            self.behavior, self.behavior_elapsed = "idle", 0.0
            if return_to_peek:
                self.peek()
                return
        if self.auto_dance and self.presence in ("out", "peek") and self.behavior not in ("sleep", "drag", "dance"):
            self.dance_countdown = max(0.0, self.dance_countdown - dt)
            if self.dance_countdown <= 1e-9 and self.behavior == "idle":
                return_to_peek = self.presence == "peek"
                self.start_dance()
                self.dance_return_to_peek = return_to_peek
                return
        if self.presence != "out" or self.behavior in ("sleep", "drag"):
            return
        self.idle_elapsed += dt
        if self.auto_peek and self.idle_elapsed >= 45.0:
            self.peek()
        elif self.behavior == "idle" and self.idle_elapsed >= self.next_idle_action:
            # Full dances have their own occasional schedule, including while peeking.
            self.behavior = "wave"
            self.behavior_elapsed = 0.0
            self.next_idle_action += self.rng.uniform(12.0, 20.0)
