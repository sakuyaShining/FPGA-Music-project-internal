"""Reserve fine-pitch escapes before planning long core trunks, virtual only."""
import hashlib
import json
import re
import grid_route as grid
import reserve_escape as escape
from physical_geometry import actual_pad
from native_review import ROOT

source=grid.capture();raw=json.dumps(source).encode()
source_name='grid-source-core-fanouts.json';(ROOT/source_name).write_bytes(raw)
drc=json.loads((ROOT/'pcb-drc.json').read_text(encoding='utf-8'))
protected={'GND','5V_IN','5V_FUSED','5V_PROTECTED','5V_PERIPH','3V3_IO','3V3_PERIPH','DAC_3V3'}
nets=[n['name'] for c in drc if c['name']=='Connection Error' for n in c['list'] if n['name'] not in protected]
assert len(nets)==25
# The recently planned mute trace crosses beneath the three I2S input toes.
# Temporarily remove it only in the virtual copy, then restore connectivity by
# planning it after the signal escapes. No native copper is changed here.
nets.append('DAC_XSMT')
working={**source,'pads':list(source['pads']),'lines':[p for p in source['lines'] if p['net'] not in nets],
         'vias':[p for p in source['vias'] if p['net'] not in nets]}
grid.pad_shape=actual_pad;grid.GAP=.17;escape.pad_shape=actual_pad;escape.GAP=.17
refs={p['ref'] for p in source['pads'] if re.fullmatch(r'U\d+',p['ref'])}
# Put the constrained audio input group first, before long bus fanouts.
order=['I2S_BCK','I2S_DIN','I2S_LRCK']+[n for n in nets if n not in ['I2S_BCK','I2S_DIN','I2S_LRCK']]
first=escape.new_mux_fanouts(working,order,refs=refs)
print('DIRECT FANOUTS',first['new_fanouts'],flush=True)
second=escape.grid_mux_fanouts(working,order,refs=refs)
print('SEARCHED FANOUTS',second['new_fanouts'],flush=True)
pending=[(p['ref'],p['n'],p['net']) for p in working['pads'] if p['net'] in nets and p['ref'] in refs and not p.get('routing_pad_exclude') and min(p['shape'][1:3])*grid.MM<=.6]
result={'nets':nets,'source_file':source_name,'source_sha256':hashlib.sha256(raw).hexdigest(),
        'working':working,'fanouts':[first,second],'pending_fine_pitch_pads':pending,
        'requires_trunk_routing_continuity_check_and_native_drc':True}
(ROOT/'grid-core-fanouts-probe.json').write_text(json.dumps(result,indent=2),encoding='utf-8')
print('PENDING FINE PADS',pending,flush=True)
