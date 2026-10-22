# -*- coding: utf-8 -*-
"""把 dsp_gui.selftest() 改成「既能打印、又能写报告文件」——
   --windowed 打包成 exe 后没有 stdout ✗，自测结果必须落盘才能验证 ✓。
   只动 selftest 函数体（行范围限定），不碰界面代码 ✓。"""
import io

p = "tools/host/dsp_gui.py"
lines = io.open(p, encoding="utf-8-sig").read().split("\n")

i0 = next(i for i, l in enumerate(lines) if l.startswith("def selftest():"))
i1 = next(i for i, l in enumerate(lines) if l.startswith("def _sel("))

# ① 函数内 print(-> say(
n = 0
for i in range(i0, i1):
    if "print(" in lines[i]:
        lines[i] = lines[i].replace("print(", "say(")
        n += 1

# ② 在 QApplication 之后插入 say()/lines
for i in range(i0, i1):
    if lines[i].strip() == "app = QApplication(sys.argv)":
        lines.insert(i, "    lines = []")
        lines.insert(i + 1, "")
        lines.insert(i + 2, "    def say(s=\"\"):")
        lines.insert(i + 3, "        \"\"\"同时打印（有 stdout 时）与收集到报告 ✓\"\"\"")
        lines.insert(i + 4, "        lines.append(s)")
        lines.insert(i + 5, "        _say(s)")
        lines.insert(i + 6, "")
        i1 += 7
        break

# ③ 输出目录改用 out_dir()
for i in range(i0, i1):
    if lines[i].startswith("    out = os.path.normpath("):
        lines[i] = "    out = out_dir()"

# ④ 在结果行之前写好报告文件
for i in range(i0, i1):
    if lines[i].strip().startswith("if fails == 0:") and "say(" in lines[i + 1]:
        lines.insert(i, "    rpt = os.path.join(out, \"selftest_report.txt\")")
        lines.insert(i + 1, "    with open(rpt, \"w\", encoding=\"utf-8\") as fh:")
        lines.insert(i + 2, "        fh.write(\"\\n\".join(lines) + \"\\n\")")
        lines.insert(i + 3, "    say(\"\")")
        lines.insert(i + 4, "    say(\"报告已写出：%s\" % rpt)")
        break

io.open(p, "w", encoding="utf-8", newline="").write("\n".join(lines))
print("  selftest：print→say 替换 %d 处；已加 lines/say、out_dir、报告落盘 ✓" % n)
