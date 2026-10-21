"""Offline corridor feasibility: preserve physical pads/power/sensors and pin escapes."""
import copy,json,re,sys
sys.path.insert(0,'D:/FPGA-Project/codex-tools/pcb-resume-20261020')
import shapely
import grid_route as grid
import reserve_escape as escape
from native_review import ROOT

source=json.loads((ROOT/'controls-final-source-78.json').read_text())
audio={'I2S_BCK','I2S_DIN','I2S_LRCK'}
power={'GND','3V3_IO','3V3_PERIPH','DAC_3V3','5V_PERIPH','5V_FUSED','5V_IN','5V_PROTECTED','5V_USB'}
allnets={p['net'] for p in source['lines']+source['vias']}
soft={n for n in allnets if n not in power|audio and not re.fullmatch(r'L[0-5]_[ME]\d\d',n)
      and not n.startswith(('DAC_','AUX_','PWR_'))}
working={**source,'pads':copy.deepcopy(source['pads']),'lines':[p for p in source['lines'] if p['net'] not in soft],
         'vias':[p for p in source['vias'] if p['net'] not in soft]}
fans={n:escape.reserve(source,working,n) for n in sorted(soft)}
# Real pads remain original. Retained short lines/vias represent real obstacles;
# virtual anchors and exclusion flags must not escape this exploratory setup.
working['pads']=source['pads']
(ROOT/'quality-corridor-virtual-source.json').write_text(json.dumps(working,indent=2),encoding='utf-8')
(ROOT/'quality-corridor-soft-nets.json').write_text(json.dumps({'soft_nets':sorted(soft),'retained_escape_lines':sum(len(f['lines']) for f in fans.values()),'not_native_source':True},indent=2),encoding='utf-8')
print('SOFT NETS',len(soft),sorted(soft),flush=True)
