"""Small, supported sound documents and a plain-language sound editor."""
import copy
import json
import os
from pathlib import Path
import tempfile
from PyQt5.QtCore import pyqtSignal
from PyQt5.QtWidgets import (QWidget,QLabel,QLineEdit,QComboBox,QPushButton,QVBoxLayout,
                            QHBoxLayout,QFileDialog,QMessageBox)
from instrument_config import default_config


def validate_tone(value):
    if not isinstance(value,dict) or set(value)!={'tone_schema','name','kind','preset','amplitudes'}:
        raise ValueError('请选择“我的音色”文件；旧的完整配置请在高级工具中打开。')
    if type(value['tone_schema']) is not int or value['tone_schema']!=1:
        raise ValueError('不支持此音色文件版本')
    if not isinstance(value['name'],str) or not value['name'].strip() or len(value['name'])>80 or any(ord(c)<32 for c in value['name']):
        raise ValueError('音色名称须为1–80个字符')
    if value['kind'] not in ('built_in','drawn') or type(value['preset']) is not int or not 0<=value['preset']<=3:
        raise ValueError('音色类型或内置音色无效')
    a=value['amplitudes']
    if not isinstance(a,list) or len(a)!=16 or any(type(v)is not int or not 0<=v<=255 for v in a):
        raise ValueError('手绘音色需有16个0–255的分量')
    return copy.deepcopy(value)


def compile_tone(value):
    tone=validate_tone(value)
    config=default_config(tone['name'])
    # Hand-drawn bars always represent integer harmonics, never a hidden bell
    # frequency-ratio table. Built-ins discard the drawing explicitly.
    config['preset']=tone['preset'] if tone['kind']=='built_in' else 0
    config['spectrum_mode']='add' if tone['kind']=='built_in' else 'replace'
    config['spectrum']=[0]*16 if tone['kind']=='built_in' else tone['amplitudes']
    return config,tone['kind']=='built_in'


class TonePanel(QWidget):
    apply_requested=pyqtSignal(object)
    def __init__(self,bars_class,presets,parent=None):
        super().__init__(parent)
        self.presets=presets;self.path=None
        self.saved=None
        v=QVBoxLayout(self);v.setContentsMargins(16,12,16,12)
        title=QLabel('编辑音色');title.setObjectName('PageTitle');v.addWidget(title)
        guide=QLabel('选择现成音色，或自己画一个声音。\n编辑和打开文件不会改变演奏，点“用于演奏”才生效。')
        guide.setWordWrap(True);v.addWidget(guide)
        self.name=QLineEdit('我的音色');self.name.setMaxLength(80)
        v.addWidget(QLabel('名称'));v.addWidget(self.name)
        self.kind=QComboBox();self.kind.addItem('内置音色','built_in');self.kind.addItem('手绘音色','drawn')
        v.addWidget(QLabel('音色来源'));v.addWidget(self.kind)
        self.preset=QComboBox();self.preset.addItems([name for name,_ in presets]);v.addWidget(self.preset)
        self.description=QLabel();self.description.setWordWrap(True);v.addWidget(self.description)
        self.drawing=QWidget();dv=QVBoxLayout(self.drawing);dv.setContentsMargins(0,0,0,0)
        self.bars=bars_class(16);self.bars.set_values([255]+[0]*15);self.bars.setMinimumHeight(150);dv.addWidget(self.bars)
        help=QLabel('第一根柱子是声音的主体；后面的柱子改变明亮度和质感。\n拖动柱子调整强弱。全部为零时没有声音。')
        help.setWordWrap(True);dv.addWidget(help)
        row=QHBoxLayout()
        for name,values in (('纯净',[255]+[0]*15),('明亮',[255,0,85,0,51,0,36,0,28,0,23,0,20,0,18,0])):
            b=QPushButton(name);b.clicked.connect(lambda checked=False,x=values:self.bars.set_values(x));row.addWidget(b)
        dv.addLayout(row);v.addWidget(self.drawing)
        self.use=QPushButton('用于演奏');self.use.setObjectName('Primary')
        self.use.clicked.connect(self._apply);v.addWidget(self.use)
        files=QHBoxLayout()
        for text,fn in (('打开音色',self.open_dialog),('保存音色',self.save_dialog)):
            b=QPushButton(text);b.clicked.connect(fn);files.addWidget(b)
        v.addLayout(files)
        self.status=QLabel('尚未用于演奏');self.status.setWordWrap(True);v.addWidget(self.status)
        v.addStretch()
        self.kind.currentIndexChanged.connect(self._mode)
        self._mode();self.saved=self.document()

    def _mode(self):
        drawn=self.kind.currentData()=='drawn'
        self.preset.setVisible(not drawn);self.drawing.setVisible(drawn)
        self.description.setText('自己决定声音成分。应用后将使用你画的声音。' if drawn else
            '管风琴适合持续长音；钢琴、钟和马林巴会逐渐衰减。选好后点“用于演奏”，再按键试听。')

    def document(self):
        return validate_tone(dict(tone_schema=1,name=self.name.text(),kind=self.kind.currentData(),
                                  preset=self.preset.currentIndex(),amplitudes=self.bars.values()))

    @property
    def dirty(self):
        try:return self.document()!=self.saved
        except ValueError:return True

    def _apply(self):
        try:self.apply_requested.emit(self.document())
        except ValueError as exc:self.status.setText(str(exc))

    def load_from(self,path):
        p=Path(path)
        if p.stat().st_size>65536:raise ValueError('音色文件过大')
        value=validate_tone(json.loads(p.read_text(encoding='utf-8')))
        self.name.setText(value['name']);self.kind.setCurrentIndex(self.kind.findData(value['kind']))
        self.preset.setCurrentIndex(value['preset']);self.bars.set_values(value['amplitudes'])
        self.saved=value;self.path=str(p);self.status.setText('已打开 · 尚未用于演奏')

    def save_to(self,path):
        value=self.document();p=Path(path);temporary=None
        try:
            with tempfile.NamedTemporaryFile(dir=str(p.parent),mode='w',encoding='utf-8',suffix='.tmp',delete=False) as f:
                temporary=f.name;json.dump(value,f,ensure_ascii=False,indent=2)
            os.replace(temporary,p);temporary=None
        finally:
            if temporary:os.unlink(temporary)
        self.saved=value;self.path=str(p);self.status.setText('已保存 · 保存不会改变演奏')

    def _discard(self):
        return not self.dirty or QMessageBox.question(self,'未保存的音色','放弃未保存的修改？',
            QMessageBox.Yes|QMessageBox.No,QMessageBox.No)==QMessageBox.Yes

    def open_dialog(self):
        if not self._discard():return
        path,_=QFileDialog.getOpenFileName(self,'打开我的音色','','音色 (*.json)')
        if not path:return
        try:self.load_from(path)
        except (OSError,ValueError) as exc:self.status.setText('打开失败：'+str(exc))

    def save_dialog(self):
        path,_=QFileDialog.getSaveFileName(self,'保存我的音色',self.path or '我的音色.fpga-tone.json','音色 (*.json)')
        if not path:return
        try:self.save_to(path)
        except (OSError,ValueError) as exc:self.status.setText('保存失败：'+str(exc))
