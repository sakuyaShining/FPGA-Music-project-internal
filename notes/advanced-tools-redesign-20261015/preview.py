import json
import os
from pathlib import Path
import sys
import tempfile

os.environ['QT_QPA_PLATFORM']='offscreen'
os.environ['QT_QPA_FONTDIR']='C:/Windows/Fonts'
ROOT=Path('C:/Users/Sakuya/.codex/worktrees/ca03/FPGA-Music-project')
sys.path[:0]=[str(ROOT/'tools/host'),str(ROOT/'tools/scripts')]
from PyQt5.QtCore import QRect
from PyQt5.QtWidgets import QApplication
from workbench import WorkbenchWindow

OUT=Path('D:/FPGA-Project/host-workbench-20261015-11/evidence')
OUT.mkdir(parents=True,exist_ok=True)
app=QApplication([])
records=[]
with tempfile.TemporaryDirectory() as directory:
    w=WorkbenchWindow(directory+'/preferences.json')
    w.show();w.timer.stop();w._open_advanced();app.processEvents()
    d=w.advanced_dialog
    for theme,size,width,height,name in (
        ('paper','comfortable',1068,728,'advanced-tools-normal'),
        ('paper','large',800,560,'advanced-tools-small-large-text'),
        ('night','comfortable',1068,728,'advanced-tools-night')):
        w.theme_picker.setCurrentIndex(w.theme_picker.findData(theme))
        w.text_size_picker.setCurrentIndex(w.text_size_picker.findData(size))
        d.fit_to_available(QRect(0,0,width,height));app.processEvents()
        scroll=w.pages.widget(0)
        scroll.verticalScrollBar().setValue(0);app.processEvents()
        d.grab().save(str(OUT/(name+'.png')))
        scroll.verticalScrollBar().setValue(scroll.verticalScrollBar().maximum()//2);app.processEvents()
        d.grab().save(str(OUT/(name+'-scrolled.png')))
        records.append(dict(name=name,theme=theme,text_size=size,size=[d.width(),d.height()],
                            scroll_max=scroll.verticalScrollBar().maximum()))
    d.close();w.close()
(OUT/'previews.json').write_text(json.dumps(records,ensure_ascii=False,indent=2),encoding='utf-8')
print(json.dumps(records,ensure_ascii=False))
