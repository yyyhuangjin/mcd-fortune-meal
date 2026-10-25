#!/usr/bin/env python3
"""麦麦黄道吉日 · 数据装配 + 单文件交互页生成。

设计原则（全部来自实跑踩坑）：

1. 定位即查天气。用户只给地点，天气是内部信号，不在对话里播报。
2. 自取 / 外送必须**双向核价**才知道差多少钱 —— 外送会多出配送费与打包费，
   差额只有 calculate-price 说了算，不能估。
3. 拿不到的数据就标「暂不可用」，绝不拿今天的数字冒充别的日期。
4. 券只做筛选，省多少由核价裁决。
"""
from __future__ import annotations

import argparse
import json
import os
import re
import sys
import urllib.parse
import urllib.request
from datetime import date, datetime, timedelta
from pathlib import Path

HERE = Path(__file__).resolve().parent
ROOT = HERE.parent
sys.path.insert(0, str(HERE))

import coupons as cp
import daily_fortune as df
import fetch_menu as fm
import suggest as sg

WEB = ROOT / "web"
TIMEOUT = 20

CAT_MEAT = {
    "BEEF": "牛肉", "FISH": "鳕鱼", "CHICKEN": "鸡肉", "PORK": "猪柳",
    "FRIED": "炸物", "VEG": "蔬果", "POTATO": "薯条",
    "DESSERT": "甜品", "COFFEE": "咖啡", "TEA": "茶饮", "SODA": "汽水", "SHARE": "分享餐",
}

# 取餐方式 → 中文与说明
MODE_CN = {
    "pickup": ("到店自取", "店里做好自己拿，省下配送费"),
    "dinein": ("堂食", "就在店里吃，薯条最脆的那几分钟"),
    "delivery": ("麦乐送", "送到门口，雨天不用出门"),
    "either": ("自取外送都行", "当天可以 —— 两种都顺，看你方便"),
}


# ── 定位 ──────────────────────────────────────────────────────

PROVINCES = ("省", "自治区", "市")


def parse_address(full: str) -> dict:
    """「福建省厦门市思明区XX路…」→ 省 / 市 / 区"""
    out = {"province": "", "city": "", "district": "", "detail": full or ""}
    m = re.match(r"(.+?(?:省|自治区|北京市|上海市|天津市|重庆市))", full or "")
    if m:
        out["province"] = m.group(1)
        rest = full[m.end():]
    else:
        rest = full or ""
    m2 = re.match(r"(.+?(?:市|自治州|地区|盟))", rest)
    if m2:
        out["city"] = m2.group(1)
        rest = rest[m2.end():]
    m3 = re.match(r"(.+?(?:区|县|市))", rest)
    if m3:
        out["district"] = m3.group(1)
    return out


def geocode_city(city: str, province: str = "") -> tuple[float, float, str]:
    """城市 → 经纬度。Open-Meteo 对中文城市名的召回很挑，需要多候选 + 打分。

    踩过的坑：「上海」能查到，「上海市」反而落到美国伊利诺伊；
    「厦门」查不到，「厦门市」才行。所以两个都试，再按省份与行政级别校正。
    """
    cands = []
    for name in dict.fromkeys([city, city.rstrip("市"), city + "市"]):
        if not name:
            continue
        q = urllib.parse.urlencode({
            "name": name, "count": 10, "language": "zh", "format": "json", "countryCode": "CN",
        })
        try:
            with urllib.request.urlopen(
                f"https://geocoding-api.open-meteo.com/v1/search?{q}", timeout=TIMEOUT
            ) as r:
                cands += (json.loads(r.read().decode()).get("results") or [])
        except Exception:
            continue
        if cands:
            break

    if not cands:
        raise LookupError(f"定位不到城市：{city}")

    def score(g: dict) -> float:
        s = 0.0
        if province and g.get("admin1") and province.startswith(g["admin1"][:2]):
            s += 100
        if str(g.get("feature_code", "")).startswith("PPLA"):
            s += 50
        if g.get("name") == city.rstrip("市"):
            s += 30
        if g.get("country_code") == "CN":
            s += 20
        return s

    best = max(cands, key=score)
    place = (best.get("admin1") or "") + best.get("name", "")
    return best["latitude"], best["longitude"], place


