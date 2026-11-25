-- =====================================================================
-- 牙科诊所诊疗信息平台 · 数据层建库脚本
-- 依据《系统分析与设计》4.1 图9 ERD 与图10 六业务域，共 57 张表
-- 约定：金额一律整数“分”；时间 ISO 8601 字符串；主键自增整数；
--       业务单据不允许物理删除，只允许状态流转或软删除标记（附录A）
-- =====================================================================
PRAGMA foreign_keys = ON;

-- ---------------------------------------------------------------------
-- 域一：主数据与组织（诊所 / 牙椅 / 牙医 / 资质 / 目录 / 授权）
-- ---------------------------------------------------------------------
CREATE TABLE clinic (
    clinic_id   INTEGER PRIMARY KEY AUTOINCREMENT,
    name        TEXT NOT NULL,
    code        TEXT UNIQUE,
    address     TEXT,
    phone       TEXT,
    status      TEXT DEFAULT '营业'          -- 营业 / 停业
);

CREATE TABLE chair (
    chair_id    INTEGER PRIMARY KEY AUTOINCREMENT,
    clinic_id   INTEGER NOT NULL REFERENCES clinic(clinic_id),
    name        TEXT NOT NULL,
    room        TEXT
);

CREATE TABLE dentist (
    dentist_id  INTEGER PRIMARY KEY AUTOINCREMENT,
    name        TEXT NOT NULL,
    title       TEXT,
    phone       TEXT,
    intro       TEXT,
    status      TEXT DEFAULT '在职'
);

CREATE TABLE qualification (
    qual_id     INTEGER PRIMARY KEY AUTOINCREMENT,
    dentist_id  INTEGER NOT NULL REFERENCES dentist(dentist_id),
    cert_name   TEXT NOT NULL,              -- 口腔执业医师 / 口腔种植资质 / 正畸专科 …
    cert_no     TEXT,
    valid_until TEXT
);

CREATE TABLE dentist_skill (
    skill_id    INTEGER PRIMARY KEY AUTOINCREMENT,
    dentist_id  INTEGER NOT NULL REFERENCES dentist(dentist_id),
    catalog_id  INTEGER NOT NULL REFERENCES treatment_catalog(catalog_id),
    level       TEXT DEFAULT '熟练'
);

CREATE TABLE staff_account (
    account_id    INTEGER PRIMARY KEY AUTOINCREMENT,
    username      TEXT UNIQUE NOT NULL,
    password_hash TEXT NOT NULL,
    display_name  TEXT NOT NULL,
    role          TEXT NOT NULL,            -- 前台 / 医生 / 财务 / 诊所经理 / 运营专员 / 患者
    clinic_id     INTEGER REFERENCES clinic(clinic_id),
    dentist_id    INTEGER REFERENCES dentist(dentist_id),
    patient_id    INTEGER,
    status        TEXT DEFAULT '启用',
    created_at    TEXT
);

CREATE TABLE duty (
    duty_id     INTEGER PRIMARY KEY AUTOINCREMENT,
    dentist_id  INTEGER NOT NULL REFERENCES dentist(dentist_id),
    clinic_id   INTEGER NOT NULL REFERENCES clinic(clinic_id),
    start_date  TEXT,
    end_date    TEXT,
    status      TEXT DEFAULT '在岗'
);

CREATE TABLE treatment_category (
    category_id INTEGER PRIMARY KEY AUTOINCREMENT,
    name        TEXT NOT NULL UNIQUE,       -- 口腔检查/洁治/补牙/根管治疗/修复/种植/正畸/儿童牙科
    sort_no     INTEGER DEFAULT 0,
    intro       TEXT
);

CREATE TABLE treatment_catalog (
    catalog_id       INTEGER PRIMARY KEY AUTOINCREMENT,
    category_id      INTEGER NOT NULL REFERENCES treatment_category(category_id),
    name             TEXT NOT NULL,
    unit             TEXT DEFAULT '次',
    price_cents      INTEGER NOT NULL,      -- 标准单位价格（分）
    duration_slots   INTEGER DEFAULT 1,     -- 标准时长（30 分钟切片数）
    requires_consent INTEGER DEFAULT 0,     -- 1=必须签知情同意书
    recall_weeks     INTEGER DEFAULT 0,     -- 复诊周期（周），0=无
    intro            TEXT,
    status           TEXT DEFAULT '启用'
);

