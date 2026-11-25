const { post } = require('../../utils/request')
const { money } = require('../../utils/format')
const app = getApp()

const ALLERGENS = ['青霉素', '麻醉剂', '金属', '树脂', '乳胶', '磺胺']

Page({
  data: {
    form: {},
    priceText: '', depositText: '', deposit: 0,
    allergens: ALLERGENS,
    checked: [],
    note: '',
    submitting: false
  },

  onLoad(options) {
    const price = Number(options.price || 0)
    const deposit = Math.max(Math.round(price * 0.1), 5000)
    this.setData({
      form: {
        catalog_id: Number(options.catalog_id),
        dentist_id: Number(options.dentist_id),
        clinic_id: Number(options.clinic_id),
        date: options.day,
        start_time: options.start_time,
        dentist_name: decodeURIComponent(options.dentist_name || ''),
        clinic_name: decodeURIComponent(options.clinic_name || ''),
        item_name: decodeURIComponent(options.item_name || '')
      },
      priceText: money(price),
      depositText: money(deposit),
      deposit,
      checked: wx.getStorageSync('allergies') || []
    })
  },

  toggle(e) {
    const v = e.currentTarget.dataset.value
    const checked = this.data.checked.slice()
    const i = checked.indexOf(v)
    if (i >= 0) checked.splice(i, 1)
    else checked.push(v)
    this.setData({ checked })
  },

  onNote(e) {
    this.setData({ note: e.detail.value })
  },

  submit() {
    if (this.data.submitting) return
    this.setData({ submitting: true })
    wx.showLoading({ title: '正在锁号…', mask: true })
    const f = this.data.form
    const idem = 'MP' + Date.now()

    app.login().then(() => {
      // 先补录过敏史（逐项登记，随预约一起落库由后端校验）
      return post('/api/booking', {
        catalog_id: f.catalog_id,
        dentist_id: f.dentist_id,
        clinic_id: f.clinic_id,
        date: f.date,
        start_time: f.start_time,
        note: this.data.note,
        deposit: true,
        allergens: this.data.checked
      }, { 'Idempotency-Key': idem })
    }).then(res => {
      wx.hideLoading()
      const inv = res.deposit_invoice
      if (!inv) {
        wx.showModal({ title: '预约成功', content: '号源已锁定', showCancel: false })
        return wx.switchTab({ url: '/pages/bookings/bookings' })
      }
      return post('/api/pay', { invoice_id: inv.invoice_id, amount_cents: inv.total_cents })
        .then(pay => this.requestPay(pay, inv))
    }).catch(err => {
      wx.hideLoading()
      this.setData({ submitting: false })
      // 业务拒绝（409 余量不足 / 422 资质或过敏）已由 request.js 统一 toast
      console.warn(err)
    })
  },

  requestPay(pay, inv) {
    const params = pay.pay_params || {}
    wx.requestPayment({
      timeStamp: params.timeStamp,
      nonceStr: params.nonceStr,
      package: params.package,
      signType: 'RSA',
      paySign: params.paySign,
      success: () => {
        wx.showToast({ title: '支付成功', icon: 'success' })
        setTimeout(() => wx.switchTab({ url: '/pages/bookings/bookings' }), 800)
      },
      fail: () => {
        // 原型期未接入真实商户号，wx.requestPayment 必然失败：
        // 此时后端流水已按模拟通道入账，以前端提示引导用户查看预约
        wx.showModal({
          title: '预约已锁定',
          content: '定金 ¥' + (inv.total_cents / 100).toFixed(2) + ' 已按模拟通道记账，可在「我的预约」查看；正式环境此处拉起微信收银台。',
          showCancel: false,
          success: () => wx.switchTab({ url: '/pages/bookings/bookings' })
        })
      }
    })
  }
})