def ip_locate() -> dict | None:
    """最后的兜底：按出口 IP 猜城市。失败不报错，交给默认值。"""
    for url, pick in (
        ("https://ipapi.co/json/", lambda d: (d.get("city"), d.get("region"), d.get("country_code"))),
        ("https://ipwho.is/", lambda d: (d.get("city"), d.get("region"), d.get("country_code"))),
    ):
        try:
            req = urllib.request.Request(url, headers={"User-Agent": "mcd-fortune-meal/1.2"})
            with urllib.request.urlopen(req, timeout=5) as r:
                d = json.loads(r.read().decode())
            city, region, cc = pick(d)
            if city and cc == "CN":
                return {"city": city, "province": region or "", "source": "网络定位"}
        except Exception:
            continue
    return None


def resolve_location(city: str | None) -> dict:
    """地点来源优先级：用户指定 > 已存配送地址 > IP 定位 > 默认。

    玩家只要能说出一个地点就行 —— 不需要自己报天气。
    """
    if city:
        lat, lon, place = geocode_city(city)
        return {"city": city, "province": "", "district": "", "lat": lat, "lon": lon,
                "place": place, "source": "你指定的地点", "address_id": "", "address": ""}

    # 1) 已存的外送地址 = 最准的「我在哪」
    try:
        r = fm.call("delivery-query-addresses", {})
        addrs = ((r.get("data") or {}).get("addresses") or [])
    except Exception:
        addrs = []
    if addrs:
        a = addrs[0]
        full = a.get("fullAddress", "")
        p = parse_address(full)
        target = p["city"] or p["province"]
        if target:
            try:
                lat, lon, place = geocode_city(target, p["province"])
                return {**p, "city": target, "lat": lat, "lon": lon, "place": place,
                        "source": "已存配送地址（自动定位）",
                        "address_id": a.get("addressId", ""), "address": full,
                        "contact": a.get("contactName", "")}
            except LookupError:
                pass

    # 2) IP 定位
    ip = ip_locate()
    if ip:
        try:
            lat, lon, place = geocode_city(ip["city"], ip["province"])
            return {"city": ip["city"], "province": ip["province"], "district": "",
                    "lat": lat, "lon": lon, "place": place, "source": "网络定位（近似）",
                    "address_id": "", "address": ""}
        except LookupError:
            pass

    # 3) 默认
    lat, lon, place = geocode_city("北京")
    return {"city": "北京", "province": "北京市", "district": "", "lat": lat, "lon": lon,
            "place": place, "source": "默认地点（没能自动定位）", "address_id": "", "address": ""}


# ── 门店 / 菜单 ────────────────────────────────────────────────

def pickup_stores(loc: dict) -> list[dict]:
    kw = loc.get("district") or loc.get("city")
    try:
        r = fm.call("query-nearby-stores", {
            "beType": 1, "searchType": 2, "city": loc["city"].rstrip("市"), "keyword": kw,
        })
        rows = r.get("data") or []
    except Exception:
        rows = []
    if not rows:
        try:
            r = fm.call("query-nearby-stores", {
                "beType": 1, "searchType": 2, "city": loc["city"].rstrip("市"),
            })
            rows = r.get("data") or []
        except Exception:
            rows = []
    rows = [s for s in rows if s.get("businessStatus") is not False]
    rows.sort(key=lambda s: s.get("distance") or 99999)
    return rows


def delivery_stores(loc: dict) -> list[dict]:
    if not loc.get("address_id"):
        return []
    try:
        r = fm.call("delivery-query-stores", {"addressId": loc["address_id"], "beType": 2})
        rows = r.get("data") or []
    except Exception:
        return []
    return [s for s in rows if s.get("businessStatus") is not False]


