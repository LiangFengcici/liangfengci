# 牙科诊所诊疗信息平台 · 交付说明

依据《信管2402梁奉慈1602240216_牙科诊所诊疗信息平台_完善版》文档实现的可运行原型，
覆盖文档第 4 章功能设计与 5.4 节 V1—V10 验收点的全部业务规则。

## 零、在线访问（已部署，无需本机运行）

| 端 | 地址 | 说明 |
|---|---|---|
| 员工端 | https://liangfengci.pythonanywhere.com/login | 五个工作台，账号见下表，密码均 `123456` |
| 患者端取码页 | https://liangfengci.pythonanywhere.com/static/qr.html | 页内展示当前有效的体验版二维码 |
| 小程序 | 微信扫码进「体验版」 | 需先加入体验成员；首开若提示离线，点「···」→「打开调试」 |

> 体验版二维码有效期约 7 天，取码页地址永久不变，到期换图即可；详见 `docs/二维码更新操作卡.md`。

## 一、快速启动（本机 IP 网址访问）

双击根目录 **`启动系统.bat`**（自动找 Python、首次自动建库），或手动：

```bash
cd web
python run.py          # 默认 8000 端口；python run.py 8080 可换端口
```

启动后控制台会打印本机局域网 IP，访问方式：

| 端 | 网址 | 说明 |
|---|---|---|
| 员工端 | `http://127.0.0.1:8000/login` | 五角色登录，密码均为 `123456` |
| 患者端 H5（小程序界面原型） | `http://127.0.0.1:8000/p/` | 模拟微信一键登录 |
| 小程序 API | `http://127.0.0.1:8000/api/catalog` | 统一响应 `{code, message, data, trace_id}` |
| 局域网 | `http://<本机IP>:8000/…` | 手机 / 小程序真机联调用这个 |

**演示账号**：`front1` 前台 / `doc1`·`doc2` 医生 / `fin1` 财务 / `mgr1` 诊所经理 / `ops1` 运营专员。
**演示快捷入口**（原型期专用）：`/demo/front`、`/demo/doctor`、`/demo/finance`、`/demo/manager`、`/demo/ops`、`/demo/patient`。

## 二、目录结构

```
系统分析与设计/
├─ 启动系统.bat              一键启动后端服务
├─ 一键公网地址.bat          ★ 把本机 8000 映射成公网 https 地址（小程序体验版用，零注册）
├─ 设置公网地址.bat          手动填写穿透地址（cpolar / natapp 等）
├─ 设置真机IP.bat            真机调试时写入电脑局域网 IP
├─ 设置AppID.bat             写入小程序正式 AppID（上传前必做）
├─ README.md                 本文件
├─ runtime/                  cloudflared / 隧道日志等运行期文件
├─ docs/
│   ├─ 接口清单.md            小程序 API 与页面路由清单
│   ├─ 验收对照表.md          V1—V10 验收点 ↔ 实现与复现方式
│   ├─ 云端部署指南.md        PythonAnywhere 部署步骤（当前线上方案）
│   ├─ 公网部署教程.md        隧道 vs 云部署的原理对比
│   ├─ 固定地址配置说明.md    ngrok 静态域名方案（备选）
│   ├─ 二维码更新操作卡.md    体验版二维码 7 天有效期的应对
│   ├─ qr_entry.png           报告附录 B.2 的永久入口码
│   └─ screenshots/           各工作台与患者端截图
├─ web/                      Flask 3 + SQLite 后端与两端页面
│   ├─ schema.sql             57 张表（对应文档 4.1 六业务域）
│   ├─ seed.py                演示数据（诊所/医生/资质/号源/过敏/分期/消毒包…）
│   ├─ extend_schedule.py     幂等续排班脚本（补未来 60 天班次与号源）
│   ├─ services.py            全部业务规则（防超卖、过敏拦截、428、幂等、红冲…）
│   ├─ app.py                 应用入口 + 五个定时任务
│   ├─ wsgi.py                云端 WSGI 入口（PythonAnywhere 用）
│   ├─ verify.py              V1—V10 自动化验收脚本
│   ├─ views/                 auth / staff / patient / api 四组路由
│   └─ templates/…static/     员工端 5 工作台 + 患者端 H5 界面 + static/qr.html 取码页
└─ miniprogram/              微信小程序患者端源码（可直接导入开发者工具上传）
    ├─ app.json               四 tab：预约 / 我的预约 / 账单 / 会员
    ├─ utils/config.js        ★ 只需改这里的 baseUrl 即可联调
    └─ pages/                 预约六步 + 预约管理 + 账单 + 会员 + 报告调阅
```

