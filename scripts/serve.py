#!/usr/bin/env python3
"""麦麦黄道吉日 · 本地预览服务。

为什么要一个服务：网页不能直接调麦当劳接口——把 Token 交给浏览器等于公开它。
所以页面只发 HTTP 请求给这个本机服务，服务端读 ~/.workbuddy/mcp.json 里的 Token
再去调 MCP。浏览器全程看不到 Token。

    python3 scripts/serve.py            # 默认 http://127.0.0.1:8765
    python3 scripts/serve.py --open     # 顺手打开浏览器

只监听 127.0.0.1，不开局域网；所有写操作（领取优惠券、创建订单）都要求
请求体里 confirm=true，且服务端会重新核价后才落单。
"""
from __future__ import annotations

import argparse
import json
import sys
import threading
import urllib.parse
import webbrowser
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from pathlib import Path

HERE = Path(__file__).resolve().parent
ROOT = HERE.parent
sys.path.insert(0, str(HERE))

import fetch_menu as fm
import make_almanac
import order as od

PAGE = ROOT / "demo" / "almanac.html"
CACHE = {"data": None}


def regenerate(city: str | None = None, **kw) -> dict:
    if city:
        CACHE["city"] = city
    else:
        city = CACHE.get("city")
    data = make_almanac.build(city, **kw)
    make_almanac.render_html(data, PAGE)
    CACHE["data"] = data
    return data


