"""One session, persistent performance and observation, explicit partial application."""
import json
import time
from pathlib import Path
import numpy as np
from PyQt5.QtCore import Qt, QTimer
from PyQt5.QtWidgets import (QApplication, QWidget, QVBoxLayout, QHBoxLayout,
    QSplitter, QLabel, QPushButton, QPlainTextEdit, QLineEdit, QAbstractSpinBox,
    QComboBox, QFileDialog, QCheckBox, QDialog, QScrollArea, QMenu)
from dsp_gui import MainWindow, SerialLink, SimLink, PRESETS, SpectrumBars, midi_name
from serial_link import find_file
import dsp_host as dh
from device_config import ApplyWorker, UNSUPPORTED
from tone_panel import TonePanel,compile_tone,validate_tone
from piano_keyboard import PianoKeyboard, OFFSETS, BINDINGS, note_name
from advanced_tools import AdvancedToolsDialog, DeviceStatusLabel


class WorkbenchWindow(MainWindow):
    def __init__(self, preferences_path=None):
        self.applying = False
        self.testing = False
        self.device_record = None
        self.apply_worker = None
        self.test_records = []
        self.ab = {}
        self.input_sources = {}
        self.export_worker = None
        self.connecting = False
        self.performance_ready = False
        self.pending_disconnect = False
        self.pending_close = False
        self.pending_preset = None
        self.pending_sound = None
        self.applying_sound_name = None
        self.sequence_playing=False
        self.sequence_busy=False
        self.sequence_record=None
        self.pending_sequence_stop=False
        self.pending_panic=False
        super().__init__(preferences_path)
        try:
            self.product_version=json.loads(Path(find_file('host_version.json')).read_text(encoding='utf-8'))['version']
        except (OSError,ValueError,TypeError,KeyError):
            self.product_version='开发版本'
        self.setWindowTitle('FPGA 乐器 · 全局演奏工作台 · '+self.product_version)
        self.resize(1280, 720)
        self.sidebar.hide()
        self.pages.tabBar().show()
        self.pages.removeTab(3)
        workspace = self.pages.parentWidget()
        outer = workspace.layout()
        outer.removeWidget(self.pages)
        self.splitter = QSplitter(Qt.Horizontal)
        self.splitter.addWidget(self.pages)
        self.splitter.addWidget(self.audio_page)
        self.audio_page.show()
        self.splitter.setSizes([470, 810])
        outer.insertWidget(1, self.splitter, 1)
        # Header belongs to the draft pane, not to all views.
        outer.removeWidget(self.editor.document_header)
        self.editor.layout().insertWidget(2, self.editor.document_header)
        toolbar = self.editor.document_header.layout().itemAt(0).layout()
        toolbar.removeWidget(self.editor.name)
        self.editor.document_header.layout().insertWidget(0, self.editor.name)
        top = outer.itemAt(outer.count()-1).widget()
        outer.removeWidget(top)
        outer.insertWidget(0, top)
        self.device_status = DeviceStatusLabel('设备音色未知 · 草稿尚未应用')
        self.device_status.setWordWrap(True)
        top.layout().addWidget(self.device_status)
        self.editor.apply_button.setText('仅应用预设与谱 · 下一次起音')
        self.editor.apply_button.setEnabled(True)
        self.editor.apply_button.setToolTip('不应用模式、包络、颤音及效果物理单位；无在奏音时可用。')
        self.editor.apply_button.clicked.connect(lambda: self.apply_draft(False))
        preset = QPushButton('仅使用所选四预设 · 清除附加谱')
        preset.clicked.connect(lambda: self.apply_draft(True))
        self.editor.apply_button.parentWidget().layout().addWidget(preset)
        self.partial_hint = QLabel('未应用字段：' + '；'.join(UNSUPPORTED))
        self.partial_hint.setWordWrap(True)
        self.editor.apply_button.parentWidget().layout().addWidget(self.partial_hint)
        self.verify_page = QWidget()
        v = QVBoxLayout(self.verify_page)
        text = QLabel('标准 A4 · 力度12 · 保持900ms / 释放500ms。\n'
                      '需要真实实时流及空闲演奏；测试仅释放自己拥有的A4。\n'
                      '检测接受事件、传输完整性、音频能量和440Hz附近谱峰；'
                      '这些结果不等于完整音色、DAC或触控验收。')
        text.setWordWrap(True); v.addWidget(text)
        self.test_button = QPushButton('测量当前音色 · A4')
        self.test_button.clicked.connect(self.start_test); v.addWidget(self.test_button)
        stop = QPushButton('中止测试'); stop.clicked.connect(self.abort_test); v.addWidget(stop)
        row = QHBoxLayout()
        for slot in ('A', 'B'):
            button = QPushButton('冻结实测 '+slot)
            button.clicked.connect(lambda checked=False, s=slot: self.freeze(s))
            row.addWidget(button)
        v.addLayout(row)
        export = QPushButton('导出配置 / 测量 / A-B证据')
        export.clicked.connect(self.export_evidence); v.addWidget(export)
        self.result_text = QPlainTextEdit(); self.result_text.setReadOnly(True)
        v.addWidget(self.result_text, 1)
        self.pages.addTab(self.verify_page, '音色验证')
        self.pages.setTabText(1, '接口实验')
        self.pages.setTabText(2, '设备诊断')
        self.audio_page.mode.setCurrentIndex(0)
        self.audio_page.mode.hide()  # D4 stream is the workbench default.
        self.audio_page.live_status.setWordWrap(True)
        self.audio_page.snapshot_panel.hide()
        self.audio_page.layout().itemAt(0).widget().hide()
        self.audio_page.trajectory.setMinimumHeight(70)
        self.audio_page.live_wave.setMinimumHeight(90)
        self.audio_page.live_spectrum.setMinimumHeight(90)
        for button in self.audio_page.play_buttons:
            button.setMinimumHeight(64)
        self.audio_page.play_state.setText('电脑键盘 Z X C V B N M , · 所有页面可演奏；输入框内停用')
        self.edit_toggle = QPushButton('音色与设备设置')
        self.edit_toggle.setCheckable(True)
        self.edit_toggle.toggled.connect(self._show_editor)
        top.layout().itemAt(1).layout().addWidget(self.edit_toggle)
        settings = QPushButton('显示设置')
        settings.clicked.connect(self._open_settings)
        top.layout().itemAt(1).layout().addWidget(settings)
        self.pages.hide()
        self.splitter.setChildrenCollapsible(False)
        self.audio_page.live_status.setText('连接FPGA后自动接收数据，即可演奏')
        self.audio_page.live_button.setText('重新启动数据流')
        self.audio_page.live_button.hide()
        self.device_status.setText('未连接 · 选择串口并连接，即可演奏')
        self.sld_vel.setValue(12)
        self.performance_preset = QComboBox()
        self.performance_preset.addItems([name for name,_ in PRESETS])
        self.performance_preset.setMinimumWidth(110)
        self.performance_preset.setFocusPolicy(Qt.NoFocus)
        self.performance_preset.setToolTip('直接应用内置音色，清除附加绘制谱；按住时等待松键，再用于下一次起音。')
        self.performance_preset.activated[int].connect(self.select_performance_preset)
        view=self.audio_page.layout().itemAt(4).layout()
        view.insertWidget(2,QLabel('设备音色'))
        view.insertWidget(3,self.performance_preset)
        self.onset_hold=QCheckBox('冻结起音谱')
        self.onset_hold.setChecked(False)
        self.onset_hold.setToolTip('默认连续刷新实时频谱。勾选后冻结FPGA接受起音后的首个完整窗口，仅用于对比；取消立即恢复实时。')
        self.onset_hold.toggled.connect(self._spectrum_mode_changed)
        self.audio_page.live_model.hold_onset=False
        view.insertWidget(4,self.onset_hold)
        self.applying_hint = QLabel('草稿与设备分开 · 预设 / 谱部分应用')
        self.applying_hint.setWordWrap(True)
        self.pages.parentWidget()
        self.editor.layout().insertWidget(0, self.applying_hint)
        self.editor.layout().insertWidget(1, preset)
        self.editor.layout().insertWidget(2, self.editor.apply_button)
        self.editor.spectrum_mode.currentIndexChanged.connect(self._draft_spectrum_hint)
        self._draft_spectrum_hint()
        self._simplify_ui(top,outer,preset)
        self._install_piano()
        self._install_score_panel(top)
        self.log('全局工作台就绪；音色应用为明确的部分应用，模拟设备不生成音频。')

    def _simplify_ui(self,top,outer,preset):
        # Keep the original developer surface intact behind one explicit entry.
        self.pages.setTabText(0,'配置草稿')
        self.pages.setTabText(1,'指令实验');self.pages.setTabText(2,'设备诊断');self.pages.setTabText(3,'音色测试')
        self.applying_hint.hide()
        for label in self.editor.findChildren(QLabel):
            if label.text() in ('音色设计','绘制声音的分量，设定它如何开始、延续与消退。'):
                label.hide()
        # Keep the document strip compact; the always-visible footer owns Save/Apply.
        toolbar=self.editor.document_header.layout().itemAt(1).layout()
        while toolbar.count():
            item=toolbar.takeAt(0)
            if item.widget():item.widget().hide()
        toolbar.addWidget(self.editor.name,1)
        file_button=QPushButton('文件…')
        menu=QMenu(file_button)
        for text,action in (('新建草稿',self.editor.new_document),('载入草稿…',self.editor.open_dialog),
                            ('另存为…',self.editor.save_as)):
            menu.addAction(text,action)
        file_button.setMenu(menu);toolbar.addWidget(file_button)
        self.editor.document_header.layout().setContentsMargins(12,8,12,8)
        self.editor.file_label.hide()
        self.editor.application_hint='本地草稿'
        self.editor._changed()
        self.advanced_dialog=AdvancedToolsDialog(self.pages,self.editor,
            self.editor.apply_button,preset,self)
        self.pages.show()
        self.device_status.text_changed.connect(self.advanced_dialog.status.setText)
        self.advanced_dialog.status.setText(self.device_status.text())
        outer.removeWidget(self.log_toggle);outer.removeWidget(self.logbox)
        logs=QWidget();lv=QVBoxLayout(logs)
        log_header=QHBoxLayout();log_header.addWidget(self.lab_tick,1);log_header.addWidget(self.btn_export)
        lv.addLayout(log_header);lv.addWidget(self.logbox,1)
        self.logbox.setMaximumHeight(16777215)
        self.log_toggle.setChecked(True);self.log_toggle.hide();self.logbox.show()
        self.pages.addTab(logs,'操作日志')
        self.editor_panel=TonePanel(SpectrumBars,PRESETS)
        self.editor_panel.apply_requested.connect(self.request_sound)
        self.sound_panel=QScrollArea();self.sound_panel.setWidgetResizable(True)
        self.sound_panel.setWidget(self.editor_panel);self.sound_panel.setMinimumWidth(320)
        self.splitter.insertWidget(0,self.sound_panel);self.sound_panel.hide()
        self.edit_toggle.setText('编辑音色')
        advanced=QPushButton('高级工具')
        advanced.clicked.connect(self._open_advanced)
        top.layout().itemAt(1).layout().addWidget(advanced)
        # Display controls move together so the main strip means "choose sound".
        self.view_dialog=QDialog(self);self.view_dialog.setWindowTitle('视图与外观')
        vv=QVBoxLayout(self.view_dialog)
        vv.addWidget(QLabel('波形显示范围'));vv.addWidget(self.audio_page.timescale)
        vv.addWidget(QLabel('波形显示放大（不改变声音）'));vv.addWidget(self.audio_page.zoom)
        vv.addWidget(self.onset_hold)
        display=QPushButton('字体与配色…');display.clicked.connect(self._open_settings);vv.addWidget(display)
        for button in top.findChildren(QPushButton):
            if button.text()=='显示设置':
                button.setText('视图设置');button.clicked.disconnect();button.clicked.connect(self.view_dialog.show)
        self.audio_page.live_status.hide()
        self.lab_detail.hide()
        self.audio_page.panic.setText('停止所有声音')
        self.performance_preset.addItem('手绘音色…')
        self.performance_preset.setToolTip('选择内置音色就会应用。想自己画声音，请选“手绘音色”或点“编辑音色”。')
        view=self.audio_page.layout().itemAt(4).layout()
        label=view.itemAt(0).widget()
        if isinstance(label,QLabel):label.setText('音色')
        for plot in (self.audio_page.trajectory,self.audio_page.live_wave,self.audio_page.live_spectrum):
            plot.setProperty('friendlyLabels',True)
        self.audio_page.trajectory.setToolTip('显示FPGA实际接受的按下和松开事件。')
        self.audio_page.live_spectrum.setToolTip('显示声音里不同频率的强弱。同一音高的主峰相近，不同音色主要看其他峰。')
        self.audio_page.play_state.setText('按 Z X C V B N M , 或点击琴键。音色可直接选择。')
        self.device_status.setText('第一步：选择串口并连接。连接成功后直接演奏。')
        # File shortcuts follow the new user-facing sound document.
        for shortcut in self.file_shortcuts:shortcut.setEnabled(False)

    def _install_piano(self):
        keyboard=self.audio_page.layout().itemAt(6).layout()
        for button in self.audio_page.play_buttons:
            keyboard.removeWidget(button);button.hide();button.deleteLater()
        self.piano=PianoKeyboard()
        self.audio_page.play_buttons=self.piano.buttons
        keyboard.addWidget(self.piano)
        self.piano.note_pressed.connect(self.note_on)
        self.piano.note_released.connect(self.note_off)
        self.piano_range=QLabel()
        self.audio_page.layout().itemAt(4).layout().addWidget(self.piano_range)
        self._shift_octave(0)
        self._performance_state()

    def _shift_octave(self, amount):
        # MainWindow calls this before the piano is installed.
        super()._shift_octave(amount)
        if hasattr(self,'piano'):
            base=60+12*self.octave
            self.piano.set_base(base)
            self.piano_range.setText('%s – %s'%(note_name(base),note_name(base+24)))
            self.audio_page.oct_down.setEnabled(self.octave>-2)
            self.audio_page.oct_up.setEnabled(self.octave<2)

    def _open_advanced(self):
        self.advanced_dialog.open_tools()

    def _install_score_panel(self,top):
        self.score_dialog=QDialog(self);self.score_dialog.setWindowTitle('曲谱播放')
        self.score_dialog.resize(900,230)
        layout=QVBoxLayout(self.score_dialog)
        help=QLabel('输入“音高:拍数”，用逗号分隔，例如 60:1,62:1,64:2。0 表示休止。\n'
            '下载只保存到开发板；“下载并播放”会循环播放，点“停止”结束。播放期间暂停手动演奏。')
        help.setWordWrap(True);layout.addWidget(help)
        card=self.ed_score.parentWidget();layout.addWidget(card)
        for label in card.findChildren(QLabel):
            if label.text().startswith('定序器实验'):label.setText('曲谱 · 开发板循环演奏')
        self.score_status=QLabel('尚未下载曲谱');self.score_status.setWordWrap(True);layout.addWidget(self.score_status)
        button=QPushButton('曲谱播放');button.clicked.connect(self.score_dialog.show)
        top.layout().itemAt(1).layout().addWidget(button)

    def _seq_status(self):
        count=len([s for s in self.ed_score.text().split(',') if s.strip()])
        self.lab_seq.setText('%d步 · %d BPM'%(count,self.spin_bpm.value()))

    def seq_download(self):self._request_sequence(False)
    def seq_play(self):self._request_sequence(True)
    def seq_stop(self):
        if self.sequence_busy:
            self.pending_sequence_stop=True
            self.score_status.setText('正在等待当前曲谱操作完成，随后停止…');return
        self._request_sequence(False,stop=True)

    def _request_sequence(self,play,stop=False):
        if self.link is None:
            self.score_status.setText('请先连接开发板');return
        if self.applying or self.testing:
            self.score_status.setText('当前操作尚未完成，请稍后重试');return
        if isinstance(self.link,SerialLink) and not self.performance_ready:
            self.score_status.setText('设备尚未准备好，请等待连接完成');return
        if self.held and not stop:
            self.score_status.setText('请先松开手动演奏的琴键');return
        notes=None if stop else self._parse_score()
        if notes is None and not stop:return
        self.applying=True;self.sequence_busy=True
        self.score_status.setText('正在停止曲谱…' if stop else '正在下载曲谱…')
        if self.live_worker is not None and self.live_worker.isRunning():
            self.live_worker.sequence(notes,self.spin_bpm.value(),play)
        else:
            from score_control import SequenceWorker
            self.apply_worker=SequenceWorker(self.link,notes,self.spin_bpm.value(),play,self)
            self.apply_worker.result.connect(self._sequence_done);self.apply_worker.start()

    def _sequence_done(self,record):
        self.applying=False;self.sequence_busy=False;self.sequence_record=record
        if record.get('sent_complete'):
            self.journal.extend(record['writes']);self.sent_total+=2*len(record['writes'])
            if self.link is not None:self.journal_kind=self.link.kind
        if record['status']=='CONFIRMED':
            self.sequence_playing=bool(record['readback']['SEQ_CTRL']&1)
            if self.sequence_playing:text='已启动循环播放 · %d步 · %d BPM'%(len(record['notes']),record['bpm'])
            elif record.get('notes') is not None:text='已下载%d步 · 尚未播放'%len(record['notes'])
            else:text='曲谱已停止 · 可以手动演奏'
        else:
            self.sequence_playing=self.sequence_playing or bool(record.get('play'))
            text='曲谱操作失败 · '+record.get('error','设备状态未知')
        if isinstance(self.link,SimLink):text='模拟流程（无音频） · '+text
        self.score_status.setText(text);self.device_status.setText(text)
        self._performance_state()
        if self.pending_sequence_stop:
            # Stay busy until the queued stop actually owns the next transaction.
            self.applying=True;self.sequence_busy=True
            QTimer.singleShot(0,self._run_pending_sequence_stop)
        elif self.pending_panic and record['status']=='CONFIRMED' and not self.sequence_playing:
            self.pending_panic=False;self._performance_panic()

    def _run_pending_sequence_stop(self):
        self.applying=False;self.sequence_busy=False;self.pending_sequence_stop=False
        self.seq_stop()

    def request_sound(self,sound):
        if self.link is None or self.testing:
            self.editor_panel.status.setText('请先连接设备，并结束测试。');return
        self.pending_sound=validate_tone(sound);self.pending_preset=None
        self.device_status.setText('准备使用：%s。%s后自动应用。'%(sound['name'],'停止曲谱' if self.sequence_playing else '松开琴键'))
        self._apply_pending_preset()

    def _show_editor(self, visible):
        panel=getattr(self,'sound_panel',self.pages)
        panel.setVisible(visible)
        if visible:
            self.editor.body_layout.setDirection(2)  # QBoxLayout.TopToBottom
            self.splitter.setSizes([max(460,int(self.width()*.43)),int(self.width()*.57)])
        self.edit_toggle.setText('收起音色编辑' if visible else '编辑音色')

    def _draft_spectrum_hint(self):
        self.applying_hint.setText('草稿未自动应用。' +
            ('仅使用绘制谱会覆盖预设幅度；试听四种内置音色请选演奏区的“设备音色”。'
             if self.editor.spectrum_mode.currentData()=='replace' else
             '绘制谱会叠加到预设；显式应用后，在下一次起音生效。'))

    def _spectrum_mode_changed(self, frozen):
        self.audio_page.live_model.hold_onset=frozen
        self.audio_page.refresh_live()

    def select_performance_preset(self, preset):
        if preset==4:
            self.editor_panel.kind.setCurrentIndex(1)
            self.edit_toggle.setChecked(True);return
        if self.link is None or self.testing:
            self.device_status.setText('请先连接设备并结束测试，再切换设备音色')
            return
        self.pending_preset = preset
        self.pending_sound = None
        self.device_status.setText('待切换为%s · %s后自动应用' % (PRESETS[preset][0],'停止曲谱' if self.sequence_playing else '松开琴键'))
        self._apply_pending_preset()

    def _apply_pending_preset(self):
        if ((self.pending_preset is None and self.pending_sound is None) or self.link is None or self.applying or self.testing or
            self.held or self.audio_test_note or self.audio_page.live_model.active or self.sequence_playing): return
        if isinstance(self.link,SerialLink) and not self.performance_ready:return
        if self.pending_sound is not None:
            sound=self.pending_sound;self.pending_sound=None
            document,preset_only=compile_tone(sound)
            self._apply_document(document,preset_only,sound['name'] if sound['kind']=='drawn' else None)
        else:
            document,_=compile_tone(dict(tone_schema=1,name=PRESETS[self.pending_preset][0],
                kind='built_in',preset=self.pending_preset,amplitudes=[0]*16))
            self.pending_preset=None
            self._apply_document(document,True)

    def _load_theme(self, *args):
        super()._load_theme(*args)
        # Compact, readable controls leave room for the actual instrument views.
        self.setStyleSheet(self.styleSheet() + '\nQLabel#PageTitle { font-size: 17pt; }\n'
            'QLabel#ConfigName, QLineEdit#ConfigName { font-size: 12pt; }\n')

    def resizeEvent(self, event):
        super().resizeEvent(event)
        if hasattr(self, 'edit_toggle') and self.edit_toggle.isChecked() and self.width()<1120:
            self.edit_toggle.setChecked(False)

    def _page_changed(self, index):
        # Internal navigation must never release held notes or replace the reader.
        if hasattr(self, 'editor'):
            self.editor.document_header.setVisible(index == 0)

    def _keyboard_active(self):
        return not self.applying and not self.testing and not isinstance(
            QApplication.focusWidget(), (QLineEdit, QPlainTextEdit, QAbstractSpinBox, QComboBox))

    def note_on(self, idx, source='mouse'):
        if self.sequence_playing:
            self.audio_page.play_state.setText('曲谱正在播放 · 请先在“曲谱播放”中停止，再手动演奏');return
        if (self.pending_preset is not None or self.pending_sound is not None) and not self.held:
            self._apply_pending_preset()
            if self.pending_preset is not None or self.pending_sound is not None:
                self.audio_page.play_state.setText('等待松键事件确认后切换音色，请稍候再起音')
                return
        if self.applying or self.testing:
            return
        if isinstance(self.link,SerialLink) and not self.performance_ready:
            self.audio_page.play_state.setText('设备尚未准备好 · 请查看连接状态')
            return
        self.input_sources.setdefault(idx,set()).add(source)
        if self.link is not None and idx not in self.held and 0<=idx<len(OFFSETS):
            midi=60+OFFSETS[idx]+12*self.octave
            if self.send_frames(dh.cmd_note('on:%d:%d'%(midi,self.sld_vel.value())), '音符开 '+note_name(midi)):
                self.held[idx]=midi
                self.audio_page.play_buttons[idx].setDown(True)
                if idx<len(self.key_btns):self.key_btns[idx].setDown(True)
                self._performance_state()
        if idx not in self.held:
            self.input_sources.pop(idx,None)

    def note_off(self, idx, source='mouse'):
        sources = self.input_sources.get(idx,set())
        sources.discard(source)
        if sources: return
        self.input_sources.pop(idx,None)
        if idx in self.held:
            midi=self.held[idx]
            if self.send_frames(dh.cmd_note('off:%d'%midi),'音符关 '+note_name(midi)):
                self.held.pop(idx)
                self.audio_page.play_buttons[idx].setDown(False)
                if idx<len(self.key_btns):self.key_btns[idx].setDown(False)
                self._performance_state()
        if (self.pending_preset is not None or self.pending_sound is not None) and not self.held:
            QTimer.singleShot(40,self._apply_pending_preset)

    def _release_keys(self):
        self.input_sources.clear()
        if hasattr(self,'piano'):self.piano.clear_mouse()
        super()._release_keys()

    def _performance_panic(self):
        if self.sequence_playing or self.sequence_busy:
            self.pending_panic=True;self.seq_stop();return
        super()._performance_panic()
        if not self.held:
            self.input_sources.clear()
            self.piano.clear_mouse()

    def keyPressEvent(self, event):
        if event.isAutoRepeat(): return
        key=event.key()
        if key in BINDINGS and self._keyboard_active() and not event.modifiers() & (Qt.ControlModifier|Qt.AltModifier|Qt.MetaModifier):
            self.note_on(BINDINGS[key],'keyboard:%d'%key)
        else:
            # Bypass the legacy page-scoped handler.
            super(MainWindow,self).keyPressEvent(event)

    def keyReleaseEvent(self, event):
        if event.isAutoRepeat(): return
        key=event.key()
        if key in BINDINGS:
            self.note_off(BINDINGS[key],'keyboard:%d'%key)
        else: super(MainWindow,self).keyReleaseEvent(event)

    def send_frames(self, frames, what):
        # Configuration owns the session; off commands remain legal at all times.
        if self.applying or self.testing:
            items = getattr(frames, 'items', [])
            if any(a not in (0x60, 0x61) for a, _, _ in items):
                self.log('后台事务进行中，暂不接受接口实验：'+what)
                return False
        result = super().send_frames(frames, what)
        if not result and self.link is not None:
            self.device_status.setText('通信失败 · 设备音符/参数状态未知')
        return result

    def read_all(self):
        if self.connecting:
            return  # Initial readback is performed by the stream worker, not UI.
        if self.applying or self.testing:
            self.log('后台事务进行中，稍后回读'); return
        super().read_all()

    def _fill_ports(self):
        previous=self.cmb_port.currentText()
        super()._fill_ports()
        index=self.cmb_port.findText(previous)
        if index>0:self.cmb_port.setCurrentIndex(index)
        elif self.cmb_port.count()>1:
            # This board exposes FT2232 A (programmer) and B (UART).
            # Prefer its UART rather than the first numerical COM port.
            from serial.tools import list_ports
            uart=next((p.device for p in list_ports.comports() if
                p.vid==0x0403 and p.pid==0x6010 and (p.serial_number or '').endswith('B')),None)
            self.cmb_port.setCurrentIndex(max(1,self.cmb_port.findText(uart or '')))

    def _toggle_conn(self):
        if self.applying or self.testing:
            self.log('先结束后台应用或标准音测试再切换连接'); return
        was_connected = self.link is not None
        if was_connected and self.live_worker is not None and self.live_worker.isRunning():
            self.pending_disconnect = True
            self.btn_conn.setEnabled(False)
            self._stop_live()
            return
        self.connecting = True
        try:
            super()._toggle_conn()
        finally:
            self.connecting = False
        self.performance_ready = False
        self.pending_preset = None
        self.pending_sound = None
        self.sequence_playing=False
        self.pending_sequence_stop=False
        self.pending_panic=False
        if hasattr(self, 'device_status'):
            self.device_record = None
            self.device_status.setText('未连接 · 选择串口并连接，即可演奏')
        if isinstance(self.link, SimLink):
            # Explicit v1.1 register model for workflow testing, never PCM.
            self.link.regs[dh.REG['PROTO_VER']] = 0x11
            self.device_status.setText('模拟设备 · 可检查按键流程；没有真实音频')
        elif not was_connected and isinstance(self.link,SerialLink):
            self.device_status.setText('正在确认设备并启动数据传输…')
            self._toggle_live()

    def apply_draft(self, preset_only=False):
        self._apply_document(self.editor.document(),preset_only)

    def _apply_document(self, document, preset_only, sound_label=None):
        if self.sequence_playing:
            self.device_status.setText('请先停止曲谱播放，再切换音色');return
        if self.link is None or self.applying or self.testing:
            self.device_status.setText('请连接设备，并等待当前操作结束'); return
        m = self.audio_page.live_model
        if self.held or self.audio_test_note or m.active:
            self.device_status.setText('请先松开全部音符；本版本仅在空闲时应用'); return
        if self.audio_worker is not None and self.audio_worker.isRunning():
            self.device_status.setText('请等待快照采集结束'); return
        self._stop_scan()
        self.applying = True
        self.applying_sound_name=sound_label
        self.device_status.setText('正在切换音色，请稍候…')
        if self.live_worker is not None and self.live_worker.isRunning():
            self.live_worker.configure(document, preset_only)
        else:
            self.apply_worker = ApplyWorker(self.link, document, preset_only, self)
            self.apply_worker.result.connect(self._applied)
            self.apply_worker.start()

    def _applied(self, record):
        self.applying = False
        self.device_record = record
        if record.get('sent_complete'):
            self.journal.extend(record.get('writes', []))
        if self.link is not None:
            self.journal_kind = self.link.kind
        if record.get('sent_complete'):
            self.sent_total += 2*len(record.get('writes', []))
        if record['status'] == 'FAILED':
            self.device_status.setText('应用失败 · 设备状态未知：'+record['error'])
        else:
            doc = record['requested']
            name = PRESETS[doc['preset']][0]
            drawn=not record['preset_only'] and doc['spectrum_mode']=='replace'
            self.performance_preset.setCurrentIndex(4 if drawn else doc['preset'])
            name=(self.applying_sound_name or '手绘音色') if drawn else name
            record['display_name']=name
            self.device_status.setText('当前音色：%s · 已设置，下一次按键使用'%name)
            self.editor_panel.status.setText('设备当前音色：'+name+' · 编辑内容需点“用于演奏”才生效')
            self.connected_registers=record['readback']
        if hasattr(self,'advanced_dialog'):
            if record['status']=='FAILED':
                self.advanced_dialog.status.setText('应用失败：'+record.get('error','设备状态未知'))
            else:
                source='模拟流程完成，无实际声音' if record.get('source')=='模拟设备' else '部分应用完成'
                scope='内置预设，已清除附加谱' if record.get('preset_only') else '预设与泛音谱'
                self.advanced_dialog.status.setText(source+' · '+scope+' · 下一次起音使用。其他草稿字段未应用。')
        self.result_text.setPlainText(json.dumps(record, ensure_ascii=False, indent=2))

    def _toggle_live(self):
        if self.applying:
            return
        from live_visualizer import LiveWorker, LiveAnalysis
        if self.live_worker is not None and self.live_worker.isRunning(): return
        if not isinstance(self.link,SerialLink): return
        self.performance_ready = False
        self.audio_page.follow.setChecked(False); self._stop_scan()
        self.audio_page.live_model = LiveAnalysis()
        self.audio_page.live_model.hold_onset=self.onset_hold.isChecked()
        for plot in (self.audio_page.trajectory,self.audio_page.live_wave,self.audio_page.live_spectrum):
            plot.model=self.audio_page.live_model
        worker = self.live_worker = LiveWorker(self.link,self,prepare_performance=True)
        worker.batch.connect(self._receive_live)
        worker.device_state.connect(self._connected_state)
        worker.failure.connect(self._live_failed)
        worker.finished.connect(self._live_finished)
        worker.configuration.connect(self._applied)
        worker.sequence_result.connect(self._sequence_done)
        worker.observation_gap.connect(self.audio_page.live_model.mark_gap)
        if not hasattr(self,'live_display_timer'):
            self.live_display_timer=QTimer(self)
            self.live_display_timer.setInterval(33)
            self.live_display_timer.timeout.connect(self.audio_page.refresh_live)
        self.live_display_timer.start()
        self.audio_page.live_button.hide()
        self.audio_page.live_status.setText('正在确认设备并启动数据传输…')
        worker.start()

    def _connected_state(self, state):
        self.sequence_playing=bool(state.get('SEQ_CTRL',0)&1)
        preset = state['PRESET'] & 3
        self.device_status.setText('FPGA已连接 · %s · 演奏模式 · 正在等待数据' % PRESETS[preset][0])
        self.connected_registers = state
        self.performance_preset.setCurrentIndex(4 if state['SPEC_MODE']&1 else preset)
        self.device_record = dict(status='DEVICE_READBACK',readback=state,source='真实串口',audio_verified=False)
        for row in range(self.tbl.rowCount()):
            name=self.tbl.item(row,1).text()
            if name in state:self.tbl.item(row,2).setText('0x%02X'%state[name])

    def _receive_live(self, batch):
        self.audio_page.live_model.ingest(batch)
        if (not self.performance_ready and not self.pending_disconnect and not self.pending_close and
                not self.live_worker.stop_requested and any(f['kind']==1 for f in batch['frames'])):
            self.performance_ready = True
            self._release_keys()  # Reconcile this host's notes after a failed disconnect.
            state=getattr(self,'connected_registers',{})
            name='手绘音色' if state.get('SPEC_MODE',0)&1 else PRESETS[state.get('PRESET',0)&3][0]
            self.device_status.setText('已连接 · 当前音色：%s · 可以演奏' % name)
            if self.connected_registers.get('PROTO_VER') != 0x11:
                self.device_status.setText(self.device_status.text() + ' · 协议标志异常，实时能力已核对')
            self._performance_state()
            self.setFocus(Qt.OtherFocusReason)

    def _performance_state(self):
        if self.sequence_playing:
            self.audio_page.play_state.setText('曲谱正在循环播放 · 点“曲谱播放”可停止，或点“停止所有声音”');return
        notes='、'.join(note_name(n) for n in self.held.values())
        self.audio_page.play_state.setText('按住的音：'+notes if notes else '点击黑白键，或按键帽字母演奏。Z–M 为低音区，Q–I 为高音区；S D G H J / 2 3 5 6 7 对应黑键。')

    def _tick(self):
        self._apply_pending_preset()
        if self.applying:
            self._tick_rate(); return
        super()._tick()

    def _live_failed(self, message):
        self.performance_ready = False
        if self.sequence_busy:
            self._sequence_done(dict(status='FAILED',error=message,writes=[],play=self.sequence_playing))
        elif self.applying:
            self._applied(dict(status='FAILED', error=message, writes=[]))
        self.abort_test()
        super()._live_failed(message)
        self.device_status.setText('连接未就绪：'+message)

    def _live_finished(self):
        self.performance_ready = False
        self.sequence_playing=False
        self.pending_sequence_stop=False;self.pending_panic=False
        super()._live_finished()
        self.audio_page.live_button.setText('重试数据传输')
        self.audio_page.live_button.show()
        if self.pending_disconnect:
            self.pending_disconnect = False
            self.btn_conn.setEnabled(True)
            self._toggle_conn()
        if self.pending_close:
            self.pending_close = False
            self.close()

    def _stop_live(self):
        self.performance_ready = False
        self.abort_test()
        super()._stop_live()

    def start_test(self):
        m = self.audio_page.live_model
        if (self.testing or self.applying or self.held or self.audio_test_note or m.active or
            self.sequence_playing or
            not isinstance(self.link, SerialLink) or self.live_worker is None or
            not self.live_worker.isRunning() or m.last_received is None or
            time.monotonic()-m.last_received > .5):
            self.result_text.setPlainText('无法开始：需要新鲜真实PCM、空闲演奏且无后台事务。'); return
        self.testing = True
        self.test_start = m.now
        self.test_health = (m.crc_errors, m.gaps, m.discontinuities, m.losses)
        self.test_wire_start = m.frames
        self.test_audio = []
        self.test_events = []
        self.test_wire = []
        self.live_worker.batch.connect(self._collect_test)
        if not self.send_frames(dh.cmd_note('on:69:12'), '标准A4起音'):
            self.abort_test(); return
        self.test_button.setEnabled(False)
        self.result_text.setPlainText('正在测量真实FPGA音频 · 手动起音暂停')
        self.test_timer = QTimer(self); self.test_timer.setSingleShot(True)
        self.test_timer.timeout.connect(self._release_test); self.test_timer.start(900)

    def _collect_test(self, batch):
        if not self.testing:
            return
        for f in batch['frames']:
            if len(self.test_wire) < 100:
                self.test_wire.append(f['raw'].hex())
            if f['kind']==1 and len(self.test_audio)<100:
                self.test_audio.append(np.frombuffer(f['payload'],dtype='<i2').copy())
            elif f['kind']==2:
                self.test_events.append(dict(note=f['payload'][0]&127,
                    on=bool(f['payload'][0]&128), velocity=f['payload'][1], timestamp=f['timestamp']))

    def _release_test(self):
        if not self.testing: return
        self.test_sustain = np.concatenate(self.test_audio) if self.test_audio else np.zeros(0)
        if not self.send_frames(dh.cmd_note('off:69'), '标准A4释放'):
            self.abort_test(); return
        self.test_timer.timeout.disconnect()
        self.test_timer.timeout.connect(self._finish_test); self.test_timer.start(500)

    def _finish_test(self):
        if not self.testing: return
        m = self.audio_page.live_model
        x = self.test_sustain.astype(float)/32768
        event_on = sum(e['note']==69 and e['on'] for e in self.test_events)==1
        event_off = sum(e['note']==69 and not e['on'] for e in self.test_events)==1
        conflict = any(e['on'] and e['note']!=69 for e in self.test_events)
        healthy = self.test_health == (m.crc_errors,m.gaps,m.discontinuities,m.losses)
        n = 1024
        fft_samples=x[-n:]
        spectrum_window='late sustain window'
        owned_on=next((e['timestamp'] for e in self.test_events if e['note']==69 and e['on']),None)
        if (owned_on is not None and m.onset_stamp==owned_on and m.onset_note==69 and len(m.onset_audio)==n):
            fft_samples=m.onset_audio
            spectrum_window='first 1024 samples after FPGA accepted test on'
        peak = None
        spectrum_db = []
        spectrum_hz = []
        if len(x)>=n:
            amp = np.abs(np.fft.rfft(fft_samples*np.hanning(n)))
            freq = np.fft.rfftfreq(n,1/m.sample_rate)
            spectrum_hz = freq.tolist()
            spectrum_db = (20*np.log10(np.maximum(amp*2/np.hanning(n).sum(),1e-6))).tolist()
            region = (freq>=410)&(freq<=470)
            peak = float(freq[region][np.argmax(amp[region])])
        rms = float(np.sqrt(np.mean(x*x))) if len(x) else 0.
        checks = dict(accepted_on=event_on, accepted_off=event_off,
                      transport_complete=healthy, no_other_notes=not conflict,
                      fresh_samples=len(x)>=n, audible_pcm=rms>1e-5,
                      fundamental_near_A4=peak is not None and abs(peak-440)<=m.sample_rate/n)
        record = dict(status='BASIC_SIGNAL_PASS' if all(checks.values()) else 'FAILED_OR_INCONCLUSIVE',
                      checks=checks, rms=rms, peak_hz=peak, sample_rate=m.sample_rate,
                      configuration=self.device_record, events=self.test_events,
                      spectrum_hz=spectrum_hz, spectrum_db=spectrum_db,
                      spectrum_window=spectrum_window,
                      pcm16=np.concatenate(self.test_audio).tolist() if self.test_audio else [],
                      wire_hex=self.test_wire, timbre_verified=False,
                      limitation='基础信号测量；未验证整谱、包络容差、DAC、触控及实体显示')
        self.test_records.append(record); self.test_records=self.test_records[-8:]
        self._end_test()
        self.result_text.setPlainText(json.dumps({k:v for k,v in record.items() if k not in ('pcm16','wire_hex')},ensure_ascii=False,indent=2))

    def _end_test(self):
        if hasattr(self, 'test_timer'): self.test_timer.stop()
        if self.live_worker is not None:
            try: self.live_worker.batch.disconnect(self._collect_test)
            except (TypeError, RuntimeError): pass
        self.testing = False
        self.test_button.setEnabled(True)

    def abort_test(self):
        if not self.testing: return
        released = self.send_frames(dh.cmd_note('off:69'), '中止时释放测试拥有的A4')
        self.test_records.append(dict(status='ABORTED', release_sent=bool(released)))
        self._end_test()
        self.result_text.setPlainText('测试已中止；释放已发送' if released else '测试中止，释放失败；设备状态未知')

    def freeze(self, slot):
        if not self.test_records or 'pcm16' not in self.test_records[-1]:
            self.result_text.setPlainText('先完成一次标准音测量再冻结'); return
        self.ab[slot] = self.test_records[-1]
        self.audio_page.live_spectrum.overlays = {
            key:(r.get('spectrum_hz',[]),r.get('spectrum_db',[])) for key,r in self.ab.items()}
        self.audio_page.live_spectrum.update()
        summary = {k:dict(status=r['status'],rms=r['rms'],peak_hz=r['peak_hz']) for k,r in self.ab.items()}
        self.result_text.setPlainText('同一A4/力度12测量快照（不自动判定音色正确）\n'+json.dumps(summary,ensure_ascii=False,indent=2))

    def export_evidence(self):
        if self.export_worker is not None and self.export_worker.isRunning(): return
        filename, _ = QFileDialog.getSaveFileName(self, '保存工作台证据', 'host-evidence-%d.json'%time.time(), 'JSON (*.json)')
        if not filename: return
        from serial_link import find_file
        identity = find_file('host_version.json')
        try:
            host_version = json.loads(Path(identity).read_text(encoding='utf-8')) if identity else None
        except (OSError, ValueError):
            host_version = None
        data = dict(schema_version=1, source='FPGA PCM / PC analysis', host_version=host_version,
                        draft=self.editor.document(), device=self.device_record,
                        sound_draft=self.editor_panel.document(),sequence=self.sequence_record,
                        tests=list(self.test_records), ab=dict(self.ab),
                        source_identity='当前工作区主机源码；未绑定或证明设备完整码流SHA')
        from evidence_export import EvidenceWorker
        self.export_worker = EvidenceWorker(filename, data, self)
        self.export_worker.result.connect(self.result_text.setPlainText)
        self.export_worker.start()
        self.result_text.setPlainText('正在后台保存证据…')

    def changeEvent(self, event):
        super().changeEvent(event)
        if hasattr(self,'test_button') and not self.isActiveWindow(): self.abort_test()

    def closeEvent(self, event):
        if (self.applying or (self.apply_worker is not None and self.apply_worker.isRunning()) or
                (self.export_worker is not None and self.export_worker.isRunning())):
            event.ignore(); return
        self.abort_test()
        if self.live_worker is not None and self.live_worker.isRunning():
            self.pending_close=True
            self._stop_live();event.ignore();return
        if hasattr(self,'editor_panel') and self.editor_panel.dirty and not self.editor_panel._discard():
            event.ignore();return
        super().closeEvent(event)


