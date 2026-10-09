"""Render deterministic showcase artifacts from the actual desktop-pet painter.

From the project root, after installing requirements and Pillow:
    python scripts/render_preview.py

The app itself never needs Pillow.  Preview rendering runs without a desktop.
"""

from __future__ import annotations

import argparse
import io
import math
import os
from pathlib import Path
import sys

os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")
ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))

from PySide6.QtCore import QBuffer, QIODevice, QPointF, QRectF, Qt
from PySide6.QtGui import QColor, QFont, QFontDatabase, QImage, QLinearGradient, QPainter, QPen
from PySide6.QtWidgets import QApplication

try:
    from PIL import Image
except ImportError as error:
    raise SystemExit("Preview export requires Pillow: python -m pip install Pillow") from error

from foxpet.renderer import draw_scene, render_icon
from foxpet.dances import DANCE_SECONDS, DANCE_STYLES


WIDTH, HEIGHT = 640, 520
FPS = 20
SEGMENTS = (
    ("peek", 0.9, "露出小脑袋", "点一下，钻出来陪你"),
    ("emerge", 0.7, "从角落钻出来", "轻轻探出，再向你挥挥手"),
    ("happy", 1.1, "摸摸头", "开心的时候，会飘起小爱心"),
    ("feed", 1.1, "吃块小饼干", "一点小零食，就是一天的小确幸"),
    ("dance_heart", 2.0, "爱心摇", "小手比心，尾巴轻轻摇"),
    ("dance_shuffle", 2.0, "左右踩点", "左一下右一下，脚步跟着心情走"),
    ("dance_swing", 2.0, "甩手扭扭", "伸伸小手，身体也跟着扭一扭"),
    ("dance_bounce", 2.0, "活力蹦蹦", "蹲一点跳一下，开心就要蹦起来"),
    ("sleep", 1.2, "睡一小会儿", "安静陪伴，也是一种温柔"),
    ("hide", 0.7, "缩回小角落", "还在这里，随时等你再点一下"),
    ("peek", 0.6, "露出小脑袋", "点一下，钻出来陪你"),
)
TOTAL_SECONDS = sum(segment[1] for segment in SEGMENTS)
DANCE_DETAILS = {
    "heart": "比个小爱心，送给最喜欢的你",
    "shuffle": "左右踩点，小脚交替踏踏踏",
    "swing": "挥挥小手，扭出今天的好心情",
    "bounce": "轻轻蓄力，开心地蹦蹦跳跳",
}
DANCE_SNAPSHOTS = {"heart": 0.36, "shuffle": 0.20, "swing": 0.22, "bounce": 0.19}


def font(size: float, bold: bool = False) -> QFont:
    result = QFont("Noto Sans CJK SC")
    result.setStyleHint(QFont.StyleHint.SansSerif)
    result.setPixelSize(round(size))
    result.setWeight(QFont.Weight.DemiBold if bold else QFont.Weight.Normal)
    return result


def text(painter: QPainter, x: float, y: float, value: str, size: float,
         color: str = "#5f4240", bold: bool = False) -> None:
    painter.setPen(QColor(color))
    painter.setFont(font(size, bold))
    painter.drawText(QPointF(x, y), value)


def rounded(painter: QPainter, box: QRectF, color: str, radius: float = 16) -> None:
    painter.setPen(Qt.PenStyle.NoPen)
    painter.setBrush(QColor(color))
    painter.drawRoundedRect(box, radius, radius)


def background(painter: QPainter, width: int, height: int) -> None:
    gradient = QLinearGradient(0, 0, width, height)
    gradient.setColorAt(0, QColor("#fff8ed"))
    gradient.setColorAt(1, QColor("#f8dfd0"))
    painter.fillRect(QRectF(0, 0, width, height), gradient)


def frame_at(time_s: float):
    elapsed = 0.0
    for state, duration, title, detail in SEGMENTS:
        if time_s < elapsed + duration:
            action_seconds = time_s - elapsed
            progress = action_seconds / duration
            smooth = progress * progress * (3 - 2 * progress)
            reveal = smooth if state == "emerge" else 1 - smooth if state == "hide" else 0 if state == "peek" else 1
            if state.startswith("dance_"):
                # The desktop demo shows excerpts at the app's real dance tempo.
                progress = action_seconds / DANCE_SECONDS
            return state, progress, reveal, title, detail
        elapsed += duration
    return "peek", 1.0, 0.0, SEGMENTS[-1][2], SEGMENTS[-1][3]


