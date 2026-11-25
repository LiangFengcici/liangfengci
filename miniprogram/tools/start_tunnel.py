# -*- coding: utf-8 -*-
"""一键公网地址：用 SSH 隧道把本机 8000 端口映射成公网 https 地址。

无需注册任何账号、无需下载额外程序（Windows 10/11 自带 OpenSSH 客户端）。

做的事：
  1. 检查本机后端是否在运行
  2. 建立 SSH 隧道（localhost.run），拿到 https://xxxx.app.lhr.life
  3. 实测该地址的 /api/catalog，通过才写入小程序 config.js
  4. 保持隧道常驻 —— 这个窗口关掉，公网地址即失效

用法：双击「一键公网地址.bat」，或
    python miniprogram/tools/start_tunnel.py
"""
from __future__ import annotations

import os
import re
import shutil
import subprocess
import sys
import threading
import time
import urllib.request

HERE = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, HERE)

# 输出重定向到文件时默认是块缓冲，进度会看不到；强制按行刷新
try:
    sys.stdout.reconfigure(line_buffering=True)
except Exception:                                        # noqa: BLE001
    pass

from set_public_host import current_settings, patch_config, probe       # noqa: E402

LOCAL_API = "http://127.0.0.1:8000/api/catalog"
URL_RE = re.compile(r"https://[a-z0-9-]+\.(?:app\.)?lhr\.life")


def check_local_backend() -> bool:
    try:
        with urllib.request.urlopen(LOCAL_API, timeout=6) as r:
            return r.status == 200
    except Exception:                                    # noqa: BLE001
        return False


def find_ssh() -> str | None:
    for p in (
        shutil.which("ssh"),
        r"C:\Windows\System32\OpenSSH\ssh.exe",
        r"C:\Program Files\Git\usr\bin\ssh.exe",
    ):
        if p and os.path.exists(p):
            return p
    return None


def main() -> int:
    print("=" * 64)
    print("  一键公网地址 · 让小程序连回你的牙科平台")
    print("=" * 64)

    if not check_local_backend():
        print("\n✗ 本机后端没在运行（http://127.0.0.1:8000/api/catalog 无响应）")
        print("  请先双击「启动系统.bat」，看到 Running on http://127.0.0.1:8000 后")
        print("  **保持那个窗口不要关**，再运行本工具。")
        return 1
    print("\n[1/4] 本机后端  …… 正常")

    ssh = find_ssh()
    if not ssh:
        print("\n✗ 找不到 ssh 客户端。请在「设置 → 应用 → 可选功能」中安装 OpenSSH 客户端。")
        return 1
    print(f"[2/4] ssh 客户端 …… {ssh}")

    cmd = [
        ssh,
        "-o", "StrictHostKeyChecking=no",
        "-o", "BatchMode=yes",
        "-o", "ServerAliveInterval=30",
        "-o", "ServerAliveCountMax=3",
        "-o", "ExitOnForwardFailure=yes",
        "-R", "80:127.0.0.1:8000",
        "nokey@localhost.run",
    ]
    print("[3/4] 正在建立隧道 ……")
    proc = subprocess.Popen(
        cmd,
        stdout=subprocess.PIPE,
        stderr=subprocess.STDOUT,
        text=True,
        encoding="utf-8",
        errors="ignore",
        bufsize=1,
    )

    url = ""
    deadline = time.time() + 60
    assert proc.stdout is not None
    while time.time() < deadline:
        line = proc.stdout.readline()
        if not line:
            if proc.poll() is not None:
                break
            time.sleep(0.2)
            continue
        m = URL_RE.search(line)
        if m:
            url = m.group(0)
            break

    if not url:
        print("\n✗ 隧道没建立成功（60 秒内没拿到地址）。")
        print("  常见原因：当前网络封了 22 端口出站。可改用手机热点后重试，")
        print("  或在 cmd 里执行下面的命令看具体报错：")
        print("  ssh -R 80:127.0.0.1:8000 nokey@localhost.run")
        proc.terminate()
        return 1

    print(f"      公网地址：{url}")

    print("[4/4] 实测公网可达性 ……", end=" ", flush=True)
    ok, detail = probe(url)
    if not ok:
        print("失败")
        print(f"      {detail}")
        print("\n  隧道已建立但访问不通，可能是刚建好还没生效，稍等 10 秒后重跑本工具。")
        proc.terminate()
        return 1
    print("通过")
    print(f"      {detail}")

    env, prod = current_settings()
    if prod == url and env == "prod":
        print("\n[ok] 配置已是最新，无需修改")
    else:
        patch_config("prod", url)
        print(f"\n[ok] 已写入 config.js：ENV = 'prod'，PROD_URL = '{url}'")

    print("""
────────────────────────────────────────────────────────────
 接下来（一次性，每次地址变化都要做）：
   1. 微信开发者工具按 Ctrl+B 重新编译
      首页顶部应显示「已连接诊所后台 · 数据实时同步」
   2. 右上角「上传」→ 版本号加一 → 后台「版本管理」设为体验版
   3. 老师扫码后点右上角「···」→「打开调试」

 ⚠ 这个窗口不能关。关掉后公网地址立即失效，小程序会退回离线演示数据。
   下次重新运行本工具即可拿到新地址（会自动改写配置）。
────────────────────────────────────────────────────────────
按 Ctrl+C 退出（同时断开隧道）。
""")

    # 保持前台：持续转发 ssh 输出，直到进程结束或用户 Ctrl+C
    def pump() -> None:
        try:
            for line in proc.stdout:                      # type: ignore[union-attr]
                if "error" in line.lower() or "Permission" in line:
                    print("  [ssh]", line.rstrip())
        except Exception:                                 # noqa: BLE001
            pass

    threading.Thread(target=pump, daemon=True).start()
    try:
        while proc.poll() is None:
            time.sleep(0.5)
    except KeyboardInterrupt:
        print("\n正在断开隧道 …")
    finally:
        if proc.poll() is None:
            proc.terminate()
        try:
            proc.wait(timeout=5)
        except Exception:                                 # noqa: BLE001
            proc.kill()
    print("隧道已断开。")
    return 0


if __name__ == "__main__":
    sys.exit(main())