class Handler(BaseHTTPRequestHandler):
    server_version = "mcd-fortune/1.2"

    def log_message(self, fmt, *args):
        sys.stderr.write("  %s\n" % (fmt % args))

    # ── 基础输出 ──
    def _send(self, code: int, body: bytes, ctype: str):
        self.send_response(code)
        self.send_header("Content-Type", ctype)
        self.send_header("Content-Length", str(len(body)))
        self.send_header("Cache-Control", "no-store")
        self.end_headers()
        self.wfile.write(body)

    def _json(self, obj, code=200):
        self._send(code, json.dumps(obj, ensure_ascii=False).encode("utf-8"),
                   "application/json; charset=utf-8")

    def _body(self) -> dict:
        n = int(self.headers.get("Content-Length") or 0)
        if not n:
            return {}
        try:
            return json.loads(self.rfile.read(n).decode("utf-8"))
        except Exception:
            return {}

    # ── 路由 ──
    def do_GET(self):
        u = urllib.parse.urlparse(self.path)
        qs = urllib.parse.parse_qs(u.query)

        if u.path in ("/", "/index.html"):
            if not PAGE.exists():
                regenerate()
            self._send(200, PAGE.read_bytes(), "text/html; charset=utf-8")
            return

        if u.path == "/api/status":
            oid = (qs.get("orderId") or [""])[0]
            if not oid:
                self._json({"ok": False, "message": "缺少 orderId"}, 400)
                return
            r = fm.call("query-order", {"orderId": oid})
            self._json({"ok": bool(r.get("success")),
                        "data": r.get("data") or {},
                        "message": r.get("message", "")})
            return

        if u.path == "/api/data":
            self._json({"ok": True, "data": CACHE["data"] or regenerate()})
            return

        if u.path == "/api/reload":
            city = (qs.get("city") or [None])[0]
            self._json({"ok": True, "data": regenerate(city)})
            return

        self._json({"ok": False, "message": "not found"}, 404)

    def do_POST(self):
        u = urllib.parse.urlparse(self.path)
        body = self._body()

        # 换一家店：只读操作，但要把整店的菜单/券/价重拉一遍（几秒）
        if u.path == "/api/store":
            code = str(body.get("storeCode") or "")
            if not code:
                self._json({"ok": False, "message": "缺少 storeCode"}, 400)
                return
            kind = body.get("kind") or "pickup"
            kw = ({"preferred_store": code} if kind == "pickup"
                  else {"preferred_delivery": code})
            try:
                data = regenerate(None, **kw)
            except Exception as e:                      # 网络抖一下不该把页面弄挂
                self._json({"ok": False, "message": f"换店失败：{e}"}, 502)
                return
            got = (data.get("stores") or {}).get("chosen") or {}
            ok = got.get(kind) == code
            self._json({"ok": ok, "data": data,
                        "message": "" if ok else "这家店当前不营业或暂无菜单"}, 200 if ok else 409)
            return

        if u.path == "/api/quote":
            q = od.build_quote(
                store_code=body.get("storeCode"),
                order_type=int(body.get("orderType", 1)),
                be_type=int(body.get("beType", 1)),
                be_code=body.get("beCode", ""),
                address_id=body.get("addressId", ""),
                items=body.get("items") or [],
                coupon=body.get("coupon"),
                remark=body.get("remark", ""),
                need_tableware=bool(body.get("needTableware")),
            )
            if not q["ok"]:
                self._json({"ok": False, "message": q.get("message") or "核价失败"}, 409)
                return
            q["takeWayCode"] = od.pick_take_way(q["take_way"])
            self._json(q)
            return

        if u.path == "/api/order":
            if not body.get("confirm"):
                self._json({"ok": False, "message": "缺少确认（confirm=true），未创建订单"}, 400)
                return
            items = [dict(x) for x in (body.get("items") or [])]
            # 价格以服务端重算为准；前端传的 total 只用来判断「有没有变」
            quote = {
                "storeCode": body.get("storeCode"),
                "orderType": int(body.get("orderType", 1)),
                "beType": int(body.get("beType", 1)),
                "beCode": body.get("beCode", ""),
                "addressId": body.get("addressId", ""),
                "items": items,
                "coupon": body.get("coupon"),
                "remark": body.get("remark", ""),
                "needTableware": bool(body.get("needTableware")),
                "total": int(round(float(body.get("total") or 0) * 100)),
            }
            r = od.place(quote, body.get("takeWayCode") or "",
                         confirm=True, accept_change=bool(body.get("acceptChange")))
            self._json(r, 200 if r.get("ok") else 409)
            return

        if u.path == "/api/cancel":
            if not body.get("confirm"):
                self._json({"ok": False, "message": "取消订单需要确认"}, 400)
                return
            oid = str(body.get("orderId") or "")
            if not oid:
                self._json({"ok": False, "message": "缺少 orderId"}, 400)
                return
            r = fm.call("cancel-order", {"orderId": oid,
                                         "cancelReasonCode": str(body.get("reason") or "1")})
            self._json({"ok": bool(r.get("success")), "message": r.get("message", ""),
                        "detail": r.get("data")})
            return

        if u.path == "/api/claim":
            if not body.get("confirm"):
                self._json({"ok": False, "message": "领取优惠券需要确认"}, 400)
                return
            av = fm.call("available-coupons", {})
            names = [c.get("couponName") for c in (av.get("data") or [])]
            r = fm.call("auto-bind-coupons", {})
            self._json({"ok": bool(r.get("success")), "claimed_target": names,
                        "message": r.get("message", ""), "detail": r.get("data")})
            return

        self._json({"ok": False, "message": "not found"}, 404)


def main():
    ap = argparse.ArgumentParser(description="麦麦黄道吉日 · 本地预览")
    ap.add_argument("--port", type=int, default=8765)
    ap.add_argument("--city", help="不填则自动定位")
    ap.add_argument("--open", action="store_true")
    ap.add_argument("--no-regen", action="store_true", help="复用已有的 almanac.html")
    a = ap.parse_args()

    if not a.no_regen:
        print("· 正在拉真实数据（定位 / 天气 / 门店 / 菜单 / 券 / 核价）…")
        regenerate(a.city)

    srv = ThreadingHTTPServer(("127.0.0.1", a.port), Handler)
    url = f"http://127.0.0.1:{a.port}/"
    print(f"· 页面：{url}")
    print("· Token 只在本进程里使用，浏览器拿不到")
    print("· 按 Ctrl+C 停止")
    if a.open:
        threading.Timer(0.8, lambda: webbrowser.open(url)).start()
    try:
        srv.serve_forever()
    except KeyboardInterrupt:
        print("\n· 已停止")


if __name__ == "__main__":
    main()
