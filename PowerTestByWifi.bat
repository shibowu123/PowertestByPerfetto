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

echo [INFO] 通过 USB 连接设备...
adb devices

echo [INFO] 切换到 Wi-Fi ADB（需要设备已连接同一 Wi-Fi）...
set "ADB_PORT=5555"
set "DEVICE_IP="
set "IP_WITH_MASK="
for /f "tokens=2 delims= " %%i in ('adb shell ip addr show wlan0 ^| findstr /R /C:" inet " ^| findstr /V "inet6"') do (
  if not defined IP_WITH_MASK set "IP_WITH_MASK=%%i"
)
for /f "tokens=1 delims=/" %%i in ("%IP_WITH_MASK%") do set "DEVICE_IP=%%i"
if not defined DEVICE_IP (
  echo [ERROR] 无法获取设备的 Wi-Fi IP，请确保设备已连接 Wi-Fi 并开启无线调试。
  exit /b 1
)
echo [INFO] 设备 Wi-Fi IP: %DEVICE_IP%
adb tcpip %ADB_PORT%
timeout /t 2 /nobreak >nul
adb connect %DEVICE_IP%:%ADB_PORT%
if errorlevel 1 (
  echo [ERROR] 通过 Wi-Fi 连接设备失败。
  exit /b 1
)
echo [INFO] 已通过 Wi-Fi 连接：%DEVICE_IP%:%ADB_PORT%
adb devices
echo.
echo [ACTION] 请拔掉 USB 线后继续（设备已通过 Wi-Fi 保持连接）...
pause >nul

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