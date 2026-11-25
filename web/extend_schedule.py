# -*- coding: utf-8 -*-
"""续排班脚本：给未来 N 天补充班次与号源（幂等，重复运行不会产生重复班次）。

用法：
    python extend_schedule.py            # 默认续 60 天
    python extend_schedule.py 90         # 自定义天数

既可以在本地（data/dental.db）运行，也可以在云端运行，
两者使用的表结构完全一致。
"""
from __future__ import annotations

import datetime
import os
import sqlite3
import sys

DB = os.path.join(os.path.dirname(os.path.abspath(__file__)), "data", "dental.db")

# 与 seed.py 相同的排班模板：医生号 → (诊所, 牙椅, 开始, 结束)
PLAN = {
    1: [(1, 1, "09:00", "12:00"), (1, 1, "13:30", "17:30")],
    2: [(2, 2, "09:00", "12:00"), (2, 2, "13:30", "17:00")],
    3: [(1, 3, "09:00", "12:00"), (2, 3, "13:30", "17:30")],
    4: [(2, 1, "09:00", "12:30"), (1, 1, "13:30", "17:00")],
    5: [(2, 2, "13:30", "17:30")],
}


def main(days: int) -> None:
    conn = sqlite3.connect(DB)
    conn.row_factory = sqlite3.Row
    today = datetime.date.today()

    # 起点：现有班次的最后一天的下一天（保证不回头补旧数据）
    row = conn.execute("SELECT MAX(shift_date) AS m FROM shift").fetchone()
    start = max(datetime.date.fromisoformat(row["m"]) + datetime.timedelta(days=1), today) if row["m"] else today
    end = today + datetime.timedelta(days=days)

    shifts, slots = 0, 0
    day_off = start.toordinal()  # 用于医生 5 隔天休
    d = start
    while d <= end:
        day = d.isoformat()
        for did, entries in PLAN.items():
            if did == 5 and day_off % 2 == 0:
                continue
            for cid, chair_id, st, et in entries:
                # 幂等：同医生同日同诊所同时段已有班次则跳过
                dup = conn.execute(
                    """SELECT 1 FROM shift WHERE dentist_id=? AND shift_date=?
                       AND clinic_id=? AND start_time=?""",
                    (did, day, cid, st)).fetchone()
                if dup:
                    continue
                h1, m1 = map(int, st.split(":"))
                h2, m2 = map(int, et.split(":"))
                count = ((h2 * 60 + m2) - (h1 * 60 + m1)) // 30
                cur = conn.execute(
                    """INSERT INTO shift(duty_id, dentist_id, clinic_id, chair_id,
                       shift_date, start_time, end_time, slot_count, ampm, status, created_by, created_at)
                       VALUES (1,?,?,?,?,?,?,?,?,'已发布','extend',datetime('now','localtime'))""",
                    (did, cid, chair_id, day, st, et, count,
                     "上午" if h1 < 12 else "下午"))
                shifts += 1
                h, m = h1, m1
                for i in range(count):
                    ss = f"{h:02d}:{m:02d}"
                    m += 30
                    if m >= 60:
                        h += 1
                        m -= 60
                    ee = f"{h:02d}:{m:02d}"
                    conn.execute(
                        "INSERT INTO slot(shift_id, seq, start_time, end_time, status) VALUES (?,?,?,?, '空闲')",
                        (cur.lastrowid, i + 1, ss, ee))
                    slots += 1
        d += datetime.timedelta(days=1)
        day_off += 1

    conn.commit()
    row = conn.execute("SELECT MAX(shift_date) FROM shift").fetchone()
    print(f"[ok] 新增班次 {shifts} 个、号源 {slots} 片")
    print(f"[ok] 排班已覆盖至 {row[0]}（{days} 天后）")
    conn.close()


if __name__ == "__main__":
    n = int(sys.argv[1]) if len(sys.argv) > 1 else 60
    main(n)
