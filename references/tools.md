# mcd-mcp 工具参考（35 个，实测 v1.0.0）

连接器：`mcd-mcp` · 地址 `https://mcp.mcd.cn` · Streamable HTTP · `Authorization: Bearer <TOKEN>` · 限流 600 次/分钟

工具全名 = `mcp__mcd-mcp__<name>`。下表只写 `<name>`。

## 参数传递速查（最容易错的地方）

```
到店自取 beType=1 → orderType=1, beCode 不传, 无 addressId
得来速   beType=5 → orderType=1, beCode 必传(来自 query-nearby-stores)
麦乐送   beType=2 → orderType=2, beCode 必传(来自 delivery-query-stores), addressId 必传
企业团餐 beType=6 → orderType=2, beCode 必传, addressId 必传, gmServiceCode 必传
```

涉及 `orderType/beType/beCode/storeCode` 的工具：`query-meals`、`query-meal-detail`、`query-store-coupons`、`calculate-price`、`create-order`、`query-meal-assistance`。

## 门店与地址

| 工具 | 作用 | 关键入参 |
|---|---|---|
| `query-nearby-stores` | 到店/得来速查门店 | `beType`(1/5)*, `searchType`(1=收藏,2=按位置)*, `city`(searchType=2 必填), `keyword` |
| `delivery-query-addresses` | 查已存配送地址 | 无 |
| `delivery-create-address` | 新增配送地址 | 按工具 schema 填收货信息 |
| `delivery-query-stores` | 外送/团餐查可配送门店 | `addressId`*, `beType`(2/6)* |
| `query-meal-assistance` | 团餐助餐服务（拿 gmServiceCode） | `storeCode` 等 |

## 菜单与商品

| 工具 | 作用 | 关键入参 |
|---|---|---|
| `query-meals` | 门店当次菜单（分类/编码/价格/标签） | `storeCode`*, `orderType`*, `beType`*, `beCode`, `reservationDate` |
| `query-meal-detail` | 套餐组成、可替换项、特制项 | `storeCode`*, `orderType`*, `beType`*, `code`*（餐品编码）, `beCode` |
| `list-nutrition-foods` | 营养成分（能量/蛋白/脂肪/碳水/钠/钙） | 无 |

## 优惠券

| 工具 | 作用 | 注意事项 |
|---|---|---|
| `query-store-coupons` | **本店本订单类型可用券**（带规则校验） | 核价/下单前用这个 |
| `query-my-coupons` | 卡包券列表 | 不代表当前订单可用；`page`/`pageSize` |
| `available-coupons` | 麦麦省可领券列表 | 只读 |
| `auto-bind-coupons` | 一键领取全部可领券 | **写操作**，先征得同意 |
| `query-survey-coupon` | 问卷券 | — |
| `query-promotions` | 促销活动 | — |

券对象关键字段（实测 `query-my-coupons` 单券）：

| 字段 | 含义 | 坑 |
|---|---|---|
| `id` / `code` | 即 `couponId` / `couponCode` | 核价时要成对塞进对应 item |
| `weekdays` | 可用星期 | **`1=周日 … 7=周六`**，别直接比 Python 的 `weekday()` |
| `tradeStartDateTime` / `tradeEndDateTime` | 生效/失效时刻 | 用这两个判断，别只看 `enable` |
| `tradeTimePeriods` | 每日可用时段 | 例 `10:30:00-23:59:59` |
| `currentDayAvailableCount` | 今日剩余可用次数 | 0 = 今天用不了 |
| `currentChannelCanRedeem` | 本渠道能否核销 | `false` + `toastText` 说「仅限App」时要提示风险 |
| `products` | 适用商品 | **经常是空数组**，只能靠标题模糊匹配 |
| `discountInfo.discountValue` | 固定价券是「用券后价格」 | 不是减免额 |

券相关的错误信息很直白，可直接转述给用户：
`此卡券不在使用日期内，请在有效期内来使用哦！`

## 下单与订单

| 工具 | 作用 | 关键入参 |
|---|---|---|
| `calculate-price` | 核价（商品+券+配送费→应付） | `storeCode`*, `orderType`*, `beType`*, `items[]`, `beCode`, `gmServiceCode` |
| `create-order` | 创建订单，返回支付链接 | 同上 + `addressId`(外送/团餐必传) |
| `cancel-order` | 取消订单 | 订单号；**需用户确认** |
| `query-order` | 订单详情/配送进度 | `orderId`* |
| `order-list` | 近期到店/外送历史订单 | — |

`items[]` 结构（`calculate-price` / `create-order` 共用）：
```json
{
  "productCode": "餐品编码",
  "quantity": 1,
  "couponId": "可选",
  "couponCode": "可选",
  "roundList": [ { "comboItemList": [ { "code": "子项编码", "quantity": 1 } ] } ],
  "modification": { "values": [ { "key": "...", "code": "...", "quantity": 1 } ] }
}
```

## 积分 / 商城 / 抽奖

| 工具 | 作用 |
|---|---|
| `query-my-account` | 我的积分（可用/累计/冻结/即将过期） |
| `mall-points-products` | 商城商品列表（积分兑换/现金） |
| `mall-product-detail` | 商品详情 |
| `mall-create-order` | 积分兑换下单（扣积分，**需确认**） |
| `mall-order-list` / `mall-order-detail` | 商城订单列表/详情 |
| `query-lottery-info` | 抽奖活动信息（奖品、消耗规则） |
| `draw-lottery` | 执行抽奖（消耗积分/次数） |
| `query-my-prizes` | 我的奖品（分页，按中奖时间倒序） |

## 活动 / 派对 / 团餐

| 工具 | 作用 |
|---|---|
| `campaign-calendar` | 当月营销活动日历（进行中/往期/未来） |
| `query-party-city` | 主题活动可参与城市 |
| `query-party-store` | 指定城市的活动门店 |
| `query-party-store-date` | 指定门店可预约日期 |
| `query-party-store-session` | 指定日期可预约场次 |
| `party-order-create` | 主题活动下单 |
| `now-time-info` | 当前时间（毫秒时间戳/格式化/时区） |

## 错误码

| code | 原因 | 处理 |
|---|---|---|
| 401 | Token 无效/过期/未提供 | 重新在 open.mcd.cn/mcp 激活，更新 mcp.json |
| 429 | 超 600 次/分 | 停止重试，等 1 分钟，减少批量核价 |

官方文档：https://open.mcd.cn/mcp/doc ｜ 仓库：https://github.com/M-China/mcd-mcp-server
