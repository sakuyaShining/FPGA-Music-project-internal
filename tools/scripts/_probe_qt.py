# -*- coding: utf-8 -*-
"""探测本机 Qt 能力的完整度 + 可选的"网页外观 + 原生窗口"路线（一次性脚本）。
只做 import / 版本读取，不打开窗口、不进入事件循环（避免卡住）。"""
import importlib

print("=== Qt（PyQt5，本机已装）===")
try:
    from PyQt5.QtCore import QT_VERSION_STR, PYQT_VERSION_STR
    print("  PyQt5 %s  /  Qt %s" % (PYQT_VERSION_STR, QT_VERSION_STR))
except Exception as e:
    print("  ✗ %s" % e)

for mod, why in [
    ("PyQt5.QtWidgets", "常规控件（窗口/按钮/滑条）"),
    ("PyQt5.QtGui", "QPainter/QSS 美化基础"),
    ("PyQt5.QtSvg", "矢量图标（高 DPI 清晰）"),
    ("PyQt5.QtChart", "现成图表（若装了）"),
    ("PyQt5.QtQuick", "QML 声明式界面（最漂亮的 Qt 路线）"),
    ("PyQt5.QtWebEngineWidgets", "Qt 内置 Chromium（可嵌网页）"),
    ("PyQt5.QtMultimedia", "音频播放（想放参考 WAV 有用）"),
]:
    try:
        importlib.import_module(mod)
        print("  %-32s ✅ %s" % (mod, why))
    except Exception:
        print("  %-32s ❌ %s" % (mod, why))

print("=== “HTML/CSS 外观 + 原生窗口” 备选 ===")
for mod, why in [("webview", "pywebview：原生窗口内嵌 Edge/WebView2"),
                 ("eel", "Eel：Python 后端 + Chrome 应用窗口")]:
    try:
        importlib.import_module(mod)
        print("  %-12s ✅ 已装（%s）" % (mod, why))
    except Exception:
        print("  %-12s ❌ 未装（%s，pip 一行；Windows 10/11 一般自带 WebView2 运行时）" % (mod, why))
