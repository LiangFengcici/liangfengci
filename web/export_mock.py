"""导出演示数据 → 小程序 utils/mock-data.js（离线演示兜底的数据源）。"""
from __future__ import annotations

import json
import os
import sqlite3

HERE = os.path.dirname(os.path.abspath(__file__))
ROOT = os.path.dirname(HERE)
OUT = os.path.join(ROOT, "miniprogram", "utils", "mock-data.js")

conn = sqlite3.connect(os.path.join(HERE, "data", "dental.db"))
conn.row_factory = sqlite3.Row
c = conn.cursor()

catalog = []
for cat in c.execute("SELECT category_id, name, intro FROM treatment_category ORDER BY sort_no, category_id").fetchall():
    items = [dict(r) for r in c.execute(
        "SELECT catalog_id, category_id, name, intro, price_cents, duration_slots, requires_consent "
        "FROM treatment_catalog WHERE category_id=? ORDER BY catalog_id", (cat["category_id"],))]
    catalog.append({**dict(cat), "items": items})

clinics = [dict(r) for r in c.execute("SELECT clinic_id, name, address FROM clinic ORDER BY clinic_id")]

dentists = []
for i, d in enumerate(c.execute("SELECT dentist_id, name, title, intro FROM dentist WHERE status='在职' ORDER BY dentist_id").fetchall()):
    quals = [r["qual"] for r in c.execute(
        "SELECT cert_name AS qual FROM qualification WHERE dentist_id=?", (d["dentist_id"],))]
    dentists.append({
        "dentist_id": d["dentist_id"], "name": d["name"], "title": d["title"],
        "intro": d["intro"], "quals": quals,
        "clinic": clinics[i % len(clinics)]["name"],
    })

data = {"catalog": catalog, "clinics": clinics, "dentists": dentists}

js = "/**\n * 离线演示数据（由 web/export_mock.py 从真实数据库导出，勿手改）。\n" \
     " * 用途：真机/体验版在接口不可达时自动降级渲染，保证完整可看的界面。\n */\n" \
     "module.exports = " + json.dumps(data, ensure_ascii=False, indent=2) + "\n"

os.makedirs(os.path.dirname(OUT), exist_ok=True)
with open(OUT, "w", encoding="utf-8") as f:
    f.write(js)
print("written", OUT, len(js), "chars;", len(dentists), "dentists,", sum(len(x["items"]) for x in catalog), "items")
