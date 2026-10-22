"""Summarize actual synthesis reports and explicit display assumptions."""
import hashlib
import json
from pathlib import Path
import re
import xml.etree.ElementTree as ET

ROOT = Path(__file__).resolve().parent


def sha(p):
    return hashlib.sha256(p.read_bytes()).hexdigest()


def main():
    evidence = json.loads((ROOT / 'source-inputs.json').read_text(encoding='utf-8'))
    source = Path(evidence['source_root'])
    unchanged = all(sha(source / name) == value for name, value in evidence['source_files'].items())
    results = {'scope': 'isolated synthesis only; no new PnR, functional or board acceptance',
               'source_inputs_unchanged': unchanged, 'profiles': {}}
    for name in ('live_reference', 'core_expression'):
        dst = ROOT / 'probes' / name
        report = dst / 'impl/gwsynthesis/probe_syn.rpt.html'
        xml = dst / 'impl/gwsynthesis/probe_syn_rsc.xml'
        root = ET.parse(xml).getroot()
        text = report.read_text(encoding='utf-8')
        logic = int(re.search(r'>Logic</td>\s*<td>(\d+)', text).group(1))
        counts = {k: int(root.attrib[k].split('(')[0]) for k in ('T_Register', 'T_Lut', 'T_Alu', 'T_Bsram', 'T_Ssram')}
        console = (dst / 'synthesis-console.txt').read_text(encoding='utf-8', errors='replace')
        success = 'GowinSynthesis finish' in console and 'ERROR' not in console
        results['profiles'][name] = {'synthesis_completed': success, 'logic': logic, **counts,
                                    'report_sha256': sha(report), 'hierarchy_sha256': sha(xml),
                                    'no_pin_constraints': True, 'no_timing_acceptance': True}
    ref, core = [results['profiles'][x] for x in ('live_reference', 'core_expression')]
    results['reference_minus_core'] = {k: ref[k] - core[k] for k in ('logic', 'T_Register', 'T_Lut', 'T_Alu', 'T_Bsram')}
    results['core_nominal_headroom_not_final_product'] = {
        'logic': 20736 - core['logic'], 'bsram_blocks': 46 - core['T_Bsram'],
        'bsram_bytes_upper_bound': (46 - core['T_Bsram']) * 18432 // 8,
        'excludes': ['new touch frontend', 'writable instrument lifecycle', 'layer allocator',
                     'FFT and waveform/trajectory analysis', 'screen renderer', 'encoder and EEPROM controllers'],
    }
    results['display_assumptions'] = []
    for w, h in ((240, 240), (320, 240), (480, 320), (800, 480)):
        bits = w * h * 16
        results['display_assumptions'].append({
            'width': w, 'height': h, 'rgb565_frame_bytes': bits // 8,
            'pixel_mbps_at_20_fps': bits * 20 / 1e6,
            'spi_full_frame_fps_ideal': {str(mhz): mhz * 1e6 / bits for mhz in (13.5, 20, 40)},
            'not_included': 'commands, idle, bus sharing, blanking and panel limits; not actual screen identity',
        })
    results['checks_passed'] = unchanged and all(x['synthesis_completed'] for x in results['profiles'].values())
    (ROOT / 'assessment.json').write_text(json.dumps(results, ensure_ascii=False, indent=2) + '\n', encoding='utf-8')
    print(json.dumps(results, ensure_ascii=False, indent=2))
    return 0 if results['checks_passed'] else 1


if __name__ == '__main__':
    raise SystemExit(main())
