"""Original, resolution-independent artwork for the Little Fox desktop pet.

All artwork is painted locally.  No image files, fonts, or network services are
needed, and the same drawing is used for the desktop pet and its tray icon.
"""

from __future__ import annotations

import math
from functools import lru_cache

from PySide6.QtCore import QPointF, QRectF, Qt
from PySide6.QtGui import (
    QColor,
    QFont,
    QIcon,
    QLinearGradient,
    QPainter,
    QPainterPath,
    QPen,
    QPixmap,
    QRadialGradient,
)

SCENE_WIDTH = 300.0
SCENE_HEIGHT = 320.0
PEEK_OFFSET = 135.0

_OUTLINE = QColor("#843e38")
_COCOA = QColor("#533b3c")
_CREAM = QColor("#fff0d6")


def _clamp(value: float, lower: float = 0.0, upper: float = 1.0) -> float:
    return max(lower, min(upper, value))


def _pen(color: QColor | str, width: float = 2.0) -> QPen:
    result = QPen(QColor(color), width)
    result.setCapStyle(Qt.PenCapStyle.RoundCap)
    result.setJoinStyle(Qt.PenJoinStyle.RoundJoin)
    return result


def _gradient(x1: float, y1: float, x2: float, y2: float, *colors: str):
    gradient = QLinearGradient(x1, y1, x2, y2)
    for index, color in enumerate(colors):
        gradient.setColorAt(index / max(1, len(colors) - 1), QColor(color))
    return gradient


def _path(points) -> QPainterPath:
    """Small helper for readable, hand-drawn cubic silhouettes."""
    result = QPainterPath()
    for operation, coordinates in points:
        if operation == "M":
            result.moveTo(*coordinates)
        elif operation == "L":
            result.lineTo(*coordinates)
        elif operation == "Q":
            result.quadTo(*coordinates)
        elif operation == "C":
            result.cubicTo(*coordinates)
        elif operation == "Z":
            result.closeSubpath()
    return result


@lru_cache(maxsize=1)
def _head_path() -> QPainterPath:
    return _path([
        ("M", (150, 67)),
        ("C", (127, 57, 99, 61, 81, 81)),
        ("C", (66, 97, 62, 116, 67, 134)),
        ("Q", (57, 145, 73, 142)),
        ("Q", (61, 154, 76, 169)),
        ("C", (90, 190, 118, 201, 150, 201)),
        ("C", (182, 201, 210, 190, 224, 169)),
        ("Q", (239, 154, 227, 142)),
        ("Q", (243, 145, 233, 134)),
        ("C", (238, 116, 234, 97, 219, 81)),
        ("C", (201, 61, 173, 57, 150, 67)),
        ("Z", ()),
    ])


@lru_cache(maxsize=2)
def _ear_path(right: bool = False) -> QPainterPath:
    path = _path([
        ("M", (91, 103)),
        ("C", (78, 85, 65, 61, 69, 37)),
        ("Q", (70, 28, 79, 32)),
        ("C", (101, 41, 118, 64, 123, 87)),
        ("Q", (116, 105, 91, 103)),
        ("Z", ()),
    ])
    if right:
        from PySide6.QtGui import QTransform

        path = QTransform(-1, 0, 0, 1, 300, 0).map(path)
    return path


@lru_cache(maxsize=1)
def _tail_path() -> QPainterPath:
    return _path([
        ("M", (177, 250)),
        ("C", (206, 278, 260, 273, 275, 236)),
        ("C", (287, 208, 277, 183, 260, 180)),
        ("C", (248, 178, 238, 190, 242, 201)),
        ("C", (253, 227, 226, 244, 199, 225)),
        ("C", (188, 217, 174, 234, 177, 250)),
        ("Z", ()),
    ])


@lru_cache(maxsize=1)
def _body_path() -> QPainterPath:
    return _path([
        ("M", (121, 180)),
        ("C", (106, 193, 101, 224, 106, 247)),
        ("C", (108, 274, 124, 283, 150, 282)),
        ("C", (176, 283, 192, 274, 194, 247)),
        ("C", (199, 224, 194, 193, 179, 180)),
        ("Z", ()),
    ])


