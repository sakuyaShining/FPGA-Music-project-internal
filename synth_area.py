"""Synthesis-only area measurement. Does NOT place, route, or program.

Purpose: full build_board.py takes ~9 minutes because it runs PnR. Area is
decided entirely by synthesis, so this tool runs only `run syn` (~1-2 min) and
reports the per-module ledger. It never produces a bitstream and never touches
the programmer. Use it to iterate on area; use build_board.py to qualify.

    python synth_area.py <label> [--ref <reference.json>]

Writes evidence/synth-<label>.json. Refuses to overwrite an existing label.
"""
from common import *
import sys, shutil, time, re, argparse

EXE = os.environ.get('FPGA_GOWIN_GW_SH',
    'D:/FPGA-Project/Gowin/Gowin_V1.9.11.03_Education/Gowin_V1.9.11.03_Education_x64/IDE/bin/gw_sh.exe')


def parse_resource_html(path):
    """Per-module REG/ALU/LUT/DSP/BSRAM/SSRAM/ROM16 from Gowin's hierarchy report."""
    s = path.read_text(encoding='utf-8', errors='replace')
    s = s[s.find('MODULE NAME'):]
    out = {}
    for p in re.split(r'<td class="label">', s)[1:]:
        name = re.sub(r'<[^>]+>', '', p.split('</td>')[0])
        name = re.sub(r'\s+', ' ', name.replace('&nbsp', '')).strip()
        name = re.sub(r'\s*\(.*', '', name)
        cells = re.findall(r'align\s*=\s*"center">(.*?)</td>', p, re.S)
        if len(cells) < 7:
            continue

        def f(x):
            try:
                return float(x.strip())
            except ValueError:
                return 0.0
        out[name] = dict(zip(('reg', 'alu', 'lut', 'dsp', 'bsram', 'ssram', 'rom16'),
                             (f(c) for c in cells[:7])))
    return out


def totals(mod):
    t = {k: sum(v[k] for v in mod.values()) for k in ('reg', 'alu', 'lut', 'dsp', 'bsram', 'ssram', 'rom16')}
    # RAM16SDP4/LUT-RAM occupy Logic as well; weight matches resource_map.py.
    t['logic_equiv'] = t['lut'] + t['alu'] + 6 * t['ssram']
    return t


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument('label')
    ap.add_argument('--ref', default=None, help='previous synth-*.json to diff against')
    a = ap.parse_args()
    assert re.fullmatch(r'synth_[a-zA-Z0-9_]+', a.label), 'label must be synth_<name>'
    D = R / a.label
    assert not D.exists(), 'Refuse to overwrite an existing synthesis run'
    D.mkdir()

    files = sources() + list((R / 'engine/src').glob('*.hex')) + list((R / 'engine/src').glob('*.vh')) \
        + [R / 'constraints/sdram_board.cst', R / 'constraints/sdram_board.sdc']
    inputs, entries = {}, []
    for p in files:
        assert p.name not in inputs, ('duplicate basename', p)
        shutil.copyfile(p, D / p.name)
        inputs[p.name] = dict(source=p.relative_to(R).as_posix(), sha256=sha(p))
        kind = {'.v': 'file.verilog', '.cst': 'file.cst', '.sdc': 'file.sdc'}.get(p.suffix)
        if kind:
            entries.append('<File path="' + p.name + '" type="' + kind + '" enable="1"/>')

    (D / 'board.gprj').write_text(
        '<?xml version="1.0" encoding="UTF-8"?><!DOCTYPE gowin-fpga-project><Project>'
        '<Template>FPGA</Template><Version>5</Version>'
        '<Device name="GW2AR-18C" pn="GW2AR-LV18QN88C8/I7">gw2ar18c-000</Device>'
        '<FileList>' + ''.join(entries) + '</FileList></Project>')
    (D / 'build.tcl').write_text(
        'open_project "' + (D / 'board.gprj').as_posix() + '"\n'
        'set_option -top_module joint_timing_top\n'
        'set_option -use_sspi_as_gpio 1\n'
        'run syn\nexit\n')

    start = time.monotonic()
    with (D / 'console.log').open('w', encoding='utf-8') as f:
        proc = subprocess.Popen([EXE, str(D / 'build.tcl')], cwd=D, stdout=f, stderr=subprocess.STDOUT)
        try:
            rc = proc.wait(timeout=900)
        except subprocess.TimeoutExpired:
            subprocess.run(['taskkill', '/PID', str(proc.pid), '/T', '/F'], capture_output=True)
            proc.wait()
            rc = 124

    log = (D / 'console.log').read_text(encoding='utf-8', errors='replace')
    html = D / 'impl/gwsynthesis/board_syn_resource.html'
    ok = rc == 0 and not re.search(r'\bERROR\s*\(', log) and html.exists()
    assert ok, ('synthesis failed', rc, log[-3000:])

    mod = parse_resource_html(html)
    tot = totals(mod)
    ram = sorted(re.findall(r"Extracting RAM for identifier '([^']*)'", log))

    data = dict(status='synthesis measured; NOT placed or routed; NEVER PROGRAM',
                label=a.label, returncode=rc, seconds=round(time.monotonic() - start, 2),
                totals=tot, modules=mod, ram_extractions=len(ram),
                inputs=inputs, console_sha256=sha(D / 'console.log'),
                bench_gate=False, hardware_programmed=False)
    (E / ('synth-' + a.label + '.json')).write_text(json.dumps(data, indent=2), encoding='utf-8')

    print('%-8s %8s %8s %8s %8s %8s' % ('', 'REG', 'ALU', 'LUT', 'SSRAM', 'LOGICeq'))
    print('%-8s %8d %8d %8d %8d %8d' % ('total', tot['reg'], tot['alu'], tot['lut'], tot['ssram'], tot['logic_equiv']))
    print('RAM16 extractions: %d' % len(ram))

    if a.ref:
        ref_path = E / a.ref
        if not ref_path.exists() and not a.ref.startswith('synth-'):
            # Labels already start with 'synth_'; accept the bare label too.
            ref_path = E / ('synth-' + a.ref)
        ref = json.loads(ref_path.read_text(encoding='utf-8'))
        rm, rt = ref['modules'], ref['totals']
        print('\ndelta vs %s:  REG %+d  ALU %+d  LUT %+d  SSRAM %+d  LOGICeq %+d' % (
            a.ref, tot['reg'] - rt['reg'], tot['alu'] - rt['alu'],
            tot['lut'] - rt['lut'], tot['ssram'] - rt['ssram'],
            tot['logic_equiv'] - rt['logic_equiv']))
        print('\n%-40s %12s %12s' % ('module', 'LUT', 'REG'))
        for k in sorted(set(rm) | set(mod)):
            b = rm.get(k, dict(lut=0, reg=0)); c = mod.get(k, dict(lut=0, reg=0))
            dl, dr = c['lut'] - b['lut'], c['reg'] - b['reg']
            if abs(dl) >= 5 or abs(dr) >= 5:
                print('%-40s %5.0f->%5.0f %+5.0f  %5.0f->%5.0f %+5.0f' % (k[:40], b['lut'], c['lut'], dl, b['reg'], c['reg'], dr))


if __name__ == '__main__':
    main()
