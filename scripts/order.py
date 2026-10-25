#!/usr/bin/env python3
"""麦麦黄道吉日 · 真实算价 / 领券 / 下单 / 查单。

三条不可越过的线：

1. **写操作必须显式确认**。领券、下单都要 `--confirm`；不加只出预览。
2. **下单前重算一次价**。确认页看到的价格必须和 create-order 用的是同一份参数，
   价格变了就停下来说清楚，不允许「差一点也下」。
3. **不确定就查，不重复提交**。create-order 超时或返回异常时，先 query-order
   核对，再决定是否重试。

用法：
    python3 order.py quote  --store-code 1410574 --order-type 1 --be-type 1 \
        --items 9900005428:1 [--coupon-id ID --coupon-code CODE]
    python3 order.py submit --quote /tmp/quote.json --confirm [--take-way-code eat-in]
    python3 order.py status --order-id 12345
    python3 order.py claim  --confirm          # 领取全部可领的麦麦省券（全量！）
"""
from __future__ import annotations

import argparse
import hashlib
import json
import os
import sys
import time
from datetime import datetime
from pathlib import Path

HERE = Path(__file__).resolve().parent
sys.path.insert(0, str(HERE))

import fetch_menu as fm

STATE_DIR = Path(os.environ.get("MCD_ORDER_DIR", Path.home() / ".workbuddy" / "mcd-orders"))


# ── 小工具 ────────────────────────────────────────────────────

def money(fen) -> str:
    return f"¥{(fen or 0) / 100:.2f}"


# ── 支付入口 ──────────────────────────────────────────────────
#
# 实测（2026-10-25）create-order 只给 payH5Url，而 payH5Url 打开是
# 「扫码进入麦当劳APP支付」的二维码页 —— 手机上自己扫不了自己的屏。
# 二维码里编的其实是 https://m.mcd.cn/mcp/jumpToApp?orderId=xxx，
# 那一页有一枚「去麦当劳APP完成支付」按钮，点下去唤起 App 收银台
# （深链带 openCashierDesk=1）。所以真正能「一点就到买单」的是后两条。

PAY_JUMP = "https://m.mcd.cn/mcp/jumpToApp?orderId={oid}"


def pay_entries(order_id: str, h5: str = "") -> dict:
    oid = str(order_id or "")
    deep = ("mcdapp://page?iosPageName=MCDOrderDetailViewController"
            "&androidPageName=ComponentOrder&androidPageAction=order_detail"
            "&harmonyPageName=OrderDetailPage&parameters="
            '%7B%22orderId%22%3A%22' + oid + '%22%2C%22openCashierDesk%22%3A%221%22%7D')
    return {"h5": h5 or "", "jump": PAY_JUMP.format(oid=oid) if oid else "", "deep": deep if oid else ""}


def fingerprint(ctx: dict, items: list, take_way: str, address: str) -> str:
    body = json.dumps({
        "s": ctx.get("storeCode"), "o": ctx.get("orderType"), "b": ctx.get("beType"),
        "bc": ctx.get("beCode", ""), "items": items, "tw": take_way, "addr": address,
    }, ensure_ascii=False, sort_keys=True)
    return hashlib.sha256(body.encode()).hexdigest()[:16]


def parse_items(spec: str) -> list[dict]:
    """`code:qty,code:qty` → items。兼容 `code` 单件。"""
    out = []
    for chunk in (spec or "").split(","):
        chunk = chunk.strip()
        if not chunk:
            continue
        if ":" in chunk:
            code, qty = chunk.split(":", 1)
        else:
            code, qty = chunk, "1"
        out.append({"productCode": code.strip(), "quantity": int(qty)})
    return out


def deep_find(obj, keys: tuple[str, ...], max_depth: int = 6):
    """在任意层级的响应里找字段 —— create-order 的返回结构没文档，只能这样兜。"""
    if max_depth < 0:
        return None
    if isinstance(obj, dict):
        for k in keys:
            if k in obj and obj[k] not in (None, "", 0):
                return obj[k]
        for v in obj.values():
            hit = deep_find(v, keys, max_depth - 1)
            if hit:
                return hit
    elif isinstance(obj, list):
        for v in obj[:8]:
            hit = deep_find(v, keys, max_depth - 1)
            if hit:
                return hit
    return None


