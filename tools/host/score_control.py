"""Sequencer transactions run with exclusive RX ownership, never on the UI."""
from PyQt5.QtCore import QThread, pyqtSignal
import dsp_host as dh


def apply_sequence(link, notes=None, bpm=120, play=False):
    record=dict(status='FAILED',writes=[],sent_complete=False,play=bool(play),
                notes=notes,bpm=bpm,readback={})
    try:
        if notes is not None:
            if type(bpm)is not int or not 40<=bpm<=240:raise ValueError('速度应为40–240 BPM')
            # Validate the entire score before any write (including stop).
            score=dh.Frames();score.score(notes)
        if link.kind=='真实串口':
            for addr,expected in ((0xa4,0xd4),(0xa5,4),(0xa9,32)):
                if link.read_reg(addr)!=expected:raise RuntimeError('设备曲谱能力不匹配')
        f=dh.Frames()
        f.w('SEQ_CTRL',0,'停止旧曲谱并释放其音符')
        if notes is not None:
            f.w24('TEMPO',dh.tempo_inc(bpm),'曲谱速度')
            f.w('SEQ_VEL',0xc0,'曲谱力度12/15')
            f.items.extend(score.items)
            if play:f.w('SEQ_CTRL',1,'下载完成后开始循环播放')
        record['writes']=list(f.items)
        if link.send(f)!=2*len(f.items):raise RuntimeError('曲谱命令短写；设备状态未知')
        record['sent_complete']=True
        expected={'SEQ_CTRL':int(play and notes is not None)}
        if notes is not None:expected['SCORE_LEN']=len(notes)
        for name,value in expected.items():
            actual=link.read_reg(dh.REG[name]);record['readback'][name]=actual
            if actual!=value:raise RuntimeError('%s回读不符：%r / %r'%(name,actual,value))
        if notes is not None:
            tempo=[link.read_reg(0x51+i) for i in range(3)]
            if any(value is None for value in tempo):raise RuntimeError('曲谱速度回读超时')
            tempo=sum(value<<(8*i) for i,value in enumerate(tempo))
            record['readback']['TEMPO_INC']=tempo
            if tempo!=dh.tempo_inc(bpm):raise RuntimeError('曲谱速度回读不符')
        record['status']='CONFIRMED'
    except Exception as exc:record['error']=str(exc)
    return record


class SequenceWorker(QThread):
    result=pyqtSignal(object)
    def __init__(self,link,notes,bpm,play,parent=None):
        super().__init__(parent);self.link=link;self.notes=notes;self.bpm=bpm;self.play=play
    def run(self):
        lock=getattr(self.link,'_transaction',None)
        if lock is not None and not lock.acquire(blocking=False):
            self.result.emit(dict(status='FAILED',error='串口正忙，请稍后重试',writes=[],sent_complete=False,play=self.play))
            return
        try:self.result.emit(apply_sequence(self.link,self.notes,self.bpm,self.play))
        finally:
            if lock is not None:lock.release()
