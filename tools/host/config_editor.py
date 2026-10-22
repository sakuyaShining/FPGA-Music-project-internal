"""本地乐器配置工作台。无通信依赖，所有控件只修改完整配置草稿。"""
import copy
import math

from PyQt5.QtCore import Qt, QPointF
from PyQt5.QtGui import QPainter, QColor, QPen, QPolygonF
from PyQt5.QtWidgets import (QWidget, QLabel, QPushButton, QLineEdit, QComboBox,
    QCheckBox, QSpinBox, QVBoxLayout, QHBoxLayout, QGridLayout, QFormLayout,
    QTabWidget, QFileDialog, QMessageBox, QButtonGroup, QBoxLayout, QFrame, QDoubleSpinBox)

from instrument_config import default_config, validate_config, load_config, save_config, ConfigError
from studio_theme import color


def hint(text):
    label = QLabel(text)
    label.setWordWrap(True)
    label.setObjectName("Hint")
    return label


class EnvelopePreview(QWidget):
    """归一化阶段示意，不冒充 FPGA 输出波形或混合方式试听结果。"""
    def __init__(self):
        super().__init__()
        self.level = 192
        self.setMinimumHeight(110)

    def paintEvent(self, event):
        p = QPainter(self)
        p.setRenderHint(QPainter.Antialiasing)
        w, h = self.width(), self.height()
        y = h - 25 - self.level / 255.0 * (h - 45)
        points = [QPointF(12, h-25), QPointF(w*.2, 20), QPointF(w*.42, y),
                  QPointF(w*.72, y), QPointF(w-12, h-25)]
        p.setPen(QPen(color(self, "accent"), 2))
        p.drawPolyline(QPolygonF(points))
        p.setPen(color(self, "muted"))
        for x, text in ((.08, "起音"), (.28, "衰减"), (.51, "持续"), (.8, "释放")):
            p.drawText(int(w*x), h-5, text)
        p.end()