def smoke_test():
    """Also runs inside the frozen executable; no serial device is opened."""
    import os
    import tempfile
    from dsp_gui import out_dir
    os.environ.setdefault('QT_QPA_PLATFORM','offscreen')
    os.environ.setdefault('QT_QPA_FONTDIR','C:/Windows/Fonts')
    app = QApplication.instance() or QApplication([])
    with tempfile.TemporaryDirectory() as folder:
        w = WorkbenchWindow(folder+'/preferences.json')
        w.show();app.processEvents()
        w.link=SimLink();w.link.regs[0x7f]=0x11
        w.note_on(0);w.pages.setCurrentIndex(3)
        held = w.held == {0:60}
        w.note_off(0);w.pages.setCurrentIndex(0)
        from piano_keyboard import INDEX
        piano_ok=len(w.piano.buttons)==25
        for offset in (1,24):
            w.piano.note_pressed.emit(INDEX[offset])
            piano_ok=piano_ok and w.held=={INDEX[offset]:60+offset}
            w.piano.note_released.emit(INDEX[offset])
            piano_ok=piano_ok and not w.held
        w.apply_draft(True)
        w.apply_worker.wait(2000);app.processEvents()
        ok = held and piano_ok and not w.held and not w.applying and w.device_record is not None
        ok = ok and w.device_record['status']=='PARTIAL_PARAMETER_CONFIRMED'
        w.ed_score.setText('60:1,62:1');w.seq_play()
        w.apply_worker.wait(2000);app.processEvents()
        ok=ok and w.sequence_playing and w.sequence_record['status']=='CONFIRMED'
        w.seq_stop();w.apply_worker.wait(2000);app.processEvents()
        ok=ok and not w.sequence_playing and w.sequence_record['status']=='CONFIRMED'
        ok = ok and w.height()==720 and w.audio_page.isVisible()
        # Exercise the same advanced dialog bundled in the normal executable.
        from PyQt5.QtCore import QRect, QPoint
        w._open_advanced();app.processEvents()
        dialog=w.advanced_dialog
        available=QRect(0,0,800,560)
        dialog.fit_to_available(available);app.processEvents()
        advanced_ok=available.contains(dialog.frameGeometry())
        for button in (dialog.top_close,dialog.bottom_close,dialog.apply_button):
            advanced_ok=advanced_ok and button.isVisible() and dialog.rect().contains(
                QRect(button.mapTo(dialog,QPoint()),button.size()))
        dialog.grab().save(str(Path(out_dir())/'advanced-tools-preview.png'))
        draft=w.editor.document();dialog.bottom_close.click();app.processEvents()
        advanced_ok=advanced_ok and not dialog.isVisible() and w.editor.document()==draft and w.isVisible()
        ok=ok and advanced_ok
        w.grab().save(str(Path(out_dir())/'workbench_preview.png'))
        record=dict(status='PASS' if ok else 'FAIL',scope='离线界面/模拟寄存器流程，非板测',
                    size=[w.width(),w.height()],application=w.device_record,advanced_dialog=advanced_ok)
        (Path(out_dir())/'workbench-selftest.json').write_text(json.dumps(record,ensure_ascii=False,indent=2),encoding='utf-8')
        w.editor._saved=w.editor.document();w.close()
    return 0 if ok else 1
