# -*- coding: utf-8 -*-
"""探测本机 GUI/串口相关库的可用性，供选型决策（一次性脚本）。"""
import importlib
import sys

print("  Python:", sys.version.split()[0], "(%s)" % sys.executable)

# 标准库 GUI
try:
    import tkinter
    print("  tkinter : 可用（Tk %s，标准库，零安装）" % tkinter.TkVersion)
except Exception as e:
    print("  tkinter : 不可用 -> %s" % e)

mods = [
    ("pyserial", "pyserial", "串口（本项目上位机必需）"),
    ("PySide6", "PySide6", "Qt6 官方绑定（LGPL）"),
    ("PyQt5", "PyQt5", "Qt5 绑定（GPL/商业）"),
    ("wx", "wxPython", "原生控件"),
    ("kivy", "Kivy", "触摸/自绘 UI"),
    ("dearpygui", "Dear PyGui", "即时模式工具面板"),
    ("pyqtgraph", "pyqtgraph", "实时曲线/频谱"),
    ("matplotlib", "matplotlib", "绘图（非实时也好用）"),
    ("flask", "Flask", "本地 Web 后端"),
    ("fastapi", "FastAPI", "本地 Web 后端（异步）"),
    ("websockets", "websockets", "WebSocket"),
    ("streamlit", "Streamlit", "数据面板（实时串口不擅长）"),
    ("gradio", "Gradio", "同上"),
    ("numpy", "numpy", "本项目判据脚本已在用"),
]
print("  --- 第三方库 ---")
for name, label, note in mods:
    try:
        importlib.import_module(name)
        print("  %-12s 已装    %s" % (label, note))
    except Exception:
        print("  %-12s 未装    %s" % (label, note))