CREATE TABLE price_history (
    price_id    INTEGER PRIMARY KEY AUTOINCREMENT,
    catalog_id  INTEGER NOT NULL REFERENCES treatment_catalog(catalog_id),
    old_cents   INTEGER,
    new_cents   INTEGER,
    changed_by  TEXT,
    changed_at  TEXT,
    reason      TEXT
);

CREATE TABLE clinic_price (
    cp_id       INTEGER PRIMARY KEY AUTOINCREMENT,
    clinic_id   INTEGER NOT NULL REFERENCES clinic(clinic_id),
    catalog_id  INTEGER NOT NULL REFERENCES treatment_catalog(catalog_id),
    price_cents INTEGER NOT NULL,
    UNIQUE (clinic_id, catalog_id)
);

CREATE TABLE clinic_quota (
    quota_id    INTEGER PRIMARY KEY AUTOINCREMENT,
    clinic_id   INTEGER NOT NULL REFERENCES clinic(clinic_id),
    catalog_id  INTEGER NOT NULL REFERENCES treatment_catalog(catalog_id),
    authorized  INTEGER DEFAULT 1,
    monthly_quota INTEGER DEFAULT 0,
    UNIQUE (clinic_id, catalog_id)
);

-- ---------------------------------------------------------------------
-- 域二：患者与会员
-- ---------------------------------------------------------------------
CREATE TABLE patient (
    patient_id   INTEGER PRIMARY KEY AUTOINCREMENT,
    name         TEXT NOT NULL,
    gender       TEXT,
    birth_date   TEXT,
    phone        TEXT,
    email        TEXT,
    address      TEXT,
    source       TEXT DEFAULT '到店',       -- 到店 / 小程序 / 转介绍
    openid       TEXT UNIQUE,
    real_name_ok INTEGER DEFAULT 0,
    no_show_cnt  INTEGER DEFAULT 0,
    status       TEXT DEFAULT '正常',
    created_at   TEXT
);

CREATE TABLE allergy (
    allergy_id  INTEGER PRIMARY KEY AUTOINCREMENT,
    patient_id  INTEGER NOT NULL REFERENCES patient(patient_id),
    allergen    TEXT NOT NULL,              -- 乳胶 / 麻醉剂 / 金属 / 树脂 / 青霉素 / 磺胺 / 其他
    note        TEXT,
    created_at  TEXT
);

CREATE TABLE medical_history (
    history_id  INTEGER PRIMARY KEY AUTOINCREMENT,
    patient_id  INTEGER NOT NULL REFERENCES patient(patient_id),
    item        TEXT,                       -- 高血压 / 糖尿病 / 心脏病 / 凝血异常 …
    note        TEXT,
    recorded_at TEXT
);

CREATE TABLE patient_contact (
    contact_id  INTEGER PRIMARY KEY AUTOINCREMENT,
    patient_id  INTEGER NOT NULL REFERENCES patient(patient_id),
    name        TEXT,
    relation    TEXT,
    phone       TEXT
);

CREATE TABLE member (
    member_id     INTEGER PRIMARY KEY AUTOINCREMENT,
    patient_id    INTEGER NOT NULL UNIQUE REFERENCES patient(patient_id),
    level         TEXT DEFAULT '普通',      -- 普通 / 银卡 / 金卡 / 白金
    points        INTEGER DEFAULT 0,
    balance_cents INTEGER DEFAULT 0,
    joined_at     TEXT
);

CREATE TABLE member_transaction (
    mt_id          INTEGER PRIMARY KEY AUTOINCREMENT,
    member_id      INTEGER NOT NULL REFERENCES member(member_id),
    kind           TEXT,                    -- 积分入账 / 积分抵扣 / 充值 / 消费 / 退款扣回
    points         INTEGER DEFAULT 0,
    amount_cents   INTEGER DEFAULT 0,
    balance_after  INTEGER DEFAULT 0,
    ref            TEXT,
    created_at     TEXT
);

CREATE TABLE coupon (
    coupon_id   INTEGER PRIMARY KEY AUTOINCREMENT,
    member_id   INTEGER REFERENCES member(member_id),
    code        TEXT UNIQUE NOT NULL,
    title       TEXT,
    amount_cents INTEGER DEFAULT 0,
    scope       TEXT,
    status      TEXT DEFAULT '未使用',      -- 未使用 / 已使用 / 已过期
    expire_at   TEXT
);

