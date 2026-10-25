---
name: mcd-fortune-meal
description: "麦麦黄道吉日（黄历 × 天气 × 五行 → 麦当劳）。当用户问「今天吃什么麦当劳」「今天适合吃牛还是鱼」「按黄历/运势点餐」「今天什么日子该吃什么」「撕今天的日历」「今天有什么限定」「帮我用券点麦当劳」「直接下单」或想要一个有点仪式感的点餐理由时使用。输出一张可交互的月历页与开运小票，菜单、优惠券、价格全部来自麦当劳 MCP 实查实核，并可在用户确认后真实创建订单。"
description_en: "Fortune-driven McDonald's ordering with an interactive calendar page and a shareable receipt: almanac + live weather + real menu + verified coupon pricing via mcd-mcp, then a confirmed real order."
version: 1.2.0
author: xinyang
---

# 麦麦黄道吉日 · mcd-fortune-meal

> 万事皆有宜忌，唯有吃麦当劳，日日皆宜。

把「今天什么日子」翻译成「今天吃什么」，落到这家店**真实在售的菜单**上，用卡包里的券
**真实核一次价**，最后给出一张能保存、能下单的开运小票。

开场是撕日历：进页只有今日一页纸，按住下沿往下撕（锯齿撕口、纸屑、整页从装订口坠走），
撕完才见今日推荐，月历收在最后的「查看黄历月历」里。

**吉凶铁律**：黄道=吉、黑道/破闭=凶。但无论吉凶，宜忌第一条永远是「宜吃麦当劳」——
凶日写作「**宜吃麦当劳转运**」，纸面印章从「吉」换成「转运」。对外口径：
万事皆有宜忌，唯有吃麦当劳，日日皆宜。

## 依赖

| 依赖 | 用途 | 是否必需 |
|---|---|---|
| `mcd-mcp` 连接器 | 查门店、拉菜单、取券、核价、下单 | 必需 |
| `lunar_python` | 本地推算黄历（离线、无 Key） | 必需，`pip install lunar_python` |
| Open-Meteo | 实时天气（免费、无 Key） | 必需，脚本内置 |

## 三条铁律（先记住再看流程）

1. **定位即查天气，但不播报天气。** 用户只要给一个地点（或什么都不给，自动定位），
   就自己去查天气；天气只是内部信号，不要在对话里念温度、念降水概率。
   天气在页面与黄历卡里自然呈现，对话里不重复。
2. **取餐方式自己判断，不要让用户选。** 下雨 / 忌出行 / 外送加价过高一算就知道。
   拿不准（差价很小、天气也不极端）就直说「**当天可以，自取外送都行**」，不要追问。
3. **任何写操作都要确认。** 领券、下单必须用户点头；支付永远交给用户。

## 执行流程

### Step 0 · 一条命令生成可交互页面（默认入口）

```bash
python3 scripts/make_almanac.py --out demo/almanac.html        # 自动定位
python3 scripts/make_almanac.py --city 厦门 --out demo/almanac.html
```

这一步内部按顺序做完：**定位 → 天气 → 门店（自取 + 外送双路）→ 菜单 → 方案 →
券比价 → 双向核价 → 宜忌/签语 → 月历 → 渲染 HTML**。

想要「点按钮就能真下单」，用本地服务打开（Token 只在服务端，浏览器拿不到）：

```bash
python3 scripts/serve.py --open        # http://127.0.0.1:8765
```

页面能力：真实月历（切月、点日期）、今日黄历卡、开运小票、换一份好运、查看优惠、
保存 PNG、一键下单（需二次确认）。用 `present_files` 打开 `demo/almanac.html` 给用户看。

### Step 1 · 命盘与天气（想单独看数据时）

```bash
python3 scripts/daily_fortune.py --city <城市> [--date 2026-11-07] [--json-only]
```

得到：干支纳音、宜忌、值日、星宿、喜神/财神、幸运色数、四槽位倾向、指向强度、取餐取向。

指向强度 `low` = 当日宜忌信息稀少、几个品类打平 —— **照实说"随缘日"**，不要硬编理由。

### Step 2 · 门店

```bash
python3 scripts/fetch_menu.py stores --city <城市> --keyword <商圈>
```

外送：`delivery-query-addresses` → 取 `addressId` → `delivery-query-stores`。
**到店自取绝对不能传 beCode**；外送 / 得来速 / 团餐必须传 beCode。

### Step 3 · 拉菜单

```bash
python3 scripts/fetch_menu.py menu --store-code 1410574 --order-type 1 --be-type 1 --out menu.json
```

菜单是门店级实时数据，每次重拉，不缓存、不凭记忆报菜名。

### Step 4 · 方案 + 券比价

```bash
python3 scripts/suggest.py --menu menu.json --store-code <门店> [--json]
```

出 4–6 套方案：天命套餐 / 手搭三件 / 轻简改运 / 甜品冲喜 / 再抽一签，并附券比价、
券预告、今日限定。

### Step 5 · 真实核价（不可跳过）

