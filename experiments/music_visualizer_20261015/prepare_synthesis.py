import shutil
from pathlib import Path

ROOT=Path(__file__).resolve().parent
dst=ROOT/'synthesis'
dst.mkdir(exist_ok=True)
sources=list((ROOT/'rtl').glob('*.v'))
for source in sources+list((ROOT/'rtl').glob('*.vh'))+list(ROOT.glob('*1024.hex')):
    shutil.copyfile(source,dst/source.name)
xml=['<?xml version="1.0" encoding="UTF-8"?>','<!DOCTYPE gowin-fpga-project>',
    '<Project><Template>FPGA</Template><Version>5</Version>',
    '<Device name="GW2AR-18C" pn="GW2AR-LV18QN88C8/I7">gw2ar18c-000</Device>','<FileList>']
xml += [f'<File path="{p.name}" type="file.verilog" enable="1"/>' for p in sources]
xml+=['</FileList></Project>']
(dst/'visualizer.gprj').write_text('\n'.join(xml)+'\n')
(dst/'synth.tcl').write_text(f'open_project "{(dst/"visualizer.gprj").as_posix()}"\nset_option -top_module music_visualizer\nrun syn\nexit\n')
print(dst)