-- ---------------------------------------------------------------------
-- 域三：排班与号源
-- ---------------------------------------------------------------------
CREATE TABLE shift (
    shift_id    INTEGER PRIMARY KEY AUTOINCREMENT,
    duty_id     INTEGER REFERENCES duty(duty_id),
    dentist_id  INTEGER NOT NULL REFERENCES dentist(dentist_id),
    clinic_id   INTEGER NOT NULL REFERENCES clinic(clinic_id),
    chair_id    INTEGER NOT NULL REFERENCES chair(chair_id),
    shift_date  TEXT NOT NULL,
    start_time  TEXT NOT NULL,              -- HH:MM
    end_time    TEXT NOT NULL,
    slot_count  INTEGER DEFAULT 8,
    ampm        TEXT,                       -- 上午 / 下午 / 晚班
    status      TEXT DEFAULT '草稿',        -- 草稿 / 已发布 / 停诊
    created_by  TEXT,
    created_at  TEXT
);

CREATE TABLE slot (
    slot_id    INTEGER PRIMARY KEY AUTOINCREMENT,
    shift_id   INTEGER NOT NULL REFERENCES shift(shift_id),
    seq        INTEGER NOT NULL,
    start_time TEXT NOT NULL,
    end_time   TEXT NOT NULL,
    status     TEXT DEFAULT '空闲',         -- 空闲 / 已占 / 停诊释放
    -- 一个就诊占用连续 N 片，故 visit_id 不设唯一；防重复占用由
    -- “UPDATE … WHERE visit_id IS NULL” 的条件更新 + (shift_id,seq) 唯一约束共同保证
    visit_id   INTEGER REFERENCES visit(visit_id),
    UNIQUE (shift_id, seq)
);

CREATE TABLE waitlist (
    wait_id    INTEGER PRIMARY KEY AUTOINCREMENT,
    patient_id INTEGER NOT NULL REFERENCES patient(patient_id),
    shift_id   INTEGER NOT NULL REFERENCES shift(shift_id),
    catalog_id INTEGER REFERENCES treatment_catalog(catalog_id),
    status     TEXT DEFAULT '候补中',       -- 候补中 / 已转正 / 已放弃
    visit_id   INTEGER REFERENCES visit(visit_id),
    created_at TEXT
);

-- ---------------------------------------------------------------------
-- 域四：就诊与临床病历
-- ---------------------------------------------------------------------
CREATE TABLE visit (
    visit_id     INTEGER PRIMARY KEY AUTOINCREMENT,
    patient_id   INTEGER NOT NULL REFERENCES patient(patient_id),
    dentist_id   INTEGER NOT NULL REFERENCES dentist(dentist_id),
    clinic_id    INTEGER NOT NULL REFERENCES clinic(clinic_id),
    chair_id     INTEGER REFERENCES chair(chair_id),
    visit_date   TEXT NOT NULL,
    start_time   TEXT NOT NULL,
    end_time     TEXT,
    slots        INTEGER DEFAULT 1,
    source       TEXT DEFAULT '到店',       -- 到店 / 在线 / 电话
    status       TEXT DEFAULT '待就诊',     -- 待就诊/已完成/待支付/已结算/已退款/已取消
    cancel_type  TEXT,                      -- 主动取消 / 停诊取消 / 爽约
    special_note TEXT,
    is_arrived   INTEGER DEFAULT 0,
    created_at   TEXT,
    cancelled_at TEXT
);

CREATE TABLE visit_treatment (
    vt_id            INTEGER PRIMARY KEY AUTOINCREMENT,
    visit_id         INTEGER NOT NULL REFERENCES visit(visit_id),
    catalog_id       INTEGER NOT NULL REFERENCES treatment_catalog(catalog_id),
    name_snapshot    TEXT,
    qty              REAL DEFAULT 1,
    unit_price_cents INTEGER NOT NULL,
    amount_cents     INTEGER NOT NULL,
    recall_weeks     INTEGER DEFAULT 0,
    created_by       TEXT,
    created_at       TEXT
);

