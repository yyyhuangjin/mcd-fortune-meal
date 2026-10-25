#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
菜单匹配器：把「黄历×天气」的品类倾向，落到真实 SKU 上，出三套方案。

输入：
  --fortune   daily_fortune.py 输出的 JSON（不传则实时计算）
  --menu      query-meals 返回体（MCP 原始 text 或已解析 JSON 均可）
用法：
  python3 scripts/suggest.py --city 北京 --menu demo/fixtures/menu_1950564_dinein.json
  python3 scripts/suggest.py --menu menu.json --json
"""

from __future__ import annotations

import argparse
import json
import re
import sys

import daily_fortune as df

# ── 名称 → 品类。只用"有辨识度"的关键词，避免「麦辣鸡腿汉堡」被误判
MAIN_KW = [
    ("BEEF",    ["巨无霸", "吉士", "安格斯", "厚牛", "牛堡", "双牛", "不素之霸", "牛肉", "牛气", "牛"]),
    ("FISH",    ["鳕鱼", "麦香鱼", "鱼排", "鱼"]),
    ("CHICKEN", ["板", "麦辣鸡腿", "麦辣鸡", "麦香鸡", "鸡腿堡", "鸡肉堡", "脆汁鸡", "辣"]),
    ("PORK",    ["猪柳", "培根"]),
]
# 炸物 / 小食强标志：出现这些词就是小食，不是主餐
FRIED_MARK = ["翅", "鸡排", "麦乐鸡", "四宫格", "拼盘", "双拼", "十翅", "芝士条", "山葵"]
POTATO_MARK = ["薯条", "薯饼"]
VEG_MARK = ["玉米杯", "苹果片", "沙拉"]
DESSERT_MARK = ["麦旋风", "圆筒", "新地", "冰淇淋", "阿芙佳朵", "派"]
COFFEE_MARK = ["咖啡", "美式", "奶铁", "黑巧", "浓缩", "牛奶", "燕麦奶"]
TEA_MARK = ["红茶", "锡兰"]
SODA_MARK = ["可乐", "雪碧", "怡泉", "麦炫酷", "柠柠", "橙橙", "柠檬", "苹果汁", "果汁", "纯悦"]
# 非餐品：周边、玩具、礼品，一律不进推荐
NON_FOOD = ["丝巾", "毛绒", "按摩捶", "周边", "公仔", "玩具", "礼品", "痒痒挠"]
# 限定信号：query-meals 的 categories[].meals[].tags 里带这些，就说明是「此刻这家店」的限定/上新
LIMITED_TAG = {"上新": "上新", "限定特惠": "限时特惠", "全球爆款": "全球爆款"}
# 多人餐：单人点餐场景下不推荐（份量与价格都不适配）
GROUP_MARK = ["双人", "多人", "分享", "全家", "家庭"]
# 自选型商品（任选件数/自由搭配）：内容不确定、价格不可控，不自动推荐
BUILD_MARK = ["任选", "随心", "自选", "拼盘"]
COMBO_PAT = ["三件套", "四件套", "套餐", "随心配", "分享餐", "双人餐", "八件套",
             "任选", "拼盘", "四宫格", "大全"]


def _hit(name, kws):
    return any(k in name for k in kws)


def _main_cat(name):
    for cat, kws in MAIN_KW:
        if _hit(name, kws):
            return cat
    return "BEEF"          # 「汉堡开心乐园餐」这类无标识的，按经典牛肉堡处理


def classify(name: str):
    if _hit(name, NON_FOOD):
        return None
    if _hit(name, GROUP_MARK):
        return None        # 双人/分享餐：单人场景不推
    if _hit(name, BUILD_MARK):
        return None        # 自选搭配：内容与价格不可控
    # 1) 含「堡 / 卷」的是主餐，优先级最高（「培根蔬萃双层牛堡」不能被当蔬菜）
    if _hit(name, ["堡", "卷"]):
        return "main", _main_cat(name)
    # 2) 炸物 / 小食强标志（「薄皮V翅双拼十翅」不能当主餐鸡肉）
    if _hit(name, FRIED_MARK):
        return "side", "FRIED"
    # 3) 配餐与饮品
    if _hit(name, POTATO_MARK):
        return "side", "POTATO"
    if _hit(name, VEG_MARK):
        return "side", "VEG"
    if _hit(name, DESSERT_MARK):
        return "dessert", "DESSERT"
    if _hit(name, COFFEE_MARK):
        return "drink", "COFFEE"
    if _hit(name, TEA_MARK):
        return "drink", "TEA"
    if _hit(name, SODA_MARK):
        return "drink", "SODA"
    # 4) 无「堡」但含主餐关键词的套餐（如「"苹"水相"鱼"套餐」）
    for cat, kws in MAIN_KW:
        if _hit(name, kws):
            return "main", cat
    if _hit(name, ["餐", "套"]):
        return "main", "BEEF"
    return None


def load_menu(path):
    """兼容三种输入：纯 data、完整 body、MCP 原始 text（JSON 后接说明文字）"""
    raw = open(path, encoding="utf-8").read()

    def first_obj(text):
        for ln in text.splitlines():
            st = ln.strip()
            if not st.startswith("{"):
                continue
            try:
                return json.JSONDecoder().raw_decode(st)[0]
            except json.JSONDecodeError:
                continue
        return None

    body = None
    try:
        body = json.loads(raw)
    except json.JSONDecodeError:
        body = first_obj(raw)

    if body is None:
        sys.exit("无法解析菜单文件")
    # MCP 原始返回：{result:{content:[{text:...}]}}
    if isinstance(body, dict) and "result" in body and "content" in body.get("result", {}):
        body = first_obj(body["result"]["content"][0]["text"]) or body
    if "data" not in body:
        sys.exit("菜单文件缺少 data 字段")
    return body["data"]


def parse_price(s):
    try:
        return float(s)
    except (TypeError, ValueError):
        return 0.0


def build_pool(menu):
    meals = menu["meals"]
    order = {}
    for c in menu["categories"]:
        for m in c["meals"]:
            code = m["code"]
            if code not in meals:
                continue
            name = meals[code].get("name", "")
            cls = classify(name)
            if not cls:
                continue
            slot, cat = cls
            price = parse_price(meals[code].get("currentPrice"))
            order[code] = {
                "code": code, "name": name, "slot": slot, "cat": cat,
                "price": price,
                "combo": any(p in name for p in COMBO_PAT),
                "cat_name": c["name"].replace("\n", ""),
                # 限定的判断在标签上，不在名字里 —— 名字叫「龙焰」看不出是不是新品
                "tags": m.get("tags") or [],
                "original_price": parse_price(meals[code].get("originalPrice")),
            }
    return order


def limited_items(menu):
    """今日限定 / 上新池。按门店实时菜单现拉现算，不缓存。

    只认标签，不认想象：菜单上没打「上新 / 限定特惠 / 全球爆款」的，
    无论名字多像限定，都不许说它是限定。
    """
    meals = menu["meals"]
    seen, seen_name, out = set(), set(), []
    for c in menu["categories"]:
        for m in c["meals"]:
            code = m["code"]
            tags = m.get("tags") or []
            hit = [LIMITED_TAG[t] for t in tags if t in LIMITED_TAG]
            if not hit or code in seen or code not in meals:
                continue
            name = meals[code].get("name", "")
            if any(x in name for x in NON_FOOD):
                continue          # 丝巾、毛绒周边也会打「上新」，不是吃的
            if name in seen_name:
                continue          # 同一商品挂在多个分类下，按名字去重
            seen.add(code)
            seen_name.add(name)
            out.append({
                "code": code, "name": name,
                "price": parse_price(meals[code].get("currentPrice")),
                "original_price": parse_price(meals[code].get("originalPrice")),
                "tags": sorted(set(hit)),
                "raw_tags": tags,
                "category": c["name"].replace("\n", ""),
                "cls": classify(name),
            })
    # 有价格的排前面，同价位按标签优先级
    order = {"上新": 0, "全球爆款": 1, "限时特惠": 2}
    out.sort(key=lambda x: (x["price"] <= 0, min(order.get(t, 9) for t in x["tags"]), x["price"]))
    return out


def group_limited(limited, per_group=3):
    """按标签分组，每组取最有代表性的几款。

    不按价格全排一遍 —— 那样 ¥5 的灰焰圆筒会把 ¥26.9 的龙焰套餐挤出视野，
    而后者才是真正让人「今天想吃这一口」的东西。
    """
    order = ["上新", "全球爆款", "限时特惠"]
    groups = {t: [] for t in order}
    for it in limited:
        for t in order:
            if t in it["tags"]:
                groups[t].append(it)
                break
    out = []
    for t in order:
        items = groups[t]
        if not items:
            continue
        # 组内：套餐优先（更有代表性），再按价格
        items = sorted(items, key=lambda x: (not any(k in x["name"] for k in ("套", "餐")), -x["price"]))
        out.append({"tag": t, "items": items[:per_group], "total": len(items)})
    return out


def pick(pool, fortune, slot, cats, prefer_combo=None, bias=None, limit=3):
    """在指定槽位、指定品类集合内挑 SKU，按运势分数排序"""
    slot_scores = {x["cat"]: x["score"] for x in fortune["slots"][slot]}
    cands = []
    for it in pool.values():
        if it["slot"] != slot or it["cat"] not in cats:
            continue
        s = slot_scores.get(it["cat"], 0)
        if prefer_combo is True and it["combo"]:
            s += 3
        if prefer_combo is False and it["combo"]:
            s -= 3
        if bias and slot == "drink":
            if bias == "hot" and it["cat"] in ("COFFEE", "TEA"):
                s += 2
            if bias in ("cold", "ice") and it["cat"] == "SODA":
                s += 2
        # 牛奶 / 燕麦奶是配餐饮品，不作主选
        if slot == "drink" and any(k in it["name"] for k in ("牛奶", "燕麦奶")):
            s -= 4
        cands.append((s, -it["price"], it))
    cands.sort(key=lambda x: (-x[0], x[1]))
    return [c[2] for c in cands[:limit]]


def build_plans(fortune, menu):
    pool = build_pool(menu)
    form, bias = fortune["form"], fortune["drink_bias"]

    mains = [x["cat"] for x in fortune["slots"]["main"]]
    sides = [x["cat"] for x in fortune["slots"]["side"]]
    drinks = [x["cat"] for x in fortune["slots"]["drink"]]
    main_top = mains[0]

    plans = []

    # 方案一 · 天命套餐：优先现成套餐，丰盛日挑件数多的
    combos = pick(pool, fortune, "main", mains, prefer_combo=True, limit=8)
    best_combo = next((c for c in combos if c["cat"] == main_top), combos[0] if combos else None)
    if best_combo:
        plans.append({
            "tag": "天命套餐", "icon": "🍔",
            "desc": f"「{df.CATEGORIES[main_top]['name']}」当令，一件省心",
            "items": [best_combo],
            "reason": f"主餐倾向「{df.CATEGORIES[main_top]['name']}」，值日「{fortune['almanac']['zhixing']}」宜{form}",
        })

    # 方案二 · 手搭三件：单品主餐 + 小食 + 饮品
    m2 = pick(pool, fortune, "main", mains, prefer_combo=False, limit=6)
    s2 = pick(pool, fortune, "side", sides, limit=4)
    d2 = pick(pool, fortune, "drink", drinks, bias=bias, limit=4)
    if m2 and s2 and d2:
        items = [m2[0], s2[0], d2[0]]
        plans.append({
            "tag": "手搭三件", "icon": "🥢", "desc": "主餐 + 小食 + 饮品，口味自己拿主意",
            "items": items,
            "reason": f"主餐「{df.CATEGORIES[m2[0]['cat']]['name']}」· 小食「{df.CATEGORIES[s2[0]['cat']]['name']}」· {fortune['drink_note']}",
        })

    # 方案三 · 轻简改运：主餐单品 + 饮品（都取同档最便宜）
    # 注意：「轻简」必须真的更便宜。套餐是捆绑价，单品+饮品经常反而更贵，
    # 那种情况下宁可不给这套方案，也不能端出一个又贵又叫「轻简」的东西。
    if m2 and d2:
        cheap_drink = min(d2[:3], key=lambda x: x["price"])
        cheap_main = min(m2[:4], key=lambda x: x["price"])
        items = [cheap_main, cheap_drink]
        total = sum(i["price"] for i in items)
        combo_total = sum(i["price"] for i in plans[0]["items"]) if plans else None
        if combo_total is None or total < combo_total - 0.01:
            ji = "、".join(fortune["almanac"]["ji"][:3])
            plans.append({
                "tag": "轻简改运", "icon": "🍃", "desc": "最便宜的一主一饮，热量与预算都收着",
                "items": items,
                "reason": (f"今日忌{ji}，诸事宜从简" if ji else "今日无禁忌，宜从容为简"),
            })

    # 甜品彩蛋：冰品分数 > 3 且非严寒/雨天
    ds = {x["cat"]: x["score"] for x in fortune["slots"]["dessert"]}
    w = fortune["weather"]
    if ds.get("DESSERT", 0) >= 3 and w["feels_like"] >= 8 and w["precip_mm"] == 0:
        d3 = pick(pool, fortune, "dessert", ["DESSERT"], limit=2)
        if d3:
            plans.append({
                "tag": "甜品冲喜", "icon": "🍦", "desc": "加一件甜品，讨个「甜」字",
                "items": [d3[0]],
                "reason": f"宜{('、'.join([y for y in fortune['almanac']['yi'] if y in ('祈福','求嗣','嫁娶')]) or '祈福')}，以甜收尾",
            })

    for p in plans:
        p["total"] = round(sum(i["price"] for i in p["items"]), 1)
        p["payload"] = [{"productCode": i["code"], "quantity": 1} for i in p["items"]]
        notes = []
        for i in p["items"]:
            if "冰/热" in i["name"] or "（冰/热）" in i["name"] or "(冰/热)" in i["name"]:
                notes.append(f"「{i['name']}」需指定{'热饮' if bias == 'hot' else '冷热'}，"
                             f"麦当劳默认给冰饮")
        if notes:
            p["notes"] = notes
    return plans, pool


def apply_coupons(plans, pool, ctx, menu, fortune):
    """给方案配券，并用「用券价」重排。

    两条铁律：
      1. 省多少一律由 calculate-price 实测，不拿券面价自己减。
      2. 验不出降价就不写省了钱，只如实说「该券对本单无优惠」。
    """
    import coupons as cp

    rep = cp.analyze(ctx["storeCode"], ctx["orderType"], ctx["beType"], pool=pool)

    for p in plans:
        best = cp.optimize_plan(p, rep["usable"], ctx)
        if best and best.get("ok"):
            src = next((c for c in rep["usable"] if c["id"] == best["coupon_id"]), {})
            p["coupon"] = {
                "title": best["coupon"], "id": best["coupon_id"],
                # 下单时 calculate-price / create-order 需要 couponId + couponCode 成对
                "code": src.get("code", ""),
                "on_item": best["on_item"],
                "before": round(best["before"] / 100, 1),
                "after": round(best["after"] / 100, 1),
                "saving": round(best["saving"] / 100, 1),
            }
            p["final_total"] = round(best["after"] / 100, 1)

    # 券作主：券能把某件商品打到很低时，这本身就是一种「今日宜吃」
    for c in rep["usable"]:
        for m in c.get("matches", [])[:1]:
            save = m["est_saving"]
            if save < 3 or c["benefit"]["kind"] != "fixed_price":
                continue
            item = pool.get(m["code"])
            if not item:
                continue
            plan = {
                "tag": "券作主", "icon": "🎟",
                "desc": f"「{c['title']}」把「{item['name']}」打到 ¥{c['benefit']['price']:g}",
                "items": [item],
                "reason": f"券面权益直降 ¥{save:g}，比按运势挑单品更划算",
                "coupon": {"title": c["title"], "id": c["id"], "on_item": item["name"],
                           "before": item["price"], "after": c["benefit"]["price"],
                           "saving": save, "verified": False},
                "final_total": c["benefit"]["price"],
            }
            plans.append(plan)
            break

    # 明日可用的券：今天用不上，但值得说一句
    upcoming = []
    for c in rep["upcoming"]:
        b = c["benefit"]
        if b["kind"] != "fixed_price" or not c.get("matches"):
            continue
        m = c["matches"][0]
        upcoming.append({
            "title": c["title"], "starts": c["reason"],
            "target": m["name"], "now_price": m["price"],
            "coupon_price": b["price"], "est_saving": m["est_saving"],
        })
    return rep, upcoming


def render(fortune, plans, coupon_rep=None, upcoming=None, limited=None):
    a, w = fortune["almanac"], fortune["weather"]
    print(f"\n{'═'*62}")
    print(f"  🗓  {a['solar']}  农历{a['lunar']}  ·  {fortune['place']}")
    print(f"  {a['day_gz']}日 · {a['nayin']} · 值日「{a['zhixing']}」· 天神{a['tianshen']}")
    print(f"  🌤 {w['desc']} {w['temp']}°C（体感 {w['feels_like']}°C）· 降水概率 {w['pop_max']}%")
    print(f"{'═'*62}")
    print(f"  宜：{('、'.join(a['yi'][:8]))}{'…' if len(a['yi'])>8 else ''}")
    print(f"  忌：{('、'.join(a['ji'])) or '无'}")
    print(f"  主餐倾向 → {df.CATEGORIES[fortune['slots']['main'][0]['cat']]['name']}"
          f"（指向强度 {fortune['confidence']}）")
    print(f"  幸运色 {a['lucky_color']} · 喜神{a['xi_position']} · {fortune['logistics_why']}")
    print(f"{'─'*62}")
    for i, p in enumerate(plans, 1):
        head = f"  {p['icon']} 方案{i} · {p['tag']}"
        if p.get("coupon"):
            c = p["coupon"]
            print(f"\n{head}   ¥{c['before']} → ¥{c['after']}  🎟 省 ¥{c['saving']}")
        else:
            print(f"\n{head}   ¥{p['total']}")
        print(f"     {p['desc']}")
        for it in p["items"]:
            print(f"       · {it['name']:<26} ¥{it['price']:>6.1f}")
        for n in p.get("notes", []):
            print(f"       ⚠ {n}")
        if p.get("coupon"):
            c = p["coupon"]
            print(f"       🎟 「{c['title']}」作用于「{c['on_item']}」，核价实测省 ¥{c['saving']}")
        print(f"     ↳ {p['reason']}")

    if upcoming:
        print(f"\n{'─'*62}")
        print("  ⏳ 明天起能用的券（今天用不了，先记着）")
        for u in upcoming:
            print(f"     · {u['title']}（{u['starts']}）")
            print(f"       「{u['target']}」现价 ¥{u['now_price']:g}"
                  f" → 用券 ¥{u['coupon_price']:g}，可省 ¥{u['est_saving']:g}")

    if limited:
        print(f"\n{'─'*62}")
        print(f"  ✨ 今日限定 / 上新（{len(limited)} 款，读自本店实时菜单标签）")
        for g in group_limited(limited):
            print(f"     · {g['tag']}（{g['total']} 款）")
            for it in g["items"]:
                print(f"         {it['name']:<26} ¥{it['price']:g}")

    print(f"\n{'─'*62}")
    if coupon_rep:
        print(f"  券：卡包 {coupon_rep['wallet_total']} 张 · 今日可用 "
              f"{len(coupon_rep['usable'])} 张 · 门店级可用 {coupon_rep['store_usable_count']} 张")
    print("  价格为门店菜单快照，用券价已由 calculate-price 核价；下单前请再复核一次")
    print("  黄历 / 五行 / 星宿属传统民俗娱乐，不构成健康或运势建议\n")


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--city", default="北京")
    ap.add_argument("--lat", type=float)
    ap.add_argument("--lon", type=float)
    ap.add_argument("--date")
    ap.add_argument("--menu", required=True, help="query-meals 返回体文件")
    ap.add_argument("--fortune", help="daily_fortune.py 的 JSON 输出，不传则实时算")
    ap.add_argument("--store-code", help="门店编码，给了才做券比价")
    ap.add_argument("--order-type", type=int, default=1)
    ap.add_argument("--be-type", type=int, default=1)
    ap.add_argument("--no-coupon", action="store_true", help="跳过券比价")
    ap.add_argument("--json", action="store_true", help="输出 JSON（含 calculate-price payload）")
    a = ap.parse_args()

    if a.fortune:
        fortune = json.load(open(a.fortune, encoding="utf-8"))
    else:
        from datetime import date
        day = date.fromisoformat(a.date) if a.date else date.today()
        fortune = df.build(a.city, a.lat, a.lon, day)

    menu = load_menu(a.menu)
    plans, pool = build_plans(fortune, menu)
    limited = limited_items(menu)

    coupon_rep, upcoming = None, []
    if a.store_code and not a.no_coupon:
        ctx = {"storeCode": a.store_code, "orderType": a.order_type, "beType": a.be_type}
        coupon_rep, upcoming = apply_coupons(plans, pool, ctx, menu, fortune)

    if a.json:
        print(json.dumps({"fortune": fortune, "plans": plans, "pool_size": len(pool),
                          "limited": limited, "coupons": coupon_rep,
                          "coupon_upcoming": upcoming},
                         ensure_ascii=False, indent=2))
    else:
        render(fortune, plans, coupon_rep, upcoming, limited)


if __name__ == "__main__":
    main()
