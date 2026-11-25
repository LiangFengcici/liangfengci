"""真机联调助手：自动检测电脑局域网 IP → 写入小程序 config.js → 自测接口可达性。

用法（在系统分析与设计目录下）：
    双击「设置真机IP.bat」
或
    python miniprogram/tools/set_lan_ip.py

原理：真机调试时 127.0.0.1 指向手机自己，必须让小程序访问电脑的局域网 IP。
"""
from __future__ import annotations

import ipaddress
import os
import re
import subprocess
import sys
import urllib.request

ROOT = os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
CONFIG = os.path.join(ROOT, "miniprogram", "utils", "config.js")
PORT = 8000


# ---------------------------------------------------------------- 网卡枚举
def list_ipv4() -> list[tuple[str, str]]:
    """返回 [(适配器名, IPv4)]，顺序即 ipconfig 顺序。"""
    try:
        raw = subprocess.check_output(["ipconfig"], encoding="gbk", errors="ignore")
    except Exception:                                    # noqa: BLE001
        return []
    result, adapter = [], ""
    for line in raw.splitlines():
        s = line.strip()
        m = re.match(r"^(?:无线局域网适配器|以太网适配器|未知适配器)\s*(.+?):", s)
        if m:
            adapter = m.group(1).strip()
            continue
        m = re.search(r"IPv4\s*地址[^:]*:\s*([\d.]+)", s)
        if m:
            result.append((adapter, m.group(1)))
    return result


def grade(ip: str) -> int:
    """越小越优先：家用/热点网段优先，CGNAT、虚拟网卡靠后。"""
    try:
        addr = ipaddress.IPv4Address(ip)
    except ValueError:
        return 99
    if addr.is_loopback or addr.is_link_local:
        return 98
    if addr in ipaddress.IPv4Network("100.64.0.0/10"):
        return 90                                        # 运营商 NAT：手机基本连不通
    if addr in ipaddress.IPv4Network("192.168.0.0/16"):
        return 0
    if addr in ipaddress.IPv4Network("172.16.0.0/12"):
        return 1
    if addr in ipaddress.IPv4Network("10.0.0.0/8"):
        return 2
    return 3


# ---------------------------------------------------------------- 写配置
def patch_config(ip: str) -> str:
    with open(CONFIG, encoding="utf-8") as f:
        text = f.read()
    text = re.sub(r"const ENV = '[^']*'", "const ENV = 'lan'", text)
    text = re.sub(r"const LAN_HOST = '[^']*'", f"const LAN_HOST = '{ip}'", text)
    with open(CONFIG, "w", encoding="utf-8") as f:
        f.write(text)
    return text


def probe(ip: str) -> tuple[bool, str]:
    url = f"http://{ip}:{PORT}/api/catalog"
    try:
        with urllib.request.urlopen(url, timeout=4) as r:
            body = r.read(120).decode("utf-8", "ignore")
        return True, body
    except Exception as exc:                             # noqa: BLE001
        return False, str(exc)


def main() -> int:
    print("=" * 62)
    print("  真机联调助手 · 配置小程序访问地址")
    print("=" * 62)

    found = list_ipv4()
    if not found:
        print("\n[!] 没有检测到任何 IPv4 地址，请确认网络已连接。")
        return 1

    found.sort(key=lambda x: grade(x[1]))
    print("\n检测到以下网络地址：")
    for i, (adapter, ip) in enumerate(found, 1):
        note = ""
        if grade(ip) >= 90:
            note = "  ← 运营商 NAT，手机通常连不通"
        print(f"  {i}. {ip:<16} {adapter}{note}")

    best_adapter, best_ip = found[0]
    auto = grade(best_ip) < 90
    if not auto:
        print("\n[warn] 当前没有可直接给手机使用的局域网地址（都是 100.x 这类 NAT 地址）。")
        print("       建议：手机开启个人热点 → 电脑连接该热点 → 重新运行本工具。")

    print(f"\n将写入：ENV = 'lan'，LAN_HOST = '{best_ip}'  （{best_adapter}）")
    if "--yes" not in sys.argv:
        try:
            input("回车确认写入，或按 Ctrl+C 取消 …")
        except (KeyboardInterrupt, EOFError):
            print("\n已取消。")
            return 0

    patch_config(best_ip)
    print(f"[ok] 已更新 {CONFIG}")

    ok, detail = probe(best_ip)
    if ok:
        print(f"[ok] 本机访问 http://{best_ip}:{PORT}/api/catalog 正常：{detail[:80]}")
        print("\n接下来：")
        print("  1) 保持后端窗口运行（启动系统.bat 别关）")
        print("  2) 开发者工具按 Ctrl+B 重新编译")
        print("  3) 手机与电脑连同一网络后，重新扫码「真机调试」")
        if not auto:
            print("  4) 但当前是 NAT 地址，手机大概率仍连不上 → 请改用手机热点后重跑本工具")
    else:
        print(f"[!] 本机访问 http://{best_ip}:{PORT}/api/catalog 失败：{detail}")
        print("    请先启动后端：双击「启动系统.bat」，再重跑本工具。")

    print("\n若手机仍提示连不上，请检查 Windows 防火墙是否放行 8000 入站端口。")
    return 0


if __name__ == "__main__":
    sys.exit(main())
