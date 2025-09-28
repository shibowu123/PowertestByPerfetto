@echo off
setlocal
echo [info] 解析数据
REM 在虚拟环境下执行 Python 脚本
set "VENV_PY=%~dp0.venv\Scripts\python.exe"
if exist "%VENV_PY%" (
    "%VENV_PY%" "%~dp0compare_traces.py" --traces "%~dp0traces" --metric avg_power
) else (
    echo [warn] 未找到虚拟环境，改用系统 Python
    python "%~dp0compare_traces.py" --trace "%~dp0traces" --metric avg_power
)