def menu_of(store_code: str, order_type: int, be_type: int, be_code: str = "") -> dict | None:
    args = {"storeCode": store_code, "orderType": order_type, "beType": be_type}
    if be_code:
        args["beCode"] = be_code
    try:
        r = fm.call("query-meals", args)
        if not r.get("success"):
            return None
        return r.get("data")
    except Exception:
        return None


MENU_GROUPS = {"main": "汉堡 / 主食", "side": "小食", "drink": "饮品", "dessert": "甜品"}


def menu_list(menu: dict | None) -> list[dict]:
    """整份菜单摊平：限定/上新是菜单的一部分，不是一个单独的展柜。

    只做「有什么、多少钱、属哪类、有没有限定标签」，不改价 ——
    页面显示的都是菜单快照价，真下单还会由 calculate-price 重算。
    """
    if not menu:
        return []
    meals = menu.get("meals") or {}
    seen, seen_name, out = set(), set(), []
    for c in menu.get("categories") or []:
        cname = (c.get("name") or "").replace("\n", "").strip()
        for m in c.get("meals") or []:
            code = m.get("code")
            if not code or code in seen or code not in meals:
                continue
            info = meals[code]
            name = info.get("name") or ""
            if not name or any(x in name for x in sg.NON_FOOD):
                continue
            if name in seen_name:
                continue          # 同一商品挂多个分类，按名字去重（菜单里会重复出现）
            seen.add(code)
            seen_name.add(name)
            tags = m.get("tags") or []
            hit = [sg.LIMITED_TAG[t] for t in tags if t in sg.LIMITED_TAG]
            cls = sg.classify(name)
            price = sg.parse_price(info.get("currentPrice"))
            out.append({
                "code": code, "name": name, "price": price,
                "original": sg.parse_price(info.get("originalPrice")),
                "cat": cls[0] if cls else "other",
                "cat_name": MENU_GROUPS.get(cls[0], "其他") if cls else "其他",
                "meat": cls[1] if cls else "",
                "group": cname,
                "tags": sorted(set(hit)),
                "limited": bool(hit),
            })
    # 限定置顶，其余按分类、价格
    order = {"main": 0, "side": 1, "drink": 2, "dessert": 3, "other": 4}
    out.sort(key=lambda x: (0 if x["limited"] else 1, order.get(x["cat"], 9), x["price"]))
    return out


def store_row(s: dict, kind: str) -> dict:
    """门店列表里的一行（到店 / 外送共用）。"""
    return {
        "kind": kind,
        "code": s.get("storeCode"),
        "name": s.get("storeName", ""),
        "address": s.get("address", ""),
        "distance": s.get("distance"),
        "beCode": s.get("beCode", ""),
        "open": f"{s.get('businessStartTime','')}-{s.get('businessEndTime','')}".strip("-"),
        "deliverable": bool(s.get("delivery") or s.get("isDelivery") or kind == "delivery"),
    }


def name_index(menu: dict) -> dict:
    """商品名 → (code, 快照价)。跨渠道比价只能靠名字对，SKU 编码两边不通用。"""
    idx = {}
    for code, m in (menu.get("meals") or {}).items():
        n = m.get("name")
        if n and n not in idx:
            idx[n] = (code, m.get("currentPrice"))
    return idx


def map_basket(items: list[dict], dmenu: dict | None) -> list[dict] | None:
    """把自取篮子的商品，按同名映射到外送菜单。

    踩过的坑：外送门店常常不是同一家店，SKU 编码完全不同
    （「培根安格斯厚牛堡三件套」在外送店根本不存在）。
    所以只认同名，不做模糊替换 —— 拿「四件套」冒充「三件套」算出来的差价是假的。
    """
    if not dmenu:
        return None
    idx = name_index(dmenu)
    out = []
    for it in items:
        hit = idx.get(it["name"])
        if not hit:
            return None
        out.append({"productCode": hit[0], "quantity": 1})
    return out