def save(kind: str, payload: dict) -> Path:
    STATE_DIR.mkdir(parents=True, exist_ok=True)
    p = STATE_DIR / f"{kind}-{datetime.now().strftime('%Y%m%d-%H%M%S')}.json"
    p.write_text(json.dumps(payload, ensure_ascii=False, indent=2), encoding="utf-8")
    return p


# ── 算价 ──────────────────────────────────────────────────────

# create-order / query-order 里真正可用的字段名（2026-10 实测，不要凭猜）
ORDER_ID_KEYS = ("orderId", "orderNo", "orderCode", "mcdOrderId")
PAY_URL_KEYS = ("payH5Url", "payUrl", "payLink", "payH5Link", "h5Url",
                "cashierUrl", "redirectUrl")
DETAIL_KEYS = ("orderId", "orderStatus", "status", "storeName", "storeAddress",
               "orderProductList", "totalAmount", "realTotalAmount",
               "totalDiscountAmount", "couponList", "createTime", "takeWay",
               "pickupCode", "expirePayTime", "payId", "deliveryPrice",
               "productPrice", "remark")


def call_price(ctx: dict, items: list, address_id: str = "") -> dict:
    args = {**ctx, "items": items}
    if address_id:
        args["addressId"] = address_id
    r = fm.call("calculate-price", args)
    if not r.get("success"):
        return {"ok": False, "msg": r.get("message") or "核价失败", "code": r.get("code")}
    d = r.get("data") or {}
    return {
        "ok": True,
        "total": d.get("price") or 0,
        "original": d.get("originalPrice") or 0,
        "discount": d.get("discount") or 0,
        "product": d.get("productPrice") or 0,
        "delivery_fee": d.get("deliveryPrice") or 0,
        "packing_fee": d.get("packingPrice") or 0,
        "take_way": d.get("takeWayList") or [],
        "products": d.get("productList") or [],
        "raw": d,
    }


def print_quote(q: dict):
    print(f"\n{'═'*58}")
    print(f"  {'外送' if q['orderType'] == 2 else '到店'} "
          f"· 门店 {q['storeCode']} · {q.get('beCode') or '自取不传 beCode'}")
    print(f"{'═'*58}")
    for p in q["products"]:
        if p.get("productCode") == "920174":
            continue
        print(f"  {p.get('productName','?'):<26} ×{p.get('quantity',1):<3} {money(p.get('subtotal'))}")
    if q.get("coupon"):
        print(f"  券：{q['coupon']['title']}")
    if q["delivery_fee"]:
        print(f"  配送费                        {money(q['delivery_fee'])}")
    if q["packing_fee"]:
        print(f"  打包费                        {money(q['packing_fee'])}")
    print(f"{'─'*58}")
    print(f"  原价 {money(q['original'])}   优惠 -{money(q['discount'])}   "
          f"应付 {money(q['total'])}")
    if q["take_way"]:
        print(f"  取餐方式： " + " / ".join(f"{t.get('title')}({t.get('code')})" for t in q["take_way"]))
    print(f"{'═'*58}\n")


def cmd_quote(a):
    ctx = {"storeCode": a.store_code, "orderType": a.order_type, "beType": a.be_type}
    if a.be_code:
        ctx["beCode"] = a.be_code
    if a.order_type == 2 and not a.be_code:
        sys.exit("外送必须传 --be-code（来自 delivery-query-stores）")
    if a.order_type == 2 and not a.address_id:
        sys.exit("外送必须传 --address-id（来自 delivery-query-addresses，需用户确认）")

    items = parse_items(a.items)
    if a.coupon_id:
        if not a.coupon_code:
            sys.exit("传了 --coupon-id 就要同时传 --coupon-code（核价要求两者成对）")
        # 券挂在价格最接近券面价的那一件上
        items[0]["couponId"] = a.coupon_id
        items[0]["couponCode"] = a.coupon_code

    price = call_price(ctx, items, a.address_id)
    if not price["ok"]:
        sys.exit(f"核价失败：{price['msg']}")

    q = {
        "created_at": datetime.now().strftime("%Y-%m-%d %H:%M:%S"),
        **ctx, "addressId": a.address_id, "items": items,
        "coupon": {"id": a.coupon_id, "code": a.coupon_code, "title": a.coupon_title} if a.coupon_id else None,
        "total": price["total"], "original": price["original"], "discount": price["discount"],
        "product": price["product"], "delivery_fee": price["delivery_fee"],
        "packing_fee": price["packing_fee"], "take_way": price["take_way"],
        "products": price["products"],
    }
    q["fingerprint"] = fingerprint(ctx, items, "", a.address_id)
    p = save("quote", q)
    print_quote(q)
    print(f"  报价已存：{p}")
    print(f"  指纹 {q['fingerprint']} —— 下单时会重算，价格变了就不下\n")