CREATE TABLE treatment_record (
    record_id      INTEGER PRIMARY KEY AUTOINCREMENT,
    visit_id       INTEGER NOT NULL REFERENCES visit(visit_id),
    chief_complaint TEXT,
    exam_note      TEXT,
    diagnosis      TEXT,
    created_by     TEXT,
    created_at     TEXT,
    locked         INTEGER DEFAULT 0
);

CREATE TABLE tooth_condition (
    tooth_id    INTEGER PRIMARY KEY AUTOINCREMENT,
    record_id   INTEGER NOT NULL REFERENCES treatment_record(record_id),
    fdi         TEXT NOT NULL,              -- 11 ~ 48
    status      TEXT,                       -- 龋 / 缺失 / 修复体 / 种植 / 隐裂 / 正常
    note        TEXT,
    recorded_at TEXT
);

CREATE TABLE tooth_surface (
    surface_id INTEGER PRIMARY KEY AUTOINCREMENT,
    tooth_id   INTEGER NOT NULL REFERENCES tooth_condition(tooth_id),
    surface    TEXT NOT NULL,               -- 近中 / 远中 / 颊 / 舌 / 咬合
    status     TEXT DEFAULT '受累'
);

CREATE TABLE perio_exam (
    perio_id   INTEGER PRIMARY KEY AUTOINCREMENT,
    tooth_id   INTEGER NOT NULL REFERENCES tooth_condition(tooth_id),
    pd1 INTEGER, pd2 INTEGER, pd3 INTEGER,
    pd4 INTEGER, pd5 INTEGER, pd6 INTEGER,
    cal INTEGER, mobility INTEGER, bleeding INTEGER DEFAULT 0
);

CREATE TABLE treatment_plan (
    plan_id    INTEGER PRIMARY KEY AUTOINCREMENT,
    visit_id   INTEGER NOT NULL REFERENCES visit(visit_id),
    stage      TEXT DEFAULT '一期',         -- 一期 / 二期 / 三期
    status     TEXT DEFAULT '计划',         -- 计划 / 进行 / 完成
    note       TEXT,
    created_at TEXT
);

CREATE TABLE plan_item (
    item_id    INTEGER PRIMARY KEY AUTOINCREMENT,
    plan_id    INTEGER NOT NULL REFERENCES treatment_plan(plan_id),
    fdi        TEXT,
    catalog_id INTEGER REFERENCES treatment_catalog(catalog_id),
    status     TEXT DEFAULT '计划',
    note       TEXT,
    auto_flag  INTEGER DEFAULT 0            -- 1=PD≥4 自动生成
);

CREATE TABLE prescription (
    rx_id      INTEGER PRIMARY KEY AUTOINCREMENT,
    record_id  INTEGER NOT NULL REFERENCES treatment_record(record_id),
    doctor_id  INTEGER REFERENCES dentist(dentist_id),
    status     TEXT DEFAULT '已开立',
    note       TEXT,
    created_at TEXT
);

CREATE TABLE prescription_item (
    rx_item_id      INTEGER PRIMARY KEY AUTOINCREMENT,
    rx_id           INTEGER NOT NULL REFERENCES prescription(rx_id),
    drug            TEXT NOT NULL,
    dose            TEXT,
    usage           TEXT,
    is_narcotic     INTEGER DEFAULT 0,
    register_no     TEXT,
    double_check_by TEXT
);

CREATE TABLE imaging (
    image_id     INTEGER PRIMARY KEY AUTOINCREMENT,
    record_id    INTEGER NOT NULL REFERENCES treatment_record(record_id),
    fdi          TEXT,
    type         TEXT,                      -- 口内照 / 根尖片 / 全景片 / CBCT
    storage_path TEXT,
    finding      TEXT,
    taken_at     TEXT
);

CREATE TABLE consent (
    consent_id  INTEGER PRIMARY KEY AUTOINCREMENT,
    record_id   INTEGER NOT NULL REFERENCES treatment_record(record_id),
    template    TEXT,
    version     TEXT,
    signed_by   TEXT,
    signature   TEXT,
    signed_at   TEXT,
    UNIQUE (record_id, template)
);

CREATE TABLE sterilization_pack (
    pack_id      INTEGER PRIMARY KEY AUTOINCREMENT,
    clinic_id    INTEGER NOT NULL REFERENCES clinic(clinic_id),
    pack_no      TEXT NOT NULL,
    batch_no     TEXT,
    sterilized_at TEXT,
    expire_at    TEXT,
    status       TEXT DEFAULT '可用'        -- 可用 / 已领用 / 过期
);

