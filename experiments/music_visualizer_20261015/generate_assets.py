import json
import math
from pathlib import Path

ROOT=Path(__file__).resolve().parent


def write_hex(name, values, width=4):
    (ROOT/name).write_text(''.join(f'{v & ((1<<(width*4))-1):0{width}x}\n' for v in values),encoding='ascii')


def main():
    write_hex('hann1024.hex',[round((0.5-0.5*math.cos(2*math.pi*i/1023))*32767) for i in range(1024)])
    write_hex('cos1024.hex',[round(math.cos(2*math.pi*i/1024)*32767) for i in range(512)])
    write_hex('sin1024.hex',[round(-math.sin(2*math.pi*i/1024)*32767) for i in range(512)])
    edges=[1]
    for i in range(1,48):
        edges.append(max(edges[-1]+1,round(512**(i/48))))
    edges.append(512)
    assert edges==sorted(set(edges)) and edges[-2]<512
    bands=[]
    for i in range(512):
        bands.append(next((b for b in range(48) if edges[b]<=i<edges[b+1]),0))
    write_hex('bands1024.hex',bands,2)
    fs=27000000/512
    (ROOT/'band-layout.json').write_text(json.dumps({'sample_rate_hz':fs,'fft_length':1024,
        'bin_hz':fs/1024,'edges_bins':edges,'edges_hz':[x*fs/1024 for x in edges],
        'display':'48 roughly logarithmic FFT bands, DC excluded; relative log L1 magnitude, not calibrated dBFS'},indent=2)+'\n')
    signals={
        'silence':[0]*1024,
        'dc':[20000]*1024,
        'single':[round(26000*math.sin(2*math.pi*16*i/1024)) for i in range(1024)],
        'dual':[round(15000*math.sin(2*math.pi*8*i/1024)+9000*math.sin(2*math.pi*37*i/1024)) for i in range(1024)],
        'negative_full':[-32768]*1024,
    }
    for name,samples in signals.items(): write_hex(f'test-{name}.hex',samples)
    from PIL import Image,ImageDraw,ImageFont
    chars=list(dict.fromkeys('音乐可视化波形频谱轨迹1234高低'))
    font=ImageFont.truetype('C:/Windows/Fonts/msyh.ttc',14)
    rows=[]
    for char in chars:
        image=Image.new('L',(14,14));draw=ImageDraw.Draw(image)
        box=draw.textbbox((0,0),char,font=font)
        draw.text(((14-(box[2]-box[0]))//2-box[0],-box[1]),char,font=font,fill=255)
        for y in range(14): rows.append(sum((image.getpixel((x,y))>=96)<<(13-x) for x in range(14)))
    lines=['function [13:0] glyph_row;','input [8:0] address;','begin case(address)']
    lines += [f"9'd{i}: glyph_row=14'h{value:04x};" for i,value in enumerate(rows)]
    lines += ["default: glyph_row=0;",'endcase end endfunction']
    (ROOT/'rtl/mv_font.vh').write_text('\n'.join(lines)+'\n',encoding='ascii')
    (ROOT/'font-map.json').write_text(json.dumps(dict(zip(chars,range(len(chars)))),ensure_ascii=False,indent=2)+'\n',encoding='utf-8')
    print(json.dumps({'assets':4,'fft_test_cases':list(signals)}))


if __name__=='__main__': main()
