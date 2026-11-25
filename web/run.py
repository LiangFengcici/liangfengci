"""一键启动脚本：检查依赖 → 初始化演示库（首次）→ 启动 Web 服务。

用法：
    python run.py            # 默认 8000 端口
    python run.py 8080       # 指定端口
"""
from __future__ import annotations

import importlib
import os
import subprocess
import sys

BASE = os.path.dirname(os.path.abspath(__file__))
os.chdir(BASE)
sys.path.insert(0, BASE)


def ensure_flask():
    try:
        importlib.import_module("flask")
        return True
    except ImportError:
        print("[依赖] 未检测到 Flask，正在安装 …")
        try:
            subprocess.check_call([sys.executable, "-m", "pip", "install", "flask"])
            return True
        except Exception as exc:                     # noqa: BLE001
            print("[错误] Flask 安装失败：", exc)
            print("       请手动执行： pip install flask")
            return False


def ensure_db():
    if not os.path.exists(os.path.join(BASE, "data", "dental.db")):
        print("[数据] 首次运行，正在初始化演示数据库（57 张表 + 种子数据）…")
        import seed
        seed.run()


def local_ips():
    import socket
    ips = []
    try:
        host = socket.gethostname()
        for info in socket.getaddrinfo(host, None):
            ip = info[4][0]
            if ip.count(".") == 3 and not ip.startswith("127."):
                ips.append(ip)
    except Exception:                                # noqa: BLE001
        pass
    return sorted(set(ips))


def main():
    port = int(sys.argv[1]) if len(sys.argv) > 1 else int(os.environ.get("PORT", "8000"))
    print("=" * 64)
    print("  牙科诊所诊疗信息平台")
    print("=" * 64)
    if not ensure_flask():
        return 1
    ensure_db()

    print("\n  员工端   http://127.0.0.1:%d/login" % port)
    print("  患者端   http://127.0.0.1:%d/p/" % port)
    for ip in local_ips():
        print("  局域网   http://%s:%d/  （手机 / 小程序真机用这个）" % (ip, port))
    print("\n  演示账号：front1 / doc1 / fin1 / mgr1 / ops1   密码：123456")
    print("  患者端直接在页面选择患者档案登录")
    print("-" * 64 + "\n")

    from app import app
    app.run(host="0.0.0.0", port=port, debug=False, threaded=True)


if __name__ == "__main__":
    sys.exit(main())