CREATE TABLE pack_trace (
    trace_id   INTEGER PRIMARY KEY AUTOINCREMENT,
    pack_id    INTEGER NOT NULL REFERENCES sterilization_pack(pack_id),
    visit_id   INTEGER REFERENCES visit(visit_id),
    used_at    TEXT,
    operator   TEXT
);

-- ---------------------------------------------------------------------
-- 域五：结算与财务
-- ---------------------------------------------------------------------
CREATE TABLE invoice (
    invoice_id      INTEGER PRIMARY KEY AUTOINCREMENT,
    invoice_no      TEXT UNIQUE NOT NULL,
    visit_id        INTEGER UNIQUE NOT NULL REFERENCES visit(visit_id),
    total_cents     INTEGER DEFAULT 0,
    paid_cents      INTEGER DEFAULT 0,
    deposit_cents   INTEGER DEFAULT 0,      -- 已收定金（同一张单，见 4.4）
    discount_rate   REAL DEFAULT 0,
    status          TEXT DEFAULT '待支付',  -- 待支付/已结算/部分退款/全额退款
    kind            TEXT DEFAULT '结算单',  -- 结算单 / 定金单（同一张单的不同阶段标注）
    is_invoiced     INTEGER DEFAULT 0,      -- 1=已开电子发票
    invoice_title   TEXT,
    created_at      TEXT,
    settled_at      TEXT
);

CREATE TABLE invoice_line (
    line_id          INTEGER PRIMARY KEY AUTOINCREMENT,
    invoice_id       INTEGER NOT NULL REFERENCES invoice(invoice_id),
    name             TEXT NOT NULL,         -- 快照：治疗名称
    qty              REAL DEFAULT 1,
    unit_price_cents INTEGER NOT NULL,
    amount_cents     INTEGER NOT NULL,
    kind             TEXT DEFAULT '治疗'    -- 治疗 / 定金抵扣 / 折扣 / 会员抵扣
);

CREATE TABLE payment_transaction (
    pay_id         INTEGER PRIMARY KEY AUTOINCREMENT,
    pay_no         TEXT UNIQUE NOT NULL,
    invoice_id     INTEGER NOT NULL REFERENCES invoice(invoice_id),
    amount_cents   INTEGER NOT NULL,
    method         TEXT NOT NULL,           -- 微信支付 / 现金 / 刷卡
    status         TEXT DEFAULT '待支付',   -- 待支付/成功/失败/已关闭
    third_party_no TEXT UNIQUE,
    idem_key       TEXT UNIQUE,
    operator       TEXT,
    created_at     TEXT,
    finished_at    TEXT
);

CREATE TABLE refund (
    refund_id   INTEGER PRIMARY KEY AUTOINCREMENT,
    refund_no   TEXT UNIQUE NOT NULL,
    pay_id      INTEGER NOT NULL REFERENCES payment_transaction(pay_id),
    amount_cents INTEGER NOT NULL,
    reason      TEXT,
    status      TEXT DEFAULT '待审核',      -- 待审核/退回中/已退回/失败
    approver    TEXT,
    channel     TEXT DEFAULT '原路退回',
    created_at  TEXT,
    finished_at TEXT
);

CREATE TABLE invoice_red (
    red_id      INTEGER PRIMARY KEY AUTOINCREMENT,
    invoice_id  INTEGER NOT NULL REFERENCES invoice(invoice_id),
    red_no      TEXT UNIQUE NOT NULL,
    amount_cents INTEGER NOT NULL,
    reason      TEXT,
    operator    TEXT,
    created_at  TEXT
);

CREATE TABLE discount_approval (
    disc_id    INTEGER PRIMARY KEY AUTOINCREMENT,
    invoice_id INTEGER NOT NULL REFERENCES invoice(invoice_id),
    rate       REAL NOT NULL,
    applicant  TEXT,
    apply_role TEXT,
    status     TEXT DEFAULT '待审批',       -- 待审批 / 已通过 / 已驳回
    approver   TEXT,
    reason     TEXT,
    created_at TEXT,
    decided_at TEXT
);

