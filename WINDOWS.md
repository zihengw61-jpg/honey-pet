# Windows 使用与打包

给家人使用，推荐 `HoneyPet-Windows-x64.zip`：完整解压后双击 `HoneyPet.exe`，无需安装 Python，也无需联网。整个文件夹需要放在一起，不能只复制 EXE。支持 Windows 10 / 11 的 64 位电脑。

便携包内含官方 Python 3.12.10 运行库、PySide6 Essentials 6.8.3 和应用源码。`HoneyPet.exe` 是改名后的官方 Pythonw 程序，由隔离的启动配置加载小狐狸。默认没有命令行黑窗，也不会添加普通任务栏按钮。

启动失败时，双击 `诊断启动.bat`。启动器的错误记录在 `%LOCALAPPDATA%\HoneyPet\launcher.log`。先确认已完整解压，而不是在压缩包预览窗口内启动。

当前便携包由 Linux 环境组装，已检查包哈希、ZIP 完整性与 Windows x64 二进制架构；尚未在真实 Windows 桌面验证透明窗口、托盘和多屏行为。

## 运行源码

安装 Python 3.12（64 位）后，双击 `start_windows.bat`。首次需要联网下载运行依赖，以后的启动复用项目目录中的 `.venv`。也支持 Python 3.9 至 3.13。

## 在 Windows 打包 EXE

双击 `build_windows.bat`。输出位于 `dist\HoneyPet\`；把整个文件夹压缩发送给对方，对方无需安装 Python。该脚本使用固定版本依赖和 PyInstaller 的文件夹模式。

项目另有 GitHub Actions 工作流，可手动触发或在推送 `v*` 标签时构建原生 Windows 包，执行测试并生成可下载的 ZIP 构建产物。工作流文件不会自动发布发行版。

## 在任意系统组装离线便携包

```bash
python scripts/build_portable_windows.py --download
```

构建脚本从官方 NuGet 与 PyPI 下载固定版本输入，再检查预先记录的 SHA-256。已有缓存时可以省略 `--download`，完全离线打包。默认产物是 `dist/HoneyPet-Windows-x64.zip`，脚本不会执行 Windows 程序。第三方许可和对应源码地址随包附带。
