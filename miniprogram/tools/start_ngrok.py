# -*- coding: utf-8 -*-
"""固定公网地址：用 ngrok 免费「静态域名」把本机 8000 端口映射成永久不变的 https 地址。

与 start_tunnel.py 的区别：
  localhost.run 每次重连都换域名 → 小程序要重新上传；
  ngrok 静态域名注册一次就固定 → config.js 只需改一次，小程序传一次就够。

前提（只需做一次，约 3 分钟）：
  1. 注册 https://dashboard.ngrok.com/signup （邮箱即可，免费）
  2. 复制 authtoken：https://dashboard.ngrok.com/get-started/your-authtoken
  3. 领一个免费静态域名：https://dashboard.ngrok.com/domains → New Domain
     （形如 dental-lfc.ngrok-free.app）

用法：双击「固定地址.bat」；首次运行会把 token / 域名记到 tools/ 下，以后直接启动。
"""
from __future__ import annotations

import json
import os
import re
import subprocess
import sys
import time
import urllib.request

HERE = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, HERE)

try:
    sys.stdout.reconfigure(line_buffering=True)
except Exception:                                        # noqa: BLE001
    pass

from set_public_host import current_settings, patch_config, probe       # noqa: E402

ROOT = os.path.dirname(os.path.dirname(HERE))            # D:\系统分析与设计
NGROK_EXE = os.path.join(ROOT, "tools", "ngrok", "ngrok.exe")
TOKEN_FILE = os.path.join(HERE, "ngrok_token.txt")
DOMAIN_FILE = os.path.join(HERE, "ngrok_domain.txt")
ADDR_FILE = os.path.join(ROOT, "runtime", "当前公网地址.txt")
API = "http://127.0.0.1:4040/api/tunnels"


def read_first(path: str) -> str:
    if os.path.exists(path):
        with open(path, encoding="utf-8-sig") as f:
            return f.read().strip()
    return ""


def save(path: str, value: str) -> None:
    with open(path, "w", encoding="utf-8") as f:
        f.write(value.strip() + "\n")


def ask(prompt: str, hint: str) -> str:
    print(f"\n{hint}\n")
    try:
        val = input(prompt).strip().strip('"').strip("'")
    except (EOFError, KeyboardInterrupt):
        return ""
    return val


def normalize_domain(raw: str) -> str:
    d = raw.strip().lower()
    d = re.sub(r"^https?://", "", d).rstrip("/")
    return d


def extract_token(raw: str) -> str:
    """兼容粘贴整条命令：ngrok config add-authtoken XXXX → 提取 XXXX。"""
    m = re.search(r"add-authtoken\s+(\S+)", raw)
    if m:
        return m.group(1)
    return raw.strip().strip('"').strip("'")


def extract_domain(raw: str) -> str:
    """兼容粘贴整条命令：ngrok http 8080 --url https://x.y → 提取域名。"""
    m = re.search(r"--url\s+(\S+)", raw)
    if m:
        raw = m.group(1)
    raw = raw.strip().strip('"').strip("'").lower()
    return re.sub(r"^https?://", "", raw).rstrip("/")


def get_token() -> str:
    token = os.environ.get("NGROK_AUTHTOKEN", "") or read_first(TOKEN_FILE)
    if token:
        token = extract_token(token) if "add-authtoken" in token else token
        print(f"[1/5] authtoken …… 已保存（{token[:6]}…）")
        return token
    token = ask("把第 2 步「添加你的认证令牌」里 Copy 的内容整个粘贴进来后回车：",
                "网页第 2 步有一行 ngrok config add-authtoken 开头的命令，\n"
                "点它右边的 Copy，然后整个粘贴到这里就行（脚本会自动取出 token）")
    if not token:
        return ""
    token = extract_token(token)
    save(TOKEN_FILE, token)
    return token


