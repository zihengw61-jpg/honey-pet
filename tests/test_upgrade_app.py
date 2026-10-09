"""GUI integration for selecting dances and sending an explicit spouse call.

All notification tests use an injected QObject fake and private temporary
configuration. No real webhook, network connection, or production settings are
used, even if this checkout contains a portable notification configuration.
"""

import json
import os
from types import SimpleNamespace

os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")

import pytest
from PySide6.QtCore import QObject, QSettings, Signal
from PySide6.QtWidgets import QApplication

import foxpet.app as app_module
from foxpet.app import PetWindow
from foxpet.dances import DANCE_STYLES


FAKE_URL = (
    "https://qyapi.weixin.qq.com/cgi-bin/webhook/send?"
    "key=00000000-0000-4000-8000-000000000001"
)
OTHER_FAKE_URL = (
    "https://qyapi.weixin.qq.com/cgi-bin/webhook/send?"
    "key=00000000-0000-4000-8000-000000000002"
)


class FakeNotifier(QObject):
    completed = Signal(bool, str)
    busy_changed = Signal(bool)

    def __init__(self):
        super().__init__()
        self.busy = False
        self.last_error = ""
        self.calls = []
        self.cancel_count = 0
        self.now = 0.0
        self.cooldown_until = 0.0
        self.reject_with = ""
        self.complete_on_start = None

    @property
    def cooldown_remaining(self):
        return max(0.0, self.cooldown_until - self.now)

    def start(self, url):
        if self.busy or self.cooldown_remaining:
            self.last_error = "稍等一下再呼叫呀"
            return False
        if self.reject_with:
            self.last_error = self.reject_with
            return False
        self.calls.append(url)
        self.busy = True
        self.busy_changed.emit(True)
        if self.complete_on_start is not None:
            self.finish(*self.complete_on_start)
        return True

    def finish(self, success, message):
        self.busy = False
        if success:
            self.cooldown_until = self.now + 25.0
        self.busy_changed.emit(False)
        self.completed.emit(success, message)

    def cancel(self):
        self.cancel_count += 1
        self.busy = False


@pytest.fixture(scope="module")
def application():
    return QApplication.instance() or QApplication([])


@pytest.fixture
def make_pet(application, tmp_path):
    windows = []

    def make(*, configured=False, config_url=None, settings=None):
        settings = settings or QSettings(
            str(tmp_path / f"pet-{len(windows)}.ini"), QSettings.Format.IniFormat
        )
        if configured:
            settings.setValue("wecom_webhook", FAKE_URL)
        config_path = tmp_path / f"notification-{len(windows)}.json"
        if config_url is not None:
            config_path.write_text(
                json.dumps({"wecom_webhook": config_url}), encoding="utf-8"
            )
        notifier = FakeNotifier()
        pet = PetWindow(
            settings=settings, tray_available=False, notifier=notifier,
            notification_config=config_path,
        )
        pet.timer.stop()
        pet.call_timer.stop()
        pet.show()
        application.processEvents()
        windows.append(pet)
        return pet

    yield make
    for pet in windows:
        pet._single_click.stop()
        pet.timer.stop()
        pet.call_timer.stop()
        pet.tray.hide()
        pet._quitting = True
        pet.close()
    application.processEvents()


def menu_action(pet, text):
    return next(action for action in pet.menu.actions() if action.text() == text)


@pytest.mark.parametrize("style", list(DANCE_STYLES))
def test_dance_menu_runs_the_selected_routine(make_pet, style):
    pet = make_pet()
    # Retain QAction too: PySide's menu() transfers wrapper ownership to the
    # action, so a temporary QAction can delete its returned QMenu immediately.
    dance_action = menu_action(pet, "跳个开心舞 ♪")
    submenu = dance_action.menu()
    chosen = next(action for action in submenu.actions()
                  if action.text() == DANCE_STYLES[style])

    chosen.trigger()

    assert pet.model.presence == "emerging"
    assert pet.model.behavior == "dance"
    assert pet.model.dance_style == style
    assert DANCE_STYLES[style] in pet.model.message
    pet.model.advance(pet.model.transition_duration)
    assert pet.model.display_state == f"dance_{style}"


def test_random_dance_menu_selects_a_different_routine(make_pet):
    pet = make_pet()
    original = pet.model.dance_style
    dance_action = menu_action(pet, "跳个开心舞 ♪")
    submenu = dance_action.menu()

    submenu.actions()[0].trigger()

    assert pet.model.behavior == "dance"
    assert pet.model.dance_style in DANCE_STYLES
    assert pet.model.dance_style != original


def test_auto_dance_menu_preference_survives_reopening(make_pet):
    pet = make_pet()
    assert pet.dance_action.isChecked()
    pet.dance_action.trigger()
    assert pet.model.auto_dance is False
    pet.settings.sync()
    reopened_settings = QSettings(pet.settings.fileName(), QSettings.Format.IniFormat)
    reopened = make_pet(settings=reopened_settings)

    assert reopened.model.auto_dance is False
    assert reopened.dance_action.isChecked() is False
    reopened.dance_action.trigger()
    assert reopened.model.auto_dance is True
    assert reopened.settings.value("auto_dance", type=bool) is True


def test_call_menu_sends_the_exact_private_configured_url(make_pet):
    pet = make_pet(config_url=FAKE_URL)

    pet.call_action.trigger()

    assert pet.notifier.calls == [FAKE_URL]
    assert pet.notifier.busy is True
    assert pet.call_action.isEnabled() is False
    assert "发送中" in pet.call_action.text()
    assert pet.model.message == "正在呼叫老公…"


