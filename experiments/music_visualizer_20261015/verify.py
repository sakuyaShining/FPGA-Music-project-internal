"""Independent floating point FFT reference + pin-stream LCD receiver.

The pictures are reconstructed from transmitted SPI bytes, not drawn from the
intended UI. This is a digital controller model, not a physical panel test.
"""
import hashlib
import json
import re
import tempfile
from pathlib import Path

import numpy as np
from PIL import Image

ROOT = Path(__file__).resolve().parent


def signed_hex(path):
    a = np.array([int(s, 16) for s in path.read_text().split()], dtype=np.int64)
    return np.where(a >= 32768, a - 65536, a)


def verify_fft():
    bins = np.loadtxt(ROOT / 'fft-bins.txt', dtype=int)
    result = []
    for case_id, name in enumerate(['silence', 'dc', 'single', 'dual', 'negative_full']):
        row = bins[bins[:, 0] == case_id]
        assert np.array_equal(row[:, 1], np.arange(512)), name
        x = signed_hex(ROOT / f'test-{name}.hex')
        # Independent mathematical reference, no emulation of HDL butterflies.
        ref = np.fft.fft(x * np.hanning(1024))[:512] / 1024
        actual = row[:, 2] + 1j * row[:, 3]
        error = float(np.max(np.abs(actual - ref)))
        assert error <= 12, (name, error)
        if name == 'silence':
            assert np.all(actual == 0)
        if name == 'single':
            assert np.argmax(np.abs(actual)) == 16
        if name == 'dual':
            assert np.argmax(np.abs(actual)) == 8
            assert np.argmax(np.abs(actual[32:42])) + 32 == 37
        result.append({'case': name, 'max_complex_error_lsb': error,
                       'peak_bin': int(np.argmax(np.abs(actual)))})
    log = (ROOT / 'fft-simulation.log').read_text()
    assert 'PASS fft interface 5 cases' in log
    assert [int(s) for s in re.findall(r'gaps=(\d+)', log)] == [4, 8, 12, 16, 20]
    return result


