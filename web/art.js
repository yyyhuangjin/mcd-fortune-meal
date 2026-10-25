/* ── 麦麦黄道吉日 · 原创插画与小票 ──────────────────────────────
   插画全部用基础几何体手绘感拼出来：圆角汉堡、带表情薯条、
   雨伞/草帽/热饮/云、金拱门、鸡块蘸酱、红白饮料杯、外卖纸袋。
   颜色取麦当劳经典红黄，风格是简洁可爱的轻微手绘扁平插画。 */

const ART = (() => {
  const C = {
    bun: '#EFB871', bunDark: '#D9954B', bunTop: '#F7CB8C',
    patty: '#6E4526', cheese: '#F5B71E', lettuce: '#86B36B',
    red: '#C8102E', yellow: '#FFC72C', cream: '#FFF6E2',
    ink: '#3A2418', blush: '#F09A9A', cup: '#FBF6EC', steam: '#C9B49A',
    sun: '#FFC72C', cloud: '#EADFCA', drip: '#8FB8D6'
  };

  const round = (x, y, w, h, r, fill, extra = '') =>
    `<rect x="${x}" y="${y}" width="${w}" height="${h}" rx="${r}" fill="${fill}" ${extra}/>`;

  /* 一个圆角汉堡，带表情。y 是「贴地」的位置 */
  function burger(x, y, s = 1, opts = {}) {
    const happy = opts.happy !== false;
    return `<g transform="translate(${x},${y}) scale(${s})">
      <ellipse cx="0" cy="3" rx="52" ry="6" fill="#3A2418" opacity=".12"/>
      ${round(-46, -17, 92, 17, 8, C.bunDark)}
      ${round(-50, -29, 100, 13, 5, C.patty)}
      <path d="M-52,-33 L52,-33 L40,-26 L28,-33 L16,-26 L4,-33 L-8,-26 L-20,-33 L-32,-26 L-44,-33 Z" fill="${C.cheese}"/>
      <path d="M-52,-36 q11,-9 22,0 t22,0 t22,0 t22,0 t22,0 l0,3 l-110,0 Z" fill="${C.lettuce}"/>
      <path d="M-50,-38 a50,40 0 0 1 100,0 Z" fill="${C.bunTop}"/>
      <ellipse cx="-14" cy="-62" rx="13" ry="7" fill="#FFDFAE" opacity=".55"/>
      <ellipse cx="18" cy="-52" rx="2.6" ry="1.6" fill="${C.cream}" opacity=".9"/>
      <ellipse cx="-2" cy="-46" rx="2.6" ry="1.6" fill="${C.cream}" opacity=".9"/>
      <ellipse cx="34" cy="-44" rx="2.4" ry="1.5" fill="${C.cream}" opacity=".8"/>
      <circle cx="-15" cy="-55" r="3" fill="${C.ink}"/>
      <circle cx="13" cy="-55" r="3" fill="${C.ink}"/>
      <circle cx="-14" cy="-56" r="1" fill="#fff"/>
      <circle cx="14" cy="-56" r="1" fill="#fff"/>
      <ellipse cx="-26" cy="-47" rx="5" ry="3" fill="${C.blush}" opacity=".5"/>
      <ellipse cx="24" cy="-47" rx="5" ry="3" fill="${C.blush}" opacity=".5"/>
      ${happy
        ? `<path d="M-7,-47 q7,6 14,0" stroke="${C.ink}" stroke-width="1.9" fill="none" stroke-linecap="round"/>`
        : `<path d="M-6,-45 q6,-3 12,0" stroke="${C.ink}" stroke-width="1.9" fill="none" stroke-linecap="round"/>`}
    </g>`;
  }

  /* 薯条杯，带表情；opts.outline 给盒子加一圈描边（按钮红底上用） */
  function fries(x, y, s = 1, lean = 0, opts = {}) {
    let sticks = '';
    const cols = [C.yellow, '#EFB922', C.yellow, '#F7D06A', C.yellow, '#EFB922'];
    for (let i = 0; i < 6; i++) {
      const px = -20 + i * 8;
      const rot = (i - 2.5) * 3.2;
      const hgt = 30 + (i % 3) * 5;
      sticks += `<g transform="translate(${px},-52) rotate(${rot})">
        ${round(-3.4, -hgt, 6.8, hgt + 4, 3.2, cols[i])}
      </g>`;
    }
    return `<g transform="translate(${x},${y}) scale(${s}) rotate(${lean})">
      <ellipse cx="0" cy="3" rx="34" ry="5" fill="#3A2418" opacity=".12"/>
      <path d="M-27,0 L27,0 L21,-54 L-21,-54 Z" fill="${opts.box || C.red}"
        ${opts.outline ? `stroke="${opts.outline}" stroke-width="2.2"` : ''}/>
      <path d="M-24.5,-13 L24.5,-13 L23.4,-24 L-23.4,-24 Z" fill="${C.yellow}" opacity=".92"/>
      <circle cx="-9" cy="-38" r="2.6" fill="${C.cream}"/>
      <circle cx="9" cy="-38" r="2.6" fill="${C.cream}"/>
      <circle cx="-8.6" cy="-38" r="1.1" fill="${C.ink}"/>
      <circle cx="9.4" cy="-38" r="1.1" fill="${C.ink}"/>
      <path d="M-5,-31 q5,4 10,0" stroke="${C.cream}" stroke-width="1.6" fill="none" stroke-linecap="round"/>
      ${sticks}
    </g>`;
  }

  function umbrella(x, y, s = 1, rot = -10) {
    return `<g transform="translate(${x},${y}) scale(${s}) rotate(${rot})">
      <path d="M0,0 L0,-64" stroke="#8A6A4A" stroke-width="3" stroke-linecap="round"/>
      <path d="M0,-64 q10,2 12,12" stroke="#8A6A4A" stroke-width="3" fill="none" stroke-linecap="round"/>
      <path d="M-54,-62 a54,44 0 0 1 108,0 q-18,10 -36,0 q-18,10 -36,0 q-18,10 -36,0 Z" fill="${C.red}"/>
      <path d="M-54,-62 a54,44 0 0 1 27,-38 q-6,22 -3,38 Z" fill="#A80C24" opacity=".5"/>
      <path d="M-27,-100 a54,44 0 0 1 27,-1" fill="none" stroke="${C.yellow}" stroke-width="2" opacity=".5"/>
    </g>`;
  }

  function hotcup(x, y, s = 1) {
    return `<g transform="translate(${x},${y}) scale(${s})">
      <path d="M-15,-40 L15,-40 L12,0 L-12,0 Z" fill="${C.cup}"/>
      <path d="M-14,-27 L14,-27 L13,-11 L-13,-11 Z" fill="${C.red}"/>
      <path d="M-15,-40 L15,-40 L15,-44 L-15,-44 Z" fill="#E8DCC4"/>
      <path d="M0,-56 q-6,-8 0,-14 q6,-6 0,-12" stroke="${C.steam}" stroke-width="2.4"
        fill="none" stroke-linecap="round" opacity=".85"/>
      <path d="M-9,-54 q-5,-7 0,-12" stroke="${C.steam}" stroke-width="2"
        fill="none" stroke-linecap="round" opacity=".55"/>
      <path d="M9,-52 q5,-7 0,-12" stroke="${C.steam}" stroke-width="2"
        fill="none" stroke-linecap="round" opacity=".55"/>
      <circle cx="-5" cy="-20" r="1.9" fill="${C.cream}"/>
      <circle cx="5" cy="-20" r="1.9" fill="${C.cream}"/>
      <path d="M-3,-15 q3,3 6,0" stroke="${C.cream}" stroke-width="1.5" fill="none" stroke-linecap="round"/>
    </g>`;
  }

  function icecup(x, y, s = 1) {
    return `<g transform="translate(${x},${y}) scale(${s})">
      <path d="M-14,-40 L14,-40 L11,0 L-11,0 Z" fill="#DCEEF7" opacity=".95"/>
      <path d="M-13,-30 L13,-30 L11,0 L-11,0 Z" fill="${C.drip}" opacity=".45"/>
      <path d="M2,-44 L9,-70" stroke="${C.red}" stroke-width="4" stroke-linecap="round"/>
      ${round(-9, -26, 8, 7, 2, '#fff', 'opacity=".85"')}
      ${round(2, -18, 8, 7, 2, '#fff', 'opacity=".7"')}
      <circle cx="-4" cy="-10" r="1.7" fill="#5B4B3C" opacity=".5"/>
    </g>`;
  }

  function sun(x, y, r = 20) {
    let rays = '';
    for (let i = 0; i < 8; i++) {
      const a = (i * Math.PI) / 4;
      const x1 = Math.cos(a) * (r + 5), y1 = Math.sin(a) * (r + 5);
      const x2 = Math.cos(a) * (r + 12), y2 = Math.sin(a) * (r + 12);
      rays += `<line x1="${x1.toFixed(1)}" y1="${y1.toFixed(1)}" x2="${x2.toFixed(1)}"
        y2="${y2.toFixed(1)}" stroke="${C.yellow}" stroke-width="3" stroke-linecap="round"/>`;
    }
    return `<g transform="translate(${x},${y})" opacity=".95">
      ${rays}<circle r="${r}" fill="${C.sun}"/>
      <circle cx="-6" cy="-4" r="2.2" fill="#8A6112"/>
      <circle cx="6" cy="-4" r="2.2" fill="#8A6112"/>
      <path d="M-5,4 q5,4 10,0" stroke="#8A6112" stroke-width="1.8" fill="none" stroke-linecap="round"/>
    </g>`;
  }

  function cloud(x, y, s = 1) {
    return `<g transform="translate(${x},${y}) scale(${s})" opacity=".92">
      <circle cx="-16" cy="0" r="15" fill="${C.cloud}"/>
      <circle cx="4" cy="-7" r="19" fill="${C.cloud}"/>
      <circle cx="24" cy="1" r="13" fill="${C.cloud}"/>
      ${round(-30, 0, 68, 14, 7, C.cloud)}
    </g>`;
  }

  function drops(seed = 0) {
    const pts = [[-150, -116], [-92, -128], [-40, -108], [22, -124], [86, -112], [140, -126], [-116, -84], [58, -86], [166, -92], [-16, -80]];
    return pts.map(([x, y], i) => {
      const yy = y + (seed + i) % 5;
      return `<line x1="${x}" y1="${yy}" x2="${x - 6}" y2="${yy + 16}" stroke="${C.drip}"
        stroke-width="3" stroke-linecap="round" opacity=".6"/>`;
    }).join('');
  }

  function flakes() {
    const pts = [[-146, -110], [-70, -126], [10, -114], [96, -128], [162, -104], [-24, -86], [130, -80]];
    return pts.map(([x, y]) => `
      <g transform="translate(${x},${y})" stroke="${C.drip}" stroke-width="2.2" stroke-linecap="round" opacity=".65">
        <line x1="-6" y1="0" x2="6" y2="0"/><line x1="0" y1="-6" x2="0" y2="6"/>
        <line x1="-4.2" y1="-4.2" x2="4.2" y2="4.2"/><line x1="-4.2" y1="4.2" x2="4.2" y2="-4.2"/>
      </g>`).join('');
  }

  /* ── 品牌小件：金拱门 / 星星 / 鸡块蘸酱 / 红白饮料杯 / 纸袋 ── */

  /* 金色双拱门：两个清晰拱形 + 中间 M 形凹口（别画成饼） */
  function arches(x, y, s = 1, stroke = C.yellow, w = 8) {
    return `<g transform="translate(${x},${y}) scale(${s})">
      <path d="M-19,22 C-19,-6 -14,-14 -9.5,-14 C-4.5,-14 -2.5,-6 -1.6,4
               M1.6,4 C2.5,-6 4.5,-14 9.5,-14 C14,-14 19,-6 19,22"
        fill="none" stroke="${stroke}" stroke-width="${w}" stroke-linecap="round"/>
    </g>`;
  }

  /* 四角闪光星星 */
  function star(x, y, r = 7, fill = C.yellow, rot = 0) {
    const k = (r * .18).toFixed(1);
    return `<g transform="translate(${x},${y}) rotate(${rot})">
      <path d="M0,${-r} Q${k},${-k} ${r},0 Q${k},${k} 0,${r} Q${-k},${k} ${-r},0 Q${-k},${-k} 0,${-r} Z" fill="${fill}"/>
    </g>`;
  }

  /* 两块鸡块 + 一盒红色蘸酱 */
  function nuggets(x, y, s = 1) {
    return `<g transform="translate(${x},${y}) scale(${s})">
      <ellipse cx="2" cy="16" rx="30" ry="4" fill="#3A2418" opacity=".12"/>
      <g transform="rotate(-8)">
        <path d="M-25,4 Q-27,-8 -14,-10 Q-2,-11 -1,-1 L-1,7 Q-2,12 -12,13 Q-24,13 -25,9 Z" fill="#E8A33D"/>
        <ellipse cx="-17" cy="-3" rx="2.2" ry="1.4" fill="#F7D9A0" opacity=".85"/>
        <ellipse cx="-8" cy="4" rx="1.8" ry="1.2" fill="#F7D9A0" opacity=".7"/>
      </g>
      <g transform="translate(13,0) rotate(10)">
        <path d="M-12,-12 Q-13,-21 -3,-21 Q7,-21 6,-11 L6,0 Q5,5 -3,5 Q-12,5 -12,0 Z" fill="#EFB765"/>
        <ellipse cx="-4" cy="-13" rx="1.8" ry="1.2" fill="#F7D9A0" opacity=".8"/>
      </g>
      <g transform="translate(4,10)">
        <circle r="8.4" fill="${C.red}"/>
        <circle r="5.8" fill="#A80C24"/>
        <ellipse cx="-2" cy="-2" rx="3.6" ry="2.2" fill="#E4663C"/>
      </g>
    </g>`;
  }

  /* 红白配色的冷饮杯，杯身印迷你金拱门 */
  function cup(x, y, s = 1) {
    return `<g transform="translate(${x},${y}) scale(${s})">
      <ellipse cx="0" cy="2" rx="22" ry="4" fill="#3A2418" opacity=".12"/>
      <path d="M-16,-34 L16,-34 L12.6,0 L-12.6,0 Z" fill="#FFF6E6"/>
      <path d="M-14.8,-23 L14.8,-23 L13.8,-12 L-13.8,-12 Z" fill="${C.red}"/>
      ${arches(0, -17.5, .16, C.yellow, 11)}
      <path d="M-16,-34 L16,-34 L15.4,-37.6 L-15.4,-37.6 Z" fill="#EFE3CB"/>
      <path d="M-15.4,-37.6 L15.4,-37.6 L14.8,-40.6 L-14.8,-40.6 Z" fill="${C.red}"/>
      <path d="M4,-40.6 L11,-55" stroke="${C.yellow}" stroke-width="4" stroke-linecap="round"/>
    </g>`;
  }

  /* 红色外卖纸袋，金色提手 + 拱门 */
  function bag(x, y, s = 1) {
    return `<g transform="translate(${x},${y}) scale(${s})">
      <ellipse cx="0" cy="2" rx="32" ry="4.5" fill="#3A2418" opacity=".12"/>
      <path d="M-25,-44 L25,-44 L28.5,0 L-28.5,0 Z" fill="${C.red}"/>
      <path d="M-25,-44 L25,-44 L24.7,-39 L-24.7,-39 Z" fill="#9E1226"/>
      ${arches(0, -14, .42, C.yellow, 10)}
      <path d="M-13,-44 Q-11,-53 0,-53 Q11,-53 13,-44" fill="none" stroke="${C.yellow}" stroke-width="3.2" stroke-linecap="round"/>
    </g>`;
  }

  /* 复古印刷线稿：薯条 / 汉堡 / 饮料杯，用于纸张角落的淡纹 */
  function lineArt() {
    const st = 'fill="none" stroke="#A8835A" stroke-width="2.2" stroke-linecap="round" stroke-linejoin="round"';
    return `<g>
      <g transform="translate(16,66)">
        <path d="M-11,12 L11,12 L8,-8 L-8,-8 Z" ${st}/>
        <path d="M-5,-8 L-7,-18 M0,-8 L0,-19 M5,-8 L7,-18" ${st}/>
      </g>
      <g transform="translate(52,62)">
        <path d="M-12,-2 A12,9 0 0 1 12,-2" ${st}/>
        <line x1="-14" y1="-2" x2="14" y2="-2" ${st}/>
        <path d="M-12,2 L12,2 L9,9 L-9,9 Z" ${st}/>
      </g>
      <g transform="translate(86,68)">
        <path d="M-6,-10 L6,-10 L4.4,10 L-4.4,10 Z" ${st}/>
        <line x1="-6" y1="-10" x2="6" y2="-10" ${st}/>
      </g>
    </g>`;
  }

  const svgWrap = (vb, w, h, inner) =>
    `<svg xmlns="http://www.w3.org/2000/svg" viewBox="${vb}" width="${w}" height="${h}" aria-hidden="true">${inner}</svg>`;

  /* ── 页面级组合（独立 <svg>，可直接 innerHTML） ─────────── */

  /* 页面右上方：薯条盒 + 芝麻汉堡 + 星星 */
  function hero() {
    return svgWrap('0 0 200 124', 200, 124, `
      ${star(170, 26, 9, C.yellow, -12)}
      ${star(148, 52, 5, '#E0A32E', 18)}
      ${star(24, 34, 6, '#E0A32E', 0)}
      ${fries(46, 108, 1.05, -5)}
      ${burger(132, 112, .88)}`);
  }

  /* 标题旁：一小包薯条 + 两颗星 */
  function brandDeco() {
    return svgWrap('0 0 64 54', 64, 54, `
      ${star(50, 12, 7, C.yellow, 10)}
      ${star(10, 18, 4.5, '#E0A32E', -8)}
      ${fries(26, 48, .42, 7)}`);
  }

  /* 大号金拱门（标题左侧） */
  function archBrand() {
    return svgWrap('0 0 48 52', 48, 52, arches(24, 27, 1.05, C.yellow, 9.5));
  }

  function archMini() { return svgWrap('0 0 44 40', 44, 40, arches(22, 17, .8, C.yellow, 10)); }
  function archTiny() { return svgWrap('0 0 40 36', 40, 36, arches(20, 14, .72, '#E0A32E', 10)); }

  /* 日期旁的小装饰：星星 + 迷你薯条 */
  function dayDeco() {
    return svgWrap('0 0 30 44', 30, 44, `
      ${star(20, 8, 5.5, C.yellow, 12)}
      ${star(7, 18, 3.6, '#E0A32E', -10)}
      ${fries(13, 40, .19, 6)}`);
  }

  /* 撕开手势：往下撕的箭头 */
  function pull() {
    return svgWrap('0 0 20 30', 20, 30, `
      <path d="M10,2 C8,6 12,9 10,13 L10,21" fill="none" stroke="#FFE9AE" stroke-width="2.6" stroke-linecap="round"/>
      <path d="M4,16 L10,25 L16,16" fill="none" stroke="#FFE9AE" stroke-width="2.6" stroke-linecap="round" stroke-linejoin="round"/>`);
  }

  /* 按钮闪光 */
  function spark(i = 0) {
    const cols = [C.yellow, '#FFD966', '#E0A32E'];
    return svgWrap('0 0 16 16', 12, 12, star(8, 8, 7, cols[i % 3], i * 42));
  }

  /* 露出层底部的小食（半透明） */
  function revealFood() {
    return svgWrap('0 0 130 44', 130, 44, `
      <g opacity=".62">${cup(26, 40, .52)}${nuggets(74, 28, .55)}${star(112, 14, 5, C.yellow, 14)}</g>`);
  }

  function doodle() { return svgWrap('0 0 100 84', 100, 84, lineArt()); }

  /* 迷你开运小票（今日页入口卡用）：锯齿纸边 + 抬头 + 虚线 + 吉章 + 条码 */
  function miniTicket() {
    let h = 7, bars = '', x = 22;
    for (let i = 0; i < 26; i++) {
      h = (h * 48271) % 2147483647;
      const w = 1 + (h % 2);
      if (i % 2 === 0) bars += `<rect x="${x}" y="95" width="${w}" height="13" fill="${C.ink}" opacity=".5"/>`;
      x += w + 2.2;
    }
    const zig = (y, dir) => {
      let d = `M0,${y}`, xx = 0;
      while (xx < 200) { d += ` L${xx + 5},${y + 4.5 * dir} L${xx + 10},${y}`; xx += 10; }
      return `${d} L200,${y} Z`;
    };
    return svgWrap('0 0 200 140', 200, 140, `
      <path d="${zig(8, 1)}" fill="#F6EBD2"/>
      <rect x="0" y="8" width="200" height="124" fill="#FBF3DF"/>
      <path d="${zig(132, -1)}" fill="#F6EBD2"/>
      ${arches(27, 32, .5, C.red, 9)}
      <text x="50" y="36" font-family="'Songti SC','STSong',serif" font-size="15.5" font-weight="700"
        fill="${C.red}" letter-spacing="2">麦麦开运小票</text>
      <line x1="18" y1="50" x2="182" y2="50" stroke="#9A8873" stroke-width="1" stroke-dasharray="3 3" opacity=".6"/>
      <line x1="18" y1="62" x2="148" y2="62" stroke="#6E5B4B" stroke-width="2.4" opacity=".32"/>
      <line x1="18" y1="70" x2="166" y2="70" stroke="#6E5B4B" stroke-width="2.4" opacity=".26"/>
      <line x1="18" y1="78" x2="130" y2="78" stroke="#6E5B4B" stroke-width="2.4" opacity=".32"/>
      <g transform="translate(158,68) rotate(-8)">
        <rect x="-15" y="-13" width="30" height="26" rx="5" fill="none" stroke="${C.red}" stroke-width="2"/>
        <text x="0" y="5" text-anchor="middle" font-family="'Songti SC',serif" font-size="12.5"
          font-weight="700" fill="${C.red}">吉</text>
      </g>
      ${bars}
      <line x1="18" y1="90" x2="182" y2="90" stroke="#9A8873" stroke-width="1" stroke-dasharray="3 3" opacity=".6"/>
      <text x="100" y="114" text-anchor="middle" font-size="8.5" fill="#9A8873"
        letter-spacing="1.5">下单后由出票机现打 · 非支付凭证</text>
    `);
  }

  /* 宜忌小图标：按关键词返回对应美食 mini */
  function icon(name) {
    const map = {
      burger: () => burger(18, 26, .21),
      fries: () => fries(18, 25, .2),
      nuggets: () => nuggets(18, 13, .52),
      cup: () => cup(18, 24, .36),
      bag: () => bag(18, 25, .3),
      star: () => star(18, 15, 10)
    };
    const draw = map[name] || map.star;
    return svgWrap('0 0 36 30', 16, 13.5, draw());
  }

  function foodKey(text) {
    const t = String(text || '');
    if (/牛|汉堡|安格斯/.test(t)) return 'burger';
    if (/鸡/.test(t)) return 'nuggets';
    if (/饮|可乐|冰|冷|椰|柠檬/.test(t)) return 'cup';
    if (/薯/.test(t)) return 'fries';
    if (/袋|自取|外送|取餐/.test(t)) return 'bag';
    return '';
  }

  /* ── 四幕场景（400 × 150） ───────────────────────────── */
  const scenes = {
    // 雨天：汉堡撑伞，薯条在旁边躲雨
    rain: () => `
      <g>${drops(1)}</g>
      ${cloud(300, 46, .9)}
      ${umbrella(96, 132, 1.02, -12)}
      ${burger(96, 132, .92)}
      ${fries(268, 132, .86, 6)}
      ${round(180, 136, 150, 3, 2, '#C9B49A', 'opacity=".35"')}`,

    // 晴天：薯条戴墨镜晒太阳，汉堡戴草帽
    hot: () => `
      ${sun(330, 44, 21)}
      <g transform="translate(300,120) scale(.72)">
        <path d="M-40,0 a40,26 0 0 1 80,0 Z" fill="#F2D08A"/>
        <ellipse cx="0" cy="0" rx="56" ry="9" fill="#F7DFA8"/>
        <path d="M-38,-4 q38,8 76,0" stroke="${C.red}" stroke-width="5" fill="none" opacity=".85"/>
      </g>
      ${fries(96, 132, 1.0, -5)}
      ${icecup(196, 132, 1.0)}
      ${burger(288, 132, .84)}
      ${round(60, 136, 300, 3, 2, '#C9B49A', 'opacity=".35"')}`,

    // 冷天：汉堡捧着热饮
    cold: () => `
      <g>${flakes()}</g>
      ${burger(92, 132, .95)}
      ${hotcup(196, 128, 1.06)}
      ${fries(300, 132, .82, 5)}
      ${round(60, 136, 290, 3, 2, '#C9B49A', 'opacity=".35"')}`,

    // 多云 / 常温：小小阳光，慢慢吃
    mild: () => `
      ${sun(348, 40, 13)}
      ${cloud(268, 60, .82)}
      ${burger(112, 132, .95)}
      ${fries(272, 132, .9, 4)}
      ${round(66, 136, 286, 3, 2, '#C9B49A', 'opacity=".35"')}`
  };

  function scene(key) {
    return `<g>${(scenes[key] || scenes.mild)()}</g>`;
  }

  return {
    scene, C, arches, star, fries, burger, cup, nuggets, bag,
    icon, foodKey,
    svg: {
      hero, brandDeco, archBrand, archMini, archTiny, dayDeco,
      pull, spark, revealFood, doodle, miniTicket
    }
  };
})();