def _ellipse_hit(x: float, y: float, cx: float, cy: float, rx: float, ry: float) -> bool:
    return ((x - cx) / rx) ** 2 + ((y - cy) / ry) ** 2 <= 1


def scene_hit_test(
    x: float, y: float, width: float, height: float, reveal: float
) -> bool:
    """Hit-test the visible neutral silhouette, including the little peek paws.

    The hidden body never catches desktop clicks.  Hosts may additionally use
    the rendered alpha mask for animated hands or speech bubbles.
    """
    if width <= 0 or height <= 0:
        return False
    scale = min(width / SCENE_WIDTH, height / SCENE_HEIGHT)
    x = (x - (width - SCENE_WIDTH * scale) / 2) / scale
    y = (y - (height - SCENE_HEIGHT * scale) / 2) / scale
    if not 0 <= x <= SCENE_WIDTH or not 0 <= y <= SCENE_HEIGHT:
        return False
    reveal = _clamp(reveal)
    if reveal < 0.96 and (
        _ellipse_hit(x, y, 105, 315, 15, 13)
        or _ellipse_hit(x, y, 195, 315, 15, 13)
    ):
        return True
    y -= PEEK_OFFSET * (1 - reveal)
    point = QPointF(x, y)
    if any(path.contains(point) for path in (_head_path(), _ear_path(), _ear_path(True), _body_path(), _tail_path())):
        return True
    return (
        _ellipse_hit(x, y, 122, 279, 20, 12)
        or _ellipse_hit(x, y, 178, 279, 20, 12)
        or _ellipse_hit(x, y, 105, 222, 16, 28)
        or _ellipse_hit(x, y, 195, 222, 16, 28)
    )


def _draw_ear(painter: QPainter, right: bool, angle: float) -> None:
    painter.save()
    pivot = 201 if right else 99
    painter.translate(pivot, 87)
    painter.rotate(-angle if right else angle)
    painter.translate(-pivot, -87)
    painter.setPen(_pen(_OUTLINE, 2.6))
    painter.setBrush(_gradient(80, 35, 110, 103, "#f8a071", "#e96551"))
    painter.drawPath(_ear_path(right))
    painter.save()
    if right:
        painter.translate(300, 0)
        painter.scale(-1, 1)
    inner = _path([
        ("M", (91, 87)),
        ("C", (82, 71, 78, 52, 78, 42)),
        ("C", (93, 51, 106, 65, 112, 82)),
        ("Q", (103, 78, 91, 87)),
        ("Z", ()),
    ])
    painter.setPen(Qt.PenStyle.NoPen)
    painter.setBrush(_gradient(82, 43, 107, 88, "#ffe0c1", "#eaa1a0"))
    painter.drawPath(inner)
    painter.setPen(_pen(QColor(255, 238, 217, 140), 2))
    painter.drawLine(QPointF(77, 39), QPointF(78, 54))
    painter.restore()
    painter.restore()


def _draw_tail(painter: QPainter, angle: float) -> None:
    painter.save()
    painter.translate(186, 246)
    painter.rotate(angle)
    painter.translate(-186, -246)
    painter.setPen(_pen(_OUTLINE, 2.5))
    painter.setBrush(_gradient(199, 215, 261, 263, "#f99768", "#df624b", "#c65245"))
    painter.drawPath(_tail_path())
    painter.setPen(Qt.PenStyle.NoPen)
    painter.setBrush(_gradient(252, 180, 270, 222, "#fff7df", "#ffe7c4"))
    tip = _path([
        ("M", (258, 181)),
        ("C", (274, 180, 286, 204, 277, 226)),
        ("Q", (272, 211, 263, 217)),
        ("Q", (258, 205, 248, 211)),
        ("C", (237, 194, 244, 181, 258, 181)),
        ("Z", ()),
    ])
    painter.drawPath(tip)
    painter.setPen(_pen(QColor(255, 201, 151, 160), 2))
    painter.drawPath(_path([("M", (212, 254)), ("C", (231, 259, 248, 252, 256, 239))]))
    painter.restore()


