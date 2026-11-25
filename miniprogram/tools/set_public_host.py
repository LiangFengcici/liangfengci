# -*- coding: utf-8 -*-
"""公网地址配置助手：把内网穿透 / 云服务器地址写入小程序 config.js。

用法：
    双击「设置公网地址.bat」
或
    python miniprogram/tools/set_public_host.py https://xxxx.cpolar.top
    python miniprogram/tools/set_public_host.py --local     # 切回本机 127.0.0.1

为什么需要它：手机上 127.0.0.1 指向手机自己，局域网 IP 只在同一 Wi-Fi 内有效。
要让老师在任何网络下都能用、并且数据回到你电脑上的牙科平台，就需要一个公网地址。
"""
from __future__ import annotations

import ipaddress
import json
import os
import re
import socket
import sys
import urllib.error
import urllib.parse
import urllib.request

ROOT = os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
CONFIG = os.path.join(ROOT, "miniprogram", "utils", "config.js")


def guess_private(host: str) -> str | None:
    """判断是否是不通公网的地址，返回提示语。"""
    if host in ("localhost", "0.0.0.0"):
        return "这是本机地址，手机访问不到"
    if re.match(r"^\d+\.\d+\.\d+\.\d+$", host):
        try:
            addr = ipaddress.IPv4Address(host)
        except ValueError:
            return "IP 格式不正确"
        if addr.is_loopback:
            return "127.x 是手机自己，不是你的电脑"
        if addr in ipaddress.IPv4Network("100.64.0.0/10"):
            return "100.64/10 是运营商 NAT 网段，外网访问不到"
        if addr.is_private:
            return "这是局域网地址，只有同一 Wi-Fi 下的设备能访问（老师在外网用不了）"
    return None


def normalize(raw: str) -> str:
    """把用户输入整理成标准 URL：必须有 scheme，末尾不留斜杠。"""
    url = raw.strip().strip('"').strip("'")
    if not url:
        return ""
    if not re.match(r"^https?://", url, re.I):
        url = "https://" + url
    p = urllib.parse.urlsplit(url)
    scheme = p.scheme.lower()
    netloc = p.netloc.rstrip("/")
    return f"{scheme}://{netloc}"


def patch_config(env: str, prod_url: str | None = None) -> None:
    with open(CONFIG, encoding="utf-8") as f:
        text = f.read()
    text = re.sub(r"const ENV = '[^']*'", f"const ENV = '{env}'", text)
    if prod_url:
        text = re.sub(r"const PROD_URL = '[^']*'", f"const PROD_URL = '{prod_url}'", text)
    with open(CONFIG, "w", encoding="utf-8") as f:
        f.write(text)


def current_settings() -> tuple[str, str]:
    with open(CONFIG, encoding="utf-8") as f:
        text = f.read()
    env = re.search(r"const ENV = '([^']*)'", text)
    prod = re.search(r"const PROD_URL = '([^']*)'", text)
    return (env.group(1) if env else "?", prod.group(1) if prod else "?")


def probe(base_url: str) -> tuple[bool, str]:
    """从本机访问 <url>/api/catalog，确认穿透链路是通的。"""
    url = base_url + "/api/catalog"
    req = urllib.request.Request(url, headers={"User-Agent": "dental-check/1.0"})
    try:
        with urllib.request.urlopen(req, timeout=25) as r:
            body = r.read().decode("utf-8", "ignore")
        try:
            data = json.loads(body)
            if data.get("code") == 0:
                cats = data.get("data") or []
                names = "、".join(c.get("name", "") for c in cats[:4])
                return True, f"返回 {len(cats)} 个分类（{names}…）"
            return False, f"响应非成功：{body[:120]}"
        except json.JSONDecodeError:
            return False, f"返回的不是 JSON（可能被拦截页替换）：{body[:120]}"
    except urllib.error.HTTPError as e:
        return False, f"HTTP {e.code}：{e.reason}"
    except Exception as exc:                             # noqa: BLE001
        return False, str(exc)


