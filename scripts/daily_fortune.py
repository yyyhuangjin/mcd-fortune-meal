#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
麦麦今日运势 · 黄历 × 天气 → 麦当劳品类倾向 引擎

不依赖任何付费 API：
  - 黄历：lunar_python 本地推算（pip install lunar_python），零网络
  - 天气：Open-Meteo 公开接口，零 Key

输出结构化 JSON，供 Agent 或 suggest.py 消费。

用法：
  python3 scripts/daily_fortune.py --city 北京
  python3 scripts/daily_fortune.py --city 南京 --date 2026-10-26
  python3 scripts/daily_fortune.py --lat 39.9042 --lon 116.4074 --json-only
"""

from __future__ import annotations

import argparse
import json
import sys
import urllib.parse
import urllib.request
from datetime import date, datetime

try:
    from lunar_python import Solar
except ImportError:
    sys.exit("缺少依赖：pip install lunar_python")

TIMEOUT = 15

# ─────────────────────────────────────────────────────────────
# 一、品类池：麦当劳真实品类 × 五行 × 意象
# ─────────────────────────────────────────────────────────────

CATEGORIES = {
    "BEEF":    {"name": "牛肉",     "wx": "土", "slot": "main",    "img": ["纳财", "开市", "厚重", "牛气"]},
    "FISH":    {"name": "鱼",       "wx": "水", "slot": "main",    "img": ["求嗣", "取渔", "有余", "顺遂"]},
    "CHICKEN": {"name": "鸡肉",     "wx": "金", "slot": "main",    "img": ["出行", "吉利", "白肉", "轻盈"]},
    "PORK":    {"name": "猪柳",     "wx": "水", "slot": "main",    "img": ["开端", "晨起"]},
    "FRIED":   {"name": "炸物",     "wx": "火", "slot": "side",    "img": ["庆典", "热闹", "红火"]},
    "POTATO":  {"name": "薯制品",   "wx": "土", "slot": "side",    "img": ["动土", "厚实"]},
    "VEG":     {"name": "蔬果",     "wx": "木", "slot": "side",    "img": ["栽种", "清净", "解除"]},
    "DESSERT": {"name": "甜品冰品", "wx": "水", "slot": "dessert", "img": ["祈福", "圆满", "甜蜜"]},
    "COFFEE":  {"name": "咖啡",     "wx": "水", "slot": "drink",   "img": ["清醒", "入学", "开光"]},
    "TEA":     {"name": "茶饮",     "wx": "木", "slot": "drink",   "img": ["清心", "沐浴", "扫舍"]},
    "SODA":    {"name": "碳酸饮",   "wx": "水", "slot": "drink",   "img": ["畅快", "开市"]},
    "SHARE":   {"name": "分享餐",   "wx": "—", "slot": "form",    "img": ["会亲友", "嫁娶", "团聚"]},
}

SLOT_CN = {"main": "主餐", "side": "小食", "drink": "饮品", "dessert": "甜品", "form": "份额"}

# 宜 → 品类偏好（weight 影响强度）
YI_MAP = {
    "求嗣":   [("FISH", 3), ("DESSERT", 1)],
    "祈福":   [("FISH", 1), ("DESSERT", 2), ("VEG", 1)],
    "祭祀":   [("VEG", 2), ("FISH", 1)],
    "斋醮":   [("VEG", 2)],
    "开光":   [("COFFEE", 1), ("CHICKEN", 1)],
    "出行":   [("CHICKEN", 2), ("COFFEE", 1)],
    "赴任":   [("CHICKEN", 2), ("COFFEE", 1)],
    "迁移":   [("CHICKEN", 1), ("POTATO", 1)],
    "嫁娶":   [("SHARE", 3), ("DESSERT", 1)],
    "会亲友": [("SHARE", 3), ("FRIED", 1)],
    "订盟":   [("SHARE", 2), ("DESSERT", 1)],
    "纳采":   [("SHARE", 2), ("DESSERT", 1)],
    "纳财":   [("BEEF", 3), ("SODA", 1)],
    "开市":   [("BEEF", 2), ("FRIED", 2), ("SODA", 1)],
    "交易":   [("BEEF", 2), ("SODA", 1)],
    "立券":   [("BEEF", 2)],
    "开仓":   [("BEEF", 2), ("POTATO", 1)],
    "出货财": [("BEEF", 2), ("POTATO", 1)],
    "置产":   [("BEEF", 2)],
    "求医":   [("VEG", 2), ("TEA", 2), ("CHICKEN", 1)],
    "治病":   [("VEG", 2), ("TEA", 1)],
    "解除":   [("VEG", 2), ("TEA", 2)],
    "沐浴":   [("TEA", 2), ("VEG", 1)],
    "扫舍":   [("VEG", 2), ("TEA", 1)],
    "栽种":   [("VEG", 3)],
    "牧养":   [("BEEF", 1), ("CHICKEN", 1)],
    "结网":   [("FISH", 2)],
    "取渔":   [("FISH", 3)],
    "动土":   [("POTATO", 2), ("BEEF", 1)],
    "破土":   [("POTATO", 1)],
    "修造":   [("POTATO", 1), ("FRIED", 1)],
    "起基":   [("POTATO", 1)],
    "竖柱":   [("POTATO", 1)],
    "上梁":   [("POTATO", 1), ("BEEF", 1)],
    "安葬":   [("VEG", 1)],
    "裁衣":   [("CHICKEN", 1)],
    "冠笄":   [("DESSERT", 1)],
    "入学":   [("COFFEE", 2), ("CHICKEN", 1)],
}

# 忌 → 品类规避
JI_MAP = {
    "取渔":   ["FISH"],
    "结网":   ["FISH"],
    "牧养":   ["BEEF"],
    "栽种":   ["VEG"],
    "开市":   ["BEEF", "FRIED"],
    "交易":   ["BEEF"],
    "纳财":   ["BEEF"],
    "动土":   ["POTATO"],
    "破土":   ["POTATO"],
    "修造":   ["POTATO"],
    "嫁娶":   ["SHARE"],
    "会亲友": ["SHARE"],
    "求医":   ["VEG"],
    "入学":   ["COFFEE"],
}

# 天干 / 地支 五行
GAN_WX = {"甲": "木", "乙": "木", "丙": "火", "丁": "火", "戊": "土",
          "己": "土", "庚": "金", "辛": "金", "壬": "水", "癸": "水"}
ZHI_WX = {"子": "水", "丑": "土", "寅": "木", "卯": "木", "辰": "土", "巳": "火",
          "午": "火", "未": "土", "申": "金", "酉": "金", "戌": "土", "亥": "水"}

# 建除十二神 → 餐量形式
FORM_BY_ZHIXING = {
    "建": ("丰盛", 2), "满": ("丰盛", 2), "成": ("丰盛", 2), "开": ("丰盛", 2),
    "定": ("均衡", 1), "平": ("均衡", 1), "执": ("均衡", 1),
    "除": ("简约", -1), "破": ("简约", -2), "危": ("简约", -1),
    "收": ("简约", -1), "闭": ("简约", -2),
}

WMO = {0: "晴", 1: "晴间多云", 2: "多云", 3: "阴", 45: "雾", 48: "雾凇",
       51: "小毛毛雨", 53: "毛毛雨", 55: "浓毛毛雨", 61: "小雨", 63: "中雨",
       65: "大雨", 66: "冻雨", 67: "强冻雨", 71: "小雪", 73: "中雪", 75: "大雪",
       77: "雪粒", 80: "阵雨", 81: "强阵雨", 82: "暴雨", 85: "阵雪", 86: "强阵雪",
       95: "雷雨", 96: "雷雨伴冰雹", 99: "强雷雨伴冰雹"}


def geocode(city: str):
    """城市名 → 经纬度（Open-Meteo Geocoding，无需 Key）"""
    q = urllib.parse.urlencode({"name": city, "count": 1, "language": "zh", "format": "json"})
    with urllib.request.urlopen(f"https://geocoding-api.open-meteo.com/v1/search?{q}", timeout=TIMEOUT) as r:
        d = json.loads(r.read().decode())
    if not d.get("results"):
        raise SystemExit(f"找不到城市：{city}")
    g = d["results"][0]
    admin, nm = g.get("admin1", ""), g.get("name", "")
    place = admin if nm and nm in admin else f"{admin}{nm}"
    return g["latitude"], g["longitude"], place


def fetch_weather(lat: float, lon: float, day: str | None):
    """Open-Meteo 当日天气 + 逐时（用于午晚餐时段判断）"""
    d0 = day.isoformat() if day else date.today().isoformat()
    params = urllib.parse.urlencode({
        "latitude": lat, "longitude": lon,
        "current": "temperature_2m,apparent_temperature,relative_humidity_2m,precipitation,weather_code,wind_speed_10m",
        "daily": "temperature_2m_max,temperature_2m_min,precipitation_probability_max,weather_code",
        "hourly": "apparent_temperature,precipitation_probability",
        "timezone": "Asia/Shanghai",
        "start_date": d0, "end_date": d0,
    })
    with urllib.request.urlopen(f"https://api.open-meteo.com/v1/forecast?{params}", timeout=TIMEOUT) as r:
        d = json.loads(r.read().decode())
    cur, daily, hourly = d["current"], d["daily"], d.get("hourly", {})

    lunch = {"temp": None, "pop": None}
    try:
        times = hourly["time"]
        for i, t in enumerate(times):
            if t.endswith("12:00"):
                lunch = {"temp": hourly["apparent_temperature"][i],
                         "pop": hourly["precipitation_probability"][i]}
                break
    except Exception:
        pass

    code = cur.get("weather_code", daily["weather_code"][0])
    return {
        "temp": cur["temperature_2m"],
        "feels_like": cur["apparent_temperature"],
        "humidity": cur["relative_humidity_2m"],
        "precip_mm": cur["precipitation"],
        "wind_kmh": cur["wind_speed_10m"],
        "code": code,
        "desc": WMO.get(code, f"code {code}"),
        "t_max": daily["temperature_2m_max"][0],
        "t_min": daily["temperature_2m_min"][0],
        "pop_max": daily["precipitation_probability_max"][0],
        "lunch": lunch,
    }


LUCKY_COLOR = {"木": "青绿", "火": "赤红", "土": "明黄", "金": "银白", "水": "藏蓝"}
LUCKY_NUM = {"木": [3, 8], "火": [2, 7], "土": [5, 10], "金": [4, 9], "水": [1, 6]}
# 日干五行 → 饮食五味上的取舍
WX_TASTE = {"木": "酸", "火": "苦", "土": "甘", "金": "辛", "水": "咸"}


def almanac(day: date):
    s = Solar.fromYmd(day.year, day.month, day.day)
    l = s.getLunar()
    gz = l.getDayInGanZhi()
    wx = GAN_WX.get(gz[0], "")
    return {
        "solar": day.isoformat(),
        "lunar": l.toString(),
        "year_gz": l.getYearInGanZhi(), "month_gz": l.getMonthInGanZhi(), "day_gz": gz,
        "gan": gz[0], "zhi": gz[1],
        "nayin": l.getDayNaYin(),
        "yi": l.getDayYi(), "ji": l.getDayJi(),
        "tianshen": l.getDayTianShen(), "tianshen_type": l.getDayTianShenType(),
        "zhixing": l.getZhiXing(),
        "xiu": f"{l.getXiu()}{l.getZheng()}{l.getAnimal()}",
        "chong": l.getDayChongDesc(),
        # 趣味维度
        "xi_position": l.getDayPositionXiDesc(),
        "cai_position": l.getDayPositionCaiDesc(),
        "fu_position": l.getDayPositionFuDesc(),
        "lucky_color": LUCKY_COLOR.get(wx, "—"),
        "lucky_numbers": LUCKY_NUM.get(wx, []),
        "taste": WX_TASTE.get(wx, "—"),
    }


def score_categories(alm: dict, weather: dict):
    score = {k: 0.0 for k in CATEGORIES}
    why = {k: [] for k in CATEGORIES}

    # ── 层1：宜忌意象
    for yi in alm["yi"]:
        for cat, w in YI_MAP.get(yi, []):
            score[cat] += w
            why[cat].append(f"宜「{yi}」+{w}")
    for ji in alm["ji"]:
        for cat in JI_MAP.get(ji, []):
            score[cat] -= 3
            why[cat].append(f"忌「{ji}」−3")

    # ── 层2：五行（日干本气 + 日支 + 纳音）
    wx_votes = [GAN_WX.get(alm["gan"], ""), ZHI_WX.get(alm["zhi"], "")]
    ny = alm["nayin"]
    for w in ("金", "木", "水", "火", "土"):
        if w in ny:
            wx_votes.append(w)
    for w in wx_votes:
        if not w:
            continue
        for cat, meta in CATEGORIES.items():
            if meta["wx"] == w:
                score[cat] += 1.2
                why[cat].append(f"五行{w}+1.2")

    # 相生：日干五行生某行，该行 +0.6
    sheng = {"木": "火", "火": "土", "土": "金", "金": "水", "水": "木"}
    main_wx = GAN_WX.get(alm["gan"], "")
    if main_wx:
        target = sheng[main_wx]
        for cat, meta in CATEGORIES.items():
            if meta["wx"] == target:
                score[cat] += 0.6
                why[cat].append(f"{main_wx}生{target}+0.6")

    # ── 层3：天气
    t = weather["feels_like"]
    pop = weather["pop_max"] or 0
    humid = weather["humidity"] or 0
    wind = weather["wind_kmh"] or 0
    wet = weather["precip_mm"] > 0 or pop >= 60

    if t < 8:
        for c in ("BEEF", "FRIED", "POTATO"):
            score[c] += 2.0; why[c].append("严寒高热量+2")
        score["DESSERT"] -= 1.5; why["DESSERT"].append("严寒不宜冰品−1.5")
        score["COFFEE"] += 1.0; why["COFFEE"].append("严寒热饮+1")
    elif t < 15:
        for c in ("BEEF", "FRIED"):
            score[c] += 1.2; why[c].append("偏冷热食+1.2")
        score["COFFEE"] += 0.8; why["COFFEE"].append("偏冷热饮+0.8")
    elif t <= 22:
        pass
    elif t <= 28:
        score["VEG"] += 0.8; why["VEG"].append("温暖清爽+0.8")
        score["SODA"] += 0.8; why["SODA"].append("温暖冷饮+0.8")
        score["FRIED"] -= 0.5; why["FRIED"].append("温暖油腻−0.5")
    else:
        score["DESSERT"] += 2.0; why["DESSERT"].append("高温冰品+2")
        score["SODA"] += 1.5; why["SODA"].append("高温冷饮+1.5")
        score["FRIED"] -= 1.2; why["FRIED"].append("高温油炸−1.2")

    if wet:
        for c in ("BEEF", "POTATO", "COFFEE", "TEA"):
            score[c] += 1.0; why[c].append("有雨热食热饮+1")
        score["DESSERT"] -= 1.0; why["DESSERT"].append("雨天外送易化−1")
    if humid > 80 and t > 22:
        score["VEG"] += 0.8; why["VEG"].append("湿热清爽+0.8")
        score["FRIED"] -= 0.8; why["FRIED"].append("湿热油炸−0.8")
    if wind > 25:
        score["COFFEE"] += 0.8; why["COFFEE"].append("大风热饮+0.8")

    # ── 层3：建除十二神 → 餐量形式
    form, form_w = FORM_BY_ZHIXING.get(alm["zhixing"], ("均衡", 0))
    if form == "丰盛":
        for c in ("SHARE", "BEEF", "FRIED"):
            score[c] += 1.0; why[c].append(f"值「{alm['zhixing']}」宜丰盛+1")
    elif form == "简约":
        for c in ("SHARE", "FRIED"):
            score[c] += form_w; why[c].append(f"值「{alm['zhixing']}」宜简约{form_w}")
        score["CHICKEN"] += 0.5; why["CHICKEN"].append("简约单品+0.5")

    # 分槽位排序：主餐 / 小食 / 饮品 / 甜品
    slots = {"main": [], "side": [], "drink": [], "dessert": []}
    for cat, v in score.items():
        s = CATEGORIES[cat]["slot"]
        if s in slots:
            slots[s].append({
                "cat": cat, "name": CATEGORIES[cat]["name"], "score": round(v, 1),
                "reasons": why[cat][:5],
            })
    for s in slots:
        slots[s].sort(key=lambda x: -x["score"])

    return score, why, slots, form


def drink_bias(weather: dict):
    t = weather["feels_like"]
    if t < 10:
        return "hot", "体感偏冷，优先热饮"
    if t < 16:
        return "hot", "微凉，热饮更稳妥"
    if t <= 23:
        return "any", "温度舒适，冷热皆可"
    if t <= 28:
        return "cold", "偏暖，冷饮更舒服"
    return "ice", "高温，冰饮 + 冰品解暑"


def build(city, lat, lon, day):
    if lat is None or lon is None:
        lat, lon, place = geocode(city)
    else:
        place = city or f"{lat},{lon}"
    w = fetch_weather(lat, lon, day)
    alm = almanac(day)
    score, why, slots, form = score_categories(alm, w)
    bias, bias_note = drink_bias(w)

    avoid = sorted(score.items(), key=lambda kv: kv[1])[:4]

    # 置信度：主餐第一名与第二名差距越小，说明当日黄历指向越弱
    mains = slots["main"]
    gap = (mains[0]["score"] - mains[1]["score"]) if len(mains) > 1 else mains[0]["score"]
    if gap >= 3:
        confidence = "high"
    elif gap >= 1:
        confidence = "medium"
    else:
        confidence = "low"
    confidence_note = {
        "high": "今日黄历指向明确，照办即可",
        "medium": "有倾向但不绝对，可按口味微调",
        "low": "今日宜忌信息少，随缘为吉——按天气和心情来",
    }[confidence]

    # 堂食 / 外送取向：雨天或「忌出行」→ 默认麦乐送
    rain = w["precip_mm"] > 0 or (w["pop_max"] or 0) >= 60
    no_go = any(k in alm["ji"] for k in ("出行", "远行", "迁移", "赴任"))
    if rain or no_go:
        logistics = "delivery"
        logistics_why = "有雨，改外送" if rain else f"忌『{[k for k in alm['ji'] if k in ('出行','远行','迁移','赴任')][0]}』，不宜出门"
    else:
        logistics = "either"
        logistics_why = "天气与黄历都支持出门，堂食外带皆可"

    return {
        "place": place,
        "generated_at": datetime.now().strftime("%Y-%m-%d %H:%M:%S"),
        "almanac": alm,
        "weather": w,
        "form": form,
        "drink_bias": bias,
        "drink_note": bias_note,
        "logistics": logistics,
        "logistics_why": logistics_why,
        "confidence": confidence,
        "confidence_note": confidence_note,
        "slots": slots,
        "avoid": [{"cat": k, "name": CATEGORIES[k]["name"], "score": round(v, 1)} for k, v in avoid],
    }


def main():
    ap = argparse.ArgumentParser(description="麦麦今日运势引擎")
    ap.add_argument("--city", default="北京")
    ap.add_argument("--lat", type=float)
    ap.add_argument("--lon", type=float)
    ap.add_argument("--date", help="YYYY-MM-DD，默认今天")
    ap.add_argument("--json-only", action="store_true", help="只输出 JSON，不打印摘要")
    a = ap.parse_args()

    day = date.fromisoformat(a.date) if a.date else date.today()
    res = build(a.city, a.lat, a.lon, day)

    if a.json_only:
        print(json.dumps(res, ensure_ascii=False, indent=2))
        return

    alm, w = res["almanac"], res["weather"]
    print(f"📍 {res['place']}  {alm['solar']}  农历{alm['lunar']}")
    print(f"🗓  干支 {alm['year_gz']}年 {alm['month_gz']}月 {alm['day_gz']}日 · {alm['nayin']}")
    print(f"   值日「{alm['zhixing']}」· 天神 {alm['tianshen']} · 星宿 {alm['xiu']} · 冲煞{alm['chong']}")
    print(f"✅ 宜：{('、'.join(alm['yi'])) or '无'}")
    print(f"⛔ 忌：{('、'.join(alm['ji'])) or '无'}")
    print(f"🌤  天气 {w['desc']} {w['temp']}°C（体感 {w['feels_like']}°C）"
          f" 湿度{w['humidity']}% 降水{w['precip_mm']}mm 降水概率{w['pop_max']}% 风{w['wind_kmh']}km/h")
    print(f"🍽  餐量形式：{res['form']} · 饮品取向：{res['drink_bias']}（{res['drink_note']}）")
    print(f"🚚 取餐方式：{res['logistics']}（{res['logistics_why']}）")
    print(f"🎨 幸运色 {alm['lucky_color']} · 幸运数 {'/'.join(map(str, alm['lucky_numbers'])) or '—'}"
          f" · 喜神{alm['xi_position']} · 财神{alm['cai_position']} · 今日主味「{alm['taste']}」")
    print(f"🔮 指向强度：{res['confidence']}　{res['confidence_note']}")
    for slot in ("main", "side", "drink", "dessert"):
        print(f"\n📊 {SLOT_CN[slot]}倾向")
        for i, t in enumerate(res["slots"][slot], 1):
            print(f"  {i}. {t['name']:<6} {t['score']:>5}  ← {'；'.join(t['reasons'][:4]) or '—'}")
    print("\n⚠️  今日宜避开：" + "、".join(f"{b['name']}({b['score']})" for b in res["avoid"]))
    print("\n（黄历与五行属传统民俗娱乐，不构成健康或运势建议）")


if __name__ == "__main__":
    main()