def _draw_foot(painter: QPainter, x: float, y: float, angle: float = 0) -> None:
    painter.save()
    painter.translate(x, y)
    painter.rotate(angle)
    painter.setPen(_pen(_OUTLINE, 2.2))
    painter.setBrush(_gradient(-10, -8, 5, 11, "#f09267", "#db6550"))
    painter.drawEllipse(QRectF(-19, -11, 38, 22))
    painter.setPen(_pen(QColor("#c25547"), 1.5))
    painter.drawLine(QPointF(-6, 3), QPointF(-6, 7))
    painter.drawLine(QPointF(1, 4), QPointF(1, 8))
    painter.restore()


def _draw_arm(painter: QPainter, right: bool, angle: float, raised: bool = False) -> None:
    painter.save()
    if right:
        painter.translate(300, 0)
        painter.scale(-1, 1)
    painter.translate(112, 202)
    painter.rotate(angle)
    painter.translate(-112, -202)
    if raised:
        arm = _path([
            ("M", (118, 200)),
            ("C", (100, 204, 91, 191, 88, 177)),
            ("C", (83, 164, 68, 167, 70, 181)),
            ("C", (70, 211, 91, 230, 112, 219)),
            ("Z", ()),
        ])
    else:
        arm = _path([
            ("M", (110, 195)),
            ("C", (95, 200, 88, 221, 93, 239)),
            ("C", (96, 250, 108, 249, 113, 239)),
            ("C", (119, 224, 127, 204, 110, 195)),
            ("Z", ()),
        ])
    painter.setPen(_pen(_OUTLINE, 2.3))
    painter.setBrush(_gradient(94, 187, 108, 244, "#f19367", "#df6852"))
    painter.drawPath(arm)
    painter.setPen(Qt.PenStyle.NoPen)
    painter.setBrush(_CREAM)
    if raised:
        painter.drawEllipse(QRectF(71, 164, 18, 23))
        painter.setBrush(QColor("#eea29f"))
        painter.drawEllipse(QRectF(77, 171, 7, 9))
    else:
        painter.drawEllipse(QRectF(94, 230, 18, 17))
    painter.restore()


def _draw_scarf(painter: QPainter, sway: float) -> None:
    painter.setPen(_pen(QColor("#766084"), 2))
    painter.setBrush(_gradient(143, 188, 151, 213, "#c7b4e5", "#a891cf"))
    painter.drawRoundedRect(QRectF(108, 181, 83, 28), 12, 12)
    painter.save()
    painter.translate(184, 201)
    painter.rotate(sway)
    painter.translate(-184, -201)
    painter.setBrush(_gradient(182, 201, 190, 237, "#b49bd7", "#9d86c3"))
    painter.drawPath(_path([
        ("M", (180, 198)), ("Q", (194, 195, 195, 207)),
        ("L", (199, 235)), ("Q", (189, 242, 180, 234)),
        ("L", (178, 209)), ("Z", ()),
    ]))
    painter.setPen(_pen(QColor("#dfccef"), 1.4))
    painter.drawLine(QPointF(184, 232), QPointF(185, 237))
    painter.drawLine(QPointF(190, 233), QPointF(191, 238))
    painter.restore()
    painter.setPen(_pen(QColor("#a07a4f"), 1.4))
    painter.setBrush(QColor("#ffe4a3"))
    star = QPainterPath()
    for index in range(10):
        angle = -math.pi / 2 + index * math.pi / 5
        radius = 8 if index % 2 == 0 else 4
        point = QPointF(150 + math.cos(angle) * radius, 204 + math.sin(angle) * radius)
        if index == 0:
            star.moveTo(point)
        else:
            star.lineTo(point)
    star.closeSubpath()
    painter.drawPath(star)


def _blink(time_s: float) -> float:
    # Two quick, irregularly spaced blinks in a long cycle feel less mechanical.
    phase = time_s % 7.3
    for center in (2.63, 5.91):
        distance = abs(phase - center)
        if distance < 0.095:
            return _clamp(distance / 0.095)
    return 1.0