def main() -> int:
    print("=" * 62)
    print("  公网地址配置助手 · 让小程序连回你的牙科平台")
    print("=" * 62)
    env, prod = current_settings()
    print(f"\n当前 config.js：ENV = '{env}'，PROD_URL = '{prod}'")

    arg = sys.argv[1].strip() if len(sys.argv) > 1 else ""

    if arg in ("--local", "local"):
        patch_config("local")
        print("\n[ok] 已切回本机模式（ENV = 'local'），开发者工具模拟器可直接用。")
        return 0

    if not arg:
        print("""
怎么拿到公网地址（以 cpolar 为例，免费版够用）：
  1. 打开 https://www.cpolar.com 注册（邮箱即可）
  2. 进入「验证」页复制你的 authtoken
  3. 下载 Windows 客户端并解压，在该目录打开 cmd 执行：
        cpolar authtoken 你的token
        cpolar http 8000
  4. 窗口里会打印一行 Forwarding，形如
        https://a1b2c3d4.r3.cpolar.top -> http://localhost:8000
     复制 https 开头那个地址（不带末尾斜杠）

  另一个可选工具：natapp（https://natapp.cn），免费隧道同样给一个公网域名。

⚠ 这个窗口必须一直开着，关掉公网地址就失效；免费版重启后域名可能变化，
  变了就再跑一次本工具粘贴新地址即可（30 秒）。
""")
        try:
            arg = input("粘贴公网地址（回车退出）：").strip()
        except (EOFError, KeyboardInterrupt):
            print("\n已退出，未修改。")
            return 0

    if not arg:
        print("未输入，已退出。")
        return 0

    url = normalize(arg)
    p = urllib.parse.urlsplit(url)
    host = p.hostname or ""
    if not host:
        print(f"\n✗ 无法解析地址：{arg}")
        return 1

    warn = guess_private(host)
    if warn:
        print(f"\n✗ {warn}\n  你输入的是：{url}")
        print("  请粘贴内网穿透工具给出的公网地址（形如 https://xxxx.cpolar.top）。")
        return 1

    if p.scheme != "https":
        print("\n[warn] 当前是 http 地址。开发者工具和「打开调试」的体验版能用，")
        print("       但正式发布的小程序只接受 https，建议优先用 https 地址。")

    print(f"\n检测域名解析：{host} …", end=" ")
    try:
        ip = socket.gethostbyname(host)
        print(ip)
    except Exception as exc:                             # noqa: BLE001
        print(f"失败（{exc}）")
        print("  → 确认穿透工具窗口还在运行，且地址复制完整。")
        return 1

    print(f"访问 {url}/api/catalog …", end=" ")
    ok, detail = probe(url)
    print("通过" if ok else "失败")
    print(f"  {detail}")

    if not ok:
        print("\n先不写入配置。请确认：")
        print("  1) 后端窗口（启动系统.bat）仍在运行")
        print("  2) 穿透窗口打印的本地端口是 8000")
        print("  3) 浏览器能直接打开上面的地址")
        print("  修好后再跑一次本工具即可。")
        return 1

    patch_config("prod", url)
    print(f"\n[ok] 已写入 config.js：ENV = 'prod'，PROD_URL = '{url}'")
    print(f"     文件：{CONFIG}")

    print("""
接下来：
  1) 微信开发者工具按 Ctrl+B 重新编译 → 首页顶部状态条应显示「已连接诊所后台」
  2) 上传新版本（版本号加一）→ 后台「版本管理」设为体验版
  3) 老师打开时若白屏：右上角「···」→ 打开调试（跳过域名校验，http 地址必须开）
  4) 验证同步：在小程序里预约 → 电脑上员工端「前台接待」当天队列里能看到这条记录
""")
    return 0


if __name__ == "__main__":
    sys.exit(main())