## 三、核心业务规则（与文档 5.2 / 5.4 一一对应）

| 验收点 | 规则 | 实现 |
|---|---|---|
| V1 | 号源防超卖：30 分钟切片、条件更新扣减、并发单winner | `services.create_booking` |
| V2 | 资质 × 档期过滤：无种植资质不出现在种植候选 | `services.eligible_dentists` |
| V3 | 过敏硬校验：青霉素过敏禁开阿莫西林（422） | `services.save_prescription` |
| V4 | 知情同意：根管/拔牙/种植未签同意书禁止结算（428） | `services.settle_visit` |
| V5 | 定金抵扣 + 24h 分档退款（>24h 100%，≤24h 50%，爽约 0） | `deposit_refund_rate` / `cancel_booking` |
| V6 | 支付幂等：幂等键 + 第三方流水号唯一，重放返回首次结果 | `services.pay` |
| V7 | 先红冲后退款：已开票单必须先红冲（422） | `services.request_refund` |
| V8 | 折扣授权分离：财务 ≤5% 直批，>20% 转审批，已收款单禁改 | `services.apply_discount` |
| V9 | 消毒追溯：过期器械包领用拦截（422） | `services.use_pack` |
| V10 | 停诊级联：取消预约、释放号源、发通知、生成候补召回 | `services.suspend_shift` |

复现方式：`cd web && python verify.py`（自动重建演示库后逐项断言，11/11 通过）。

## 四、微信小程序上传

见 `miniprogram/README.md`。要点：
1. 微信开发者工具导入 `miniprogram` 目录（游客 AppID 可直接编译）；
2. 「详情 → 本地设置」勾选**不校验合法域名**；
3. `utils/config.js` 的 `baseUrl` 改为后端地址（本机 `http://127.0.0.1:8000`，真机用局域网 IP）;
4. 登录/支付为原型模拟通道，正式发布替换为 `code2session` 与微信支付统一下单（前端零改动）。

## 五、定时任务（文档 4.12）

服务内置 5 个任务，每次启动时自动注册（每小时整点 + 每日 08:00 触发）：
爽约标记、未支付单过期释放号源、复诊提醒推送、每日对账、季度业绩汇总。
手动触发：`POST /api/jobs/run`（Header `X-Job-Key: dental-cron-2024`）。

## 六、已知原型边界

- 支付为模拟通道：`/api/pay` 直接记账并返回 `pay_params`，未接真实微信商户号；
- 影像为参数化 SVG 渲染（索引 + 示意图），原型期替代 PACS/DICOM；
- `/demo/*` 快捷登录仅为演示便利，上线前应移除；
- 开发服务器（Flask built-in）仅用于教学演示，生产部署请换 gunicorn/waitress。

## 七、数据重建

仓库不包含数据库文件（`web/data/*.db` 已被 gitignore），克隆后首次启动会自动建库并灌入演示数据：

```bash
cd web
python run.py            # 首次启动自动执行 schema.sql + seed.py
python extend_schedule.py 60    # 把班次从 7 天续到 60 天（否则次日无号可约）
python verify.py         # V1—V10 自动化验收，11/11 通过
```

## 八、云端部署

线上实例部署在 PythonAnywhere 免费版（24 小时在线，本机关机也能访问），
完整步骤见 `docs/云端部署指南.md`。关键四点：

1. 上传代码 → Bash 里 `pip install -r requirements.txt`（虚拟环境 `dentenv`，Python 3.10）
2. Web 页 Manual configuration → WSGI 指向 `app:application`，并设 `DENTAL_NO_JOBS=1`（免费实例不跑定时任务）
3. Virtualenv 填 `/home/<用户名>/.virtualenvs/dentenv`，静态映射 `/static/` → `web/static`
4. 免费实例每 3 个月需在 Web 页点一次 **Run** 续期

## 九、交付物

| 文件 | 说明 |
|---|---|
| `信管2402梁奉慈1602240216_牙科诊所诊疗信息平台_完善版.docx` | 课程报告（含附录 B 运行与演示说明、图 B-1 入口码） |
| `web/` | 后端与员工端、患者端 H5 全部源码 |
| `miniprogram/` | 微信小程序患者端源码，可直接导入开发者工具上传 |
| `docs/` | 接口清单、验收对照表、部署指南、二维码操作卡、界面截图 |

