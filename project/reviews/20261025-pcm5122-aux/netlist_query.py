#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
netlist_query.py —— 从 EasyEDA .epcb2 还原「网络 <-> 焊盘」双向映射

为什么不用 .esch2：原理图侧 WIRE 记录是空壳（几何被剥离），做不出连通性。
.epcb2 的 PAD_NET 记录带 padNet 字段，配 COMPONENT 的 Designator 即可还原全板网表。

用法：
    python netlist_query.py net  <网络名>          # 列出该网络上的所有 (位号, 焊盘)
    python netlist_query.py part <位号>            # 列出该器件每个焊盘接的网络
    python netlist_query.py stats                  # 网络总数 / 器件总数
    python netlist_query.py grep <子串>            # 模糊查网络名

示例：
    python netlist_query.py part U12
    python netlist_query.py net I2S_BCK
    python netlist_query.py grep I2S
"""
import json
import re
import sys
from pathlib import Path

# 默认 PCB 路径：脚本位于 project/reviews/<日期>-<主题>/，往上三层到仓库根
ROOT = Path(__file__).resolve().parents[3]
DEFAULT_PCB = ROOT / "hardware/current/native/pcb/PCB1.epcb2"


def _dec(s):
    """反复 json.loads 直到不是字符串。

    .epcb2 里部分记录的 payload 本身是一个 JSON 字符串（双重编码），
    一次 loads 得到的是 str 而不是 dict，必须再解一次。
    """
    v = s
    for _ in range(3):
        v = json.loads(v)
        if not isinstance(v, str):
            return v
    return v


def load(path=DEFAULT_PCB):
    """返回 (pads, refs, parts)
    pads : list of (uuid, pad, net)     —— 每一条 PAD_NET
    refs : dict uuid -> designator      —— 来自 ATTR(key=Designator, parentId=器件uuid)
    parts: dict uuid -> 器件型号名       —— 来自 COMPONENT.attrs.DeviceName

    注意：Designator **不在** COMPONENT 的 attrs 里。COMPONENT 只有
    Reuse Block / Group ID / Channel ID / Unique ID / DeviceName。
    位号在独立的 ATTR 记录里，且必须带 parentId（parentId 为空的是库符号定义，
    value 形如 "U?"、"C?"，是模板不是实例，要过滤掉）。
    """
    pads, refs, parts = [], {}, {}
    with open(path, encoding="utf-8", errors="ignore") as f:
        for line in f:
            t = line.strip()
            if not t.startswith("{"):
                continue
            try:
                head, rest = t.split("||", 1)
                h = _dec(head)
                p = _dec(rest.rstrip("|")) if rest.strip("|") else {}
            except Exception:
                continue
            if not isinstance(p, dict):
                continue
            ty = h.get("type")
            if ty == "PAD_NET":
                try:
                    ident = json.loads(h["id"])   # ["PAD_NET", uuid, pad, padid]
                    pads.append((ident[1], ident[2], p.get("padNet") or ""))
                except Exception:
                    continue
            elif ty == "COMPONENT":
                a = p.get("attrs", {})
                if isinstance(a, str):
                    try:
                        a = _dec(a)
                    except Exception:
                        a = {}
                try:
                    parts[h["id"]] = _dec(a["DeviceName"]).get("name", "?")
                except Exception:
                    pass
            elif ty == "ATTR":
                if p.get("parentId") and p.get("key") == "Designator":
                    refs[p["parentId"]] = p["value"]
    return pads, refs, parts


def by_net(pads, refs, name):
    hit = [(refs.get(u, u), p) for (u, p, n) in pads if n == name]
    # 位号排序：字母前缀 + 数字
    hit.sort(key=lambda t: (re.sub(r"\d+", "", t[0]), int(re.sub(r"\D", "", t[0]) or 0)))
    return hit


def by_part(pads, refs, des):
    uuids = [u for u, d in refs.items() if d == des]
    if not uuids:
        return None
    out = [(p, n) for (u, p, n) in pads if u in uuids]
    out.sort(key=lambda t: int(re.sub(r"\D", "", t[0]) or 0))
    return out


def main():
    if len(sys.argv) < 2:
        print(__doc__)
        return 1
    cmd = sys.argv[1]
    pcb = Path(sys.argv[3]) if len(sys.argv) > 3 else DEFAULT_PCB
    pads, refs, parts = load(pcb)

    if cmd == "stats":
        nets = {n for (_, _, n) in pads if n}
        print("PCB      :", pcb)
        print("焊盘记录 :", len(pads))
        print("器件     :", len(refs))
        print("网络     :", len(nets))
        return 0

    # parts 不需要额外参数：列出全板器件清单。
    # 这是"全板有没有 X"这类结论唯一正确的查法 —— 不要在某一张原理图里 grep。
    if cmd == "parts":
        inv = {v: k for k, v in refs.items()}
        want = sys.argv[2].upper() if len(sys.argv) > 2 else ""

        def sortkey(d):
            m = re.fullmatch(r"([A-Za-z]+)(\d+)", d)
            return (m.group(1), int(m.group(2))) if m else (d, 0)

        rows = []
        for des in refs.values():
            nm = parts.get(inv.get(des, ""), "?")
            if want and want not in (des.upper() + " " + nm.upper()):
                continue
            rows.append((des, nm))
        rows.sort(key=lambda r: sortkey(r[0]))
        print("器件清单（%d 个）%s" % (len(rows), "  过滤=%r" % sys.argv[2] if want else ""))
        for des, nm in rows:
            print("  %-6s %s" % (des, nm))
        return 0

    if len(sys.argv) < 3:
        print("缺少参数"); return 1
    arg = sys.argv[2]

    if cmd == "net":
        hit = by_net(pads, refs, arg)
        if not hit:
            print("网络 %r 不存在（用 grep 模糊查）" % arg); return 2
        print("网络 %s —— %d 个焊盘" % (arg, len(hit)))
        for ref, pad in hit:
            print("  %-8s .%s" % (ref, pad))
        return 0

    if cmd == "part":
        out = by_part(pads, refs, arg)
        if out is None:
            print("位号 %r 不存在" % arg); return 2
        inv = {v: k for k, v in refs.items()}
        print("%s —— %s，%d 个焊盘" % (arg, parts.get(inv.get(arg, ""), "?"), len(out)))
        for pad, net in out:
            print("  .%-4s -> %s" % (pad, net or "(NC/未连接)"))
        return 0

    if cmd == "grep":
        nets = sorted({n for (_, _, n) in pads if n and arg.upper() in n.upper()})
        print("匹配 %r 的网络（%d 个）：" % (arg, len(nets)))
        for n in nets:
            print("  %-28s %d 焊盘" % (n, len(by_net(pads, refs, n))))
        return 0

    print("未知命令", cmd); return 1


if __name__ == "__main__":
    sys.exit(main())
