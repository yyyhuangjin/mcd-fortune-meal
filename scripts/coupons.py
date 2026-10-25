#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
优惠券比价引擎 —— 只信核价，不猜折扣

设计红线（改了会骗人）：
  1. 券面只用来「筛」，省多少钱一律由 calculate-price 实测得出。
  2. 券能不能用，先本地预校验（日期 / 星期 / 时段 / 点餐方式），
     别拿一堆注定报错的券去刷接口。
  3. 验不过的券要说清楚为什么，不许静默丢弃。
  4. 券对应的商品拿不到时（products 字段为空），用标题模糊匹配 + 核价双重确认，
     匹配结果一律标注为「推测」。

用法：
  python3 scripts/coupons.py list   --store-code 1950564 --order-type 1 --be-type 1
  python3 scripts/coupons.py check  --store-code 1950564 --items 1440
  python3 scripts/coupons.py claim              # 领取麦麦省券（会动账号资产，需显式执行）
"""

from __future__ import annotations

import argparse
import json
import re
import sys
from datetime import date, datetime, time
from difflib import SequenceMatcher

import fetch_menu as fm

# 麦当劳的 weekdays 约定：1=周日, 2=周一 … 7=周六（已用「周一至周五 = [2..6]」实测确认）
WD_CN = {1: "周日", 2: "周一", 3: "周二", 4: "周三", 5: "周四", 6: "周五", 7: "周六"}
BT_CN = {1: "到店取餐", 2: "麦乐送到家", 5: "得来速", 6: "企业团餐"}


def mcd_weekday(d: date) -> int:
    """Python isoweekday 是 1=周一…7=周日，转成麦当劳口径"""
    return d.isoweekday() % 7 + 1


# ── 券面权益解析 ────────────────────────────────────────────────

def parse_benefit(title: str, discount: dict | None = None) -> dict:
    """把券标题翻译成结构化权益。拿不准就给 unknown，不硬猜。"""
    title = (title or "").strip()
    b = {"kind": "unknown", "price": None, "target": None, "qty": 1,
         "threshold": None, "raw": title}

    # 满 30 减 5
    m = re.search(r"满\s*(\d+(?:\.\d+)?)\s*减\s*(\d+(?:\.\d+)?)", title)
    if m:
        b.update(kind="threshold", threshold=float(m.group(1)), price=float(m.group(2)))
        return b

    # 5 折 / 75折
    m = re.search(r"(\d+(?:\.\d+)?)\s*折", title)
    if m:
        b.update(kind="discount", price=float(m.group(1)))
        return b

    # 11.9元麦辣鸡腿堡 / 免费脆薯饼
    m = re.search(r"(\d+(?:\.\d+)?)\s*元\s*(.+)", title)
    if m:
        b.update(kind="fixed_price", price=float(m.group(1)), target=m.group(2).strip())
    else:
        m = re.search(r"^免费\s*(.+)", title)
        if m:
            b.update(kind="fixed_price", price=0.0, target=m.group(1).strip())

    tgt = b["target"]
    if tgt:
        q = re.search(r"任选\s*(\d+)", tgt)
        if q:
            b["qty"] = int(q.group(1))
            b["target"] = tgt[: q.start()].strip()
        else:
            q = re.search(r"[x×]\s*(\d+)", tgt)
            if q:
                b["qty"] = int(q.group(1))
                b["target"] = tgt[: q.start()].strip()

    # 券面没写清价格时，退回 discountInfo
    if b["price"] is None and discount:
        try:
            b["price"] = float(discount.get("discountValue"))
            if b["kind"] == "unknown":
                b["kind"] = "fixed_price"
        except (TypeError, ValueError):
            pass
    return b


# ── 有效期预校验 ────────────────────────────────────────────────

def _fmt_wd(wds: list[int]) -> str:
    wds = sorted(set(wds))
    if len(wds) == 7:
        return "每天"
    if wds == [2, 3, 4, 5, 6]:
        return "周一至周五"
    if wds == [1, 7]:
        return "周末"
    return "、".join(WD_CN.get(w, str(w)) for w in wds)


def _parse_dt(s: str | None):
    if not s:
        return None
    for fmt in ("%Y-%m-%d %H:%M:%S", "%Y-%m-%d %H:%M", "%Y-%m-%d"):
        try:
            return datetime.strptime(s, fmt)
        except ValueError:
            continue
    return None


def _in_period(now: time, periods: list[dict]) -> bool:
    if not periods:
        return True
    for p in periods:
        try:
            st = time.fromisoformat(p["startTime"])
            et = time.fromisoformat(p["endTime"])
        except (KeyError, ValueError):
            continue
        if st <= now <= et:
            return True
    return False


def precheck(c: dict, now: datetime, order_type: int, be_type: int) -> tuple[str, str]:
    """返回 (status, reason)。status ∈ ok / upcoming / expired / blocked

    顺序刻意如此：先判断「还没到 / 已过」，因为这是最有信息量的原因。
    注意：必须读 normalize() 产出的 start/end，别去读原始字段名。
    """
    start = c.get("start")
    end = c.get("end")

    if start and now < start:
        return "upcoming", f"{start:%m-%d %H:%M} 起可用"
    if end and now > end:
        return "expired", f"{end:%m-%d %H:%M} 已过期"

    wds = c.get("weekdays") or []
    if wds and mcd_weekday(now.date()) not in wds:
        return "blocked", f"限{_fmt_wd(wds)}可用"

    periods = c.get("tradeTimePeriods") or []
    if not _in_period(now.time(), periods):
        seg = "、".join(f"{p['startTime'][:5]}-{p['endTime'][:5]}" for p in periods)
        return "blocked", f"限 {seg} 可用"

    if order_type not in (c.get("orderTypes") or [order_type]):
        return "blocked", "不适用于该点餐方式"

    if be_type not in (c.get("beTypes") or [be_type]):
        return "blocked", f"不适用{BT_CN.get(be_type, be_type)}"

    if c.get("currentDayAvailableCount", 1) == 0:
        return "blocked", "今日可用次数为 0"

    return "ok", ""


# ── 数据获取 ──────────────────────────────────────────────────

def normalize(c: dict) -> dict:
    return {
        "id": c.get("id"),
        "code": c.get("code"),
        "title": c.get("title") or "",
        "benefit": parse_benefit(c.get("title"), c.get("discountInfo")),
        "start": _parse_dt(c.get("tradeStartDateTime") or c.get("tradeStartDate")),
        "end": _parse_dt(c.get("tradeEndDateTime") or c.get("tradeEndDate")),
        "window": (c.get("tradeStartDateTime"), c.get("tradeEndDateTime")),
        "weekdays": c.get("weekdays") or [],
        "order_types": c.get("orderTypes") or [],
        "be_types": c.get("beTypes") or [],
        "channel_ok": c.get("currentChannelCanRedeem"),
        "toast": c.get("toastText") or "",
        "products": c.get("products") or [],
    }


def load_wallet(page_size: int = 200) -> list[dict]:
    """用户卡包全量券（不等于当前门店可用）"""
    r = fm.call("query-my-coupons", {"page": "1", "pageSize": str(page_size)})
    if not r.get("success"):
        return []
    d = r.get("data") or {}
    raw = d.get("coupons") if isinstance(d, dict) else d
    return [normalize(c) for c in (raw or [])]


def load_store_coupons(store_code: str, order_type: int, be_type: int) -> list[dict]:
    """当前门店+点餐方式下真正可用的券（权威口径）"""
    args = {"storeCode": store_code, "orderType": order_type, "beType": be_type}
    r = fm.call("query-store-coupons", args)
    if not r.get("success"):
        return []
    d = r.get("data")
    raw = d.get("coupons") if isinstance(d, dict) else d
    return raw or []


def load_claimable() -> list[dict]:
    r = fm.call("available-coupons", {})
    return r.get("data") or [] if r.get("success") else []


def claim_all() -> dict:
    """领取麦麦省全部可领券 —— 会改变账号资产，只在用户明确要求时调用"""
    return fm.call("auto-bind-coupons", {})


# ── 菜品匹配 ──────────────────────────────────────────────────

COMBO_HINT = ("套餐", "三件套", "四件套", "八件套", "分享餐", "双人餐", "随心配", "拼盘")


def match_items(target: str, pool: dict, topn: int = 3, threshold: float = 0.6) -> list[dict]:
    """按标题与菜单名做相似度匹配。券的 products 字段常常是空的，只能靠这个。

    「11.9元麦辣鸡腿堡」既像「麦辣鸡腿汉堡」，也像「麦辣鸡腿汉堡三件套」。
    券几乎总是作用在单点上，所以对套餐类名字降权，避免把三件套算成券的受益商品
    ——那会把省的钱虚报一倍。
    """
    if not target:
        return []
    scored = []
    for it in pool.values():
        ratio = SequenceMatcher(None, target, it["name"]).ratio()
        if target in it["name"]:
            ratio = max(ratio, 0.95)
        if any(h in it["name"] for h in COMBO_HINT):
            ratio -= 0.12
        if ratio >= threshold:
            scored.append((ratio, it))
    scored.sort(key=lambda x: (-x[0], x[1]["price"]))
    return [dict(it, match=round(r, 2)) for r, it in scored[:topn]]


def estimate_saving(coupon: dict, pool: dict) -> list[dict]:
    """按菜单快照价预估省多少 —— 仅供展示，最终一律以核价为准。

    排序沿用匹配度（不按省钱多少排），否则会把最贵的套餐顶到第一行，
    看起来"省得多"，实际券根本不作用于它。
    """
    b = coupon["benefit"]
    if b["kind"] != "fixed_price" or b["price"] is None or not b["target"]:
        return []
    out = []
    for it in match_items(b["target"], pool, topn=3):
        if it["price"] <= 0:
            continue
        if b["qty"] > 1:
            saving = it["price"] * b["qty"] - b["price"]
        else:
            saving = it["price"] - b["price"]
        out.append({**it, "est_saving": round(saving, 1),
                    "is_combo": any(h in it["name"] for h in COMBO_HINT)})
    return out


# ── 真实核价验证 ───────────────────────────────────────────────

def price_of(items: list[dict], ctx: dict) -> dict:
    """items: [{productCode, quantity, couponId?, couponCode?}]"""
    r = fm.call("calculate-price", {**ctx, "items": items})
    if not r.get("success"):
        return {"ok": False, "msg": r.get("message") or "核价失败"}
    d = r.get("data") or {}
    return {"ok": True, "price": d.get("price"), "original": d.get("originalPrice"),
            "discount": d.get("discount"), "detail": d}


def verify_on_items(items: list[dict], coupon: dict, ctx: dict) -> dict:
    """把券挂到 items 里最匹配的一件上，前后各核一次价，看真实节省额。

    这是整套券逻辑的唯一裁判：核价不降，就是不省。
    """
    base_items = [{"productCode": i["code"], "quantity": 1} for i in items]
    before = price_of(base_items, ctx)
    if not before["ok"]:
        return {"ok": False, "stage": "before", "msg": before["msg"]}

    # 挑一张券最可能作用的商品：优先标题匹配，其次价格最接近券面价
    b = coupon["benefit"]
    target_code = None
    if b["target"]:
        m = match_items(b["target"], {i["code"]: i for i in items}, topn=1, threshold=0.5)
        if m:
            target_code = m[0]["code"]
    if target_code is None and b["price"] is not None:
        target_code = min(items, key=lambda i: abs(i["price"] - b["price"]))["code"]
    if target_code is None:
        target_code = items[0]["code"]

    trial = []
    for i in items:
        row = {"productCode": i["code"], "quantity": 1}
        if i["code"] == target_code:
            row["couponId"] = coupon["id"]
            row["couponCode"] = coupon["code"]
        trial.append(row)

    after = price_of(trial, ctx)
    if not after["ok"]:
        return {"ok": False, "stage": "after", "msg": after["msg"],
                "before": before["price"]}

    saving = (before["price"] or 0) - (after["price"] or 0)
    return {
        "ok": saving > 0,
        "stage": "done",
        "coupon": coupon["title"],
        "coupon_id": coupon["id"],
        "on_item": next((i["name"] for i in items if i["code"] == target_code), ""),
        "before": before["price"],
        "after": after["price"],
        "saving": saving,
        "msg": "" if saving > 0 else "核价未降价，该券对本单无效",
    }


def optimize_plan(plan: dict, analysed: list[dict], ctx: dict) -> dict:
    """给一套方案挑最省的那张券（只考虑今日可用的券）"""
    usable = [c for c in analysed if c["status"] == "ok"]
    best = None
    for c in usable:
        r = verify_on_items(plan["items"], c, ctx)
        if r.get("ok") and (best is None or r["saving"] > best["saving"]):
            best = r
    return best


# ── 汇总 ────────────────────────────────────────────────────

def analyze(store_code: str, order_type: int, be_type: int,
            pool: dict | None = None, now: datetime | None = None) -> dict:
    now = now or datetime.now()
    wallet = load_wallet()
    store_list = load_store_coupons(store_code, order_type, be_type)
    store_ids = {c.get("couponId") or c.get("id") for c in store_list}

    buckets = {"usable": [], "upcoming": [], "expired": [], "blocked": []}
    for c in wallet:
        status, reason = precheck(c, now, order_type, be_type)
        entry = {
            "id": c["id"], "code": c["code"], "title": c["title"],
            "benefit": c["benefit"], "status": status, "reason": reason,
            "window": c["window"], "weekdays": c["weekdays"],
            "channel_ok": c["channel_ok"], "toast": c["toast"],
            "matches": estimate_saving(c, pool) if pool else [],
        }
        if status == "ok":
            # 门店口径二次确认：卡包能用 ≠ 这家店能用。
            # 门店接口返回空时无法反证，标记 store_confirmed=False，
            # 后续由 calculate-price 做最终裁决（optimize_plan 里）。
            entry["store_confirmed"] = bool(store_list) and c["id"] in store_ids
            if store_list and not entry["store_confirmed"]:
                entry["status"] = "blocked"
                entry["reason"] = "该门店当前不可用"
                buckets["blocked"].append(entry)
                continue
            buckets["usable"].append(entry)
        elif status == "upcoming":
            buckets["upcoming"].append(entry)
        elif status == "expired":
            buckets["expired"].append(entry)
        else:
            buckets["blocked"].append(entry)

    notes = []
    if store_list:
        notes.append(f"门店当前可用券 {len(store_list)} 张（query-store-coupons 口径）")
    else:
        notes.append("该门店+点餐方式下 query-store-coupons 返回空：当前没有门店级可用券")

    return {
        "checked_at": now.strftime("%Y-%m-%d %H:%M:%S"),
        "weekday": WD_CN[mcd_weekday(now.date())],
        "store_code": store_code,
        "order": {"orderType": order_type, "beType": be_type,
                  "beType_name": BT_CN.get(be_type, str(be_type))},
        "wallet_total": len(wallet),
        **buckets,
        "store_usable_count": len(store_list),
        "notes": notes,
    }


def render(rep: dict):
    print(f"\n{'═'*62}")
    print(f"  🎟  卡包 {rep['wallet_total']} 张  ·  {rep['checked_at']}（{rep['weekday']}）")
    print(f"  门店 {rep['store_code']} · {rep['order']['beType_name']}"
          f"  ·  门店级可用 {rep['store_usable_count']} 张")
    print(f"{'═'*62}")
    for tag, key, icon in (("今日可用", "usable", "✅"),
                           ("即将生效", "upcoming", "⏳"),
                           ("当前不可用", "blocked", "⛔"),
                           ("已过期", "expired", "🕓")):
        rows = rep[key]
        if not rows:
            continue
        print(f"\n  {icon} {tag}（{len(rows)}）")
        for c in rows:
            b = c["benefit"]
            money = ""
            if b["kind"] == "fixed_price" and b["price"] is not None:
                money = f"¥{b['price']:g}" + (f"/{b['qty']}件" if b["qty"] > 1 else "")
            elif b["kind"] == "threshold":
                money = f"满{b['threshold']:g}减{b['price']:g}"
            elif b["kind"] == "discount":
                money = f"{b['price']:g}折"
            line = f"    · {c['title']:<22} {money}"
            print(line)
            if c["status"] != "ok":
                print(f"       ↳ {c['reason']}")
            for i, m in enumerate(c["matches"][:1]):
                extra = "（推测，非券面明示）" if m.get("is_combo") else ""
                print(f"       → 可作用于「{m['name']}」现价 ¥{m['price']:g}"
                      f"，预估省 ¥{m['est_saving']:g}{extra}")
            if not c["matches"]:
                b = c["benefit"]
                if b["kind"] == "fixed_price" and b["target"]:
                    print(f"       → 菜单里找不到「{b['target']}」对应商品，需到店确认适用品")
                elif b["kind"] in ("threshold", "discount"):
                    print("       → 满减/折扣类，需按实际选品核价")
                elif b["kind"] == "unknown":
                    print("       → 券面权益无法解析，需人工确认")
            if c["channel_ok"] is False:
                print("       ⚠ 该渠道可能不能核销，下单前需实测")
            if c["status"] == "ok" and not c.get("store_confirmed"):
                print("       ⚠ 门店券接口未返回该券，能否用需核价确认")
            if len(c["matches"]) > 1:
                print(f"       （另有 {len(c['matches'])-1} 个候选商品）")
    for n in rep["notes"]:
        print(f"\n  · {n}")
    print()


def main():
    ap = argparse.ArgumentParser(description="麦当劳优惠券比价")
    sub = ap.add_subparsers(dest="cmd", required=True)

    s = sub.add_parser("list", help="列出卡包券与今日可用性")
    s.add_argument("--store-code", required=True)
    s.add_argument("--order-type", type=int, default=1)
    s.add_argument("--be-type", type=int, default=1)
    s.add_argument("--menu", help="菜单 JSON，用于预估可作用商品")
    s.add_argument("--json", action="store_true")
    s.add_argument("--now", help="按指定时间判断（YYYY-MM-DD HH:MM，用于演示）")

    s2 = sub.add_parser("check", help="对指定商品实测券是否真的省钱")
    s2.add_argument("--store-code", required=True)
    s2.add_argument("--order-type", type=int, default=1)
    s2.add_argument("--be-type", type=int, default=1)
    s2.add_argument("--items", required=True, help="商品编码，逗号分隔")

    s3 = sub.add_parser("claim", help="领取麦麦省可领券（会改变账号资产）")
    s3.add_argument("--yes", action="store_true", help="我确认要领取")

    a = ap.parse_args()

    if a.cmd == "claim":
        if not a.yes:
            sys.exit("领券会改变你的账号资产，加 --yes 才执行。可先跑 available-coupons 看看有什么。")
        r = claim_all()
        print(json.dumps(r, ensure_ascii=False, indent=2))
        return

    ctx = {"storeCode": a.store_code, "orderType": a.order_type, "beType": a.be_type}

    if a.cmd == "list":
        pool = None
        if a.menu:
            import suggest
            pool = suggest.build_pool(suggest.load_menu(a.menu))
        now = datetime.strptime(a.now, "%Y-%m-%d %H:%M") if a.now else None
        rep = analyze(a.store_code, a.order_type, a.be_type, pool=pool, now=now)
        if a.json:
            print(json.dumps(rep, ensure_ascii=False, indent=2))
        else:
            render(rep)
        return

    if a.cmd == "check":
        codes = [x.strip() for x in a.items.split(",") if x.strip()]
        items = [{"code": c, "name": c, "price": 0} for c in codes]
        rep = analyze(a.store_code, a.order_type, a.be_type)
        usable = [c for c in rep["usable"]]
        if not usable:
            print("今日没有可用券，无法比价。")
            print("卡包里不可用的：" + "；".join(
                f"{c['title']}（{c['reason']}）" for c in rep["upcoming"] + rep["blocked"]) or "无")
            return
        for c in usable:
            r = verify_on_items(items, c, ctx)
            print(f"\n{c['title']}")
            if r.get("ok"):
                print(f"  原价 {r['before']} 分 → 用券 {r['after']} 分，省 {r['saving']} 分")
            else:
                print(f"  未能省钱：{r.get('msg')}")


if __name__ == "__main__":
    main()