def _draw_eye(painter: QPainter, x: float, y: float, opening: float, look, happy: bool = False, sleeping: bool = False) -> None:
    if opening < 0.18 or happy or sleeping:
        painter.setPen(_pen(_COCOA, 3.3))
        painter.setBrush(Qt.BrushStyle.NoBrush)
        arch = -7 if happy else 5
        painter.drawPath(_path([("M", (x - 9, y + 2)), ("Q", (x, y + arch, x + 9, y + 2))]))
        return
    gaze_x, gaze_y = look
    eye_y = y + _clamp(float(gaze_y), -1, 1) * 2
    eye_x = x + _clamp(float(gaze_x), -1, 1) * 3
    painter.save()
    painter.translate(eye_x, eye_y)
    painter.scale(1, max(0.2, opening))
    painter.setPen(Qt.PenStyle.NoPen)
    painter.setBrush(_gradient(-4, -11, 4, 13, "#463337", "#71504a"))
    painter.drawEllipse(QRectF(-9, -13, 18, 27))
    painter.setBrush(QColor("#fff8ec"))
    painter.drawEllipse(QRectF(-5, -9, 6.2, 7.4))
    painter.setBrush(QColor(255, 225, 193, 150))
    painter.drawEllipse(QRectF(3, 4, 3.4, 3.4))
    painter.restore()


def _draw_face(painter: QPainter, state: str, time_s: float, look, tilt: float, ear_motion: float, paused: bool) -> None:
    painter.save()
    painter.translate(150, 154)
    painter.rotate(tilt)
    painter.translate(-150, -154)
    _draw_ear(painter, False, ear_motion)
    _draw_ear(painter, True, -ear_motion * 0.65)
    painter.setPen(_pen(_OUTLINE, 2.8))
    painter.setBrush(_gradient(126, 66, 171, 196, "#ffa578", "#ef7c5c", "#dc6251"))
    painter.drawPath(_head_path())
    painter.setPen(Qt.PenStyle.NoPen)
    painter.setBrush(_gradient(140, 133, 153, 201, "#fff8e6", "#ffe7c5"))
    painter.drawPath(_path([
        ("M", (76, 125)),
        ("C", (86, 137, 103, 132, 119, 142)),
        ("C", (132, 151, 139, 157, 150, 157)),
        ("C", (161, 157, 168, 151, 181, 142)),
        ("C", (197, 132, 214, 137, 224, 125)),
        ("C", (229, 154, 218, 175, 200, 185)),
        ("C", (180, 197, 162, 198, 150, 198)),
        ("C", (138, 198, 120, 197, 100, 185)),
        ("C", (82, 175, 71, 154, 76, 125)),
        ("Z", ()),
    ]))
    # Three soft fur tufts make the forehead less like a rigid geometric oval.
    painter.setBrush(QColor(255, 190, 133, 130))
    painter.drawPath(_path([
        ("M", (131, 72)), ("Q", (141, 78, 145, 91)),
        ("Q", (149, 77, 152, 72)), ("Q", (159, 83, 160, 93)),
        ("Q", (167, 79, 173, 73)), ("Q", (151, 61, 131, 72)),
        ("Z", ()),
    ]))
    blush = QRadialGradient(91, 155, 16)
    blush.setColorAt(0, QColor(242, 141, 141, 110))
    blush.setColorAt(1, QColor(242, 141, 141, 0))
    painter.setBrush(blush)
    painter.drawEllipse(QRectF(73, 145, 36, 20))
    blush.setCenter(209, 155)
    blush.setFocalPoint(209, 155)
    painter.setBrush(blush)
    painter.drawEllipse(QRectF(191, 145, 36, 20))
    happy = state in ("happy", "dance", "feed")
    sleeping = state == "sleep" or paused
    opening = 0 if sleeping else _blink(time_s)
    _draw_eye(painter, 111, 129, opening, look, happy=happy, sleeping=sleeping)
    wink = state == "wave" and math.sin(time_s * 4) > 0.45
    _draw_eye(painter, 189, 129, 0 if wink else opening, look, happy=happy, sleeping=sleeping)
    if sleeping:
        painter.setPen(_pen(_COCOA, 1.5))
        painter.setBrush(QColor("#c98079"))
        painter.drawEllipse(QRectF(146.5, 174, 7, 6))
    elif state == "drag":
        painter.setPen(Qt.PenStyle.NoPen)
        painter.setBrush(_COCOA)
        painter.drawEllipse(QRectF(146, 171, 8, 10))
    else:
        if happy:
            painter.setPen(Qt.PenStyle.NoPen)
            painter.setBrush(_COCOA)
            painter.drawPath(_path([
                ("M", (139, 169)), ("Q", (150, 174, 161, 169)),
                ("Q", (159, 185, 150, 186)), ("Q", (141, 185, 139, 169)),
                ("Z", ()),
            ]))
            painter.setBrush(QColor("#ed9b9b"))
            painter.drawEllipse(QRectF(145, 179, 11, 6))
        else:
            painter.setPen(_pen(_COCOA, 2))
            painter.setBrush(Qt.BrushStyle.NoBrush)
            painter.drawPath(_path([
                ("M", (138, 169)), ("Q", (143, 177, 150, 170)),
                ("Q", (157, 177, 162, 169)),
            ]))
    painter.setPen(_pen(_COCOA, 1.8))
    painter.drawLine(QPointF(150, 159), QPointF(150, 168))
    painter.setPen(Qt.PenStyle.NoPen)
    painter.setBrush(_COCOA)
    painter.drawPath(_path([
        ("M", (143, 154)), ("Q", (150, 150, 157, 154)),
        ("Q", (156, 159, 150, 161)), ("Q", (144, 159, 143, 154)),
        ("Z", ()),
    ]))
    painter.setBrush(QColor(255, 239, 220, 190))
    painter.drawEllipse(QRectF(146, 153, 4, 2))
    painter.restore()


