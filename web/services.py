"""业务服务层：把 4.4—4.9 与 5.2 的规则固化成代码。

原则：所有业务规则以业务层为准（4.3），界面只转发校验结果；
任何拒绝都抛出 BusinessError(status, message)，status 复用 4.12 的错误码分段。
"""
from __future__ import annotations

import json
from datetime import datetime, date, timedelta

from db import execute, query, now, today, gen_no, audit, TZ

# ---------------------------------------------------------------------------
# 错误码（4.12 接口通用约定）
# ---------------------------------------------------------------------------
ERR_BAD_REQUEST = 400
ERR_UNAUTHORIZED = 401
ERR_FORBIDDEN = 403
ERR_NOT_FOUND = 404
ERR_CONFLICT = 409          # 状态冲突，如重复预约
ERR_BUSINESS = 422          # 业务规则拒绝：过敏拦截、余量不足
ERR_PRECONDITION = 428      # 前置条件未满足：知情同意书未签署


class BusinessError(Exception):
    def __init__(self, message: str, status: int = ERR_BUSINESS, data=None):
        super().__init__(message)
        self.message = message
        self.status = status
        self.data = data


# ---------------------------------------------------------------------------
# 权限（4.12 权限矩阵）
# ---------------------------------------------------------------------------
ROLE_CLINIC = {"前台": "前台接待", "医生": "牙医", "财务": "财务",
               "诊所经理": "诊所经理", "运营专员": "运营专员"}

DISCOUNT_LIMITS = {"前台": 0.05, "财务": 0.05, "诊所经理": 0.20, "运营专员": 0.0}


def require_role(*roles):
    from flask import session
    role = session.get("role")
    if role not in roles:
        raise BusinessError("当前角色无权执行该操作（4.12 最小权限）", ERR_FORBIDDEN)


# ---------------------------------------------------------------------------
# 过敏知识库（5.2 之(2)）
# ---------------------------------------------------------------------------
DRUG_ALLERGEN = {
    "阿莫西林": ["青霉素"],
    "青霉素": ["青霉素"],
    "氨苄西林": ["青霉素"],
    "哌拉西林": ["青霉素"],
    "头孢克洛": ["头孢", "青霉素"],
    "头孢呋辛": ["头孢", "青霉素"],
    "甲硝唑": ["硝基咪唑"],
    "利多卡因": ["麻醉剂"],
    "阿替卡因": ["麻醉剂"],
    "普鲁卡因": ["麻醉剂"],
    "布洛芬": ["非甾体"],
    "阿司匹林": ["非甾体"],
    "对乙酰氨基酚": ["非甾体"],
    "树脂": ["树脂"],
    "复合树脂": ["树脂"],
    "钴铬合金": ["金属"],
    "镍铬合金": ["金属"],
    "钛合金": ["金属"],
}

CROSS_ALLERGY = {"青霉素": ["头孢"], "头孢": ["青霉素"]}


def patient_allergens(patient_id: int) -> list[str]:
    rows = query("SELECT allergen FROM allergy WHERE patient_id=?", (patient_id,))
    return [r["allergen"] for r in rows]


def check_rx_allergy(patient_id: int, drugs: list[str]) -> list[dict]:
    """返回命中的过敏项；空列表=通过。"""
    allergens = patient_allergens(patient_id)
    hits = []
    for drug in drugs:
        for key, targets in DRUG_ALLERGEN.items():
            if key and key in drug:
                for t in targets:
                    if t in allergens:
                        hits.append({"drug": drug, "allergen": t, "cross": False})
        # 交叉过敏：青霉素过敏者用头孢——只提示，不硬拦
        for base, cross in CROSS_ALLERGY.items():
            if base in allergens and any(c in drug for c in cross):
                hits.append({"drug": drug, "allergen": base, "cross": True})
    return hits


# ---------------------------------------------------------------------------
# 号源与资质×档期匹配（4.5 / 4.8）
# ---------------------------------------------------------------------------
def catalog(catalog_id: int):
    row = query("""SELECT c.*, g.name AS category_name FROM treatment_catalog c
                   JOIN treatment_category g ON g.category_id=c.category_id
                   WHERE c.catalog_id=?""", (catalog_id,), one=True)
    if not row:
        raise BusinessError("治疗项目不存在", ERR_NOT_FOUND)
    return row


def catalog_price(catalog_id: int, clinic_id: int) -> int:
    """门店差异价优先，总部目录价为基准（4.9）。"""
    row = query("SELECT price_cents FROM clinic_price WHERE clinic_id=? AND catalog_id=?",
                (clinic_id, catalog_id), one=True)
    return row["price_cents"] if row else catalog(catalog_id)["price_cents"]


def dentist_has_skill(dentist_id: int, catalog_id: int) -> bool:
    row = query("SELECT 1 FROM dentist_skill WHERE dentist_id=? AND catalog_id=?",
                (dentist_id, catalog_id), one=True)
    return bool(row)


def available_slots(catalog_id: int, day: str, clinic_id: int | None = None,
                    dentist_id: int | None = None):
    """按项目时长返回可用号源切片（连续 N 片）。"""
    need = catalog(catalog_id)["duration_slots"] or 1
    sql = """SELECT s.*, sh.start_time AS shift_start, sh.end_time AS shift_end,
                    sh.clinic_id, sh.dentist_id, d.name AS dentist_name, d.title,
                    c.name AS clinic_name, ch.name AS chair_name
             FROM slot s
             JOIN shift sh ON sh.shift_id = s.shift_id
             JOIN dentist d ON d.dentist_id = sh.dentist_id
             JOIN clinic c ON c.clinic_id = sh.clinic_id
             JOIN chair ch ON ch.chair_id = sh.chair_id
             WHERE sh.shift_date=? AND sh.status='已发布' AND s.status='空闲'"""
    args: list = [day]
    if clinic_id:
        sql += " AND sh.clinic_id=?"
        args.append(clinic_id)
    if dentist_id:
        sql += " AND sh.dentist_id=?"
        args.append(dentist_id)
    sql += " AND EXISTS (SELECT 1 FROM dentist_skill ds WHERE ds.dentist_id=sh.dentist_id AND ds.catalog_id=?)"
    args.append(catalog_id)
    sql += " ORDER BY sh.dentist_id, sh.clinic_id, s.start_time"
    rows = query(sql, args)

    # 连续 N 片分组：同一班次内 seq 连续的切片才可预约
    grouped: dict[int, list] = {}
    for r in rows:
        grouped.setdefault(r["shift_id"], []).append(r)

    out = []
    for shift_id, items in grouped.items():
        items.sort(key=lambda x: x["seq"])
        for i in range(len(items) - need + 1):
            window = items[i:i + need]
            if all(window[k + 1]["seq"] == window[k]["seq"] + 1 for k in range(need - 1)):
                head = window[0]
                out.append({
                    "shift_id": shift_id,
                    "clinic_id": head["clinic_id"], "clinic_name": head["clinic_name"],
                    "dentist_id": head["dentist_id"], "dentist_name": head["dentist_name"],
                    "title": head["title"], "chair_name": head["chair_name"],
                    "start_time": head["start_time"],
                    "end_time": window[-1]["end_time"],
                    "slot_ids": [w["slot_id"] for w in window],
                    "slots": need,
                })
    out.sort(key=lambda x: (x["start_time"], x["dentist_id"]))
    return out


def candidate_dentists(catalog_id: int, day: str, clinic_id: int | None = None):
    """资质×档期筛选：先按资质，再按当日已发布班次且余量充足。"""
    sql = """SELECT DISTINCT d.dentist_id, d.name, d.title, d.intro
             FROM dentist d
             JOIN dentist_skill ds ON ds.dentist_id=d.dentist_id
             WHERE ds.catalog_id=? AND d.status='在职'"""
    rows = query(sql, (catalog_id,))
    result = []
    for d in rows:
        slots = available_slots(catalog_id, day, clinic_id, d["dentist_id"])
        if slots:
            quals = [q["cert_name"] for q in query(
                "SELECT cert_name FROM qualification WHERE dentist_id=?", (d["dentist_id"],))]
            result.append({**dict(d), "free_windows": len(slots),
                           "earliest": slots[0]["start_time"],
                           "clinic_name": slots[0]["clinic_name"],
                           "quals": quals})
    result.sort(key=lambda x: (-x["free_windows"], x["name"]))
    return result


def _lock_slots(slot_ids: list[int], visit_id: int):
    """5.2 之(1) 号源防超卖：条件更新，任一片被抢则整体回滚。"""
    for sid in slot_ids:
        cur = execute("UPDATE slot SET status='已占', visit_id=? WHERE slot_id=? AND visit_id IS NULL",
                      (visit_id, sid))
        if cur.rowcount == 0:
            execute("UPDATE slot SET status='空闲', visit_id=NULL WHERE visit_id=?", (visit_id,))
            raise BusinessError("该时段已被约满，请选择其他时段", ERR_CONFLICT)


