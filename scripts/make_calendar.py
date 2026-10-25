#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
生成「今日撕历」——按当日真实数据现场渲染，不是写死的模板

撕前：只见农历、干支、宜忌、一个主餐提示字。
撕后：露出今天的运势餐单、券比价、限定彩蛋。

用法：
  python3 scripts/make_calendar.py --city 北京 --store-code 1950564 \\
      --menu /tmp/menu_live.json --out demo/today_calendar.html
"""

from __future__ import annotations

import argparse
import html
import json
import sys
from datetime import date

import daily_fortune as df
import suggest as sg

# 主餐倾向 → 一个可以刻在日历上的字
BIG_CHAR = {
    "BEEF": "牛", "FISH": "鱼", "CHICKEN": "鸡", "PORK": "猪",
    "FRIED": "炸", "VEG": "蔬", "POTATO": "薯", "DESSERT": "甜",
    "COFFEE": "咖", "TEA": "茶", "SODA": "饮", "SHARE": "聚",
}
CONF_CN = {"high": "指向明确", "medium": "略有倾向", "low": "今日宜忌平淡，随缘为吉"}


def e(s) -> str:
    return html.escape(str(s), quote=True)


def build_sheet(f: dict) -> str:
    a, w = f["almanac"], f["weather"]
    main_cat = f["slots"]["main"][0]["cat"]
    big = BIG_CHAR.get(main_cat, "食")
    conf = CONF_CN.get(f.get("confidence"), "")

    yi = "、".join(a["yi"][:6]) or "无"
    ji = "、".join(a["ji"][:6]) or "无"

    y, m, d = (int(x) for x in a["solar"].split("-"))
    wd = "周一周二周三周四周五周六周日"[date(y, m, d).weekday() * 2:][:2]
    cn_month = "〇一二三四五六七八九十"[m] if m <= 10 else str(m)
    lunar_disp = a["lunar"].replace("农历", "")

    return f"""
    <div class="sheet" id="sheet">
      <div class="sheet-inner">
        <div class="sheet-top">
          <div class="solar-line">{y} 年 {cn_month} 月</div>
          <div class="dow">{wd} · 值日「{e(a['zhixing'])}」</div>
          <div class="extra">
            <span>星宿 {e(a['xiu'])}</span>
            <span>喜神 {e(a['xi_position'])}</span>
            <span>财神 {e(a['cai_position'])}</span>
            <span>幸运色 {e(a['lucky_color'])}</span>
          </div>
        </div>

        <div class="sheet-hero">
          <div class="daynum">{d}</div>
          <div class="hero-right">
            <div class="lunar-big">{e(lunar_disp)}</div>
            <div class="gz">{e(a['day_gz'])}日 · {e(a['nayin'])}</div>
          </div>
        </div>

        <div class="sheet-mid">
          <div class="yi-ji">
            <div class="col">
              <div class="badge yi">宜</div>
              <div class="words">{e(yi)}</div>
            </div>
            <div class="col">
              <div class="badge ji">忌</div>
              <div class="words">{e(ji)}</div>
            </div>
          </div>

          <div class="seal">
            <div class="seal-char">{e(big)}</div>
            <div class="seal-cap">今日主食</div>
          </div>
        </div>

        <div class="sheet-meta">
          <span>{e(w['desc'])} {w['temp']}°C · 体感 {w['feels_like']}°C</span>
          <span>{e(f['place'])}</span>
          <span>{e(conf)}</span>
        </div>

        <div class="sheet-foot">
          <div class="hint" id="hint">↑ 按住这张纸，向上拖动撕开</div>
          <button class="tear-btn" id="tearBtn" type="button">撕开看看</button>
        </div>
      </div>
      <div class="serration" aria-hidden="true"></div>
    </div>
    """


def build_reveal(f: dict, plans: list, coupon_rep, upcoming, limited) -> str:
    a, w = f["almanac"], f["weather"]
    main_cat = f["slots"]["main"][0]["cat"]
    main_name = df.CATEGORIES[main_cat]["name"]
    conf = CONF_CN.get(f.get("confidence"), "")

    # 方案卡片
    cards = []
    for i, p in enumerate(plans, 1):
        c = p.get("coupon")
        price_html = (f'<span class="was">¥{c["before"]:g}</span>'
                      f'<span class="now">¥{c["after"]:g}</span>'
                      f'<span class="save">省 ¥{c["saving"]:g}</span>') if c else \
                     f'<span class="now">¥{p["total"]:g}</span>'
        items = "".join(
            f'<li><span class="iname">{e(it["name"])}</span>'
            f'<span class="iprice">¥{it["price"]:g}</span></li>' for it in p["items"])
        notes = "".join(f'<div class="note">⚠ {e(n)}</div>' for n in p.get("notes", []))
        coupon_line = (f'<div class="coupon-hit">🎟 「{e(c["title"])}」作用于「{e(c["on_item"])}」，'
                       f'核价实测省 ¥{c["saving"]:g}</div>') if c else ""
        cards.append(f"""
        <article class="plan">
          <div class="plan-head">
            <span class="picon">{e(p['icon'])}</span>
            <span class="ptag">方案{i} · {e(p['tag'])}</span>
            <span class="pprice">{price_html}</span>
          </div>
          <p class="pdesc">{e(p['desc'])}</p>
          <ul class="items">{items}</ul>
          {notes}{coupon_line}
          <p class="preason">{e(p['reason'])}</p>
        </article>""")

    # 券区
    coupon_html = ""
    if coupon_rep:
        usable = coupon_rep["usable"]
        rows = []
        if usable:
            for c in usable:
                rows.append(f'<li><b>{e(c["title"])}</b><span class="ok">今日可用</span></li>')
        for c in coupon_rep["upcoming"]:
            b = c["benefit"]
            price = f'¥{b["price"]:g}' if b["price"] is not None else "—"
            rows.append(f'<li><b>{e(c["title"])}</b> {price}'
                        f'<span class="wait">⏳ {e(c["reason"])}</span></li>')
        for c in coupon_rep["blocked"][:3]:
            rows.append(f'<li><b>{e(c["title"])}</b><span class="no">⛔ {e(c["reason"])}</span></li>')

        upcoming_html = ""
        if upcoming:
            u = upcoming[0]
            upcoming_html = (f'<div class="upcoming-tip">明天起：'
                             f'「{e(u["target"])}」现价 ¥{u["now_price"]:g} → 用券 ¥{u["coupon_price"]:g}，'
                             f'可省 ¥{u["est_saving"]:g}</div>')

        coupon_html = f"""
        <section class="block">
          <h3>🎟 今天的券 <span class="dim">卡包 {coupon_rep['wallet_total']} 张 ·
            今日可用 {len(usable)} 张</span></h3>
          <ul class="coupon-list">{''.join(rows) or '<li class="dim">卡包里没有券</li>'}</ul>
          {upcoming_html}
        </section>"""

    # 限定区
    limited_html = ""
    if limited:
        groups = sg.group_limited(limited)
        ghtml = []
        for g in groups:
            lis = "".join(f'<li><span class="iname">{e(it["name"])}</span>'
                          f'<span class="iprice">¥{it["price"]:g}</span></li>'
                          for it in g["items"])
            ghtml.append(f'<div class="lg"><div class="lgtag">{e(g["tag"])}'
                         f'<span class="dim"> · {g["total"]} 款</span></div>'
                         f'<ul class="items">{lis}</ul></div>')
        limited_html = f"""
        <section class="block">
          <h3>✨ 本店限定 <span class="dim">读自此刻这家店的菜单标签</span></h3>
          {''.join(ghtml)}
        </section>"""

    return f"""
    <div class="reveal" id="reveal">
      <header class="rev-head">
        <div class="rev-date">{e(a['solar'])} · {e(a['day_gz'])}日 · {e(a['nayin'])}</div>
        <h1>今日宜吃<span class="hl">{e(main_name)}</span></h1>
        <div class="rev-sub">{e(conf)} · {e(w['desc'])} {w['temp']}°C（体感 {w['feels_like']}°C）
          · {e(f['logistics_why'])}</div>
      </header>

      <section class="block">
        <h3>🍔 今日餐单 <span class="dim">价格为本店菜单快照</span></h3>
        {''.join(cards)}
      </section>

      {coupon_html}
      {limited_html}

      <footer class="rev-foot">
        <p>黄历、五行、星宿属传统民俗娱乐，不构成健康或运势建议。</p>
        <p>用券价由 calculate-price 实测；下单前请再核一次价。</p>
        <button class="again" id="again" type="button">↺ 把纸贴回去</button>
      </footer>
    </div>
    """


CSS = """
:root{
  --paper:#F6EFE2; --paper2:#FBF6EC; --ink:#2A241E; --ink2:#6B5F52;
  --red:#C8102E; --gold:#E0A32E; --line:#D8CBB6;
}
*{box-sizing:border-box;margin:0;padding:0}
body{
  background:#E8DFCF;
  color:var(--ink);
  font-family:"Songti SC","Noto Serif SC",Georgia,"Times New Roman",serif;
  display:flex;justify-content:center;padding:24px 16px 48px;
  -webkit-font-smoothing:antialiased;
}
.stage{
  position:relative;width:100%;max-width:680px;height:820px;
  border-radius:18px;overflow:hidden;
  box-shadow:0 24px 60px rgba(60,44,28,.28), 0 2px 0 rgba(255,255,255,.6) inset;
  background:var(--paper2);
}
.reveal{
  position:absolute;inset:0;overflow-y:auto;padding:24px 22px 32px;
  background:linear-gradient(180deg,#FDFAF3,#F4EDE0);
  filter:blur(3px);transform:scale(.985);transform-origin:top center;
  transition:filter .5s ease, transform .5s ease;
}
.reveal::-webkit-scrollbar{width:6px}
.reveal::-webkit-scrollbar-thumb{background:#D9CDB8;border-radius:3px}

.sheet{
  position:absolute;inset:0;z-index:5;
  background:
    radial-gradient(120% 90% at 50% 0%, #FFFDF7 0%, var(--paper) 62%, #EFE5D3 100%);
  clip-path:polygon(0% 0%,100% 0%,100% 100%,0% 100%);
  transition:opacity .35s ease;
  cursor:grab;touch-action:none;
}
.sheet:active{cursor:grabbing}
.sheet-inner{
  height:100%;display:flex;flex-direction:column;
  padding:34px 30px 26px;text-align:center;
}
.sheet::after{
  content:"";position:absolute;inset:0;pointer-events:none;
  background-image:repeating-linear-gradient(0deg,rgba(120,100,70,.05) 0 1px,transparent 1px 4px);
  mix-blend-mode:multiply;opacity:.6;
}
.sheet-top{border-bottom:2px solid var(--red);padding-bottom:14px}
.solar-line{font-size:12.5px;letter-spacing:.42em;color:var(--ink2)}
.sheet-hero{
  flex:1;display:flex;align-items:center;justify-content:center;gap:24px;
  padding:10px 0;
}
.daynum{font-size:120px;line-height:.82;color:var(--red);font-weight:700;font-family:Georgia,serif}
.hero-right{text-align:left}
.lunar-big{font-size:40px;letter-spacing:.1em;color:var(--ink);font-weight:700}
.gz{margin-top:8px;color:var(--ink2);font-size:13.5px;letter-spacing:.1em}
.dow{font-size:12.5px;color:var(--ink2);letter-spacing:.22em;margin-top:10px}
.extra{
  display:flex;justify-content:center;gap:14px;flex-wrap:wrap;
  font-size:11.5px;color:#8A7D6C;letter-spacing:.1em;margin-top:9px;
}
.sheet-mid{
  position:relative;display:flex;align-items:center;justify-content:space-between;
  gap:18px;padding:18px 6px 22px;
}
.yi-ji{display:flex;flex-direction:column;gap:18px;flex:1;text-align:left}
.col{display:flex;gap:10px;align-items:flex-start}
.badge{
  flex:none;width:30px;height:30px;border-radius:6px;display:grid;place-items:center;
  font-size:15px;font-weight:700;color:#fff;
}
.badge.yi{background:var(--red)}
.badge.ji{background:#5C5348}
.words{font-size:14.5px;line-height:1.9;color:var(--ink);padding-top:4px;
  flex:1;word-break:keep-all;overflow-wrap:anywhere}
.seal{
  flex:none;width:132px;height:132px;border-radius:50%;
  border:3px double var(--red);display:grid;place-items:center;
  background:radial-gradient(circle at 35% 30%,#FFF6E6,#F6E7CB);
  box-shadow:0 6px 18px rgba(200,16,46,.12) inset;
  transform:rotate(-6deg);
}
.seal-char{font-size:56px;color:var(--red);font-weight:700;line-height:1}
.seal-cap{font-size:11px;letter-spacing:.3em;color:var(--ink2);margin-top:4px}
.sheet-meta{
  display:flex;justify-content:center;gap:16px;flex-wrap:wrap;
  font-size:12.5px;color:var(--ink2);padding:10px 0;
  border-top:1px dashed var(--line);
}
.sheet-foot{padding-top:14px;display:grid;gap:10px;justify-items:center}
.hint{font-size:13px;color:var(--ink2);letter-spacing:.08em;transition:opacity .2s}
.tear-btn,.again{
  font-family:inherit;font-size:14px;letter-spacing:.2em;
  padding:11px 30px;border-radius:999px;border:1.5px solid var(--red);
  background:var(--red);color:#fff;cursor:pointer;transition:.2s;
}
.tear-btn:hover,.again:hover{background:#A50D26;border-color:#A50D26}
.again{background:transparent;color:var(--red)}
.again:hover{background:var(--red);color:#fff}
.serration{position:absolute;left:0;right:0;bottom:-1px;height:14px;pointer-events:none}

/* ── 撕开后 ── */
.rev-head{border-bottom:2px solid var(--red);padding-bottom:14px;margin-bottom:20px}
.rev-date{font-size:13px;color:var(--ink2);letter-spacing:.1em}
.rev-head h1{font-size:30px;margin:10px 0 8px;letter-spacing:.06em}
.hl{color:var(--red);border-bottom:4px solid rgba(224,163,46,.55)}
.rev-sub{font-size:13px;color:var(--ink2);line-height:1.7}
.block{margin-bottom:22px}
.block h3{font-size:15px;letter-spacing:.1em;margin-bottom:10px;color:var(--ink)}
.dim{color:var(--ink2);font-weight:400;font-size:12px;letter-spacing:0}
.plan{
  background:#fff;border:1px solid var(--line);border-radius:12px;
  padding:14px 16px;margin-bottom:12px;
  box-shadow:0 2px 0 rgba(216,203,182,.5);
}
.plan-head{display:flex;align-items:center;gap:8px;flex-wrap:wrap}
.picon{font-size:17px}
.ptag{font-size:14px;font-weight:700;letter-spacing:.04em;flex:1}
.pprice{display:flex;align-items:baseline;gap:7px;font-family:ui-sans-serif,system-ui,sans-serif}
.was{color:#A99C88;text-decoration:line-through;font-size:13px}
.now{color:var(--red);font-size:19px;font-weight:700}
.save{background:#FDE9E5;color:var(--red);font-size:11px;padding:2px 7px;border-radius:999px}
.pdesc{font-size:12.5px;color:var(--ink2);margin:6px 0 10px}
.items{list-style:none;display:grid;gap:5px}
.items li{display:flex;justify-content:space-between;font-size:13.5px;padding:3px 0;border-bottom:1px dotted #EFE6D6}
.items li:last-child{border-bottom:none}
.iname{color:var(--ink)}
.iprice{color:var(--ink2);font-family:ui-sans-serif,system-ui,sans-serif}
.note{font-size:11.5px;color:#8A6A2E;background:#FCF4E0;padding:4px 8px;border-radius:6px;margin-top:7px}
.coupon-hit{font-size:12px;color:var(--red);margin-top:8px}
.preason{font-size:12px;color:var(--ink2);margin-top:9px;padding-top:8px;border-top:1px dashed var(--line)}
.coupon-list{list-style:none;display:grid;gap:7px}
.coupon-list li{
  display:flex;align-items:center;gap:9px;flex-wrap:wrap;
  background:#fff;border:1px solid var(--line);border-radius:9px;padding:9px 12px;font-size:13px;
}
.coupon-list .ok{color:#1B7A3D;font-size:11px;background:#E8F5EC;padding:2px 7px;border-radius:999px}
.coupon-list .wait{color:#8A6A2E;font-size:11px;background:#FCF4E0;padding:2px 7px;border-radius:999px}
.coupon-list .no{color:#8A8177;font-size:11px;background:#F2EEE6;padding:2px 7px;border-radius:999px}
.upcoming-tip{
  margin-top:10px;font-size:12.5px;color:#8A6A2E;background:#FCF4E0;
  border-left:3px solid var(--gold);padding:9px 12px;border-radius:0 8px 8px 0;
}
.lg{margin-bottom:12px}
.lgtag{font-size:13px;font-weight:700;margin-bottom:6px;color:var(--red)}
.rev-foot{border-top:1px solid var(--line);padding-top:14px;font-size:11.5px;color:var(--ink2);line-height:1.9}
.rev-foot p{margin-bottom:4px}
.again{margin-top:12px}

@media (max-width:520px){
  .lunar-big{font-size:36px}
  .seal{width:104px;height:104px}
  .seal-char{font-size:44px}
  .words{max-width:150px;font-size:13px}
  .rev-head h1{font-size:24px}
  .stage{height:88vh}
}
"""

JS = """
(function(){
  var stage  = document.querySelector('.stage');
  var sheet  = document.getElementById('sheet');
  var reveal = document.getElementById('reveal');
  var hint   = document.getElementById('hint');
  var btn    = document.getElementById('tearBtn');
  var again  = document.getElementById('again');
  var p = 0, dragging = false, startY = 0, done = false, raf = null;

  // 撕口用锯齿状 clip-path：越靠上撕开越多，边缘带一点随机抖动才像纸
  function paint(prog){
    var base = 100 - prog * 100;
    var pts  = ['0% 0%', '100% 0%'];
    for (var x = 100; x >= 0; x -= 2.5){
      var j = (prog > 0.02 && prog < 0.99)
        ? Math.sin(x * 1.7) * 1.25 + Math.cos(x * 3.1) * 0.65
        : 0;
      var y = Math.min(100, Math.max(0, base + j));
      pts.push(x + '% ' + y + '%');
    }
    sheet.style.clipPath = 'polygon(' + pts.join(',') + ')';
    sheet.style.transform = 'translateY(' + (-prog * 10) + 'px) rotate(' + (-prog * 0.7) + 'deg)';
    sheet.style.opacity = prog > 0.94 ? String(1 - (prog - 0.94) / 0.06) : '1';
    reveal.style.filter = 'blur(' + ((1 - prog) * 3).toFixed(2) + 'px)';
    reveal.style.transform = 'scale(' + (0.985 + prog * 0.015).toFixed(4) + ')';
    if (hint) hint.style.opacity = String(Math.max(0, 1 - prog * 2.2));
  }

  function animateTo(target, cb){
    cancelAnimationFrame(raf);
    reveal.style.transition = 'none';
    var from = p, t0 = performance.now(), dur = 380;
    function step(t){
      var k = Math.min(1, (t - t0) / dur);
      var ease = 1 - Math.pow(1 - k, 3);
      p = from + (target - from) * ease;
      paint(p);
      if (k < 1) raf = requestAnimationFrame(step);
      else if (cb) cb();
    }
    raf = requestAnimationFrame(step);
  }

  function finish(){
    if (done) return;
    done = true;
    animateTo(1, function(){
      sheet.style.pointerEvents = 'none';
      sheet.style.display = 'none';
      reveal.style.filter = 'none';
      reveal.style.transform = 'scale(1)';
    });
  }

  function reset(){
    done = false;
    sheet.style.display = '';
    sheet.style.pointerEvents = 'auto';
    p = 0; paint(0);
    reveal.style.filter = 'blur(3px)';
    reveal.style.transform = 'scale(0.985)';
    reveal.scrollTop = 0;
  }

  sheet.addEventListener('pointerdown', function(ev){
    if (done) return;
    // 关键：按钮上不能开始拖拽。一旦 setPointerCapture，后续的 click
    // 会被重定向到 sheet 本身，按钮就永远收不到点击了。
    if (ev.target && ev.target.closest && ev.target.closest('button')) return;
    dragging = true; startY = ev.clientY;
    reveal.style.transition = 'none';   // 拖动时要跟手，别被 CSS 过渡拖慢
    try { sheet.setPointerCapture(ev.pointerId); } catch (e) {}
  });
  sheet.addEventListener('pointermove', function(ev){
    if (!dragging) return;
    var d = (startY - ev.clientY) / 300;
    p = Math.max(0, Math.min(1, d));
    paint(p);
  });
  function endDrag(){
    if (!dragging) return;
    dragging = false;
    if (p > 0.5) finish();
    else animateTo(0);
  }
  sheet.addEventListener('pointerup', endDrag);
  sheet.addEventListener('pointercancel', endDrag);
  sheet.addEventListener('pointerleave', function(){ if (dragging) endDrag(); });

  btn.addEventListener('click', function(ev){ ev.stopPropagation(); finish(); });
  if (again) again.addEventListener('click', reset);
  window.addEventListener('keydown', function(ev){
    if ((ev.key === ' ' || ev.key === 'Enter') && !done){ ev.preventDefault(); finish(); }
  });
  paint(0);
})();
"""

TEMPLATE = """<!DOCTYPE html>
<html lang="zh-CN">
<head>
<meta charset="utf-8">
<meta name="viewport" content="width=device-width,initial-scale=1">
<title>今日撕历 · %%TITLE%%</title>
<style>%%CSS%%</style>
</head>
<body>
  <div class="stage">
    %%REVEAL%%
    %%SHEET%%
  </div>
<script>%%JS%%</script>
</body>
</html>
"""


def generate(city, menu_path, store_code=None, order_type=1, be_type=1,
             day=None, fortune_path=None) -> str:
    if fortune_path:
        f = json.load(open(fortune_path, encoding="utf-8"))
    else:
        f = df.build(city, None, None, day or date.today())

    if menu_path:
        menu = sg.load_menu(menu_path)
        plans, pool = sg.build_plans(f, menu)
        limited = sg.limited_items(menu)
    else:
        plans, pool, limited = [], {}, []

    coupon_rep, upcoming = None, []
    if store_code and menu_path:
        coupon_rep, upcoming = sg.apply_coupons(
            plans, pool, {"storeCode": store_code, "orderType": order_type,
                          "beType": be_type}, menu, f)

    title = f"{f['almanac']['solar']} 农历{f['almanac']['lunar']}"
    return (TEMPLATE
            .replace("%%CSS%%", CSS)
            .replace("%%JS%%", JS)
            .replace("%%TITLE%%", e(title))
            .replace("%%SHEET%%", build_sheet(f))
            .replace("%%REVEAL%%", build_reveal(f, plans, coupon_rep, upcoming, limited)))


def main():
    ap = argparse.ArgumentParser(description="生成今日撕历 HTML")
    ap.add_argument("--city", default="北京")
    ap.add_argument("--menu", help="query-meals 返回体；不给则只出命盘页")
    ap.add_argument("--fortune", help="daily_fortune.py 的 JSON")
    ap.add_argument("--store-code")
    ap.add_argument("--order-type", type=int, default=1)
    ap.add_argument("--be-type", type=int, default=1)
    ap.add_argument("--date")
    ap.add_argument("--out", default="demo/today_calendar.html")
    a = ap.parse_args()

    day = date.fromisoformat(a.date) if a.date else None
    html_text = generate(a.city, a.menu, a.store_code, a.order_type, a.be_type, day, a.fortune)
    with open(a.out, "w", encoding="utf-8") as fp:
        fp.write(html_text)
    print(f"已生成：{a.out}（{len(html_text)} 字节）")


if __name__ == "__main__":
    main()
