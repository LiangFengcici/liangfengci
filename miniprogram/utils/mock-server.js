/**
 * 离线演示模式 · 虚拟后端
 * ---------------------------------------------
 * 当真机/体验版访问不到后端时（config.fallbackMock = true），
 * 所有请求自动落到这里：用 mock-data.js 的真实导出数据 + 内存状态，
 * 让预约全流程（浏览 → 选医生 → 选时段 → 下单 → 支付 → 取消/改期 → 账单/会员/报告）完整可走。
 *
 * 数据保存在内存，杀掉小程序即重置 —— 演示友好，不产生真实数据。
 */
const DB = require('./mock-data')

const now = () => new Date().toISOString().slice(0, 19)
const today = () => new Date().toISOString().slice(0, 10)

function dateAfter(days) {
  const d = new Date()
  d.setDate(d.getDate() + days)
  return d.toISOString().slice(0, 10)
}

/** 组装 {code, message, data} —— 与后端响应体一致 */
function ok(data, code = 0, message = 'ok') {
  return Promise.resolve({ code, message, data, trace_id: 'MOCK' })
}

function bad(message, code = 422) {
  return Promise.resolve({ code, message, data: null, trace_id: 'MOCK' })
}

// ---------------------------------------------------------------- 内存状态
const PATIENT = {
  patient_id: 1, name: '周若彤', gender: '女', phone: '138****6201',
  allergies: ['青霉素']
}

const state = {
  seq: 100,
  bookings: [
    {
      visit_id: 1, visit_date: today(), start_time: '09:30', end_time: '10:30',
      status: '待就诊', source: '在线', dentist_name: '张明远', clinic_name: '中山路旗舰诊所',
      total_cents: 150000, paid_cents: 15000, invoice_id: 1,
      item_name: '根管治疗（磨牙）'
    },
    {
      visit_id: 2, visit_date: dateAfter(-10), start_time: '10:00', end_time: '10:30',
      status: '已结算', source: '到店', dentist_name: '王振宇', clinic_name: '高新园区诊所',
      total_cents: 28000, paid_cents: 28000, invoice_id: 2,
      item_name: '超声波洁治'
    }
  ],
  invoices: [
    {
      invoice_id: 1, invoice_no: 'INVMOCK0001', kind: '结算单', status: '待支付',
      visit_id: 1, visit_date: today(), dentist_name: '张明远',
      total_cents: 150000, paid_cents: 15000,
      lines: [{ name: '根管治疗（磨牙）', qty: 1, amount_cents: 150000 }]
    },
    {
      invoice_id: 2, invoice_no: 'INVMOCK0002', kind: '结算单', status: '已结算',
      visit_id: 2, visit_date: dateAfter(-10), dentist_name: '王振宇',
      total_cents: 28000, paid_cents: 28000,
      lines: [{ name: '超声波洁治', qty: 1, amount_cents: 28000 }]
    }
  ]
}

// ---------------------------------------------------------------- 各接口实现
function allItems() {
  const rows = []
  DB.catalog.forEach(cat => cat.items.forEach(it => rows.push(it)))
  return rows
}

function itemById(id) {
  return allItems().find(it => it.catalog_id === Number(id))
}

function genNo(prefix) {
  state.seq += 1
  return prefix + now().replace(/[-:T]/g, '').slice(0, 14) + String(state.seq)
}

function apiCatalog() {
  return ok(DB.catalog.map(cat => ({
    category_id: cat.category_id, name: cat.name, intro: cat.intro, items: cat.items
  })))
}

function apiDentists(qs) {
  const cid = Number(qs.catalog_id || 0)
  const item = itemById(cid)
  // 演示版资质过滤：根管/种植类只展示具备相应资质的医生
  const needImplant = item && /种植/.test(item.name)
  const needEndo = item && /根管/.test(item.name)
  const list = DB.dentists
    .filter(d => !(needImplant || needEndo) ||
      d.quals.some(q => needImplant ? /种植/.test(q) : /颌面外科|根管/.test(q)))
    .map(d => ({
      dentist_id: d.dentist_id, name: d.name, title: d.title,
      quals: d.quals, intro: d.intro,
      clinic_name: d.clinic, earliest: '09:00', free_windows: 12
    }))
  return ok(list)
}