def _release_slots(visit_id: int, mark: str = "空闲"):
    execute("UPDATE slot SET status=?, visit_id=NULL WHERE visit_id=?", (mark, visit_id))


# ---------------------------------------------------------------------------
# 预约：UC1 到店 / UC4 在线（共用同一号源池）
# ---------------------------------------------------------------------------
def create_booking(patient_id: int, catalog_id: int, day: str, start_time: str,
                   dentist_id: int, clinic_id: int, source: str = "到店",
                   special_note: str = "", deposit: bool = False,
                   operator: str = "") -> dict:
    item = catalog(catalog_id)
    need = item["duration_slots"] or 1

    # 资质覆盖校验（UC1 业务规则）
    if not dentist_has_skill(dentist_id, catalog_id):
        raise BusinessError(f"该牙医资质不覆盖「{item['name']}」，请重新选择医生", ERR_BUSINESS)

    # 患者同一时段最多一条有效就诊（UC4 业务规则）
    dup = query("""SELECT 1 FROM visit WHERE patient_id=? AND visit_date=? AND start_time=?
                   AND status IN ('待就诊','已完成','待支付')""",
                (patient_id, day, start_time), one=True)
    if dup:
        raise BusinessError("该患者同一时段已有预约，不可重复下单", ERR_CONFLICT)

    # 匹配可用号源（连续 N 片）
    windows = [w for w in available_slots(catalog_id, day, clinic_id, dentist_id)
               if w["start_time"] == start_time]
    if not windows:
        raise BusinessError("该时段已无可约号源，请返回重新选择", ERR_CONFLICT)
    win = windows[0]

    # 牙医档期冲突（同一时段既有就诊）
    conflict = query("""SELECT 1 FROM visit WHERE dentist_id=? AND visit_date=? AND start_time=?
                        AND status IN ('待就诊','已完成','待支付')""",
                     (dentist_id, day, start_time), one=True)
    if conflict:
        raise BusinessError("该牙医同时段已有就诊，请另选时段", ERR_CONFLICT)

    visit_id = execute(
        """INSERT INTO visit(patient_id, dentist_id, clinic_id, chair_id, visit_date,
                             start_time, end_time, slots, source, status, special_note,
                             is_arrived, created_at)
           VALUES (?,?,?,?,?,?,?,?,?, '待就诊', ?,0,?)""",
        (patient_id, dentist_id, clinic_id, None, day, win["start_time"], win["end_time"],
         need, source, special_note, now())).lastrowid
    execute("UPDATE visit SET chair_id=(SELECT chair_id FROM shift WHERE shift_id=?) WHERE visit_id=?",
            (win["shift_id"], visit_id))
    _lock_slots(win["slot_ids"], visit_id)

    # 在线预约申请单（UC4）
    booking_no = None
    if source == "在线":
        booking_no = gen_no("BK")
        expire = (datetime.now(TZ) + timedelta(minutes=15)).replace(microsecond=0).isoformat()
        execute("""INSERT INTO online_booking(booking_no, patient_id, catalog_id, clinic_id,
                                             visit_id, want_date, want_time, status, created_at, expire_at)
                   VALUES (?,?,?,?,?,?,?, '待确认', ?, ?)""",
                (booking_no, patient_id, catalog_id, clinic_id, visit_id, day, start_time, now(), expire))

    result = {"visit_id": visit_id, "booking_no": booking_no, "deposit_invoice": None,
              "start_time": win["start_time"], "end_time": win["end_time"],
              "dentist_name": win["dentist_name"], "clinic_name": win["clinic_name"]}

    # 定金：UC4 步骤 7a —— 同一张结算单，只含“预约定金”一行
    if deposit:
        inv = create_deposit_invoice(visit_id, catalog_id, clinic_id)
        result["deposit_invoice"] = inv
    audit("创建预约", f"visit#{visit_id}",
          after={"patient_id": patient_id, "catalog": item["name"], "date": day, "time": start_time},
          actor=operator or None)
    _notify(patient_id, visit_id, "预约确认",
            f"您已预约 {day} {start_time} · {win['clinic_name']} · {win['dentist_name']}")
    return result


def create_deposit_invoice(visit_id: int, catalog_id: int, clinic_id: int) -> dict:
    """预约定金 = 目录价 × 10%，不足 50 元按 50 元计（UC4 7a）。"""
    price = catalog_price(catalog_id, clinic_id)
    deposit = max(int(round(price * 0.1)), 5000)
    existing = query("SELECT * FROM invoice WHERE visit_id=?", (visit_id,), one=True)
    if existing:
        return dict(existing)
    inv_no = gen_no("INV")
    inv_id = execute("""INSERT INTO invoice(invoice_no, visit_id, total_cents, paid_cents,
                                            deposit_cents, status, kind, created_at)
                        VALUES (?,?,?,0,0,'待支付','定金单',?)""",
                     (inv_no, visit_id, deposit, now())).lastrowid
    execute("""INSERT INTO invoice_line(invoice_id, name, qty, unit_price_cents, amount_cents, kind)
               VALUES (?,?,1,?,?,'定金')""",
            (inv_id, "预约定金", deposit, deposit))
    return {"invoice_id": inv_id, "invoice_no": inv_no, "total_cents": deposit}


def reschedule_visit(visit_id: int, day: str, start_time: str, dentist_id: int,
                     catalog_id: int | None = None) -> dict:
    v = query("SELECT * FROM visit WHERE visit_id=?", (visit_id,), one=True)
    if not v:
        raise BusinessError("就诊不存在", ERR_NOT_FOUND)
    if v["status"] != "待就诊":
        raise BusinessError("仅“待就诊”状态允许改期（3.3 状态机）", ERR_CONFLICT)
    if not catalog_id:
        row = query("SELECT catalog_id FROM visit_treatment WHERE visit_id=?", (visit_id,), one=True)
        if not row:
            raise BusinessError("缺少治疗项目，无法改期", ERR_BAD_REQUEST)
        catalog_id = row["catalog_id"]

    windows = [w for w in available_slots(catalog_id, day, v["clinic_id"], dentist_id)
               if w["start_time"] == start_time]
    if not windows:
        raise BusinessError("目标时段无可用号源", ERR_CONFLICT)
    win = windows[0]

    _release_slots(visit_id)
    execute("""UPDATE visit SET visit_date=?, start_time=?, end_time=?, dentist_id=?, chair_id=?
               WHERE visit_id=?""",
            (day, win["start_time"], win["end_time"], dentist_id,
             query("SELECT chair_id FROM shift WHERE shift_id=?", (win["shift_id"],), one=True)["chair_id"],
             visit_id))
    _lock_slots(win["slot_ids"], visit_id)
    audit("改期", f"visit#{visit_id}", before={"date": v["visit_date"], "time": v["start_time"]},
          after={"date": day, "time": start_time})
    _notify(v["patient_id"], visit_id, "预约确认", f"您的预约已改期至 {day} {start_time}")
    return {"visit_id": visit_id, "date": day, "time": win["start_time"]}


def deposit_refund_rate(visit_date: str, start_time: str) -> float:
    """定金退还口径：24 小时外全退、24 小时内退 50%、爽约不退（UC7）。"""
    try:
        dt = datetime.fromisoformat(f"{visit_date}T{start_time}:00").replace(tzinfo=TZ)
    except ValueError:
        return 0.0
    delta = dt - datetime.now(TZ)
    if delta.total_seconds() > 24 * 3600:
        return 1.0
    if delta.total_seconds() > 0:
        return 0.5
    return 0.0


