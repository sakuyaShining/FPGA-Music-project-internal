# -*- coding: utf-8 -*-
"""
dsp_gui.py —— FPGA 加法合成器上位机 v2（PyQt5 + QSS）

用法：
    python tools/host/dsp_gui.py                # 正常启动（选串口或"模拟设备"）
    python tools/host/dsp_gui.py --selftest     # 离线自测：建界面→截图→校验帧一致性

【v2 相对 v1 的变化（围绕 8 分钟演示叙事重排）】
  1. 左列 = 演奏：五声音阶键盘（八度可移）+ 力度 + **表情轴卡**（颤音/滑音，
     M1"两个表情维度同时独立调节互不干扰"的现场演示面板）
  2. 中列 = 塑谱：**手绘画谱**（按住拖动直接"抹"出 16 泛音谱形）+
     **逐声部塑形目标**（A1：谱可只刷给声部 0–31，对 Hammond"全局注册"的差异化卖点）
  3. 右列 = 遥测与调试：电极遥测（新增**自动循环扫描**）+ 寄存器表（连接后自动回读）
  4. 底部 = **定序器卡**（脱机演示线：BPM + 曲谱文本 + 下载/播放/停止）
     —— v1 里定序器只能靠命令行 dsp_host demo-score，GUI 演示叙事第 1 幕没有面板
  5. 判据统一：量程判定 verdict() 只有一份（在 dsp_host.py，GUI/CLI 共用）

【架构纪律（项目要求，v1 已立、v2 沿用）】
  1. 协议/帧层与界面分离：界面只调 `serial_link` 的 send()/read_reg() ✓
  2. 地址表与帧构造**直接复用** `dsp_host.py`（REG / Frames / cmd_note / cmd_spectrum /
     cmd_fx / cmd_refresh / tempo_inc）—— 不另抄一份 ✗，从根上防"上位机与 RTL 各改各的" ✓
     （v2 新增的表情轴/定序器写入也只碰冻结表里的寄存器名，不发明新地址 ✓）
  3. 顶部**明确显示**当前是「真实串口」还是「模拟设备」✗ 绝不让人误以为在跟板子说话
  4. 每个动作都进"帧流水"，可一键导出成 `dsp_host.py --emit` 同格式 ⇒ 仿真里原样重放 ✓
  5. 字节率读数常显 —— 用来直观证明"电脑只发参数级数据（~几十 B/s），音频是 FPGA 算的" ✓

  协议收敛（2026-10-06）：SEQ_CTRL 的"曲谱源"位已按修正案 A6/A7 删除，
  **SCORE_LEN>0 即自动使用下载曲谱**。所以播放只写 SEQ_CTRL=0x01（bit0 使能），
  bit2 是无关位。本文件曾留下三处不一致（头部注释写 0x05、实现写 0x01、
  自检期望 0x05），自检因此长期 FAIL（帧一致性 ⑥）—— 现已统一为 0x01。
"""

import os
import sys
import time

_HERE = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, _HERE)
sys.path.insert(0, os.path.normpath(os.path.join(_HERE, "..", "scripts")))

import dsp_host as dh                                        # noqa: E402
from serial_link import (SerialLink, SimLink, verdict, addr_name,   # noqa: E402
                         list_ports, TEL, find_file, frozen, exe_dir)

from PyQt5.QtCore import Qt, QTimer, QRectF, pyqtSignal      # noqa: E402
from PyQt5.QtGui import QPainter, QColor, QPen, QFont        # noqa: E402
from PyQt5.QtWidgets import (                                # noqa: E402
    QApplication, QMainWindow, QWidget, QFrame, QLabel, QPushButton,
    QVBoxLayout, QHBoxLayout, QGridLayout, QComboBox, QSlider,
    QCheckBox, QPlainTextEdit, QTableWidget, QTableWidgetItem,
    QHeaderView, QFileDialog, QMessageBox, QSizePolicy,
    QSpinBox, QLineEdit, QButtonGroup
)

# ---- 与硬件布局一致：左手 8 个五声音阶音高键（MIDI 60 62 64 67 69 72 74 76）----
PENTA = [60, 62, 64, 67, 69, 72, 74, 76]
KEYMAP = ["Z", "X", "C", "V", "B", "N", "M", ","]
PRESETS = [("管风琴", 0), ("钢琴", 1), ("钟", 2), ("马林巴", 3)]
FXS = [("干声", "dry"), ("延迟", "delay"), ("合唱", "chorus"), ("混响", "reverb"),
       ("延+混", "delay+reverb"), ("全开", "all")]

# 塑谱示例：谱形即音色（演示"画出来的曲线 = 频谱形状"）
SPECTRA = [
    ("示例谱", [255, 0, 160, 0, 120, 0, 90, 0, 70, 0, 55, 0, 40, 0, 30, 0]),
    ("正弦", [255] + [0] * 15),
    ("方波", [255, 0, 85, 0, 51, 0, 36, 0, 28, 0, 23, 0, 20, 0, 18, 0]),
    ("全零", [0] * 16),
]

# 寄存器表里常显的（其余可通过回读查看）
SHOW_REGS = ["CTRL", "PRESET", "FX_CTRL", "DELAY_LEN", "RV_FB", "RV_DAMP",
             "SPEC_MODE", "HARM_PADS", "SEQ_CTRL", "TEMPO", "PROTO_VER"]

DEMO_SCORE_TEXT = "64:1,64:1,65:1,67:1,67:1,65:1,64:1,62:2"      # 欢乐颂开头

_NOTE_NAMES = ["C", "C#", "D", "D#", "E", "F", "F#", "G", "G#", "A", "A#", "B"]


