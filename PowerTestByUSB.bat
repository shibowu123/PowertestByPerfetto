@echo off
setlocal

REM 通过 ADB 关闭蓝牙/定位/移动数据，并将亮度设置为 50%

REM 检查 ADB 是否可用
adb version >nul 2>&1
if errorlevel 1 (
  echo [ERROR] 未找到 adb，请安装 Android 平台工具并配置 PATH。
  exit /b 1
)

REM 检查是否有已连接设备
for /f %%A in ('adb get-state') do set STATE=%%A
if /i not "%STATE%"=="device" (
  echo [ERROR] 未检测到已连接的设备，请连接并开启 USB 调试。
  exit /b 1
)

echo [INFO] 连接设备...
adb devices

echo [INFO] 正在关闭蓝牙...
adb shell svc bluetooth disable


echo [INFO] 正在关闭定位（Location/GPS）...
adb shell settings put secure location_mode 0

echo [INFO] 正在关闭移动数据（流量网络）...
adb shell svc data disable

echo [INFO] 正在将亮度设置为 一半（关闭自动亮度）...
adb shell settings put system screen_brightness_mode 0
adb shell settings put system screen_brightness 15

echo [INFO] 将自定义的配置文件推送到设备的Perfetto-config路径下 ...
adb push config/config.pbtxt /data/misc/perfetto-configs

echo [info] 执行测试采集perfetto Trace文件 （按ctrl+C提前结束测试）...
adb shell -t perfetto --txt -c /data/misc/perfetto-configs/config.pbtxt -o /data/misc/perfetto-traces/trace.pftrace

echo [info] 导出测试数据到PC
adb pull /data/misc/perfetto-traces/trace.pftrace traces/trace.pftrace

echo [info] 解析数据
REM 在虚拟环境下执行 Python 脚本
set "VENV_PY=%~dp0.venv\Scripts\python.exe"
if exist "%VENV_PY%" (
    "%VENV_PY%" "%~dp0main.py" --trace "%~dp0traces/trace.pftrace"
) else (
    echo [warn] 未找到虚拟环境，改用系统 Python
    python "%~dp0main.py" --trace "%~dp0traces/trace.pftrace"
)




echo [DONE] 操作完成。
echo.
echo 按任意键退出...
pause >nul
exit /b 0