def cancel_visit(visit_id: int, cancel_type: str = "主动取消", reason: str = "") -> dict:
    v = query("SELECT * FROM visit WHERE visit_id=?", (visit_id,), one=True)
    if not v:
        raise BusinessError("就诊不存在", ERR_NOT_FOUND)
    if v["status"] not in ("待就诊", "已完成"):
        raise BusinessError("该就诊状态不允许取消", ERR_CONFLICT)

    rate = 1.0 if cancel_type == "停诊取消" else deposit_refund_rate(v["visit_date"], v["start_time"])
    if cancel_type == "爽约":
        rate = 0.0

    execute("UPDATE visit SET status='已取消', cancel_type=?, cancelled_at=? WHERE visit_id=?",
            (cancel_type, now(), visit_id))
    _release_slots(visit_id)

    refunded = 0
    inv = query("SELECT * FROM invoice WHERE visit_id=?", (visit_id,), one=True)
    if inv:
        pays = query("""SELECT * FROM payment_transaction WHERE invoice_id=? AND status='成功'
                        AND method='微信支付'""", (inv["invoice_id"],))
        for p in pays:
            already = query("SELECT COALESCE(SUM(amount_cents),0) s FROM refund WHERE pay_id=? AND status!='失败'",
                            (p["pay_id"],), one=True)["s"]
            amount = int(p["amount_cents"] * rate) - already
            if amount > 0:
                r = request_refund(p["pay_id"], amount,
                                   f"{cancel_type}·按 UC7 分档退还（{int(rate*100)}%）", actor="系统")
                approve_refund(r["refund_id"], "诊所经理")
                execute_refund(r["refund_id"], "财务")
                refunded += amount
        if refunded:
            execute("UPDATE invoice SET status='全额退款' WHERE invoice_id=?", (inv["invoice_id"],))
    execute("UPDATE online_booking SET status='已取消' WHERE visit_id=?", (visit_id,))
    # 候补转正：释放出的号源按登记顺序补位（4.5）
    _promote_waitlist(v["clinic_id"], v["visit_date"])
    audit(f"取消预约·{cancel_type}", f"visit#{visit_id}", before={"status": v["status"]},
          after={"status": "已取消", "refund_cents": refunded, "reason": reason})
    _notify(v["patient_id"], visit_id, "预约取消",
            f"{v['visit_date']} {v['start_time']} 的预约已取消，定金退回 {refunded/100:.2f} 元")
    return {"refund_cents": refunded, "rate": rate}


def _promote_waitlist(clinic_id: int, day: str):
    rows = query("""SELECT w.* FROM waitlist w JOIN shift sh ON sh.shift_id=w.shift_id
                    WHERE w.status='候补中' AND sh.shift_date=?
                    ORDER BY w.created_at""", (day,))
    for w in rows:
        free = query("""SELECT 1 FROM slot s JOIN shift sh ON sh.shift_id=s.shift_id
                        WHERE s.shift_id=? AND s.status='空闲' AND sh.status='已发布'""",
                     (w["shift_id"],), one=True)
        if free:
            execute("UPDATE waitlist SET status='已转正' WHERE wait_id=?", (w["wait_id"],))
            _notify(w["patient_id"], None, "候补转正", "您候补的时段已释放号源，可一键确认预约")


# ---------------------------------------------------------------------------
# 治疗登记 / 诊毕结算（UC2 / UC3）
# ---------------------------------------------------------------------------
def add_treatment(visit_id: int, catalog_id: int, qty: float = 1, operator: str = ""):
    v = query("SELECT * FROM visit WHERE visit_id=?", (visit_id,), one=True)
    if not v:
        raise BusinessError("就诊不存在", ERR_NOT_FOUND)
    if v["status"] not in ("待就诊", "已完成", "待支付"):
        raise BusinessError("该就诊状态不允许登记治疗", ERR_CONFLICT)
    item = catalog(catalog_id)
    price = catalog_price(catalog_id, v["clinic_id"])
    amount = int(round(price * qty))
    vt = execute("""INSERT INTO visit_treatment(visit_id, catalog_id, name_snapshot, qty,
                                                unit_price_cents, amount_cents, recall_weeks,
                                                created_by, created_at)
                    VALUES (?,?,?,?,?,?,?,?,?)""",
                 (visit_id, catalog_id, item["name"], qty, price, amount,
                  item["recall_weeks"], operator, now())).lastrowid
    # 复诊计划（4.5）：按项目规则生成
    if item["recall_weeks"]:
        due = (datetime.now(TZ) + timedelta(weeks=item["recall_weeks"])).strftime("%Y-%m-%d")
        execute("""INSERT INTO recall_plan(visit_id, patient_id, catalog_id, due_date, status)
                   VALUES (?,?,?,?, '待提醒')""", (visit_id, v["patient_id"], catalog_id, due))
    audit("登记治疗项目", f"visit#{visit_id}",
          after={"item": item["name"], "qty": qty, "amount_cents": amount}, actor=operator or None)
    return {"vt_id": vt, "amount_cents": amount, "name": item["name"]}


def finish_visit(visit_id: int, operator: str = ""):
    """生成结算单：含知情同意书 428 刚性校验（5.2 之(3)）与定金抵扣。"""
    v = query("SELECT * FROM visit WHERE visit_id=?", (visit_id,), one=True)
    if not v:
        raise BusinessError("就诊不存在", ERR_NOT_FOUND)
    treatments = query("""SELECT vt.*, c.requires_consent, g.name AS category_name
                          FROM visit_treatment vt
                          JOIN treatment_catalog c ON c.catalog_id=vt.catalog_id
                          JOIN treatment_category g ON g.category_id=c.category_id
                          WHERE vt.visit_id=?""", (visit_id,))
    if not treatments:
        raise BusinessError("该就诊尚无治疗记录，无法生成结算单", ERR_BUSINESS)

    record = query("SELECT * FROM treatment_record WHERE visit_id=? ORDER BY record_id DESC LIMIT 1",
                   (visit_id,), one=True)
    consent = None
    if record:
        consent = query("SELECT * FROM consent WHERE record_id=?", (record["record_id"],), one=True)

    need_consent = [t for t in treatments if t["requires_consent"]]
    if need_consent and not consent:
        cats = "、".join(sorted({t["category_name"] for t in need_consent}))
        raise BusinessError(
            f"该类治疗（{cats}）须先签署知情同意书（含治疗风险与费用）", ERR_PRECONDITION)

    total = sum(t["amount_cents"] for t in treatments)
    inv = query("SELECT * FROM invoice WHERE visit_id=?", (visit_id,), one=True)
    if inv and inv["paid_cents"] > 0:
        # 折扣仅未收款时允许（5.2 之(6) 已收款不可追溯）
        rate = inv["discount_rate"] or 0
    else:
        rate = inv["discount_rate"] if inv else 0
    total_after = int(round(total * (1 - (rate or 0))))

    if inv:
        inv_id = inv["invoice_id"]
        execute("DELETE FROM invoice_line WHERE invoice_id=? AND kind!='定金'", (inv_id,))
        execute("""UPDATE invoice SET total_cents=?, kind='结算单', status=?
                   WHERE invoice_id=?""",
                (total_after, "已结算" if inv["paid_cents"] >= total_after else "待支付", inv_id))
    else:
        inv_id = execute("""INSERT INTO invoice(invoice_no, visit_id, total_cents, paid_cents,
                                                deposit_cents, status, kind, created_at)
                            VALUES (?,?,?,0,0,?, '结算单', ?)""",
                         (gen_no("INV"), visit_id, total_after,
                          "待支付", now())).lastrowid

    for t in treatments:
        execute("""INSERT INTO invoice_line(invoice_id, name, qty, unit_price_cents, amount_cents, kind)
                   VALUES (?,?,?,?,?, '治疗')""",
                (inv_id, t["name_snapshot"], t["qty"], t["unit_price_cents"],
                 t["amount_cents"]))
    if rate:
        discount_amt = total - total_after
        execute("""INSERT INTO invoice_line(invoice_id, name, qty, unit_price_cents, amount_cents, kind)
                   VALUES (?,?,1,?,?, '折扣')""",
                (inv_id, f"折扣减免（{rate*100:.1f}%）", -discount_amt, -discount_amt))

    # 定金抵扣：同一张单，paid_cents 已包含定金流水
    execute("UPDATE invoice SET deposit_cents=(SELECT COALESCE(SUM(amount_cents),0) FROM payment_transaction WHERE invoice_id=? AND status='成功' AND method='微信支付' AND pay_no LIKE 'DEP%') WHERE invoice_id=?",
            (inv_id, inv_id))
    inv = query("SELECT * FROM invoice WHERE invoice_id=?", (inv_id,), one=True)
    total_now = inv["total_cents"]
    if inv["paid_cents"] >= total_now:
        execute("UPDATE invoice SET status='已结算', settled_at=? WHERE invoice_id=?", (now(), inv_id))
        execute("UPDATE visit SET status='已结算' WHERE visit_id=?", (visit_id,))
        _after_settled(visit_id, inv_id)
        # 超付原路退回
        over = inv["paid_cents"] - total_now
        if over > 0:
            p = query("""SELECT * FROM payment_transaction WHERE invoice_id=? AND status='成功'
                         ORDER BY pay_id DESC LIMIT 1""", (inv_id,), one=True)
            r = request_refund(p["pay_id"], over, "结算重算超付，原路退回", actor=operator or "系统")
            approve_refund(r["refund_id"], "诊所经理")
            execute_refund(r["refund_id"], "财务")
    else:
        execute("UPDATE visit SET status='待支付', is_arrived=1 WHERE visit_id=?", (visit_id,))
        execute("UPDATE invoice SET status='待支付' WHERE invoice_id=?", (inv_id,))

    audit("生成结算单", f"visit#{visit_id}",
          after={"invoice_no": query("SELECT invoice_no FROM invoice WHERE invoice_id=?", (inv_id,), one=True)["invoice_no"],
                 "total_cents": total_now, "paid_cents": inv["paid_cents"]}, actor=operator or None)
    return {"invoice_id": inv_id, "total_cents": total_now, "paid_cents": inv["paid_cents"]}