def _heart(painter: QPainter, x: float, y: float, size: float, opacity: float) -> None:
    painter.save()
    painter.setOpacity(opacity)
    painter.translate(x, y)
    painter.scale(size / 20, size / 20)
    painter.setPen(_pen(QColor("#d97588"), 1.2))
    painter.setBrush(_gradient(0, -10, 0, 10, "#ffb5c3", "#ee849b"))
    painter.drawPath(_path([
        ("M", (0, 10)), ("C", (-20, -3, -9, -15, 0, -6)),
        ("C", (9, -15, 20, -3, 0, 10)), ("Z", ()),
    ]))
    painter.setPen(_pen(QColor(255, 244, 240, 190), 1.8))
    painter.drawPath(_path([("M", (-6, -6)), ("Q", (-10, -5, -8, -1))]))
    painter.restore()


def _draw_notes(painter: QPainter, time_s: float) -> None:
    for index, (x, y, color) in enumerate(((57, 172, "#b596d9"), (245, 122, "#89b9c7"))):
        painter.save()
        painter.translate(x + math.sin(time_s * 2 + index) * 3, y + math.sin(time_s * 3 + index) * 5)
        painter.rotate(-12 if index == 0 else 10)
        painter.setPen(_pen(QColor(color), 3))
        painter.drawLine(QPointF(3, 1), QPointF(3, -18))
        painter.drawLine(QPointF(3, -18), QPointF(12, -20))
        painter.setPen(Qt.PenStyle.NoPen)
        painter.setBrush(QColor(color))
        painter.drawEllipse(QRectF(-6, -3, 10, 7))
        painter.restore()