def pick_take_way(take_way_list: list) -> str:
    """从 calculate-price 的 takeWayList 里挑一个能用的取餐方式。

    堂食优先（用户站在店里最快），其次是外带/取餐柜，最后才退回第一项。
    绝不硬编码 "eat-in"：门店不同，可取的方式也不同。
    """
    codes = [t.get("code") for t in (take_way_list or []) if t.get("code")]
    for want in ("eat-in", "locker-in", "take-out", "drive-thru"):
        if want in codes:
            return want
    return codes[0] if codes else ""


def build_quote(*, store_code: str, order_type: int = 1, be_type: int = 1,
                be_code: str = "", address_id: str = "", items: list | None = None,
                coupon: dict | None = None, remark: str = "",
                need_tableware: bool = False) -> dict:
    """算价并装配成一份「可提交的报价单」。CLI 与服务端共用，避免两边字段长歪。

    券（couponId + couponCode）必须成对挂在同一件商品上，这是 calculate-price 的硬要求。
    """
    items = [dict(x) for x in (items or [])]
    if coupon and coupon.get("id") and items:
        items[0]["couponId"] = coupon["id"]
        items[0]["couponCode"] = coupon.get("code", "")

    ctx = {"storeCode": store_code, "orderType": order_type, "beType": be_type}
    if be_code:
        ctx["beCode"] = be_code

    price = call_price(ctx, items, address_id)
    return {
        "ok": price["ok"],
        "message": price.get("msg", ""),
        "created_at": datetime.now().strftime("%Y-%m-%d %H:%M:%S"),
        **ctx,
        "addressId": address_id,
        "items": items,
        "coupon": coupon or None,
        "remark": remark,
        "needTableware": need_tableware,
        "total": price.get("total", 0),
        "original": price.get("original", 0),
        "discount": price.get("discount", 0),
        "product": price.get("product", 0),
        "delivery_fee": price.get("delivery_fee", 0),
        "packing_fee": price.get("packing_fee", 0),
        "take_way": price.get("take_way", []),
        "products": price.get("products", []),
    }


# ── 下单 ──────────────────────────────────────────────────────

