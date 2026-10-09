@echo off
chcp 65001 >nul
setlocal
cd /d "%~dp0"

if exist ".venv\Scripts\python.exe" goto check_dependencies

py -3.12 -c "import sys" >nul 2>&1
if not errorlevel 1 (
    set "PET_PYTHON=py -3.12"
    goto create_environment
)
py -3 -c "import sys; assert (3, 9) <= sys.version_info[:2] < (3, 14)" >nul 2>&1
if not errorlevel 1 (
    set "PET_PYTHON=py -3"
    goto create_environment
)
python -c "import sys; assert (3, 9) <= sys.version_info[:2] < (3, 14)" >nul 2>&1
if not errorlevel 1 (
    set "PET_PYTHON=python"
    goto create_environment
)
echo 未找到兼容的 Python。推荐直接使用免安装包中的 HoneyPet.exe。
echo 如需运行源码，请安装 Python 3.12（64 位），然后再次双击本文件。
pause
exit /b 1

:create_environment
echo 正在准备小狐狸的运行环境，首次启动需要联网……
%PET_PYTHON% -m venv .venv
if errorlevel 1 goto failed

:check_dependencies
".venv\Scripts\python.exe" -c "from PySide6 import QtCore, QtGui, QtWidgets; assert QtCore.__version__ == '6.8.3'" >nul 2>&1
if not errorlevel 1 goto ready
".venv\Scripts\python.exe" -m pip install --disable-pip-version-check -r requirements.txt
if errorlevel 1 goto failed

:ready
if /i "%~1"=="--install-only" exit /b 0
start "" "%CD%\.venv\Scripts\pythonw.exe" "%CD%\main.py" %*
exit /b 0

:failed
echo 准备失败。请检查网络连接，或改用免安装版本。
pause
exit /b 1
