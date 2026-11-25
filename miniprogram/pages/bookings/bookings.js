const { request, post } = require('../../utils/request')
const { money, statusType } = require('../../utils/format')
const app = getApp()

Page({
  data: { rows: [], loading: true },

  onShow() { this.load() },

  onPullDownRefresh() { this.load().then(() => wx.stopPullDownRefresh()) },

  load() {
    const that = this
    return app.login().then(() => request('/api/bookings')).then(list => {
      const rows = (list || []).map(v => Object.assign({}, v, {
        statusType: statusType(v.status),
        totalText: money(v.total_cents),
        paidText: money(v.paid_cents),
        shortDate: (v.visit_date || '').slice(5)
      }))
      that.setData({ rows, loading: false })
    }).catch(() => that.setData({ loading: false }))
  },

  cancel(e) {
    const v = e.currentTarget.dataset.item
    wx.showModal({
      title: '取消预约',
      content: '取消会按 24 小时规则退回定金并释放号源，确认？',
      success: (r) => {
        if (!r.confirm) return
        post('/api/booking/' + v.visit_id + '/cancel').then(res => {
          wx.showToast({
            title: '已取消，退回 ¥' + (res.refund_cents / 100).toFixed(2),
            icon: 'none', duration: 2500
          })
          this.load()
        })
      }
    })
  },

  pay(e) {
    const v = e.currentTarget.dataset.item
    post('/api/pay', { invoice_id: v.invoice_id }).then(() => {
      wx.showToast({ title: '支付成功', icon: 'success' })
      this.load()
    })
  },

  goBook() { wx.switchTab({ url: '/pages/index/index' }) },

  goReport() { wx.navigateTo({ url: '/pages/report/report' }) }
})