def get_domain() -> str:
    dom = read_first(DOMAIN_FILE)
    if dom:
        dom = extract_domain(dom)
        print(f"[2/5] 固定域名 …… {dom}")
        return dom
    dom = ask("把第 3 步「启动你的终端」里 Copy 的内容整个粘贴进来后回车：",
              "网页第 3 步有一行 ngrok http 8080 --url https://xxxx.ngrok-free.dev 的命令，\n"
              "点它右边的 Copy，然后整个粘贴到这里就行（脚本会自动取出域名）")
    if not dom:
        return ""
    dom = extract_domain(dom)
    save(DOMAIN_FILE, dom)
    return dom


def ngrok_alive() -> bool:
    try:
        with urllib.request.urlopen(API, timeout=4) as r:
            return r.status == 200
    except Exception:                                    # noqa: BLE001
        return False


def public_url_from_api() -> str:
    try:
        with urllib.request.urlopen(API, timeout=6) as r:
            data = json.loads(r.read().decode("utf-8", "ignore"))
        for t in data.get("tunnels", []):
            u = t.get("public_url", "")
            if u.startswith("https://"):
                return u
        for t in data.get("tunnels", []):
            if t.get("public_url"):
                return t["public_url"]
    except Exception:                                    # noqa: BLE001
        pass
    return ""


NGROK_ZIP_URL = "https://bin.equinox.io/c/bNyj1mQVY4c/ngrok-v3-stable-windows-amd64.zip"