```bash
python3 scripts/fetch_menu.py price --store-code <门店> --order-type 1 --be-type 1 --items a,b,c
```

**菜单上的 `currentPrice` 会骗人**：带「随单购麦金卡优惠」的商品显示的是会员加购价。
实测「麦辣鸡腿堡四件套」显示 ¥28、核价实收 ¥57。任何报价都要过 `calculate-price`。

### Step 6 · 领券（仅当用户明确要求）

```bash
python3 scripts/order.py claim            # 预览可领的券，不领
python3 scripts/order.py claim --confirm  # 真领
```

`auto-bind-coupons` 会**一次领走全部可领的麦麦省券**，不是只领一张。必须先跟用户讲清楚。

### Step 7 · 下单（三步，缺一不可）

```bash
# 1) 报价：不产生任何写操作，存一份 quote 到 ~/.workbuddy/mcd-orders/
python3 scripts/order.py quote --store-code 1410574 --order-type 1 --be-type 1 \
  --items 9900005428:1 [--coupon-id ID --coupon-code CODE]

# 2) 预览：会重算一次价，但不提交（不加 --confirm）
python3 scripts/order.py submit --quote <quote.json> --take-way-code eat-in

# 3) 真下单：用户明确说「确认」之后
python3 scripts/order.py submit --quote <quote.json> --take-way-code eat-in --confirm

# 4) 反悔了：真的取消（不可撤销）
python3 scripts/order.py cancel --order-id <id> --reason 1
```

规则：

- **`takeWayCode` 只能来自 `calculate-price` 返回的 `takeWayList`**（实测到店是
  `eat-in` 堂食 / `locker-in` 外带，不同门店可能不同，不许猜）。
- **外送必须带用户确认过的 `addressId`**，不许填默认地址。
- **下单前必重算**：价格与确认页不一致就停下（要强行接受才加 `--accept-change`）。
- 下单用的商品、数量、券参数必须与确认页完全一致。
- **超时/返回不明先查单，不要重复提交。**

`create-order` 的真实返回（2026-10 实测，别照旧猜字段）：

| 字段 | 含义 |
|---|---|
| `data.orderId` | 订单号（19 位以上字符串） |
| `data.payId` | 支付单号 |
| **`data.payH5Url`** | **支付入口**，形如 `https://m.mcd.cn/mcp/scanToPay?orderId=...` |
| `data.orderDetail.orderStatus` | 刚建好是「待支付」，`status` = `10` |
| `data.orderDetail.expirePayTime` | **15 分钟**支付窗口，过点自动取消 |
| `data.orderDetail.pickupCode` | 取餐码，**付款后才有**，付款前是空串 |

所以下单成功后必须做三件事：把 `payH5Url` 递给用户、告诉他 15 分钟要付完、告诉他付款后查状态才能拿到取餐码。

## 页面流程（顺序不能反）

1. **进来只有一张纸** —— 今日的日历页面（年/月/日/农历/干支/宜忌/大「吉」印），不是月历网格。
2. **撕** —— 按住纸的下沿往下拖，纸沿锯齿撕口裂开，上半截留手、下半截连纸屑一起飞走，露出背后的红底「吉」。
3. **撕完才给今天吃什么** —— 黄历卡 + 开运小票 + 今日限定。
4. **月历放最后** —— 点「查看黄历月历」才出网格。

实现要点（`web/app.js` 的 `tear` 对象）：撕口是用 `clip-path: polygon()` 逐帧重算的
锯齿折线，上下两半共用同一份纸面 HTML，所以静止时严丝合缝；拖动位移决定撕线高度，
松手过 40% 就算撕开，不过就带回弹归位。不要改成淡入淡出——那就不是撕了。

## 网页下单链路（`scripts/serve.py`）

| 接口 | 作用 | 写操作 |
|---|---|---|
| `POST /api/quote` | 实时核价 + 返回可用的 `takeWayCode` | 否 |
| `POST /api/order` | 重算 → 建单；必须带 `confirm:true` | **是** |
| `POST /api/cancel` | 调 `cancel-order` 真取消 | **是** |
| `GET /api/status?orderId=` | 查状态与取餐码 | 否 |

- 前端传的 `total` 只用于「价格有没有变」的比对，**服务端一律重算**。
- 价格变了返回 `stage: "price-changed"` + `before/after`，前端弹「按新价下单」，不自动接受。
- Token 只在服务进程里读 `~/.workbuddy/mcp.json`，浏览器全程看不到。
- 服务只监听 `127.0.0.1`，**不要改成 `0.0.0.0`**。

## 页面上每个数字的来源

| 页面元素 | 来源 |
|---|---|
| 月历「吉」、农历、干支、宜忌 | `lunar_python` 本地推算（±40 天） |
| 今日天气 | Open-Meteo 实查；失败显示「天气暂不可用」 |
| 菜单、限定、价格 | `query-meals` + `calculate-price` |
| 券、省多少钱 | `query-my-coupons` + 核价前后差额 |
| 取餐方式与费用差 | 同篮子自取/外送**各核一次价** |
| 别的日期 | 只出黄历与签语，标注「天气/菜单/价格需当天实时查询」 |

