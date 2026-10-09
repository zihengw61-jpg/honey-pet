"""Transparent desktop window, tray controls, and mouse interaction."""

import random
import time
import math
from pathlib import Path

from PySide6.QtCore import QSettings, Qt, QTimer
from PySide6.QtGui import QActionGroup, QBitmap, QCursor, QImage, QPainter, QRegion
from PySide6.QtWidgets import (
    QApplication, QInputDialog, QLineEdit, QMenu, QSystemTrayIcon, QWidget,
)

from .dances import DANCE_STYLES
from .model import PetModel, clamp_position
from .notifications import WeComNotifier, read_url, validate_webhook
from .renderer import draw_scene, render_icon


class PetWindow(QWidget):
    def __init__(self, settings=None, tray_available=None, notifier=None, notification_config=None):
        super().__init__(None, Qt.WindowType.FramelessWindowHint |
                         Qt.WindowType.Tool | Qt.WindowType.WindowStaysOnTopHint)
        self.setAttribute(Qt.WidgetAttribute.WA_TranslucentBackground)
        self.setAttribute(Qt.WidgetAttribute.WA_ShowWithoutActivating)
        self.setWindowTitle("桃桃 · 桌面小狐狸")
        self.setWindowIcon(render_icon())
        self.setMouseTracking(True)
        self.setCursor(Qt.CursorShape.PointingHandCursor)
        self.settings = settings or QSettings("HoneyPet", "Taotao")
        self.notification_config = (Path(notification_config) if notification_config is not None
                                    else Path(__file__).resolve().parents[1] / "notification_config.json")
        self.notifier = notifier if notifier is not None else WeComNotifier(self)
        self.notifier.completed.connect(self.on_call_completed)
        self.notifier.busy_changed.connect(self.update_call_action)
        self.nickname = str(self.settings.value("nickname", "你"))[:16]
        self.model = PetModel()
        self.model.auto_peek = self.settings.value("auto_peek", True, type=bool)
        self.model.auto_dance = self.settings.value("auto_dance", True, type=bool)
        self.model.paused = self.settings.value("paused", False, type=bool)
        self.model.say("点点我的小脑袋呀", 6.0)
        self._pressed_at = None
        self._pressed_window_at = None
        self._dragging = False
        self._frame = None
        self._last_tick = time.monotonic()
        self._last_interval = None
        self._screen = None
        self._quitting = False
        self._single_click = QTimer(self)
        self._single_click.setSingleShot(True)
        self._single_click.timeout.connect(self.on_click)
        self.tray_available = (QSystemTrayIcon.isSystemTrayAvailable()
                               if tray_available is None else tray_available)
        self.tray = QSystemTrayIcon(render_icon(), self)
        self.tray.setToolTip("桃桃 · 点一下，陪你一会儿")
        self.menu = self.build_menu()
        self.tray.setContextMenu(self.menu)
        self.tray.activated.connect(self.on_tray)
        if self.tray_available:
            self.tray.show()
        self.set_pet_size(float(self.settings.value("scale", 1.0)))
        self.watch_screens()
        QApplication.instance().screenAdded.connect(lambda _: self.watch_screens())
        QApplication.instance().screenRemoved.connect(self.on_screen_removed)
        self.timer = QTimer(self)
        self.timer.setTimerType(Qt.TimerType.PreciseTimer)
        self.timer.timeout.connect(self.tick)
        self.timer.start(33)
        self.call_timer = QTimer(self)
        self.call_timer.setInterval(500)
        self.call_timer.timeout.connect(self.update_call_action)
        self.call_timer.start()
        self.update_hit_mask()

    def build_menu(self):
        menu = QMenu()
        menu.setStyleSheet("""
            QMenu { background: #fff9f2; color: #553a37; border: 1px solid #efcfbd;
                    border-radius: 10px; padding: 7px; font-size: 13px; }
            QMenu::item { padding: 7px 24px 7px 13px; border-radius: 5px; }
            QMenu::item:selected { background: #fbe4d5; }
            QMenu::separator { height: 1px; background: #f0ded1; margin: 5px 9px; }
        """)
        def action(text, callback):
            item = menu.addAction(text)
            item.triggered.connect(callback)
            return item
        action("探出来陪我", self.summon)
        action("摸摸头 ♡", lambda: self.react("happy"))
        action("吃一块小饼干", lambda: self.react("feed"))
        self.dances_menu = menu.addMenu("跳个开心舞 ♪")
        dances = self.dances_menu
        dances.addAction("随机跳一套").triggered.connect(lambda: self.dance())
        for style, label in DANCE_STYLES.items():
            dances.addAction(label).triggered.connect(lambda checked=False, value=style: self.dance(value))
        action("睡一小会儿", lambda: self.react("sleep"))
        self.call_action = action("呼叫老公 ♡", self.call_husband)
        menu.addSeparator()
        action("缩回去，露出小脑袋", self.return_to_corner)
        hide = action("藏到右下角托盘", self.hide_to_tray)
        hide.setEnabled(self.tray_available)
        self.sizes_menu = menu.addMenu("小狐狸的大小")
        sizes = self.sizes_menu
        group = QActionGroup(self)
        for label, scale in (("小小只", 0.8), ("刚刚好", 1.0), ("大一点", 1.2)):
            item = sizes.addAction(label)
            item.setCheckable(True)
            group.addAction(item)
            item.setChecked(abs(float(self.settings.value("scale", 1.0)) - scale) < 0.05)
            item.triggered.connect(lambda checked=False, value=scale: self.set_pet_size(value))
        self.auto_action = action("闲置 45 秒后缩回", self.toggle_auto_peek)
        self.auto_action.setCheckable(True)
        self.auto_action.setChecked(self.model.auto_peek)
        self.dance_action = action("偶尔自动跳一段", self.toggle_auto_dance)
        self.dance_action.setCheckable(True)
        self.dance_action.setChecked(self.model.auto_dance)
        self.pause_action = action("暂停小动作", self.toggle_pause)
        self.pause_action.setCheckable(True)
        self.pause_action.setChecked(self.model.paused)
        action("我该怎么称呼你…", self.change_nickname)
        action("设置企业微信通知…", self.configure_wecom)
        menu.addSeparator()
        action("退出小狐狸", self.quit_pet)
        return menu

    def watch_screens(self):
        for screen in QApplication.screens():
            if not screen.property("honey_pet_watched"):
                screen.availableGeometryChanged.connect(lambda rect: self.ensure_on_screen())
                screen.setProperty("honey_pet_watched", True)
        if self._screen not in QApplication.screens():
            self._screen = QApplication.primaryScreen()
        self.ensure_on_screen()

    def on_screen_removed(self, screen):
        if screen == self._screen:
            self._screen = QApplication.primaryScreen()
            self.place_corner()

    def bounds(self):
        screen = self._screen or QApplication.primaryScreen()
        area = screen.availableGeometry()
        return (area.x(), area.y(), area.width(), area.height())

    def place_corner(self):
        self._screen = self._screen or QApplication.primaryScreen()
        left, top, width, height = self.bounds()
        x, y = clamp_position(left + width - self.width() - 12,
                              top + height - self.height(), self.width(), self.height(), self.bounds())
        self.move(int(x), int(y))

    def ensure_on_screen(self):
        if self.model.presence in ("peek", "retreating"):
            self.place_corner()
        else:
            x, y = clamp_position(self.x(), self.y(), self.width(), self.height(), self.bounds())
            self.move(int(x), int(y))

    def set_pet_size(self, scale):
        scale = max(0.8, min(1.2, scale))
        self.settings.setValue("scale", scale)
        self.resize(round(300 * scale), round(320 * scale))
        self.ensure_on_screen()
        self.update_hit_mask()
        self.update()

    def tick(self):
        now = time.monotonic()
        self.model.advance(max(0.0, now - self._last_tick))
        self._last_tick = now
        if self.model.presence == "tray":
            return
        if self.model.presence == "retreating":
            self.place_corner()
        cursor = QCursor.pos()
        relative = self.mapFromGlobal(cursor)
        self.look = (max(-1.0, min(1.0, (relative.x() / self.width() - .5) * 2)),
                     max(-1.0, min(1.0, (relative.y() / self.height() - .55) * 2)))
        interval = 100 if self.model.paused else (33 if self.model.presence == "peek" else 16)
        if interval != self._last_interval:
            self.timer.setInterval(interval)
            self._last_interval = interval
        self.update_hit_mask()
        self.update()

    def update_hit_mask(self):
        # The rendered alpha includes moving hands, outlines, and effects. Qt
        # converts it in native code, avoiding a slow Python silhouette scan.
        ratio = self.devicePixelRatioF()
        self._frame = QImage(round(self.width() * ratio), round(self.height() * ratio),
                             QImage.Format.Format_ARGB32_Premultiplied)
        self._frame.setDevicePixelRatio(ratio)
        self._frame.fill(Qt.GlobalColor.transparent)
        painter = QPainter(self._frame)
        draw_scene(painter, self.width(), self.height(), self.model.display_state,
                   self.model.time_s, self.model.progress, self.model.reveal,
                   getattr(self, "look", (0.0, 0.0)), self.model.message, self.model.paused)
        painter.end()
        mask_image = self._frame
        if ratio != 1.0:
            mask_image = self._frame.scaled(self.size())
            mask_image.setDevicePixelRatio(1.0)
        # Include faint effects and antialiased outlines, not just opaque pixels.
        # QBitmap/QRegion includes black bits: transparent pixels must be white.
        bitmap = QBitmap.fromImage(mask_image.createMaskFromColor(
            0, Qt.MaskMode.MaskInColor))
        region = QRegion(bitmap)
        if ratio > 1.0:
            # A logical pixel covers several physical pixels. Keep edge pixels
            # omitted by downsampling with one pixel of native region padding.
            expanded = QRegion(region)
            for dx in (-1, 0, 1):
                for dy in (-1, 0, 1):
                    expanded |= region.translated(dx, dy)
            region = expanded.intersected(QRegion(self.rect()))
        self.setMask(region)

    def paintEvent(self, event):
        painter = QPainter(self)
        if self._frame is not None:
            painter.drawImage(0, 0, self._frame)

    def summon(self):
        self.model.show()
        self.model.say(f"{self.nickname}，我在呀 ♡")
        self._last_tick = time.monotonic()
        self.update_hit_mask()
        self.show()
        self.raise_()
        self.update_hit_mask()
        self.update()

    def on_click(self):
        if self.model.presence in ("peek", "retreating", "tray"):
            self.summon()
        else:
            self.react("happy")

    def react(self, kind):
        if self.model.presence == "tray":
            self.show()
        self.model.react(kind)
        lines = {"happy": ("被你摸到啦 ♡", "再摸摸耳朵嘛", f"最喜欢{self.nickname}啦"),
                 "feed": ("咔嚓！好香的小饼干",), "dance": ("把开心分你一半 ♪",),
                 "sleep": ("呼噜…陪你安静一会儿",)}
        self.model.say(random.choice(lines.get(kind, ("我在呀",))))
        self._last_tick = time.monotonic()
        self.update_hit_mask()
        self.update()

    def dance(self, style=None):
        self._single_click.stop()
        if self.model.presence == "tray":
            self.show()
        self.model.start_dance(style)
        self.model.say(f"给{self.nickname}跳个{DANCE_STYLES[self.model.dance_style]} ♪")
        self._last_tick = time.monotonic()
        self.update_hit_mask()
        self.update()

    def toggle_auto_dance(self, checked):
        self.model.auto_dance = checked
        self.settings.setValue("auto_dance", checked)

    def configure_wecom(self):
        current = read_url(self.settings, self.notification_config)
        text, accepted = QInputDialog.getText(
            None, "设置企业微信通知", "粘贴企业微信机器人 webhook 地址：",
            QLineEdit.EchoMode.Password, current)
        if not accepted:
            return False
        url = text.strip()
        if not validate_webhook(url):
            self.model.say("地址不正确，请粘贴完整的企业微信机器人地址", 6.0)
            self.update_hit_mask()
            self.update()
            return False
        self.settings.setValue("wecom_webhook", url)
        self.settings.sync()
        self.model.say("记好啦，点“呼叫老公”就能通知他 ♡", 4.0)
        self.update_hit_mask()
        self.update()
        return True

    def update_call_action(self, *args):
        cooldown = math.ceil(self.notifier.cooldown_remaining)
        self.call_action.setEnabled(not self.notifier.busy and cooldown <= 0)
        label = ("呼叫老公（发送中…）" if self.notifier.busy else
                 f"呼叫老公（{cooldown} 秒后可再呼叫）" if cooldown else "呼叫老公 ♡")
        self.call_action.setText(label)

    def call_husband(self):
        self._single_click.stop()
        url = read_url(self.settings, self.notification_config)
        if not url:
            if not self.configure_wecom():
                return
            url = read_url(self.settings, self.notification_config)
        if self.model.presence == "tray":
            self.summon()
        self.model.react("wave")
        self.model.say("正在呼叫老公…", 12.0)
        if not self.notifier.start(url):
            self.model.say(self.notifier.last_error or "稍等一下再呼叫呀", 5.0)
        self.update_call_action()
        self.update_hit_mask()
        self.update()

    def on_call_completed(self, success, message):
        if self._quitting:
            return
        if success and self.model.presence != "tray":
            self.model.react("happy")
        self.model.say(message, 6.0)
        self.update_call_action()
        self.update_hit_mask()
        self.update()

    def return_to_corner(self):
        self._single_click.stop()
        self.model.peek()
        self.place_corner()
        self.show()
        self.update_hit_mask()
        self.update()

    def hide_to_tray(self):
        if not self.tray_available:
            self.return_to_corner()
            return False
        self._single_click.stop()
        self.model.stash()
        self.hide()
        return True

    def on_tray(self, reason):
        if reason in (QSystemTrayIcon.ActivationReason.Trigger,
                      QSystemTrayIcon.ActivationReason.DoubleClick):
            self.summon()

    def toggle_auto_peek(self, checked):
        self.model.auto_peek = checked
        self.model.idle_elapsed = 0.0
        self.settings.setValue("auto_peek", checked)

    def toggle_pause(self, checked):
        self.model.paused = checked
        self.settings.setValue("paused", checked)

    def change_nickname(self):
        text, accepted = QInputDialog.getText(None, "给你的小称呼", "小狐狸怎么称呼你？", text=self.nickname)
        if accepted and text.strip():
            self.nickname = text.strip()[:16]
            self.settings.setValue("nickname", self.nickname)
            self.model.say(f"记住啦，{self.nickname} ♡")

    def mousePressEvent(self, event):
        if event.button() == Qt.MouseButton.LeftButton:
            self._pressed_at = event.globalPosition().toPoint()
            self._pressed_window_at = self.pos()
            self._dragging = False
            event.accept()

    def mouseMoveEvent(self, event):
        if self._pressed_at is None or not (event.buttons() & Qt.MouseButton.LeftButton):
            return
        delta = event.globalPosition().toPoint() - self._pressed_at
        if not self._dragging and delta.manhattanLength() >= QApplication.startDragDistance():
            self._single_click.stop()
            self._dragging = True
            self.model.begin_drag()
            self.setCursor(Qt.CursorShape.ClosedHandCursor)
        if self._dragging:
            screen = QApplication.screenAt(event.globalPosition().toPoint())
            if screen:
                self._screen = screen
            wanted = self._pressed_window_at + delta
            x, y = clamp_position(wanted.x(), wanted.y(), self.width(), self.height(), self.bounds())
            self.move(int(x), int(y))
            self.update_hit_mask()
            self.update()
        event.accept()

    def mouseReleaseEvent(self, event):
        if event.button() == Qt.MouseButton.LeftButton and self._pressed_at is not None:
            was_dragging = self._dragging
            self._pressed_at = None
            self._dragging = False
            self.setCursor(Qt.CursorShape.PointingHandCursor)
            if was_dragging:
                self.model.end_drag()
            else:
                self._single_click.start(QApplication.doubleClickInterval())
            event.accept()

    def mouseDoubleClickEvent(self, event):
        if event.button() == Qt.MouseButton.LeftButton:
            self._single_click.stop()
            self._pressed_at = None
            self.react("dance")
            event.accept()

    def contextMenuEvent(self, event):
        self._single_click.stop()
        self.menu.popup(event.globalPos())

    def closeEvent(self, event):
        if self._quitting:
            event.accept()
        else:
            event.ignore()
            self.hide_to_tray()

    def quit_pet(self):
        self._quitting = True
        self.settings.sync()
        self.tray.hide()
        self.timer.stop()
        self.call_timer.stop()
        self.notifier.cancel()
        QApplication.instance().quit()
