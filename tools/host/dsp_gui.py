# -*- coding: utf-8 -*-
"""
dsp_gui.py —— FPGA 加法合成器上位机（PyQt5 + QSS）

用法：
    python tools/host/dsp_gui.py                # 正常启动（选串口或"模拟设备"）
    python tools/host/dsp_gui.py --selftest     # 离线自测：建界面→截图→校验帧一致性

【架构纪律（项目要求 ✓）】
  1. 协议/帧层与界面分离：界面只调 `serial_link` 的 send()/read_reg() ✓
  2. 地址表与帧构造**直接复用** `dsp_host.py`（REG / Frames / cmd_note / cmd_spectrum / cmd_fx）✓
     —— 不另抄一份 ✗，从根上防"上位机与 RTL 各改各的" ✓
  3. 顶部**明确显示**当前是「真实串口」还是「模拟设备」✗ 绝不让人误以为在跟板子说话
  4. 每个动作都进"帧流水"，可一键导出成 `dsp_host.py --emit` 同格式 ⇒ 仿真里原样重放 ✓
  5. 字节率读数常显 —— 用来直观证明"电脑只发参数级数据（~几十 B/s），音频是 FPGA 算的" ✓
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

from PyQt5.QtCore import Qt, QTimer, QRectF                 # noqa: E402
from PyQt5.QtGui import QPainter, QColor, QPen, QFont       # noqa: E402
from PyQt5.QtWidgets import (                                # noqa: E402
    QApplication, QMainWindow, QWidget, QFrame, QLabel, QPushButton,
    QVBoxLayout, QHBoxLayout, QGridLayout, QComboBox, QSlider,
    QCheckBox, QPlainTextEdit, QTableWidget, QTableWidgetItem,
    QHeaderView, QFileDialog, QMessageBox, QSizePolicy
)

# ---- 与硬件布局一致：左手 8 个五声音阶音高键（MIDI 60 62 64 67 69 72 74 76）----
PENTA = [60, 62, 64, 67, 69, 72, 74, 76]
PENTA_NAME = ["C4", "D4", "E4", "G4", "A4", "C5", "D5", "E5"]
KEYMAP = ["Z", "X", "C", "V", "B", "N", "M", ","]
PRESETS = [("管风琴", 0), ("钢琴", 1), ("钟", 2), ("马林巴", 3)]
FXS = [("干声", "dry"), ("延迟", "delay"), ("合唱", "chorus"), ("混响", "reverb")]

# 寄存器表里常显的（其余可通过回读查看）
SHOW_REGS = ["CTRL", "PRESET", "FX_CTRL", "DELAY_LEN", "RV_FB", "RV_DAMP",
             "SPEC_MODE", "HARM_PADS", "SEQ_CTRL", "TEMPO", "PROTO_VER"]


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
#  电极遥测柱（自绘：base 暗条 + raw 亮条 + 判定颜色）
# =============================================================================
class ElectrodeBars(QWidget):
    def __init__(self):
        super().__init__()
        self.data = {}          # ch -> (base, raw)
        self.sel = 0
        self.setMinimumHeight(210)
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
        self.setWindowTitle("FPGA 加法合成器 · 上位机  (v1.0 协议)")
        self.resize(1320, 860)
        self.link = None
        self.journal = []                    # [(addr, data, note)] —— 可导出重放
        self.sent_total = 0
        self._rate = []                      # [(t, total)]
        self.ele = {}
        self.scan_i = -1
        self.held = {}
        self._build_ui()
        self._load_theme()

        self.timer = QTimer(self)
        self.timer.timeout.connect(self._tick)
        self.timer.start(200)
        self.scan_timer = QTimer(self)
        self.scan_timer.timeout.connect(self._scan_step)
        self.log("就绪 ✓ 顶部可切「模拟设备」（无板自测）或选串口连接 ✓")
        self.log("提示：键盘 Z X C V B N M , 对应五声音阶 8 键（与板上电极布局一致）✓")

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

        # ===== 主体 =====
        body = QHBoxLayout()
        body.setSpacing(8)

        left = QVBoxLayout()
        left.setSpacing(8)

        # --- 键盘卡 ---
        c, v = card("键盘（左手 · 五声音阶）")
        kb = QHBoxLayout()
        kb.setSpacing(4)
        self.key_btns = []
        for i, (m, nm) in enumerate(zip(PENTA, PENTA_NAME)):
            b = QPushButton("%s\n%d" % (nm, m))
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
        row2 = QHBoxLayout()
        row2.addWidget(QLabel("音色"))
        for nm, v_ in PRESETS:
            b = QPushButton(nm)
            b.clicked.connect(lambda _c=False, val=v_: self.set_preset(val))
            row2.addWidget(b)
        row2.addSpacing(12)
        row2.addWidget(QLabel("效果"))
        for nm, key in FXS:
            b = QPushButton(nm)
            b.clicked.connect(lambda _c=False, k=key: self.set_fx(k))
            row2.addWidget(b)
        row2.addStretch(1)
        v.addLayout(row2)
        left.addWidget(c)

        # --- 塑谱卡 ---
        c2, v2 = card("塑谱（右手 · 16 泛音幅度 → 0x58/0x59/0x5A）")
        sl = QHBoxLayout()
        sl.setSpacing(3)
        self.spec = []
        demo = [255, 0, 160, 0, 120, 0, 90, 0, 70, 0, 55, 0, 40, 0, 30, 0]
        for i in range(16):
            s = QSlider(Qt.Vertical)
            s.setRange(0, 255)
            s.setValue(demo[i])
            s.setMinimumHeight(120)
            s.setToolTip("泛音 %d" % (i + 1))
            sl.addWidget(s)
            self.spec.append(s)
        v2.addLayout(sl)
        row3 = QHBoxLayout()
        self.chk_replace = QCheckBox("替换模式（只用谱；不勾=叠加预设底谱）")
        row3.addWidget(self.chk_replace)
        b = QPushButton("下发谱 + 自动刷新")
        b.setObjectName("Primary")
        b.clicked.connect(self.send_spectrum)
        row3.addWidget(b)
        b = QPushButton("只刷新全刷")
        b.clicked.connect(lambda: self.send_frames(dh.cmd_refresh("all"), "刷新全部在响声部"))
        row3.addWidget(b)
        b = QPushButton("示例谱")
        b.clicked.connect(lambda: [s.setValue(demo[i]) for i, s in enumerate(self.spec)])
        row3.addWidget(b)
        row3.addStretch(1)
        v2.addLayout(row3)
        left.addWidget(c2)
        body.addLayout(left, 3)

        right = QVBoxLayout()
        right.setSpacing(8)

        # --- 电极遥测卡 ---
        c3, v3 = card("电极遥测（上板 bring-up 第 0 步：量 RC 量程）")
        self.bars = ElectrodeBars()
        v3.addWidget(self.bars)
        row4 = QHBoxLayout()
        row4.addWidget(QLabel("通道"))
        self.cmb_ch = QComboBox()
        self.cmb_ch.addItems([str(i) for i in range(16)])
        self.cmb_ch.currentIndexChanged.connect(self._sel_ch)
        row4.addWidget(self.cmb_ch)
        b = QPushButton("扫描 16 路")
        b.setObjectName("Primary")
        b.clicked.connect(self.scan_all)
        row4.addWidget(b)
        self.chk_touch = QCheckBox("模拟触摸（仅模拟设备）")
        self.chk_touch.stateChanged.connect(self._touch_changed)
        self.chk_touch.setEnabled(False)
        row4.addWidget(self.chk_touch)
        row4.addStretch(1)
        v3.addLayout(row4)
        self.lab_verd = QLabel("—")
        self.lab_verd.setObjectName("Ticker")
        self.lab_verd.setWordWrap(True)
        v3.addWidget(self.lab_verd)
        right.addWidget(c3)

        # --- 寄存器表卡 ---
        c4, v4 = card("寄存器（A3 回读：写 [0x0F][addr] → 回两字节）")
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
        self.tbl.setMinimumHeight(210)
        v4.addWidget(self.tbl)
        b = QPushButton("回读全部")
        b.clicked.connect(self.read_all)
        v4.addWidget(b)
        right.addWidget(c4)
        body.addLayout(right, 4)

        outer.addLayout(body, 1)

        # --- 日志 ---
        self.logbox = QPlainTextEdit()
        self.logbox.setReadOnly(True)
        self.logbox.setMaximumHeight(150)
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

    def _restyle(self):
        self.badge.style().unpolish(self.badge)
        self.badge.style().polish(self.badge)
        self.btn_conn.style().unpolish(self.btn_conn)
        self.btn_conn.style().polish(self.btn_conn)

    # ---------------- 动作 ----------------
    def note_on(self, idx):
        if idx in self.held:
            return
        midi = PENTA[idx]
        vel = self.sld_vel.value()
        self.held[idx] = midi
        self.send_frames(dh.cmd_note("on:%d:%d" % (midi, vel)), "音符开 %s" % PENTA_NAME[idx])

    def note_off(self, idx):
        if idx not in self.held:
            return
        midi = self.held.pop(idx)
        self.send_frames(dh.cmd_note("off:%d" % midi), "音符关 %s" % PENTA_NAME[idx])

    def set_preset(self, v):
        f = dh.Frames()
        f.w("PRESET", v & 0x03, "音色预设 %d" % v)
        f.w("CTRL", 0x02 | 0x08, "preset_src=寄存器（bit3）")
        self.send_frames(f, "音色预设 %d" % v)

    def set_fx(self, key):
        self.send_frames(dh.cmd_fx(key), "效果器 %s" % key)

    def send_spectrum(self):
        vals = [s.value() for s in self.spec]
        mode = "replace" if self.chk_replace.isChecked() else "add"
        self.send_frames(dh.cmd_spectrum(mode, vals), "塑谱（%s）" % mode)
        # 替换模式：cmd_spectrum 写的是 0x5A=0x00（自动刷新关）⇒ 必须补一条显式刷新
        #   （这是 CLI 的既有行为，界面替用户补上，避免"改了没生效"）
        if mode == "replace":
            self.send_frames(dh.cmd_refresh("all"), "补一次全刷（替换模式必须）")

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

    # ---------------- 遥测读取 ----------------
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
        self.log("—" * 30)
        self.log("电极量程扫描结果（判据见 步骤16 §1：松手 raw∈[20,2000]；按住 raw ≥1.3×base）")
        bad = 0
        for i in range(16):
            if i not in self.ele:
                self.log("  通道 %2d：无数据" % i)
                bad += 1
                continue
            b, r = self.ele[i]
            t, c = verdict(b, r)
            if c == "red":
                bad += 1
            self.log("  通道 %2d：base %5d  raw %5d  ⇒ %s" % (i, b, r, t))
        self.log("—" * 30)
        self.log(("★ 16 路都在可用区间 ✓ 再逐个按住确认 raw 上升即可 ✓" if bad == 0
                  else "★ 有 %d 路需处理 ✗ 先按 步骤16 §1 调外接 R/C（建议 1MΩ + 22pF）" % bad))
        self.scan_i = -1

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

    # ① 音符：界面 note_on/off ⇒ 与 cmd_note 相同
    w.sld_vel.setValue(12)
    w.held = {}
    w.journal = []
    w.note_on(0)                      # C4 = 60
    w.note_off(0)
    got = list(w.journal)
    want = items(dh.cmd_note("on:60:12,off:60"))
    ok = [(a, d) for a, d, _ in got] == want
    say("  [帧一致性 ①] 音符 on/off：%s" % ("一致 ✓" if ok else "不一致 ✗"))
    fails += 0 if ok else 1

    # ② 塑谱：界面滑条值 ⇒ 与 cmd_spectrum 相同（替换模式还要多一条全刷）
    vals = [s.value() for s in w.spec]
    w.journal = []
    w.send_spectrum()
    got = [(a, d) for a, d, _ in w.journal]
    want = items(dh.cmd_spectrum("add", vals))
    if w.chk_replace.isChecked():
        want = want + items(dh.cmd_refresh("all"))
    ok = got == want
    say("  [帧一致性 ②] 塑谱（16 字节谱 + 模式%s）：%s"
          % (" + 全刷" if w.chk_replace.isChecked() else "",
             "一致 ✓" if ok else "不一致 ✗"))
    fails += 0 if ok else 1

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