def compare_channels(plans: list[dict], dmenu: dict | None, ctx_ship: dict | None) -> dict | None:
    """自取 vs 外送：同一份篮子，两边各核一次价。"""
    if not ctx_ship or not dmenu:
        return None
    for i, p in enumerate(plans):
        basket = map_basket(p["items"], dmenu)
        if not basket:
            continue
        pick = price_of([{"productCode": b["productCode"], "quantity": 1} for b in basket], {
            "storeCode": ctx_ship["storeCode"], "orderType": 1, "beType": 1,
        })
        ship = price_of(basket, ctx_ship)
        if not ship["ok"]:
            continue
        # 自取价用「同店同品」重算，保证两边口径一致
        return {
            "plan_index": i,
            "plan_tag": p["tag"],
            "pickup": pick["total"] if pick["ok"] else p["total"],
            "delivery": ship["total"],
            "delivery_fee": ship["delivery_fee"],
            "packing_fee": ship["packing_fee"],
            "diff": round(ship["total"] - (pick["total"] if pick["ok"] else p["total"]), 2),
            "store": dmenu.get("_store", ""),
        }
    return None


def price_of(payload: list[dict], ctx: dict) -> dict:
    r = cp.price_of(payload, ctx)
    if not r.get("ok"):
        return {"ok": False, "msg": r.get("msg", "核价失败")}
    d = r.get("detail") or {}
    return {
        "ok": True,
        "total": round((r["price"] or 0) / 100, 2),
        "original": round((r.get("original") or 0) / 100, 2),
        "discount": round((r.get("discount") or 0) / 100, 2),
        "delivery_fee": round((d.get("deliveryPrice") or 0) / 100, 2),
        "packing_fee": round((d.get("packingPrice") or 0) / 100, 2),
        "product": round((d.get("productPrice") or 0) / 100, 2),
    }


# ── 方案 ──────────────────────────────────────────────────────

def extra_variants(fortune: dict, pool: dict) -> list[dict]:
    """再抽两签：同运势下的换位搭配，让「换一份好运」真有东西可换。"""
    mains = [x["cat"] for x in fortune["slots"]["main"]]
    sides = [x["cat"] for x in fortune["slots"]["side"]]
    drinks = [x["cat"] for x in fortune["slots"]["drink"]]
    bias = fortune["drink_bias"]

    m = sg.pick(pool, fortune, "main", mains, prefer_combo=False, limit=6)
    s = sg.pick(pool, fortune, "side", sides, limit=4)
    d = sg.pick(pool, fortune, "drink", drinks, bias=bias, limit=4)

    out = []
    combos = [(1, 1), (2, 2)]
    for mi, si in combos:
        if len(m) <= mi or len(s) <= min(si, len(s) - 1) or not d:
            continue
        items = [m[mi], s[min(si, len(s) - 1)], d[min(si, len(d) - 1)]]
        if len({i["code"] for i in items}) < len(items):
            continue
        out.append({
            "tag": "再抽一签", "icon": "🎲",
            "desc": "同一份运势，换个搭法",
            "items": items,
            "reason": f"主餐仍是「{CAT_MEAT.get(items[0]['cat'], '当下')}」当家，配菜换个口味",
        })
    return out


def finalize_plans(plans: list[dict], ctx: dict) -> list[dict]:
    """每套方案都过一遍真实核价 —— 菜单快照价经常不等于结算价。"""
    out = []
    for p in plans:
        payload = p.get("payload") or [{"productCode": i["code"], "quantity": 1} for i in p["items"]]
        v = price_of(payload, ctx)
        snapshot = round(sum(i["price"] for i in p["items"]), 2)
        row = {
            "tag": p["tag"], "icon": p["icon"], "desc": p["desc"], "reason": p["reason"],
            "notes": p.get("notes", []),
            "items": [{"code": i["code"], "name": i["name"], "price": i["price"],
                       "cat": i["cat"], "cat_name": i.get("cat_name", "")} for i in p["items"]],
            "snapshot": snapshot,
            "verified": v["ok"],
            "total": v["total"] if v["ok"] else snapshot,
            "discount": v.get("discount", 0) if v["ok"] else 0,
            "coupon": p.get("coupon"),
            "payload": payload,
        }
        if v["ok"]:
            diff = round(snapshot - v["total"], 2)
            if diff >= 0.05:
                row["adjust"] = {"kind": "discount", "amount": diff,
                                 "label": "套餐价与单点价差额"}
            elif diff <= -0.05:
                row["adjust"] = {"kind": "extra", "amount": -diff,
                                 "label": "包装/服务费"}
        out.append(row)
    return out


