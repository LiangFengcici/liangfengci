@echo off
chcp 65001 >nul
title 固定公网地址 · 小程序永久连回牙科平台
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
  echo [错误] 未找到 Python 3，请先安装 Python 3.10+ 并勾选 Add to PATH
  pause
  exit /b 1
)

%PY% "%~dp0miniprogram\tools\start_ngrok.py"
echo.
pause
