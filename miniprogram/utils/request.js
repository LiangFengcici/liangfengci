const config = require('./config')
const mock = require('./mock-server')

/**
 * 运行模式（供页面显示状态徽标）
 *   real    = 连的是真实后端，数据与电脑上的牙科平台同步
 *   offline = 走内置演示数据，重启即重置
 */
let mode = 'unknown'
const modeListeners = []

function setMode(next) {
  if (mode === next) return
  mode = next
  modeListeners.forEach(fn => {
    try { fn(next) } catch (e) { /* ignore */ }
  })
}

function getMode() { return mode }

function onModeChange(fn) { modeListeners.push(fn) }

/** 离线提示只弹一次，避免刷屏 */
let offlineNotified = false
function notifyOfflineOnce() {
  if (!offlineNotified) {
    offlineNotified = true
    wx.showToast({ title: '已切换离线演示数据', icon: 'none', duration: 2600 })
  }
}

/**
 * 统一请求封装。
 * - config.offlineDemo = true  → 强制走离线演示数据（不看后端脸色）
 * - config.fallbackMock = true → 真实请求失败时自动降级到离线数据（真机/体验版兜底）
 */
function request(path, { method = 'GET', data = {}, header = {} } = {}) {
  if (config.offlineDemo) {
    setMode('offline')
    notifyOfflineOnce()
    return mock.handle(path, method, data)
  }

  return new Promise((resolve, reject) => {
    const token = wx.getStorageSync(config.tokenKey)
    wx.request({
      url: config.baseUrl + path,
      method,
      data,
      header: Object.assign({
        'content-type': 'application/json',
        'Authorization': token ? 'Bearer ' + token : '',
        'ngrok-skip-browser-warning': '1'
      }, header),
      success(res) {
        setMode('real')
        const body = res.data || {}
        if (res.statusCode === 401) {
          // token 属于另一个环境（如离线演示时签发的），清掉后重进即可
          wx.removeStorageSync(config.tokenKey)
          wx.showToast({ title: '登录已失效，请重新进入小程序', icon: 'none', duration: 2600 })
          return reject(new Error('unauthorized'))
        }
        if (res.statusCode === 200 && body.code === 0) {
          resolve(body.data)
        } else {
          const msg = body.message || ('请求失败(' + res.statusCode + ')')
          wx.showToast({ title: msg, icon: 'none', duration: 2600 })
          reject(new Error(msg))
        }
      },
      fail(err) {
        const raw = (err && err.errMsg) || '未知错误'
        console.error('[request fail]', config.baseUrl + path, raw)

        // 自动降级：接口不可达 → 离线演示数据（体验版/答辩兜底）
        if (config.fallbackMock) {
          setMode('offline')
          notifyOfflineOnce()
          mock.handle(path, method, data).then(body2 => {
            if (body2.code === 0) resolve(body2.data)
            else {
              wx.showToast({ title: body2.message || '操作失败', icon: 'none', duration: 2600 })
              reject(new Error(body2.message || 'mock error'))
            }
          })
          return
        }

        let tip = '连不上后端：' + raw
        if (raw.indexOf('domain list') >= 0) {
          tip = '接口未在合法域名中：请勾选「不校验合法域名」'
        } else if (raw.indexOf('timeout') >= 0) {
          tip = '请求超时：确认后端窗口仍在运行、baseUrl 端口一致'
        } else if (raw.indexOf('fail') >= 0) {
          tip = '服务未启动或地址不对：' + config.baseUrl
        }
        wx.showToast({ title: tip, icon: 'none', duration: 3000 })
        reject(err)
      }
    })
  })
}

function post(path, data, header) {
  return request(path, { method: 'POST', data, header })
}

/** 手动探测后端是否可达（用于首页状态条） */
function ping() {
  return new Promise(resolve => {
    if (config.offlineDemo) {
      setMode('offline')
      return resolve('offline')
    }
    wx.request({
      url: config.baseUrl + '/api/catalog',
      method: 'GET',
      timeout: 5000,
      header: { 'ngrok-skip-browser-warning': '1' },
      success(res) {
        const ok = res.statusCode === 200 && (res.data || {}).code === 0
        setMode(ok ? 'real' : 'offline')
        resolve(ok ? 'real' : 'offline')
      },
      fail() {
        setMode('offline')
        resolve('offline')
      }
    })
  })
}

module.exports = { request, post, ping, getMode, onModeChange, setMode }