# ── 宜忌 / 签语 ────────────────────────────────────────────────

def day_luck(alm: dict) -> dict:
    """吉凶：传统看天神（黄道吉 / 黑道凶）+ 建星（破、闭最凶）。
    但本店历法只有一条铁律：凶日更要吃麦当劳——转运从这一口开始。"""
    unlucky = alm.get("tianshen_type") == "黑道" or alm.get("zhixing") in ("破", "闭")
    if unlucky:
        return {"luck": "凶", "luck_note": "黑道压顶？不怕——宜吃麦当劳，转运从第一口开始"}
    return {"luck": "吉", "luck_note": "黄道吉日，吃麦当劳是锦上添花"}


def make_yiji(f: dict, plan: dict, coupon_rep: dict, limited: list, logistics: dict) -> dict:
    """宜忌要好玩，但每一条都得挂在一件真实的事上。"""
    a, w = f["almanac"], f["weather"]
    t = w["feels_like"]
    rain = (w["precip_mm"] or 0) > 0 or (w["pop_max"] or 0) >= 60
    hot = t >= 28
    cold = t < 10
    main_cat = f["slots"]["main"][0]["cat"]
    meat = CAT_MEAT.get(main_cat, "今天想吃的那口")

    lk = day_luck(a)
    # 铁律：无论吉凶，第一条永远是「宜吃麦当劳」；凶日改成「转运」版
    if lk["luck"] == "凶":
        yi = ["宜吃麦当劳转运", f"宜吃{meat}压惊"]
    else:
        yi = ["宜吃麦当劳", f"宜吃{meat}"]
    if f["drink_bias"] == "hot":
        yi.append("宜热饮")
    elif f["drink_bias"] in ("cold", "ice"):
        yi.append("宜冰饮")
    else:
        yi.append("宜冷热皆可")

    yi.append({"delivery": "宜麦乐送", "pickup": "宜到店自取",
               "dinein": "宜堂食", "either": "宜出门走走"}[logistics["mode"]])

    if coupon_rep["usable"]:
        yi.append("宜用券")
    elif coupon_rep["upcoming"]:
        yi.append("宜记着明天的券")
    if limited:
        yi.append("宜尝新")
    if plan and any(CAT_MEAT.get(i["cat"]) in ("薯条", "炸物") for i in plan["items"]):
        yi.append("宜加一份小食")

    ji = ["忌饿着肚子看这篇"]
    if rain:
        ji.append("忌淋雨排队")
    if hot:
        ji.append("忌在太阳底下排队")
    if cold and any(i["cat"] == "DESSERT" for i in (plan["items"] if plan else [])):
        ji.append("忌贪凉")
    if coupon_rep["upcoming"]:
        ji.append("忌把券放到过期")
    if lk["luck"] == "凶":
        ji.append("忌空着手转运")
    if f["confidence"] == "low":
        ji.append("忌纠结太久")
    if len(ji) < 3:
        ji.append("忌一个人硬撑着省这顿")

    return {"yi": yi[:6], "ji": ji[:5], "luck": lk["luck"], "luck_note": lk["luck_note"]}


def make_sign(f: dict, plan: dict, logistics: dict) -> str:
    """今日签语：只写天气的「感觉」，不背温度数字。"""
    w = f["weather"]
    t = w["feels_like"]
    rain = (w["precip_mm"] or 0) > 0 or (w["pop_max"] or 0) >= 60
    if rain:
        head = "天降微雨，宜在家等一份热乎的敲门"
    elif t >= 28:
        head = "日头正盛，宜用一杯冰的压住暑气"
    elif t < 10:
        head = "风里带刀，宜捧一杯热的走完这条街"
    elif w["code"] in (1, 2, 3, 45, 48):
        head = "云压得低，正好把这一顿吃得慢一点"
    else:
        head = "天光大好，宜出门把吃饭吃成一件正事"
    tail = {
        "delivery": "不用出门，快乐会自己找上门。",
        "pickup": "两步路的功夫，薯条还是脆的。",
        "dinein": "坐下来吃，才对得起刚出锅的那五分钟。",
        "either": "当天可以 —— 走两步，或者等它来。",
    }[logistics["mode"]]
    return f"{head}。{tail}"


