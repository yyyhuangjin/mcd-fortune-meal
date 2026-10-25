#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
取菜单 / 核价 / 查门店 的小 CLI —— 复用 ~/.workbuddy/mcp.json 里的 Token

用法：
  python3 scripts/fetch_menu.py stores --city 北京 --keyword 国贸
  python3 scripts/fetch_menu.py menu   --store-code 1950564 --order-type 1 --be-type 1 --out menu.json
  python3 scripts/fetch_menu.py price  --store-code 1950564 --order-type 1 --be-type 1 --items 511781,4437,515955

设计原则：只做「读」。下单相关动作一律交给 Agent 在用户确认后通过 MCP 工具执行。
"""

from __future__ import annotations

import argparse
import json
import os
import sys
import urllib.request

MCP_URL = "https://mcp.mcd.cn"
CFG = os.path.expanduser("~/.workbuddy/mcp.json")


def token():
    try:
        cfg = json.load(open(CFG, encoding="utf-8"))
        auth = cfg["mcpServers"]["mcd-mcp"]["headers"]["Authorization"]
        return auth.split("Bearer", 1)[1].strip()
    except Exception:
        sys.exit("读不到 Token，请检查 ~/.workbuddy/mcp.json 里的 mcd-mcp 配置")


def parse_json_object(text: str):
    """从 MCP 响应里取出业务数据。踩过的坑：

    1. 整条响应是**单行 JSON**，业务数据在 result.structuredContent 里最干净；
    2. result.content[0].text 里既有 markdown 说明，又有粘在表格行尾部的 JSON；
    3. 文本里的 "success" 会被 JSON 转义成 \\"success\\"，所以不能用
       find('{"success"') 定位——会误命中内层 structuredContent。

    顺序：structuredContent → content 文本里的 JSON → 全文兜底。
    """
    dec = json.JSONDecoder()

    # 1) JSON-RPC 外壳
    env = None
    body = text
    try:
        env = json.loads(body)
    except json.JSONDecodeError:
        # SSE / 带前缀的情况
        for ln in body.splitlines():
            st = ln.strip()
            if st.startswith("data:"):
                st = st[5:].strip()
            if st.startswith("{"):
                try:
                    env = json.loads(st)
                    break
                except json.JSONDecodeError:
                    continue

    if isinstance(env, dict) and "error" in env:
        sys.exit(f"MCP 错误：{json.dumps(env['error'], ensure_ascii=False)}")

    if isinstance(env, dict) and "result" in env:
        res = env["result"]
        # 1a) 首选：结构化的业务数据
        sc = res.get("structuredContent")
        if isinstance(sc, dict) and "success" in sc:
            return sc
        # 1b) 退回 content 文本
        content = res.get("content") or []
        if content:
            inner = _scan_json(content[0].get("text") or "")
            if inner is not None:
                return inner
        return sc if isinstance(sc, dict) else {}

    return _scan_json(text) or {}


def _scan_json(text: str):
    """在混杂说明文字的文本里找出 JSON 对象（取最靠后的完整对象）"""
    dec = json.JSONDecoder()
    best = None
    i = 0
    while True:
        j = text.find('"success"', i)
        if j < 0:
            break
        # 回退到该 key 前最近的 {
        k = text.rfind("{", 0, j)
        if k >= 0:
            try:
                obj, _ = dec.raw_decode(text[k:])
                if isinstance(obj, dict) and "success" in obj:
                    best = obj
            except json.JSONDecodeError:
                pass
        i = j + 1
    return best


def call(name: str, args: dict, timeout=40):
    body = json.dumps({
        "jsonrpc": "2.0", "id": 1, "method": "tools/call",
        "params": {"name": name, "arguments": args},
    }).encode()
    req = urllib.request.Request(
        MCP_URL, data=body, method="POST",
        headers={
            "Content-Type": "application/json",
            "Accept": "application/json, text/event-stream",
            "Authorization": f"Bearer {token()}",
        },
    )
    with urllib.request.urlopen(req, timeout=timeout) as r:
        raw = r.read().decode()
    payload = parse_json_object(raw)
    if not payload:
        sys.exit(f"响应无法解析：{raw[:200]}")
    return payload


def main():
    ap = argparse.ArgumentParser()
    sub = ap.add_subparsers(dest="cmd", required=True)

    s1 = sub.add_parser("stores")
    s1.add_argument("--city", required=True)
    s1.add_argument("--keyword", default="")
    s1.add_argument("--be-type", type=int, default=1, choices=[1, 5])

    s2 = sub.add_parser("menu")
    s2.add_argument("--store-code", required=True)
    s2.add_argument("--order-type", type=int, default=1, choices=[1, 2])
    s2.add_argument("--be-type", type=int, default=1, choices=[1, 2, 5, 6])
    s2.add_argument("--be-code")
    s2.add_argument("--out", default="menu.json")

    s3 = sub.add_parser("price")
    s3.add_argument("--store-code", required=True)
    s3.add_argument("--order-type", type=int, default=1, choices=[1, 2])
    s3.add_argument("--be-type", type=int, default=1, choices=[1, 2, 5, 6])
    s3.add_argument("--be-code")
    s3.add_argument("--items", required=True, help="逗号分隔的 productCode")

    a = ap.parse_args()

    if a.cmd == "stores":
        res = call("query-nearby-stores",
                   {"beType": a.be_type, "searchType": 2, "city": a.city, "keyword": a.keyword})
        for s in (res.get("data") or [])[:8]:
            print(f"{s.get('storeCode')}  {s.get('storeName')}  {s.get('distance')}m  {s.get('address')}")
        return

    if a.cmd == "menu":
        args = {"storeCode": a.store_code, "orderType": a.order_type, "beType": a.be_type}
        if a.be_code:
            args["beCode"] = a.be_code
        res = call("query-meals", args)
        json.dump(res, open(a.out, "w", encoding="utf-8"), ensure_ascii=False, indent=1)
        n = len((res.get("data") or {}).get("meals") or {})
        print(f"已保存 {a.out}（{n} 个 SKU）")
        return

    if a.cmd == "price":
        args = {
            "storeCode": a.store_code, "orderType": a.order_type, "beType": a.be_type,
            "items": [{"productCode": c.strip(), "quantity": 1} for c in a.items.split(",") if c.strip()],
        }
        if a.be_code:
            args["beCode"] = a.be_code
        res = call("calculate-price", args)
        d = res.get("data") or {}
        for p in d.get("productList", []):
            print(f"  {p.get('productName'):<26} ¥{p.get('subtotal', 0)/100:>6.2f}")
        print(f"  原价 ¥{d.get('originalPrice', 0)/100:.2f}  优惠 ¥{d.get('discount', 0)/100:.2f}  "
              f"应付 ¥{d.get('price', 0)/100:.2f}")


if __name__ == "__main__":
    main()
