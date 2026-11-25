"""种子数据：一套可直接演示的诊所运营现场。

覆盖：2 家诊所 / 5 名轮岗牙医 / 8 类 18 个项目 / 7 天排班与 30 分钟切片号源 /
患者与逐项过敏症 / 各种状态的就诊（待就诊、已完成、待支付、已结算、已取消）/
支付流水、退款、分期、会员、消毒包（含一个过期包）、复诊计划、日营收。
"""
from __future__ import annotations

import os
import sqlite3
from datetime import datetime, timedelta, date

from werkzeug.security import generate_password_hash

from db import DB_PATH, init_db, now, gen_no, TZ

PWD = "123456"


def connect():
    conn = sqlite3.connect(DB_PATH)
    conn.row_factory = sqlite3.Row
    conn.execute("PRAGMA foreign_keys = ON")
    return conn


def run():
    init_db(force=True)
    db = connect()
    ts = now()
    d0 = date.today()

    # ---------------- 诊所与牙椅 ----------------
    clinics = [("中山路旗舰诊所", "ZS", "中山路 88 号 3 层", "0411-8888 1001"),
               ("高新园区诊所", "GX", "高新园区软件园 12 号楼 2 层", "0411-8888 1002")]
    for name, code, addr, tel in clinics:
        db.execute("INSERT INTO clinic(name, code, address, phone) VALUES (?,?,?,?)",
                   (name, code, addr, tel))
    chairs = {1: ["1 号椅", "2 号椅", "3 号椅"], 2: ["A 椅", "B 椅"]}
    for cid, names in chairs.items():
        for i, n in enumerate(names, 1):
            db.execute("INSERT INTO chair(clinic_id, name, room) VALUES (?,?,?)",
                       (cid, n, f"{i} 诊室"))

    # ---------------- 牙医与资质 ----------------
    dentists = [
        ("张明远", "主任医师", "擅长种植与复杂根管，口腔种植资质 12 年"),
        ("李慧", "副主任医师", "正畸专科医师，隐适美认证"),
        ("王振宇", "主治医师", "显微根管与美学充填"),
        ("陈雪", "主治医师", "全瓷修复与贴面美学"),
        ("刘博", "医师", "儿童牙科与预防保健"),
    ]
    for n, t, intro in dentists:
        db.execute("INSERT INTO dentist(name, title, phone, intro) VALUES (?,?,?,?)",
                   (n, t, "1380000" + str(len(n)) + "位", intro))
    quals = [(1, "口腔执业医师", "D1101", "2030-12-31"), (1, "口腔种植资质", "IM1101", "2029-12-31"),
             (1, "口腔颌面外科", "OS1101", "2031-12-31"),
             (2, "口腔执业医师", "D1102", "2032-06-30"), (2, "正畸专科资质", "OR1102", "2030-06-30"),
             (3, "口腔执业医师", "D1103", "2031-03-31"),
             (4, "口腔执业医师", "D1104", "2033-01-31"), (4, "修复工艺资质", "PR1104", "2029-09-30"),
             (5, "口腔执业医师", "D1105", "2034-05-31")]
    for did, cert, no, valid in quals:
        db.execute("INSERT INTO qualification(dentist_id, cert_name, cert_no, valid_until) VALUES (?,?,?,?)",
                   (did, cert, no, valid))

    # ---------------- 项目分类与目录 ----------------
    cats = [("口腔检查", "初诊检查、影像检查"),
            ("洁治", "超声波洁治与牙周维护"),
            ("补牙", "树脂充填与玻璃离子充填"),
            ("根管治疗", "显微根管治疗"),
            ("修复", "全瓷冠、贴面与拔牙"),
            ("种植", "种植体植入与种植冠修复"),
            ("正畸", "固定矫正与隐形矫正"),
            ("儿童牙科", "窝沟封闭、涂氟与儿童充填")]
    for i, (n, intro) in enumerate(cats, 1):
        db.execute("INSERT INTO treatment_category(name, sort_no, intro) VALUES (?,?,?)", (n, i, intro))

    # (category_id, 名称, 单位, 价格分, 时长切片, 需同意书, 复诊周, 介绍)
    catalog = [
        (1, "初诊口腔检查", "次", 8000, 1, 0, 0, "含口腔全面检查、治疗计划制定"),
        (1, "口腔全景片", "次", 12000, 1, 0, 0, "数字全景 X 光片"),
        (2, "超声波洁治", "次", 28000, 1, 0, 24, "全口超声洁治＋抛光"),
        (2, "龈下刮治（单象限）", "象限", 40000, 1, 0, 12, "牙周基础治疗"),
        (3, "树脂充填（单面）", "颗", 38000, 1, 0, 0, "进口纳米树脂，色泽匹配"),
        (3, "玻璃离子充填", "颗", 22000, 1, 0, 0, "适用于乳牙与颈部缺损"),
        (4, "根管治疗（前牙）", "颗", 90000, 2, 1, 0, "显微根管，含充填"),
        (4, "根管治疗（磨牙）", "颗", 150000, 2, 1, 0, "三根管以上，含热牙胶充填"),
        (5, "全瓷冠修复", "颗", 280000, 2, 0, 0, "二氧化锆全瓷冠"),
        (5, "瓷贴面", "颗", 320000, 2, 0, 0, "超薄美学贴面"),
        (5, "拔牙（简单）", "颗", 30000, 1, 1, 0, "含局部麻醉"),
        (5, "拔牙（阻生智齿）", "颗", 120000, 2, 1, 0, "微创拔除，含缝合"),
        (6, "种植体植入", "颗", 980000, 3, 1, 52, "含种植体与基台"),
        (6, "种植冠修复", "颗", 360000, 2, 0, 26, "种植上部结构修复"),
        (7, "正畸初戴（金属自锁）", "例", 880000, 2, 1, 4, "全口托槽粘接与弓丝初戴"),
        (7, "正畸复诊加力", "次", 30000, 1, 0, 6, "更换弓丝与加力调整"),
        (8, "窝沟封闭", "颗", 20000, 1, 0, 12, "六龄齿防龋"),
        (8, "全口涂氟", "次", 18000, 1, 0, 26, "儿童防龋涂氟"),
    ]
    for c in catalog:
        db.execute("""INSERT INTO treatment_catalog(category_id, name, unit, price_cents,
                        duration_slots, requires_consent, recall_weeks, intro)
                      VALUES (?,?,?,?,?,?,?,?)""", c)

    # 医生技能（资质覆盖规则的数据基础）
    skills = {
        1: ["初诊口腔检查", "口腔全景片", "根管治疗（磨牙）", "种植体植入", "种植冠修复", "拔牙（阻生智齿）", "全瓷冠修复", "超声波洁治"],
        2: ["初诊口腔检查", "正畸初戴（金属自锁）", "正畸复诊加力", "超声波洁治", "窝沟封闭"],
        3: ["初诊口腔检查", "树脂充填（单面）", "根管治疗（前牙）", "根管治疗（磨牙）", "超声波洁治", "拔牙（简单）"],
        4: ["初诊口腔检查", "全瓷冠修复", "瓷贴面", "树脂充填（单面）", "超声波洁治"],
        5: ["初诊口腔检查", "窝沟封闭", "全口涂氟", "超声波洁治", "玻璃离子充填", "树脂充填（单面）"],
    }
    for did, names in skills.items():
        for n in names:
            row = db.execute("SELECT catalog_id FROM treatment_catalog WHERE name=?", (n,)).fetchone()
            db.execute("INSERT INTO dentist_skill(dentist_id, catalog_id, level) VALUES (?,?, '熟练')",
                       (did, row["catalog_id"]))

    # 门店授权与门店差异价（4.9）
    all_cat = db.execute("SELECT catalog_id, price_cents, category_id FROM treatment_catalog").fetchall()
    for cid in (1, 2):
        for c in all_cat:
            authorized = 0 if (cid == 2 and c["category_id"] == 6) else 1   # 高新店无种植授权
            db.execute("INSERT INTO clinic_quota(clinic_id, catalog_id, authorized, monthly_quota) VALUES (?,?,?,0)",
                       (cid, c["catalog_id"], authorized))
            price = c["price_cents"]
            if cid == 2:
                price = int(price * 0.95)      # 高新店 95 折差异价
            db.execute("INSERT INTO clinic_price(clinic_id, catalog_id, price_cents) VALUES (?,?,?)",
                       (cid, c["catalog_id"], price))

    # ---------------- 员工账号 ----------------
    accounts = [
        ("front1", "前台", "前台接待 · 赵蕾", 1, None),
        ("doc1", "医生", "张明远 · 主任医师", 1, 1),
        ("doc2", "医生", "王振宇 · 主治医师", 1, 3),
        ("fin1", "财务", "财务 · 孙会计", 1, None),
        ("mgr1", "诊所经理", "诊所经理 · 郑晓峰", 1, None),
        ("ops1", "运营专员", "总部运营 · 总部运营组", None, None),
    ]
    for username, role, display, cid, did in accounts:
        db.execute("""INSERT INTO staff_account(username, password_hash, display_name, role,
                        clinic_id, dentist_id, created_at) VALUES (?,?,?,?,?,?,?)""",
                   (username, generate_password_hash(PWD), display, role, cid, did, ts))

    # 轮岗任职
    for did in range(1, 6):
        db.execute("INSERT INTO duty(dentist_id, clinic_id, start_date, end_date, status) VALUES (?,?,?,?, '在岗')",
                   (did, 1 if did % 2 else 2, (d0 - timedelta(days=30)).isoformat(),
                    (d0 + timedelta(days=180)).isoformat()))
        db.execute("INSERT INTO duty(dentist_id, clinic_id, start_date, end_date, status) VALUES (?,?,?,?, '在岗')",
                   (did, 2 if did % 2 else 1, (d0 - timedelta(days=30)).isoformat(),
                    (d0 + timedelta(days=180)).isoformat()))

    # ---------------- 排班与号源（今天起 7 天） ----------------
    plan = {1: [(1, 1, "09:00", "12:00"), (1, 1, "13:30", "17:30")],
            2: [(2, 2, "09:00", "12:00"), (2, 2, "13:30", "17:00")],
            3: [(1, 3, "09:00", "12:00"), (2, 3, "13:30", "17:30")],
            4: [(2, 1, "09:00", "12:30"), (1, 1, "13:30", "17:00")],
            5: [(2, 2, "13:30", "17:30")]}
    for day_off in range(0, 7):
        day = (d0 + timedelta(days=day_off)).isoformat()
        for did, entries in plan.items():
            if did == 5 and day_off % 2 == 0:
                continue
            for cid, chair_id, st, et in entries:
                h1, m1 = map(int, st.split(":"))
                h2, m2 = map(int, et.split(":"))
                count = ((h2 * 60 + m2) - (h1 * 60 + m1)) // 30
                sid = db.execute("""INSERT INTO shift(duty_id, dentist_id, clinic_id, chair_id,
                        shift_date, start_time, end_time, slot_count, ampm, status, created_by, created_at)
                        VALUES (1,?,?,?,?,?,?,?,?, '已发布', 'seed', ?)""",
                                 (did, cid, chair_id, day, st, et, count,
                                  "上午" if h1 < 12 else "下午", ts)).lastrowid
                h, m = h1, m1
                for i in range(count):
                    ss = f"{h:02d}:{m:02d}"
                    m += 30
                    if m >= 60:
                        h += 1
                        m -= 60
                    ee = f"{h:02d}:{m:02d}"
                    db.execute("INSERT INTO slot(shift_id, seq, start_time, end_time, status) VALUES (?,?,?,?, '空闲')",
                               (sid, i + 1, ss, ee))

    # ---------------- 患者与过敏症 ----------------
    patients = [
        ("周若彤", "女", "1994-03-12", "13900001111", "小程序", ["青霉素"], ["高血压"], 0),
        ("赵启明", "男", "1987-08-02", "13900002222", "转介绍", ["金属"], [], 1),
        ("孙一诺", "女", "2015-06-21", "13900003333", "到店", [], [], 0),
        ("吴敏", "女", "1990-11-09", "13900004444", "小程序", ["乳胶"], ["糖尿病"], 0),
        ("何俊", "男", "1979-01-30", "13900005555", "到店", ["磺胺"], [], 2),
    ]
    for i, (name, g, birth, phone, src, allergies, hist, noshow) in enumerate(patients, 1):
        pid = db.execute("""INSERT INTO patient(name, gender, birth_date, phone, source, openid,
                              real_name_ok, no_show_cnt, created_at)
                            VALUES (?,?,?,?,?,?,1,?,?)""",
                         (name, g, birth, phone, src, f"mock-openid-{i}", noshow, ts)).lastrowid
        for a in allergies:
            db.execute("INSERT INTO allergy(patient_id, allergen, note, created_at) VALUES (?,?,?,?)",
                       (pid, a, "既往用药后出现皮疹", ts))
        for h in hist:
            db.execute("INSERT INTO medical_history(patient_id, item, note, recorded_at) VALUES (?,?,?,?)",
                       (pid, h, "需术前评估", ts))
        db.execute("INSERT INTO patient_contact(patient_id, name, relation, phone) VALUES (?,?,?,?)",
                   (pid, name[0] + "先生/女士", "本人", phone))
        db.execute("INSERT INTO member(patient_id, level, points, balance_cents, joined_at) VALUES (?,?,?,?,?)",
                   (pid, "金卡" if i % 2 == 0 else "普通", 120 * i, 0, ts))
        db.execute("INSERT INTO prepaid_card(patient_id, card_no, balance_cents, status) VALUES (?,?,?, '正常')",
                   (pid, f"PC{i:04d}", 50000 if i == 2 else 0))

    db.execute("INSERT INTO coupon(member_id, code, title, amount_cents, scope, status, expire_at) VALUES (1,'CPN88','洁治立减 88 元',8800,'洁治','未使用',?)",
               ((d0 + timedelta(days=60)).isoformat(),))
    db.execute("INSERT INTO coupon(member_id, code, title, amount_cents, scope, status, expire_at) VALUES (2,'CPN200','修复类满 2000 减 200',20000,'修复','未使用',?)",
               ((d0 + timedelta(days=30)).isoformat(),))

    # ---------------- 套餐 ----------------
    for name, kind, price, total in [("洁治年卡 3 次", "次卡", 72000, 84000),
                                     ("儿童防龋套餐", "套餐", 32000, 38000),
                                     ("正畸全周期（含保持器）", "套餐", 1080000, 1180000)]:
        db.execute("INSERT INTO price_package(name, kind, price_cents, catalog_total_cents) VALUES (?,?,?,?)",
                   (name, kind, price, total))

    # ---------------- 消毒包 ----------------
    for cid in (1, 2):
        for i in range(1, 4):
            st_at = (datetime.now(TZ) - timedelta(days=1)).replace(microsecond=0).isoformat()
            db.execute("""INSERT INTO sterilization_pack(clinic_id, pack_no, batch_no, sterilized_at,
                            expire_at, status) VALUES (?,?,?,?,?, '可用')""",
                       (cid, f"PK{cid}0{i}", f"B{(d0 - timedelta(days=1)).strftime('%m%d')}{i}",
                        st_at, (d0 + timedelta(days=6)).isoformat()))
    # 一个过期包（验收 V9）
    db.execute("""INSERT INTO sterilization_pack(clinic_id, pack_no, batch_no, sterilized_at,
                    expire_at, status) VALUES (1,'PK019','B0920-9',?,?, '可用')""",
               ((datetime.now(TZ) - timedelta(days=20)).replace(microsecond=0).isoformat(),
                (d0 - timedelta(days=13)).isoformat()))

    # ---------------- 就诊现场 ----------------
    def slot_ids(day, did, start, n):
        rows = db.execute("""SELECT s.slot_id FROM slot s JOIN shift sh ON sh.shift_id=s.shift_id
                             WHERE sh.shift_date=? AND sh.dentist_id=? AND s.start_time>=?
                             ORDER BY s.seq LIMIT ?""", (day, did, start, n)).fetchall()
        return [r["slot_id"] for r in rows]

    def add_visit(pid, did, cid, day, start, end, n, status, source="到店", arrived=0,
                  cancel_type=None, note=""):
        vid = db.execute("""INSERT INTO visit(patient_id, dentist_id, clinic_id, chair_id, visit_date,
                    start_time, end_time, slots, source, status, cancel_type, special_note,
                    is_arrived, created_at)
                    VALUES (?,?,?, (SELECT chair_id FROM shift WHERE shift_date=? AND dentist_id=? LIMIT 1),
                    ?,?,?,?,?,?,?,?,?,?)""",
                         (pid, did, cid, day, did, day, start, end, n, source, status,
                          cancel_type, note, arrived, ts)).lastrowid
        for sid in slot_ids(day, did, start, n):
            db.execute("UPDATE slot SET status='已占', visit_id=? WHERE slot_id=?", (vid, sid))
        return vid

    today = d0.isoformat()
    tomorrow = (d0 + timedelta(days=1)).isoformat()

    # 今日待就诊：周若彤 → 张明远 09:30 根管（需同意书，已付定金）
    v1 = add_visit(1, 1, 1, today, "09:30", "10:30", 2, "待就诊", "在线", 1,
                   note="右下后牙夜间痛，既往青霉素过敏")
    db.execute("""INSERT INTO online_booking(booking_no, patient_id, catalog_id, clinic_id, visit_id,
                    want_date, want_time, status, created_at, expire_at)
                  VALUES (?,1,8,1,?,?,?, '已确认', ?, ?)""",
               (gen_no("BK"), v1, today, "09:30", ts, ts))
    db.execute("INSERT INTO visit_treatment(visit_id, catalog_id, name_snapshot, qty, unit_price_cents, amount_cents, created_at) VALUES (?,8,'根管治疗（磨牙）',1,150000,150000,?)", (v1, ts))
    inv1 = db.execute("""INSERT INTO invoice(invoice_no, visit_id, total_cents, paid_cents, deposit_cents,
                          status, kind, created_at) VALUES (?,?,1500000,150000,150000,'待支付','结算单',?)""",
                      (gen_no("INV"), v1, ts)).lastrowid
    db.execute("""INSERT INTO payment_transaction(pay_no, invoice_id, amount_cents, method, status,
                    third_party_no, idem_key, operator, created_at, finished_at)
                  VALUES (?,?,150000,'微信支付','成功',?,?, '患者', ?, ?)""",
               (gen_no("DEP"), inv1, "WXDEMO001", "seed-dep-1", ts, ts))
    db.execute("""INSERT INTO invoice_line(invoice_id, name, qty, unit_price_cents, amount_cents, kind)
                  VALUES (?, '根管治疗（磨牙）',1,150000,150000,'治疗')""", (inv1,))

    # 今日待就诊（已到店）：赵启明 → 王振宇 10:00 补牙
    v2 = add_visit(2, 3, 1, today, "10:00", "10:30", 1, "待就诊", "到店", 1, note="左上后牙充填物脱落")
    # 今日待就诊：孙一诺 → 刘博 14:00 涂氟
    v3 = add_visit(3, 5, 2, today, "14:00", "14:30", 1, "待就诊", "到店", 0)
    # 已完成待结算：吴敏 → 陈雪 昨日 全瓷冠
    v4 = add_visit(4, 4, 2, (d0 - timedelta(days=1)).isoformat(), "09:00", "10:00", 2, "已完成", "在线", 1)
    db.execute("INSERT INTO visit_treatment(visit_id, catalog_id, name_snapshot, qty, unit_price_cents, amount_cents, created_at) VALUES (?,9,'全瓷冠修复',1,266000,266000,?)", (v4, ts))
    db.execute("INSERT INTO visit_treatment(visit_id, catalog_id, name_snapshot, qty, unit_price_cents, amount_cents, created_at) VALUES (?,3,'超声波洁治',1,26600,26600,?)", (v4, ts))
    rec4 = db.execute("INSERT INTO treatment_record(visit_id, chief_complaint, exam_note, diagnosis, created_by, created_at) VALUES (?,?,?,?, '陈雪', ?)",
                      (v4, "上前牙变色要求修复", "26 牙体缺损，牙髓活力正常", "26 牙体缺损", ts)).lastrowid
    db.execute("INSERT INTO tooth_condition(record_id, fdi, status, recorded_at) VALUES (?, '26', '龋', ?)", (rec4, ts))

    # 已结算：何俊 → 张明远 前日 种植（含同意书与影像）
    v5 = add_visit(5, 1, 1, (d0 - timedelta(days=2)).isoformat(), "09:00", "10:30", 3, "已结算", "到店", 1)
    db.execute("INSERT INTO visit_treatment(visit_id, catalog_id, name_snapshot, qty, unit_price_cents, amount_cents, created_at) VALUES (?,13,'种植体植入',1,980000,980000,?)", (v5, ts))
    rec5 = db.execute("INSERT INTO treatment_record(visit_id, chief_complaint, exam_note, diagnosis, created_by, created_at, locked) VALUES (?,?,?,?, '张明远', ?,1)",
                      (v5, "36 缺失要求种植", "36 缺牙区骨量充足", "36 牙列缺损", ts)).lastrowid
    db.execute("INSERT INTO tooth_condition(record_id, fdi, status, recorded_at) VALUES (?, '36', '缺失', ?)", (rec5, ts))
    db.execute("INSERT INTO consent(record_id, template, version, signed_by, signature, signed_at) VALUES (?, '种植手术知情同意书','V2.1','何俊','电子签名',?)", (rec5, ts))
    db.execute("INSERT INTO imaging(record_id, fdi, type, storage_path, finding, taken_at) VALUES (?, '36','CBCT','/static/img/xray/36_CBCT.svg','36 区骨高度 12.4mm，可用',?)", (rec5, ts))
    inv5 = db.execute("""INSERT INTO invoice(invoice_no, visit_id, total_cents, paid_cents, deposit_cents,
                          status, kind, is_invoiced, invoice_title, created_at, settled_at)
                         VALUES (?,?,980000,980000,0,'已结算','结算单',1,'何俊',?,?)""",
                      (gen_no("INV"), v5, ts, ts)).lastrowid
    db.execute("INSERT INTO invoice_line(invoice_id, name, qty, unit_price_cents, amount_cents, kind) VALUES (?, '种植体植入',1,980000,980000,'治疗')", (inv5,))
    db.execute("""INSERT INTO payment_transaction(pay_no, invoice_id, amount_cents, method, status,
                    third_party_no, idem_key, operator, created_at, finished_at)
                  VALUES (?,?,980000,'微信支付','成功',?,?, '患者', ?, ?)""",
               (gen_no("PAY"), inv5, "WXDEMO002", "seed-pay-2", ts, ts))
    for kind in ("收款归属", "业绩归属"):
        db.execute("INSERT INTO revenue_share(invoice_id, clinic_id, dentist_id, kind, amount_cents, created_at) VALUES (?,1,1,?,980000,?)",
                   (inv5, kind, ts))
    db.execute("UPDATE member SET points=points+9800 WHERE patient_id=5")

    # 已取消（主动取消）
    v6 = add_visit(3, 5, 2, (d0 - timedelta(days=1)).isoformat(), "15:00", "15:30", 1, "已取消", "在线", 0, "主动取消")

    # 待支付：昨日 王振宇 完成但未收款
    v7 = add_visit(2, 3, 1, (d0 - timedelta(days=1)).isoformat(), "14:00", "14:30", 1, "待支付", "到店", 1)
    db.execute("INSERT INTO visit_treatment(visit_id, catalog_id, name_snapshot, qty, unit_price_cents, amount_cents, created_at) VALUES (?,5,'树脂充填（单面）',2,38000,76000,?)", (v7, ts))
    inv7 = db.execute("""INSERT INTO invoice(invoice_no, visit_id, total_cents, paid_cents, deposit_cents,
                          status, kind, created_at) VALUES (?,?,76000,0,0,'待支付','结算单',?)""",
                      (gen_no("INV"), v7, ts)).lastrowid
    db.execute("INSERT INTO invoice_line(invoice_id, name, qty, unit_price_cents, amount_cents, kind) VALUES (?, '树脂充填（单面）',2,38000,76000,'治疗')", (inv7,))

    # 病历示例（牙位图、牙周、处方、影像）——给 v2 一份历史记录用于演示
    rec2 = db.execute("INSERT INTO treatment_record(visit_id, chief_complaint, exam_note, diagnosis, created_by, created_at) VALUES (?,?,?,?, '王振宇', ?)",
                      (v2, "左上后牙冷热敏感", "26 合面龋坏，探（+）", "26 中龋", ts)).lastrowid
    t26 = db.execute("INSERT INTO tooth_condition(record_id, fdi, status, note, recorded_at) VALUES (?, '26','龋','合面深龋', ?)", (rec2, ts)).lastrowid
    for s in ("咬合", "近中"):
        db.execute("INSERT INTO tooth_surface(tooth_id, surface) VALUES (?,?)", (t26, s))
    db.execute("""INSERT INTO perio_exam(tooth_id, pd1,pd2,pd3,pd4,pd5,pd6, cal, mobility, bleeding)
                  VALUES (?,3,4,3,3,5,3,1,0,1)""", (t26,))
    db.execute("INSERT INTO treatment_plan(visit_id, stage, status, note, created_at) VALUES (?, '一期','进行','树脂充填＋牙周基础治疗',?)", (v2, ts))
    db.execute("INSERT INTO plan_item(plan_id, fdi, catalog_id, status, note, auto_flag) VALUES (1,'26',5,'进行','26 合面树脂充填',0)")
    db.execute("INSERT INTO plan_item(plan_id, fdi, catalog_id, status, note, auto_flag) VALUES (1,'26',4,'计划','PD≥4 自动生成牙周治疗',1)")
    db.execute("INSERT INTO prescription(record_id, doctor_id, status, created_at) VALUES (?,3,'已开立',?)", (rec2, ts))
    db.execute("INSERT INTO prescription_item(rx_id, drug, dose, usage, is_narcotic, double_check_by) VALUES (1,'阿莫西林胶囊','0.5g tid×3 天','口服',0,'王振宇')")
    db.execute("INSERT INTO imaging(record_id, fdi, type, storage_path, finding, taken_at) VALUES (?, '26','根尖片','/static/img/xray/26_根尖片.svg','26 近中邻面低密度影，未及髓',?)", (rec2, ts))

    # 历史就诊：周若彤 10 天前洁治（患者端「报告与影像」「历史病历」的演示数据）
    v9 = add_visit(1, 3, 1, (d0 - timedelta(days=10)).isoformat(), "10:00", "10:30", 1,
                   "已结算", "到店", 1, note="牙龈出血，要求洁治")
    db.execute("INSERT INTO visit_treatment(visit_id, catalog_id, name_snapshot, qty, unit_price_cents, amount_cents, created_at) VALUES (?,3,'超声波洁治',1,28000,28000,?)", (v9, ts))
    rec9 = db.execute("""INSERT INTO treatment_record(visit_id, chief_complaint, exam_note, diagnosis,
                            created_by, created_at, locked) VALUES (?,?,?,?, '王振宇', ?, 1)""",
                      (v9, "刷牙出血两周", "全口牙石 I°，16 龈缘红肿，PD≤3mm",
                       "慢性龈炎", ts)).lastrowid
    db.execute("INSERT INTO tooth_condition(record_id, fdi, status, note, recorded_at) VALUES (?, '16','正常','龈缘红肿，洁治后好转', ?)", (rec9, ts))
    db.execute("INSERT INTO imaging(record_id, fdi, type, storage_path, finding, taken_at) VALUES (?, '16','根尖片','/static/img/xray/16_根尖片.svg','16 根尖周未见低密度影',?)", (rec9, ts))
    inv9 = db.execute("""INSERT INTO invoice(invoice_no, visit_id, total_cents, paid_cents, deposit_cents,
                          status, kind, created_at, settled_at)
                         VALUES (?,?,28000,28000,0,'已结算','结算单',?,?)""",
                      (gen_no("INV"), v9, ts, ts)).lastrowid
    db.execute("INSERT INTO invoice_line(invoice_id, name, qty, unit_price_cents, amount_cents, kind) VALUES (?, '超声波洁治',1,28000,28000,'治疗')", (inv9,))
    db.execute("""INSERT INTO payment_transaction(pay_no, invoice_id, amount_cents, method, status,
                    third_party_no, idem_key, operator, created_at, finished_at)
                  VALUES (?,?,28000,'微信支付','成功',?,?, '患者', ?, ?)""",
               (gen_no("PAY"), inv9, "WXDEMO003", "seed-pay-3", ts, ts))
    db.execute("UPDATE member SET points=points+280 WHERE patient_id=1")

    # 复诊计划：明日到期（定时任务会推送）
    db.execute("""INSERT INTO recall_plan(visit_id, patient_id, catalog_id, due_date, status)
                  VALUES (?,1,16,?, '待提醒')""", (v1, tomorrow))
    db.execute("""INSERT INTO recall_plan(visit_id, patient_id, catalog_id, due_date, status)
                  VALUES (?,4,9,?, '待提醒')""", (v4, (d0 + timedelta(days=3)).isoformat()))

    # 候补登记
    db.execute("""INSERT INTO waitlist(patient_id, shift_id, catalog_id, status, created_at)
                  VALUES (3, 1, 17, '候补中', ?)""", (ts,))

    # 器械追溯
    db.execute("INSERT INTO pack_trace(pack_id, visit_id, used_at, operator) VALUES (1,?,?, '前台接待 · 赵蕾')", (v5, ts))

    # 分期计划（吴敏 正畸）
    plan_id = db.execute("""INSERT INTO installment_plan(plan_no, patient_id, visit_id, mode, total_cents,
                              down_cents, periods, per_cents, status, signed, created_at, expire_at)
                            VALUES (?,4,NULL,'分期',880000,264000,6,102666,'已生效',1,?,?)""",
                         (gen_no("IP"), ts, ts)).lastrowid
    db.execute("INSERT INTO installment(plan_id, seq, due_date, amount_cents, status) VALUES (?,0,?,264000,'已付')",
               (plan_id, today))
    for i in range(1, 7):
        db.execute("INSERT INTO installment(plan_id, seq, due_date, amount_cents, status) VALUES (?,?,?,?,?)",
                   (plan_id, i, (d0 + timedelta(days=30 * i)).isoformat(), 102666,
                    "已付" if i <= 2 else "待付"))

    # 病例成本与运营费用
    db.execute("INSERT INTO case_cost(visit_id, item_name, qty, batch_no, unit_cost_cents, amount_cents, created_at) VALUES (?, '种植体（士卓曼 BLT）',1,'IMP-2409-11',320000,320000,?)", (v5, ts))
    db.execute("INSERT INTO case_cost(visit_id, item_name, qty, batch_no, unit_cost_cents, amount_cents, created_at) VALUES (?, '全瓷冠（二氧化锆）',1,'ZR-2410-02',68000,68000,?)", (v4, ts))
    for m_off in (0, 1, 2):
        mm = (d0.replace(day=1) - timedelta(days=30 * m_off)).strftime("%Y-%m")
        db.execute("INSERT INTO expense(clinic_id, month, item, amount_cents) VALUES (1,?, '房租', 1800000)", (mm,))
        db.execute("INSERT INTO expense(clinic_id, month, item, amount_cents) VALUES (1,?, '人力', 4200000)", (mm,))
        db.execute("INSERT INTO expense(clinic_id, month, item, amount_cents) VALUES (2,?, '房租', 1200000)", (mm,))

    # 价格变更历史
    db.execute("""INSERT INTO price_history(catalog_id, old_cents, new_cents, changed_by, changed_at, reason)
                  VALUES (9, 260000, 280000, '总部运营', ?, '材料成本上调')""", (ts,))

    # 通知记录
    db.execute("""INSERT INTO notification_log(visit_id, patient_id, template, content, channel, status, created_at)
                  VALUES (?,1,'预约确认','您已预约今日 09:30 中山路旗舰诊所 · 张明远','服务号订阅消息','已发送',?)""",
               (v1, ts))

    # 昨日日营收
    y = (d0 - timedelta(days=1)).isoformat()
    db.execute("""INSERT INTO daily_revenue(clinic_id, rev_date, receivable_cents, received_cents,
                    refund_cents, diff_cents, created_at) VALUES (1,?,136000,136000,0,0,?)""", (y, ts))
    db.execute("""INSERT INTO daily_revenue(clinic_id, rev_date, receivable_cents, received_cents,
                    refund_cents, diff_cents, created_at) VALUES (2,?,292600,292600,0,0,?)""", (y, ts))

    db.commit()
    db.close()
    print("seed done:", DB_PATH)


if __name__ == "__main__":
    run()
