const { request } = require('../../utils/request')
const { money, dateAdd } = require('../../utils/format')
const app = getApp()

Page({
  data: {
    catalogId: 0, itemName: '', price: 0, date: '',
    dates: [], cands: [], loading: true
  },

  onLoad(options) {
    const dates = []
    for (let i = 1; i <= 7; i++) {
      const d = dateAdd(i)
      dates.push({ date: d, label: d.slice(5), week: '周' + '日一二三四五六'[new Date(d).getDay()] })
    }
    this.setData({
      catalogId: Number(options.catalog_id),
      itemName: decodeURIComponent(options.name || ''),
      price: Number(options.price || 0),
      date: options.date || dates[0].date,
      dates
    })
    wx.setNavigationBarTitle({ title: this.data.itemName })
    this.load()
  },

  load() {
    const that = this
    app.login().then(() => request(
      '/api/dentists?catalog_id=' + this.data.catalogId + '&date=' + this.data.date
    )).then(list => {
      const cands = (list || []).map(d => Object.assign({}, d, {
        qualsText: (d.quals || []).join(' · ')
      }))
      that.setData({ cands, loading: false })
    }).catch(() => that.setData({ loading: false }))
  },

  pickDate(e) {
    this.setData({ date: e.currentTarget.dataset.date, loading: true })
    this.load()
  },

  goSlots(e) {
    const d = e.currentTarget.dataset.item
    wx.navigateTo({
      url: '/pages/slots/slots?catalog_id=' + this.data.catalogId +
        '&dentist_id=' + d.dentist_id +
        '&dentist_name=' + encodeURIComponent(d.name) +
        '&day=' + this.data.date +
        '&item_name=' + encodeURIComponent(this.data.itemName) +
        '&price=' + this.data.price
    })
  }
})
