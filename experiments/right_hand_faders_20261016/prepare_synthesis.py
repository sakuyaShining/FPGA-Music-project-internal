"""Standalone logic estimate, not a physical pinout or a joint product build."""
from pathlib import Path
import shutil
ROOT=Path(__file__).resolve().parent
for profile,top in [('generic','rh_fader_bank'),('panel','rh_fader_panel')]:
 DST=ROOT/'synthesis'/profile;DST.mkdir(parents=True,exist_ok=True)
 for source in (ROOT/'rtl').glob('*.v'):shutil.copyfile(source,DST/source.name)
 (DST/'faders.gprj').write_text('''<?xml version="1.0" encoding="UTF-8"?>
<!DOCTYPE gowin-fpga-project>
<Project><Template>FPGA</Template><Version>5</Version>
<Device name="GW2AR-18C" pn="GW2AR-LV18QN88C8/I7">gw2ar18c-000</Device>
<FileList><File path="rh_fader_bank.v" type="file.verilog" enable="1"/>
<File path="rh_fader_panel.v" type="file.verilog" enable="1"/></FileList></Project>
''',encoding='utf-8')
 (DST/'synth.tcl').write_text('open_project "'+(DST/'faders.gprj').as_posix()+'"\nset_option -top_module '+top+'\nrun syn\nexit\n',encoding='utf-8')
 print(DST)
