const { request, ping } = require('../../utils/request')
const config = require('../../utils/config')
const { money, statusType } = require('../../utils/format')
const app = getApp()

const EMOJI = ['🦷', '✨', '🧩', '🩺', '👑', '🔩', '😁', '🧒']

Page({
  data: {
    patient: null,
    allergies: [],
    cats: [],
    upcoming: null,
    loading: true,
    mode: 'unknown'          // real = 已连诊所后台；offline = 离线演示
  },

  onShow() {
    this.loadAll()
  },

  onPullDownRefresh() {
    this.loadAll().then(() => wx.stopPullDownRefresh())
  },

  loadAll() {
    const that = this
    return app.login().then(() => {
      wx.setStorageSync('token', wx.getStorageSync('token'))
      that.setData({
        patient: app.globalData.patient,
        allergies: wx.getStorageSync('allergies') || []
      })
      return Promise.all([
        request('/api/catalog'),
        request('/api/bookings').catch(() => []),
        ping()
      ]).then(([cats, bookings, mode]) => {
        const list = (cats || []).map((c, i) => ({
          category_id: c.category_id,
          name: c.name,
          emoji: EMOJI[i] || '🦷',
          count: (c.items || []).length,
          from: (c.items || []).reduce((m, it) => Math.min(m, it.price_cents), 99999999)
        }))
        const next = (bookings || [])
          .filter(b => b.status === '待就诊' || b.status === '待支付')
          .sort((a, b) => (a.visit_date + a.start_time > b.visit_date + b.start_time ? 1 : -1))[0]
        if (next) {
          next.priceText = money(next.total_cents)
          next.statusType = statusType(next.status)
        }
        that.setData({ cats: list, upcoming: next || null, mode: mode || 'unknown', loading: false })
      })
    }).catch((err) => {
      that.setData({ loading: false, mode: 'offline' })
      console.error('[index] 数据加载失败：', err && err.errMsg ? err.errMsg : err)
    })
  },

  /** 点击状态条：显示当前接口地址与排查提示 */
  showMode() {
    wx.showModal({
      title: this.data.mode === 'real' ? '已连接诊所后台' : '离线演示模式',
      content: this.data.mode === 'real'
        ? '接口地址：' + config.baseUrl + '\n预约、支付等操作会写入电脑上的牙科平台，可在员工端看到。'
        : '接口地址：' + config.baseUrl +
          '\n\n未能访问该地址，已自动改用内置演示数据。\n排查：① 电脑上后端窗口是否在运行；② utils/config.js 的地址是否正确；③ 若走公网穿透，确认终端里显示的是 Running。',
      showCancel: false,
      confirmText: '知道了'
    })
  },

  goCategory(e) {
    const id = e.currentTarget.dataset.id
    wx.navigateTo({ url: '/pages/detail/detail?category_id=' + id })
  },

  goBookings() {
    wx.switchTab({ url: '/pages/bookings/bookings' })
  },

  goReport() {
    wx.navigateTo({ url: '/pages/report/report' })
  }
})
