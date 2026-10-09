"""Notification checks use a fake Qt transport and never contact a webhook."""

import json
import os

os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")

import pytest
from PySide6.QtCore import QByteArray, QObject, QSettings, Signal
from PySide6.QtNetwork import QNetworkReply, QNetworkRequest
from PySide6.QtTest import QTest
from PySide6.QtWidgets import QApplication

from foxpet.notifications import WeComNotifier, build_payload, read_url, validate_webhook


WEBHOOK = "https://qyapi.weixin.qq.com/cgi-bin/webhook/send?key=offline-test-key"


@pytest.fixture(scope="module")
def application():
    return QApplication.instance() or QApplication([])


class FakeReply(QObject):
    finished = Signal()

    def __init__(self, *, data=b'{"errcode":0,"errmsg":"ok"}', status=200,
                 error=QNetworkReply.NetworkError.NoError):
        super().__init__()
        self.data = data
        self.status = status
        self.network_error = error
        self.aborted = False
        self.deleted = False
        self.done = False

    def attribute(self, attr):
        assert attr == QNetworkRequest.Attribute.HttpStatusCodeAttribute
        return self.status

    def error(self):
        return self.network_error

    def readAll(self):
        return QByteArray(self.data)

    def isFinished(self):
        return self.done

    def finish(self):
        self.done = True
        self.finished.emit()

    def abort(self):
        self.aborted = True
        self.network_error = QNetworkReply.NetworkError.OperationCanceledError
        self.finish()

    def deleteLater(self):
        self.deleted = True


class FakeManager:
    def __init__(self, reply=None):
        self.reply = reply or FakeReply()
        self.requests = []

    def post(self, request, payload):
        self.requests.append((request, bytes(payload)))
        return self.reply


def make_notifier(application, *, reply=None, timeout_ms=10000, clock=None):
    manager = FakeManager(reply)
    notifier = WeComNotifier(manager=manager, timeout_ms=timeout_ms, clock=clock)
    results = []
    states = []
    notifier.completed.connect(lambda success, message: results.append((success, message)))
    notifier.busy_changed.connect(states.append)
    return notifier, manager, results, states


def test_payload_is_exact_requested_utf8_text():
    payload = build_payload()
    assert "呼叫".encode("utf-8") in payload
    assert json.loads(payload) == {"msgtype": "text", "text": {"content": "呼叫"}}


@pytest.mark.parametrize("url", [WEBHOOK, WEBHOOK.replace("qyapi", "QYAPI"),
                                  "  " + WEBHOOK + "  "])
def test_accepts_only_wecom_robot_endpoint(url):
    assert validate_webhook(url)


@pytest.mark.parametrize("url", [
    "", None, 123, WEBHOOK.replace("https:", "http:"),
    WEBHOOK.replace("qyapi.weixin.qq.com", "example.com"),
    WEBHOOK.replace("qyapi.weixin.qq.com", "qyapi.weixin.qq.com.evil.test"),
    WEBHOOK.replace("qyapi.weixin.qq.com", "qyapi.weixin.qq.com:443"),
    WEBHOOK.replace("qyapi.weixin.qq.com", "user:secret@qyapi.weixin.qq.com"),
    WEBHOOK.replace("/send?", "/other?"), WEBHOOK + "#fragment",
    WEBHOOK + "&key=another", WEBHOOK + "&other=another",
    WEBHOOK.replace("offline-test-key", ""),
    WEBHOOK.replace("offline-test-key", "%20"),
    WEBHOOK.replace("offline-test-key", "%0Asecret"),
    WEBHOOK + "\nattacker", WEBHOOK.replace("?key=", "?key"),
])
def test_rejects_unexpected_addresses(url):
    assert not validate_webhook(url)


def test_private_config_and_saved_settings_precedence(tmp_path):
    config = tmp_path / "notification_config.json"
    config.write_text(json.dumps({"wecom_webhook": WEBHOOK}), encoding="utf-8")
    settings = QSettings(str(tmp_path / "pet.ini"), QSettings.Format.IniFormat)
    assert read_url(settings, config) == WEBHOOK
    personal = WEBHOOK.replace("offline-test-key", "second-offline-key")
    settings.setValue("wecom_webhook", personal)
    assert read_url(settings, config) == personal
    settings.setValue("wecom_webhook", "https://unexpected.test")
    assert read_url(settings, config) == ""


@pytest.mark.parametrize("content", [b"not-json", b"[]", b"null", b"\xff",
                                      b'{"wecom_webhook":123}', b"x" * 65537])
def test_bad_private_config_is_harmless(tmp_path, content):
    config = tmp_path / "notification_config.json"
    config.write_bytes(content)
    assert read_url(None, config) == ""


def test_missing_config_is_harmless(tmp_path):
    assert read_url(None, tmp_path / "missing.json") == ""
    assert read_url(None) == ""


def test_queued_request_stays_async_and_disables_duplicates(application):
    notifier, manager, results, states = make_notifier(application)
    assert notifier.start(WEBHOOK)
    assert notifier.busy
    assert not results
    assert states == [True]
    assert not notifier.start(WEBHOOK)
    assert "正在呼叫" in notifier.last_error
    assert len(manager.requests) == 1
    assert results == []
    manager.reply.finish()
    assert not notifier.busy
    assert results == [(True, "已经呼叫老公啦 ♡")]
    assert states == [True, False]
    assert manager.reply.deleted


