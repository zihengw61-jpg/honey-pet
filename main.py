"""Run 桃桃, an offline Python desktop fox."""

import argparse
import getpass
import hashlib
import logging
import os
from pathlib import Path
import sys
import tempfile


def configure_logging():
    folder = Path(os.environ.get("LOCALAPPDATA") or tempfile.gettempdir()) / "HoneyPet"
    folder.mkdir(parents=True, exist_ok=True)
    logging.basicConfig(filename=folder / "pet.log", level=logging.WARNING,
                        encoding="utf-8", format="%(asctime)s %(levelname)s %(message)s")
    def report(exception_type, value, traceback):
        logging.error("Unhandled error", exc_info=(exception_type, value, traceback))
        if sys.stderr:
            sys.__excepthook__(exception_type, value, traceback)
    sys.excepthook = report


def main(argv=None):
    from foxpet import __version__
    parser = argparse.ArgumentParser(description="桃桃 · 桌面小狐狸")
    parser.add_argument("--version", action="version", version=f"HoneyPet {__version__}")
    parser.add_argument("--smoke-test", action="store_true", help="Exit after a brief GUI startup check")
    args = parser.parse_args(argv)
    configure_logging()
    from PySide6.QtCore import QTimer
    from PySide6.QtNetwork import QLocalServer, QLocalSocket
    from PySide6.QtWidgets import QApplication
    from foxpet.app import PetWindow

    app = QApplication(sys.argv[:1])
    app.setApplicationName("HoneyPet")
    app.setQuitOnLastWindowClosed(False)
    identity = hashlib.sha256(getpass.getuser().encode()).hexdigest()[:16]
    server_name = "honey-pet-" + identity
    server = QLocalServer(app)
    if not args.smoke_test:
        socket = QLocalSocket()
        socket.connectToServer(server_name)
        if socket.waitForConnected(300):
            socket.write(b"show")
            socket.waitForBytesWritten(300)
            socket.disconnectFromServer()
            return 0
        if not server.listen(server_name):
            QLocalServer.removeServer(server_name)
            if not server.listen(server_name):
                logging.warning("Single instance socket unavailable: %s", server.errorString())
    pet = PetWindow()
    pet.show()
    pending_sockets = []
    def summon_existing():
        client = server.nextPendingConnection()
        if client:
            pending_sockets.append(client)
            pet.summon()
            client.disconnectFromServer()
            client.deleteLater()
            pending_sockets.remove(client)
    server.newConnection.connect(summon_existing)
    if args.smoke_test:
        QTimer.singleShot(100, pet.summon)
        QTimer.singleShot(900, lambda: pet.react("happy"))
        QTimer.singleShot(1600, pet.quit_pet)
    return app.exec()


if __name__ == "__main__":
    raise SystemExit(main())
