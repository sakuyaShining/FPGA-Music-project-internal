# -*- coding: utf-8 -*-
"""
regmap_dump.py —— 寄存器地址表的【单一事实源】抽取器 + 对账器

【为什么需要它】
  地址表同时活在两个地方：RTL（tdm_top.v 里的 R[8'hXX*8 +: 8] 与开机自举写入）
  和协议文档（UART 协议规格）。两边各改各的 = 必然分叉。
  本项目已经出过一次：17 号文档曾写"混响预留 0x51–0x55"，
     而我实际把混响实现在 0x48/0x49 —— 文档与代码不一致。

【机制】不靠约定，靠一条会自动报错的检查：
     RTL  ──抽取──►  地址表（本脚本输出，唯一权威）
                      │
     协议文档 ────────┘  文档里只写"以本脚本输出为准"，不再手抄

  用法：
    python tools/scripts/regmap_dump.py --dump          # 打印当前 RTL 的权威地址表
    python tools/scripts/regmap_dump.py --write-csv     # 把当前表写成基线（冻结时做一次）
    python tools/scripts/regmap_dump.py --check         # 与基线 CSV 对账，不一致则退出码 1

  冻结后的规矩：
    · 任何一方要动地址 ⇒ 先改 RTL + 更新基线 CSV ⇒ 跑 --check 绿 ⇒ 双方知会 ⇒ 用户点头
    · 协议文档不手抄地址，只写"以 regmap_dump.py --dump 的输出为准"
"""
import argparse
import csv
import os
import re
import sys

RTL = os.path.join("src", "rtl", "tdm_top.v")
BASE = os.path.join("docs", "02-技术方案", "regmap_baseline.csv")


def extract(path=RTL):
    src = open(path, encoding="utf-8").read()

    # 读侧：R[8'hXX*8 +: n]
    reads = {}
    for m in re.finditer(r"R\[\s*8'h([0-9A-Fa-f]{2})\s*\*\s*8\s*\+:\s*(\d+)\s*\]", src):
        a, w = int(m.group(1), 16), int(m.group(2))
        reads.setdefault(a, set()).add(w)

    # 上位机写侧：wr_addr == 8'hXX
    hostw = set(int(m, 16) for m in re.findall(r"wr_addr\s*==\s*8'h([0-9A-Fa-f]{2})", src))

    # 开机自举写侧：b_addr <= 8'hXX （并抓同一条的 b_data 默认值）
    boot = {}
    for m in re.finditer(r"b_addr\s*<=\s*8'h([0-9A-Fa-f]{2});\s*b_data\s*<=\s*8'h([0-9A-Fa-f]{2})", src):
        boot[int(m.group(1), 16)] = m.group(2).upper()

    # (本次)补：reg_bank 的**初值块**也是权威默认来源
    #   背景：0x7F 协议版本只写在初值块里（引导 FSM 不写它），
    #   而抽取器原来只扫 R[] 切片与自举写入 ⇒ 把 0x7F 误判成"RTL 里不存在" 。
    #   reg_bank.v 的 `mem[8'hXX] = 8'hYY;` 才是§3 冻结默认表的真身
    rb = os.path.join(os.path.dirname(RTL), "reg_bank.v")
    if os.path.isfile(rb):
        for m in re.finditer(r"mem\[8'h([0-9A-Fa-f]{2})\]\s*=\s*8'h([0-9A-Fa-f]{2})",
                             open(rb, encoding="utf-8").read()):
            a = int(m.group(1), 16)
            boot.setdefault(a, m.group(2).upper())     # 自举写的值优先（它最后生效）

    # (本次)：遥测写通路（电极遥测每 4096 拍刷一遍）也是合法写侧
    for m in re.finditer(r"pmon_addr\s*<=\s*8'h([0-9A-Fa-f]{2})", src):
        boot.setdefault(int(m.group(1), 16), "--")

    addrs = sorted(set(reads) | hostw | set(boot))
    rows = []
    for a in addrs:
        rows.append({
            "addr": "0x%02X" % a,
            "width": "+".join(sorted(str(w) for w in reads.get(a, []))) or "-",
            "rd": "Y" if a in reads else "-",
            "wr_host": "Y" if a in hostw else "-",
            "wr_boot": boot.get(a, "-"),
        })
    return rows


def dump(rows):
    print("地址  位宽  读  主机写  自举默认")
    print("-" * 46)
    for r in rows:
        print("%-5s %-5s %-3s %-6s %s" % (r["addr"], r["width"], r["rd"], r["wr_host"], r["wr_boot"]))
    print("-" * 46)
    print("已用地址 %d 个" % len(rows))
    used = set(int(r["addr"], 16) for r in rows)
    free = [a for a in range(0x00, 0x80) if a not in used]
    print("0x00–0x7F 空闲：%s" % " ".join("0x%02X" % a for a in free))


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--dump", action="store_true")
    ap.add_argument("--write-csv", action="store_true")
    ap.add_argument("--check", action="store_true")
    a = ap.parse_args()
    rows = extract()

    if a.write_csv:
        os.makedirs(os.path.dirname(BASE), exist_ok=True)
        with open(BASE, "w", encoding="utf-8", newline="") as fh:
            w = csv.DictWriter(fh, fieldnames=["addr", "width", "rd", "wr_host", "wr_boot"])
            w.writeheader()
            w.writerows(rows)
        print("已写出基线：%s（%d 条）" % (BASE, len(rows)))
        return 0

    if a.check:
        if not os.path.exists(BASE):
            print("缺基线 %s —— 先跑 --write-csv" % BASE)
            return 2
        old = list(csv.DictReader(open(BASE, encoding="utf-8")))
        ok = True
        olds = {r["addr"]: r for r in old}
        news = {r["addr"]: r for r in rows}
        for k in sorted(set(olds) | set(news)):
            if k not in olds:
                print("  ＋ 新增地址 %s（RTL 有、基线没有）" % k)
                ok = False
            elif k not in news:
                print("  － 地址消失 %s（基线有、RTL 没有）" % k)
                ok = False
            elif olds[k] != news[k]:
                print("  ！地址 %s 变更：基线 %s → RTL %s" % (k, olds[k], news[k]))
                ok = False
        if ok:
            print("地址表与基线一致（%d 条）" % len(rows))
            return 0
        print("★ 地址表与基线不一致 —— 协议文档还按旧表写就会分叉，先对齐再冻结")
        return 1

    dump(rows)
    return 0


if __name__ == "__main__":
    sys.exit(main())
