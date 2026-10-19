"""Resource ledger for the RA8875 renderer swap, diffed against the measured
baseline build.  Both builds are run with the same 103 input files, so every
difference comes from the two modules that were replaced."""
import json, re, xml.etree.ElementTree as ET
from pathlib import Path

R = Path(__file__).resolve().parent.parent
BASE = Path('D:/FPGA-Project/codex-builds/joint-probe-resources-20261019/build_nominal_v4')
SWAP = R/'build_swap_v0'

def value(node, key): return int(node.get(key, '0').split('(')[0])

def walk(node, path=''):
    path += ('/' if path else '') + node.get('name')
    l, a, s = [value(node, 'T_'+k) for k in ('Lut', 'Alu', 'Ssram')]
    row = dict(path=path, logic=l + a + 6*s, lut=l, alu=a, ssram=s,
               register=value(node, 'T_Register'), bsram=value(node, 'T_Bsram'))
    yield row
    for child in node:
        yield from walk(child, path)

def load(report):
    rows = list(walk(ET.parse(report).getroot()))
    return {r['path']: r for r in rows}

def pnr(report):
    text = report.read_text(encoding='utf-8', errors='replace')
    out = {}
    for key in ('Logic', 'Register', 'CLS', 'BSRAM', 'DSP'):
        m = re.search(r'\n\s*%s\s*\|\s*(\d+)\s*/\s*(\d+)' % key, text)
        if m:
            out[key] = (int(m.group(1)), int(m.group(2)))
    return out

base_syn, swap_syn = load(BASE/'impl/gwsynthesis/board_syn_rsc.xml'), load(SWAP/'impl/gwsynthesis/board_syn_rsc.xml')
base_pnr, swap_pnr = pnr(BASE/'impl/pnr/board.rpt.txt'), pnr(SWAP/'impl/pnr/board.rpt.txt')

delta = {k: (swap_pnr[k][0] - base_pnr[k][0], base_pnr[k][1]) for k in swap_pnr}
print('=== placed / routed totals ===')
for k, (d, cap) in delta.items():
    print('%s: %d -> %d (%+d) of %d' % (k, base_pnr[k][0], swap_pnr[k][0], d, cap))

print()
print('=== hierarchy deltas (synthesis XML) ===')
for p in sorted(set(base_syn) | set(swap_syn)):
    b, s = base_syn.get(p), swap_syn.get(p)
    if b is None:
        print('  + %-52s %+7d logic %+7d reg' % (p, s['logic'], s['register']))
    elif s is None:
        print('  - %-52s %+7d logic %+7d reg' % (p, -b['logic'], -b['register']))
    elif b['logic'] != s['logic'] or b['register'] != s['register']:
        print('    %-52s %+7d logic %+7d reg' % (p, s['logic']-b['logic'], s['register']-b['register']))

log = (SWAP/'console.log').read_text(encoding='utf-8', errors='replace')
print()
print('=== route status ===')
print('DesRoute failed' if 'DesRoute failed' in log else 'no DesRoute failure')
print('returncode see build stdout')
(R/'evidence').mkdir(exist_ok=True)
json.dump(dict(baseline_pnr=base_pnr, swap_pnr=swap_pnr,
               baseline_syn=base_syn, swap_syn=swap_syn),
          (R/'evidence/resource-diff.json').open('w'), indent=2, ensure_ascii=False)