def paint_desktop(time_s: float) -> QImage:
    image = QImage(WIDTH, HEIGHT, QImage.Format.Format_ARGB32)
    painter = QPainter(image)
    painter.setRenderHint(QPainter.RenderHint.Antialiasing)
    background(painter, WIDTH, HEIGHT)

    painter.setPen(Qt.PenStyle.NoPen)
    painter.setBrush(QColor("#fff3e5"))
    painter.drawEllipse(QRectF(315, 140, 365, 365))
    text(painter, 40, 61, "桃桃", 34, bold=True)
    text(painter, 42, 96, "你的桌面小狐狸", 17, "#916c63")
    rounded(painter, QRectF(485, 31, 112, 31), "#f2d4c6", 15)
    text(painter, 504, 52, "四套舞蹈", 13, "#80544c")

    state, progress, reveal, title, detail = frame_at(time_s)
    rounded(painter, QRectF(39, 170, 188, 39), "#fffdf5", 19)
    text(painter, 56, 196, title, 16, bold=True)
    # The descriptive lines intentionally stay away from the actual pet area.
    split = detail.find("，")
    lines = [detail] if split < 0 else [detail[:split], detail[split + 1:]]
    for index, line in enumerate(lines):
        text(painter, 42, 242 + index * 24, line, 13, "#9b776a")

    # This is the app's real transparent scene on a small desktop illustration.
    painter.save()
    painter.translate(325, 166)
    draw_scene(painter, 300, 320, state, time_s, progress=progress, reveal=reveal,
               look=(math.sin(time_s * 0.7) * 0.45, 0.15))
    painter.restore()

    text(painter, 42, 430, "点击互动  ·  拖动抱走", 13, "#ad8879")
    text(painter, 42, 454, "右键菜单  ·  托盘随时唤回", 13, "#ad8879")
    rounded(painter, QRectF(0, 486, WIDTH, 34), "#eddacd", 0)
    # A generic taskbar supplies the visible edge the pet emerges from.
    for x in (18, 28):
        for y in (497, 507):
            rounded(painter, QRectF(x, y, 7, 7), "#b9907d", 1)
    rounded(painter, QRectF(51, 495, 101, 20), "#f7e8dc", 6)
    text(painter, 65, 509, "搜索", 10, "#b79686")
    for index, color in enumerate(("#d9ac94", "#e6ba99", "#cea5a3")):
        rounded(painter, QRectF(182 + index * 31, 497, 14, 14), color, 4)
    rounded(painter, QRectF(549, 496, 24, 22), "#f7e8dc", 6)
    painter.save()
    painter.translate(550, 496)
    painter.drawPixmap(0, 0, render_icon(22).pixmap(22, 22))
    painter.restore()
    text(painter, 593, 509, "♡", 13, "#b6897a")
    painter.end()
    return image


def as_pillow(image: QImage) -> Image.Image:
    buffer = QBuffer()
    buffer.open(QIODevice.OpenModeFlag.WriteOnly)
    image.save(buffer, "PNG")
    return Image.open(io.BytesIO(bytes(buffer.data()))).convert("RGB")


def make_contact_sheet(target: Path) -> None:
    width, height = 1480, 860
    image = QImage(width, height, QImage.Format.Format_ARGB32)
    painter = QPainter(image)
    painter.setRenderHint(QPainter.RenderHint.Antialiasing)
    background(painter, width, height)
    text(painter, 45, 62, "桃桃 · 桌面小狐狸", 30, bold=True)
    text(painter, 46, 97, "四套小舞蹈，和一整天软乎乎的陪伴。", 16, "#9b776a")
    items = (
        ("peek", 0.0, 0.8, "探出小脑袋", "点击就能钻出来"),
        ("happy", 1.0, 2.5, "摸摸头", "爱心、笑眼和摇尾巴"),
        ("feed", 1.0, 4.1, "吃块小饼干", "吃饱饱，心情好好"),
        ("sleep", 1.0, 8.5, "睡一小会儿", "呼吸、闭眼和轻轻的 Zzz"),
        *((f"dance_{style}", 1.0, DANCE_SNAPSHOTS[style] * DANCE_SECONDS,
           label, DANCE_DETAILS[style]) for style, label in DANCE_STYLES.items()),
    )
    for index, (state, reveal, time_s, title, detail) in enumerate(items):
        left, top = 30 + index % 4 * 360, 128 + index // 4 * 350
        rounded(painter, QRectF(left, top, 340, 330), "#fffaf1", 22)
        text(painter, left + 22, top + 35, f"0{index + 1}", 12, "#d1a68e")
        # Paws align with the card's inner desktop edge in the peek state.
        painter.save()
        painter.translate(left + 27, top + 33)
        progress = time_s / DANCE_SECONDS if state.startswith("dance_") else 0.0
        draw_scene(painter, 286, 235, state, time_s, progress=progress,
                   reveal=reveal, look=(0.2, 0.1))
        painter.restore()
        if state == "peek":
            painter.setPen(QPen(QColor("#e8cfc0"), 1.5))
            painter.drawLine(QPointF(left + 25, top + 268), QPointF(left + 315, top + 268))
        rounded(painter, QRectF(left + 10, top + 269, 320, 51), "#fffaf1", 0)
        text(painter, left + 21, top + 290, title, 17, bold=True)
        text(painter, left + 21, top + 312, detail, 12, "#a48172")
    text(painter, 47, 843, "Python / PySide6     ·     透明桌面窗口     ·     点击、拖拽、右键与托盘互动", 13, "#a58172")
    painter.end()
    if not image.save(str(target)):
        raise RuntimeError(f"Could not write {target}")


