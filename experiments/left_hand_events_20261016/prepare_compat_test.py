from pathlib import Path
R=Path(__file__).resolve().parent;U=R.parent/'system_integration_20261016'
s=(R/'rtl/rh_music_probe.v').read_text(encoding='utf-8').replace('module rh_music_probe #(','module compat_music_probe #(').replace('    tdm_top_rh #(','    tdm_top_owned #(')
(R/'candidate/compat_music_probe.v').write_text(s,encoding='utf-8')
s=(U/'tb_compat_music.v').read_text(encoding='utf-8').replace('    rh_music_probe dut(', '    compat_music_probe dut(')
(R/'tb_compat_music.v').write_text(s,encoding='utf-8')
print('Prepared original PCM/I2S compatibility test with owned input disabled')