/* ── 小票 ──────────────────────────────────────────────────────
   全 SVG，导出 PNG 时逐字逐画都在，不会被裁掉。 */

const RECEIPT = (() => {
  const W = 460;          // 票面宽
  const M = 30;           // 左右留白
  const CW = W - M * 2;   // 内容宽
  const INK = '#2B211C', INK2 = '#6E5B4B', INK3 = '#9A8873';
  const RED = '#C8102E', GOLD = '#E0A32E', PAPER = '#FBF3DF';
  const SERIF = `'Songti SC','STSong','SimSun',Georgia,serif`;
  const SANS = `'PingFang SC','Hiragino Sans GB','Microsoft YaHei',sans-serif`;

  const esc = s => String(s == null ? '' : s)
    .replace(/&/g, '&amp;').replace(/</g, '&lt;').replace(/>/g, '&gt;')
    .replace(/"/g, '&quot;');

  // 中英混排的粗估宽度：汉字算满宽，ASCII 算半宽
  const width = (s, size) => {
    let w = 0;
    for (const ch of String(s)) w += /[\u3000-\u9fff\uff00-\uffef]/.test(ch) ? size : size * 0.55;
    return w;
  };

  function wrap(text, maxW, size) {
    const out = [];
    let line = '';
    for (const ch of String(text)) {
      if (width(line + ch, size) > maxW) { out.push(line); line = ch; }
      else line += ch;
    }
    if (line) out.push(line);
    return out;
  }

  const text = (x, y, str, o = {}) =>
    `<text x="${x}" y="${y}" font-family="${o.serif ? SERIF : SANS}" font-size="${o.size || 12}"
      fill="${o.fill || INK}" ${o.weight ? `font-weight="${o.weight}"` : ''}
      ${o.anchor ? `text-anchor="${o.anchor}"` : ''}
      ${o.ls ? `letter-spacing="${o.ls}"` : ''}
      ${o.op ? `opacity="${o.op}"` : ''}>${esc(str)}</text>`;

  const dashed = (y, op = 1) =>
    `<line x1="${M}" y1="${y}" x2="${W - M}" y2="${y}" stroke="${INK3}" stroke-width="1"
      stroke-dasharray="4 4" opacity="${op * 0.6}"/>`;

  /* 撕纸锯齿：向上/向下 */
  function teeth(y, dir, color) {
    // 手撕的边不会等宽等高：用固定种子做伪随机，保证每次渲染一致
    let seed = 7, rnd = () => (seed = (seed * 1103515245 + 12345) & 0x7fffffff) / 0x7fffffff;
    let d = `M0,${y}`, x = 0;
    while (x < W) {
      const step = 10 + rnd() * 9;
      const h = (6 + rnd() * 8) * (dir < 0 ? -1 : 1);
      d += ` L${(x + step / 2).toFixed(1)},${(y + h).toFixed(1)} L${(x + step).toFixed(1)},${y}`;
      x += step;
    }
    d += ` L${W},${y} Z`;
    return `<path d="${d}" fill="${color}"/>`;
  }

  /* 红色印章 */
  function seal(cx, cy, chars = '大吉', s = 38) {
    return `<g transform="translate(${cx},${cy}) rotate(-9)" opacity=".93">
      <rect x="${-s}" y="${-s}" width="${s * 2}" height="${s * 2}" rx="8"
        fill="none" stroke="${RED}" stroke-width="3.6"/>
      <rect x="${-s + 7}" y="${-s + 7}" width="${(s - 7) * 2}" height="${(s - 7) * 2}" rx="4"
        fill="none" stroke="${RED}" stroke-width="1" opacity=".7"/>
      ${text(0, -2, chars[0], { serif: 1, size: Math.round(s * 0.72), fill: RED, weight: 700, anchor: 'middle' })}
      ${text(0, Math.round(s * 0.78), chars[1], { serif: 1, size: Math.round(s * 0.72), fill: RED, weight: 700, anchor: 'middle' })}
    </g>`;
  }

  /* 条码：日期算出来的，纯装饰 */
  function barcode(y, seed) {
    let h = 0;
    for (const ch of String(seed)) h = (h * 31 + ch.charCodeAt(0)) % 9973;
    let x = M, bars = '';
    for (let i = 0; i < 44; i++) {
      h = (h * 1103515245 + 12345) & 0x7fffffff;
      const w = 1 + (h % 3);
      if (i % 2 === 0) bars += `<rect x="${x}" y="${y}" width="${w}" height="26" fill="${INK}" opacity=".62"/>`;
      x += w + 2;
    }
    return bars;
  }

  function build(d) {
    const p = d.plan || {};
    const w = d.weather || {};
    const parts = [];
    let y = 34;

    // ── 抬头
    parts.push(text(M, y + 12, '麦麦开运小票', { serif: 1, size: 23, weight: 700, fill: RED, ls: 2 }));
    parts.push(text(W - M, y + 4, d.dateText, { size: 10.5, fill: INK2, anchor: 'end', ls: 1 }));
    parts.push(text(W - M, y + 20, `No.${d.ticketNo}`, { size: 9.5, fill: INK3, anchor: 'end' }));
    y += 34;
    parts.push(text(M, y, '万事皆有宜忌 · 唯有吃麦当劳 · 日日皆宜',
      { serif: 1, size: 9.8, fill: INK3, ls: 1.2 }));
    y += 10;
    parts.push(dashed(y));
    y += 12;

    // ── 插画
    const AH = 150;
    parts.push(`<g transform="translate(${M},${y}) scale(${CW / 400},${AH / 150})">${ART.scene(d.scene)}</g>`);
    y += AH + 6;

    // ── 天气 / 开运食材 / 取餐方式
    const info = [
      ['今日天气', d.weatherText],
      ['开运食材', d.meatText],
      ['幸运取餐', d.modeText],
    ];
    info.forEach(([k, v]) => {
      parts.push(text(M, y + 11, k, { size: 10.5, fill: INK3, ls: 1 }));
      parts.push(text(W - M, y + 11, v, { size: 11.5, fill: INK, anchor: 'end' }));
      y += 19;
    });
    y += 4;
    parts.push(dashed(y));
    y += 16;

    // ── 宜 / 忌（右侧给印章留出固定宽度，不让字压到章上）
    const sealW = 104;
    const colW = CW - sealW - 22;
    const yiLines = wrap(d.yiText, colW, 11).slice(0, 3);
    const jiLines = wrap(d.jiText, colW, 11).slice(0, 3);
    parts.push(text(M, y + 4, '宜', { serif: 1, size: 13, fill: RED, weight: 700 }));
    yiLines.forEach((ln, i) => {
      parts.push(text(M + 21, y + 4 + i * 15, ln, { size: 11, fill: INK }));
    });
    let yy = y + yiLines.length * 15 + 2;
    parts.push(text(M, yy + 6, '忌', { serif: 1, size: 13, fill: INK2, weight: 700 }));
    jiLines.forEach((ln, i) => {
      parts.push(text(M + 21, yy + 6 + i * 15, ln, { size: 11, fill: INK2 }));
    });
    yy += jiLines.length * 15 + 10;
    parts.push(seal(M + colW + sealW / 2 + 8, (y + yy) / 2 + 2, '大吉', 34));
    y = yy + 10;

    parts.push(dashed(y));
    y += 22;

    // ── 品项
    parts.push(text(M, y, '品项', { size: 10, fill: INK3, ls: 1.5 }));
    parts.push(text(W - M, y, '金额', { size: 10, fill: INK3, anchor: 'end', ls: 1.5 }));
    y += 8;
    (p.items || []).forEach(it => {
      const nm = width(it.name, 11.5) > CW - 60
        ? it.name.slice(0, 15) + '…' : it.name;
      parts.push(text(M, y + 12, nm, { size: 11.5, fill: INK }));
      parts.push(text(W - M, y + 12, `¥${(+it.price).toFixed(1)}`, { size: 11.5, fill: INK, anchor: 'end' }));
      y += 19;
    });

    if (p.adjust) {
      parts.push(text(M, y + 10, p.adjust.label, { size: 10.5, fill: INK3 }));
      parts.push(text(W - M, y + 10,
        `${p.adjust.kind === 'discount' ? '-' : '+'}¥${(+p.adjust.amount).toFixed(1)}`,
        { size: 10.5, fill: INK3, anchor: 'end' }));
      y += 17;
    }

    if (p.coupon) {
      parts.push(text(M, y + 11, `券 · ${p.coupon.title}`, { size: 10.5, fill: RED }));
      parts.push(text(W - M, y + 11, `-¥${(+p.coupon.saving).toFixed(1)}`,
        { size: 10.5, fill: RED, anchor: 'end' }));
      y += 19;
      parts.push(text(M, y + 2, `核价实测省下 · 作用于「${p.coupon.on_item || '-'}」`,
        { size: 9, fill: INK3 }));
      y += 12;
    }

    y += 4;
    parts.push(dashed(y));
    y += 10;

    // ── 合计
    parts.push(text(M, y + 16, '合计', { serif: 1, size: 12.5, fill: INK2, ls: 2 }));
    parts.push(text(W - M, y + 20, `¥${(+p.total).toFixed(2)}`,
      { serif: 1, size: 27, fill: RED, weight: 700, anchor: 'end' }));
    y += 34;
    parts.push(text(M, y, d.ate
      ? `✓ 今日已吃${d.ate.pickupCode ? ' · 取餐码 ' + d.ate.pickupCode : ''}${d.ate.time ? ' · ' + d.ate.time : ''}`
      : d.payNote, { size: 9.2, fill: d.ate ? RED : INK3 }));
    y += 18;

    // ── 签语
    const signLines = wrap(d.sign, CW - 34, 11).slice(0, 3);
    const boxH = 24 + signLines.length * 16;
    parts.push(`<rect x="${M}" y="${y}" width="${CW}" height="${boxH}" rx="9"
      fill="#FFF8E6" stroke="${GOLD}" stroke-width="1" stroke-dasharray="5 4" opacity=".95"/>`);
    parts.push(text(M + 14, y + 18, '今日签', { serif: 1, size: 9.5, fill: GOLD, ls: 1.5 }));
    signLines.forEach((ln, i) => {
      parts.push(text(M + 14, y + 34 + i * 16, ln, { serif: 1, size: 11, fill: INK }));
    });
    y += boxH + 20;

    // ── 页脚
    parts.push(dashed(y));
    y += 14;
    parts.push(text(W / 2, y, d.ate ? '今日已吃 · 这一顿记在今天头上' : '本票为今日趣味推荐 · 未下单 · 非支付凭证',
      { size: 9, fill: d.ate ? RED : INK3, anchor: 'middle' }));
    y += 14;
    parts.push(barcode(y, d.ticketNo));
    y += 38;
    parts.push(text(W / 2, y, d.storeText, { size: 8.6, fill: INK3, anchor: 'middle', op: .9 }));
    y += 26;

    const H = y;

    return `<svg xmlns="http://www.w3.org/2000/svg" viewBox="0 0 ${W} ${H}" width="${W}" height="${H}">
      <defs>
        <filter id="paperGrain" x="0" y="0" width="100%" height="100%">
          <feTurbulence type="fractalNoise" baseFrequency="0.9" numOctaves="3" stitchTiles="stitch"/>
          <feColorMatrix type="saturate" values="0"/>
        </filter>
        <linearGradient id="paperG" x1="0" y1="0" x2="0.3" y2="1">
          <stop offset="0" stop-color="#FDF7E7"/><stop offset="0.55" stop-color="${PAPER}"/>
          <stop offset="1" stop-color="#F6EBD2"/>
        </linearGradient>
      </defs>
      ${teeth(9, -1, PAPER)}
      <rect x="0" y="9" width="${W}" height="${H - 18}" fill="url(#paperG)"/>
      <rect x="0" y="9" width="${W}" height="${H - 18}" filter="url(#paperGrain)" opacity=".045"/>
      ${teeth(H - 9, 1, PAPER)}
      ${d.ate ? `<g transform="translate(${W / 2},${H * 0.44}) rotate(-15)" opacity=".07">
        ${text(0, 0, '已吃', { serif: 1, size: 132, fill: RED, weight: 700, anchor: 'middle' })}
      </g>` : ''}
      ${parts.join('\n      ')}
    </svg>`;
  }

  return { build, W };
})();