def _after_settled(visit_id: int, invoice_id: int):
    """结算后置动作：跨店分账、会员积分、病例毛利归集。"""
    v = query("SELECT * FROM visit WHERE visit_id=?", (visit_id,), one=True)
    inv = query("SELECT * FROM invoice WHERE invoice_id=?", (invoice_id,), one=True)
    execute("""INSERT INTO revenue_share(invoice_id, clinic_id, dentist_id, kind, amount_cents, created_at)
               VALUES (?,?,?, '收款归属', ?,?)""",
            (invoice_id, v["clinic_id"], v["dentist_id"], inv["paid_cents"], now()))
    execute("""INSERT INTO revenue_share(invoice_id, clinic_id, dentist_id, kind, amount_cents, created_at)
               VALUES (?,?,?, '业绩归属', ?,?)""",
            (invoice_id, v["clinic_id"], v["dentist_id"], inv["paid_cents"], now()))
    member = query("SELECT * FROM member WHERE patient_id=?", (v["patient_id"],), one=True)
    if member:
        pts = inv["paid_cents"] // 100          # 实付 1 元 = 1 分
        execute("UPDATE member SET points=points+? WHERE member_id=?", (pts, member["member_id"]))
        execute("""INSERT INTO member_transaction(member_id, kind, points, amount_cents,
                                                  balance_after, ref, created_at)
                   VALUES (?, '积分入账', ?, 0, ?, ?, ?)""",
                (member["member_id"], pts, member["points"] + pts, inv["invoice_no"], now()))


# ---------------------------------------------------------------------------
# 支付与退款（UC5 / UC7）
# ---------------------------------------------------------------------------
def pay(invoice_id: int, amount_cents: int, method: str = "微信支付",
        idem_key: str = "", third_party_no: str = "", operator: str = "患者"):
    """支付幂等（5.2 之(5)）：同一幂等键/第三方流水号只入账一次。"""
    inv = query("SELECT * FROM invoice WHERE invoice_id=?", (invoice_id,), one=True)
    if not inv:
        raise BusinessError("结算单不存在", ERR_NOT_FOUND)
    if inv["status"] in ("全额退款",):
        raise BusinessError("该结算单已全额退款，不可再支付", ERR_CONFLICT)

    if idem_key:
        dup = query("SELECT * FROM payment_transaction WHERE idem_key=?", (idem_key,), one=True)
        if dup:
            return {"duplicated": True, "pay_id": dup["pay_id"], "pay_no": dup["pay_no"],
                    "status": dup["status"]}
    if third_party_no:
        dup = query("SELECT * FROM payment_transaction WHERE third_party_no=?", (third_party_no,), one=True)
        if dup:
            return {"duplicated": True, "pay_id": dup["pay_id"], "pay_no": dup["pay_no"],
                    "status": dup["status"]}

    remaining = inv["total_cents"] - inv["paid_cents"]
    # 已收满：重复提交（患者连点/回调重放）直接按幂等返回，不报错（5.2 之(5)）
    if remaining <= 0:
        return {"duplicated": True, "pay_id": None, "pay_no": None,
                "status": inv["status"], "paid_cents": inv["paid_cents"],
                "total_cents": inv["total_cents"],
                "message": "该结算单已无待收金额"}
    if amount_cents <= 0:
        raise BusinessError("支付金额必须大于 0", ERR_BAD_REQUEST)
    if amount_cents > remaining:
        raise BusinessError(f"支付金额不得超过结算单待收金额（待收 {remaining/100:.2f} 元），不允许改价支付",
                            ERR_BUSINESS)

    prefix = "DEP" if inv["kind"] == "定金单" else "PAY"
    pay_no = gen_no(prefix)
    if not third_party_no and method == "微信支付":
        third_party_no = "WX" + pay_no
    pay_id = execute("""INSERT INTO payment_transaction(pay_no, invoice_id, amount_cents, method,
                                                        status, third_party_no, idem_key,
                                                        operator, created_at, finished_at)
                        VALUES (?,?,?,?, '成功', ?,?,?,?,?)""",
                     (pay_no, invoice_id, amount_cents, method, third_party_no,
                      idem_key or None, operator, now(), now())).lastrowid
    paid = inv["paid_cents"] + amount_cents
    is_deposit = inv["kind"] == "定金单"
    # 定金只是这张单的第一笔流水：不推进就诊状态，也不触发结算后置动作（4.4）
    # 付清后置「定金已付」，与「已结算」区分，避免定金被计入营收或挂在待收清单
    if is_deposit:
        status = "定金已付" if paid >= inv["total_cents"] else "待支付"
    else:
        status = "已结算" if paid >= inv["total_cents"] else "待支付"
    execute("UPDATE invoice SET paid_cents=?, status=?, settled_at=? WHERE invoice_id=?",
            (paid, status, now() if status == "已结算" else None, invoice_id))
    if status == "已结算" and not is_deposit:
        execute("UPDATE visit SET status='已结算' WHERE visit_id=?", (inv["visit_id"],))
        _after_settled(inv["visit_id"], invoice_id)
    execute("UPDATE online_booking SET status='已确认' WHERE visit_id=?", (inv["visit_id"],))
    audit("收款", f"invoice#{invoice_id}",
          after={"pay_no": pay_no, "amount": amount_cents, "method": method}, actor=operator)
    v = query("SELECT * FROM visit WHERE visit_id=?", (inv["visit_id"],), one=True)
    if v:
        _notify(v["patient_id"], v["visit_id"], "支付凭证",
                f"已收到 {method} 支付 {amount_cents/100:.2f} 元，单号 {pay_no}")
    return {"duplicated": False, "pay_id": pay_id, "pay_no": pay_no,
            "status": status, "paid_cents": paid, "total_cents": inv["total_cents"]}


def refundable(pay_id: int) -> int:
    p = query("SELECT * FROM payment_transaction WHERE pay_id=?", (pay_id,), one=True)
    if not p or p["status"] != "成功":
        return 0
    used = query("SELECT COALESCE(SUM(amount_cents),0) s FROM refund WHERE pay_id=? AND status!='失败'",
                 (pay_id,), one=True)["s"]
    return max(0, p["amount_cents"] - used)


def request_refund(pay_id: int, amount_cents: int, reason: str, actor: str = "") -> dict:
    p = query("SELECT * FROM payment_transaction WHERE pay_id=?", (pay_id,), one=True)
    if not p:
        raise BusinessError("支付流水不存在", ERR_NOT_FOUND)
    if p["status"] != "成功":
        raise BusinessError("仅成功的支付流水可退款", ERR_CONFLICT)
    remain = refundable(pay_id)
    if amount_cents <= 0 or amount_cents > remain:
        raise BusinessError(f"退款金额不得超过原流水可退金额（可退 {remain/100:.2f} 元）", ERR_BUSINESS)

    inv = query("SELECT * FROM invoice WHERE invoice_id=?", (p["invoice_id"],), one=True)
    # 先红冲后退款（5.2 之(4)）
    if inv and inv["is_invoiced"]:
        red = query("SELECT * FROM invoice_red WHERE invoice_id=?", (inv["invoice_id"],), one=True)
        if not red:
            raise BusinessError("已开票结算单须先红冲发票，再办理退款", ERR_BUSINESS)

    refund_no = gen_no("RF")
    rid = execute("""INSERT INTO refund(refund_no, pay_id, amount_cents, reason, status,
                                         approver, channel, created_at)
                     VALUES (?,?,?,?, '待审核', NULL, '原路退回', ?)""",
                  (refund_no, pay_id, amount_cents, reason, now())).lastrowid
    audit("发起退款", f"pay#{pay_id}",
          after={"refund_no": refund_no, "amount": amount_cents, "reason": reason}, actor=actor or None)
    return {"refund_id": rid, "refund_no": refund_no, "amount_cents": amount_cents}


def approve_refund(refund_id: int, approver: str):
    r = query("SELECT * FROM refund WHERE refund_id=?", (refund_id,), one=True)
    if not r:
        raise BusinessError("退款记录不存在", ERR_NOT_FOUND)
    if r["status"] != "待审核":
        raise BusinessError("仅待审核退款可审批", ERR_CONFLICT)
    execute("UPDATE refund SET status='退回中', approver=? WHERE refund_id=?", (approver, refund_id))
    audit("退款审核通过", f"refund#{refund_id}", after={"approver": approver})
    return {"refund_id": refund_id, "status": "退回中"}