## 优惠券怎么算（三条硬规矩）

1. **券面只用来筛，省多少一律看核价。** `couponId` + `couponCode` 成对塞进对应 item，
   前后各核一次价，差额才是省下的钱。**不许拿标价减券面价。**
2. **能用 ≠ 今天能用。** 有效期、星期、时段、点餐方式、门店口径五层都要过。
   券的 `weekdays` 是 `1=周日 … 7=周六`，别按 Python 的 `weekday()` 比。
3. **验不过就照实说。** 核价报「此卡券不在使用日期内」，原样转述，别糊过去。

拿不到的两件事要承认：`products` 常为空（只能标题模糊匹配，标「推测」）；
`currentChannelCanRedeem: false` + `该券仅限麦当劳App使用` → **只提示，不承诺**。

## 红线

- 黄历 / 五行 / 星宿 / 方位属**传统民俗娱乐**，结尾保留娱乐声明；不得预测健康或吉凶。
- 不得虚构门店、菜品、价格、优惠券；所有数字来自工具返回。
- **不得自己算优惠金额**；省了多少只能来自核价差额。
- **不得把不可用的券说成可用**；说清是日期、星期、时段还是渠道。
- 下单、领券、扣积分**一律先确认**；绝不代付、绝不索取支付凭证。
- **不得在前端出现 Token**：页面只与本机 `serve.py` 通信，Token 只在服务端进程里。
- 页面上的每个数字都必须来自本次真实数据，不许为了好看编一个。

## 故障处理

| 现象 | 处理 |
|---|---|
| `lunar_python` 缺失 | `pip install lunar_python`，别用记忆代替 |
| 天气接口超时 | 传 `--lat --lon`；仍失败则跳过天气层，标注「天气暂不可用」 |
| 城市找不到 | Open-Meteo 对中文名召回很挑：`厦门` 查不到、`厦门市` 才行；`上海市` 会落到美国。脚本已做多候选 + 省份校正 |
| 菜单为空 | 门店可能非营业时段，换门店或提示用户 |
| 核价与快照价不一致 | 以核价为准，讲清差异（会员加购价 / 打包费 / 配送费） |
| 外送商品下单失败 `商品已售罄或不可售` | 外送门店常与本店不是同一家，SKU 不通用；跨渠道比价只认同名商品 |
| 券「不在使用日期内」 | 照实转述，能预告就预告 |
| `create-order` 超时 | 先 `query-order` 核对，不要重复提交 |
| MCP 401 / 429 | 401 让用户重新激活 Token；429 触达 600 次/分限流，停止重试 |

> 解析坑：MCP 返回体不统一（单行 JSON / JSON 后同行拼说明 / markdown 在前 JSON 粘在表格行尾）。
> `fetch_menu.parse_json_object` 优先取 `result.structuredContent`，别按「以 `{` 开头的行」切。

## 文件

```
scripts/make_almanac.py    定位 + 天气 + 门店 + 菜单 + 方案 + 券 + 双向核价 → 单文件 HTML
scripts/serve.py           本地预览服务（/api/quote /api/order /api/status /api/claim）
scripts/order.py           报价 / 提交 / 查单 / 领券（写操作全部要 --confirm）
scripts/daily_fortune.py   黄历 + 天气 + 三层映射 → 四槽位倾向
scripts/coupons.py         券比价：有效期预校验 + 核价验证节省额
scripts/suggest.py         倾向 + 真实菜单 + 券 → 方案 / 限定池 / payload
scripts/make_calendar.py   旧版撕纸页（v1.1，保留兼容）
scripts/fetch_menu.py      查门店 / 拉菜单 / 核价 / 取券 CLI
web/index.html app.css app.js art.js   月历、黄历卡、小票与原创插画的源码
demo/almanac.html          这次生成的可交互页面（真实数据）
references/tools.md        mcd-mcp 35 个工具速查与参数铁律
references/rule-system.md  映射规则全表
```

美术基调（v1.3 改版）：第一眼麦当劳、第二眼老黄历、第三眼才是撕开领好运。
- 配色：奶油黄页面底 + 麦当劳红 `#E4182F/#C8102E` + 金黄 `#FFC72C`，黄历纸保留米白；body::after 是隐约的金拱门 M 重复纹样
- art.js 里 `ART.svg.*` 是原创 SVG 插画套件（金拱门/薯条/汉堡/鸡块蘸酱/红白饮料杯/外卖纸袋/线稿），`ART.icon(name)` + `ART.foodKey(text)` 按**真实宜忌文案与推荐食材**动态配美食小图标，不许写死
- 品牌区：金拱门 + 圆体红金标题 + 红色包装标签宣传语 + 右上薯条汉堡 hero；纸面「吉」章是认证章样式（拱门 + 吉 + 「今日宜吃麦」）
- 撕纸按钮：红底金边 + 薯条图标 + 「撕开今日麦麦好运」+ 下撕手势 + 黄色闪光；露出层顶部有红黄雨棚条纹，先看到的是包装元素