def _draw_cookie(painter: QPainter, time_s: float) -> None:
    painter.save()
    painter.translate(150, 236 + math.sin(time_s * 6) * 1.5)
    painter.rotate(math.sin(time_s * 3) * 6)
    painter.setPen(_pen(QColor("#a36b41"), 2))
    painter.setBrush(_gradient(-9, -17, 10, 16, "#f7cf8d", "#ddac68"))
    cookie = QPainterPath()
    cookie.addEllipse(QRectF(-20, -20, 40, 40))
    bite = QPainterPath()
    for bx, by, radius in ((14, -18, 7), (20, -11, 6), (21, -2, 5)):
        bite.addEllipse(QRectF(bx - radius, by - radius, radius * 2, radius * 2))
    painter.drawPath(cookie.subtracted(bite))
    painter.setPen(Qt.PenStyle.NoPen)
    painter.setBrush(QColor("#9a654b"))
    for x, y, radius in ((-9, -9, 2.7), (3, -13, 2), (-11, 5, 2.5), (3, 1, 2.8), (8, 11, 2.2), (-3, 12, 1.8)):
        painter.drawEllipse(QRectF(x - radius, y - radius, radius * 2, radius * 2))
    painter.setBrush(_CREAM)
    painter.setPen(_pen(_OUTLINE, 1.7))
    painter.drawEllipse(QRectF(-29, -5, 15, 19))
    painter.drawEllipse(QRectF(14, -5, 15, 19))
    painter.restore()
    painter.setPen(Qt.PenStyle.NoPen)
    painter.setBrush(QColor("#d9a167"))
    for index in range(3):
        phase = (time_s * 1.8 + index * 0.32) % 1
        painter.save()
        painter.setOpacity(1 - phase)
        painter.drawEllipse(QRectF(158 + index * 7, 232 + phase * 29, 2.5, 2.5))
        painter.restore()


def _draw_peek_paws(painter: QPainter, reveal: float, time_s: float) -> None:
    painter.save()
    painter.setOpacity(_clamp((1 - reveal) * 1.8))
    for index, x in enumerate((105, 195)):
        y = 315 + math.sin(time_s * 2 + index * 0.7) * 0.7
        painter.setPen(_pen(_OUTLINE, 2))
        painter.setBrush(_gradient(x, y - 12, x, y + 9, "#ffa47a", "#e77258"))
        painter.drawEllipse(QRectF(x - 14, y - 12, 28, 25))
        painter.setPen(_pen(QColor("#c86652"), 1.4))
        painter.drawLine(QPointF(x - 4, y - 5), QPointF(x - 4, y))
        painter.drawLine(QPointF(x + 4, y - 5), QPointF(x + 4, y))
    painter.restore()


def _draw_message(painter: QPainter, message: str, reveal: float) -> None:
    if not message:
        return
    painter.save()
    font = QFont()
    font.setPointSizeF(10)
    font.setWeight(QFont.Weight.Medium)
    painter.setFont(font)
    metrics = painter.fontMetrics()
    available = 260.0
    text_width = metrics.horizontalAdvance(message)
    bubble_width = min(available + 20, max(104.0, text_width + 30.0))
    lines = max(1, math.ceil(text_width / (bubble_width - 24)))
    bubble_height = min(70.0, 14 + metrics.height() * min(lines, 3))
    x = (SCENE_WIDTH - bubble_width) / 2
    y = 7 if reveal > 0.45 else 98
    painter.setPen(_pen(QColor(162, 117, 100, 150), 1.3))
    painter.setBrush(QColor(255, 248, 237, 246))
    painter.drawRoundedRect(QRectF(x, y, bubble_width, bubble_height), 13, 13)
    painter.setPen(Qt.PenStyle.NoPen)
    painter.drawPath(_path([
        ("M", (163, y + bubble_height - 1)),
        ("L", (158, y + bubble_height + 7)),
        ("L", (150, y + bubble_height - 1)), ("Z", ()),
    ]))
    painter.setPen(QColor("#77554c"))
    painter.drawText(
        QRectF(x + 12, y + 6, bubble_width - 24, bubble_height - 12),
        Qt.AlignmentFlag.AlignCenter | Qt.TextFlag.TextWordWrap,
        message,
    )
    painter.restore()


