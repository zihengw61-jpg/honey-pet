"""Copied to app/sitecustomize.py in the offline Windows distribution.

Python's documented ._pth startup imports this module. Only the renamed GUI
interpreter starts the pet, so python.exe stays usable for diagnostics.
"""

from __future__ import annotations

import os
from pathlib import Path
import sys


def launch() -> int:
    import datetime
    import logging
    import runpy
    import tempfile
    import traceback

    app_dir = Path(__file__).resolve().parent
    root = app_dir.parent
    log_dir = Path(os.environ.get("LOCALAPPDATA") or tempfile.gettempdir()) / "HoneyPet"
    try:
        log_dir.mkdir(parents=True, exist_ok=True)
        stream = (log_dir / "launcher.log").open("a", encoding="utf-8", buffering=1)
    except OSError:
        log_dir = Path(tempfile.gettempdir()) / "HoneyPet"
        log_dir.mkdir(parents=True, exist_ok=True)
        stream = (log_dir / "launcher.log").open("a", encoding="utf-8", buffering=1)
    if sys.stdout is None:
        sys.stdout = stream
    if sys.stderr is None:
        sys.stderr = stream

    # Keep DLL directory handles alive while Qt is running.
    dll_handles = []
    result = 0
    try:
        for directory in (root, root / "DLLs", root / "Lib/site-packages/PySide6",
                          root / "Lib/site-packages/shiboken6"):
            if directory.is_dir():
                dll_handles.append(os.add_dll_directory(str(directory)))
        os.environ["QT_PLUGIN_PATH"] = str(root / "Lib/site-packages/PySide6/plugins")
        sys.argv[0] = str(app_dir / "main.py")
        runpy.run_path(str(app_dir / "main.py"), run_name="__main__")
    except SystemExit as error:
        result = error.code if isinstance(error.code, int) else (0 if error.code is None else 1)
    except BaseException:
        result = 1
        stream.write(f"\n[{datetime.datetime.now().isoformat(timespec='seconds')}] Startup failed\n")
        traceback.print_exc(file=stream)
        stream.flush()
        try:
            import ctypes
            ctypes.windll.user32.MessageBoxW(
                None,
                "小狐狸启动失败。请完整解压压缩包后重新运行。\n\n"
                f"错误记录：{log_dir / 'launcher.log'}\n"
                "也可以双击“诊断启动.bat”查看详情。",
                "HoneyPet · 小狐狸", 0x10,
            )
        except Exception:
            pass
    finally:
        logging.shutdown()
        stream.flush()
    return result


if sys.platform == "win32" and Path(sys.executable).name.lower() == "honeypet.exe":
    # Do not continue into the interpreter's stdin startup after Qt exits.
    os._exit(launch())
