"""Plot archived real FPGA samples; never connects to a board."""
import json
import hashlib
from pathlib import Path
import numpy as np
import matplotlib
matplotlib.use('Agg')
import matplotlib.pyplot as plt
from matplotlib.font_manager import FontProperties

ROOT=Path(__file__).resolve().parents[3]
OUT=Path(__file__).resolve().parent
SRC=ROOT/'project/evidence/bench/20261010-session-check02'
FS=52734.375
font=FontProperties(fname='C:/Windows/Fonts/msyh.ttc')
plt.rcParams.update({'axes.facecolor':'#f7f9fc','figure.facecolor':'white','axes.edgecolor':'#b5c0ce','grid.color':'#dce3ed'})
fig,axes=plt.subplots(2,2,figsize=(12,6.6),layout='constrained')
items=[('a4_base.npy','A4 基准音','#2563eb',440.955),('a4_plus75cents.npy','同一音：位置移动 +75 cents','#c2410c',460.267)]
provenance={}
for col,(filename,label,color,peak) in enumerate(items):
    path=SRC/filename
    x=np.load(path,allow_pickle=False).astype(float)
    assert len(x)==2048 and np.isfinite(x).all()
    y=x/(2**23)
    ax=axes[0,col]
    ax.plot(np.arange(len(x))/FS*1000,y,color=color,lw=.85)
    ax.set_title(label,fontproperties=font,fontsize=13)
    ax.set_xlabel('时间 / ms',fontproperties=font)
    ax.set_ylabel('数字满幅比例',fontproperties=font)
    ax.set_xlim(0,len(x)/FS*1000)
    ax.grid(alpha=.7)
    w=np.hanning(len(x))
    amp=2*np.abs(np.fft.rfft((y-y.mean())*w,n=16384))/w.sum()
    freq=np.fft.rfftfreq(16384,1/FS)
    db=20*np.log10(np.maximum(amp,1e-8))
    ax=axes[1,col]
    ax.plot(freq,db,color=color,lw=1)
    ax.set_xlim(0,2200); ax.set_ylim(-105,0)
    ax.set_xlabel('频率 / Hz',fontproperties=font)
    ax.set_ylabel('幅度 / dBFS',fontproperties=font)
    ax.axvline(peak,color=color,alpha=.4,ls='--')
    ax.set_title('实测谱峰约 %.2f Hz'%peak,fontproperties=font,fontsize=12)
    ax.grid(alpha=.7)
    provenance[filename]={'sha256':hashlib.sha256(path.read_bytes()).hexdigest(),'samples':len(x),'rms_fullscale':float(np.sqrt(np.mean(y*y))),'peak_fullscale':float(np.abs(y).max())}
fig.suptitle('真实 FPGA 数字采样 · 历史记录对照（非实时 / 非模拟音频回录）',fontproperties=font,fontsize=15)
fig.savefig(OUT/'actual-waveform-spectrum.png',dpi=150)
plt.close(fig)
record={'source':'project/evidence/bench/20261010-session-check02','report_finished_utc':json.loads((SRC/'report.json').read_text(encoding='utf-8'))['finished_at'],'sample_rate_hz':FS,'window_ms':2048/FS*1000,'input_files':provenance,'analysis':'24bit fullscale normalization; Hann window;16384-point zero-padded FFT; padding does not improve underlying resolution','scope':'Archived FPGA internal samples, no current capture, no DAC or speaker measurement'}
(OUT/'plot-record.json').write_text(json.dumps(record,ensure_ascii=False,indent=2)+'\n',encoding='utf-8')
print(OUT/'actual-waveform-spectrum.png')
