"""Check preserved source, final synthesis inputs and report identities."""
import hashlib
import json
import re
import zipfile
from pathlib import Path

ROOT = Path(__file__).resolve().parent
REPO = ROOT.parents[1]
ENGINE = Path('C:/Users/Sakuya/.codex/worktrees/instrument-engine-safety/FPGA-Music-project')
BACKUP = REPO / 'notes/backups/20261015-085907-before-music-visualizer'


def sha(path):
    return hashlib.sha256(path.read_bytes()).hexdigest()


def main():
    receipt = json.loads((BACKUP / 'backup-receipt.json').read_text(encoding='utf-8'))
    archives = {}
    for name, entry in receipt['archives'].items():
        path = Path(entry['path'])
        assert sha(path) == entry['sha256']
        with zipfile.ZipFile(path) as archive:
            assert archive.testzip() is None
            assert len(archive.namelist()) == entry['files']
            for relative, digest in entry['file_sha256'].items():
                assert hashlib.sha256(archive.read(relative)).hexdigest() == digest
                if name == 'main-source':
                    assert sha(REPO / relative) == digest, relative
        archives[name] = {'files': entry['files'], 'sha256': entry['sha256'], 'crc_and_content_pass': True}
    manifest = json.loads((ENGINE / 'project/versions/engine-safety-20261014-01.json').read_text(encoding='utf-8'))
    for relative, digest in manifest['files'].items():
        assert sha(ENGINE / relative) == digest, relative
    artifacts = {}
    current = list((ROOT / 'rtl').glob('*')) + list(ROOT.glob('*1024.hex'))
    for folder, stem in [('synthesis', 'visualizer'), ('engine_probe', 'probe')]:
        for source in current:
            assert sha(source) == sha(ROOT / folder / source.name), (folder, source.name)
        html_path = ROOT / folder / 'impl/gwsynthesis' / f'{stem}_syn.rpt.html'
        html = html_path.read_text(encoding='utf-8', errors='replace')
        logic = int(re.search(r'<td class="label">Logic</td>\s*<td>(\d+)', html)[1])
        bsram = int(re.search(r'<td class="label">BSRAM</td>\s*<td>(\d+)', html)[1])
        registers = int(re.search(r'<td class="label">Register</td>\s*<td>(\d+)', html)[1])
        files = list((ROOT / folder).glob('*.v')) + list((ROOT / folder).glob('*.vh')) + list((ROOT / folder).glob('*.hex'))
        files += [ROOT / folder / f'{stem}.gprj', ROOT / folder / 'synth.tcl', html_path,
                  html_path.with_name(f'{stem}_syn_rsc.xml')]
        artifacts[folder] = {'logic': logic, 'logic_capacity': 20736, 'registers': registers,
                             'bsram': bsram, 'bsram_capacity': 46,
                             'files_sha256': {str(p.relative_to(ROOT)): sha(p) for p in files}}
    # Every core input except the intentional read-only tap is byte-for-byte copied.
    copies = json.loads((ROOT / 'engine_probe/copied-inputs.json').read_text(encoding='utf-8'))
    for name, digest in copies.items():
        if name != 'tdm_top.v':
            assert sha(ROOT / 'engine_probe' / name) == digest, name
    original = (REPO / 'notes/visualization-feasibility-20261015/probes/core_expression/tdm_top.v').read_text(encoding='utf-8')
    reference = (ROOT / 'engine_probe/tdm_top_reference.v').read_text(encoding='utf-8')
    assert reference == original.replace('module tdm_top #(', 'module tdm_top_reference #(')
    expected = original.replace('output wire [6:0] voice_note',
        'output wire [6:0] voice_note,\n    output wire monitor_valid,\n    output wire signed [15:0] monitor_pcm')
    expected = expected.replace('endmodule', 'assign monitor_valid=sample_en;\nassign monitor_pcm=audio[23:8];\nendmodule')
    assert (ROOT / 'engine_probe/tdm_top.v').read_text(encoding='utf-8') == expected
    isolation = (ROOT / 'engine-isolation.log').read_text(encoding='utf-8')
    match = re.search(r'PASS engine isolation cycles=(\d+) samples=(\d+) nonzero=(\d+) lcd_edges=(\d+) spectra=(\d+) note_events=(\d+)', isolation)
    assert match, 'engine isolation test must pass'
    experiment_inputs = list((ROOT/'rtl').glob('*')) + list(ROOT.glob('*.v')) + list(ROOT.glob('*.py')) + list(ROOT.glob('*.hex'))
    result = {'status': 'PASS', 'main_backup_files_unchanged': 297,
              'engine_manifest_inputs_unchanged': len(manifest['files']),
              'archives': archives, 'synthesis': artifacts,
              'engine_isolation': dict(zip(('cycles', 'samples', 'nonzero', 'lcd_edges', 'spectra', 'note_events'), map(int, match.groups()))),
              'engine_isolation_log_sha256': sha(ROOT/'engine-isolation.log'),
              'experiment_inputs_sha256': {str(p.relative_to(ROOT)): sha(p) for p in experiment_inputs},
              'core_copy_changes': 'two output-only PCM taps; original and reference otherwise identical',
              'not_verified': ['physical I/O', 'place and route', 'actual panel', 'full future product']}
    (ROOT / 'delivery-audit.json').write_text(json.dumps(result, indent=2)+'\n')
    print(json.dumps({k: v for k, v in result.items() if k not in ('archives', 'synthesis', 'experiment_inputs_sha256')}))


if __name__ == '__main__':
    main()