def rgb565(array):
    a = array.astype(np.uint32)
    return np.stack([((a >> 11) & 31) * 255 // 31,
                     ((a >> 5) & 63) * 255 // 63,
                     (a & 31) * 255 // 31], axis=-1).astype('uint8')


def verify_panel(capture=None):
    gram = np.zeros((240, 320), dtype=np.uint16)
    command = None
    data = []
    bounds = {}
    high_byte = None
    pixel_count = 0
    window_count = 0
    all_bytes = 0
    mode = None
    colmod = None
    frames, transfer_times, snapshots = [], [], []
    first_static = None

    def finish_window():
        if command == 0x2C:
            l, r = bounds[0x2A]
            t, b = bounds[0x2B]
            assert high_byte is None and pixel_count == (r-l+1)*(b-t+1), (bounds, pixel_count)

    for line in (capture or ROOT / 'visualizer-spi.log').read_text().splitlines():
        fields = line.split()
        if fields[0] == 'BYTE':
            all_bytes += 1
            dc, value = int(fields[2]), int(fields[3], 16)
            if dc == 0:
                finish_window()
                command, data, pixel_count, high_byte = value, [], 0, None
                if value == 0x2C:
                    assert mode == 0x20 and colmod == 0x55
                    l, r = bounds[0x2A]
                    t, b = bounds[0x2B]
                    assert 0 <= l <= r < 320 and 0 <= t <= b < 240
                    window_count += 1
            elif command == 0x2C:
                if high_byte is None:
                    high_byte = value
                else:
                    l, r = bounds[0x2A]
                    t, b = bounds[0x2B]
                    assert pixel_count < (r-l+1)*(b-t+1), 'window overflow'
                    y, x = divmod(pixel_count, r-l+1)
                    gram[t+y, l+x] = (high_byte << 8) | value
                    high_byte = None
                    pixel_count += 1
                    if window_count == 1 and pixel_count == 76800:
                        first_static = gram.copy()
            else:
                data.append(value)
                if command in (0x2A, 0x2B) and len(data) == 4:
                    bounds[command] = ((data[0] << 8) | data[1], (data[2] << 8) | data[3])
                elif command == 0x36:
                    assert len(data) == 1
                    mode = value
                elif command == 0x3A:
                    assert len(data) == 1
                    colmod = value
                else:
                    assert command in (0x2A, 0x2B), ('unexpected command data', command, data)
        elif fields[0] == 'TRANSFER':
            finish_window()
            transfer_times.append(float(fields[1]) / 1e6)
        elif fields[0] == 'FRAME':
            finish_window()
            time_ms = float(fields[1]) / 1e6
            frame_no, late, gaps, spectra, layers = map(int, fields[2:])
            assert late == 0 and spectra > 0
            assert frame_no == len(frames)+1
            image = Image.fromarray(rgb565(gram))
            image.save(ROOT / f'frame-{frame_no:02d}.png')
            snapshots.append(image)
            frames.append({'number': frame_no, 'boundary_ms': time_ms,
                           'transfer_done_ms': transfer_times[-1], 'late': late,
                           'analysis_gap_samples': gaps, 'spectrum_sequence': spectra,
                           'input_layer_mask_at_boundary': layers})
            # Accepted note and pitch events: verify actual received trace pixels.
            ys = [210] if frame_no <= 2 else ([200, 210] if frame_no <= 4 else ([200, 207] if frame_no <= 6 else [207]))
            actual_ys = np.where(gram[190:229, 15+frame_no] == 0xFDC8)[0] + 190
            assert list(actual_ys) == sorted(ys), (frame_no, actual_ys, ys)
    finish_window()
    assert len(frames) == 8 and len(transfer_times) == 8
    assert 'PASS visualizer 8 updates' in (ROOT / 'visualizer-simulation.log').read_text()
    intervals = np.diff([f['boundary_ms'] for f in frames])
    assert np.all((intervals >= 49.99) & (intervals <= 50.01)), intervals
    # The first transfer follows startup. Subsequent work must finish within the next 50ms period.
    durations = [frames[i]['transfer_done_ms'] - frames[i-1]['boundary_ms'] for i in range(1, 8)]
    assert max(durations) < 50
    allowed = np.zeros(gram.shape, dtype=bool)
    allowed[3:20, 212:308] = True
    allowed[49:81, 32:287:2] = True
    allowed[113:148, 40:280] = True
    allowed[190:229, 16:304] = True
    assert first_static is not None
    assert np.all(gram[~allowed] == first_static[~allowed]), 'static area changed'
    assert np.count_nonzero(gram[113:148, 40:280] != first_static[113:148, 40:280]) > 100, 'missing spectrum'
    snapshots[-1].resize((960, 720), Image.Resampling.NEAREST).save(ROOT / 'preview-3x.png')
    snapshots[0].save(ROOT / 'simulation.gif', save_all=True, append_images=snapshots[1:], duration=50, loop=0)
    return {'bytes': all_bytes, 'windows': window_count, 'frames': frames,
            'boundary_intervals_ms': intervals.tolist(), 'post_startup_transfer_work_ms': durations,
            'static_area_unchanged': True, 'accepted_note_pitch_trace_checked': True,
            'caution': 'Digital SPI receiver only. Frame boundary is telemetry; LCD writes are progressive, not atomic.'}


def main():
    ui_inputs = list((ROOT / 'rtl').glob('*')) + list(ROOT.glob('*1024.hex'))
    ui_inputs += [ROOT / 'test-dual.hex', ROOT / 'tb_visualizer.v']
    # Never attach changed RTL to an old capture merely by rerunning this checker.
    assert (ROOT / 'visualizer.vvp').stat().st_mtime_ns >= max(p.stat().st_mtime_ns for p in ui_inputs), 'recompile and rerun UI simulation'
    assert (ROOT / 'visualizer-spi.log').stat().st_mtime_ns >= (ROOT / 'visualizer.vvp').stat().st_mtime_ns
    for stem, inputs in [('fft', [ROOT/'rtl/mv_fft1024.v', ROOT/'tb_fft.v']),
                         ('wave', [ROOT/'rtl/mv_wave_capture.v', ROOT/'tb_wave.v'])]:
        assert (ROOT/f'{stem}.vvp').stat().st_mtime_ns >= max(p.stat().st_mtime_ns for p in inputs)
        assert 'PASS' in (ROOT/f'{stem}-simulation.log').read_text()
    report = {'fft': verify_fft(), 'panel': verify_panel()}
    # Two malformed captures must be rejected by the independent receiver.
    lines = (ROOT / 'visualizer-spi.log').read_text().splitlines()
    command_index = next(i for i, s in enumerate(lines) if s.startswith('BYTE ') and s.endswith(' 0 2c'))
    address_index = next(i for i, s in enumerate(lines) if s.startswith('BYTE ') and s.endswith(' 0 2a'))
    missing = lines[:command_index+1] + lines[command_index+2:]
    outside = lines.copy()
    outside[address_index+4] = outside[address_index+4].rsplit(' ', 1)[0] + ' ff'
    report['negative_checks'] = []
    with tempfile.TemporaryDirectory() as temp:
        for name, damaged in [('missing_pixel_byte', missing), ('window_x511', outside)]:
            path = Path(temp) / f'{name}.log'
            path.write_text('\n'.join(damaged)+'\n')
            try:
                verify_panel(path)
            except AssertionError:
                report['negative_checks'].append({'case': name, 'rejected': True})
            else:
                raise AssertionError(f'Corrupt capture unexpectedly accepted: {name}')
    files = list((ROOT / 'rtl').glob('*')) + list(ROOT.glob('*1024.hex'))
    files += [ROOT / n for n in ('tb_fft.v', 'tb_wave.v', 'tb_visualizer.v', 'verify.py')]
    report['inputs_sha256'] = {str(p.relative_to(ROOT)): hashlib.sha256(p.read_bytes()).hexdigest() for p in files}
    report['captures_sha256'] = {name: hashlib.sha256((ROOT/name).read_bytes()).hexdigest()
        for name in ('visualizer-spi.log', 'visualizer-simulation.log', 'fft-bins.txt',
                     'fft-simulation.log', 'wave-simulation.log')}
    (ROOT / 'verification.json').write_text(json.dumps(report, indent=2)+'\n')
    print(json.dumps({'status': 'PASS', 'fft_cases': len(report['fft']),
                      'spi_bytes': report['panel']['bytes'], 'frames': 8,
                      'max_transfer_work_ms': max(report['panel']['post_startup_transfer_work_ms'])}))


if __name__ == '__main__':
    main()