class TimbrePreview(QWidget):
    """仅绘制同相谐波的归一化单周期示意，不生成或播放音频。"""
    def __init__(self):
        super().__init__()
        self.values = [255] + [0]*15
        self.setMinimumHeight(95)

    def paintEvent(self, event):
        p = QPainter(self)
        p.setRenderHint(QPainter.Antialiasing)
        width, height = self.width(), self.height()
        samples = [sum(a * math.sin(2*math.pi*(k+1)*i/320) for k, a in enumerate(self.values)) for i in range(321)]
        peak = max(max(abs(x) for x in samples), 1)
        points = QPolygonF([QPointF(8+i*(width-16)/320, height/2-x/peak*(height/2-14)) for i, x in enumerate(samples)])
        p.setPen(QPen(color(self, "border"), 1))
        p.drawLine(8, height//2, width-8, height//2)
        p.setPen(QPen(color(self, "accent"), 2))
        p.drawPolyline(points)
        p.end()


class ConfigEditor(QWidget):
    def __init__(self, spectrum_class, spectra, card_factory):
        super().__init__()
        self.path = None
        self._loading = True
        self.fields = {}
        self.scaled_fields = set()
        self._saved = default_config()
        outer = QVBoxLayout(self)
        outer.setContentsMargins(24, 18, 24, 14)
        outer.setSpacing(8)
        title = QLabel("音色设计")
        title.setObjectName("PageTitle")
        outer.addWidget(title)
        outer.addWidget(hint("绘制声音的分量，设定它如何开始、延续与消退。"))

        self.document_header = QFrame()
        self.document_header.setObjectName("DocumentHeader")
        header_layout = QVBoxLayout(self.document_header)
        header_layout.setContentsMargins(24, 12, 24, 12)
        toolbar = QHBoxLayout()
        self.name = QLineEdit()
        self.name.setObjectName("ConfigName")
        self.name.setMaxLength(80)
        self.name.setPlaceholderText("给这个音色起个名字")
        toolbar.addWidget(self.name, 1)
        for text, fn in (("新建", self.new_document), ("载入…", self.open_dialog),
                         ("保存", self.save_document), ("另存为…", self.save_as)):
            b = QPushButton(text)
            if text == "保存":
                b.setObjectName("Primary")
            b.clicked.connect(fn)
            toolbar.addWidget(b)
        header_layout.addLayout(toolbar)
        self.status = QLabel()
        self.status.setObjectName("Ticker")
        self.status.setWordWrap(True)
        header_layout.addWidget(self.status)
        self.file_label = hint("尚未保存到文件")
        header_layout.addWidget(self.file_label)

        body = QHBoxLayout()
        self.body_layout = body
        left = QVBoxLayout()
        c, v = card_factory("01  /  声音的构成")
        row = QHBoxLayout()
        self.preset = QComboBox()
        self.preset.addItems(["管风琴", "钢琴", "钟", "马林巴"])
        self.spectrum_mode = QComboBox()
        self.spectrum_mode.addItem("仅使用绘制谱", "replace")
        self.spectrum_mode.addItem("叠加到预设谱", "add")
        row.addWidget(QLabel("预设"))
        row.addWidget(self.preset)
        row.addWidget(self.spectrum_mode, 1)
        v.addLayout(row)
        self.spectrum = spectrum_class(16)
        self.spectrum.setMinimumHeight(220)
        v.addWidget(self.spectrum)
        precision = QHBoxLayout()
        self.part_selector = QComboBox()
        self.part_selector.addItems(["第 1 分量 · 基音"] + ["第 %d 分量" % n for n in range(2,17)])
        self.amplitude = QSpinBox()
        self.amplitude.setRange(0,255)
        self.amplitude.setSuffix(" / 255")
        precision.addWidget(self.part_selector, 1)
        precision.addWidget(self.amplitude)
        v.addLayout(precision)
        self.part_selector.currentIndexChanged.connect(self.spectrum.select)
        self.spectrum.selected.connect(self._part_selected)
        self.amplitude.valueChanged.connect(self._set_amplitude)
        row = QHBoxLayout()
        for label, values in spectra:
            button = QPushButton(label)
            button.clicked.connect(lambda checked=False, vals=values: self.spectrum.set_values(vals))
            row.addWidget(button)
        v.addLayout(row)
        v.addWidget(hint("拖动画谱，或选中分量精确输入 · 方向键微调，Shift 加速"))
        self.wave = TimbrePreview()
        v.addWidget(self.wave)
        v.addWidget(hint("绘制谱的归一化周期示意 · 同相叠加，不含预设与效果"))
        left.addWidget(c)
        guide = QPushButton("了解左、右手的演奏分工  ↗")
        guide.clicked.connect(self.show_playing_guide)
        left.addWidget(guide)
        left.addStretch()
        body.setSpacing(18)
        body.addLayout(left, 6)

        right = QVBoxLayout()
        c, v = card_factory("02  /  声音的性格")
        self.sections = QTabWidget()
        v.addWidget(self.sections)
        articulation = QWidget()
        av = QVBoxLayout(articulation)
        self.mode = QComboBox(articulation)
        for label, key in (("持续激发", "sustain"), ("瞬间激发", "strike"), ("击发 + 持续", "hybrid")):
            self.mode.addItem(label, key)
        self.mode.hide()
        modes = QHBoxLayout()
        modes.setSpacing(5)
        self.mode_buttons = []
        self.mode_group = QButtonGroup(self)
        for i, label in enumerate(("持续", "击发", "混合")):
            button = QPushButton(label)
            button.setObjectName("Mode")
            button.setCheckable(True)
            self.mode_group.addButton(button)
            button.clicked.connect(lambda checked=False, index=i: self.mode.setCurrentIndex(index))
            modes.addWidget(button)
            self.mode_buttons.append(button)
        av.addLayout(modes)
        self.mode_help = hint("")
        av.addWidget(self.mode_help)
        self.envelope = EnvelopePreview()
        av.addWidget(self.envelope)
        av.addWidget(hint("包络阶段示意 · 不按时间比例绘制"))
        form = QFormLayout()
        for label, field, high, unit in (("起音时间", "attack_ms", 60000, " ms"),
                ("衰减时间", "decay_ms", 60000, " ms"), ("持续电平", "sustain_level", 255, " / 255"),
                ("释放时间", "release_ms", 60000, " ms")):
            self._spin(form, label, ("articulation", field), high, unit)
        av.addLayout(form)
        self.hybrid = QWidget()
        hv = QVBoxLayout(self.hybrid)
        hv.setContentsMargins(0, 0, 0, 0)
        hv.addWidget(hint("候选分组：勾选为持续，未勾选为击发。仅保存草稿；混合实现尚未定案。"))
        grid = QGridLayout()
        self.parts = []
        for index in range(16):
            box = QCheckBox(str(index+1))
            self.parts.append(box)
            grid.addWidget(box, index//8, index%8)
            box.toggled.connect(self._changed)
        hv.addLayout(grid)
        av.addWidget(self.hybrid)
        av.addStretch()
        self.sections.addTab(articulation, "发声方式")

        expression = QWidget()
        ev = QVBoxLayout(expression)
        form = QFormLayout()
        self._check(form, "保存颤音开关", ("vibrato", "enabled"))
        self._spin(form, "速率", ("vibrato", "rate_millihz"), 20000, " Hz")
        self._spin(form, "深度", ("vibrato", "depth_cents"), 200, " 音分")
        ev.addLayout(form)
        ev.addWidget(hint("速率表示每秒摆动次数；100 音分 = 1 个半音。\n左手手势仍待触控输入接合，当前编辑配置参数。"))
        ev.addStretch()
        self.sections.addTab(expression, "颤音")

        effects = QWidget()
        fv = QVBoxLayout(effects)
        form = QFormLayout()
        self._check(form, "保留干声", ("effects", "dry_enabled"))
        for label, effect, specs in (
            ("延迟", "delay", (("时间", "time_ms", 2000, " ms"), ("反馈", "feedback_q8", 255, " / 255"))),
            ("合唱", "chorus", (("速率", "rate_millihz", 20000, " Hz"), ("深度", "depth_ms", 100, " ms"))),
            ("混响", "reverb", (("反馈", "feedback_q8", 255, " / 255"), ("阻尼", "damping", 7, "")))):
            self._check(form, label, ("effects", effect, "enabled"))
            for text, key, high, unit in specs:
                self._spin(form, label + " · " + text, ("effects", effect, key), high, unit)
        fv.addLayout(form)
        fv.addWidget(hint("配置范围用于保存草稿；实际设备支持的范围须由后续适配器检查。"))
        fv.addStretch()
        self.sections.addTab(effects, "效果器")
        right.addWidget(c)
        c, v = card_factory("03  /  配置概览")
        self.summary = QLabel()
        self.summary.setWordWrap(True)
        v.addWidget(self.summary)
        self.apply_button = QPushButton("应用到在奏音 · 待接入")
        self.apply_button.setEnabled(False)
        self.apply_button.setToolTip("需先完成完整配置的设备适配与在奏音状态保持验证。保存、载入不会发送设备命令。")
        v.addWidget(self.apply_button)
        v.addWidget(hint("本地草稿 · 保存 / 载入不改变设备声音"))
        right.addWidget(c)
        right.addStretch()
        body.addLayout(right, 5)
        outer.addLayout(body)
        for control in (self.name, self.preset, self.spectrum_mode, self.mode):
            signal = control.textChanged if isinstance(control, QLineEdit) else control.currentIndexChanged
            signal.connect(self._changed)
        self.spectrum.changed.connect(self._changed)
        self.set_document(default_config())

    def resizeEvent(self, event):
        super().resizeEvent(event)
        self.reflow()

    def reflow(self):
        minimum = self.fontMetrics().horizontalAdvance("宽") * 54 + 48
        self.body_layout.setDirection(QBoxLayout.TopToBottom if self.width() < minimum else QBoxLayout.LeftToRight)

    def _part_selected(self, index):
        self.part_selector.blockSignals(True)
        self.part_selector.setCurrentIndex(index)
        self.part_selector.blockSignals(False)
        self.amplitude.blockSignals(True)
        self.amplitude.setValue(self.spectrum.values()[index])
        self.amplitude.blockSignals(False)

    def _set_amplitude(self, value):
        values = self.spectrum.values()
        values[self.spectrum.selected_index] = value
        self.spectrum.set_values(values)

    def show_playing_guide(self):
        QMessageBox.information(self, "演奏分工与实现状态",
            "左手：选择音符与和弦；左右摇摆对应围绕基准音的轻微音高变化。多指移动映射仍需验证。\n\n"
            "右手：强调已有分量，双触点组合，作用于整个在奏和弦；松手保留最后结果。\n\n"
            "以上手势仍待触控与 RTL 接入。本页编辑基础配置；周期与包络曲线仅为示意，不是设备输出，也不产生声音。\n\n"
            "三种发声方式、混合分组和默认参数仍需实现与试听验收。")

    def _spin(self, form, label, path, high, suffix):
        if path[-1] == "rate_millihz":
            widget = QDoubleSpinBox()
            widget.setDecimals(3)
            widget.setSingleStep(.1)
            widget.setRange(0, high / 1000)
            self.scaled_fields.add(path)
        else:
            widget = QSpinBox()
            widget.setRange(0, high)
        widget.setSuffix(suffix)
        widget.valueChanged.connect(self._changed)
        self.fields[path] = widget
        form.addRow(label, widget)

    def _check(self, form, label, path):
        widget = QCheckBox(label)
        widget.toggled.connect(self._changed)
        self.fields[path] = widget
        form.addRow(widget)

    def document(self):
        value = copy.deepcopy(self._saved)
        value.update(name=self.name.text(), preset=self.preset.currentIndex(),
                     spectrum_mode=self.spectrum_mode.currentData(), spectrum=self.spectrum.values())
        value["articulation"]["mode"] = self.mode.currentData()
        value["articulation"]["hybrid_parts"] = ["sustain" if w.isChecked() else "strike" for w in self.parts]
        for path, widget in self.fields.items():
            node = value
            for key in path[:-1]:
                node = node[key]
            node[path[-1]] = (widget.isChecked() if isinstance(widget, QCheckBox) else
                int(round(widget.value()*1000)) if path in self.scaled_fields else widget.value())
        return value

    @property
    def dirty(self):
        return self.document() != self._saved

    def set_document(self, value, path=None):
        checked = validate_config(value)  # 全部通过才改界面
        self._loading = True
        self._saved = checked
        self.path = str(path) if path else None
        self.name.setText(checked["name"])
        self.preset.setCurrentIndex(checked["preset"])
        self.spectrum_mode.setCurrentIndex(self.spectrum_mode.findData(checked["spectrum_mode"]))
        self.spectrum.set_values(checked["spectrum"])
        self.mode.setCurrentIndex(self.mode.findData(checked["articulation"]["mode"]))
        for box, part in zip(self.parts, checked["articulation"]["hybrid_parts"]):
            box.setChecked(part == "sustain")
        for path_keys, widget in self.fields.items():
            node = checked
            for key in path_keys:
                node = node[key]
            (widget.setChecked if isinstance(widget, QCheckBox) else widget.setValue)(node / 1000 if path_keys in self.scaled_fields else node)
        self._loading = False
        self._changed()

    def _changed(self, *args):
        if self._loading:
            return
        doc = self.document()
        self._part_selected(self.spectrum.selected_index)
        if self.path:
            from pathlib import Path
            self.file_label.setText("文件：" + Path(self.path).name)
            self.file_label.setToolTip(self.path)
        else:
            self.file_label.setText("尚未保存到文件 · Ctrl+S 保存，Ctrl+O 载入")
        self.wave.values = doc["spectrum"]
        self.wave.update()
        for i, button in enumerate(self.mode_buttons):
            button.setChecked(i == self.mode.currentIndex())
        self.status.setText(("有未保存修改" if self.dirty else "已保存到文件" if self.path else "新建草稿 · 尚未保存") + "  ·  设备尚未应用")
        self.status.setToolTip(self.path or "尚未选择保存位置")
        mode = doc["articulation"]["mode"]
        self.mode_help.setText({"sustain": "按住延续，松开释放。",
            "strike": "一次触发，短促击发。",
            "hybrid": "短促击发与持续部分共同发声。"}[mode] + "（配置草稿）")
        self.hybrid.setVisible(mode == "hybrid")
        self.envelope.level = doc["articulation"]["sustain_level"]
        self.envelope.update()
        active = sum(1 for x in doc["spectrum"] if x)
        fx = [label for key, label in (("delay", "延迟"), ("chorus", "合唱"), ("reverb", "混响")) if doc["effects"][key]["enabled"]]
        self.summary.setText("%s · %s\n绘制谱含 %d 个非零分量 · %s\n效果：%s" % (
            doc["name"] or "未命名", self.mode.currentText(), active, self.spectrum_mode.currentText(),
            "、".join((["干声"] if doc["effects"]["dry_enabled"] else []) + fx) or "全部关闭"))

    def save_to(self, path):
        value = self.document()
        save_config(path, value)
        self._saved = validate_config(value)
        self.path = str(path)
        self._changed()

    def load_from(self, path):
        self.set_document(load_config(path), path)

    def confirm_discard(self):
        if not self.dirty:
            return True
        result = QMessageBox.question(self, "保存配置修改", "当前草稿有未保存修改。是否先保存？",
            QMessageBox.Save | QMessageBox.Discard | QMessageBox.Cancel, QMessageBox.Save)
        if result == QMessageBox.Save:
            return self.save_document()
        return result == QMessageBox.Discard

    def new_document(self):
        if self.confirm_discard():
            self.set_document(default_config())

    def open_dialog(self):
        path, _ = QFileDialog.getOpenFileName(self, "载入完整配置", self.path or "", "乐器配置 (*.json)")
        if not path:
            return
        try:
            value = load_config(path)
            if self.confirm_discard():
                self.set_document(value, path)
        except (ConfigError, OSError) as exc:
            QMessageBox.warning(self, "载入失败 · 原草稿保留", str(exc))

    def save_document(self):
        if not self.path:
            return self.save_as()
        try:
            self.save_to(self.path)
            return True
        except (ConfigError, OSError) as exc:
            QMessageBox.warning(self, "保存失败", str(exc))
            return False

    def save_as(self):
        path, _ = QFileDialog.getSaveFileName(self, "保存完整配置", self.path or "instrument.json", "乐器配置 (*.json)")
        if not path:
            return False
        try:
            self.save_to(path)
            return True
        except (ConfigError, OSError) as exc:
            QMessageBox.warning(self, "保存失败", str(exc))
            return False
