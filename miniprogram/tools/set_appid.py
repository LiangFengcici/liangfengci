# -*- coding: utf-8 -*-
"""把正式 AppID 写入 miniprogram/project.config.json。

用法：双击 设置AppID.bat，或 python tools/set_appid.py wx1234567890abcdef
"""
from __future__ import annotations

import json
import os
import re
import sys

HERE = os.path.dirname(os.path.abspath(__file__))
CONFIG = os.path.join(os.path.dirname(HERE), "project.config.json")

PATTERN = re.compile(r"^wx[0-9a-f]{16}$")

# 测试号 / 游客模式专用标识，不能上传
INVALID = {
    "touristappid": "游客模式 AppID",
    "": "空 AppID",
}


def read_appid() -> str:
    with open(CONFIG, encoding="utf-8") as f:
        return json.load(f).get("appid", "")


def validate(appid: str) -> str | None:
    """返回错误说明；合法则返回 None。"""
    if appid in INVALID:
        return f"{INVALID[appid]}（{appid}）不能上传，必须换成你自己的正式 AppID"
    if not appid.startswith("wx"):
        return "AppID 必须以 wx 开头"
    if not PATTERN.match(appid):
        return f"AppID 格式不对：应为 wx + 16 位小写字母/数字，共 18 位，你输入的是 {len(appid)} 位"
    return None


def write_appid(appid: str) -> None:
    with open(CONFIG, encoding="utf-8") as f:
        raw = f.read()
    data = json.loads(raw)
    data["appid"] = appid
    with open(CONFIG, "w", encoding="utf-8") as f:
        json.dump(data, f, ensure_ascii=False, indent=2)
        f.write("\n")


def where_to_find() -> None:
    print("""
去哪里找正式 AppID？
  1. 浏览器打开 https://mp.weixin.qq.com 扫码登录（用你注册小程序的那个微信）
  2. 左侧菜单 → 管理 → 开发管理 → 开发设置
  3. 页面顶部「开发者ID」里的 AppID(小程序ID)，形如 wx1a2b3c4d5e6f7890
  ⚠ 别复制 AppSecret，那个是密钥，不要发给任何人。

如果后台提示「未完成注册」或没有 AppID：
  说明小程序还没走完注册流程（个人/企业主体信息未提交），
  需要先在「首页」按引导完成注册，注册完才有 AppID。
""")


def main() -> int:
    print("=" * 62)
    print("  小程序 AppID 设置工具")
    print("=" * 62)
    current = read_appid()
    print(f"\n当前 project.config.json 中的 appid：{current}")
    err = validate(current)
    if err:
        print(f"  ✗ {err}")
    else:
        print("  ✓ 格式合法（若上传仍报测试号，说明这个号在后台没注册完成）")

    arg = sys.argv[1].strip() if len(sys.argv) > 1 else ""
    if not arg:
        where_to_find()
        try:
            arg = input("粘贴你的正式 AppID（直接回车退出）：").strip()
        except (EOFError, KeyboardInterrupt):
            print("\n已退出，未修改任何文件。")
            return 0

    if not arg:
        print("未输入，已退出。")
        return 0

    err = validate(arg)
    if err:
        print(f"\n✗ {err}")
        print("   请重新核对后再试。")
        return 1

    if arg == current:
        print("\n与当前值相同，无需修改。")
        return 0

    write_appid(arg)
    print(f"\n✓ 已写入：{arg}")
    print(f"  文件：{CONFIG}")
    print("""
接下来：
  1. 回到微信开发者工具，它会提示「AppID 已变更，是否重新打开」→ 点「确定」
     （若没提示，右上「详情 → 基本信息 → AppID」处点「修改」，确认已变成新号）
  2. 按 Ctrl+B 重新编译，看模拟器是否正常
  3. 右上角「上传」→ 版本号 1.0.0 → 备注「体验版」→ 上传
""")
    return 0


if __name__ == "__main__":
    sys.exit(main())