CREATE TABLE installment_plan (
    inst_plan_id INTEGER PRIMARY KEY AUTOINCREMENT,
    plan_no      TEXT UNIQUE NOT NULL,
    patient_id   INTEGER NOT NULL REFERENCES patient(patient_id),
    visit_id     INTEGER REFERENCES visit(visit_id),
    mode         TEXT DEFAULT '分期',       -- 套餐 / 次卡 / 储值 / 分期
    total_cents  INTEGER NOT NULL,
    down_cents   INTEGER NOT NULL,
    periods      INTEGER NOT NULL,
    per_cents    INTEGER NOT NULL,
    status       TEXT DEFAULT '待支付',     -- 待支付/已生效/已结清/已终止
    signed       INTEGER DEFAULT 0,
    created_at   TEXT,
    expire_at    TEXT
);

CREATE TABLE installment (
    inst_id     INTEGER PRIMARY KEY AUTOINCREMENT,
    plan_id     INTEGER NOT NULL REFERENCES installment_plan(inst_plan_id),
    seq         INTEGER NOT NULL,
    due_date    TEXT NOT NULL,
    amount_cents INTEGER NOT NULL,
    status      TEXT DEFAULT '待付',        -- 待付 / 已付 / 逾期 / 已退
    pay_no      TEXT,
    retry_count INTEGER DEFAULT 0,
    UNIQUE (plan_id, seq)
);

CREATE TABLE price_package (
    package_id         INTEGER PRIMARY KEY AUTOINCREMENT,
    name               TEXT NOT NULL,
    kind               TEXT DEFAULT '套餐', -- 套餐 / 次卡 / 储值
    price_cents        INTEGER NOT NULL,
    catalog_total_cents INTEGER,
    status             TEXT DEFAULT '启用'
);

CREATE TABLE package_item (
    pkg_item_id INTEGER PRIMARY KEY AUTOINCREMENT,
    package_id  INTEGER NOT NULL REFERENCES price_package(package_id),
    catalog_id  INTEGER NOT NULL REFERENCES treatment_catalog(catalog_id),
    times       INTEGER DEFAULT 1
);

CREATE TABLE prepaid_card (
    card_id       INTEGER PRIMARY KEY AUTOINCREMENT,
    patient_id    INTEGER NOT NULL REFERENCES patient(patient_id),
    card_no       TEXT UNIQUE NOT NULL,
    balance_cents INTEGER DEFAULT 0,
    status        TEXT DEFAULT '正常'
);

CREATE TABLE card_transaction (
    card_txn_id      INTEGER PRIMARY KEY AUTOINCREMENT,
    card_id          INTEGER NOT NULL REFERENCES prepaid_card(card_id),
    kind             TEXT,                  -- 充值 / 核销
    amount_cents     INTEGER NOT NULL,
    balance_after_cents INTEGER,
    ref              TEXT,
    created_at       TEXT
);

CREATE TABLE case_cost (
    cost_id    INTEGER PRIMARY KEY AUTOINCREMENT,
    visit_id   INTEGER NOT NULL REFERENCES visit(visit_id),
    item_name  TEXT,
    qty        REAL DEFAULT 1,
    batch_no   TEXT,
    unit_cost_cents INTEGER,
    amount_cents INTEGER,
    created_at TEXT
);

CREATE TABLE revenue_share (
    share_id   INTEGER PRIMARY KEY AUTOINCREMENT,
    invoice_id INTEGER NOT NULL REFERENCES invoice(invoice_id),
    clinic_id  INTEGER NOT NULL REFERENCES clinic(clinic_id),
    dentist_id INTEGER REFERENCES dentist(dentist_id),
    kind       TEXT,                        -- 收款归属 / 业绩归属
    amount_cents INTEGER NOT NULL,
    created_at TEXT
);

CREATE TABLE daily_revenue (
    revenue_id       INTEGER PRIMARY KEY AUTOINCREMENT,
    clinic_id        INTEGER NOT NULL REFERENCES clinic(clinic_id),
    rev_date         TEXT NOT NULL,
    receivable_cents INTEGER DEFAULT 0,
    received_cents   INTEGER DEFAULT 0,
    refund_cents     INTEGER DEFAULT 0,
    diff_cents       INTEGER DEFAULT 0,
    created_at       TEXT,
    UNIQUE (clinic_id, rev_date)
);