function apiAvailability(qs) {
  const did = Number(qs.dentist_id || 0)
  const doc = DB.dentists.find(d => d.dentist_id === did) || DB.dentists[0]
  const win = []
  let h = 9, m = 0
  while (h < 17 || (h === 17 && m === 0)) {
    const start = ('0' + h).slice(-2) + ':' + ('0' + m).slice(-2)
    const endMin = m + 30
    const end = ('0' + (h + Math.floor(endMin / 60))).slice(-2) + ':' + ('0' + (endMin % 60)).slice(-2)
    // 已约时段不再展示
    const taken = state.bookings.some(b =>
      b.dentist_name === doc.name && b.visit_date === qs.date && b.start_time === start &&
      b.status !== '已取消')
    if (!taken) {
      win.push({
        clinic_id: 1, clinic_name: doc.clinic, dentist_id: doc.dentist_id,
        dentist_name: doc.name, shift_id: 1, start_time: start, end_time: end,
        slots: 1, slot_ids: [1], chair_name: '演示椅位', title: doc.title
      })
    }
    m += 30
    if (m >= 60) { m = 0; h += 1 }
  }
  return ok(win)
}

function apiBooking(body) {
  const item = itemById(body.catalog_id)
  if (!item) return bad('项目不存在', 404)
  const doc = DB.dentists.find(d => d.dentist_id === Number(body.dentist_id)) || DB.dentists[0]
  const dup = state.bookings.find(b =>
    b.visit_date === body.date && b.start_time === body.start_time && b.status !== '已取消')
  if (dup) return bad('该时段已无可约号源，请返回重新选择', 409)

  state.seq += 1
  const vid = state.seq
  const dep = Math.max(Math.round(item.price_cents * 0.1), 5000)
  state.seq += 1
  const invId = state.seq

  state.bookings.unshift({
    visit_id: vid, visit_date: body.date, start_time: body.start_time,
    end_time: body.end_time || body.start_time, status: '待支付',
    source: '在线', dentist_name: doc.name, clinic_name: doc.clinic,
    total_cents: item.price_cents, paid_cents: 0, invoice_id: invId,
    item_name: item.name
  })
  state.invoices.unshift({
    invoice_id: invId, invoice_no: genNo('INV'), kind: '定金单', status: '待支付',
    visit_id: vid, visit_date: body.date, dentist_name: doc.name,
    total_cents: dep, paid_cents: 0,
    lines: [{ name: item.name + '（定金）', qty: 1, amount_cents: dep }]
  })
  return ok({
    visit_id: vid,
    message: '预约成功（离线演示）',
    deposit_invoice: { invoice_id: invId, invoice_no: genNo('DEP'), total_cents: dep }
  })
}

function apiPay(body) {
  const inv = state.invoices.find(i => i.invoice_id === Number(body.invoice_id))
  if (!inv) return bad('结算单不存在', 404)
  const payId = ++state.seq
  inv.paid_cents = inv.total_cents
  inv.status = inv.kind === '定金单' ? '定金已付' : '已结算'
  const bk = state.bookings.find(b => b.visit_id === inv.visit_id)
  if (bk) {
    bk.paid_cents = inv.total_cents
    if (bk.total_cents <= bk.paid_cents) bk.status = '待就诊'
  }
  return ok({
    duplicated: false, pay_id: payId, pay_no: genNo('DEP'), status: inv.status,
    paid_cents: inv.paid_cents, total_cents: inv.total_cents,
    pay_params: { timeStamp: '', nonceStr: '', package: '', paySign: 'MOCK' }
  })
}

