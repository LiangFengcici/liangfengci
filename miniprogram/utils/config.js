/**
 * 接口地址配置 —— 只改 ENV 一行，其余交给脚本。
 *
 * 三种场景：
 *   'local' → 开发者工具模拟器，走本机 127.0.0.1:8000
 *   'lan'   → 手机与电脑同一 Wi-Fi（真机调试），走电脑局域网 IP
 *   'prod'  → 公网地址（内网穿透 / 云服务器），老师在任何网络都能用，数据与牙科平台同步
 *
 * ⚠ 手机上 127.0.0.1 指的是「手机自己」，永远不会是你的电脑。
 *   所以真机 / 体验版必须用 'lan' 或 'prod'，不能留在 'local'。
 *
 * 不想手改？双击：
 *   D:\系统分析与设计\设置公网地址.bat   → 配 'prod'（推荐，老师也能用）
 *   D:\系统分析与设计\设置真机IP.bat     → 配 'lan'（仅同一 Wi-Fi 自测）
 */

const ENV = 'prod'                       // ← 需要改的就是这一行

const LAN_HOST = '192.168.1.20'           // 局域网 IP（不带 http://）
const PROD_URL = 'https://liangfengci.pythonanywhere.com'  // 公网地址（带 https://，末尾不加斜杠）

const LOCAL_URL = 'http://127.0.0.1:8000'
const LAN_URL = 'http://' + LAN_HOST + ':8000'

const BASE_URLS = {
  local: LOCAL_URL,
  lan: LAN_URL,
  prod: PROD_URL
}

const BASE_URL = BASE_URLS[ENV] || LOCAL_URL

module.exports = {
  env: ENV,
  baseUrl: BASE_URL,
  // 缓存键按环境隔离：换地址后不会沿用上一个环境签发的 token
  tokenKey: 'token@' + BASE_URL,
  useMockLogin: true,          // 演示期固定绑定 1 号患者档案（正式上线改 false）
  mockOpenid: 'mock-openid-1', // 与后端 patient.openid 对应
  fallbackMock: true,          // ★ 接口不可达时自动降级到离线演示数据（体验版兜底）
  offlineDemo: false,          // ★ true = 完全不请求后端，全程用演示数据
  version: '1.0.0'
}
