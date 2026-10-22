"""Record actual driver/core-driver synthesis results; no PnR acceptance."""
import hashlib
import json
from pathlib import Path
import re
import xml.etree.ElementTree as ET

ROOT = Path(__file__).resolve().parent


def sha(path):
    return hashlib.sha256(path.read_bytes()).hexdigest()


def main():
    results = {'scope': 'synthesis only; logical interfaces exposed as ports, not physical pinout', 'profiles': {}}
    for profile in ('driver', 'core_driver'):
        folder = ROOT / 'synthesis' / profile
        report = folder / 'impl/gwsynthesis/probe_syn.rpt.html'
        xml = folder / 'impl/gwsynthesis/probe_syn_rsc.xml'
        root = ET.parse(xml).getroot()
        html = report.read_text(encoding='utf-8')
        console = (folder / 'synthesis-console.txt').read_text(encoding='utf-8', errors='replace')
        assert 'GowinSynthesis finish' in console and 'ERROR' not in console
        assert sha(ROOT / 'rtl/ili9341_spi_byte.v') == sha(folder / 'ili9341_spi_byte.v')
        assert sha(ROOT / 'rtl/ili9341_window.v') == sha(folder / 'ili9341_window.v')
        results['profiles'][profile] = {
            'logic': int(re.search(r'>Logic</td>\s*<td>(\d+)', html).group(1)),
            'registers': int(root.attrib.get('T_Register', '0').split('(')[0]),
            'bsram': int(root.attrib.get('T_Bsram', '0').split('(')[0]),
            'io_ports_probe_only': int(re.search(r'>I/O Port </b></td>\s*<td>(\d+)', html).group(1)),
            'report_sha256': sha(report), 'hierarchy_sha256': sha(xml),
        }
    baseline_root = ROOT.parent / 'visualization-feasibility-20261015'
    baseline = json.loads((baseline_root / 'assessment.json').read_text(encoding='utf-8'))['profiles']['core_expression']
    results['core_baseline'] = {k: baseline[k] for k in ('logic', 'T_Register', 'T_Bsram')}
    results['combined_logic_delta_not_standalone_cost'] = results['profiles']['core_driver']['logic'] - baseline['logic']
    manifest = json.loads((baseline_root / 'source-inputs.json').read_text(encoding='utf-8'))
    for name, digest in manifest['source_files'].items():
        assert sha(ROOT / 'synthesis/core_driver' / Path(name).name) == digest, f'copied core mismatch: {name}'
    results['copied_core_inputs_match_previous_probe'] = True
    results['limitations'] = ['no physical IO allocation or PnR', 'pixel producer/FFT/trajectory renderer absent',
                              'new custom-instrument/layering/touch/encoder/storage logic absent',
                              'no physical display or audio test', 'core profile excludes diagnostic/PC live observation']
    (ROOT / 'evidence/synthesis-review.json').write_text(json.dumps(results, indent=2) + '\n', encoding='utf-8')
    print(json.dumps(results, indent=2))


if __name__ == '__main__':
    main()