def ensure_ngrok() -> bool:
    """没有 ngrok.exe 就自动下载解压（12MB，视网络 1~5 分钟）。"""
    if os.path.exists(NGROK_EXE):
        return True
    import urllib.request
    import zipfile
    target_dir = os.path.dirname(NGROK_EXE)
    os.makedirs(target_dir, exist_ok=True)
    zip_path = os.path.join(target_dir, "ngrok.zip")
    print("[!] 没找到 ngrok.exe，正在自动下载（约 12MB）……")
    try:
        def hook(blocks: int, block_size: int, total: int) -> None:
            if total > 0:
                pct = min(100, blocks * block_size * 100 // total)
                if pct % 5 == 0:
                    print(f"    下载中 {pct}%", flush=True)

        urllib.request.urlretrieve(NGROK_ZIP_URL, zip_path, hook)
        with zipfile.ZipFile(zip_path) as z:
            z.extractall(target_dir)
        try:
            os.remove(zip_path)
        except OSError:
            pass
    except Exception as exc:                             # noqa: BLE001
        print(f"\n✗ 自动下载失败：{exc}")
        print("  请手动打开下面的链接下载压缩包，解压出 ngrok.exe 放到：")
        print(f"    {target_dir}")
        print(f"    {NGROK_ZIP_URL}")
        return False
    if not os.path.exists(NGROK_EXE):
        print(f"\n✗ 解压后仍没有 {NGROK_EXE}")
        return False
    print("    下载完成")
    return True


def _clean_env() -> dict:
    """免费账号不允许 agent 走 http 代理：启动 ngrok 时清掉代理环境变量。"""
    env = dict(os.environ)
    for k in ("HTTP_PROXY", "HTTPS_PROXY", "ALL_PROXY",
              "http_proxy", "https_proxy", "all_proxy"):
        env.pop(k, None)
    return env


def main() -> int:
    print("=" * 66)
    print("  固定公网地址 · 让小程序永久连回你的牙科平台")
    print("=" * 66)

    if not ensure_ngrok():
        return 1

    # 后端是否在跑
    try:
        with urllib.request.urlopen("http://127.0.0.1:8000/api/catalog", timeout=6) as r:
            ok = r.status == 200
    except Exception:                                    # noqa: BLE001
        ok = False
    if not ok:
        print("\n✗ 本机后端没在运行。请先双击「启动系统.bat」，保持那个窗口开着。")
        return 1
    print("[0/5] 本机后端 …… 正常")

    token = get_token()
    if not token:
        print("\n已取消（没有 authtoken）。")
        return 1

    print("[3/5] 写入 ngrok 配置 ……", end=" ")
    r = subprocess.run([NGROK_EXE, "config", "add-authtoken", token],
                       capture_output=True, text=True)
    if r.returncode != 0:
        print("失败")
        print((r.stderr or r.stdout).strip()[:400])
        print("\n  → token 可能粘贴错了，删掉 tools\\ngrok_token.txt 后重跑。")
        return 1
    print("完成")

    domain = get_domain()
    if not domain:
        print("\n已取消（没有静态域名）。")
        return 1

    if ngrok_alive():
        print("\n[!] 4040 端口已有 ngrok 在跑，先关掉那个窗口再运行本工具。")
        return 1

    print("[4/5] 建立隧道 ……", end=" ")
    proc = subprocess.Popen(
        [NGROK_EXE, "http", "8000", "--url", f"https://{domain}", "--log", "stdout",
         "--log-format", "logfmt"],
        stdout=subprocess.PIPE, stderr=subprocess.STDOUT, text=True,
        encoding="utf-8", errors="ignore", bufsize=1,
        env=_clean_env(),
    )

    url = ""
    deadline = time.time() + 40
    while time.time() < deadline:
        time.sleep(1.5)
        url = public_url_from_api()
        if url:
            break
        if proc.poll() is not None:
            break

    if not url:
        print("失败")
        out = ""
        if proc.stdout:
            try:
                out = proc.stdout.read()[:800]
            except Exception:                            # noqa: BLE001
                pass
        print(out.strip() or "（无输出）")
        print("""
  常见原因：
   • 域名没填对 / 已被别的账号占用 → 回 https://dashboard.ngrok.com/domains 核对
   • 免费账号只能同时开 1 条隧道 → 关掉其它 ngrok 窗口
   • authtoken 失效 → 删掉 tools\\ngrok_token.txt 重新粘贴""")
        if proc.poll() is None:
            proc.terminate()
        return 1
    print("成功")
    print(f"      固定地址：{url}")

    print("[5/5] 实测公网可达 ……", end=" ")
    good, detail = probe(url)
    if not good:
        print("失败")
        print(f"      {detail}")
        print("  等 10 秒再重跑一次；若一直失败，检查浏览器能否打开上面的地址。")
        proc.terminate()
        return 1
    print("通过")
    print(f"      {detail}")

    env, prod = current_settings()
    if prod == url and env == "prod":
        print("\n[ok] config.js 已指向该地址，无需改动")
    else:
        patch_config("prod", url)
        print(f"\n[ok] 已写入 config.js：ENV = 'prod'，PROD_URL = '{url}'")

    os.makedirs(os.path.dirname(ADDR_FILE), exist_ok=True)
    with open(ADDR_FILE, "w", encoding="utf-8") as f:
        f.write(url + "\n")

    print(f"""
────────────────────────────────────────────────────────────
  地址是固定的：以后再启动还是 https://{domain}
  也就是说，小程序只需要「上传一次」，以后不用再传。

  小程序那边（只做一次）：
   1. 微信开发者工具 Ctrl+B 重新编译 → 首页横幅应变绿
      「已连接诊所后台 · 数据实时同步」
   2. 右上角「上传」→ 版本号 1.0.1 → 微信后台「版本管理」设为体验版
   3. 老师扫体验版二维码，点右上角「···」→「打开调试」

  员工端网页（你自己用）：
   {url}/login     演示账号 front1 / doc1 / fin1 / mgr1 / ops1，密码 123456

  ⚠ 这个窗口要开着（你的电脑就是服务器）。关掉 = 小程序连不上，退回离线演示。
     忘了地址就重新双击「固定地址.bat」，地址不会变。
────────────────────────────────────────────────────────────
按 Ctrl+C 退出（同时断开隧道）。
""")

    # 常驻：转发 ngrok 关键日志
    assert proc.stdout is not None
    try:
        for line in proc.stdout:
            low = line.lower()
            if any(k in low for k in ("err", "fail", "reconnect", "expired", "denied")):
                print("  [ngrok]", line.rstrip()[:200])
    except KeyboardInterrupt:
        print("\n正在断开隧道 …")
    finally:
        if proc.poll() is None:
            proc.terminate()
        try:
            proc.wait(timeout=5)
        except Exception:                                # noqa: BLE001
            proc.kill()
    print("隧道已断开。")
    return 0


if __name__ == "__main__":
    sys.exit(main())
