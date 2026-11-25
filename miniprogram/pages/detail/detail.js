const { request } = require('../../utils/request')
const { money, dateAdd } = require('../../utils/format')
const app = getApp()

Page({
  data: { categoryId: 0, items: [], catName: '', loading: true },

  onLoad(options) {
    this.setData({ categoryId: Number(options.category_id || 1) })
    this.load()
  },

  load() {
    app.login().then(() => request('/api/catalog')).then(cats => {
      const cat = (cats || []).find(c => c.category_id === this.data.categoryId)
      if (!cat) return
      const items = (cat.items || []).map(it => Object.assign({}, it, {
        priceText: money(it.price_cents),
        minutes: it.duration_slots * 30,
        deposit: money(Math.max(Math.round(it.price_cents * 0.1), 5000))
      }))
      this.setData({ items, catName: cat.name, loading: false })
      wx.setNavigationBarTitle({ title: cat.name })
    })
  },

  goDentists(e) {
    const it = e.currentTarget.dataset.item
    wx.navigateTo({
      url: '/pages/dentists/dentists?catalog_id=' + it.catalog_id +
        '&name=' + encodeURIComponent(it.name) +
        '&price=' + it.price_cents +
        '&date=' + dateAdd(1)
    })
  }
})
