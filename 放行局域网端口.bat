@echo off
chcp 65001 >nul
title 放行 8000 端口 · 让局域网设备能打开网站
net session >nul 2>&1
if %errorlevel% neq 0 (
  echo [!] 需要管理员权限，正在请求 …
  powershell -Command "Start-Process -FilePath '%~f0' -Verb RunAs"
  exit /b
)
netsh advfirewall firewall delete rule name="DentalClinic8000" >nul 2>&1
netsh advfirewall firewall add rule name="DentalClinic8000" dir=in action=allow protocol=TCP localport=8000 profile=any
if %errorlevel% equ 0 (
  echo.
  echo [ok] 已放行 TCP 8000 入站。
  echo      同一 Wi-Fi 下的手机/电脑现在可以用下面的地址打开网站：
  echo      http://本机局域网IP:8000   （IP 见「启动系统.bat」窗口里打印的 局域网 行）
) else (
  echo [错误] 添加规则失败。
)
echo.
pause