# ── 主装配 ────────────────────────────────────────────────────

def build(city: str | None, days_back: int = 40, days_fwd: int = 40,
          preferred_store: str | None = None,
          preferred_delivery: str | None = None) -> dict:
    warnings: list[str] = []
    loc = resolve_location(city)
    today = date.today()

    try:
        weather = df.fetch_weather(loc["lat"], loc["lon"], today)
    except Exception as e:
        weather = None
        warnings.append(f"天气暂不可用（{e}）")

    # 命盘：天气缺失会让打分退化，这里用一个中性天气兜底，但页面上会标注「天气暂不可用」
    w_for_score = weather or {"temp": 20, "feels_like": 20, "humidity": 55, "precip_mm": 0,
                              "wind_kmh": 8, "code": 0, "desc": "数据暂不可用", "t_max": 22,
                              "t_min": 18, "pop_max": 0, "lunch": {"temp": None, "pop": None}}
    fortune = df.build(loc["place"], loc["lat"], loc["lon"], today) if weather else None
    if fortune is None:
        alm = df.almanac(today)
        score, why, slots, form = df.score_categories(alm, w_for_score)
        fortune = {"place": loc["place"], "almanac": alm, "weather": w_for_score, "form": form,
                   "drink_bias": "any", "drink_note": "天气不可用，冷热随你",
                   "logistics": "either", "logistics_why": "", "confidence": "low",
                   "confidence_note": "天气缺数据，指向偏弱", "slots": slots, "avoid": []}
    fortune["place"] = loc["place"]

    # ── 门店：默认最近的这家，但把候选一并交出去，让玩家自己挑
    stores = pickup_stores(loc)
    pickup_store = stores[0] if stores else None
    if preferred_store:
        hit = next((s for s in stores if s.get("storeCode") == preferred_store), None)
        if hit:
            pickup_store = hit
    d_stores = delivery_stores(loc)
    d_store = d_stores[0] if d_stores else None
    if preferred_delivery:
        hit = next((s for s in d_stores if s.get("storeCode") == preferred_delivery), None)
        if hit:
            d_store = hit
    if not pickup_store:
        warnings.append("附近没查到营业中的门店")

    # ── 菜单
    menu = None
    ctx_pick = ctx_ship = None
    if pickup_store:
        menu = menu_of(pickup_store["storeCode"], 1, 1)
        ctx_pick = {"storeCode": pickup_store["storeCode"], "orderType": 1, "beType": 1}
        if not menu:
            warnings.append("菜单暂不可用（本店 query-meals 无返回）")
    if d_store:
        ctx_ship = {"storeCode": d_store["storeCode"], "orderType": 2, "beType": 2,
                    "beCode": d_store.get("beCode", "")}

    # ── 方案 + 券
    plans_raw, pool, limited = [], {}, []
    if menu:
        plans_raw, pool = sg.build_plans(fortune, menu)
        plans_raw += extra_variants(fortune, pool)
        limited = sg.limited_items(menu)

    coupon_rep, upcoming = {"usable": [], "upcoming": [], "wallet_total": 0,
                            "store_usable_count": 0, "notes": [], "checked": False}, []
    if pickup_store:
        try:
            coupon_rep, upcoming = sg.apply_coupons(plans_raw, pool, ctx_pick, menu, fortune)
            coupon_rep["checked"] = True
        except Exception as e:
            warnings.append(f"优惠券暂不可用（{e}）")

    plans = finalize_plans(plans_raw, ctx_pick) if ctx_pick else []

    # 券已由 apply_coupons 把 saving 写进 plan["coupon"]；方案总价仍以核价为准
    for p in plans:
        if p.get("coupon"):
            p["total"] = p["coupon"]["after"]

    # ── 自取 vs 外送：同一份篮子，两边各核一次价
    dmenu = None
    if d_store:
        dmenu = menu_of(d_store["storeCode"], 2, 2, d_store.get("beCode", ""))
        if dmenu:
            dmenu["_store"] = d_store.get("storeName", "")
    compare = compare_channels(plans, dmenu, ctx_ship) if plans else None

    # 外送门店与到店门店的 SKU 编码不通用：每套方案再备一份「同名映射」的篮子，
    # 映射不上就明确标记「这单只能自取」，不许拿自取的码去外送店硬下。
    for p in plans:
        p["delivery_items"] = None
        if dmenu:
            b = map_basket(p["items"], dmenu)
            if b:
                p["delivery_items"] = [
                    {"code": bb["productCode"], "name": it["name"],
                     "price": it["price"], "cat": it.get("cat", "")}
                    for bb, it in zip(b, p["items"])
                ]
    base_plan = plans[0] if plans else None
    # ── 取餐方式
    rain = (weather or {}).get("precip_mm", 0) > 0 or ((weather or {}).get("pop_max") or 0) >= 60
    no_go = any(k in fortune["almanac"]["ji"] for k in ("出行", "远行", "迁移", "赴任"))
    if not ctx_ship:
        mode, why = "pickup", "该地址暂无外送门店，到店自取更稳"
    elif rain or no_go:
        mode = "delivery"
        why = "不宜出门，交给麦乐送" if not rain else "有雨，交给麦乐送更省事"
    elif compare and compare["diff"] > 8:
        mode, why = "pickup", f"外送要多花 ¥{compare['diff']:g}，走两步更划算"
    elif compare and compare["diff"] > 0:
        mode, why = "either", f"外送只多 ¥{compare['diff']:g}，当天可以，看你方便"
    else:
        mode, why = "either", "当天可以，自取外送两种都顺"
    logistics = {"mode": mode, "label": MODE_CN[mode][0], "sub": MODE_CN[mode][1], "why": why,
                 "compare": compare}

    # ── 宜忌 / 签语
    yiji = make_yiji(fortune, base_plan, coupon_rep, limited, logistics)
    sign = make_sign(fortune, base_plan, logistics)

    # ── 可领取的麦麦省券（只读，不领取）
    claimable = []
    try:
        r = fm.call("available-coupons", {})
        claimable = [c.get("couponName") for c in (r.get("data") or [])
                     if (c.get("couponStatus") or "CAN_GET") == "CAN_GET"]
    except Exception:
        pass

    # ── 月历范围（黄历离线可算，不含天气/价格）
    cal = {}
    for i in range(-days_back, days_fwd + 1):
        d = today + timedelta(days=i)
        a = df.almanac(d)
        cal[d.isoformat()] = {
            "lunar": a["lunar"].replace("二〇二六年", "").replace("二〇二五年", "").replace("二〇二七年", "") or a["lunar"],
            "lunar_full": a["lunar"],
            "gz": f"{a['gan']}{a['zhi']}",
            "nayin": a["nayin"],
            "zhixing": a["zhixing"],
            "yi": a["yi"][:6], "ji": a["ji"][:4],
            "color": a["lucky_color"],
            "xi": a["xi_position"],
            "day_gz": a["day_gz"],
        }

    data = {
        "meta": {
            "generated_at": datetime.now().strftime("%Y-%m-%d %H:%M"),
            "today": today.isoformat(),
            "weekday": "日一二三四五六"[today.isoweekday() % 7],
            "city": loc["city"], "district": loc.get("district", ""),
            "place": loc["place"], "loc_source": loc["source"],
            "address": loc.get("address", ""),
            "address_id": loc.get("address_id", ""),
            "range": {"from": (today - timedelta(days=days_back)).isoformat(),
                      "to": (today + timedelta(days=days_fwd)).isoformat()},
        },
        "weather": weather,
        "almanac": fortune["almanac"],
        "fortune": {
            "confidence": fortune["confidence"], "confidence_note": fortune["confidence_note"],
            "drink_bias": fortune["drink_bias"], "drink_note": fortune["drink_note"],
            "form": fortune["form"],
            "luck": yiji.get("luck", "吉"), "luck_note": yiji.get("luck_note", ""),
            "slots": {k: v[:4] for k, v in fortune["slots"].items()},
        },
        "store": {
            "pickup": {"code": pickup_store["storeCode"], "name": pickup_store["storeName"],
                       "address": pickup_store.get("address", ""),
                       "distance": pickup_store.get("distance"),
                       "open": f"{pickup_store.get('businessStartTime','')}-{pickup_store.get('businessEndTime','')}"
                       } if pickup_store else None,
            "delivery": {"code": d_store["storeCode"], "name": d_store["storeName"],
                         "beCode": d_store.get("beCode", "")} if d_store else None,
            "menu_size": len(pool),
        },
        "stores": {
            "pickup": [store_row(s, "pickup") for s in stores[:12]],
            "delivery": [store_row(s, "delivery") for s in d_stores[:8]],
            "chosen": {"pickup": pickup_store.get("storeCode") if pickup_store else "",
                       "delivery": d_store.get("storeCode") if d_store else ""},
        },
        "menu": menu_list(menu),
        "plans": plans,
        "coupons": {
            "wallet_total": coupon_rep.get("wallet_total", 0),
            "usable": [{k: c.get(k) for k in ("title", "reason", "benefit", "toast")}
                       for c in coupon_rep.get("usable", [])],
            "upcoming": [{k: c.get(k) for k in ("title", "reason", "benefit")}
                         for c in coupon_rep.get("upcoming", [])],
            "store_usable_count": coupon_rep.get("store_usable_count", 0),
            "notes": coupon_rep.get("notes", []),
            "checked": coupon_rep.get("checked", False),
            "upcoming_est": upcoming,
            "claimable": claimable,
        },
        "limited": limited[:18],
        "logistics": logistics,
        "yiji": yiji,
        "sign": sign,
        "calendar": cal,
        "warnings": warnings,
    }
    return data


