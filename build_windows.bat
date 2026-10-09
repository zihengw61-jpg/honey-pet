@echo off
chcp 65001 >nul
setlocal
cd /d "%~dp0"
call start_windows.bat --install-only
if errorlevel 1 exit /b 1
".venv\Scripts\python.exe" -m pip install --disable-pip-version-check -r requirements-build.txt
if errorlevel 1 goto failed

set "PET_ICON="
if exist "assets\pet.ico" set PET_ICON=--icon "assets\pet.ico"
set "PET_ASSETS="
if exist "assets" set PET_ASSETS=--add-data "assets;assets"

".venv\Scripts\python.exe" -m PyInstaller --noconfirm --clean --windowed --onedir --name HoneyPet %PET_ICON% %PET_ASSETS% main.py
if errorlevel 1 goto failed
echo 打包完成。请将 dist\HoneyPet 整个文件夹发给对方。
echo 对方无需安装 Python，双击 HoneyPet.exe 即可运行。
pause
exit /b 0

:failed
echo 打包失败。请查看上面的错误信息。
pause
exit /b 1