def test_post_has_utf8_header_manual_redirects_and_timeout(application):
    notifier, manager, _, _ = make_notifier(application)
    assert notifier.start(WEBHOOK)
    request, payload = manager.requests[0]
    assert request.url().toString() == WEBHOOK
    assert request.header(QNetworkRequest.KnownHeaders.ContentTypeHeader) == (
        "application/json; charset=utf-8")
    assert request.attribute(QNetworkRequest.Attribute.RedirectPolicyAttribute) == (
        QNetworkRequest.RedirectPolicy.ManualRedirectPolicy)
    assert request.transferTimeout() == 10000
    assert payload == build_payload()
    manager.reply.finish()


def test_success_cooldown_prevents_repeated_calls(application):
    now = [100.0]
    notifier, manager, results, _ = make_notifier(application, clock=lambda: now[0])
    assert notifier.start(WEBHOOK)
    manager.reply.finish()
    assert notifier.cooldown_remaining == 25
    assert not notifier.start(WEBHOOK)
    assert "25 秒" in notifier.last_error
    assert len(manager.requests) == 1
    assert len(results) == 1
    now[0] += 25
    manager.reply = FakeReply()
    assert notifier.start(WEBHOOK)
    manager.reply.finish()
    assert len(manager.requests) == 2


@pytest.mark.parametrize("error", [QNetworkReply.NetworkError.ConnectionRefusedError,
                                    QNetworkReply.NetworkError.SslHandshakeFailedError,
                                    QNetworkReply.NetworkError.TimeoutError])
def test_network_failure_is_friendly_and_allows_retry(application, error):
    notifier, manager, results, _ = make_notifier(application, reply=FakeReply(error=error))
    assert notifier.start(WEBHOOK)
    manager.reply.finish()
    assert len(results) == 1 and results[0][0] is False
    assert not notifier.busy
    assert notifier.cooldown_remaining == 0
    manager.reply = FakeReply()
    assert notifier.start(WEBHOOK)
    manager.reply.finish()
    assert results[-1][0] is True


@pytest.mark.parametrize("data", [b"not-json", b"[]", b"null", b"\xff",
                                  b"{}", b'{"errcode":false}',
                                  b'{"errcode":"0"}', b"x" * 65537])
def test_malformed_reply_is_not_a_success(application, data):
    notifier, manager, results, _ = make_notifier(application, reply=FakeReply(data=data))
    assert notifier.start(WEBHOOK)
    manager.reply.finish()
    assert results == [(False, "企业微信回复异常，请稍后再试")]
    assert notifier.cooldown_remaining == 0


@pytest.mark.parametrize("status", [None, 301, 302, 401, 500])
def test_http_failure_or_redirect_is_not_a_success(application, status):
    notifier, manager, results, _ = make_notifier(application, reply=FakeReply(status=status))
    assert notifier.start(WEBHOOK)
    manager.reply.finish()
    assert results == [(False, "企业微信连接失败，请稍后再试")]
    assert len(manager.requests) == 1


@pytest.mark.parametrize("code", [45009, 40058, 93000])
def test_api_failure_never_echoes_raw_error_or_secret(application, code):
    data = json.dumps({"errcode": code, "errmsg": WEBHOOK}).encode()
    notifier, manager, results, _ = make_notifier(application, reply=FakeReply(data=data))
    assert notifier.start(WEBHOOK)
    manager.reply.finish()
    assert results[0][0] is False
    assert "offline-test-key" not in results[0][1]
    assert "https://" not in results[0][1]
    assert notifier.cooldown_remaining == 0


def test_timeout_aborts_once_and_late_reply_cannot_cancel_retry(application):
    old_reply = FakeReply()
    notifier, manager, results, states = make_notifier(
        application, reply=old_reply, timeout_ms=20)
    assert notifier.start(WEBHOOK)
    QTest.qWait(60)
    assert old_reply.aborted and old_reply.deleted
    assert not notifier.busy
    assert results == [(False, "呼叫超时了，请稍后再试")]
    assert states == [True, False]
    assert len(manager.requests) == 1  # No automatic retry.

    manager.reply = FakeReply()
    assert notifier.start(WEBHOOK)
    old_reply.finished.emit()
    assert notifier.busy
    assert len(results) == 1
    manager.reply.finish()
    assert results[-1][0] is True
    assert len(results) == 2


def test_invalid_url_does_not_queue_or_emit_completion(application):
    notifier, manager, results, _ = make_notifier(application)
    assert not notifier.start("https://example.com?key=offline-test-key")
    assert notifier.last_error == "请先设置企业微信通知地址"
    assert not notifier.busy
    assert manager.requests == [] and results == []


def test_cancel_aborts_pending_request_without_success(application):
    notifier, manager, results, states = make_notifier(application)
    assert notifier.start(WEBHOOK)
    notifier.cancel()
    notifier.cancel()
    manager.reply.finished.emit()
    assert manager.reply.aborted and manager.reply.deleted
    assert not notifier.busy
    assert results == [(False, "呼叫已取消")]
    assert states == [True, False]
    assert notifier.cooldown_remaining == 0


def test_transport_exception_does_not_disclose_address(application):
    class BrokenManager:
        def post(self, request, payload):
            raise RuntimeError(request.url().toString())

    notifier = WeComNotifier(manager=BrokenManager())
    assert not notifier.start(WEBHOOK)
    assert not notifier.busy
    assert notifier.last_error == "暂时无法发送，请稍后再试"
