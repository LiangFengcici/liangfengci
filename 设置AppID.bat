@echo off
chcp 65001 >nul
title 小程序 AppID 设置工具
cd /d "%~dp0"

set PY=
if exist "%~dp0runtime\python.exe" set PY="%~dp0runtime\python.exe"
if not defined PY if exist "%~dp0web\.venv\Scripts\python.exe" set PY="%~dp0web\.venv\Scripts\python.exe"
if not defined PY (
  py -3 --version >nul 2>&1 && set PY=py -3
)
if not defined PY (
  python --version >nul 2>&1 && set PY=python
)
if not defined PY (
  echo [错误] 未找到 Python 3，请不要用这个脚本，直接在微信开发者工具里手动改 AppID。
  pause
  exit /b 1
)

%PY% "%~dp0miniprogram\tools\set_appid.py" %1
echo.
pause