CREATE TABLE quarterly_performance (
    perf_id       INTEGER PRIMARY KEY AUTOINCREMENT,
    dentist_id    INTEGER NOT NULL REFERENCES dentist(dentist_id),
    year          INTEGER NOT NULL,
    quarter       INTEGER NOT NULL,
    revenue_cents INTEGER DEFAULT 0,
    material_cents INTEGER DEFAULT 0,
    expense_cents INTEGER DEFAULT 0,
    profit_cents  INTEGER DEFAULT 0,
    fund_cents    INTEGER DEFAULT 0,        -- 激励基金 = 净利润 × 10%
    created_at    TEXT,
    UNIQUE (dentist_id, year, quarter)
);

CREATE TABLE expense (
    expense_id   INTEGER PRIMARY KEY AUTOINCREMENT,
    clinic_id    INTEGER NOT NULL REFERENCES clinic(clinic_id),
    month        TEXT NOT NULL,
    item         TEXT,
    amount_cents INTEGER NOT NULL
);

-- ---------------------------------------------------------------------
-- 域六：运营、通知与审计
-- ---------------------------------------------------------------------
CREATE TABLE online_booking (
    booking_id  INTEGER PRIMARY KEY AUTOINCREMENT,
    booking_no  TEXT UNIQUE NOT NULL,
    patient_id  INTEGER NOT NULL REFERENCES patient(patient_id),
    catalog_id  INTEGER NOT NULL REFERENCES treatment_catalog(catalog_id),
    clinic_id   INTEGER NOT NULL REFERENCES clinic(clinic_id),
    visit_id    INTEGER UNIQUE REFERENCES visit(visit_id),
    want_date   TEXT,
    want_time   TEXT,
    status      TEXT DEFAULT '待确认',      -- 待确认/已确认/已取消/已过期
    created_at  TEXT,
    expire_at   TEXT
);

CREATE TABLE recall_plan (
    recall_id   INTEGER PRIMARY KEY AUTOINCREMENT,
    visit_id    INTEGER REFERENCES visit(visit_id),
    patient_id  INTEGER NOT NULL REFERENCES patient(patient_id),
    catalog_id  INTEGER REFERENCES treatment_catalog(catalog_id),
    due_date    TEXT NOT NULL,
    status      TEXT DEFAULT '待提醒',      -- 待提醒 / 已提醒 / 已预约 / 已逾期 / 已完成
    notified_at TEXT,
    channel     TEXT
);

CREATE TABLE notification_log (
    notify_id  INTEGER PRIMARY KEY AUTOINCREMENT,
    visit_id   INTEGER REFERENCES visit(visit_id),
    patient_id INTEGER REFERENCES patient(patient_id),
    template   TEXT,
    content    TEXT,
    channel    TEXT DEFAULT '服务号订阅消息',
    status     TEXT DEFAULT '已发送',
    created_at TEXT
);

CREATE TABLE audit_log (
    log_id     INTEGER PRIMARY KEY AUTOINCREMENT,
    account_id INTEGER,
    actor      TEXT,
    role       TEXT,
    action     TEXT NOT NULL,
    target     TEXT,
    before_json TEXT,
    after_json TEXT,
    ip         TEXT,
    created_at TEXT
);

-- ---------------------------------------------------------------------
-- 索引（按 4.10 性能对策：筛选走索引）
-- ---------------------------------------------------------------------
CREATE INDEX idx_slot_shift       ON slot(shift_id, seq);
CREATE INDEX idx_slot_status      ON slot(status);
CREATE INDEX idx_slot_visit       ON slot(visit_id);
CREATE INDEX idx_visit_date       ON visit(visit_date, status);
CREATE INDEX idx_visit_dentist    ON visit(dentist_id, visit_date);
CREATE INDEX idx_visit_patient    ON visit(patient_id);
CREATE INDEX idx_invoice_visit    ON invoice(visit_id);
CREATE INDEX idx_pay_invoice      ON payment_transaction(invoice_id);
CREATE INDEX idx_shift_date       ON shift(clinic_id, shift_date, status);
CREATE INDEX idx_catalog_cat      ON treatment_catalog(category_id);
CREATE INDEX idx_recall_due       ON recall_plan(due_date, status);
CREATE INDEX idx_audit_time       ON audit_log(created_at);
