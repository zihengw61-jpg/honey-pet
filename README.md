# 桃桃 · 桌面小狐狸

一只用 Python + PySide6 写的原创红色小狐狸，可以送给喜欢的人。透明背景、没有普通任务栏窗口，默认在桌面右下角露出小脑袋。程序本身离线运行。

## Windows 免安装版本

下载 `HoneyPet-Windows-x64.zip`，**完整解压**到一个文件夹，再双击其中的 `HoneyPet.exe`。无需安装 Python，无需联网。适用于 Windows 10 / 11 的 64 位 Intel / AMD 电脑。

请把整个压缩包发给对方；只发送 `HoneyPet.exe` 不够，因为运行库也在同一个文件夹里。不要直接在压缩包预览窗口里运行。

便携包包含官方 Python 3.12.10 运行库和 PySide6 Essentials 6.8.3。启动器使用随包 Python GUI 解释器加载应用；它不是一个单文件打包程序。Python 和 Qt 的第三方许可文件随包保留。

## 和它玩

| 操作 | 小狐狸的反应 |
| --- | --- |
| 点击露出的小脑袋 | 从任务栏上方钻出来，挥挥手 |
| 单击出来的小狐狸 | 开心地眯眼，冒出爱心 |
| 双击 | 跳一段开心舞 |
| 按住并拖动 | 抱起它，放到桌面其他位置 |
| 右键小狐狸或托盘图标 | 喂小饼干、跳舞、睡觉、缩回、隐藏、调整大小 |
| 点击托盘图标，或再次运行程序 | 唤回小狐狸 |

默认闲置 45 秒后缩回右下角，可以在右键菜单关闭这个选项。睡觉时会一直安静陪着你，点击就能叫醒。右键菜单还可以设置它对你的称呼，修改后会记住。

“缩回去”保留可点击的小脑袋；“藏到托盘”完全隐藏桌面形象，只留下右下角托盘图标。Windows 有时会把图标放进托盘的向上小箭头里。右键菜单的“退出小狐狸”会真正结束程序。

“钻出来”是在桌面工作区底边做的动画效果，位置在任务栏上方。不会修改 Windows 的任务栏。

## 动画怎么做得自然

小狐狸使用代码绘制的分层矢量角色，放大仍然清晰，无需额外 GIF 素材。

- 呼吸、眨眼、视线跟随、耳朵轻摆和尾巴摇动一直叠加在主动作上。
- 开心、挥手、跳舞、吃饼干、睡觉和被抱起有不同的表情和肢体动作。
- 探出和缩回使用缓动插值；动作按经过的时间推进，帧率变化时仍保持速度。
- 桌面显示约 60 帧/秒，小脑袋待机约 30 帧/秒；“暂停小动作”可让角色保持安静。
- 透明区域使用窗口命中区域，减少对其他桌面内容的点击遮挡。

后续如果想换成手绘风格，可以保留交互和状态逻辑，把 `foxpet/renderer.py` 换成透明 PNG 序列帧或骨骼动画渲染。

## 运行源码

推荐 Python 3.12。Windows 用户可双击 `start_windows.bat`，首次会安装依赖，之后直接启动。

其他系统或手动运行：

```bash
python -m venv .venv
# Windows: .venv\Scripts\python -m pip install -r requirements.txt
.venv/bin/python -m pip install -r requirements.txt
.venv/bin/python main.py
```

Python 源码可用于 macOS 和具有 Qt 桌面支持的 Linux；本次交付的便携运行库仅支持 Windows x64。Linux Wayland 的窗口位置、置顶和托盘行为取决于桌面环境。

## 在 Windows 重新打包

双击 `build_windows.bat`，会用 PyInstaller 生成 `dist/HoneyPet/`。把整个文件夹压缩发给对方即可。仓库也提供 Windows GitHub Actions 构建流程。

开发者可在任意系统整理 Windows 便携运行库：

```bash
python scripts/build_portable_windows.py --download
```

这个脚本下载官方 Windows Python 运行库与 Windows 二进制依赖并整理成便携包。它不在其他系统上执行 Windows 程序。

## 验证与排错

```bash
python -m pip install pytest
QT_QPA_PLATFORM=offscreen python -m pytest tests
QT_QPA_PLATFORM=offscreen python main.py --smoke-test
```

测试覆盖动画切换、快速反向、长帧、睡眠唤醒、拖拽与点击区分、无托盘隐藏恢复、多屏坐标边界等。Linux 无显示器环境可使用 Qt 的 offscreen 后端；它不能代替在真实 Windows 桌面验证透明窗口、任务栏和托盘效果。

Windows 启动异常时运行包内的 `诊断启动.bat`。启动错误记录在 `%LOCALAPPDATA%\HoneyPet\launcher.log`，应用错误记录在同目录的 `pet.log`。

预览生成脚本：`scripts/render_preview.py`。预览使用与桌面程序相同的角色渲染代码。