def save_animation(frames: list[Image.Image], target: Path, preview_width: int) -> None:
    # Keep chat previews small; full-size static exports retain the crisp artwork.
    width, height = frames[0].size
    if width > preview_width:
        preview_size = (preview_width, round(height * preview_width / width))
        frames = [frame.resize(preview_size, Image.Resampling.LANCZOS) for frame in frames]
    # One shared palette keeps flat vector colors stable across all frames.
    width, height = frames[0].size
    palette_sample = Image.new("RGB", (width * 4, height * 3))
    for index in range(12):
        sample = frames[min(len(frames) - 1, index * len(frames) // 12)]
        palette_sample.paste(sample, ((index % 4) * width, (index // 4) * height))
    palette = palette_sample.quantize(colors=256, method=Image.Quantize.MEDIANCUT)
    indexed = [frame.quantize(palette=palette, dither=Image.Dither.NONE) for frame in frames]
    indexed[0].save(target, save_all=True, append_images=indexed[1:],
                    duration=round(1000 / FPS), loop=0, optimize=True, disposal=1)


def make_gif(target: Path) -> None:
    frames = [as_pillow(paint_desktop(index / FPS))
              for index in range(round(TOTAL_SECONDS * FPS))]
    save_animation(frames, target, preview_width=560)


def paint_dances(time_s: float, snapshot: bool = False) -> QImage:
    """Show four actual routines together, with no private or notification UI."""
    width, height = 800, 780
    image = QImage(width, height, QImage.Format.Format_ARGB32)
    painter = QPainter(image)
    painter.setRenderHint(QPainter.RenderHint.Antialiasing)
    background(painter, width, height)
    text(painter, 40, 53, "桃桃的四套小舞蹈", 28, bold=True)
    text(painter, 42, 84, "想开心一下，就点点小狐狸。", 15, "#9b776a")
    for index, (style, label) in enumerate(DANCE_STYLES.items()):
        left, top = 40 + index % 2 * 370, 110 + index // 2 * 320
        rounded(painter, QRectF(left, top, 350, 306), "#fffaf1", 22)
        text(painter, left + 21, top + 33, f"0{index + 1}", 12, "#d1a68e")
        progress = DANCE_SNAPSHOTS[style] if snapshot else time_s / DANCE_SECONDS
        scene_time = progress * DANCE_SECONDS
        painter.save()
        painter.translate(left + 15, top + 16)
        draw_scene(painter, 320, 238, f"dance_{style}", scene_time,
                   progress=progress, reveal=1.0)
        painter.restore()
        text(painter, left + 23, top + 269, label, 18, bold=True)
        text(painter, left + 23, top + 290, DANCE_DETAILS[style], 12, "#a48172")
    text(painter, 42, 768, "右键选择喜欢的舞蹈，也会偶尔自己跳给你看。", 13, "#a58172")
    painter.end()
    return image


def make_dance_gif(target: Path) -> None:
    frames = [as_pillow(paint_dances(index / FPS))
              for index in range(round(DANCE_SECONDS * FPS))]
    save_animation(frames, target, preview_width=600)


def make_icon(target: Path) -> None:
    pixmap = render_icon(256).pixmap(256, 256)
    buffer = QBuffer()
    buffer.open(QIODevice.OpenModeFlag.WriteOnly)
    pixmap.save(buffer, "PNG")
    image = Image.open(io.BytesIO(bytes(buffer.data()))).convert("RGBA")
    image.save(target, sizes=[(size, size) for size in (16, 24, 32, 48, 64, 128, 256)])


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--output", type=Path, default=ROOT / "artifacts")
    parser.add_argument("--skip-gif", action="store_true")
    parser.add_argument("--skip-icon", action="store_true")
    args = parser.parse_args()
    app = QApplication.instance() or QApplication([])
    cjk = Path("/usr/share/fonts/opentype/noto/NotoSansCJK-Regular.ttc")
    if cjk.exists():
        QFontDatabase.addApplicationFont(str(cjk))
    app.setFont(font(13))
    args.output.mkdir(parents=True, exist_ok=True)
    (ROOT / "assets").mkdir(exist_ok=True)
    make_contact_sheet(args.output / "taotao-poses.png")
    paint_dances(0.0, snapshot=True).save(str(args.output / "taotao-dances.png"))
    paint_desktop(3.0).save(str(args.output / "taotao-desktop.png"))
    if not args.skip_icon:
        make_icon(ROOT / "assets" / "pet.ico")
    if not args.skip_gif:
        make_gif(args.output / "taotao-preview.gif")
        make_dance_gif(args.output / "taotao-dance-preview.gif")
    for output in sorted(args.output.glob("taotao-*")):
        print(f"{output}: {output.stat().st_size:,} bytes")
    if not args.skip_icon:
        print(f"{ROOT / 'assets' / 'pet.ico'}: generated")


if __name__ == "__main__":
    main()
