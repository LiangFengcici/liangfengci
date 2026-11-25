# 微信小程序患者端 · 上传与联调说明

本目录是**原生微信小程序**源码（无 npm 依赖、无云开发），对应文档 4.13「微信小程序患者端设计」，
覆盖 UC4 在线自助预约与 UC5 在线支付的完整链路。

## 一、目录结构

```
miniprogram/
├─ app.js / app.json / app.wxss      全局逻辑、路由与样式
├─ project.config.json               开发者工具工程配置（appid：touristappid 可改为自己的）
├─ sitemap.json
├─ utils/
│   ├─ config.js                     ★ 接口地址与登录方式配置（只需改这里）
│   ├─ request.js                    统一请求封装（Bearer token、错误码提示）
│   └─ format.js                     金额/日期/状态格式化
└─ pages/
    ├─ index/         预约 · 项目分类（tab1）
    ├─ detail/        分类下的项目列表
    ├─ dentists/      选医生（资质 × 档期过滤）
    ├─ slots/         选时段（30 分钟切片、实时余量）
    ├─ confirm/       确认订单 + 过敏史核对 + 支付定金
    ├─ bookings/      我的预约（tab2，取消/支付/查看病历）
    ├─ bills/         账单（tab3，结算单明细与分期）
    ├─ member/        会员（tab4，积分/储值/优惠券）
    └─ report/       报告与影像调阅
```

## 二、上传步骤（微信开发者工具）

1. 打开**微信开发者工具** → 导入项目 → 目录选择本 `miniprogram` 文件夹。
2. AppID 一栏可先用「测试号 / 游客模式」（`project.config.json` 中为 `touristappid`）；
   正式上传请换成自己在微信公众平台申请的小程序 AppID。
3. 导入后：右上角「详情 → 本地设置」勾选 **不校验合法域名、web-view（业务域名）、TLS 版本以及 HTTPS 证书**。
4. 修改 `utils/config.js` 中的 `baseUrl`，指向后端服务地址：
   - 模拟器在同一台电脑：`http://127.0.0.1:8000`
   - 真机预览：改成电脑的局域网 IP，例如 `http://192.168.1.20:8000`（手机与电脑同一 Wi-Fi）
5. 编译运行，即可走通「项目分类 → 详情 → 选医生 → 选时段 → 确认 → 付定金 → 我的预约」。

## 三、登录与微信生态三处集成点

| 集成点 | 原型实现 | 正式改造 |
|---|---|---|
| 登录 | `config.useMockLogin = true`，固定以 `mock-openid-1` 调 `/api/login` | 置 `false`，改为 `wx.login` 取 code，后端接 `code2session` 换 openid |
| 支付 | `/api/pay` 返回模拟 `pay_params`，`wx.requestPayment` 失败时提示“模拟通道已记账” | 后端接微信支付统一下单，返回真实 `prepay_id` 与签名；回调按 `第三方流水号` 幂等入账 |
| 触达 | 后端 `notification_log` 记录推送（预约确认/支付凭证/复诊召回） | 接入订阅消息模板 ID，由后端调用 `subscribeMessage.send` |

> 前端**不判断支付成功**：一切以 `/api/pay`（或回调）返回的状态为准，符合 4.13「支付结果以回调验签＋流水号唯一键幂等入账」的约定。

## 四、接口清单

见 `../docs/接口清单.md`，或直接访问后端 `/api/catalog` 观察统一响应体
`{code, message, data, trace_id}`。

## 五、联调排错（看到「连不上后端」时按此顺序查）

**第 0 步：确认后端真的在跑**
启动 `D:/系统分析与设计/启动系统.bat`，窗口里出现 `Running on http://127.0.0.1:8000` 才算成功。
该黑窗口**不能关**，关掉服务就停。浏览器访问 `http://127.0.0.1:8000/api/catalog`
若能看到 `{"code":0,...}`，说明后端正常，问题一定在小程序侧。

**第 1 步：关掉域名校验**
开发者工具 → 右上「详情」→「本地设置」→ 勾选
**不校验合法域名、web-view（业务域名）、TLS 版本以及 HTTPS 证书**。
（未勾选时报错：`request:fail url not in domain list`）

**第 2 步：核对 baseUrl 与端口**
`utils/config.js` 的 `baseUrl` 必须与启动窗口里的地址**逐字符一致**：
`http://127.0.0.1:8000`（末尾不要加 `/`）。改完按 `Ctrl+B` 重新编译。

**第 3 步：看控制台真实错误**
调试器 → Console，会打印 `[request fail] <完整URL> <errMsg>`。对照：

| errMsg 关键字 | 原因 | 处理 |
|---|---|---|
| `url not in domain list` | 域名校验未关 | 回到第 1 步 |
| `fail` / `ERR_CONNECTION_REFUSED` | 服务没起 / 端口不一致 | 重启 `启动系统.bat`，核对端口 |
| `timeout` | 地址不通（真机常见） | 见第 4 步换局域网 IP |
| 返回 4xx + message | 业务校验（如过敏拦截） | 属正常业务提示，非接口故障 |

**第 4 步：真机预览（手机扫码）**
手机与电脑连同一 Wi-Fi，把 `baseUrl` 改成电脑局域网 IP（cmd 执行 `ipconfig` 看「IPv4 地址」）。
注意：若电脑 IP 是 `100.x.x.x`（运营商 NAT / 虚拟网卡），手机通常连不通，
此时用手机开热点让电脑连接，再取电脑在新热点下的 IP。

**应急自检一行命令**（开发者工具 Console 直接粘贴，可绕过自家封装判断通不通）：
```js
wx.request({ url: 'http://127.0.0.1:8000/api/catalog', success: r => console.log(r.statusCode, r.data), fail: e => console.error(e.errMsg) })
```
