/* ── 麦麦黄道吉日 · 交互 ────────────────────────────────────────
   页面只消费 MCD_DATA 里的真实数据：天气、门店菜单、券、核价。
   拿不到的（别的日期的天气/菜单/价格）一律标「需当天实时查询」。 */

(function () {
  let D = window.MCD_DATA;
  const $ = (s, r) => (r || document).querySelector(s);
  const $$ = (s, r) => Array.from((r || document).querySelectorAll(s));

  const MEAT = {
    BEEF: '牛肉', FISH: '鳕鱼', CHICKEN: '鸡肉', PORK: '猪柳', FRIED: '炸物',
    VEG: '蔬果', POTATO: '薯条', DESSERT: '甜品', COFFEE: '咖啡',
    TEA: '茶饮', SODA: '汽水', SHARE: '分享餐'
  };
  const WD = ['日', '一', '二', '三', '四', '五', '六'];

  const state = { planIdx: 0, sel: D.meta.today, cursor: null, view: 'tear', order: null, quote: null,
                  basket: {}, takeWay: '', storeKind: 'pickup' };

  /* ── 工具 ─────────────────────────────────────────── */
  const key = d => `${d.getFullYear()}-${String(d.getMonth() + 1).padStart(2, '0')}-${String(d.getDate()).padStart(2, '0')}`;
  const parse = k => { const [y, m, d] = k.split('-').map(Number); return new Date(y, m - 1, d); };
  const fmtCN = k => { const d = parse(k); return `${d.getMonth() + 1}月${d.getDate()}日`; };
  const esc = s => String(s == null ? '' : s).replace(/[&<>"]/g, c => ({ '&': '&amp;', '<': '&lt;', '>': '&gt;', '"': '&quot;' }[c]));
  const money = n => `¥${(+n || 0).toFixed(2)}`;

  function toast(msg, ms = 2200) {
    let t = $('.toast');
    if (!t) { t = document.createElement('div'); t.className = 'toast'; document.body.appendChild(t); }
    t.textContent = msg; t.classList.add('on');
    clearTimeout(t._h); t._h = setTimeout(() => t.classList.remove('on'), ms);
  }

  function go(view) {
    state.view = view;
    $$('.view').forEach(v => v.classList.toggle('on', v.id === 'view-' + view));
    window.scrollTo({ top: 0, behavior: 'smooth' });
  }

  /* ── 数据边界 ─────────────────────────────────────── */
  let days = Object.keys(D.calendar).sort();
  let minK = days[0], maxK = days[days.length - 1];
  const plan = () => (D.plans && D.plans.length ? D.plans[state.planIdx % D.plans.length] : null);

  /* ── 篮子：菜单和小票共用同一份选中状态 ──────────────
     进页先把推荐套餐配进篮子（先帮玩家配好），玩家在菜单卡
     里加减货，小票实时跟着换；动过之后就算「自选」。 */
  function basketList() {
    const all = D.menu || [];
    return Object.keys(state.basket).map(c => {
      const m = all.find(x => x.code === c);
      return m ? { ...m, qty: state.basket[c] }
        : { code: c, name: '（这家店没有此商品）', price: 0, qty: state.basket[c], cat: '' };
    });
  }
  const basketSum = () => basketList().reduce((s, i) => s + i.price * i.qty, 0);

  function prefillBasket() {
    const p = plan();
    state.basket = {};
    (p ? p.items : []).forEach(i => { if (i.code) state.basket[i.code] = i.qty || 1; });
    state.basketTouched = false;
  }

  /* 动过篮子（且不为空）→ 小票按自选画；没动过 → 按推荐套餐（已核价）画 */
  function basketMode() {
    return !!state.basketTouched && basketList().length > 0;
  }

  function effectivePlan() {
    if (basketMode()) {
      const list = basketList();
      return {
        tag: '自选', verified: false, coupon: null, adjust: null, delivery_items: null,
        items: list.map(i => ({
          code: i.code, cat: i.cat || '',
          name: i.qty > 1 ? `${i.name} ×${i.qty}` : i.name,
          price: i.price * i.qty
        })),
        total: basketSum()
      };
    }
    return plan();
  }

  /* ── 置顶菜单卡：进页先看到，先配好、可增减、跟小票同步 ── */
  function renderMenuCard() {
    const host = $('#menuCard');
    if (!host) return;
    const list = basketList();
    const limited = D.limited || [];
    const rows = list.map(it => `
      <div class="mt-item on" data-code="${esc(it.code)}">
        <div class="mt-names">
          <div class="mt-name">${esc(it.name)}
            ${(it.tags || []).slice(0, 1).map(t => `<span class="tagline">${esc(t)}</span>`).join('')}</div>
          <div class="mt-meta">${esc(it.group || it.cat_name || '')}</div>
        </div>
        <div class="mt-act">
          <span class="mt-price">${money(it.price * it.qty)}</span>
          <div class="stepper"><button data-m="-1">−</button><b>${it.qty}</b><button data-m="1">＋</button></div>
        </div>
      </div>`).join('')
      || `<div class="note" style="padding:10px 2px">菜单暂不可用，先看看黄历。</div>`;

    const chips = limited.slice(0, 4).map(it => `
      <button class="lim-chip${state.basket[it.code] ? ' on' : ''}" data-add="${esc(it.code)}">
        ${esc(it.name)}<i>${money(it.price)}</i></button>`).join('');

    host.innerHTML = `<div class="card">
      <div class="alm-title" style="font-size:17px">今日菜单 · 已替你配好一份
        <small>${(D.menu || []).length} 款实时在售 · 限定 ${limited.length} 款 · 改了小票就跟着换</small></div>
      <div class="mt-list">${rows}</div>
      ${chips ? `<div class="lim-row">${chips}</div>` : ''}
      <div class="basket-bar" style="margin-top:12px">
        <div><b>合计（菜单价）</b><span>${money(basketSum())} · 下单前由 calculate-price 再核一次</span></div>
        <button class="btn btn-ghost" id="resetPlan">换回推荐</button>
      </div>
      <div style="margin-top:10px;display:flex;gap:8px">
        <button class="btn btn-primary" id="menuOrder">使用优惠 · 一键下单</button>
        <button class="btn btn-ghost" id="menuMore">整份菜单</button>
      </div>
    </div>`;

    $$('#menuCard .mt-item').forEach(row => {
      row.onclick = ev => {
        const btn = ev.target.closest('[data-m]');
        if (!btn) return;
        const code = row.dataset.code;
        const next = Math.max(0, (state.basket[code] || 0) + Number(btn.dataset.m));
        if (next) state.basket[code] = next; else delete state.basket[code];
        state.basketTouched = true;
        renderMenuCard();
        renderReceipt();
      };
    });
    $$('#menuCard .lim-chip').forEach(chip => {
      chip.onclick = () => {
        const code = chip.dataset.add;
        if (!state.basket[code]) { state.basket[code] = 1; state.basketTouched = true; }
        renderMenuCard();
        renderReceipt();
      };
    });
    $('#resetPlan').onclick = () => {
      prefillBasket();
      renderMenuCard();
      renderReceipt();
      toast('换回今天的推荐搭配');
    };
    $('#menuOrder').onclick = () => {
      const o = orderParams(
        basketList().map(i => ({ code: i.code, name: i.name, price: i.price, cat: i.cat, qty: i.qty })),
        basketSum(), basketMode() ? '自选' : (plan() ? plan().tag : ''));
      if (!o) { toast('当前取餐方式下这单没法下'); return; }
      openOrder(o);
    };
    $('#menuMore').onclick = openMenu;
  }

  /* 换一家店 = 换一整套菜单 / 券 / 价，页面得整块重画 */
  function applyData(d) {
    D = d;
    state.planIdx = 0;
    state.sel = D.meta.today;
    state.cursor = null;
    state.basket = {};
    state.takeWay = '';
    days = Object.keys(D.calendar).sort();
    minK = days[0]; maxK = days[days.length - 1];
    $('#locName').textContent = D.meta.place.replace(/^.*?(省|市)/, '') || D.meta.place;
    $('#locSrc').textContent = D.meta.loc_source;
    $('#genAt').textContent = D.meta.generated_at;
    $('#warnHost').innerHTML = warnHTML();
    renderCalendar();
    renderSide(D.meta.today);
    renderToday();
    renderAte();
    prefillBasket();
    renderMenuCard();
    renderOrderReceipt();
  }

  function warnHTML() {
    return (D.warnings || []).length
      ? `<div class="warnbar" style="max-width:1080px;margin:0 auto 14px"><span>⚠ 数据提示</span><span>${D.warnings.map(esc).join('；')}</span></div>` : '';
  }

  function sceneKey() {
    const w = D.weather;
    if (!w) return 'mild';
    if ((w.precip_mm || 0) > 0 || (w.pop_max || 0) >= 60) return 'rain';
    if ((w.feels_like ?? 20) >= 28) return 'hot';
    if ((w.feels_like ?? 20) < 10) return 'cold';
    return 'mild';
  }

  /* ── 月历 ─────────────────────────────────────────── */
  function renderCalendar() {
    const base = parse(state.sel === D.meta.today ? D.meta.today : state.sel);
    if (!state.cursor) state.cursor = new Date(base.getFullYear(), base.getMonth(), 1);
    const c = state.cursor;
    const y = c.getFullYear(), m = c.getMonth();

    $('#monthLabel').textContent = `${y} 年 ${m + 1} 月`;
    $('#monthSub').textContent = `农历${D.calendar[D.meta.today] ? D.calendar[D.meta.today].lunar_full.replace(/二〇.+\u5e74/, '') : ''} · 每日皆吉`;

    const first = new Date(y, m, 1);
    const startPad = first.getDay();
    const daysInMonth = new Date(y, m + 1, 0).getDate();

    let html = '';
    for (let i = 0; i < startPad; i++) html += `<div class="day dim"></div>`;
    for (let d = 1; d <= daysInMonth; d++) {
      const k = key(new Date(y, m, d));
      const info = D.calendar[k];
      const isToday = k === D.meta.today;
      const cls = ['day'];
      if (!info) cls.push('dim');
      if (isToday) cls.push('today');
      if (k === state.sel && !isToday) cls.push('sel');
      if (k < D.meta.today) cls.push('past');
      const lun = info ? info.lunar.replace(/^.*?月/, '') : '';
      html += `<div class="${cls.join(' ')}" data-k="${k}" role="button" tabindex="0"
          aria-label="${fmtCN(k)}${info ? '，农历' + info.lunar : '，超出可查范围'}">
        ${isToday ? '<span class="deco star">✦</span>' : ''}
        <span class="n">${d}</span>
        ${info ? `<span class="l">${esc(lun)}</span><span class="ji">吉</span>` : ''}
        ${isToday ? smallDoodle() : ''}
      </div>`;
    }
    const tail = (7 - ((startPad + daysInMonth) % 7)) % 7;
    for (let i = 0; i < tail; i++) html += `<div class="day dim"></div>`;

    const grid = $('#grid');
    grid.innerHTML = html;
    grid.onclick = e => {
      const cell = e.target.closest('.day[data-k]');
      if (!cell || cell.classList.contains('dim')) return;
      pick(cell.dataset.k);
    };

    const curK = key(new Date(y, m, 1));
    $('#prevM').disabled = key(new Date(y, m - 1, 1)) < minK.slice(0, 7) + '-01' && (y === parse(minK).getFullYear() && m - 1 < parse(minK).getMonth());
    $('#nextM').disabled = key(new Date(y, m + 1, 1)) > maxK;
  }

  function smallDoodle() {
    // 今天的小薯条装饰
    return `<svg class="deco fries" viewBox="0 0 12 14" aria-hidden="true">
      <rect x="1.5" y="0.5" width="1.6" height="7" fill="#F2C14E" rx=".8"/>
      <rect x="4" y="0" width="1.6" height="7.5" fill="#EFB922" rx=".8"/>
      <rect x="6.6" y="1" width="1.6" height="6.5" fill="#F2C14E" rx=".8"/>
      <rect x="9" y="1.5" width="1.6" height="6" fill="#EFB922" rx=".8"/>
      <path d="M1 6.5h10l-1.2 7H2.2z" fill="#C8102E"/>
    </svg>`;
  }

  function pick(k) {
    state.sel = k;
    if (k === D.meta.today) { go('today'); renderToday(); return; }
    renderCalendar();
    renderSide(k);
    if (window.innerWidth <= 860) $('#side').scrollIntoView({ behavior: 'smooth', block: 'start' });
  }

  /* 非今日：只有黄历可查，天气/菜单/价格必须标注不可用 */
  function localSign(info) {
    const yi = (info.yi || [])[0] || '诸事皆宜';
    const ji = (info.ji || [])[0];
    const tail = ji ? `忌${ji}，那就别硬来。` : '没有要忌的事，正好吃顿好的。';
    return `今日宜「${yi}」，宜顺手开一顿麦当劳。${tail}`;
  }

  function renderSide(k) {
    const info = D.calendar[k];
    const d = parse(k);
    $('#side').innerHTML = `
      <div class="card">
        <div class="side-date"><span class="big">${d.getDate()}</span>
          <span class="sub">${d.getFullYear()}年${d.getMonth() + 1}月 · 周${WD[d.getDay()]}</span></div>
        <div class="side-lunar">${esc(info.lunar_full)}</div>
        <div class="side-gz">${esc(info.day_gz)}日 · ${esc(info.nayin)} · 值日「${esc(info.zhixing)}」</div>
        <div class="side-yiji">
          <div><span class="k yi">宜</span><span class="v">${esc((info.yi || []).join('、') || '无')}</span></div>
          <div><span class="k ji">忌</span><span class="v">${esc((info.ji || []).join('、') || '无')}</span></div>
        </div>
        <div class="sign-box">${esc(localSign(info))}</div>
        <div class="note">这一天只可查黄历。天气、门店菜单与价格必须当天实时查询 —— 不能拿今天的数字充数。</div>
        ${k === D.meta.today ? '' : `<button class="btn btn-ghost btn-block" style="margin-top:12px" onclick="MCD.today()">回到今天 · 生成今日套餐</button>`}
      </div>
      <div class="card">
        <div class="row"><span class="lab">幸运色</span><span class="val">${esc(info.color)}</span></div>
        <div class="row" style="margin:0"><span class="lab">喜神</span><span class="val">${esc(info.xi)}</span></div>
      </div>`;
  }

  /* ── 今日黄历牌 ───────────────────────────────────── */
  function weatherBlock() {
    const w = D.weather;
    if (!w) {
      return `<div class="weather-strip"><div class="d"><b>天气暂不可用</b><br>查询失败，今日不作天气相关推荐</div></div>`;
    }
    return `<div class="weather-strip">
      <svg class="ico" viewBox="0 0 40 40" aria-hidden="true">${weatherIcon(w)}</svg>
      <div>
        <div class="t">${w.temp}° <span class="tt">${esc(w.desc)}</span></div>
        <div class="d">体感 ${w.feels_like}° · 降水概率 ${w.pop_max}%<br>
        ${esc(D.meta.city)}${D.meta.district ? ' ' + esc(D.meta.district) : ''}</div>
      </div>
    </div>`;
  }

  function weatherIcon(w) {
    const s = sceneKey();
    if (s === 'rain') {
      return `<circle cx="20" cy="15" r="9" fill="#EADFCA"/>
        <circle cx="11" cy="18" r="6" fill="#EADFCA"/><circle cx="29" cy="18" r="6" fill="#EADFCA"/>
        <path d="M13 25l-2 6M20 25l-2 7M27 25l-2 6" stroke="#8FB8D6" stroke-width="2.6" stroke-linecap="round"/>`;
    }
    if (s === 'hot') {
      return `<circle cx="20" cy="20" r="8" fill="#FFC72C"/>
        <g stroke="#FFC72C" stroke-width="2.4" stroke-linecap="round">
          <line x1="20" y1="4" x2="20" y2="8"/><line x1="20" y1="32" x2="20" y2="36"/>
          <line x1="4" y1="20" x2="8" y2="20"/><line x1="32" y1="20" x2="36" y2="20"/>
          <line x1="8.6" y1="8.6" x2="11.4" y2="11.4"/><line x1="28.6" y1="28.6" x2="31.4" y2="31.4"/>
        </g>`;
    }
    if (s === 'cold') {
      return `<g stroke="#8FB8D6" stroke-width="2.4" stroke-linecap="round" transform="translate(20,20)">
        <line x1="-11" y1="0" x2="11" y2="0"/><line x1="0" y1="-11" x2="0" y2="11"/>
        <line x1="-7.8" y1="-7.8" x2="7.8" y2="7.8"/><line x1="-7.8" y1="7.8" x2="7.8" y2="-7.8"/></g>`;
    }
    return `<circle cx="27" cy="13" r="7" fill="#FFC72C"/>
      <circle cx="16" cy="22" r="8" fill="#EADFCA"/><circle cx="26" cy="24" r="6.5" fill="#EADFCA"/>
      <rect x="9" y="22" width="24" height="7" rx="3.5" fill="#EADFCA"/>`;
  }

  function renderToday() {
    const a = D.almanac, p = plan();
    const yi = D.yiji.yi, ji = D.yiji.ji;
    const coupons = D.coupons;

    const save = coupons.usable.length ? `${coupons.usable.length} 张今日可用`
      : (coupons.upcoming.length ? `${coupons.upcoming.length} 张明天起可用` : '今日暂无可用券');

    // 宜忌小图标：按真实文案/推荐食材动态匹配，不是写死的
    const yiIcon = x => { const k = ART.foodKey(x); return k ? ART.icon(k) : ''; };
    const meatWord = p ? (MEAT[p.items[0].cat] || '—') : '待定（菜单不可用）';
    const meatIcon = p ? ART.icon(ART.foodKey(meatWord) || 'star') : '';

    $('#almCard').innerHTML = `
      <div class="alm-head">
        <div>
          <div class="alm-title">今日麦麦黄历
            <small>${a.solar} · 农历${a.lunar.replace(/二〇.+\u5e74/, '')} · ${a.day_gz}日 ${a.nayin}</small></div>
        </div>
        <div class="chips">
          <span class="chip ${D.yiji.luck === '凶' ? '' : 'gold'}">${D.yiji.luck === '凶' ? '凶日 · 宜吃麦当劳转运' : '黄道吉日'}</span>
          <span class="chip gold">值日「${esc(a.zhixing)}」</span>
          <span class="chip gold">${esc(a.xiu)}</span>
          <span class="chip">喜神 ${esc(a.xi_position)}</span>
          <span class="chip">幸运色 ${esc(a.lucky_color)}</span>
        </div>
      </div>
      <div class="alm-grid">
        <div class="alm-left">
          ${weatherBlock()}
          <div class="yj-line"><span class="k yi">宜</span>
            <div class="chips">${yi.map(x => `<span class="chip yi">${yiIcon(x)}<span>${esc(x)}</span></span>`).join('')}</div></div>
          <div class="yj-line"><span class="k ji">忌</span>
            <div class="chips">${ji.map(x => `<span class="chip ji"><span>${esc(x)}</span></span>`).join('')}</div></div>
        </div>
        <div class="alm-right">
          <div class="mode-box">
            <div class="m">${ART.icon('bag')}<span>${esc(D.logistics.label)}</span></div>
            <div class="w">${esc(D.logistics.why)}</div>
            ${D.store.pickup ? `<div class="w" style="margin-top:6px">
              ${esc(D.store.pickup.name)}${D.store.pickup.distance != null ? ' · ' + D.store.pickup.distance + 'm' : ''}
              <button class="linkbtn" id="chgStore2">换一家</button></div>` : ''}
            ${D.logistics.compare ? `<div class="w" style="margin-top:6px;opacity:.9">
              自取 ${money(D.logistics.compare.pickup)} · 外送 ${money(D.logistics.compare.delivery)}
              （配送 ${money(D.logistics.compare.delivery_fee)} + 打包 ${money(D.logistics.compare.packing_fee)}）</div>` : ''}
          </div>
          <div class="row" style="margin-top:12px"><span class="lab">开运食材</span>
            <span class="val meat-val">${meatIcon}<b>${esc(meatWord)}</b></span></div>
          <div class="row"><span class="lab">省钱妙招</span><span class="val">${esc(save)}</span></div>
          <div class="row" style="margin-bottom:0"><span class="lab">指向强度</span>
            <span class="val">${esc(D.fortune.confidence_note)}</span></div>
        </div>
      </div>
      <div class="alm-doodle" aria-hidden="true">${ART.svg.doodle()}</div>`;

    renderReceipt();
    renderLimited();
    const c2 = $('#chgStore2');
    if (c2) c2.onclick = openStores;
  }

  /* 今日限定 / 上新：只认菜单标签，不认想象。
     限定已经并进整份菜单（openMenu 里置顶），这块只做入口与摘要。 */
  function renderLimited() {
    const host = $('#limCard');
    if (!host) return;
    const menu = D.menu || [];
    const items = D.limited || [];
    const menuCount = menu.length;
    if (!menuCount) {
      host.innerHTML = `<div class="card"><div class="row" style="margin:0">
        <span class="lab">本店菜单</span><span class="val">菜单暂不可用</span></div></div>`;
      return;
    }
    const tags = {};
    items.forEach(it => ((it.tags || ['上新'])[0] && (tags[(it.tags || ['上新'])[0]] = (tags[(it.tags || ['上新'])[0]] || 0) + 1)));
    const tagLine = Object.keys(tags).map(t => `${esc(t)} ${tags[t]}`).join(' · ') || '本店当前没有打「上新 / 限定」标签的商品';
    host.innerHTML = `<div class="card">
      <div class="alm-title" style="font-size:17px">本店菜单
        <small>${menuCount} 款 · 限定已并进菜单，置顶显示 · 实时现拉</small></div>
      <div class="row"><span class="lab">限定 / 上新</span><span class="val">${tagLine}</span></div>
      <div style="margin-top:10px;display:flex;flex-direction:column;gap:5px">
        ${items.slice(0, 4).map(it => `<div class="kv" style="padding:3px 0">
          <span class="k" style="color:var(--ink)">${esc(it.name)}
            ${(it.tags || []).slice(0, 1).map(t => `<span class="tagline">${esc(t)}</span>`).join('')}</span>
          <span class="v">${money(it.price)}</span></div>`).join('')}
        ${items.length > 4 ? `<div class="note">还有 ${items.length - 4} 款限定在菜单里</div>` : ''}
      </div>
      <div style="margin-top:12px"><button class="btn btn-ghost btn-block" id="openMenu">打开整份菜单 · 挑自己的</button></div>
    </div>`;
    $('#openMenu').onclick = openMenu;
  }

  /* ── 今日吃了麦当劳 ──────────────────────────────────
     付款在麦当劳 App 里完成，页面看不见那一下。所以两条路：
     ① 查订单状态自己认（状态里出现「已支付 / 制作中 / 已完成」）
     ② 你自己点一下「我吃到了」 */
  function ateKey() { return 'mcd-ate-' + D.meta.today; }

  function ateGet() {
    try { return JSON.parse(localStorage.getItem(ateKey()) || 'null'); } catch (e) { return null; }
  }

  function ateSet(v) {
    try { localStorage.setItem(ateKey(), JSON.stringify(v)); } catch (e) { }
    renderAte();
    renderReceipt();
    renderCalendar();
  }

  function renderAte() {
    const host = $('#ateCard');
    if (!host) return;
    const a = ateGet();
    if (!a) {
      host.innerHTML = `<div class="ate-empty">
        <span>今天这一顿，吃完再回来盖章</span>
        <button class="btn btn-ghost" id="ateManual">我今天吃了麦当劳</button>
      </div>`;
      $('#ateManual').onclick = () => askAte();
      return;
    }
    host.innerHTML = `<div class="ate-card">
      <div class="ate-seal">已吃</div>
      <div class="ate-main">
        <div class="ate-title">今日吃了麦当劳</div>
        <div class="ate-sub">${esc(a.dateText || fmtCN(D.meta.today))} · ${esc(a.time || '')}
          ${a.store ? ' · ' + esc(a.store) : ''}</div>
        <div class="ate-meta">
          ${a.pickupCode ? `<span class="ate-code">取餐码 ${esc(a.pickupCode)}</span>` : ''}
          ${a.orderId ? `<span>订单 ${esc(String(a.orderId).slice(-8))}</span>` : ''}
        </div>
      </div>
    </div>`;
  }

  function askAte() {
    showSheet('今天吃了麦当劳？', `
      <div class="note">盖个章，今天这一页就算圆满。要写在这一天的记录里，
      不吃也可以留白。</div>
      <div style="height:10px"></div>
      <div class="kv"><span class="k">门店</span><span class="v">${esc((D.store.pickup || {}).name || '—')}</span></div>
      <div class="kv"><span class="k">这一顿</span><span class="v">${esc(plan() ? plan().tag : '—')}</span></div>`,
      `<button class="btn btn-ghost" id="ateNo">还没吃</button>
       <button class="btn btn-primary" id="ateYes">盖章：已吃</button>`);
    $('#ateNo').onclick = () => $('#modal').classList.remove('on');
    $('#ateYes').onclick = () => {
      markAte({ time: new Date().toTimeString().slice(0, 5), store: (D.store.pickup || {}).name });
      showSheet('今日已圆满', `
        <div class="note">「${esc(D.sign.split('。')[0])}」<br>这一顿算你今天做对的事之一。</div>`, '');
    };
  }

  function markAte(extra) {
    const prev = ateGet() || {};
    ateSet({ ...prev, ...extra, dateText: fmtCN(D.meta.today) });
  }

  /* ── 整份菜单（限定置顶，能自己挑） ───────────────── */
  const MENU_FILTERS = [
    ['all', '全部'], ['limited', '限定 / 上新'], ['main', '汉堡主食'],
    ['side', '小食'], ['drink', '饮品'], ['dessert', '甜品']
  ];

  /* ── 订单小票：下单成功后生成，跟着这单的支付状态走 ── */
  function orderRecGet() {
    try { return JSON.parse(localStorage.getItem('mcd-order-latest') || 'null'); } catch (e) { return null; }
  }

  function orderRecSet(rec) {
    try { localStorage.setItem('mcd-order-latest', JSON.stringify(rec)); } catch (e) { }
    renderOrderReceipt();
  }

  function renderOrderReceipt() {
    const o = orderRecGet();
    // 今日页和小票页各放一张，状态同步
    ['#orderCard', '#orderCardRp'].forEach(sel => {
      const host = $(sel);
      if (!host) return;
      if (!o) { host.innerHTML = ''; return; }
      const rows = (o.items || []).map(i => `
        <div class="or-row item"><span class="k"></span>
          <span class="v"><b>${esc(i.name)}</b>${i.qty > 1 ? ` ×${i.qty}` : ''}</span></div>`).join('');
      const exp = o.expireAt ? new Date(String(o.expireAt).replace(/-/g, '/')) : null;

      host.innerHTML = `<div class="order-rec">
        <div class="or-head">麦麦订单小票<span>No.${esc(String(o.orderId || '').slice(-10))}</span></div>
        <div class="or-body">
          <div class="or-stamp">${o.paid ? '已付' : (o.canceled ? '已取消' : '待付')}</div>
          <div class="or-row"><span class="k">门店</span><span class="v">${esc(o.storeName || '—')}</span></div>
          <div class="or-row"><span class="k">取餐</span><span class="v">${esc(o.takeWay || '—')}</span></div>
          ${o.paid && o.pickupCode ? `<div class="or-row"><span class="k">取餐码</span>
            <span class="v" style="font-family:var(--serif);font-size:19px;color:var(--red)"><b>${esc(o.pickupCode)}</b></span></div>` : ''}
          ${rows}
          ${o.couponTitle ? `<div class="or-row"><span class="k">优惠券</span><span class="v" style="color:var(--red)">${esc(o.couponTitle)}</span></div>` : ''}
          <div class="or-row total"><span class="k">应付</span><span class="v">${money(o.total || 0)}</span></div>
          <span class="or-status">已下单 · ${o.paid ? '已支付' : '待支付'}${o.time ? ' · ' + esc(o.time) : ''}</span>
          ${exp && !o.paid ? `<div class="or-row" style="margin-top:4px"><span class="k">支付剩余</span>
            <span class="v or-cd" data-exp="${exp.getTime()}">—</span></div>` : ''}
          ${o.jump && !o.paid ? `<div class="note" style="margin:8px 0 2px">点「去支付」会打开麦当劳官方中转页，
            再点一下黄色按钮就唤起 App 收银台，不用重新选商品。</div>` : ''}
          <div class="or-btns">
            ${o.jump && !o.paid ? `<a class="btn btn-primary" href="${esc(o.jump)}" target="_blank" rel="noopener">去支付 ${money(o.total || 0)}</a>` : ''}
            ${o.h5 && !o.paid ? `<button class="btn btn-ghost js-orQr">扫码付</button>` : ''}
            ${o.orderId ? `<button class="btn btn-ghost js-orStatus">查状态</button>` : ''}
            <button class="btn btn-ghost js-orClear">划掉这张</button>
          </div>
        </div>
      </div>`;

      // 倒数到支付截止
      const cd = host.querySelector('.or-cd');
      if (cd) {
        const tick = () => {
          const left = Math.floor((Number(cd.dataset.exp) - Date.now()) / 1000);
          if (left <= 0) { cd.textContent = '已超时'; clearInterval(cd._h); return; }
          cd.textContent = `${Math.floor(left / 60)}:${String(left % 60).padStart(2, '0')}`;
        };
        tick(); cd._h = setInterval(tick, 1000);
      }
      const st = host.querySelector('.js-orStatus');
      if (st) st.onclick = () => checkStatus(o.orderId);
      const qr = host.querySelector('.js-orQr');
      if (qr) qr.onclick = () => showQr(o.h5, o.orderId);
      host.querySelector('.js-orClear').onclick = () => {
        try { localStorage.removeItem('mcd-order-latest'); } catch (e) { }
        renderOrderReceipt();
      };
    });
  }

  /* 回到页面时自动核对上一单：付过了就直接盖章「已付」，不用手动点查状态 */
  let orderSyncing = false;
  async function syncOrderSilent() {
    const rec = orderRecGet();
    if (!rec || rec.paid || !rec.orderId || orderSyncing) return;
    if (rec.expireAt && new Date(String(rec.expireAt).replace(/-/g, '/')) < new Date()) return;
    orderSyncing = true;
    try {
      const r = await api('/api/status?orderId=' + encodeURIComponent(rec.orderId));
      const d = r.data || {};
      const paid = /已支付|制作中|待取餐|已完成|已取餐|配送中|已送达/.test(String(d.orderStatus || ''));
      const canceled = /已取消|已退款/.test(String(d.orderStatus || ''));
      if (canceled) {
        orderRecSet({ ...rec, canceled: true });
      } else if (paid) {
        markAte({ time: rec.time || new Date().toTimeString().slice(0, 5), orderId: rec.orderId,
                  pickupCode: d.pickupCode || '', store: d.storeName || rec.storeName });
        orderRecSet({ ...rec, paid: true, pickupCode: d.pickupCode || rec.pickupCode || '' });
        toast('上一单付好了，小票已盖章「已付」');
      }
    } catch (e) { /* 静默失败，不打扰 */ }
    orderSyncing = false;
  }

  function openMenu() {
    const all = D.menu || [];
    if (!all.length) { toast('本店菜单暂不可用'); return; }
    let filter = 'all';

    const find = c => all.find(x => x.code === c);
    const basketItems = () => Object.keys(state.basket).map(c => ({ ...find(c), qty: state.basket[c] }))
      .filter(x => x.code);
    const basketTotal = () => basketItems().reduce((s, i) => s + i.price * i.qty, 0);
    const basketCount = () => basketItems().reduce((s, i) => s + i.qty, 0);

    const rowHTML = it => {
      const q = state.basket[it.code] || 0;
      return `<div class="mt-item${q ? ' on' : ''}" data-code="${esc(it.code)}">
        <div class="mt-names">
          <div class="mt-name">${esc(it.name)}
            ${(it.tags || []).map(t => `<span class="tagline">${esc(t)}</span>`).join('')}</div>
          <div class="mt-meta">${esc(it.group || it.cat_name)}</div>
        </div>
        <div class="mt-act">
          <span class="mt-price">${money(it.price)}</span>
          ${q
            ? `<div class="stepper"><button data-m="-1">−</button><b>${q}</b><button data-m="1">+</button></div>`
            : `<button class="add" data-m="1" aria-label="加入">＋</button>`}
        </div>
      </div>`;
    };

    const show = list => list.map(rowHTML).join('') ||
      `<div class="note" style="padding:18px 2px">这一类里没有商品。</div>`;

    function paint() {
      const list = filter === 'all'
        ? all
        : (filter === 'limited' ? all.filter(x => x.limited) : all.filter(x => x.cat === filter));
      const chips = MENU_FILTERS.map(([k, label]) => {
        const n = k === 'all' ? all.length
          : (k === 'limited' ? all.filter(x => x.limited).length : all.filter(x => x.cat === k).length);
        return `<button class="mf${filter === k ? ' on' : ''}" data-f="${k}">${label}<i>${n}</i></button>`;
      }).join('');

      $('#menuBody').innerHTML = `
        <div class="note" style="margin-top:0">本店实时菜单 ${all.length} 款，限定/上新直接排在菜单最前面。
        标价是菜单价，真正付款前会由 calculate-price 再核一次。</div>
        <div class="mf-bar">${chips}</div>
        <div class="mt-list">${show(list)}</div>`;

      const n = basketCount();
      $('#menuFoot').innerHTML = n
        ? `<div class="basket-bar">
             <div><b>${n} 件</b><span>菜单价 ${money(basketTotal())}</span></div>
             <button class="btn btn-primary" id="basketGo">就点这些</button>
           </div>`
        : `<button class="btn btn-ghost btn-block" id="menuClose">先看看，不下单</button>`;

      $$('#menuBody .mf').forEach(b => b.onclick = () => { filter = b.dataset.f; paint(); });
      $$('#menuBody .mt-item').forEach(row => {
        row.onclick = ev => {
          const btn = ev.target.closest('[data-m]');
          if (!btn) return;
          const code = row.dataset.code;
          const d = Number(btn.dataset.m);
          const next = Math.max(0, (state.basket[code] || 0) + d);
          if (next) state.basket[code] = next; else delete state.basket[code];
          paint();
        };
      });
      const go = $('#basketGo');
      if (go) go.onclick = () => {
        const items = basketItems();
        const o = orderParams(items.map(i => ({ code: i.code, name: i.name, price: i.price, cat: i.cat, qty: i.qty })),
          basketTotal(), '自选');
        if (!o) { toast('当前取餐方式下这单没法下'); return; }
        $('#modal').classList.remove('on');
        openOrder(o);
      };
      const cl = $('#menuClose');
      if (cl) cl.onclick = () => $('#modal').classList.remove('on');
    }

    showSheet('本店菜单', `<div id="menuBody"></div>`, `<div id="menuFoot"></div>`);
    // showSheet 的 foot 是独立容器，这里把两段都接管
    paint();
  }

  /* ── 换餐厅：自动定位后先替你选最近的，不满意再换 ──── */
  function openStores() {
    const s = D.stores || { pickup: [], delivery: [] };
    const pk = s.pickup || [], dv = s.delivery || [];
    state.storeKind = state.storeKind || 'pickup';

    const fmtDist = d => (d == null ? '' : (d >= 1000 ? `${(d / 1000).toFixed(1)}km` : `${d}m`));

    function rows(kind) {
      const list = kind === 'pickup' ? pk : dv;
      const chosen = (s.chosen || {})[kind];
      if (!list.length) {
        return `<div class="note">${kind === 'delivery'
          ? (D.meta.address_id ? '这个地址暂时查不到麦乐送门店。' : '还没有存过外送地址，先定位或存一个地址才有麦乐送。')
          : '附近没查到营业中的门店。'}</div>`;
      }
      return list.map((x, i) => `<button class="st-row${x.code === chosen ? ' on' : ''}" data-code="${esc(x.code)}" data-kind="${kind}">
        <span class="st-rank">${i === 0 ? '最近' : i + 1}</span>
        <span class="st-main">
          <span class="st-name">${esc(x.name)}</span>
          <span class="st-sub">${esc(x.address || '')}</span>
          <span class="st-meta">${fmtDist(x.distance)}${x.open ? ' · 营业 ' + esc(x.open) : ''}${x.code === chosen ? ' · 现在就这家' : ''}</span>
        </span>
        <span class="st-go">${x.code === chosen ? '✓' : ''}</span>
      </button>`).join('');
    }

    function paint() {
      const kind = state.storeKind;
      $('#stBody').innerHTML = `
        <div class="note" style="margin-top:0">定位到 <b>${esc(D.meta.place)}</b>（${esc(D.meta.loc_source)}），
        已经按距离替你排好序、选中最近那家。想换随时换 —— 换店会重新拉这家的菜单、券和价。</div>
        <div class="seg" id="stSeg">
          <button class="${kind === 'pickup' ? 'on' : ''}" data-k="pickup">到店 · 堂食/自取 <i>${pk.length}</i></button>
          <button class="${kind === 'delivery' ? 'on' : ''}" data-k="delivery">麦乐送 <i>${dv.length}</i></button>
        </div>
        <div class="mt-list" style="margin-top:10px">${rows(kind)}</div>
        ${kind === 'pickup' ? `<div class="note">堂食还是外带，会在确认下单那一步让你点头。</div>` : ''}`;

      $$('#stSeg button').forEach(b => b.onclick = () => { state.storeKind = b.dataset.k; paint(); });
      $$('#stBody .st-row').forEach(b => b.onclick = () => switchStore(b.dataset.code, b.dataset.kind));
    }

    showSheet('选择餐厅', `<div id="stBody"></div>`, '');
    paint();
  }

  async function switchStore(code, kind) {
    if (!code) return;
    if (!ONLINE) { toast('本地打开时不能换店（要连服务端）'); return; }
    showSheet('正在换店', `<div class="note">重新拉这家店的菜单、限定、券，再核一遍价…大概几秒。</div>`, '');
    let r;
    try { r = await api('/api/store', { storeCode: code, kind }); }
    catch (e) { showSheet('换店失败', `<div class="note">${esc(e.message)}</div>`, ''); return; }
    if (!r.ok) {
      showSheet('没换成', `<div class="note">${esc(r.message || '这家店当前不可用')}</div>
        <div class="note">还留在原来那家，价格没变。</div>`, '');
      return;
    }
    applyData(r.data);
    const got = kind === 'pickup' ? (r.data.store.pickup || {}).name : (r.data.store.delivery || {}).name;
    showSheet('换好了', `
      <div class="kv"><span class="k">现在的店</span><span class="v">${esc(got || '')}</span></div>
      <div class="kv"><span class="k">菜单</span><span class="v">${(r.data.menu || []).length} 款</span></div>
      <div class="kv"><span class="k">限定</span><span class="v">${(r.data.limited || []).length} 款</span></div>`,
      `<button class="btn btn-primary" id="okStore">看这一家</button>`);
    $('#okStore').onclick = () => $('#modal').classList.remove('on');
  }

  /* ── 小票 ─────────────────────────────────────────── */
  function receiptData(p) {
    p = p || effectivePlan();
    const a = D.almanac, w = D.weather;
    const d = parse(D.meta.today);
    const self = basketMode();
    const idx = self ? 0 : D.plans.indexOf(p) + 1;
    const wi = w ? `${w.desc} ${w.temp}°` : '数据暂不可用';
    return {
      plan: p,
      weather: w,
      scene: sceneKey(),
      ate: ateGet(),
      dateText: `${d.getFullYear()}.${String(d.getMonth() + 1).padStart(2, '0')}.${String(d.getDate()).padStart(2, '0')} 周${WD[d.getDay()]}`,
      ticketNo: `${String(d.getMonth() + 1).padStart(2, '0')}${String(d.getDate()).padStart(2, '0')}-${String(idx).padStart(2, '0')}${self ? 'S' : ''}`,
      weatherText: wi,
      meatText: p && p.items && p.items.length ? (MEAT[p.items[0].cat] || '—') : '—',
      modeText: D.logistics.label,
      yiText: D.yiji.yi.join(' · '),
      jiText: D.yiji.ji.join(' · '),
      sign: D.sign,
      payNote: self
        ? '自己挑的一篮 · 菜单快照价，下单前再核'
        : p && p.verified
          ? '金额由麦当劳 calculate-price 实时核出 · 未下单'
          : '价格暂未核验，以下为菜单快照价',
      storeText: D.store.pickup
        ? `${D.store.pickup.name} · ${D.store.pickup.distance != null ? D.store.pickup.distance + 'm' : ''}`
        : '门店数据暂不可用'
    };
  }

  function renderReceipt() {
    const host = $('#receiptHost');
    if (!host) return;
    const p = effectivePlan();
    if (!p || !p.items || !p.items.length) {
      host.innerHTML = `<div class="card" style="text-align:center;padding:34px 20px">
        <div style="font-family:var(--serif);font-size:17px;color:var(--red)">小票暂不可用</div>
        <div class="note" style="margin-top:8px">${(D.warnings || []).join('；') || '本店菜单未取到'}<br>
        不作演示数据兜底。</div></div>`;
      return;
    }
    host.innerHTML = RECEIPT.build(receiptData(p));
  }

  /* ── 优惠 ─────────────────────────────────────────── */
  function openCoupons() {
    const c = D.coupons;
    const row = (x, cls, badge) => `<div class="coupon-item ${cls}">
      <div class="t">${esc(x.title)}<span class="badge">${badge}</span></div>
      <div class="s">${esc(x.reason || '')}${x.toast ? ' · ' + esc(x.toast) : ''}</div></div>`;

    const body = `
      <div class="kv"><span class="k">卡包</span><span class="v">${c.wallet_total} 张</span></div>
      <div class="kv"><span class="k">本店可用</span><span class="v">${c.store_usable_count} 张</span></div>
      <div class="kv"><span class="k">今日可用</span><span class="v">${c.usable.length} 张</span></div>
      ${c.claimable && c.claimable.length ? `<div class="kv"><span class="k">可领取（麦麦省）</span><span class="v">${c.claimable.length} 张</span></div>` : ''}
      <div style="height:12px"></div>
      ${c.usable.map(x => row(x, 'ok', '今日可用')).join('')}
      ${c.upcoming.map(x => row(x, 'wait', '稍后生效')).join('')}
      ${!c.usable.length && !c.upcoming.length ? `<div class="note">卡包里暂时没有能用的券。</div>` : ''}
      ${c.claimable && c.claimable.length ? `<div style="margin-top:14px">
        <div class="note" style="margin-bottom:8px">麦麦省可领：${c.claimable.map(x => esc(x)).join('、')}</div>
        <div class="note">领取会一次领走全部可领券（官方 auto-bind-coupons 的行为），需要你在对话里确认；
        本页不会自动领。</div></div>` : ''}
      ${(c.notes || []).map(n => `<div class="note">· ${esc(n)}</div>`).join('')}
      <div class="note" style="margin-top:12px">所有省下的钱都由 calculate-price 带券前后各核一次价得出，
      核价不降价就不写省了钱。</div>`;
    showSheet('优惠明细', body, '');
  }

  /* ── 撕日历：一进页面只有这一张纸，撕开才给今天 ────── */
  const tear = {
    t: 0, maxDy: 0, W: 0, H: 0, jag: [], active: false, done: false, el: {},

    init() {
      this.el.box = $('#paperBox');
      this.el.stub = $('#sheetStub');
      this.el.piece = $('#sheetPiece');
      this.el.hint = $('#tearHint');
      this.el.auto = $('#tearAuto');
      this.el.rvSub = $('#rvSub');
      this.paint();
      this.measure();
      this.bind();
      window.addEventListener('resize', () => {
        if (!this.done) { this.measure(); this.draw(this.t); }
      });
    },

    /* 残留条和被撕走的整页必须是同一份内容，撕开的锯齿才对得上 */
    paint() {
      const html = faceHTML();
      this.el.stub.innerHTML = html;
      this.el.piece.innerHTML = html;
      const a = D.almanac;
      if (this.el.rvSub) {
        const unluck = D.yiji && D.yiji.luck === '凶';
        this.el.rvSub.textContent = unluck
          ? '凶日也大吉 · 吃了麦当劳就转运'
          : `农历${(a.lunar || '').replace(/^.*?年/, '')} · 值日「${a.zhixing}」`;
      }
    },

    measure() {
      this.W = this.el.box.clientWidth || 320;
      this.H = this.el.box.clientHeight || 440;
      this.maxDy = Math.max(160, this.H * 0.88);
      // 撕口锯齿：一次撕只随机一次，拖动过程中不能抖
      const N = 36, DEPTH = 16 + Math.random() * 8;
      this.jag = [];
      for (let i = 0; i <= N; i++) {
        const edge = (i === 0 || i === N) ? 0.25 : 1;
        this.jag.push(3 + (i % 2 ? 1 : 0.45) * Math.random() * DEPTH * edge);
      }
      // 装订残留：撕完后上缘留一条锯齿纸边
      const pts = [[0, 0]];
      for (let i = 0; i <= N; i++) pts.push([(this.W * i) / N, this.jag[i]]);
      pts.push([this.W, 0]);
      this.el.stub.style.clipPath =
        `polygon(${pts.map(p => `${p[0].toFixed(1)}px ${p[1].toFixed(1)}px`).join(',')})`;
    },

    /* 拖动：上端还咬在装订口，纸身跟着手往下坠、歪斜越来越狠 */
    draw(t) {
      this.t = Math.max(0, Math.min(1, t));
      const dy = this.t * this.maxDy;
      this.el.piece.style.transform =
        `translateY(${(dy * 0.24).toFixed(1)}px) rotate(${(this.t * 7).toFixed(2)}deg) skewX(${(-this.t * 2.2).toFixed(2)}deg)`;
    },

    bind() {
      const box = this.el.box;
      let startY = 0, base = 0;

      const down = e => {
        if (this.done) return;
        this.active = true;
        box.classList.add('dragging');
        startY = e.clientY;
        base = this.t * this.maxDy;
        try { box.setPointerCapture(e.pointerId); } catch (err) { }
        if (e.cancelable) e.preventDefault();
      };
      const move = e => {
        if (!this.active || this.done) return;
        const dy = Math.max(0, Math.min(this.maxDy, base + (e.clientY - startY)));
        this.draw(dy / this.maxDy);
        if (dy > 8 && this.el.hint) this.el.hint.style.opacity = '0';
        if (e.cancelable) e.preventDefault();
      };
      const up = () => {
        if (!this.active) return;
        this.active = false;
        box.classList.remove('dragging');
        if (this.done) return;
        if (this.t >= 0.42) this.finish();
        else this.springBack();
      };

      box.addEventListener('pointerdown', down);
      box.addEventListener('pointermove', move);
      box.addEventListener('pointerup', up);
      box.addEventListener('pointercancel', up);

      // 不想拖也行：点一下按钮，自动撕给你看
      this.el.auto.onclick = () => { if (!this.done) this.autoTear(); };
    },

    springBack() {
      const from = this.t, t0 = performance.now(), dur = 260;
      const step = now => {
        const k = Math.min(1, (now - t0) / dur);
        const e = 1 - Math.pow(1 - k, 3);
        this.draw(from * (1 - e));
        if (k < 1) requestAnimationFrame(step);
        else { this.draw(0); if (this.el.hint) this.el.hint.style.opacity = ''; }
      };
      requestAnimationFrame(step);
    },

    autoTear() {
      if (this.done) return;
      const t0 = performance.now(), dur = 760;
      const step = now => {
        const k = Math.min(1, (now - t0) / dur);
        const e = k < 0.5 ? 2 * k * k : 1 - Math.pow(-2 * k + 2, 2) / 2;
        this.draw(e);
        if (k < 1) requestAnimationFrame(step);
        else this.finish();
      };
      requestAnimationFrame(step);
    },

    finish() {
      if (this.done || this._finishing) return;
      this._finishing = true;
      this.done = true;
      this.el.box.classList.remove('dragging');
      if (this.el.hint) this.el.hint.style.opacity = '0';

      // 撕脱：锯齿撕口成形（残留条与页面两片严丝合缝），整页脱开坠走
      const N = this.jag.length - 1;
      const top = [];
      for (let i = 0; i <= N; i++) top.push([(this.W * i) / N, this.jag[i]]);
      this.el.piece.style.transform = '';
      this.el.piece.style.clipPath =
        `polygon(${top.concat([[this.W, this.H], [0, this.H]])
          .map(p => `${p[0].toFixed(1)}px ${p[1].toFixed(1)}px`).join(',')})`;
      this.el.piece.classList.add('gone');

      setTimeout(() => this.shred(), 120);
      setTimeout(() => {
        renderToday();
        go('today');
        this.el.box.style.pointerEvents = 'none';
      }, 820);
    },

    /* 纸屑：从撕口（顶部锯齿线）崩出来，纯装饰 */
    shred() {
      const r = this.el.box.getBoundingClientRect();
      for (let i = 0; i < 16; i++) {
        const b = document.createElement('i');
        b.className = 'shred';
        const w = 4 + Math.random() * 7, h = 3 + Math.random() * 6;
        b.style.cssText = `left:${r.left + Math.random() * r.width}px;`
          + `top:${r.top + Math.random() * 26}px;`
          + `width:${w}px;height:${h}px;border-radius:1px;`
          + `--dx:${(Math.random() - 0.5) * 160}px;--dy:${60 + Math.random() * 180}px;`
          + `--rot:${(Math.random() - 0.5) * 560}deg;`
          + `animation-delay:${Math.random() * 0.16}s`;
        document.body.appendChild(b);
        setTimeout(() => b.remove(), 1500);
      }
    },

    rearm() {
      this._finishing = false;
      this.done = false;
      this.t = 0;
      this.el.box.style.pointerEvents = '';
      this.el.piece.classList.remove('gone');
      this.el.piece.style.clipPath = '';
      this.el.piece.style.transform = '';
      this.el.piece.style.opacity = '';
      if (this.el.hint) this.el.hint.style.opacity = '';
      this.measure();
      this.draw(0);
    }
  };

  function faceHTML() {
    const a = D.almanac, d = parse(D.meta.today);
    const unluck = D.yiji && D.yiji.luck === '凶';
    const yi = (D.yiji.yi || []).slice(0, 4).join(' · ') || '诸事皆宜';
    const ji = (D.yiji.ji || []).slice(0, 4).join(' · ') || '无忌';
    const lunar = (a.lunar || '').replace(/^.*?年/, '');
    const doy = Math.floor((d - new Date(d.getFullYear(), 0, 0)) / 864e5);
    return `<div class="face">
      <div class="f-brand"><b><span class="fb-arch">${ART.svg.archMini()}</span>麦麦黄道吉日</b><i>第 ${doy} 天</i></div>
      <div class="f-year">${d.getFullYear()}</div>
      <div class="f-month">${d.getMonth() + 1} 月 · ${esc(a.zhixing)}日值</div>
      <div class="f-dayrow">
        <div class="f-day">${d.getDate()}</div>
        <span class="f-daydeco" aria-hidden="true">${ART.svg.dayDeco()}</span>
        <div class="f-week">周${WD[d.getDay()]}<small>${esc(a.xiu || '')}</small></div>
      </div>
      <div class="f-mark">吉</div>
      <div class="f-lunar">农历${esc(lunar)}</div>
      <div class="f-gz">${esc(a.day_gz)}日 · ${esc(a.nayin)} · 值日「${esc(a.zhixing)}」</div>
      <div class="f-meta">
        <span>${esc(a.xiu || '—')}</span>
        <span>喜神 ${esc(a.xi_position || '—')}</span>
        <span>幸运色 ${esc(a.lucky_color || '—')}</span>
      </div>
      <div class="f-seal${unluck ? ' two' : ''}" aria-hidden="true">
        <span class="fs-arch">${ART.svg.archTiny()}</span>
        <b>${unluck ? '转运' : '吉'}</b>
        <i>今日宜吃麦</i>
      </div>
      <div class="f-doodle" aria-hidden="true">${ART.svg.doodle()}</div>
      <div class="f-yj">
        <div class="ln"><span class="k yi">宜</span><span class="v">${esc(yi)}</span></div>
        <div class="ln"><span class="k ji">忌</span><span class="v">${esc(ji)}</span></div>
      </div>
      <div class="f-guide"><span class="sc">✂</span><span>${unluck ? '凶日不慌 · 撕了这页吃麦当劳转运' : '按住纸的下沿 · 往下撕'}</span><span class="sc">✂</span></div>
    </div>`;
  }

  /* ── 下单 ─────────────────────────────────────────── */
  /* items 不传就用推荐的这套方案；传了就是菜单里自己挑的一篮 */
  function orderParams(items, total, tag) {
    const p = plan();
    let mode = D.logistics.mode === 'delivery' ? 'delivery' : 'pickup';
    let list = items || (p ? p.items : null);
    if (!list || !list.length) return null;

    // 外送门店和到店门店的 SKU 不通用：没有同名映射就只能自取
    if (mode === 'delivery' && p && !items && !p.delivery_items) mode = 'pickup';

    const st = mode === 'delivery' ? D.store.delivery : D.store.pickup;
    if (!st) return null;

    if (mode === 'delivery' && p && !items) list = p.delivery_items;

    return {
      mode,
      tag: tag || (p ? p.tag : ''),
      storeCode: st.code,
      storeName: st.name,
      orderType: mode === 'delivery' ? 2 : 1,
      beType: mode === 'delivery' ? 2 : 1,
      beCode: mode === 'delivery' ? st.beCode : '',
      addressId: mode === 'delivery' ? (D.meta.address_id || '') : '',
      takeWayCode: state.takeWay || '',
      items: list.map(i => ({ productCode: i.code, quantity: i.qty || 1 })),
      names: list.map(i => i.name),
      // 自选篮也先猜推荐套餐那张券去核价：满减类券能不能用由 calculate-price 说了算，
      // 核不出来确认页上就看不到优惠，不会虚报。
      coupon: (p && p.coupon) || null,
      total: total != null ? total : (p ? p.total : 0)
    };
  }

  function commandText(o) {
    const items = o.items.map(i => `${i.productCode}:${i.quantity}`).join(',');
    const lines = [
      `python3 scripts/order.py quote --store-code ${o.storeCode} --order-type ${o.orderType} --be-type ${o.beType}`
      + (o.beCode ? ` --be-code ${o.beCode}` : '')
      + (o.addressId ? ` --address-id ${o.addressId}` : '')
      + ` --items ${items}`
      + (o.coupon ? ` --coupon-id ${o.coupon.id} --coupon-code ${o.coupon.code || ''}` : '')
    ];
    return lines.join(' ');
  }

  /* 确认页必须先核一次真实价：确认页上写的数，就是建单会用的数 */
  async function openOrder(o) {
    o = o || orderParams();
    if (!o) { toast('还没有可下单的套餐'); return; }
    state.order = o;

    showSheet('正在核价', `<div class="note">把这一单交给麦当劳 calculate-price 算实付，
      顺便看看门店现在给哪些取餐方式…</div>`, '');

    let q = null;
    if (ONLINE) {
      try { q = await api('/api/quote', o); } catch (e) { q = null; }
    }

    const live = q && q.ok;
    const totalFen = live ? q.total : Math.round((o.total || 0) * 100);
    state.quote = live ? q : null;

    const rows = o.items.map((it, i) =>
      `<div class="kv"><span class="k">${esc(o.names[i])}</span><span class="v">×${it.quantity}</span></div>`).join('');
    const feeRows = live && (q.delivery_fee || q.packing_fee)
      ? `${q.delivery_fee ? `<div class="kv"><span class="k">配送费</span><span class="v">${money(q.delivery_fee / 100)}</span></div>` : ''}
         ${q.packing_fee ? `<div class="kv"><span class="k">打包费</span><span class="v">${money(q.packing_fee / 100)}</span></div>` : ''}`
      : '';
    const discRow = live && q.discount
      ? `<div class="kv"><span class="k">优惠</span><span class="v">-${money(q.discount / 100)}</span></div>` : '';

    const note = live
      ? `金额由 calculate-price 刚刚核出。点「确认下单」会再核一次，一致才建单；
         建单后门店会在 <b>15 分钟</b>内等付款，超时自动取消。`
      : (ONLINE ? `核价失败：${esc((q && q.message) || '未知原因')}。可以照菜单价先下，服务端会重算。`
        : `当前离线打开，页面不能直接调麦当劳接口（也不能把 Token 放进网页）。
           点「确认下单」会给你一条本机指令，回到对话里说一声就行。`);

    // 取餐方式：堂食 / 外带 由 calculate-price 的 takeWayList 说了算，不硬编码
    const ways = (live && o.orderType === 1 && (q.take_way || []).length) ? q.take_way : [];
    const picked = state.takeWay || (ways[0] ? ways[0].code : '');
    const waySeg = ways.length
      ? `<div class="seg" id="waySeg">${ways.map(w => `<button data-w="${esc(w.code)}"
           class="${w.code === picked ? 'on' : ''}">${esc(w.title || w.code)}</button>`).join('')}</div>`
      : (o.orderType === 1 ? `<div class="note">这家店没返回取餐方式（takeWayList 为空），下单会被拒。</div>`
        : `<div class="note">麦乐送：送到 ${esc(D.meta.address || '已存地址')}</div>`);

    showSheet('确认下单', `
      <div class="kv"><span class="k">餐厅</span><span class="v">${esc(o.storeName)}
        ${o.storeCode ? `<button class="linkbtn" id="chgStore">换一家</button>` : ''}</span></div>
      ${waySeg}
      <div style="height:8px"></div>
      ${rows}${feeRows}${discRow}
      ${o.coupon ? `<div class="kv"><span class="k">优惠券</span><span class="v">${esc(o.coupon.title)}</span></div>` : ''}
      <div class="kv total"><span class="k">应付</span><span class="v">${money(totalFen / 100)}</span></div>
      <div class="note" style="margin-top:12px">${note}</div>
      ${live && q.original && q.original > q.total
        ? `<div class="note">原价 ${money(q.original / 100)}，省 ${money((q.original - q.total) / 100)}</div>` : ''}
      ${ONLINE ? '' : `<div class="cmd" style="margin-top:10px">${esc(commandText(o))}</div>`}`,
      `${ONLINE ? '' : '<button class="btn btn-ghost" id="copyCmd">复制作业指令</button>'}
       <button class="btn btn-primary" id="doOrder">确认下单</button>`);

    const cc = $('#copyCmd');
    if (cc) cc.onclick = () => copy(commandText(o));
    const cs = $('#chgStore');
    if (cs) cs.onclick = () => { $('#modal').classList.remove('on'); openStores(); };
    $$('#waySeg button').forEach(b => b.onclick = () => {
      state.takeWay = b.dataset.w;
      o.takeWayCode = b.dataset.w;
      $$('#waySeg button').forEach(x => x.classList.toggle('on', x === b));
    });
    if (ways.length && !state.takeWay) state.takeWay = ways[0].code;
    $('#doOrder').onclick = () => submitOrder(totalFen);
  }

  async function submitOrder(totalFen, acceptChange) {
    const o = state.order;
    if (!o) return;

    if (!ONLINE) {
      copy(commandText(o));
      showSheet('已复制作业指令', `
        <div class="note">此页面是本地文件打开的，前端不能直接调麦当劳接口，也不该把 Token 放进网页。
        指令已复制，回到对话里说「确认下单」，我这边会真实建单并把支付链接给你。</div>
        <div class="cmd" style="margin-top:10px">${esc(commandText(o))}</div>`, '');
      return;
    }

    showSheet('正在下单', `<div class="note">重算价 → 创建订单 → 取支付入口…</div>`, '');
    let r;
    try {
      r = await api('/api/order', {
        ...o,
        total: (totalFen || 0) / 100,
        acceptChange: !!acceptChange,
        confirm: true
      });
    } catch (e) {
      showSheet('网络断了', `<div class="note">${esc(e.message)}<br>
        结果不确定的时候不要重复点，先用订单号查一下状态。</div>`, '');
      return;
    }

    if (r.stage === 'price-changed') {
      showSheet('价格变了', `
        <div class="note">核价从 <b>${money((r.before || 0) / 100)}</b> 变成了
          <b>${money((r.after || 0) / 100)}</b>，我没有提交。
          多办是券换了时段、或者门店调价。</div>
        <div class="note">接受新价就点下面这个按钮，我再下一单。</div>`,
        `<button class="btn btn-primary" id="acceptPrice">按 ${money((r.after || 0) / 100)} 下单</button>`);
      $('#acceptPrice').onclick = () => submitOrder(r.after, true);
      return;
    }

    if (!r.ok) {
      showSheet('没下成', `
        <div class="note">${esc(r.message || '接口返回失败')}</div>
        ${r.timeout ? `<div class="note">⚠ 超时：结果不确定，先去麦当劳 App「我的订单」看看有没有这笔，
          别急着重下。</div>` : ''}
        <div class="cmd" style="margin-top:10px">${esc(JSON.stringify(r.detail || {}, null, 1).slice(0, 700))}</div>`,
        `<button class="btn btn-ghost" id="retryOrder">再试一次</button>`);
      const rb = $('#retryOrder');
      if (rb) rb.onclick = () => submitOrder(totalFen, acceptChange);
      return;
    }

    orderCreated(r, o);
  }

  /* 建单成功：不弹窗，直接带去出票页 —— 打印机现打小票，
     支付入口 / 倒计时 / 取餐码 / 取消都跟在订单小票上
     —— payH5Url 只是个二维码页，真正一点就到收银台的是 /mcp/jumpToApp?orderId= */
  function orderCreated(r, o) {
    const od = r.order || {};
    const pay = r.pay || {};
    const jump = pay.jump || r.appUrl || '';
    const deep = pay.deep || r.deepLink || '';
    const h5 = pay.h5 || r.payUrl || '';

    orderRecSet({
      orderId: r.orderId || '',
      storeName: od.storeName || o.storeName || '',
      takeWay: od.takeWay || D.logistics.label || '',
      items: o.items.map((it, i) => ({ name: (o.names || [])[i] || it.productCode, qty: it.quantity || 1 })),
      couponTitle: o.coupon ? o.coupon.title : '',
      total: (r.total || 0) / 100,
      expireAt: r.expire_at || '',
      jump: jump || '', deep: deep || '', h5: h5 || '',
      paid: false,
      time: new Date().toTimeString().slice(0, 5)
    });

    $('#modal').classList.remove('on');
    goReceipt(true);          // 出票机开工：滋滋滋打出这张小票
  }

  /* 二维码：官方 payH5Url 本身就是「扫码进入麦当劳APP支付」的页面 */
  function showQr(url, orderId) {
    showSheet('扫码付款', `
      <div class="qr-wrap"><iframe class="qr-frame" src="${esc(url)}" title="麦当劳付款二维码"></iframe></div>
      <div class="note" style="text-align:center">用<b>另一台设备</b>上的麦当劳 App 或微信扫这个码。
        同一台手机扫不了自己的屏 —— 那就用上面那个「去麦当劳 App 付款」按钮。</div>
      <div class="cmd" style="margin-top:10px">${esc(url)}</div>
      <div class="note">订单号 ${esc(orderId || '')}</div>`, '');
  }

  async function cancelOrder(orderId) {
    if (!orderId) return;
    showSheet('取消这单？', `<div class="note">会调 cancel-order 真的取消这笔订单，不可撤销。</div>`,
      `<button class="btn btn-ghost" id="noCancel">算了</button>
       <button class="btn btn-primary" id="yesCancel">确认取消</button>`);
    $('#noCancel').onclick = () => $('#modal').classList.remove('on');
    $('#yesCancel').onclick = async () => {
      showSheet('正在取消', `<div class="note">…</div>`, '');
      try {
        const r = await api('/api/cancel', { orderId, reason: '1', confirm: true });
        showSheet(r.ok ? '已取消' : '没取消成',
          `<div class="note">${esc(r.message || (r.ok ? '订单已取消' : '接口返回失败'))}</div>`, '');
      } catch (e) {
        showSheet('网络断了', `<div class="note">${esc(e.message)}</div>`, '');
      }
    };
  }

  async function checkStatus(orderId) {
    if (!orderId) return;
    showSheet('正在查状态', `<div class="note">…</div>`, '');
    let r;
    try { r = await api('/api/status?orderId=' + encodeURIComponent(orderId)); }
    catch (e) { showSheet('网络断了', `<div class="note">${esc(e.message)}</div>`, ''); return; }
    const d = r.data || {};
    if (!r.ok && !d.orderStatus) {
      showSheet('查不到', `<div class="note">${esc(r.message || '接口返回失败')}</div>`, '');
      return;
    }
    // 付款成功的几个状态：见了就盖章「今日已吃」，不用等吃完
    const paid = /已支付|制作中|待取餐|已完成|已取餐|配送中|已送达/.test(String(d.orderStatus || ''));
    if (paid) {
      markAte({ time: new Date().toTimeString().slice(0, 5), orderId,
                pickupCode: d.pickupCode || '', store: d.storeName || (D.store.pickup || {}).name });
      // 订单小票同步盖章
      const rec = orderRecGet();
      if (rec && rec.orderId === orderId && !rec.paid) {
        rec.paid = true;
        rec.pickupCode = d.pickupCode || '';
        orderRecSet(rec);
      }
    }
    showSheet(paid ? '付好了 · 今日已吃' : '订单状态', `
      ${paid ? `<div class="ate-inline"><span class="ate-mini">已吃</span>
        这一顿记在 ${esc(fmtCN(D.meta.today))} 上了</div>` : ''}
      <div class="kv"><span class="k">状态</span><span class="v"><b>${esc(d.orderStatus || '—')}</b></span></div>
      ${d.pickupCode ? `<div class="kv"><span class="k">取餐码</span>
        <span class="v" style="font-family:var(--serif);font-size:22px;color:var(--red)">${esc(d.pickupCode)}</span></div>`
        : `<div class="note">还没有取餐码 —— 付款后才会出。</div>`}
      <div class="kv"><span class="k">餐厅</span><span class="v">${esc(d.storeName || '—')}</span></div>
      <div class="kv"><span class="k">取餐</span><span class="v">${esc(d.takeWay || '—')}</span></div>
      <div class="kv total"><span class="k">实付</span><span class="v">${money(d.realTotalAmount || d.totalAmount || 0)}</span></div>
      <div style="height:10px"></div>
      <div class="cmd">${esc(JSON.stringify(d, null, 1).slice(0, 900))}</div>`,
      `<button class="btn btn-ghost" id="reCheck">再查一次</button>`);
    const rc = $('#reCheck');
    if (rc) rc.onclick = () => checkStatus(orderId);
  }

  /* ── 弹层 ─────────────────────────────────────────── */
  function showSheet(title, body, foot) {
    const m = $('#modal');
    m.innerHTML = `<div class="sheet">
      <div class="sheet-head"><h3>${esc(title)}</h3>
        <button class="x" aria-label="关闭">✕</button></div>
      <div class="sheet-body">${body}</div>
      ${foot ? `<div class="sheet-foot">${foot}</div>` : ''}
    </div>`;
    m.classList.add('on');
    m.querySelector('.x').onclick = () => m.classList.remove('on');
    m.onclick = e => { if (e.target === m) m.classList.remove('on'); };
  }

  function copy(t) {
    const ta = document.createElement('textarea');
    ta.value = t;
    ta.style.cssText = 'position:fixed;left:-9999px';
    document.body.appendChild(ta); ta.select();
    try { document.execCommand('copy'); } catch (e) { }
    document.body.removeChild(ta);
    toast('已复制作业指令');
  }

  /* ── PNG 导出 ─────────────────────────────────────── */
  async function savePNG() {
    const svg = $('#receiptHost svg');
    if (!svg) { toast('还没有小票'); return; }
    const clone = svg.cloneNode(true);
    // 不要手动补 xmlns —— XMLSerializer 自己会加上，重复定义会让浏览器拒绝解析这张 SVG
    clone.setAttribute('width', svg.viewBox.baseVal.width);
    clone.setAttribute('height', svg.viewBox.baseVal.height);
    const src = new XMLSerializer().serializeToString(clone);
    const url = URL.createObjectURL(new Blob([src], { type: 'image/svg+xml;charset=utf-8' }));

    const img = new Image();
    const done = new Promise((res, rej) => { img.onload = res; img.onerror = rej; img.src = url; });
    try { await done; } catch (e) { toast('导出失败：浏览器拒绝了 SVG 渲染'); return; }

    const w = +(clone.getAttribute('width')) || 460;
    const h = +(clone.getAttribute('height')) || 900;
    const scale = 2.6;
    const cv = document.createElement('canvas');
    cv.width = Math.round(w * scale);
    cv.height = Math.round(h * scale);
    // 背景留透明：撕边在任何底色上都能看出来，也方便直接发出去
    const ctx = cv.getContext('2d');
    ctx.drawImage(img, 0, 0, cv.width, cv.height);

    cv.toBlob(b => {
      const a = document.createElement('a');
      a.href = URL.createObjectURL(b);
      a.download = `麦麦开运小票-${D.meta.today}.png`;
      a.click();
      setTimeout(() => URL.revokeObjectURL(a.href), 4000);
      toast('小票已保存');
    }, 'image/png');
    URL.revokeObjectURL(url);
  }

  /* ── 出票页：麦麦出票机现打小票 ───────────────────── */
  let printTimer = null;
  function goReceipt(animate) {
    renderReceipt();
    go('receipt');
    playPrint(animate !== false);
  }

  function playPrint(animate) {
    const stage = $('#prStage'), status = $('#prStatus');
    if (!stage) return;
    stage.classList.remove('printing');
    clearTimeout(printTimer);
    if (!animate) {
      status.textContent = orderRecGet() && !orderRecGet().canceled
        ? '这张小票已经是你的了 · 长按或点「保存小票」带走'
        : '还没下单 · 这台机器随时为你开工';
      return;
    }
    status.textContent = '正在打印今日好运…';
    void stage.offsetWidth;              // 强制重排，动画从头放
    stage.classList.add('printing');
    printTimer = setTimeout(() => {
      stage.classList.remove('printing');
      status.textContent = orderRecGet() && !orderRecGet().paid
        ? '打印完成 · 付完款回来盖「已付」章'
        : '打印完成 · 撕下来吧';
    }, 2700);
  }

  /* ── 启动 ─────────────────────────────────────────── */
  const ONLINE = location.protocol === 'http:' || location.protocol === 'https:';

  async function api(path, body) {
    const r = await fetch(path, {
      method: body ? 'POST' : 'GET',
      headers: { 'Content-Type': 'application/json' },
      body: body ? JSON.stringify(body) : undefined
    });
    return r.json();
  }

  function boot() {
    $('#locName').textContent = D.meta.place.replace(/^.*?(省|市)/, '') || D.meta.place;
    $('#locSrc').textContent = D.meta.loc_source;
    $('#genAt').textContent = D.meta.generated_at;

    // 麦麦品牌装饰：金拱门 / 薯条汉堡 hero / 标签拱门 / 撕纸按钮小件
    const put = (sel, html) => { const el = $(sel); if (el) el.innerHTML = html; };
    put('#archesIco', ART.svg.archBrand());
    put('#brandDeco', ART.svg.brandDeco());
    put('#heroDeco', ART.svg.hero());
    put('#taFries', ART.icon('fries'));
    put('#taPull', ART.svg.pull());
    put('#rvArch', ART.svg.archMini());
    put('#rvFood', ART.svg.revealFood());
    put('#bagSeal', `${ART.svg.archTiny()}<span>麦麦外卖封签 · 撕开有好运</span>${ART.svg.archTiny()}`);
    put('#stArch', ART.svg.archMini());
    put('#stYi', '宜');
    put('#reIco', ART.svg.miniTicket());
    put('#prArch', ART.svg.archMini());
    $$('#tearAuto .spark').forEach((el, i) => { el.innerHTML = ART.svg.spark(i); });

    const warn = warnHTML();

    $('#warnHost').innerHTML = warn;

    renderCalendar();
    renderSide(D.meta.today);
    renderToday();           // 先备好，撕完立刻就有内容
    renderAte();
    prefillBasket();         // 先帮玩家把推荐套餐配进篮子
    renderMenuCard();
    renderOrderReceipt();
    syncOrderSilent();       // 回到页面先核对上一单，付过了自动盖章
    tear.init();             // 一进页面只给一张纸
    const h = location.hash;
    if (/receipt/.test(h)) goReceipt(true);                        // #receipt 深链：直达出票页
    else go(/today/.test(h) ? 'today' : 'tear');                   // #today 深链：跳过撕日历

    $('#prevM').onclick = () => { state.cursor = new Date(state.cursor.getFullYear(), state.cursor.getMonth() - 1, 1); renderCalendar(); };
    $('#nextM').onclick = () => { state.cursor = new Date(state.cursor.getFullYear(), state.cursor.getMonth() + 1, 1); renderCalendar(); };
    $('#openToday').onclick = () => { state.sel = D.meta.today; state.cursor = null; renderCalendar(); tear.rearm(); go('tear'); };
    $('#backToday').onclick = () => { renderToday(); renderAte(); go('today'); };
    $('#backCal').onclick = () => { renderCalendar(); renderSide(state.sel); go('cal'); };
    $('#backMenu').onclick = () => go('today');
    $('#goReceipt').onclick = () => goReceipt(true);
    $('#planSwitch').onclick = () => {
      state.planIdx = (state.planIdx + 1) % Math.max(1, D.plans.length);
      if (!state.basketTouched) prefillBasket();   // 没动过篮子就跟新方案走
      renderMenuCard();
      renderReceipt();
      toast(`换了一份：${plan().tag}`);
    };
    $('#openCoupons').onclick = openCoupons;
    $('#savePng').onclick = savePNG;
    const mb = $('#openMenuBtn'); if (mb) mb.onclick = openMenu;
    const sb = $('#openStores'); if (sb) sb.onclick = openStores;
  }

  window.MCD = {
    today: () => { state.sel = D.meta.today; state.cursor = null; renderCalendar(); renderToday(); go('today'); },
    receipt: () => goReceipt(true)
  };

  if (document.readyState === 'loading') document.addEventListener('DOMContentLoaded', boot);
  else boot();
})();
