const { request } = require('../../utils/request')
const app = getApp()

Page({
  data: { rows: [], loading: true },

  onLoad() {
    const that = this
    app.login().then(() => request('/api/reports')).then(list => {
      that.setData({
        rows: (list || []).map(r => Object.assign({}, r, { dateText: (r.taken_at || '').replace('T', ' ').slice(0, 16) })),
        loading: false
      })
    }).catch(() => that.setData({ loading: false }))
  }
})