def draw_scene(
    painter: QPainter,
    width: float,
    height: float,
    state: str,
    time_s: float,
    progress: float = 0.0,
    reveal: float = 1.0,
    look: tuple[float, float] = (0, 0),
    message: str = "",
    paused: bool = False,
) -> None:
    """Paint the fox onto a transparent surface, fitting a 300 × 320 scene.

    ``time_s`` is monotonic animation time; ``progress`` is an action's 0–1
    progress; ``reveal`` controls how far the fox emerges from the screen edge.
    Pausing draws a calm resting pose without requiring the host timer to run.
    """
    if width <= 0 or height <= 0:
        return
    reveal, progress = _clamp(reveal), _clamp(progress)
    time_s = max(0.0, time_s)
    painter.save()
    painter.setRenderHint(QPainter.RenderHint.Antialiasing, True)
    painter.setRenderHint(QPainter.RenderHint.TextAntialiasing, True)
    scale = min(width / SCENE_WIDTH, height / SCENE_HEIGHT)
    painter.translate((width - SCENE_WIDTH * scale) / 2, (height - SCENE_HEIGHT * scale) / 2)
    painter.scale(scale, scale)
    painter.setClipRect(QRectF(0, 0, SCENE_WIDTH, SCENE_HEIGHT), Qt.ClipOperation.IntersectClip)
    active_state = "sleep" if paused else state
    motion_time = 0.0 if paused else time_s
    breathe = math.sin(motion_time * (1.4 if active_state == "sleep" else 2.2))
    body_scale_x = 1 + breathe * 0.007
    body_scale_y = 1 - breathe * 0.007
    bounce, shift_x, angle = 0.0, 0.0, 0.0
    head_tilt = math.sin(motion_time * 1.15) * 2.2
    ear_motion = math.sin(motion_time * 1.8 + 0.5) * 2.4
    tail_angle = math.sin(motion_time * 1.9) * 5
    arm_angle = math.sin(motion_time * 2.2) * 2
    if active_state == "peek":
        head_tilt = math.sin(motion_time * 1.1) * 4
    elif active_state in ("emerge", "hide"):
        head_tilt = math.sin(progress * math.pi) * (-7 if active_state == "hide" else 5)
        bounce = -math.sin(progress * math.pi) * 3
        ear_motion += math.sin(progress * math.pi * 2) * 4
    elif active_state == "happy":
        bounce = -abs(math.sin(motion_time * 5)) * 7
        body_scale_x += abs(math.sin(motion_time * 5)) * 0.018
        head_tilt = math.sin(motion_time * 4) * 5
        tail_angle = math.sin(motion_time * 9) * 13
        ear_motion = math.sin(motion_time * 7) * 4
    elif active_state == "feed":
        head_tilt = math.sin(motion_time * 6) * 2
        tail_angle = math.sin(motion_time * 5) * 7
    elif active_state == "dance":
        bounce = -abs(math.sin(motion_time * 6.5)) * 10
        shift_x = math.sin(motion_time * 6.5) * 7
        angle = math.sin(motion_time * 6.5) * 5
        head_tilt = math.sin(motion_time * 6.5 + 0.3) * 7
        tail_angle = math.sin(motion_time * 6.5 + 1) * 12
        ear_motion = math.sin(motion_time * 6.5) * 4
        body_scale_x += abs(math.sin(motion_time * 6.5)) * 0.015
    elif active_state == "sleep":
        head_tilt = -8
        ear_motion = -4 + breathe * 0.5
        tail_angle = -4 + breathe
        body_scale_x = 1.04 + breathe * 0.006
        body_scale_y = 0.98 - breathe * 0.006
    elif active_state == "drag":
        angle = math.sin(motion_time * 5) * 4
        head_tilt = -angle * 0.6
        tail_angle = -12 + math.sin(motion_time * 4) * 6
        body_scale_x, body_scale_y = 0.97, 1.02
    elif active_state == "wave":
        head_tilt = -5 + math.sin(motion_time * 3) * 2
        tail_angle = math.sin(motion_time * 6) * 9

    if reveal > 0.5:
        painter.setPen(Qt.PenStyle.NoPen)
        shadow = QRadialGradient(157, 287, 79)
        shadow.setColorAt(0, QColor(96, 56, 58, int(31 * reveal)))
        shadow.setColorAt(1, QColor(96, 56, 58, 0))
        painter.setBrush(shadow)
        painter.drawEllipse(QRectF(80, 276, 156, 21))
    painter.save()
    painter.translate(150 + shift_x, 282 + PEEK_OFFSET * (1 - reveal) + bounce)
    painter.rotate(angle)
    painter.scale(body_scale_x, body_scale_y)
    painter.translate(-150, -282)
    _draw_tail(painter, tail_angle)
    leg_offset = 5 if active_state == "drag" else 0
    _draw_foot(painter, 122, 279 + leg_offset, -12 if active_state == "dance" and math.sin(motion_time * 6.5) > 0 else -3)
    _draw_foot(painter, 178, 279 + leg_offset, 12 if active_state == "dance" and math.sin(motion_time * 6.5) < 0 else 3)
    painter.setPen(_pen(_OUTLINE, 2.5))
    painter.setBrush(_gradient(128, 180, 173, 282, "#f18b63", "#e07153", "#d5634f"))
    painter.drawPath(_body_path())
    painter.setPen(Qt.PenStyle.NoPen)
    painter.setBrush(_gradient(143, 214, 159, 278, "#fff3de", "#ffdfb9"))
    painter.drawPath(_path([
        ("M", (150, 210)), ("C", (126, 215, 119, 241, 124, 260)),
        ("C", (128, 278, 172, 278, 176, 260)),
        ("C", (181, 241, 174, 215, 150, 210)), ("Z", ()),
    ]))
    if active_state == "dance":
        _draw_arm(painter, False, -15 + math.sin(motion_time * 6.5) * 16, raised=True)
        _draw_arm(painter, True, -15 - math.sin(motion_time * 6.5) * 16, raised=True)
    elif active_state == "wave":
        _draw_arm(painter, False, arm_angle)
        _draw_arm(painter, True, -17 + math.sin(motion_time * 9) * 14, raised=True)
    elif active_state == "happy":
        _draw_arm(painter, False, -9, raised=True)
        _draw_arm(painter, True, -9, raised=True)
    else:
        _draw_arm(painter, False, -17 if active_state == "feed" else arm_angle)
        _draw_arm(painter, True, -17 if active_state == "feed" else -arm_angle)
    _draw_scarf(painter, math.sin(motion_time * 2.2) * 3)
    _draw_face(painter, active_state, motion_time, look, head_tilt, ear_motion, paused)
    if active_state == "feed":
        _draw_cookie(painter, motion_time)
    if active_state == "happy":
        for index, (x, y, size) in enumerate(((57, 107, 17), (247, 74, 21), (248, 144, 13))):
            phase = (motion_time * 0.55 + index * 0.3) % 1
            opacity = math.sin(phase * math.pi) * 0.85
            _heart(painter, x + math.sin(motion_time * 2 + index) * 4, y - phase * 23, size, opacity)
    elif active_state == "dance":
        _draw_notes(painter, motion_time)
    elif active_state == "sleep":
        painter.setPen(QColor("#a497c1"))
        for index in range(3):
            phase = (motion_time * 0.22 + index * 0.32) % 1
            painter.save()
            painter.setOpacity(0.35 + math.sin(phase * math.pi) * 0.6)
            font = QFont()
            font.setPointSizeF(9 + index * 3)
            font.setWeight(QFont.Weight.DemiBold)
            painter.setFont(font)
            painter.drawText(QPointF(224 + index * 12, 102 - index * 17 - phase * 8), "z")
            painter.restore()
    painter.restore()
    if reveal < 0.96:
        _draw_peek_paws(painter, reveal, motion_time)
    _draw_message(painter, message, reveal)
    painter.restore()


def render_icon(size: int = 64) -> QIcon:
    """Return a crisp, transparent fox-face tray icon (requires a QApplication)."""
    size = max(16, int(size))
    pixmap = QPixmap(size, size)
    pixmap.fill(Qt.GlobalColor.transparent)
    painter = QPainter(pixmap)
    painter.scale(size / 188, size / 188)
    painter.translate(-56, -25)
    draw_scene(painter, SCENE_WIDTH, SCENE_HEIGHT, "idle", 0.0)
    painter.end()
    return QIcon(pixmap)
