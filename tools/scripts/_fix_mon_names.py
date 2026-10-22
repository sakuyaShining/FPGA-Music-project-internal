# -*- coding: utf-8 -*-
"""修命名冲突：测试模式块的计数器恢复为 tm_cnt；我的电极遥测改名 pmon_*"""
import io
import re

p = "src/rtl/tdm_top.v"
s = io.open(p, encoding="utf-8-sig").read()
lines = s.split("\n")

# ① 测试模式块（第 714 行起的那一段）里的 mon_cnt 还原成 tm_cnt
start = next(i for i, l in enumerate(lines) if "测试模式：一次性把 512 个时隙" in l)
end = next(i for i, l in enumerate(lines) if "assign tm_load_epar" in l)
cnt1 = 0
for i in range(start, end + 1):
    if "mon_cnt" in lines[i]:
        lines[i] = re.sub(r"\bmon_cnt\b", "tm_cnt", lines[i])
        cnt1 += 1

s = "\n".join(lines)

# ② 剩下所有 mon_* 都是我的电极遥测 ⇒ 改名 pmon_*
n2 = 0
for a, b in (("mon_cnt", "pmon_cnt"), ("mon_st", "pmon_st"), ("mon_we", "pmon_we"),
             ("mon_addr", "pmon_addr"), ("mon_data", "pmon_data")):
    s, c = re.subn(r"\b" + a + r"\b", b, s)
    n2 += c

io.open(p, "w", encoding="utf-8", newline="").write(s)
print("  测试模式块还原 %d 行；遥测改名替换 %d 处" % (cnt1, n2))