def execute_refund(refund_id: int, operator: str):
    r = query("SELECT * FROM refund WHERE refund_id=?", (refund_id,), one=True)
    if not r:
        raise BusinessError("退款记录不存在", ERR_NOT_FOUND)
    if r["status"] != "退回中":
        raise BusinessError("退款需先经诊所经理审核", ERR_CONFLICT)
    execute("UPDATE refund SET status='已退回', finished_at=? WHERE refund_id=?",
            (now(), refund_id))
    p = query("SELECT * FROM payment_transaction WHERE pay_id=?", (r["pay_id"],), one=True)
    inv = query("SELECT * FROM invoice WHERE invoice_id=?", (p["invoice_id"],), one=True)
    refunded = query("SELECT COALESCE(SUM(amount_cents),0) s FROM refund WHERE pay_id=? AND status='已退回'",
                     (p["pay_id"],), one=True)["s"]
    if refunded >= p["amount_cents"]:
        execute("UPDATE invoice SET status='部分退款' WHERE invoice_id=?", (inv["invoice_id"],))
    if refunded >= inv["paid_cents"]:
        execute("UPDATE invoice SET status='全额退款' WHERE invoice_id=?", (inv["invoice_id"],))
        execute("UPDATE visit SET status='已退款' WHERE visit_id=?", (inv["visit_id"],))
    audit("退款执行", f"refund#{refund_id}",
          after={"amount": r["amount_cents"], "channel": "原路退回"}, actor=operator)
    return {"refund_id": refund_id, "status": "已退回", "amount_cents": r["amount_cents"]}


# ---------------------------------------------------------------------------
# 发票与折扣（4.7）
# ---------------------------------------------------------------------------
def issue_invoice(invoice_id: int, title: str, operator: str):
    inv = query("SELECT * FROM invoice WHERE invoice_id=?", (invoice_id,), one=True)
    if not inv:
        raise BusinessError("结算单不存在", ERR_NOT_FOUND)
    if inv["status"] not in ("已结算",):
        raise BusinessError("仅已结算的结算单可申请开票", ERR_CONFLICT)
    if inv["is_invoiced"]:
        raise BusinessError("该结算单已开票，不可重复开具", ERR_CONFLICT)
    execute("UPDATE invoice SET is_invoiced=1, invoice_title=? WHERE invoice_id=?",
            (title or "个人", invoice_id))
    audit("开具电子发票", f"invoice#{invoice_id}", after={"title": title}, actor=operator)
    return {"invoice_id": invoice_id, "is_invoiced": 1}


def reverse_invoice(invoice_id: int, reason: str, operator: str):
    inv = query("SELECT * FROM invoice WHERE invoice_id=?", (invoice_id,), one=True)
    if not inv or not inv["is_invoiced"]:
        raise BusinessError("该结算单未开票，无需红冲", ERR_CONFLICT)
    exists = query("SELECT * FROM invoice_red WHERE invoice_id=?", (invoice_id,), one=True)
    if exists:
        raise BusinessError("该发票已红冲，不可重复红冲", ERR_CONFLICT)
    red_no = gen_no("RED")
    execute("""INSERT INTO invoice_red(invoice_id, red_no, amount_cents, reason, operator, created_at)
               VALUES (?,?,?,?,?,?)""",
            (invoice_id, red_no, inv["paid_cents"], reason, operator, now()))
    audit("发票红冲", f"invoice#{invoice_id}", after={"red_no": red_no}, actor=operator)
    return {"red_no": red_no}


def apply_discount(invoice_id: int, rate: float, role: str, applicant: str, reason: str = ""):
    """折扣授权（5.2 之(6)）：限内直接生效，超额转诊所经理审批，已收款不可追溯。"""
    inv = query("SELECT * FROM invoice WHERE invoice_id=?", (invoice_id,), one=True)
    if not inv:
        raise BusinessError("结算单不存在", ERR_NOT_FOUND)
    if inv["paid_cents"] > 0:
        raise BusinessError("已收款账单不可追溯改折扣", ERR_BUSINESS)
    if rate < 0 or rate >= 1:
        raise BusinessError("折扣幅度不合法", ERR_BAD_REQUEST)
    limit = DISCOUNT_LIMITS.get(role, 0)
    if rate > limit:
        disc_id = execute("""INSERT INTO discount_approval(invoice_id, rate, applicant, apply_role,
                                                             status, reason, created_at)
                             VALUES (?,?,?,?, '待审批', ?, ?)""",
                          (invoice_id, rate, applicant, role, reason, now())).lastrowid
        audit("折扣申请（超额转审批）", f"invoice#{invoice_id}",
              after={"rate": rate, "limit": limit}, actor=applicant, role=role)
        return {"need_approval": True, "disc_id": disc_id,
                "message": f"折扣 {rate*100:.1f}% 超出{role}权限（≤{limit*100:.0f}%），已转诊所经理审批"}
    execute("UPDATE invoice SET discount_rate=? WHERE invoice_id=?", (rate, invoice_id))
    audit("折扣生效", f"invoice#{invoice_id}", after={"rate": rate}, actor=applicant, role=role)
    return {"need_approval": False, "rate": rate}


def decide_discount(disc_id: int, approve: bool, approver: str):
    d = query("SELECT * FROM discount_approval WHERE disc_id=?", (disc_id,), one=True)
    if not d:
        raise BusinessError("审批单不存在", ERR_NOT_FOUND)
    if d["status"] != "待审批":
        raise BusinessError("该审批单已处理", ERR_CONFLICT)
    execute("UPDATE discount_approval SET status=?, approver=?, decided_at=? WHERE disc_id=?",
            ("已通过" if approve else "已驳回", approver, now(), disc_id))
    if approve:
        execute("UPDATE invoice SET discount_rate=? WHERE invoice_id=?", (d["rate"], d["invoice_id"]))
    audit("折扣审批" + ("通过" if approve else "驳回"), f"disc#{disc_id}",
          after={"approver": approver}, actor=approver, role="诊所经理")
    return {"disc_id": disc_id, "status": "已通过" if approve else "已驳回"}


# ---------------------------------------------------------------------------
# 临床病历（UC8）
# ---------------------------------------------------------------------------
def ensure_record(visit_id: int, operator: str = "") -> int:
    rec = query("SELECT * FROM treatment_record WHERE visit_id=?", (visit_id,), one=True)
    if rec:
        return rec["record_id"]
    rid = execute("""INSERT INTO treatment_record(visit_id, created_by, created_at)
                     VALUES (?,?,?)""", (visit_id, operator, now())).lastrowid
    return rid


def save_tooth(visit_id: int, fdi: str, status: str, surfaces: list[str], note: str,
               operator: str = ""):
    rid = ensure_record(visit_id, operator)
    old = query("SELECT * FROM tooth_condition WHERE record_id=? AND fdi=?", (rid, fdi), one=True)
    if old:
        execute("UPDATE tooth_condition SET status=?, note=?, recorded_at=? WHERE tooth_id=?",
                (status, note, now(), old["tooth_id"]))
        tid = old["tooth_id"]
        execute("DELETE FROM tooth_surface WHERE tooth_id=?", (tid,))
    else:
        tid = execute("""INSERT INTO tooth_condition(record_id, fdi, status, note, recorded_at)
                         VALUES (?,?,?,?,?)""", (rid, fdi, status, note, now())).lastrowid
    for s in surfaces:
        execute("INSERT INTO tooth_surface(tooth_id, surface, status) VALUES (?,?, '受累')", (tid, s))
    audit("记录牙位状况", f"visit#{visit_id}·{fdi}",
          before={"status": old["status"]} if old else None,
          after={"status": status, "surfaces": surfaces}, actor=operator or None)
    return tid