def test_saved_url_takes_precedence_over_portable_config(make_pet):
    pet = make_pet(configured=True, config_url=OTHER_FAKE_URL)

    pet.call_husband()

    assert pet.notifier.calls == [FAKE_URL]


def test_pending_and_cooldown_prevent_duplicate_menu_calls(make_pet):
    pet = make_pet(configured=True)
    pet.call_action.trigger()
    pet.call_action.trigger()
    assert pet.notifier.calls == [FAKE_URL]

    pet.notifier.finish(True, "已经通知老公啦 ♡")
    assert not pet.call_action.isEnabled()
    assert "25 秒" in pet.call_action.text()
    pet.call_action.trigger()
    assert pet.notifier.calls == [FAKE_URL]

    pet.notifier.now = 24.1
    pet.update_call_action()
    assert not pet.call_action.isEnabled()
    assert "1 秒" in pet.call_action.text()
    pet.notifier.now = 25.0
    pet.update_call_action()
    assert pet.call_action.isEnabled()
    assert pet.call_action.text() == "呼叫老公 ♡"
    pet.call_action.trigger()
    assert pet.notifier.calls == [FAKE_URL, FAKE_URL]


@pytest.mark.parametrize(
    ("success", "message"),
    [(True, "已经通知老公啦 ♡"), (False, "网络暂时连接不上，请稍后再试")],
)
def test_completion_shows_the_actual_result(make_pet, success, message):
    pet = make_pet(configured=True)
    pet.call_husband()

    pet.notifier.finish(success, message)

    assert pet.model.message == message
    assert pet.notifier.busy is False
    assert pet.call_action.isEnabled() is not success
    assert (pet.model.behavior == "happy") is success


def test_immediate_send_rejection_is_shown(make_pet):
    pet = make_pet(configured=True)
    pet.notifier.reject_with = "通知暂时无法启动"

    pet.call_husband()

    assert pet.notifier.calls == []
    assert pet.model.message == "通知暂时无法启动"
    assert pet.call_action.isEnabled()


def test_synchronous_completion_message_is_not_replaced_by_sending(make_pet):
    pet = make_pet(configured=True)
    message = "已经通知老公啦 ♡"
    pet.notifier.complete_on_start = True, message

    pet.call_husband()

    assert pet.notifier.calls == [FAKE_URL]
    assert pet.notifier.busy is False
    assert pet.model.message == message
    assert pet.model.behavior == "happy"
    assert "发送中" not in pet.call_action.text()
    assert not pet.call_action.isEnabled()


def test_success_keeps_pet_hidden_when_user_stashes_during_send(make_pet):
    pet = make_pet(configured=True)
    pet.call_husband()
    pet.model.stash()
    pet.hide()

    pet.notifier.finish(True, "已经通知老公啦 ♡")

    assert pet.notifier.calls == [FAKE_URL]
    assert pet.model.presence == "tray"
    assert not pet.isVisible()
    assert pet.model.behavior != "happy"


def test_first_call_cancel_does_not_send_or_save(make_pet, monkeypatch):
    pet = make_pet()
    monkeypatch.setattr(app_module.QInputDialog, "getText",
                        lambda *args, **kwargs: (FAKE_URL, False))

    pet.call_action.trigger()

    assert pet.notifier.calls == []
    assert not pet.settings.contains("wecom_webhook")
    assert pet.call_action.isEnabled()


def test_first_call_accept_saves_trimmed_url_and_sends_once(make_pet, monkeypatch):
    pet = make_pet()
    prompts = []

    def accept(*args, **kwargs):
        prompts.append((args, kwargs))
        return f"  {FAKE_URL}\n", True

    monkeypatch.setattr(app_module.QInputDialog, "getText", accept)
    pet.call_action.trigger()

    assert len(prompts) == 1
    assert pet.settings.value("wecom_webhook") == FAKE_URL
    assert pet.notifier.calls == [FAKE_URL]
    assert not pet.call_action.isEnabled()


def test_invalid_first_time_url_does_not_send_or_save(make_pet, monkeypatch):
    pet = make_pet()
    monkeypatch.setattr(app_module.QInputDialog, "getText",
                        lambda *args, **kwargs: ("https://example.com/webhook", True))

    pet.call_action.trigger()

    assert pet.notifier.calls == []
    assert not pet.settings.contains("wecom_webhook")
    assert "地址不正确" in pet.model.message


def test_configuring_url_alone_never_sends(make_pet, monkeypatch):
    pet = make_pet()
    monkeypatch.setattr(app_module.QInputDialog, "getText",
                        lambda *args, **kwargs: (FAKE_URL, True))

    menu_action(pet, "设置企业微信通知…").trigger()

    assert pet.settings.value("wecom_webhook") == FAKE_URL
    assert pet.notifier.calls == []


def test_tray_call_reveals_the_pet_and_sends_once(make_pet):
    pet = make_pet(configured=True)
    pet.model.stash()
    pet.hide()

    pet.call_action.trigger()

    assert pet.isVisible()
    assert pet.model.presence == "emerging"
    assert pet.model.message == "正在呼叫老公…"
    assert pet.notifier.calls == [FAKE_URL]


def test_exit_cancels_pending_notification_and_stops_timers(make_pet, monkeypatch):
    pet = make_pet(configured=True)
    pet.call_husband()
    pet.timer.start()
    pet.call_timer.start()
    quits = []
    monkeypatch.setattr(app_module, "QApplication", SimpleNamespace(
        instance=lambda: SimpleNamespace(quit=lambda: quits.append(True))))

    pet.quit_pet()

    assert pet._quitting is True
    assert not pet.timer.isActive()
    assert not pet.call_timer.isActive()
    assert pet.notifier.cancel_count == 1
    assert pet.notifier.busy is False
    assert quits == [True]
