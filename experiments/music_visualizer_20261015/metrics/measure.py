"""Cycle-level performance audit. Production RTL is read, never edited.

The benches use #5 clocks for speed; all reported milliseconds are converted
from cycles at the real target 27MHz. The rendering bench shortens init and
skips static paint. Electrical protocol and startup evidence remain the earlier
27MHz pin-stream test; these benches measure dirty work and analysis schedules.
"""
import argparse
import hashlib
import json
import math
import subprocess
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
OUT = ROOT / 'metrics'
HZ = 27000000


def digest(path):
    return hashlib.sha256(path.read_bytes()).hexdigest()


def milliseconds(cycles):
    return cycles * 1000 / HZ


def simulate(name, top, sources, log):
    subprocess.run(['D:/iverilog/bin/iverilog.exe', '-g2012', '-I', 'rtl', '-s', top,
                    '-o', f'metrics/{name}.vvp', *sources], cwd=ROOT, check=True)
    with (OUT / log).open('w') as output:
        subprocess.run(['D:/iverilog/bin/vvp.exe', f'metrics/{name}.vvp'], cwd=ROOT,
                       stdout=output, stderr=subprocess.STDOUT, check=True)


def analyze():
    for stem, tb, sources in [
        ('render-budget', 'tb_render_budget.v', ['mv_renderer.v', 'mv_panel_driver.v', 'mv_spi_byte.v']),
        ('analysis-timing', 'tb_analysis_timing.v', ['mv_fft1024.v', 'mv_wave_capture.v'])]:
        dependencies = [OUT / tb] + [ROOT / 'rtl' / name for name in sources]
        if stem == 'render-budget':
            dependencies.append(ROOT / 'rtl/mv_font.vh')
        assert (OUT / f'{stem}.vvp').stat().st_mtime_ns >= max(p.stat().st_mtime_ns for p in dependencies)
        assert (OUT / f'{stem}.log').stat().st_mtime_ns >= (OUT / f'{stem}.vvp').stat().st_mtime_ns
    assert 'COMPLETE render budget 4' in (OUT/'render-simulation.log').read_text()
    assert 'PASS analysis timing 4' in (OUT/'analysis-simulation.log').read_text()
    raw = [line.split() for line in (OUT/'render-budget.log').read_text().splitlines()]
    starts = {int(f[2]): int(f[1]) for f in raw if f[0] == 'START'}
    frames = [dict(zip(('cycle', 'number', 'late'), map(int, f[1:]))) for f in raw if f[0] == 'FRAME']
    transfers = [dict(zip(('cycle', 'number', 'work_cycles', 'bytes', 'pixels', 'windows', 'late'),
                          map(int, f[1:]))) for f in raw if f[0] == 'TRANSFER']
    assert len(frames) == len(transfers) == len(starts) == 4
    for f in transfers:
        assert f['work_cycles'] == f['cycle'] - starts[f['number']]
        assert f['bytes'] == 2*f['pixels'] + 11*f['windows']
        f['work_ms_at_27MHz'] = milliseconds(f['work_cycles'])
    # The maximal changed wave span has 32+31 pixels per column. Spectrum
    # rises from zero to 35 pixels, all 48 bands, and the header changes.
    assert transfers[1]['pixels'] == 128*63 + 48*4*35 + 39 + 96*17
    assert transfers[1]['windows'] == 128*2 + 48 + 1 + 1
    trace = [int(f[3], 16) for f in raw if f[0] == 'TRACE']
    assert trace == [1 << 18]*4  # Held MIDI60; the short MIDI67 would be bit28.
    on = next(int(f[1]) for f in raw if f[0] == 'NOTE_ON')
    off = next(int(f[1]) for f in raw if f[0] == 'NOTE_OFF')
    assert off > on

    fft = {}
    wave_starts, wave_ends = [], []
    for line in (OUT/'analysis-timing.log').read_text().splitlines():
        f = line.split()
        if f[0].startswith('FFT_'):
            row = fft.setdefault(int(f[2]), {})
            row[f[0][4:].lower()] = int(f[1])
            if f[0] == 'FFT_READY':
                row['gap_samples'] = int(f[3])
        elif f[0] == 'WAVE_START': wave_starts.append(int(f[1]))
        elif f[0] == 'WAVE_READY': wave_ends.append(int(f[1]))
    assert len(fft) == 4 and len(wave_starts) == len(wave_ends) == 2
    fft_periods = []
    for k, row in fft.items():
        assert row['last'] - row['first'] == 1023*512
        row['capture_first_to_last_ms'] = milliseconds(row['last']-row['first'])
        row['last_sample_to_ready_ms'] = milliseconds(row['ready']-row['last'])
        row['first_sample_to_ready_ms'] = milliseconds(row['ready']-row['first'])
        if k > 1: fft_periods.append(fft[k]['ready']-fft[k-1]['ready'])
    assert len(set(fft_periods)) == 1
    previous = json.loads((ROOT/'verification.json').read_text())
    result = {
        'scope': 'Cycle-level digital measurements at nominal 27MHz; no physical panel/PnR claim',
        'production_rtl_changed': False,
        'normal_workload_prior_evidence': {
            'gui_boundary_intervals_ms': previous['panel']['boundary_intervals_ms'],
            'draw_work_ms': previous['panel']['post_startup_transfer_work_ms'],
            'first_transfer_done_ms': previous['panel']['frames'][0]['transfer_done_ms'],
            'first_boundary_ms': previous['panel']['frames'][0]['boundary_ms']},
        'stress': {'transfers': transfers,
            'nominal_20hz_deadline_met_for_all_tested_transitions': all(f['work_cycles'] < 1350000 for f in transfers),
            'largest_work_ms': max(f['work_ms_at_27MHz'] for f in transfers),
            'frame_boundary_intervals_ms': [milliseconds(b['cycle']-a['cycle']) for a,b in zip(frames,frames[1:])],
            'transfer_completion_intervals_ms': [milliseconds(b['cycle']-a['cycle']) for a,b in zip(transfers,transfers[1:])],
            'late_frames_final': frames[-1]['late'],
            'note': 'Conservative legal interface stress, not proof all bands can reach this height simultaneously from bounded PCM.'},
        'short_note_trace': {'duration_ms': milliseconds(off-on), 'trace_samples': trace,
                             'midi67_expected_bit': 28, 'ever_visible': any(v & (1 << 28) for v in trace),
                             'meaning': 'Display trace can miss an accepted short note; this does not demonstrate audio note loss.'},
        'analysis': {'sample_rate_hz': HZ/512, 'fft_size':1024, 'bin_spacing_hz': HZ/512/1024,
                     'nominal_window_duration_ms': milliseconds(1024*512), 'windows':fft,
                     'fft_period_ms': milliseconds(fft_periods[0]), 'fft_update_hz': HZ/fft_periods[0],
                     'wave_request_to_ready_ms':[milliseconds(b-a) for a,b in zip(wave_starts,wave_ends)],
                     'nominal_wave_snapshot_ms': milliseconds(512*512),
                     'nominal_wave_snapshot_coverage_per_50ms_percent': milliseconds(512*512)/50*100},
        'derived_from_rtl': {'bar_max_height_px':35, 'bar_release_px_per_update':2,
                            'bar_max_release_updates':math.ceil(35/2), 'bar_release_ms_at_20hz':900,
                            'trace_pixels_per_semitone':1.5, 'trace_cents_per_pixel':100/1.5,
                            'trace_sweep_seconds':288/20,
                            'wave_continuous_step_visibility_estimate': 'Roughly 50-100ms plus column drawing; schedule inference, not measured photon latency.'},
        'still_unverified': ['worst-case analog panel latency', 'tearing/TE wiring', 'brightness and RGB direction',
                            'full-product place-and-route', 'universal bound for real PCM workloads'],
    }
    sources = list((ROOT/'rtl').glob('*')) + list(ROOT.glob('*1024.hex')) + list(OUT.glob('*.v')) + [Path(__file__).resolve()]
    logs = [OUT / name for name in ('render-budget.log', 'render-simulation.log', 'analysis-timing.log', 'analysis-simulation.log')]
    logs += [ROOT/'verification.json', ROOT/'delivery-audit.json']
    result['source_sha256'] = {str(p.relative_to(ROOT)):digest(p) for p in sources}
    result['evidence_sha256'] = {str(p.relative_to(ROOT)):digest(p) for p in logs}
    (OUT/'metrics-summary.json').write_text(json.dumps(result,indent=2)+'\n')
    print(json.dumps({'audit':'COMPLETE', 'all_stress_20hz_met':result['stress']['nominal_20hz_deadline_met_for_all_tested_transitions'],
        'max_work_ms':result['stress']['largest_work_ms'], 'fft_hz':result['analysis']['fft_update_hz'],
        'short_note_ever_visible':result['short_note_trace']['ever_visible']}))


def main():
    parser=argparse.ArgumentParser()
    parser.add_argument('--analyze-existing',action='store_true')
    args=parser.parse_args()
    if not args.analyze_existing:
        simulate('render-budget','tb_render_budget',
            ['rtl/mv_renderer.v','rtl/mv_panel_driver.v','rtl/mv_spi_byte.v','metrics/tb_render_budget.v'],'render-simulation.log')
        simulate('analysis-timing','tb_analysis_timing',
            ['rtl/mv_fft1024.v','rtl/mv_wave_capture.v','metrics/tb_analysis_timing.v'],'analysis-simulation.log')
    analyze()


if __name__=='__main__': main()
