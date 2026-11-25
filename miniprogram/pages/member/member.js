const { request } = require('../../utils/request')
const { money } = require('../../utils/format')
const app = getApp()

Page({
  data: { member: null, coupons: [], loading: true },

  onShow() { this.load() },
  onPullDownRefresh() { this.load().then(() => wx.stopPullDownRefresh()) },

  load() {
    const that = this
    return app.login()
      .then(() => Promise.all([
        request('/api/member'),
        request('/api/bills').catch(() => ({ invoices: [], plans: [] }))
      ]))
      .then(([m, bills]) => that.setData({
        member: Object.assign({}, m, { balanceText: money(m.balance_cents) }),
        coupons: (m.coupons || []).map(c => Object.assign({}, c, { amountText: money(c.amount_cents) })),
        unpaid: (bills.invoices || []).filter(i => i.status === '待支付').length,
        loading: false
      }))
      .catch(() => that.setData({ loading: false }))
  },

  goReport() { wx.navigateTo({ url: '/pages/report/report' }) },
  goBills() { wx.switchTab({ url: '/pages/bills/bills' }) }
})
