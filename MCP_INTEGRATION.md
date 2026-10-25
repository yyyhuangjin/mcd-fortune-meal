# MCP_INTEGRATION · 麦当劳 MCP 接入说明

本项目的全部餐饮数据与交易能力都来自麦当劳官方 MCP Server（`mcd-mcp`），无任何爬虫、无演示数据兜底。

## 接入的 MCP Server

| 项 | 值 |
|---|---|
| Server | `mcd-mcp` |
| 地址 | `https://mcp.mcd.cn`（Streamable HTTP） |
| 认证 | `Authorization: Bearer <MCD_TOKEN>`（环境变量 / 本地连接器配置，不进代码库） |
| 工具数 | 35 个 |
| 限流 | 600 次/分钟 |

Token 从麦当劳开放平台申请：https://open.mcd.cn/mcp 。本仓库不包含任何真实凭证，
`mcp-config.example.json` 只提供环境变量占位符。

## 实际用到的工具与调用链

### ① 定位与门店

- `query-nearby-stores`：按经纬度找自取门店（距离、营业状态）
- `delivery-query-addresses`：读已存配送地址（优先级最高的定位来源）
- `delivery-query-stores`：外送门店与自取门店不是同一家，分开查

### ② 菜单与商品

- `query-meals`：拉取门店真实在售菜单（含 `currentPrice`、售罄状态、标签）
- `query-meal-detail`：单品详情（套餐内子项、规格）

### ③ 优惠券

- `query-my-coupons`：读用户卡包（券面额、门槛、时段限制）
- `available-coupons` / `query-store-coupons`：本店可用性初筛
- `auto-bind-coupons`：领取「麦麦省」可领券（**需用户明确确认后才会执行**，官方行为是一次领走全部可领券）

### ④ 核价（项目里的价格真相）

- `calculate-price`：每个推荐方案都过一次真实核价——自取、外送各核一次；
  带券前后各核一次，差额才是「省下的钱」。菜单 `currentPrice` 对会员加购商品是加购价
  （实测差一倍），所以**页面上的所有金额一律以核价结果为准**。
- 取餐方式 `takeWayCode` 只从 `calculate-price` 返回的 `takeWayList` 里取（实测 `eat-in` / `locker-in`），不猜。

### ⑤ 下单与订单

- `create-order`：用户点「确认下单」才调用。返回体无官方文档，脚本对
  订单号 / `payH5Url` / `jumpToApp` 深链做多层字段嗅探，并保留原始返回便于排查
- `query-order`：查真实订单状态；付款成功态（已支付/制作中/待取餐/已完成）才会盖章「今日已吃」并展示取餐码
- `cancel-order`：真取消，页面「划掉这张」按钮直连
- `order-list`：兜底查询

### ⑥ 辅助

- `now-time-info`：以服务器时间为准做时段判断（早餐/正餐/下午茶），不用本机时间
- `query-promotions`：今日限定（上新 / 全球爆款 / 限时特惠）标签来源

## 业务价值

1. **把黄历翻译成菜单**：宜忌 / 五行 / 天气三层打分 → 槽位倾向 → 只在真实在售商品里配方案，
   拿不到的数据明说「暂不可用」，不编。
2. **价格全程可核**：推荐页、确认页、下单三次核价，价格变了必须用户点头才继续。
3. **交易闭环且克制**：领券、下单、取消全部要用户确认；超时或返回不明先 `query-order`，绝不重复提交。
4. **Token 零暴露**：前端页面不碰 MCP，所有调用走本地服务端（`scripts/serve.py` 代理）。

## 调用流程图

见 README.md 顶部的 mermaid 流程图；工具速查全表见 `references/tools.md`。