function apiCancel(id) {
  const bk = state.bookings.find(b => b.visit_id === Number(id))
  if (!bk) return bad('预约不存在', 404)
  bk.status = '已取消'
  const hours = (new Date(bk.visit_date + 'T' + bk.start_time) - Date.now()) / 3600000
  const rate = hours > 24 ? 1 : 0.5
  const inv = state.invoices.find(i => i.invoice_id === bk.invoice_id)
  const refund = Math.round((inv ? inv.paid_cents : 0) * rate)
  if (inv && refund > 0) inv.status = '部分退款'
  return ok({ refund_cents: refund, message: '已取消并按规则退回定金' })
}

function apiReschedule(id, body) {
  const bk = state.bookings.find(b => b.visit_id === Number(id))
  if (!bk) return bad('预约不存在', 404)
  bk.visit_date = body.date || bk.visit_date
  bk.start_time = body.start_time || bk.start_time
  return ok({ message: '改期成功（离线演示）' })
}

function apiBookings() {
  return ok(state.bookings.map(b => ({ ...b })))
}

function apiBills() {
  return ok({
    invoices: state.invoices.map(i => ({ ...i })),
    plans: [{
      inst_plan_id: 1, plan_no: 'IPMOCK0001', mode: '分期', periods: 6,
      total_cents: 880000, down_cents: 264000, per_cents: 102666, status: '已生效'
    }]
  })
}

function apiMember() {
  return ok({
    level: '普通', points: 980, balance_cents: 50000,
    coupons: [
      { code: 'NEW2026', title: '新客洁治 5 折券', scope: '洁治', expire_at: dateAfter(30), amount_cents: 14000, status: '未使用' },
      { code: 'BDAY11', title: '生日 8 折券', scope: '全项目', expire_at: dateAfter(60), amount_cents: 5600, status: '未使用' }
    ]
  })
}

function apiReports() {
  return ok([
    {
      image_id: 1, fdi: '16', type: '根尖片',
      finding: '16 根尖周未见低密度影', taken_at: dateAfter(-10) + 'T10:05:00',
      visit_date: dateAfter(-10), dentist_name: '王振宇'
    }
  ])
}

// ---------------------------------------------------------------- 路由分发
function handle(path, method, body) {
  const [clean, qsRaw] = String(path).split('?')
  const qs = {};
  (qsRaw || '').split('&').filter(Boolean).forEach(kv => {
    const [k, v] = kv.split('=')
    qs[k] = decodeURIComponent(v || '')
  })
  const seg = clean.replace(/\/$/, '').split('/').filter(Boolean) // ['api','booking','3','cancel']

  if (seg[0] !== 'api') return bad('离线模式不支持的请求：' + path, 404)

  if (seg[1] === 'login') {
    return ok({
      token: 'mock-token-offline', patient: PATIENT, allergies: PATIENT.allergies
    })
  }
  if (seg[1] === 'catalog') return apiCatalog()
  if (seg[1] === 'dentists') return apiDentists(qs)
  if (seg[1] === 'availability') return apiAvailability(qs)
  if (seg[1] === 'bookings') return apiBookings()
  if (seg[1] === 'bills') return apiBills()
  if (seg[1] === 'member') return apiMember()
  if (seg[1] === 'reports') return apiReports()

  if (seg[1] === 'booking' && method === 'POST' && seg.length === 2) return apiBooking(body || {})
  if (seg[1] === 'booking' && seg[3] === 'cancel') return apiCancel(seg[2])
  if (seg[1] === 'booking' && seg[3] === 'reschedule') return apiReschedule(seg[2], body || {})

  if (seg[1] === 'pay' && method === 'POST' && seg.length === 2) return apiPay(body || {})
  if (seg[1] === 'pay' && seg[2] === 'notify') return ok({ message: '回调已入账（离线演示）' })
  if (seg[1] === 'jobs' && seg[2] === 'run') return ok({ message: '定时任务已执行（离线演示）' })

  return bad('离线模式暂不支持：' + method + ' ' + path, 404)
}

module.exports = { handle, state, _reset: () => { state.bookings = []; state.invoices = [] } }
