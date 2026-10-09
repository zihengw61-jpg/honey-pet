"""Async, bounded delivery of the pet's one-message WeCom notification."""

import json
import math
from pathlib import Path
import time
from urllib.parse import parse_qsl, urlsplit

from PySide6.QtCore import QObject, QTimer, QUrl, Signal
from PySide6.QtNetwork import QNetworkAccessManager, QNetworkReply, QNetworkRequest


def validate_webhook(url):
    """Accept only a WeCom robot endpoint, with one nonempty key.

    Never use a stored address for arbitrary HTTP requests. The credential is
    deliberately absent from the module and from all user-facing errors.
    """
    if not isinstance(url, str) or not url.strip():
        return False
    url = url.strip()
    if any(ord(char) < 32 or ord(char) == 127 for char in url):
        return False
    try:
        parts = urlsplit(url)
        if (parts.scheme != "https" or
                parts.netloc.lower() != "qyapi.weixin.qq.com" or
                parts.path != "/cgi-bin/webhook/send" or parts.fragment):
            return False
        query = parse_qsl(parts.query, keep_blank_values=True, strict_parsing=True)
    except (ValueError, UnicodeError):
        return False
    if len(query) != 1 or query[0][0] != "key":
        return False
    key = query[0][1]
    return (bool(key) and len(key) <= 256 and
            not any(char.isspace() or ord(char) < 32 or ord(char) == 127 for char in key))


def build_payload():
    """Encode exactly the short text the user requested."""
    return json.dumps({"msgtype": "text", "text": {"content": "呼叫"}},
                      ensure_ascii=False, separators=(",", ":")).encode("utf-8")


def read_url(settings, config_path=None):
    """Read the user's saved address, then an optional private bundle config.

    An invalid saved address is returned as empty rather than unexpectedly
    falling back to a different robot. Missing/malformed config is harmless.
    """
    saved = settings.value("wecom_webhook", "") if settings is not None else ""
    if isinstance(saved, str) and saved.strip():
        return saved.strip() if validate_webhook(saved) else ""
    if config_path is None:
        return ""
    try:
        content = Path(config_path).read_bytes()
        if len(content) > 65536:
            return ""
        config = json.loads(content.decode("utf-8-sig"))
    except (OSError, ValueError, UnicodeError, TypeError):
        return ""
    url = config.get("wecom_webhook", "") if isinstance(config, dict) else ""
    return url.strip() if validate_webhook(url) else ""


class WeComNotifier(QObject):
    """Use Qt's network event loop so the pet continues moving while sending.

    ``start`` returns False and sets ``last_error`` when nothing was queued.
    Only a queued request emits ``completed``. A successful request starts a
    short cooldown; a failed request can be tried again immediately. Requests
    never follow redirects or retry automatically, preventing credential leaks
    and duplicate messages. A transport/clock can be supplied by offline tests.
    """

    completed = Signal(bool, str)
    busy_changed = Signal(bool)

    def __init__(self, parent=None, *, manager=None, timeout_ms=10000,
                 cooldown_s=25.0, clock=None):
        super().__init__(parent)
        self._manager = manager if manager is not None else QNetworkAccessManager(self)
        self._clock = clock or time.monotonic
        self._timeout_ms = max(1, int(timeout_ms))
        self._cooldown_s = max(0.0, float(cooldown_s))
        self._success_at = None
        self._reply = None
        self.last_error = ""
        self._timer = QTimer(self)
        self._timer.setSingleShot(True)
        self._timer.timeout.connect(self._on_timeout)

    @property
    def busy(self):
        return self._reply is not None

    @property
    def cooldown_remaining(self):
        if self._success_at is None:
            return 0
        return math.ceil(max(0.0, self._cooldown_s - (self._clock() - self._success_at)))

    def start(self, url):
        if self.busy:
            self.last_error = "正在呼叫中，等一下呀"
            return False
        remaining = self.cooldown_remaining
        if remaining:
            self.last_error = f"刚刚呼叫过啦，{remaining} 秒后再试"
            return False
        if not validate_webhook(url):
            self.last_error = "请先设置企业微信通知地址"
            return False

        request = QNetworkRequest(QUrl(url.strip()))
        request.setHeader(QNetworkRequest.KnownHeaders.ContentTypeHeader,
                          "application/json; charset=utf-8")
        request.setAttribute(QNetworkRequest.Attribute.RedirectPolicyAttribute,
                             QNetworkRequest.RedirectPolicy.ManualRedirectPolicy)
        request.setTransferTimeout(self._timeout_ms)
        try:
            reply = self._manager.post(request, build_payload())
        except Exception:
            # Transport exception strings may include the credential-bearing URL.
            self.last_error = "暂时无法发送，请稍后再试"
            return False
        if reply is None:
            self.last_error = "暂时无法发送，请稍后再试"
            return False
        self.last_error = ""
        self._reply = reply
        reply.finished.connect(lambda: self._on_finished(reply))
        self._timer.start(self._timeout_ms)
        self.busy_changed.emit(True)
        if reply.isFinished():
            self._on_finished(reply)
        return True

    def _on_timeout(self):
        reply = self._reply
        if reply is not None:
            self._complete(reply, False, "呼叫超时了，请稍后再试", abort=True)

    def cancel(self):
        """Abort a pending request when the user exits, without a success result."""
        reply = self._reply
        if reply is not None:
            self._complete(reply, False, "呼叫已取消", abort=True)

    def _on_finished(self, reply):
        if reply is not self._reply:
            return
        if reply.error() != QNetworkReply.NetworkError.NoError:
            message = ("呼叫超时了，请稍后再试"
                       if reply.error() == QNetworkReply.NetworkError.TimeoutError
                       else "发送失败了，检查网络后再试呀")
            self._complete(reply, False, message)
            return
        status = reply.attribute(QNetworkRequest.Attribute.HttpStatusCodeAttribute)
        if not isinstance(status, int) or not 200 <= status < 300:
            self._complete(reply, False, "企业微信连接失败，请稍后再试")
            return
        try:
            data = bytes(reply.readAll())
            if len(data) > 65536:
                raise ValueError("oversized reply")
            result = json.loads(data.decode("utf-8"))
            if not isinstance(result, dict) or type(result.get("errcode")) is not int:
                raise ValueError("invalid reply")
        except (ValueError, UnicodeError, TypeError):
            self._complete(reply, False, "企业微信回复异常，请稍后再试")
            return
        code = result["errcode"]
        if code == 0:
            self._complete(reply, True, "已经呼叫老公啦 ♡")
        elif code == 45009:
            self._complete(reply, False, "呼叫太频繁了，请稍后再试")
        else:
            self._complete(reply, False, "企业微信没有收到消息，请检查通知设置")

    def _complete(self, reply, success, message, *, abort=False):
        if reply is not self._reply:
            return
        # Clear first: abort() can emit finished synchronously. Late signals from
        # an old request must not complete or cancel a newer request.
        self._reply = None
        self._timer.stop()
        self.last_error = "" if success else message
        if success:
            self._success_at = self._clock()
        if abort:
            reply.abort()
        reply.deleteLater()
        self.busy_changed.emit(False)
        self.completed.emit(success, message)