def save_perio(visit_id: int, fdi: str, pds: list[int], cal: int, mobility: int, bleeding: int,
               operator: str = ""):
    rid = ensure_record(visit_id, operator)
    tooth = query("SELECT * FROM tooth_condition WHERE record_id=? AND fdi=?", (rid, fdi), one=True)
    if not tooth:
        tid = execute("""INSERT INTO tooth_condition(record_id, fdi, status, recorded_at)
                         VALUES (?,?, '正常', ?)""", (rid, fdi, now())).lastrowid
    else:
        tid = tooth["tooth_id"]
    execute("DELETE FROM perio_exam WHERE tooth_id=?", (tid,))
    execute("""INSERT INTO perio_exam(tooth_id, pd1,pd2,pd3,pd4,pd5,pd6, cal, mobility, bleeding)
               VALUES (?,?,?,?,?,?,?,?,?,?)""",
            (tid, *pds[:6], cal, mobility, bleeding))
    auto = None
    # UC8 扩展 3a：任一位点 PD≥4 自动生成牙周治疗计划项
    if max(pds) >= 4:
        plan = query("SELECT * FROM treatment_plan WHERE visit_id=? ORDER BY plan_id LIMIT 1",
                     (visit_id,), one=True)
        if not plan:
            pid = execute("""INSERT INTO treatment_plan(visit_id, stage, status, note, created_at)
                             VALUES (?, '一期', '计划', '牙周基础治疗', ?)""",
                          (visit_id, now())).lastrowid
        else:
            pid = plan["plan_id"]
        exists = query("SELECT 1 FROM plan_item WHERE plan_id=? AND fdi=? AND auto_flag=1",
                       (pid, fdi), one=True)
        if not exists:
            execute("""INSERT INTO plan_item(plan_id, fdi, catalog_id, status, note, auto_flag)
                       VALUES (?,?,?, '计划', ?, 1)""",
                    (pid, fdi, _catalog_id_by_name("龈下刮治"), f"PD≥4，自动生成牙周治疗计划"))
            auto = "已按 PD≥4 自动生成牙周治疗计划项"
    audit("录入牙周检查", f"visit#{visit_id}·{fdi}",
          after={"pd": pds, "cal": cal, "mobility": mobility}, actor=operator or None)
    return {"auto_plan": auto}


def _catalog_id_by_name(name: str):
    row = query("SELECT catalog_id FROM treatment_catalog WHERE name LIKE ?", (f"%{name}%",), one=True)
    return row["catalog_id"] if row else None


def add_plan_item(visit_id: int, fdi: str, catalog_id: int, stage: str, note: str,
                  operator: str = ""):
    plan = query("SELECT * FROM treatment_plan WHERE visit_id=? ORDER BY plan_id LIMIT 1",
                 (visit_id,), one=True)
    if plan:
        pid = plan["plan_id"]
        execute("UPDATE treatment_plan SET stage=? WHERE plan_id=?", (stage, pid))
    else:
        pid = execute("""INSERT INTO treatment_plan(visit_id, stage, status, note, created_at)
                         VALUES (?,?, '计划', ?, ?)""", (visit_id, stage, note, now())).lastrowid
    execute("""INSERT INTO plan_item(plan_id, fdi, catalog_id, status, note, auto_flag)
               VALUES (?,?,?, '计划', ?, 0)""", (pid, fdi, catalog_id, note))
    audit("维护治疗计划项", f"visit#{visit_id}", after={"fdi": fdi, "stage": stage},
          actor=operator or None)
    return pid


def save_prescription(visit_id: int, drug: str, dose: str, usage: str, is_narcotic: bool,
                      register_no: str, double_check_by: str, operator: str = "",
                      dentist_id: int | None = None):
    """处方过敏硬校验（5.2 之(2)）+ 麻精药品专册双人核对。"""
    v = query("SELECT * FROM visit WHERE visit_id=?", (visit_id,), one=True)
    if not v:
        raise BusinessError("就诊不存在", ERR_NOT_FOUND)
    hits = check_rx_allergy(v["patient_id"], [drug])
    hard = [h for h in hits if not h["cross"]]
    if hard:
        h = hard[0]
        raise BusinessError(f"过敏拦截：患者对{h['allergen']}过敏，禁用{h['drug']}", ERR_BUSINESS)
    if is_narcotic and (not register_no or not double_check_by):
        raise BusinessError("麻醉/精神药品须登记专册编号并完成双人核对", ERR_BUSINESS)

    rid = ensure_record(visit_id, operator)
    rx = query("SELECT * FROM prescription WHERE record_id=?", (rid,), one=True)
    if rx:
        rx_id = rx["rx_id"]
    else:
        rx_id = execute("""INSERT INTO prescription(record_id, doctor_id, status, created_at)
                           VALUES (?,?, '已开立', ?)""",
                        (rid, dentist_id or v["dentist_id"], now())).lastrowid
    execute("""INSERT INTO prescription_item(rx_id, drug, dose, usage, is_narcotic,
                                             register_no, double_check_by)
               VALUES (?,?,?,?,?,?,?)""",
            (rx_id, drug, dose, usage, 1 if is_narcotic else 0, register_no, double_check_by))
    audit("开立处方", f"visit#{visit_id}",
          after={"drug": drug, "narcotic": bool(is_narcotic)}, actor=operator or None)
    warn = [f"{h['allergen']}过敏者使用{h['drug']}存在交叉过敏风险，已提示" for h in hits if h["cross"]]
    return {"rx_id": rx_id, "warnings": warn}


def save_imaging(visit_id: int, fdi: str, type_: str, finding: str, operator: str = ""):
    rid = ensure_record(visit_id, operator)
    path = f"/static/img/xray/{fdi or 'pan'}_{type_}.svg"
    iid = execute("""INSERT INTO imaging(record_id, fdi, type, storage_path, finding, taken_at)
                     VALUES (?,?,?,?,?,?)""", (rid, fdi, type_, path, finding, now())).lastrowid
    audit("影像归档", f"visit#{visit_id}·{fdi}", after={"type": type_}, actor=operator or None)
    return {"image_id": iid, "path": path}


CONSENT_TEMPLATES = ["种植手术知情同意书", "拔牙知情同意书", "根管治疗知情同意书", "正畸治疗知情同意书"]


def sign_consent(visit_id: int, template: str, signed_by: str, signature: str,
                 operator: str = ""):
    rid = ensure_record(visit_id, operator)
    exists = query("SELECT * FROM consent WHERE record_id=? AND template=?", (rid, template), one=True)
    if exists:
        raise BusinessError("该同意书已签署，模板版本已锁定", ERR_CONFLICT)
    cid = execute("""INSERT INTO consent(record_id, template, version, signed_by, signature, signed_at)
                     VALUES (?,?,?,?,?,?)""",
                  (rid, template, "V2.1", signed_by, signature or "电子签名", now())).lastrowid
    audit("知情同意签署", f"visit#{visit_id}", after={"template": template, "version": "V2.1"},
          actor=operator or signed_by)
    return {"consent_id": cid}


def use_pack(visit_id: int, pack_id: int, operator: str = ""):
    """消毒追溯（V9）：过期包拦截。"""
    p = query("SELECT * FROM sterilization_pack WHERE pack_id=?", (pack_id,), one=True)
    if not p:
        raise BusinessError("器械包不存在", ERR_NOT_FOUND)
    if p["status"] == "已领用":
        raise BusinessError("该器械包已被领用", ERR_CONFLICT)
    if p["expire_at"] and p["expire_at"] < today():
        execute("UPDATE sterilization_pack SET status='过期' WHERE pack_id=?", (pack_id,))
        raise BusinessError(f"器械包 {p['pack_no']} 已过有效期（{p['expire_at']}），请重新灭菌后使用",
                            ERR_BUSINESS)
    execute("UPDATE sterilization_pack SET status='已领用' WHERE pack_id=?", (pack_id,))
    execute("INSERT INTO pack_trace(pack_id, visit_id, used_at, operator) VALUES (?,?,?,?)",
            (pack_id, visit_id, now(), operator))
    audit("消毒包领用", f"visit#{visit_id}", after={"pack_no": p["pack_no"]}, actor=operator or None)
    return {"pack_no": p["pack_no"]}


# ---------------------------------------------------------------------------
# 排班（UC6）与停诊级联（V10）
# ---------------------------------------------------------------------------
def create_shift(dentist_id: int, clinic_id: int, chair_id: int, day: str,
                 start_time: str, end_time: str, operator: str = "", publish: bool = True):
    # 资质：班次必须至少覆盖该医生一项技能
    skills = query("SELECT catalog_id FROM dentist_skill WHERE dentist_id=?", (dentist_id,))
    if not skills:
        raise BusinessError("该牙医未维护任何资质，无法排班", ERR_BUSINESS)
    if not query("""SELECT 1 FROM dentist_skill ds JOIN clinic_quota q
                    ON q.catalog_id=ds.catalog_id AND q.clinic_id=? AND q.authorized=1
                    WHERE ds.dentist_id=?""", (clinic_id, dentist_id), one=True):
        raise BusinessError("该门店未获授权该牙医的任何项目，请先在门店项目授权中配置", ERR_BUSINESS)

    # 牙医同时段冲突
    if query("""SELECT 1 FROM shift WHERE dentist_id=? AND shift_date=? AND status!='停诊'
                AND NOT (end_time<=? OR start_time>=?)""",
             (dentist_id, day, start_time, end_time), one=True):
        raise BusinessError("该牙医此时段已有班次，排班冲突", ERR_CONFLICT)
    # 牙椅占用
    if query("""SELECT 1 FROM shift WHERE chair_id=? AND shift_date=? AND status!='停诊'
                AND NOT (end_time<=? OR start_time>=?)""",
             (chair_id, day, start_time, end_time), one=True):
        raise BusinessError("该牙椅此时段已被占用", ERR_CONFLICT)

    slot_count = _slot_span(start_time, end_time)
    sid = execute("""INSERT INTO shift(dentist_id, clinic_id, chair_id, shift_date, start_time,
                                        end_time, slot_count, status, created_by, created_at)
                     VALUES (?,?,?,?,?,?,?,?,?,?)""",
                  (dentist_id, clinic_id, chair_id, day, start_time, end_time,
                   slot_count, "已发布" if publish else "草稿", operator, now())).lastrowid
    _ensure_slots(sid, start_time, slot_count)
    audit("维护排班", f"shift#{sid}",
          after={"dentist_id": dentist_id, "date": day, "time": f"{start_time}-{end_time}"},
          actor=operator or None)
    return {"shift_id": sid, "slot_count": slot_count}