def midi_name(m):
    return "%s%d" % (_NOTE_NAMES[m % 12], m // 12 - 1)


def _say(s):
    """打包成 --windowed exe 后 sys.stdout 可能是 None ✗ ⇒ 必须防 ✓"""
    try:
        if sys.stdout is not None:
            sys.stdout.write(s + "\n")
            sys.stdout.flush()
    except Exception:
        pass


def out_dir():
    """截图/报告输出目录：优先仓库里的 sim_build/gui，不可写就放 exe 旁边 ✓"""
    for base in (os.getcwd(), exe_dir()):
        d = os.path.join(base, "sim_build", "gui")
        try:
            if not os.path.isdir(d):
                os.makedirs(d)
            return d
        except Exception:
            continue
    import tempfile
    d = os.path.join(tempfile.gettempdir(), "dsp_gui")
    if not os.path.isdir(d):
        os.makedirs(d)
    return d


def card(title):
    """带标题的卡片容器，返回 (卡片, 内容布局)"""
    f = QFrame()
    f.setObjectName("Card")
    v = QVBoxLayout(f)
    v.setContentsMargins(12, 10, 12, 12)
    v.setSpacing(8)
    if title:
        lab = QLabel(title)
        lab.setObjectName("CardTitle")
        v.addWidget(lab)
    return f, v


# =============================================================================
#  手绘画谱（自绘：按住拖动直接画 16 根泛音条 —— "谱形就是音色"的直观化）
# =============================================================================
class SpectrumBars(QWidget):
    """16 根可拖动的泛音幅度条。

      · 鼠标按住某根上下拖 = 改该泛音幅度；横向扫过 = 连续"抹"出谱形
      · values()/set_values() 供界面与自测使用
      · changed 信号：值变化时发（界面用它更新读数标签）
    """
    changed = pyqtSignal()

    def __init__(self, n=16):
        super().__init__()
        self.n = n
        self.vals = [0] * n
        self._drag = False
        self.setMinimumHeight(170)
        self.setSizePolicy(QSizePolicy.Expanding, QSizePolicy.Expanding)
        self.setMouseTracking(True)

    # ---- 数据接口 ----
    def values(self):
        return list(self.vals)

    def set_values(self, vals):
        self.vals = [max(0, min(255, int(v))) for v in vals[:self.n]]
        self.vals += [0] * (self.n - len(self.vals))
        self.changed.emit()
        self.update()

    # ---- 鼠标 ----
    def _geom(self):
        w, h = self.width(), self.height()
        pad_l, pad_r, pad_t, pad_b = 30, 6, 8, 18
        n = self.n
        step = (w - pad_l - pad_r) / float(n)
        bw = max(5.0, step - 6.0)
        return w, h, pad_l, pad_r, pad_t, pad_b, step, bw

    def _apply_at(self, pos):
        w, h, pad_l, pad_r, pad_t, pad_b, step, bw = self._geom()
        x, y = pos.x(), pos.y()
        idx = int((x - pad_l) / step)
        if not (0 <= idx < self.n):
            return
        plot_h = h - pad_t - pad_b
        v = int(round((h - pad_b - y) * 255.0 / plot_h))
        v = max(0, min(255, v))
        if self.vals[idx] != v:
            self.vals[idx] = v
            self.changed.emit()
            self.update()

    def mousePressEvent(self, ev):
        self._drag = True
        self._apply_at(ev.pos())

    def mouseMoveEvent(self, ev):
        if self._drag:
            self._apply_at(ev.pos())

    def mouseReleaseEvent(self, ev):
        self._drag = False

    # ---- 绘制 ----
    def paintEvent(self, ev):
        p = QPainter(self)
        p.setRenderHint(QPainter.Antialiasing, True)
        w, h, pad_l, pad_r, pad_t, pad_b, step, bw = self._geom()
        plot_h = h - pad_t - pad_b

        # 网格 + 刻度
        p.setPen(QPen(QColor("#262b34"), 1))
        for i in range(1, 4):
            y = pad_t + plot_h * i / 4.0
            p.drawLine(pad_l - 4, int(y), w - pad_r, int(y))
        p.setPen(QColor("#6b7381"))
        p.setFont(QFont("Consolas", 8))
        for i in range(0, 4):
            v = 255 * (4 - i) / 4.0
            y = pad_t + plot_h * i / 4.0
            p.drawText(QRectF(0, y - 7, pad_l - 6, 14),
                       Qt.AlignRight | Qt.AlignVCenter, "%.0f" % v)

        for ch in range(self.n):
            x = pad_l + ch * step + (step - bw) / 2.0
            v = self.vals[ch]
            hv = plot_h * v / 255.0
            p.setPen(Qt.NoPen)
            # 底槽
            p.setBrush(QColor("#20242c"))
            p.drawRoundedRect(QRectF(x, pad_t, bw, plot_h), 3, 3)
            # 幅度条（奇次泛音略亮，帮助看出"方波=奇次"这类结构）
            c = QColor("#35d0ba") if ch % 2 == 0 else QColor("#2a9c8b")
            p.setBrush(c)
            if hv >= 2.0:
                p.drawRoundedRect(QRectF(x, pad_t + plot_h - hv, bw, hv), 3, 3)
            # 谐波序号
            p.setPen(QColor("#8b98a8"))
            p.setFont(QFont("Consolas", 7))
            p.drawText(QRectF(x - 3, h - pad_b + 2, bw + 6, 14),
                       Qt.AlignHCenter, str(ch + 1))
            # 幅度值（非 0 才画，避免糊成一排数字；满幅时夹回绘图区内）
            if v > 0:
                ty = max(pad_t + 1.0, pad_t + plot_h - hv - 14)
                p.setPen(QColor("#f0c46a"))
                p.setFont(QFont("Consolas", 7, QFont.Bold))
                p.drawText(QRectF(x - 6, ty, bw + 12, 12),
                           Qt.AlignHCenter, str(v))
        p.end()


# =============================================================================
#  电极遥测柱（自绘：base 暗条 + raw 亮条 + 判定颜色）
# =============================================================================
class ElectrodeBars(QWidget):
    def __init__(self):
        super().__init__()
        self.data = {}          # ch -> (base, raw)
        self.sel = 0
        self.setMinimumHeight(200)
        self.setSizePolicy(QSizePolicy.Expanding, QSizePolicy.Expanding)

    def set_point(self, ch, base, raw):
        self.data[ch] = (base, raw)
        self.update()

    def clear(self):
        self.data = {}
        self.update()

    def paintEvent(self, ev):
        p = QPainter(self)
        p.setRenderHint(QPainter.Antialiasing, True)
        w, h = self.width(), self.height()
        n = 16
        pad_l, pad_r, pad_t, pad_b = 34, 8, 6, 18
        bw = max(4.0, (w - pad_l - pad_r) / float(n) - 6.0)
        maxv = 1.0
        for b, r in self.data.values():
            maxv = max(maxv, b or 0, r or 0)
        maxv = max(maxv * 1.15, 60.0)

        # 网格 + 刻度
        p.setPen(QPen(QColor("#262b34"), 1))
        for i in range(1, 4):
            y = pad_t + (h - pad_t - pad_b) * i / 4.0
            p.drawLine(pad_l - 4, int(y), w - pad_r, int(y))
        p.setPen(QColor("#6b7381"))
        p.setFont(QFont("Consolas", 8))
        for i in range(0, 4):
            v = maxv * (4 - i) / 4.0
            y = pad_t + (h - pad_t - pad_b) * i / 4.0
            p.drawText(QRectF(0, y - 7, pad_l - 6, 14),
                       Qt.AlignRight | Qt.AlignVCenter, "%.0f" % v)

        for ch in range(n):
            x = pad_l + ch * (bw + 6.0)
            base, raw = self.data.get(ch, (None, None))
            if base is None:
                continue
            txt, col = verdict(base, raw)
            colmap = {"green": "#35d0ba", "red": "#e05a5a",
                      "dim": "#4a5b6b", "gray": "#333a45"}
            c = QColor(colmap.get(col, "#4a5b6b"))
            if ch == self.sel:
                p.setPen(QPen(QColor("#f0c46a"), 2))
                p.setBrush(Qt.NoBrush)
                p.drawRoundedRect(QRectF(x - 3, pad_t - 3, bw + 6,
                                         h - pad_t - pad_b + 6), 5, 5)
            # base 暗条
            hb = (h - pad_t - pad_b) * (base / maxv)
            p.setPen(Qt.NoPen)
            p.setBrush(QColor("#2b3140"))
            p.drawRoundedRect(QRectF(x, h - pad_b - hb, bw, hb), 3, 3)
            # raw 亮条
            hr = (h - pad_t - pad_b) * ((raw or 0) / maxv)
            p.setBrush(c)
            p.drawRoundedRect(QRectF(x, h - pad_b - hr, bw, hr), 3, 3)
            # 通道号
            p.setPen(QColor("#f0c46a") if ch == self.sel else QColor("#8b98a8"))
            p.setFont(QFont("Consolas", 8, QFont.Bold if ch == self.sel else QFont.Normal))
            p.drawText(QRectF(x - 3, h - pad_b + 2, bw + 6, 14),
                       Qt.AlignHCenter, str(ch))
        p.end()


# =============================================================================
#  主窗口
# =============================================================================
class MainWindow(QMainWindow):
    def __init__(self):
        super().__init__()
        self.setWindowTitle("FPGA 加法合成器 · 上位机 v2  (协议 v1.0 + A1 逐声部塑形)")
        self.resize(1420, 920)
        self.link = None
        self.journal = []                    # [(addr, data, note)] —— 可导出重放
        self.sent_total = 0
        self._rate = []                      # [(t, total)]
        self.ele = {}
        self.scan_i = -1
        self.held = {}
        self.octave = 0                      # 键盘八度移位（±2 上限）
        self._build_ui()
        self._load_theme()

        self.timer = QTimer(self)
        self.timer.timeout.connect(self._tick)
        self.timer.start(200)
        self.scan_timer = QTimer(self)
        self.scan_timer.timeout.connect(self._scan_step)
        self.log("就绪 ✓ 顶部可切「模拟设备」（无板自测）或选串口连接 ✓")
        self.log("演奏线：键盘 Z X C V B N M , = 五声音阶 8 键（与板上电极布局一致，八度可移）✓")
        self.log("塑谱线：按住鼠标在 16 根泛音条上拖动即可画谱；可指定只刷新某个声部（A1）✓")
        self.log("脱机线：底部定序器面板下载曲谱并播放，不依赖电脑演奏 ✓")

    # ---------------- UI ----------------
    def _build_ui(self):
        root = QWidget()
        self.setCentralWidget(root)
        outer = QVBoxLayout(root)
        outer.setContentsMargins(10, 8, 10, 8)
        outer.setSpacing(8)

        # ===== 顶栏 =====
        top = QFrame()
        top.setObjectName("TopBar")
        th = QHBoxLayout(top)
        th.setContentsMargins(10, 8, 10, 8)
        th.setSpacing(10)
        self.cmb_port = QComboBox()
        self.cmb_port.setMinimumWidth(190)
        self.btn_refresh = QPushButton("刷新端口")
        self.btn_refresh.clicked.connect(self._fill_ports)
        self.btn_conn = QPushButton("连接")
        self.btn_conn.setObjectName("Primary")
        self.btn_conn.clicked.connect(self._toggle_conn)
        self.badge = QLabel("未连接")
        self.badge.setObjectName("BadgeOff")
        self.lab_detail = QLabel("")
        self.lab_detail.setStyleSheet("color:#8b98a8;")
        self.lab_tick = QLabel("已发 0 B · 0.0 B/s")
        self.lab_tick.setObjectName("Ticker")
        self.btn_export = QPushButton("导出帧序列")
        self.btn_export.clicked.connect(self._export)
        th.addWidget(QLabel("端口"))
        th.addWidget(self.cmb_port)
        th.addWidget(self.btn_refresh)
        th.addWidget(self.btn_conn)
        th.addWidget(self.badge)
        th.addWidget(self.lab_detail, 1)
        th.addWidget(self.lab_tick)
        th.addWidget(self.btn_export)
        outer.addWidget(top)

        # ===== 主体：三列（演奏 | 塑谱 | 遥测调试）=====
        body = QHBoxLayout()
        body.setSpacing(8)

        # ---------- 左列：演奏 ----------
        colL = QVBoxLayout()
        colL.setSpacing(8)

        # --- 键盘卡 ---
        c, v = card("键盘（左手 · 五声音阶 · 八度可移）")
        octrow = QHBoxLayout()
        octrow.addWidget(QLabel("八度"))
        b = QPushButton("−")
        b.setFixedWidth(36)
        b.clicked.connect(lambda: self._shift_octave(-1))
        octrow.addWidget(b)
        self.lab_oct = QLabel("C4 – E5")
        self.lab_oct.setObjectName("Ticker")
        self.lab_oct.setAlignment(Qt.AlignHCenter)
        octrow.addWidget(self.lab_oct, 1)
        b = QPushButton("＋")
        b.setFixedWidth(36)
        b.clicked.connect(lambda: self._shift_octave(+1))
        octrow.addWidget(b)
        v.addLayout(octrow)
        kb = QHBoxLayout()
        kb.setSpacing(4)
        self.key_btns = []
        for i, m in enumerate(PENTA):
            b = QPushButton("%s\n%d" % (midi_name(m), m))
            b.setProperty("white", "true")
            b.pressed.connect(lambda idx=i: self.note_on(idx))
            b.released.connect(lambda idx=i: self.note_off(idx))
            b.setToolTip("MIDI %d（电脑键 %s）" % (m, KEYMAP[i]))
            kb.addWidget(b)
            self.key_btns.append(b)
        v.addLayout(kb)
        row = QHBoxLayout()
        row.addWidget(QLabel("力度"))
        self.sld_vel = QSlider(Qt.Horizontal)
        self.sld_vel.setRange(0, 15)
        self.sld_vel.setValue(12)
        self.lab_vel = QLabel("12/15")
        self.lab_vel.setObjectName("Ticker")
        self.sld_vel.valueChanged.connect(lambda x: self.lab_vel.setText("%d/15" % x))
        row.addWidget(self.sld_vel, 1)
        row.addWidget(self.lab_vel)
        v.addLayout(row)
        colL.addWidget(c)

        # --- 表情轴卡 ---
        c1, v1 = card("表情轴（颤音 / 滑音 —— M1「独立可控」演示面板）")
        grid = QGridLayout()
        grid.setHorizontalSpacing(8)
        grid.setVerticalSpacing(6)
        self.chk_vib = QCheckBox("颤音")
        self.chk_vib.toggled.connect(self._expr_toggled)
        grid.addWidget(self.chk_vib, 0, 0)
        grid.addWidget(QLabel("深度"), 0, 1)
        self.sld_vib_depth = QSlider(Qt.Horizontal)
        self.sld_vib_depth.setRange(0, 1000)
        self.sld_vib_depth.setValue(400)
        self.sld_vib_depth.sliderReleased.connect(self.send_expression)
        grid.addWidget(self.sld_vib_depth, 0, 2)
        self.lab_vib_depth = QLabel("400")
        self.lab_vib_depth.setObjectName("Ticker")
        self.sld_vib_depth.valueChanged.connect(
            lambda x: self.lab_vib_depth.setText(str(x)))
        grid.addWidget(self.lab_vib_depth, 0, 3)
        grid.addWidget(QLabel("速率"), 1, 1)
        self.sld_vib_rate = QSlider(Qt.Horizontal)
        self.sld_vib_rate.setRange(5, 80)          # 0.5 – 8.0 Hz
        self.sld_vib_rate.setValue(55)             # 5.5 Hz
        self.sld_vib_rate.sliderReleased.connect(self.send_expression)
        grid.addWidget(self.sld_vib_rate, 1, 2)
        self.lab_vib_rate = QLabel("5.5 Hz")
        self.lab_vib_rate.setObjectName("Ticker")
        self.sld_vib_rate.valueChanged.connect(
            lambda x: self.lab_vib_rate.setText("%.1f Hz" % (x / 10.0)))
        grid.addWidget(self.lab_vib_rate, 1, 3)
        self.chk_glide = QCheckBox("滑音")
        self.chk_glide.toggled.connect(self._expr_toggled)
        grid.addWidget(self.chk_glide, 2, 0)
        grid.addWidget(QLabel("步长"), 2, 1)
        self.sld_glide = QSlider(Qt.Horizontal)
        self.sld_glide.setRange(0, 1023)
        self.sld_glide.setValue(64)
        self.sld_glide.sliderReleased.connect(self.send_expression)
        grid.addWidget(self.sld_glide, 2, 2)
        self.lab_glide = QLabel("64")
        self.lab_glide.setObjectName("Ticker")
        self.sld_glide.valueChanged.connect(
            lambda x: self.lab_glide.setText(str(x)))
        grid.addWidget(self.lab_glide, 2, 3)
        v1.addLayout(grid)
        hint = QLabel("演示动作：颤音✓ + 滑音✓ 同时开，两个滑条反方向拖 → 示波器上各自独立变化")
        hint.setObjectName("Hint")
        hint.setWordWrap(True)
        v1.addWidget(hint)
        colL.addWidget(c1)

        # --- 音色与效果卡 ---
        c2, v2 = card("音色与效果")
        row2 = QHBoxLayout()
        row2.addWidget(QLabel("音色"))
        for nm, v_ in PRESETS:
            b = QPushButton(nm)
            b.clicked.connect(lambda _c=False, val=v_: self.set_preset(val))
            row2.addWidget(b)
        v2.addLayout(row2)
        row3 = QHBoxLayout()
        row3.addWidget(QLabel("效果"))
        for nm, key in FXS:
            b = QPushButton(nm)
            b.clicked.connect(lambda _c=False, k=key: self.set_fx(k))
            row3.addWidget(b)
        v2.addLayout(row3)
        colL.addWidget(c2)
        colL.addStretch(1)
        body.addLayout(colL, 10)

        # ---------- 中列：塑谱 ----------
        colM = QVBoxLayout()
        colM.setSpacing(8)
        c3, v3 = card("塑谱（右手 · 16 泛音幅度 → 0x58/0x59/0x5A + A1 逐声部刷新）")
        self.spec = SpectrumBars(16)
        self.spec.set_values(SPECTRA[0][1])
        self.spec.changed.connect(self._spec_changed)
        v3.addWidget(self.spec)
        row4 = QHBoxLayout()
        self.chk_replace = QCheckBox("替换模式（只用谱；不勾=叠加预设底谱）")
        row4.addWidget(self.chk_replace)
        row4.addWidget(QLabel("刷新目标"))
        self.cmb_voice = QComboBox()
        self.cmb_voice.addItem("全部声部（0xFF 全刷）")
        for i in range(32):
            self.cmb_voice.addItem("声部 %d" % i)
        self.cmb_voice.setMinimumWidth(150)
        row4.addWidget(self.cmb_voice)
        row4.addStretch(1)
        v3.addLayout(row4)
        row5 = QHBoxLayout()
        b = QPushButton("下发谱 + 刷新")
        b.setObjectName("Primary")
        b.clicked.connect(self.send_spectrum)
        row5.addWidget(b)
        for nm, vals in SPECTRA:
            b = QPushButton(nm)
            b.clicked.connect(lambda _c=False, vv=vals: self.spec.set_values(vv))
            row5.addWidget(b)
        row5.addStretch(1)
        v3.addLayout(row5)
        self.lab_spec = QLabel("")
        self.lab_spec.setObjectName("Hint")
        self.lab_spec.setWordWrap(True)
        self._spec_changed()
        v3.addWidget(self.lab_spec)
        hint2 = QLabel("逐声部塑形（A1）：① 选「声部 0」→ 画谱 → 下发；② 改谱 → 选「声部 1」→ 下发；\n"
                       "两个音同时响时各用各的谱 —— 这是与拉杆风琴「全局注册」的本质差异")
        hint2.setObjectName("Hint")
        hint2.setWordWrap(True)
        v3.addWidget(hint2)
        colM.addWidget(c3)
        colM.addStretch(1)
        body.addLayout(colM, 11)

        # ---------- 右列：遥测与调试 ----------
        colR = QVBoxLayout()
        colR.setSpacing(8)

        # --- 电极遥测卡 ---
        c4, v4 = card("电极遥测（上板 bring-up 第 0 步：量 RC 量程）")
        self.bars = ElectrodeBars()
        v4.addWidget(self.bars)
        row6 = QHBoxLayout()
        row6.addWidget(QLabel("通道"))
        self.cmb_ch = QComboBox()
        self.cmb_ch.addItems([str(i) for i in range(16)])
        self.cmb_ch.currentIndexChanged.connect(self._sel_ch)
        row6.addWidget(self.cmb_ch)
        b = QPushButton("扫描 16 路")
        b.setObjectName("Primary")
        b.clicked.connect(self.scan_all)
        row6.addWidget(b)
        self.chk_autoscan = QCheckBox("自动循环")
        self.chk_autoscan.setToolTip("每 ~1.3 s 重扫一遍 16 路（调试基线漂移用）")
        self.chk_autoscan.toggled.connect(self._autoscan_toggled)
        row6.addWidget(self.chk_autoscan)
        self.chk_touch = QCheckBox("模拟触摸（仅模拟设备）")
        self.chk_touch.stateChanged.connect(self._touch_changed)
        self.chk_touch.setEnabled(False)
        row6.addWidget(self.chk_touch)
        row6.addStretch(1)
        v4.addLayout(row6)
        self.lab_verd = QLabel("—")
        self.lab_verd.setObjectName("Ticker")
        self.lab_verd.setWordWrap(True)
        v4.addWidget(self.lab_verd)
        colR.addWidget(c4)

        # --- 寄存器表卡 ---
        c5, v5 = card("寄存器（A3 回读：写 [0x0F][addr] → 回两字节）")
        self.tbl = QTableWidget(len(SHOW_REGS), 3)
        self.tbl.setHorizontalHeaderLabels(["地址", "名称", "值"])
        self.tbl.verticalHeader().setVisible(False)
        self.tbl.setEditTriggers(QTableWidget.NoEditTriggers)
        self.tbl.setAlternatingRowColors(True)
        self.tbl.horizontalHeader().setSectionResizeMode(0, QHeaderView.ResizeToContents)
        self.tbl.horizontalHeader().setSectionResizeMode(1, QHeaderView.Stretch)
        self.tbl.horizontalHeader().setSectionResizeMode(2, QHeaderView.ResizeToContents)
        for i, nm in enumerate(SHOW_REGS):
            a = dh.REG.get(nm)
            self.tbl.setItem(i, 0, QTableWidgetItem("0x%02X" % a if a is not None else "--"))
            self.tbl.setItem(i, 1, QTableWidgetItem(nm))
            self.tbl.setItem(i, 2, QTableWidgetItem("--"))
        self.tbl.setMinimumHeight(200)
        v5.addWidget(self.tbl)
        row7 = QHBoxLayout()
        b = QPushButton("回读全部")
        b.clicked.connect(self.read_all)
        row7.addWidget(b)
        row7.addStretch(1)
        v5.addLayout(row7)
        colR.addWidget(c5)
        colR.addStretch(1)
        body.addLayout(colR, 10)

        outer.addLayout(body, 1)

        # ===== 定序器卡（脱机演示线）=====
        c6, v6 = card("定序器（脱机演示线：下载曲谱 → 播放，不依赖电脑实时演奏）")
        sq = QHBoxLayout()
        sq.setSpacing(8)
        sq.addWidget(QLabel("BPM"))
        self.spin_bpm = QSpinBox()
        self.spin_bpm.setRange(40, 240)
        self.spin_bpm.setValue(120)
        self.spin_bpm.setToolTip("每拍时钟数 = BPM/60 × 2^24 / fs（PC 算好除法，RTL 只做加法）")
        sq.addWidget(self.spin_bpm)
        sq.addWidget(QLabel("曲谱（音高:拍数，逗号分隔）"))
        self.ed_score = QLineEdit(DEMO_SCORE_TEXT)
        sq.addWidget(self.ed_score, 1)
        self.lab_seq = QLabel("")
        self.lab_seq.setObjectName("Ticker")
        self._seq_status()
        self.ed_score.textChanged.connect(lambda _t: self._seq_status())
        sq.addWidget(self.lab_seq)
        b = QPushButton("下载曲谱")
        b.clicked.connect(self.seq_download)
        sq.addWidget(b)
        b = QPushButton("▶ 下载并播放")
        b.setObjectName("Primary")
        b.clicked.connect(self.seq_play)
        sq.addWidget(b)
        b = QPushButton("■ 停止")
        b.setObjectName("Danger")
        b.clicked.connect(self.seq_stop)
        sq.addWidget(b)
        v6.addLayout(sq)
        outer.addWidget(c6)

        # --- 日志 ---
        self.logbox = QPlainTextEdit()
        self.logbox.setReadOnly(True)
        self.logbox.setMaximumHeight(130)
        outer.addWidget(self.logbox)

        self._fill_ports()

    def _load_theme(self):
        # 打包后 theme.qss 在 _MEIPASS 里 ⇒ 用 find_file 找（源码/onefile 两用）
        p = find_file("theme.qss")
        if p:
            with open(p, encoding="utf-8") as fh:
                self.setStyleSheet(fh.read())

    # ---------------- 工具 ----------------
    def log(self, s):
        self.logbox.appendPlainText("[%s] %s" % (time.strftime("%H:%M:%S"), s))

    def send_frames(self, frames, what):
        if frames is None:
            self.log("✗ %s：命令构造失败" % what)
            return
        if self.link is None:
            self.log("✗ 未连接：%s（可切「模拟设备」先试）" % what)
            return
        n = self.link.send(frames)
        self.sent_total += n
        for a, d, note in frames.items:
            self.journal.append((a, d, note))
        self.log("→ %s：%d 帧 / %d 字节   %s" % (what, len(frames.items), n,
                 "  ".join("%s=0x%02X" % (addr_name(a), d) for a, d, _ in frames.items[:4])))
        self._tick_rate()

    def _ctrl_val(self):
        """CTRL：bit3=preset_src(寄存器) 固定 1，bit1/2 跟随表情轴开关。"""
        v = 0x08
        if self.chk_vib.isChecked():
            v |= 0x02
        if self.chk_glide.isChecked():
            v |= 0x04
        return v

    # ---------------- 演奏 ----------------
    def note_on(self, idx):
        if idx in self.held:
            return
        midi = PENTA[idx] + 12 * self.octave
        vel = self.sld_vel.value()
        self.held[idx] = midi
        self.send_frames(dh.cmd_note("on:%d:%d" % (midi, vel)),
                         "音符开 %s" % midi_name(midi))

    def note_off(self, idx):
        if idx not in self.held:
            return
        midi = self.held.pop(idx)
        self.send_frames(dh.cmd_note("off:%d" % midi),
                         "音符关 %s" % midi_name(midi))

    def _shift_octave(self, d):
        self.octave = max(-2, min(2, self.octave + d))
        for i, b in enumerate(self.key_btns):
            m = PENTA[i] + 12 * self.octave
            b.setText("%s\n%d" % (midi_name(m), m))
            b.setToolTip("MIDI %d（电脑键 %s）" % (m, KEYMAP[i]))
        self.lab_oct.setText("%s – %s%s" % (midi_name(PENTA[0] + 12 * self.octave),
                                            midi_name(PENTA[-1] + 12 * self.octave),
                                            {0: "", 1: "（+1oct）", -1: "（−1oct）",
                                             2: "（+2oct）", -2: "（−2oct）"}[self.octave]))

    # ---------------- 表情轴 ----------------
    def _expr_toggled(self, _on):
        self.send_expression()

    def send_expression(self):
        f = dh.Frames()
        f.w("CTRL", self._ctrl_val(), "CTRL（bit1 颤音 / bit2 滑音 / bit3 preset_src）")
        if self.chk_vib.isChecked():
            f.w16("VIB_DEPTH", self.sld_vib_depth.value(),
                  "颤音深度（音分×100 尺度）")
            hz = self.sld_vib_rate.value() / 10.0
            f.w24("VIB_INC", int(round(hz * (1 << 24) / dh.FS)),
                  "颤音速率 %.1f Hz（Q24 每样本增量）" % hz)
        if self.chk_glide.isChecked():
            f.w16("GLIDE_STEP", self.sld_glide.value(), "滑音每样本步进")
        self.send_frames(f, "表情轴")

    # ---------------- 音色 / 效果 ----------------
    def set_preset(self, v):
        f = dh.Frames()
        f.w("PRESET", v & 0x03, "音色预设 %d" % v)
        f.w("CTRL", self._ctrl_val(), "preset_src=寄存器（bit3）+ 表情轴开关")
        self.send_frames(f, "音色预设 %d" % v)

    def set_fx(self, key):
        self.send_frames(dh.cmd_fx(key), "效果器 %s" % key)

    # ---------------- 塑谱 ----------------
    def _spec_changed(self):
        vals = self.spec.values()
        self.lab_spec.setText("当前谱：%s" % ",".join(str(x) for x in vals))

    def send_spectrum(self):
        vals = self.spec.values()
        mode = "replace" if self.chk_replace.isChecked() else "add"
        vi = self.cmb_voice.currentIndex()
        self.send_frames(dh.cmd_spectrum(mode, vals), "塑谱（%s）" % mode)
        # 显式刷新：全部（0xFF）或单个声部（A1: 0–31）。
        #   叠加模式写 0x5A 时 RTL 会自动刷在响声部；这里补显式刷新是
        #   「界面替用户兜底」，保证"改了必生效"，且逐声部目标只有这条路能到。
        if vi <= 0:
            self.send_frames(dh.cmd_refresh("all"), "全刷（替换模式必须）")
        else:
            self.send_frames(dh.cmd_refresh(str(vi - 1)),
                             "刷新声部 %d 谱形（A1 逐声部塑形）" % (vi - 1))

    # ---------------- 定序器 ----------------
    def _seq_status(self):
        n = len([t for t in self.ed_score.text().split(",") if t.strip()])
        self.lab_seq.setText("%d 步 · 每拍 %d" % (n, dh.tempo_inc(self.spin_bpm.value())))

    def _parse_score(self):
        notes = []
        for tok in self.ed_score.text().split(","):
            tok = tok.strip()
            if not tok:
                continue
            p = tok.split(":")
            try:
                n = int(p[0])
                b = int(p[1]) if len(p) > 1 else 1
            except (ValueError, IndexError):
                QMessageBox.warning(self, "曲谱格式",
                                    "看不懂这一段：%r\n格式应为 音高:拍数，如 64:1（音高 0–127，拍数 1–255）" % tok)
                return None
            if not (0 <= n <= 127 and 1 <= b <= 255):
                QMessageBox.warning(self, "曲谱格式",
                                    "这一段超出范围：%r（音高 0–127，拍数 1–255）" % tok)
                return None
            notes.append((n, b))
        if not notes:
            QMessageBox.warning(self, "曲谱为空", "请先填入至少一步「音高:拍数」")
            return None
        return notes

    def _seq_frames(self, notes, enable):
        """下载（enable=False）或下载并启动（enable=True）。
        使能必须放在最后一步写 —— 曲谱装载完成后才允许定序器跑起来。"""
        bpm = self.spin_bpm.value()
        f = dh.Frames()
        f.w24("TEMPO", dh.tempo_inc(bpm), "节拍 %d BPM（Q24 每样本增量）" % bpm)
        f.w("SEQ_VEL", 0xC0, "定序器力度 12/15")
        f.score(notes)
        if enable:
            # SEQ_CTRL=0x05：bit0 使能 + bit2 使用下载曲谱（RTL 现行语义；
            #   冻结文档 A6 与此有分歧，GUI 跟随 RTL/CLI 同款写法）
            f.w("SEQ_CTRL", 0x01, "使能定序器（A6：SCORE_LEN>0 即用下载曲谱）")
        return f

    def seq_download(self):
        notes = self._parse_score()
        if notes is None:
            return
        self.send_frames(self._seq_frames(notes, enable=False),
                         "下载曲谱 %d 步 @%d BPM" % (len(notes), self.spin_bpm.value()))

    def seq_play(self):
        notes = self._parse_score()
        if notes is None:
            return
        self.send_frames(self._seq_frames(notes, enable=True),
                         "播放曲谱 %d 步 @%d BPM" % (len(notes), self.spin_bpm.value()))

    def seq_stop(self):
        f = dh.Frames()
        f.w("SEQ_CTRL", 0x00, "停定序器")
        self.send_frames(f, "停止定序器")

    # ---------------- 遥测 ----------------
    def _sel_ch(self, i):
        self.bars.sel = i
        self.bars.update()
        if self.link is not None:
            f = dh.Frames()
            f.w("PAD_SEL", i & 0x0F, "遥测通道 %d" % i)
            self.send_frames(f, "选遥测通道 %d" % i)

    def _touch_changed(self, st):
        if isinstance(self.link, SimLink):
            self.link.set_touch(st == Qt.Checked)

    def _autoscan_toggled(self, on):
        if on:
            self.scan_all()
        else:
            self.scan_i = -1
            self.scan_timer.stop()

    def _read_pair(self, lo, hi):
        a = self.link.read_reg(TEL[lo])
        b = self.link.read_reg(TEL[hi])
        if a is None or b is None:
            return None
        return ((b & 0x0F) << 8) | a

    def _refresh_bars(self):
        i = self.cmb_ch.currentIndex()
        base = self._read_pair("PAD_BASE_LO", "PAD_BASE_HI")
        raw = self._read_pair("PAD_RAW_LO", "PAD_RAW_HI")
        if base is None or raw is None:
            self.lab_verd.setText("回读失败 ✗（板子在跑吗？协议是写 [0x0F][addr] 回两字节）")
            return
        self.ele[i] = (base, raw)
        self.bars.set_point(i, base, raw)
        t, c = verdict(base, raw)
        self.lab_verd.setText("通道 %d：base %d / raw %d ⇒ %s" % (i, base, raw, t))

    def scan_all(self):
        if self.link is None:
            self.log("✗ 未连接：无法扫描")
            self.chk_autoscan.setChecked(False)
            return
        self.ele = {}
        self.bars.clear()
        self.scan_i = 0
        self.log("开始扫描 16 路电极（每路写 PAD_SEL 后等 80 ms 让遥测刷新）…")
        self.scan_timer.start(80)

    def _scan_step(self):
        if self.scan_i is None or self.scan_i > 15:
            self.scan_timer.stop()
            self._scan_report()
            return
        i = self.scan_i
        f = dh.Frames()
        f.w("PAD_SEL", i & 0x0F, "扫描通道 %d" % i)
        self.link.send(f)
        self.sent_total += 2
        for a, d, note in f.items:
            self.journal.append((a, d, note))
        self._refresh_bars()
        self.bars.sel = i
        self.bars.update()
        self.scan_i += 1
        self._tick_rate()
        if self.scan_i > 15:
            self.scan_timer.stop()
            self._scan_report()

    def _scan_report(self):
        bad = 0
        for i in range(16):
            if i not in self.ele:
                bad += 1
                continue
            b, r = self.ele[i]
            t, c = verdict(b, r)
            if c == "red":
                bad += 1
        if self.chk_autoscan.isChecked():
            # 自动循环模式：只报一行结论，不刷屏
            self.log("自动扫描：16 路全部可用 ✓" if bad == 0
                     else "自动扫描：%d 路需处理 ✗" % bad)
        else:
            self.log("—" * 30)
            self.log("电极量程扫描结果（判据见 步骤16 §1：松手 raw∈[20,2000]；按住 raw ≥1.3×base）")
            for i in range(16):
                if i not in self.ele:
                    self.log("  通道 %2d：无数据" % i)
                    continue
                b, r = self.ele[i]
                t, c = verdict(b, r)
                self.log("  通道 %2d：base %5d  raw %5d  ⇒ %s" % (i, b, r, t))
            self.log("—" * 30)
            self.log(("★ 16 路都在可用区间 ✓ 再逐个按住确认 raw 上升即可 ✓" if bad == 0
                      else "★ 有 %d 路需处理 ✗ 先按 步骤16 §1 调外接 R/C（建议 1MΩ + 22pF）" % bad))
        self.scan_i = -1
        # 自动循环：歇一拍再扫（避免和 200ms 的 _tick 打架）
        if self.chk_autoscan.isChecked() and self.link is not None:
            QTimer.singleShot(300, self._autoscan_restart)

    def _autoscan_restart(self):
        if self.chk_autoscan.isChecked() and self.link is not None:
            self.scan_i = 0
            self.ele = {}
            self.bars.clear()
            self.scan_timer.start(80)

    def read_all(self):
        if self.link is None:
            self.log("✗ 未连接：无法回读")
            return
        ok = 0
        for i, nm in enumerate(SHOW_REGS):
            a = dh.REG.get(nm)
            if a is None:
                continue
            v = self.link.read_reg(a)
            if v is None:
                self.tbl.setItem(i, 2, QTableWidgetItem("超时 ✗"))
                continue
            self.tbl.setItem(i, 2, QTableWidgetItem("0x%02X" % v))
            ok += 1
        self.log("回读 %d 个寄存器 ✓（写 [0x0F][addr] → 回两字节）" % ok)

    # ---------------- 连接 ----------------
    def _fill_ports(self):
        self.cmb_port.clear()
        self.cmb_port.addItem("【模拟设备】进程内自测，无硬件")
        for p in list_ports():
            self.cmb_port.addItem(p)
        if self.cmb_port.count() == 1:
            self.log("未发现串口（pyserial 未装或没有设备）⇒ 可用「模拟设备」自测 ✓")

    def _toggle_conn(self):
        if self.link is not None:
            self.link.close()
            self.link = None
            self.badge.setText("未连接")
            self.badge.setObjectName("BadgeOff")
            self.badge.setStyleSheet("")
            self.btn_conn.setText("连接")
            self.btn_conn.setObjectName("Primary")
            self.chk_touch.setEnabled(False)
            self.chk_autoscan.setChecked(False)
            self.log("已断开")
            self._restyle()
            return
        sel = self.cmb_port.currentText()
        try:
            if sel.startswith("【模拟设备】"):
                self.link = SimLink()
                self.chk_touch.setEnabled(True)
            else:
                self.link = SerialLink(sel)
                self.chk_touch.setEnabled(False)
            self.link.open()
        except Exception as e:
            self.link = None
            QMessageBox.warning(self, "连接失败", str(e))
            self.log("✗ 连接失败：%s" % e)
            return
        real = self.link.kind == "真实串口"
        self.badge.setText(self.link.kind)
        self.badge.setObjectName("BadgeReal" if real else "BadgeSim")
        self.lab_detail.setText(self.link.detail)
        self.btn_conn.setText("断开")
        self.btn_conn.setObjectName("Danger")
        self.journal = []
        self.sent_total = 0
        self._rate = []
        self.log("已连接：%s（%s）%s" % (self.link.kind, self.link.detail,
                 "" if real else "← 这是模拟设备，不是板子 ✗"))
        self._restyle()
        # 连上先回读一轮：立刻能看到"板子活着吗 + 寄存器现在是什么状态"
        self.read_all()

    def _restyle(self):
        self.badge.style().unpolish(self.badge)
        self.badge.style().polish(self.badge)
        self.btn_conn.style().unpolish(self.btn_conn)
        self.btn_conn.style().polish(self.btn_conn)

    # ---------------- 定时 ----------------
    def _tick(self):
        if self.link is not None and self.scan_i in (-1, None):
            self._refresh_bars()
        self._tick_rate()

    def _tick_rate(self):
        self._rate.append((time.time(), self.sent_total))
        cut = time.time() - 1.0
        self._rate = [(t, n) for t, n in self._rate if t >= cut]
        if len(self._rate) >= 2:
            dt = self._rate[-1][0] - self._rate[0][0]
            dn = self._rate[-1][1] - self._rate[0][1]
            r = dn / dt if dt > 0 else 0.0
        else:
            r = 0.0
        self.lab_tick.setText("已发 %d B · %.1f B/s" % (self.sent_total, r))

    # ---------------- 导出 / 按键 ----------------
    def _export(self):
        if not self.journal:
            QMessageBox.information(self, "导出帧序列", "还没有发过任何帧 ✓")
            return
        p, _ = QFileDialog.getSaveFileName(self, "导出帧序列（可在仿真里原样重放）",
                                           "gui_frames.txt", "文本 (*.txt)")
        if not p:
            return
        with open(p, "w", encoding="utf-8") as fh:
            fh.write("# addr data  （dsp_gui.py 导出；与 dsp_host.py --emit 同格式，"
                     "可被仿真测试台原样重放）\n")
            for a, d, note in self.journal:
                fh.write("%02X %02X   # %s\n" % (a, d, note))
        self.log("已导出 %d 帧 → %s ✓" % (len(self.journal), p))

    def keyPressEvent(self, ev):
        if ev.isAutoRepeat():
            return
        t = ev.text().upper()
        if t in KEYMAP:
            self.note_on(KEYMAP.index(t))
        else:
            super().keyPressEvent(ev)

    def keyReleaseEvent(self, ev):
        if ev.isAutoRepeat():
            return
        t = ev.text().upper()
        if t in KEYMAP:
            self.note_off(KEYMAP.index(t))
        else:
            super().keyReleaseEvent(ev)

    def closeEvent(self, ev):
        if self.link is not None:
            self.link.close()
        ev.accept()


# =============================================================================
#  离线自测：建界面 → 截图 → 校验"界面发的帧 == dsp_host 的帧"
# =============================================================================
def selftest():
    os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")
    # 离屏平台默认找不到字体目录（Qt5 不再自带字体）⇒ 指向系统字体，
    #   否则截图里没有文字 （stderr 会刷 "Cannot find font directory"）
    if os.name == "nt" and "QT_QPA_FONTDIR" not in os.environ:
        os.environ["QT_QPA_FONTDIR"] = os.path.join(os.environ.get("WINDIR", r"C:\Windows"),
                                                    "Fonts")
    lines = []

    def say(s=""):
        """同时打印（有 stdout 时）与收集到报告 ✓"""
        lines.append(s)
        _say(s)

    app = QApplication(sys.argv)
    w = MainWindow()
    w.show()
    app.processEvents()

    # 用模拟设备填充数据（让截图里遥测柱/判定都有东西）
    w.link = SimLink()
    w.link.open()
    w.badge.setText(w.link.kind)
    w.badge.setObjectName("BadgeSim")
    w.btn_conn.setText("断开")
    w.btn_conn.setObjectName("Danger")
    w.chk_touch.setEnabled(True)
    w._restyle()                       # 徽标/断开按钮换 objectName 后必须 repolish 才上色 ✓
    app.processEvents()
    w.cmb_ch.setCurrentIndex(3)
    for ch in range(16):
        w.link.send(_sel(ch))
        b = w.link.read_reg(TEL["PAD_BASE_LO"])
        bh = w.link.read_reg(TEL["PAD_BASE_HI"])
        r = w.link.read_reg(TEL["PAD_RAW_LO"])
        rh = w.link.read_reg(TEL["PAD_RAW_HI"])
        w.ele[ch] = (((bh & 0x0F) << 8) | b, ((rh & 0x0F) << 8) | r)
        w.bars.set_point(ch, w.ele[ch][0], w.ele[ch][1])
    w.bars.sel = 3
    w.sent_total = 1234
    w.lab_tick.setText("已发 %d B · 18.3 B/s" % w.sent_total)
    w.lab_verd.setText("通道 3：base 45 / raw 103 ⇒ 触摸 ✓ (2.29×)")
    for i, nm in enumerate(SHOW_REGS):
        a = dh.REG.get(nm)
        if a is not None:
            w.tbl.setItem(i, 2, QTableWidgetItem("0x%02X" % w.link.read_reg(a)))
    w.log("自测：模拟设备已填充 16 路遥测与寄存器表 ✓")
    app.processEvents()

    out = out_dir()
    if not os.path.isdir(out):
        os.makedirs(out)
    png = os.path.join(out, "gui_preview.png")
    w.grab().save(png)
    say("  已保存界面截图：%s" % png)

    # ---- 帧一致性：界面动作必须与 dsp_host 输出逐字节相同 ----
    def items(f):
        return [(a, d) for a, d, _n in f.items]

    fails = 0

    # ① 音符：界面 note_on/off ⇒ 与 cmd_note 相同（八度 0 基准）
    w.sld_vel.setValue(12)
    w.octave = 0
    w.held = {}
    w.journal = []
    w.note_on(0)                      # C4 = 60
    w.note_off(0)
    got = list(w.journal)
    want = items(dh.cmd_note("on:60:12,off:60"))
    ok = [(a, d) for a, d, _ in got] == want
    say("  [帧一致性 ①] 音符 on/off：%s" % ("一致 ✓" if ok else "不一致 ✗"))
    fails += 0 if ok else 1

    # ①b 八度移位：+1 后 C4 键 ⇒ MIDI 72
    w.held = {}
    w.journal = []
    w._shift_octave(1)
    w.note_on(0)
    w.note_off(0)
    w._shift_octave(-1)
    ok = [(a, d) for a, d, _ in w.journal] == items(dh.cmd_note("on:72:12,off:72"))
    say("  [帧一致性 ①b] 八度 +1 后同一键 = MIDI 72：%s" % ("一致 ✓" if ok else "不一致 ✗"))
    fails += 0 if ok else 1

    # ② 塑谱：界面谱值 ⇒ 与 cmd_spectrum 相同 + 显式刷新（全刷 / 逐声部）
    vals = [7, 26, 45, 64, 83, 102, 121, 140, 159, 178, 197, 216, 235, 250, 3, 99]
    w.spec.set_values(vals)
    w.chk_replace.setChecked(False)
    w.cmb_voice.setCurrentIndex(0)
    w.journal = []
    w.send_spectrum()
    got = [(a, d) for a, d, _ in w.journal]
    want = items(dh.cmd_spectrum("add", vals)) + items(dh.cmd_refresh("all"))
    ok = got == want
    say("  [帧一致性 ②] 塑谱（16 字节谱 + 全刷）：%s" % ("一致 ✓" if ok else "不一致 ✗"))
    fails += 0 if ok else 1

    # ②b 逐声部塑形：目标声部 5 ⇒ 谱 + SPEC_REFRESH=5（A1）
    w.cmb_voice.setCurrentIndex(6)          # 索引 0=全部 ⇒ 6 = 声部 5
    w.journal = []
    w.send_spectrum()
    got = [(a, d) for a, d, _ in w.journal]
    want = items(dh.cmd_spectrum("add", vals)) + items(dh.cmd_refresh("5"))
    ok = got == want
    say("  [帧一致性 ②b] 逐声部塑形（A1，声部 5）：%s" % ("一致 ✓" if ok else "不一致 ✗"))
    fails += 0 if ok else 1
    w.cmb_voice.setCurrentIndex(0)

    # ③ 效果器：界面按钮 ⇒ 与 cmd_fx 相同（顺带核对 RTL 的位定义 bit6=混响）
    w.journal = []
    w.set_fx("reverb")
    got = [(a, d) for a, d, _ in w.journal]
    want = items(dh.cmd_fx("reverb"))
    ok = got == want and want[0][1] == 0x41
    say("  [帧一致性 ③] 效果器 reverb = 0x41（bit6=混响，与 tdm_top 一致）：%s"
          % ("一致 ✓" if ok else "不一致 ✗"))
    fails += 0 if ok else 1

    # ④ 遥测选通道
    w.journal = []
    w._sel_ch(7)
    got = [(a, d) for a, d, _ in w.journal]
    ok = got == [(dh.REG["PAD_SEL"], 7)]
    say("  [帧一致性 ④] 遥测通道选择：%s" % ("一致 ✓" if ok else "不一致 ✗"))
    fails += 0 if ok else 1

    # ⑤ 表情轴：颤音✓（深度 400 @5.5Hz）滑音✗ ⇒ CTRL=0x0A + 深度 + 速率
    w.chk_vib.setChecked(True)
    w.chk_glide.setChecked(False)
    w.sld_vib_depth.setValue(400)
    w.sld_vib_rate.setValue(55)
    w.journal = []
    w.send_expression()
    got = [(a, d) for a, d, _ in w.journal]
    exp = dh.Frames()
    exp.w("CTRL", 0x0A, "")
    exp.w16("VIB_DEPTH", 400, "")
    exp.w24("VIB_INC", int(round(5.5 * (1 << 24) / dh.FS)), "")
    ok = got == items(exp)
    say("  [帧一致性 ⑤] 表情轴（颤音 400 @5.5Hz）：%s" % ("一致 ✓" if ok else "不一致 ✗"))
    fails += 0 if ok else 1

    # ⑥ 定序器：BPM 120 + 欢乐颂 8 步 ⇒ TEMPO + 力度 + 曲谱 + SEQ_CTRL=0x01
    #   0x01 而不是 0x05：曲谱源由 SCORE_LEN>0 判定（修正案 A6/A7），bit2 是无关位。
    #   本自检的期望值曾长期写着 0x05（与实现不符），导致 ⑥ 一直 FAIL、
    #   进而把被跟踪的 selftest_report.txt 一直弄脏 —— 那是"陈旧期望值"而不是产品缺陷。
    w.spin_bpm.setValue(120)
    w.ed_score.setText(DEMO_SCORE_TEXT)
    w.journal = []
    w.seq_play()
    got = [(a, d) for a, d, _ in w.journal]
    exp = dh.Frames()
    exp.w24("TEMPO", dh.tempo_inc(120), "")
    exp.w("SEQ_VEL", 0xC0, "")
    exp.score([(64, 1), (64, 1), (65, 1), (67, 1), (67, 1), (65, 1), (64, 1), (62, 2)])
    exp.w("SEQ_CTRL", 0x01, "")
    ok = got == items(exp)
    say("  [帧一致性 ⑥] 定序器下载并播放（含 SEQ_CTRL=0x01）：%s" % ("一致 ✓" if ok else "不一致 ✗"))
    fails += 0 if ok else 1

    # ⑥b 停止
    w.journal = []
    w.seq_stop()
    got = [(a, d) for a, d, _ in w.journal]
    ok = got == [(dh.REG["SEQ_CTRL"], 0x00)]
    say("  [帧一致性 ⑥b] 定序器停止 = SEQ_CTRL 0x00：%s" % ("一致 ✓" if ok else "不一致 ✗"))
    fails += 0 if ok else 1

    # ⑦ 音色预设不覆盖表情轴开关：颤音✓ 时设钢琴 ⇒ CTRL bit1 应保留
    w.chk_vib.setChecked(True)
    w.chk_glide.setChecked(False)
    w.journal = []
    w.set_preset(1)
    got = [(a, d) for a, d, _ in w.journal]
    ok = got == [(dh.REG["PRESET"], 1), (dh.REG["CTRL"], 0x0A)]
    say("  [帧一致性 ⑦] 预设保留表情轴开关（CTRL bit1）：%s" % ("一致 ✓" if ok else "不一致 ✗"))
    fails += 0 if ok else 1

    say("")
    # 报一行"打包内是否含 pyserial" →：exe 冻结后**不能**再用系统里的 pyserial，
    #   必须在打包时已安装才会被带进包 。这一行让"exe 能不能连板子"变成可检查的事实
    try:
        import serial as _s
        say("打包内含 pyserial = 有（%s）⇒ exe 可连真实串口 ✓" % _s.__version__)
    except Exception:
        say("打包内含 pyserial = 无 ✗ ⇒ exe 只能用「模拟设备」；"
            "请在有网环境 pip install pyserial 后重新打包 ✓")
    if fails == 0:
        say("RESULT gui_selftest=PASS png=%s" % png)
    else:
        say("RESULT gui_selftest=FAIL fails=%d" % fails)
    # 报告必须在 RESULT 之后再落盘 →（否则文件里没有 PASS，外部无法判定）
    #   编码用 utf-8-sig（带 BOM）：Windows 记事本/PowerShell 也能正确显示中文
    rpt = os.path.join(out, "selftest_report.txt")
    with open(rpt, "w", encoding="utf-8-sig") as fh:
        fh.write("\n".join(lines) + "\n")
    _say("报告已写出：%s" % rpt)
    return 0 if fails == 0 else 1


def _sel(ch):
    f = dh.Frames()
    f.w("PAD_SEL", ch & 0x0F, "sel")
    return f


def main():
    if "--selftest" in sys.argv:
        return selftest()
    app = QApplication(sys.argv)
    w = MainWindow()
    w.show()
    return app.exec_()


if __name__ == "__main__":
    sys.exit(main())