# ── 输出 ──────────────────────────────────────────────────────

def render_html(data: dict, out_path: Path) -> Path:
    tpl = (WEB / "index.html").read_text(encoding="utf-8")
    css = (WEB / "app.css").read_text(encoding="utf-8")
    app = (WEB / "app.js").read_text(encoding="utf-8")
    art = (WEB / "art.js").read_text(encoding="utf-8")
    payload = json.dumps(data, ensure_ascii=False, separators=(",", ":"))
    html = (tpl
            .replace("/*__CSS__*/", css)
            .replace("/*__DATA__*/", "window.MCD_DATA = " + payload + ";")
            .replace("/*__ART__*/", art)
            .replace("/*__APP__*/", app))
    out_path.parent.mkdir(parents=True, exist_ok=True)
    out_path.write_text(html, encoding="utf-8")
    return out_path


def main():
    ap = argparse.ArgumentParser(description="麦麦黄道吉日 · 页面生成")
    ap.add_argument("--city", help="地点，不填则自动定位")
    ap.add_argument("--out", default=str(ROOT / "demo" / "almanac.html"))
    ap.add_argument("--json", action="store_true", help="只输出数据 JSON")
    a = ap.parse_args()

    data = build(a.city)
    if a.json:
        print(json.dumps(data, ensure_ascii=False, indent=2))
        return
    p = render_html(data, Path(a.out))
    print(f"已生成：{p}")
    print(f"地点 {data['meta']['place']}（{data['meta']['loc_source']}）"
          f" · 门店 {data['store']['pickup']['name'] if data['store']['pickup'] else '无'}")
    print(f"方案 {len(data['plans'])} 套 · 限定 {len(data['limited'])} 款 · "
          f"取餐 {data['logistics']['label']}")
    for w in data["warnings"]:
        print("⚠", w)


if __name__ == "__main__":
    main()