def _slot_span(start_time: str, end_time: str) -> int:
    h1, m1 = map(int, start_time.split(":"))
    h2, m2 = map(int, end_time.split(":"))
    return max(1, ((h2 * 60 + m2) - (h1 * 60 + m1)) // 30)


def _ensure_slots(shift_id: int, start_time: str, count: int):
    h, m = map(int, start_time.split(":"))
    for i in range(count):
        s = f"{h:02d}:{m:02d}"
        m += 30
        if m >= 60:
            h += 1
            m -= 60
        e = f"{h:02d}:{m:02d}"
        execute("""INSERT OR IGNORE INTO slot(shift_id, seq, start_time, end_time, status)
                   VALUES (?,?,?,?, '空闲')""", (shift_id, i + 1, s, e))


def suspend_shift(shift_id: int, operator: str = ""):
    """V10 停诊级联：号源下架、关联预约自动取消、定金批量退回。"""
    sh = query("SELECT * FROM shift WHERE shift_id=?", (shift_id,), one=True)
    if not sh:
        raise BusinessError("班次不存在", ERR_NOT_FOUND)
    if sh["status"] == "停诊":
        raise BusinessError("该班次已停诊", ERR_CONFLICT)
    execute("UPDATE shift SET status='停诊' WHERE shift_id=?", (shift_id,))
    execute("UPDATE slot SET status='停诊释放' WHERE shift_id=? AND visit_id IS NULL", (shift_id,))
    visits = query("""SELECT DISTINCT v.* FROM visit v JOIN slot s ON s.visit_id=v.visit_id
                      WHERE s.shift_id=? AND v.status='待就诊'""", (shift_id,))
    cancelled = []
    for v in visits:
        try:
            res = cancel_visit(v["visit_id"], "停诊取消", "班次停诊")
            cancelled.append({"visit_id": v["visit_id"], "refund": res["refund_cents"]})
        except BusinessError:
            pass
    audit("停诊", f"shift#{shift_id}", after={"cancelled": len(cancelled)}, actor=operator or None)
    return {"cancelled": cancelled, "count": len(cancelled)}


# ---------------------------------------------------------------------------
# 分期收费（UC9）
# ---------------------------------------------------------------------------
def create_installment(patient_id: int, total_cents: int, mode: str, periods: int,
                       down_rate: float = 0.3, visit_id: int | None = None,
                       operator: str = ""):
    if periods < 1 or periods > 24:
        raise BusinessError("期数应在 1—24 之间", ERR_BAD_REQUEST)
    down = int(round(total_cents * down_rate))
    per = (total_cents - down) // periods if periods else 0
    adjust = total_cents - down - per * periods
    plan_no = gen_no("IP")
    pid = execute("""INSERT INTO installment_plan(plan_no, patient_id, visit_id, mode, total_cents,
                                                  down_cents, periods, per_cents, status, signed,
                                                  created_at, expire_at)
                     VALUES (?,?,?,?,?,?,?,?, '待支付', 0, ?, ?)""",
                  (plan_no, patient_id, visit_id, mode, total_cents, down, periods, per,
                   now(), (datetime.now(TZ) + timedelta(minutes=15)).replace(microsecond=0).isoformat())).lastrowid
    execute("""INSERT INTO installment(plan_id, seq, due_date, amount_cents, status)
               VALUES (?, 0, ?, ?, '待付')""", (pid, today(), down))
    for i in range(1, periods + 1):
        due = (date.today() + timedelta(days=30 * i)).isoformat()
        amt = per + (adjust if i == periods else 0)
        execute("""INSERT INTO installment(plan_id, seq, due_date, amount_cents, status)
                   VALUES (?,?,?,?, '待付')""", (pid, i, due, amt))
    audit("办理分期", f"plan#{pid}", after={"total": total_cents, "periods": periods},
          actor=operator or None)
    return {"plan_id": pid, "plan_no": plan_no, "down_cents": down, "per_cents": per}


def sign_installment(plan_id: int, signer: str, operator: str = ""):
    p = query("SELECT * FROM installment_plan WHERE inst_plan_id=?", (plan_id,), one=True)
    if not p:
        raise BusinessError("收款计划不存在", ERR_NOT_FOUND)
    execute("UPDATE installment_plan SET signed=1 WHERE inst_plan_id=?", (plan_id,))
    audit("收费协议电子签署", f"plan#{plan_id}", after={"signer": signer}, actor=signer)
    return {"plan_id": plan_id, "signed": 1}


def pay_installment(inst_id: int, method: str = "微信支付", operator: str = "前台",
                    idem_key: str = ""):
    inst = query("SELECT * FROM installment WHERE inst_id=?", (inst_id,), one=True)
    if not inst:
        raise BusinessError("期款不存在", ERR_NOT_FOUND)
    if inst["status"] not in ("待付", "逾期"):
        raise BusinessError("该期款已处理", ERR_CONFLICT)
    plan = query("SELECT * FROM installment_plan WHERE inst_plan_id=?", (inst["plan_id"],), one=True)
    if not plan["signed"]:
        raise BusinessError("收费协议未签署，不能收款", ERR_BUSINESS)

    if idem_key:
        dup = query("SELECT * FROM installment WHERE pay_no=?", (idem_key,), one=True)
        if dup and dup["status"] == "已付":
            return {"duplicated": True, "inst_id": dup["inst_id"]}
    pay_no = gen_no("IPAY")
    execute("UPDATE installment SET status='已付', pay_no=?, retry_count=retry_count+1 WHERE inst_id=?",
            (pay_no, inst_id))
    paid_cnt = query("SELECT COUNT(*) c FROM installment WHERE plan_id=? AND status='已付'",
                     (plan["inst_plan_id"],), one=True)["c"]
    total_cnt = query("SELECT COUNT(*) c FROM installment WHERE plan_id=?",
                      (plan["inst_plan_id"],), one=True)["c"]
    if paid_cnt >= total_cnt:
        execute("UPDATE installment_plan SET status='已结清' WHERE inst_plan_id=?", (plan["inst_plan_id"],))
    elif inst["seq"] >= 0:
        execute("UPDATE installment_plan SET status='已生效' WHERE inst_plan_id=?", (plan["inst_plan_id"],))
    audit("期款核销", f"installment#{inst_id}", after={"pay_no": pay_no, "method": method},
          actor=operator)
    return {"duplicated": False, "pay_no": pay_no, "paid_cnt": paid_cnt, "total_cnt": total_cnt}


def mark_overdue():
    """期款逾期：到期未付置逾期，冻结新的预约（4.7 图14）。"""
    rows = query("""SELECT i.*, p.patient_id FROM installment i
                    JOIN installment_plan p ON p.inst_plan_id=i.plan_id
                    WHERE i.status='待付' AND i.due_date < ? AND p.status='已生效'""", (today(),))
    for r in rows:
        execute("UPDATE installment SET status='逾期' WHERE inst_id=?", (r["inst_id"],))
        audit("期款逾期", f"installment#{r['inst_id']}", actor="系统(定时任务)")
    return len(rows)


# ---------------------------------------------------------------------------
# 通知
# ---------------------------------------------------------------------------
def _notify(patient_id: int, visit_id, template: str, content: str,
            channel: str = "服务号订阅消息"):
    execute("""INSERT INTO notification_log(visit_id, patient_id, template, content, channel,
                                            status, created_at)
               VALUES (?,?,?,?,?, '已发送', ?)""",
            (visit_id, patient_id, template, content, channel, now()))


# ---------------------------------------------------------------------------
# 定时任务（4.4 / 4.5 / 4.8 / 4.10）
# ---------------------------------------------------------------------------
def job_release_expired():
    """线上未支付订单 15 分钟自动释放号源（4.13）。"""
    rows = query("""SELECT ob.*, v.status AS vstatus FROM online_booking ob
                    JOIN visit v ON v.visit_id=ob.visit_id
                    WHERE ob.status='待确认' AND ob.expire_at < ?""", (now(),))
    n = 0
    for r in rows:
        inv = query("SELECT * FROM invoice WHERE visit_id=?", (r["visit_id"],), one=True)
        if inv and inv["paid_cents"] > 0:
            continue
        execute("UPDATE online_booking SET status='已过期' WHERE booking_id=?", (r["booking_id"],))
        execute("UPDATE visit SET status='已取消', cancel_type='主动取消', cancelled_at=? WHERE visit_id=?",
                (now(), r["visit_id"]))
        _release_slots(r["visit_id"])
        if inv:
            execute("UPDATE invoice SET status='待支付' WHERE invoice_id=?", (inv["invoice_id"],))
            execute("UPDATE payment_transaction SET status='已关闭' WHERE invoice_id=? AND status='待支付'",
                    (inv["invoice_id"],))
        n += 1
    if n:
        audit("定时任务·释放超时号源", after={"count": n}, actor="系统(定时任务)")
    return n


def job_mark_no_show():
    """就诊时段结束后未到店且未取消 → 爽约（4.5）。"""
    rows = query("""SELECT * FROM visit WHERE status='待就诊' AND is_arrived=0
                    AND (visit_date < ? OR (visit_date = ? AND end_time < ?))""",
                 (today(), today(), datetime.now(TZ).strftime("%H:%M")))
    n = 0
    for v in rows:
        execute("UPDATE visit SET status='已取消', cancel_type='爽约', cancelled_at=? WHERE visit_id=?",
                (now(), v["visit_id"]))
        _release_slots(v["visit_id"])
        execute("UPDATE patient SET no_show_cnt=no_show_cnt+1 WHERE patient_id=?", (v["patient_id"],))
        execute("UPDATE online_booking SET status='已过期' WHERE visit_id=?", (v["visit_id"],))
        _notify(v["patient_id"], v["visit_id"], "爽约提醒",
                "您未按时到店且未提前取消，本次定金不予退还，累计爽约将影响后续预约")
        n += 1
    if n:
        audit("定时任务·标记爽约", after={"count": n}, actor="系统(定时任务)")
    return n


def job_dispatch_recall():
    """每日扫描次日到期复诊计划，推送提醒（4.5 / 4.8）。"""
    tomorrow = (date.today() + timedelta(days=1)).isoformat()
    rows = query("""SELECT rp.*, p.name FROM recall_plan rp JOIN patient p ON p.patient_id=rp.patient_id
                    WHERE rp.status='待提醒' AND rp.due_date<=?""", (tomorrow,))
    n = 0
    for r in rows:
        _notify(r["patient_id"], r["visit_id"], "复诊召回",
                f"尊敬的患者，您的复诊计划已到期（{r['due_date']}），点击可一键预约专属号源")
        execute("UPDATE recall_plan SET status='已提醒', notified_at=?, channel='服务号订阅消息' WHERE recall_id=?",
                (now(), r["recall_id"]))
        n += 1
    if n:
        audit("定时任务·复诊提醒", after={"count": n}, actor="系统(定时任务)")
    return n


def job_daily_reconcile(day: str | None = None):
    """每日 02:00 对账 + 日营收（4.4）。"""
    day = day or (date.today() - timedelta(days=1)).isoformat()
    clinics = query("SELECT * FROM clinic")
    n = 0
    for c in clinics:
        recv = query("""SELECT COALESCE(SUM(p.amount_cents),0) s FROM payment_transaction p
                        JOIN invoice i ON i.invoice_id=p.invoice_id
                        JOIN visit v ON v.visit_id=i.visit_id
                        WHERE v.clinic_id=? AND p.status='成功' AND substr(p.finished_at,1,10)=?""",
                     (c["clinic_id"], day), one=True)["s"]
        rf = query("""SELECT COALESCE(SUM(r.amount_cents),0) s FROM refund r
                      JOIN payment_transaction p ON p.pay_id=r.pay_id
                      JOIN invoice i ON i.invoice_id=p.invoice_id
                      JOIN visit v ON v.visit_id=i.visit_id
                      WHERE v.clinic_id=? AND r.status='已退回' AND substr(r.finished_at,1,10)=?""",
                   (c["clinic_id"], day), one=True)["s"]
        recv_amt = query("""SELECT COALESCE(SUM(i.total_cents),0) s FROM invoice i
                            JOIN visit v ON v.visit_id=i.visit_id
                            WHERE v.clinic_id=? AND substr(i.created_at,1,10)=?""",
                         (c["clinic_id"], day), one=True)["s"]
        diff = recv - max(0, recv_amt) + 0
        execute("""INSERT INTO daily_revenue(clinic_id, rev_date, receivable_cents, received_cents,
                                             refund_cents, diff_cents, created_at)
                   VALUES (?,?,?,?,?,?,?)
                   ON CONFLICT(clinic_id, rev_date) DO UPDATE SET
                     receivable_cents=excluded.receivable_cents,
                     received_cents=excluded.received_cents,
                     refund_cents=excluded.refund_cents,
                     diff_cents=excluded.diff_cents""",
                (c["clinic_id"], day, recv_amt, recv, rf, (recv_amt - recv - rf), now()))
        n += 1
    audit("定时任务·日对账", after={"date": day, "clinics": n}, actor="系统(定时任务)")
    return n


def job_quarterly_summary(year: int | None = None, quarter: int | None = None):
    """季度业绩 + 激励基金 = 净利润 × 10%（4.4）。"""
    d = date.today()
    year = year or d.year
    quarter = quarter or ((d.month - 1) // 3 + 1)
    start = date(year, 3 * (quarter - 1) + 1, 1).isoformat()
    end_m = 3 * quarter
    end = date(year, end_m, 28).isoformat()
    dentists = query("SELECT * FROM dentist")
    n = 0
    for doc in dentists:
        revenue = query("""SELECT COALESCE(SUM(i.paid_cents),0) s FROM invoice i
                           JOIN visit v ON v.visit_id=i.visit_id
                           WHERE v.dentist_id=? AND i.status='已结算'
                             AND substr(i.created_at,1,10) BETWEEN ? AND ?""",
                        (doc["dentist_id"], start, end), one=True)["s"]
        material = query("""SELECT COALESCE(SUM(cc.amount_cents),0) s FROM case_cost cc
                            JOIN visit v ON v.visit_id=cc.visit_id
                            WHERE v.dentist_id=? AND substr(cc.created_at,1,10) BETWEEN ? AND ?""",
                         (doc["dentist_id"], start, end), one=True)["s"]
        # 运营费用按该医生当期已结算金额占门店比例分摊
        total_rev = query("""SELECT COALESCE(SUM(i.paid_cents),0) s FROM invoice i
                             WHERE i.status='已结算' AND substr(i.created_at,1,10) BETWEEN ? AND ?""",
                          (start, end), one=True)["s"] or 1
        month_list = [f"{year}-{m:02d}" for m in range(3 * quarter - 2, 3 * quarter + 1)]
        expense_all = query(f"""SELECT COALESCE(SUM(amount_cents),0) s FROM expense
                                WHERE month IN ({','.join('?'*len(month_list))})""",
                            month_list, one=True)["s"]
        expense = int(expense_all * revenue / total_rev)
        profit = revenue - material - expense
        fund = int(profit * 0.10)
        execute("""INSERT INTO quarterly_performance(dentist_id, year, quarter, revenue_cents,
                                                     material_cents, expense_cents, profit_cents,
                                                     fund_cents, created_at)
                   VALUES (?,?,?,?,?,?,?,?,?)
                   ON CONFLICT(dentist_id, year, quarter) DO UPDATE SET
                     revenue_cents=excluded.revenue_cents, material_cents=excluded.material_cents,
                     expense_cents=excluded.expense_cents, profit_cents=excluded.profit_cents,
                     fund_cents=excluded.fund_cents""",
                (doc["dentist_id"], year, quarter, revenue, material, expense, profit, fund, now()))
        n += 1
    audit("定时任务·季度业绩汇总", after={"year": year, "quarter": quarter, "dentists": n},
          actor="系统(定时任务)")
    return n


def run_all_jobs() -> dict:
    return {
        "release_expired": job_release_expired(),
        "no_show": job_mark_no_show(),
        "recall": job_dispatch_recall(),
        "overdue": mark_overdue(),
        "reconcile": job_daily_reconcile(),
        "quarterly": job_quarterly_summary(),
    }
