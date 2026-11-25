const { request } = require('../../utils/request')
const { money } = require('../../utils/format')
const app = getApp()

Page({
  data: { invoices: [], plans: [], loading: true },

  onShow() { this.load() },
  onPullDownRefresh() { this.load().then(() => wx.stopPullDownRefresh()) },

  load() {
    const that = this
    return app.login().then(() => request('/api/bills')).then(data => {
      const invoices = (data.invoices || []).map(inv => Object.assign({}, inv, {
        totalText: money(inv.total_cents),
        paidText: money(inv.paid_cents),
        remainText: money(inv.total_cents - inv.paid_cents),
        lines: (inv.lines || []).map(l => Object.assign({}, l, { amountText: money(l.amount_cents) }))
      }))
      const plans = (data.plans || []).map(p => Object.assign({}, p, {
        totalText: money(p.total_cents),
        downText: money(p.down_cents),
        perText: money(p.per_cents)
      }))
      that.setData({ invoices, plans, loading: false })
    }).catch(() => that.setData({ loading: false }))
  },

  payNow(e) {
    const inv = e.currentTarget.dataset.item
    wx.showModal({
      title: '在线支付',
      content: '应付 ' + money(inv.total_cents - inv.paid_cents) + '，确认支付？',
      success: (r) => {
        if (!r.confirm) return
        require('../../utils/request').post('/api/pay', { invoice_id: inv.invoice_id }).then(() => {
          wx.showToast({ title: '支付成功', icon: 'success' })
          this.load()
        })
      }
    })
  }
})