def place(quote: dict, take_way: str = "", confirm: bool = False,
          accept_change: bool = False) -> dict:
    """确认页 → 重算 → 创建订单。CLI 与本地服务共用这一条路径。

    返回 stage 说明卡在哪一步：
      quoted       重算过，但还没确认（预览）
      price-changed 价格变了且未接受
      reprice-failed 重算失败（券失效/售罄）
      create-failed 接口拒绝
      created      订单已创建
    """
    q = quote
    ctx = {k: q[k] for k in ("storeCode", "orderType", "beType")}
    if q.get("beCode"):
        ctx["beCode"] = q["beCode"]

    if q["orderType"] == 2 and not q.get("addressId"):
        return {"ok": False, "stage": "bad-request", "message": "外送订单缺少 addressId"}

    # 先重算：价格、取餐方式都以此为准，不信前端传过来的旧数
    price = call_price(ctx, q["items"], q.get("addressId", ""))
    if not price["ok"]:
        return {"ok": False, "stage": "reprice-failed",
                "message": f"重算失败：{price['msg']}（多半是券失效或商品售罄）"}

    if q["orderType"] == 1 and not take_way:
        take_way = pick_take_way(price["take_way"])
    if q["orderType"] == 1 and not take_way:
        return {"ok": False, "stage": "bad-request",
                "message": "门店没返回可用的取餐方式（takeWayList 为空），不能下单"}

    changed = abs(price["total"] - q["total"]) > 1
    if changed and not accept_change:
        return {"ok": False, "stage": "price-changed",
                "message": f"价格从 {money(q['total'])} 变成 {money(price['total'])}，未提交",
                "before": q["total"], "after": price["total"]}
    if not confirm:
        return {"ok": False, "stage": "quoted", "message": "预览：未确认，不会创建订单",
                "total": price["total"], "takeWayCode": take_way}

    body = {"storeCode": q["storeCode"], "orderType": q["orderType"],
            "beType": q["beType"], "items": q["items"],
            "needTableware": bool(q.get("needTableware"))}
    if q.get("beCode"):
        body["beCode"] = q["beCode"]
    if q["orderType"] == 2:
        body["addressId"] = q["addressId"]
        if q.get("remark"):
            body["remark"] = str(q["remark"])[:50]
    else:
        body["takeWayCode"] = take_way

    r = fm.call("create-order", body)
    if not r.get("success"):
        msg = r.get("message") or ""
        timeout = ("超时" in msg) or ("timeout" in msg.lower())
        save("order-failed", {"request": body, "response": r})
        return {"ok": False, "stage": "create-failed", "message": msg,
                "timeout": timeout, "detail": r}

    data = r.get("data") or {}
    det = data.get("orderDetail") or {}
    order_id = data.get("orderId") or deep_find(data, ORDER_ID_KEYS)
    pay_url = data.get("payH5Url") or deep_find(data, PAY_URL_KEYS)
    if isinstance(pay_url, dict):
        pay_url = deep_find(pay_url, ("url", "payUrl", "h5Url", "redirectUrl")) or ""

    rec = {"request": body, "response": data, "orderId": order_id,
           "payId": data.get("payId") or det.get("payId"),
           "payUrl": pay_url, "total": price["total"],
           "pay": pay_entries(order_id, pay_url),
           "created_at": datetime.now().strftime("%Y-%m-%d %H:%M:%S")}
    p = save("order", rec)
    return {"ok": True, "stage": "created", "orderId": order_id,
            "payId": rec["payId"], "payUrl": pay_url,
            "pay": rec["pay"], "appUrl": rec["pay"]["jump"], "deepLink": rec["pay"]["deep"],
            "total": price["total"], "takeWayCode": take_way,
            "expire_at": det.get("expirePayTime", ""),
            "order": {k: det.get(k) for k in DETAIL_KEYS if k in det},
            "detail": data, "saved": str(p)}


def cmd_submit(a):
    q = json.loads(Path(a.quote).read_text(encoding="utf-8"))
    take_way = a.take_way_code or (q["take_way"][0]["code"] if q.get("take_way") else "")

    print("\n【提交前重算】")
    r = place(q, take_way, confirm=a.confirm, accept_change=a.accept_change)

    if r["stage"] == "price-changed":
        print("  ⚠ " + r["message"] + "；确认接受请加 --accept-change")
        return
    if r["stage"] in ("reprice-failed", "bad-request"):
        sys.exit("  " + r["message"])
    print(f"  ✓ 当前应付 {money(r.get('total', q['total']))}")

    print("\n【订单内容】")
    for it in q["items"]:
        print(f"  {it['productCode']:<16} ×{it['quantity']}"
              f"{'  (用券 ' + it.get('couponCode', '') + ')' if it.get('couponId') else ''}")
    print(f"  取餐/配送：{take_way or '外送 ' + str(q.get('addressId'))}")
    print(f"  应付：{money(r.get('total', q['total']))}")

    if r["stage"] == "quoted":
        print("\n  这只是预览。确认后加 --confirm 才会真正创建订单。")
        return
    if r["stage"] == "create-failed":
        print(f"\n  ✗ 下单失败：{r['message']}")
        if r.get("timeout"):
            print("  ⚠ 超时：结果不确定，先去麦当劳 App「我的订单」核对，不要重复提交。")
        print(json.dumps(r.get("detail") or {}, ensure_ascii=False)[:500])
        return

    print("\n  ✅ 订单已创建")
    print(f"  订单号：{r['orderId'] or '（响应里没找到订单号，见下方原始返回）'}")
    print(f"  支付入口：{r['payUrl'] or '（没找到支付链接，请到麦当劳 App 完成支付）'}")
    if not r["orderId"]:
        print("  原始返回：" + json.dumps(r.get("detail"), ensure_ascii=False)[:500])
    print(f"  记录已存：{r['saved']}")
    if r["orderId"]:
        print(f"\n  支付后查状态：python3 order.py status --order-id {r['orderId']}")


