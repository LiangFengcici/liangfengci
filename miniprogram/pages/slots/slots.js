const { request } = require('../../utils/request')
const { money } = require('../../utils/format')
const app = getApp()

Page({
  data: {
    catalogId: 0, dentistId: 0, dentistName: '', itemName: '', day: '',
    price: 0, deposit: 0, wins: [], selected: null, loading: true
  },

  onLoad(options) {
    const price = Number(options.price || 0)
    this.setData({
      catalogId: Number(options.catalog_id),
      dentistId: Number(options.dentist_id),
      dentistName: decodeURIComponent(options.dentist_name || ''),
      itemName: decodeURIComponent(options.item_name || ''),
      day: options.day,
      price,
      deposit: Math.max(Math.round(price * 0.1), 5000)
    })
    this.setData({ depositText: money(this.data.deposit), priceText: money(price) })
    this.load()
  },

  load() {
    const that = this
    app.login().then(() => request(
      '/api/availability?catalog_id=' + this.data.catalogId +
      '&dentist_id=' + this.data.dentistId + '&date=' + this.data.day
    )).then(list => that.setData({ wins: list || [], loading: false }))
      .catch(() => that.setData({ loading: false }))
  },

  pick(e) {
    this.setData({ selected: e.currentTarget.dataset.item })
  },

  next() {
    const w = this.data.selected
    if (!w) return wx.showToast({ title: '请先选择时段', icon: 'none' })
    wx.navigateTo({
      url: '/pages/confirm/confirm?catalog_id=' + this.data.catalogId +
        '&dentist_id=' + w.dentist_id +
        '&clinic_id=' + w.clinic_id +
        '&day=' + this.data.day +
        '&start_time=' + w.start_time +
        '&dentist_name=' + encodeURIComponent(this.data.dentistName) +
        '&clinic_name=' + encodeURIComponent(w.clinic_name) +
        '&item_name=' + encodeURIComponent(this.data.itemName) +
        '&price=' + this.data.price
    })
  }
})
