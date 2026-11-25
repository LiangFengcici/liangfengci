const config = require('./utils/config')
const { post } = require('./utils/request')

App({
  globalData: {
    token: '',
    patient: null,
    baseUrl: config.baseUrl
  },

  onLaunch() {
    this.login()
  },

  /**
   * 登录：wx.login 取 code → 后端 code2session 换 openid → 与患者档案一对一绑定。
   * 原型期后端使用模拟通道（config.useMockLogin = true），
   * 正式联调时把 useMockLogin 置 false，后端接真实 code2session 即可，页面代码零改动。
   * 走统一的 request 封装：接口不可达时自动降级到离线演示数据。
   */
  login() {
    return new Promise((resolve, reject) => {
      const cached = wx.getStorageSync(config.tokenKey)
      if (cached) {
        this.globalData.token = cached
        this.globalData.patient = wx.getStorageSync('patient') || null
        return resolve(cached)
      }
      const done = (code) => {
        post('/api/login', { code }).then(data => {
          this.globalData.token = data.token
          this.globalData.patient = data.patient
          wx.setStorageSync(config.tokenKey, data.token)
          wx.setStorageSync('patient', data.patient)
          wx.setStorageSync('allergies', data.allergies || [])
          resolve(data.token)
        }).catch(reject)
      }
      if (config.useMockLogin) {
        done(config.mockOpenid)          // 演示：固定绑定 1 号患者档案
      } else {
        wx.login({ success: (r) => done(r.code), fail: reject })
      }
    })
  }
})