# ── 查单 ──────────────────────────────────────────────────────

STATUS_HINT = {
    "1": "待支付", "2": "已支付/制作中", "3": "已完成", "4": "已取消",
}


def cmd_status(a):
    r = fm.call("query-order", {"orderId": str(a.order_id)})
    if not r.get("success"):
        sys.exit(f"查询失败：{r.get('message')}")
    d = r.get("data") or {}
    print(json.dumps(d, ensure_ascii=False, indent=2)[:2000])
    st = deep_find(d, ("orderStatus", "status", "orderStatusName", "statusName"))
    print(f"\n  订单 {a.order_id} 状态：{st}")
    return


# ── 领券 ──────────────────────────────────────────────────────

def cmd_claim(a):
    r0 = fm.call("available-coupons", {})
    rows = r0.get("data") or []
    can = [c for c in rows if (c.get("couponStatus") or "CAN_GET") == "CAN_GET"]
    print(f"\n可领券 {len(can)} 张：")
    for c in can:
        print(f"  · {c.get('couponName')}")
    if not can:
        print("  暂无可领的券。")
        return
    print("\n  ⚠ auto-bind-coupons 会领取**全部**可领的麦麦省券，不是只领其中一张。")
    if not a.confirm:
        print("  这只是预览。确认后加 --confirm 才会真正领取。")
        return
    r = fm.call("auto-bind-coupons", {})
    print(f"\n  领取结果 success={r.get('success')} msg={r.get('message')}")
    print(json.dumps(r.get("data"), ensure_ascii=False)[:400])
    if r.get("success"):
        print("\n  已重新查询卡包：")
        try:
            import coupons as cp
            for c in cp.load_wallet():
                print(f"    · {c['title']}")
        except Exception as e:
            print("    查询卡包失败：", e)


# ── 取消订单 ──────────────────────────────────────────────────

CANCEL_REASON = {
    "1": "改主意了", "2": "重复下单", "3": "点错了/点多了/点少了",
    "4": "地址/电话填错了", "5": "送达时间选错了", "-1": "其它原因",
}


def cmd_cancel(a):
    r = fm.call("cancel-order", {"orderId": str(a.order_id),
                                 "cancelReasonCode": str(a.reason)})
    if not r.get("success"):
        sys.exit(f"取消失败：{r.get('message')}")
    print(f"\n  ✅ 订单 {a.order_id} 已取消"
          f"（原因：{CANCEL_REASON.get(str(a.reason), a.reason)}）")
    if r.get("data"):
        print(json.dumps(r["data"], ensure_ascii=False)[:400])


def main():
    ap = argparse.ArgumentParser(description="麦麦黄道吉日 · 算价 / 领券 / 下单")
    sub = ap.add_subparsers(dest="cmd", required=True)

    q = sub.add_parser("quote", help="只算价，不产生任何写操作")
    q.add_argument("--store-code", required=True)
    q.add_argument("--order-type", type=int, default=1)
    q.add_argument("--be-type", type=int, default=1)
    q.add_argument("--be-code")
    q.add_argument("--address-id")
    q.add_argument("--items", required=True, help="code:qty,code:qty")
    q.add_argument("--coupon-id")
    q.add_argument("--coupon-code")
    q.add_argument("--coupon-title", default="")
    q.set_defaults(func=cmd_quote)

    s = sub.add_parser("submit", help="重算 + 创建订单（需 --confirm）")
    s.add_argument("--quote", required=True)
    s.add_argument("--take-way-code")
    s.add_argument("--confirm", action="store_true")
    s.add_argument("--accept-change", action="store_true")
    s.set_defaults(func=cmd_submit)

    st = sub.add_parser("status", help="查询订单状态")
    st.add_argument("--order-id", required=True)
    st.set_defaults(func=cmd_status)

    c = sub.add_parser("claim", help="领取可领的麦麦省券（需 --confirm）")
    c.add_argument("--confirm", action="store_true")
    c.set_defaults(func=cmd_claim)

    x = sub.add_parser("cancel", help="取消订单")
    x.add_argument("--order-id", required=True)
    x.add_argument("--reason", default="2", help="1改主意/2重复下单/3点错/4地址错/5时间错/-1其它")
    x.set_defaults(func=cmd_cancel)

    a = ap.parse_args()
    a.func(a)


if __name__ == "__main__":
    main()
