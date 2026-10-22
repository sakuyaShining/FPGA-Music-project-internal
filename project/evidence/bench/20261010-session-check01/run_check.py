"""Current powered-board check. No download/reset, not power-on defaults."""
import json
import sys
from datetime import datetime, timezone
from pathlib import Path
import numpy as np

ROOT = Path(__file__).resolve().parents[4]
sys.path.insert(0, str(ROOT / 'tools/scripts'))
import test_board_hardware as hw

OUT = Path(__file__).resolve().parent
hw.OUT = OUT
if (OUT / 'report.json').exists():
    raise SystemExit('Refusing to overwrite previous check')
report = {
    'started_at': datetime.now(timezone.utc).isoformat(),
    'port': 'COM6', 'status': 'RUNNING', 'cases': [],
    'source_manifest': 'project/versions/integration-20261010-04.json',
    'build_record': 'project/versions/board-build-20261010-04.json',
    'identity_boundary': 'Readback is configuration tag, not a unique bitstream hash.04 attribution relies on verified stored build/download and user continuous-power statement.',
    'scope': 'Powered-board synthetic UART inputs and internal digital samples; no reset, new download, startup-default claim, physical touch, DAC or latency acceptance.',
}

def save():
    (OUT / 'report.json').write_text(json.dumps(report, indent=2), encoding='utf-8')

board = None
saved = {}
try:
    board = hw.Board('COM6')
    ids = {hex(a): board.read(a) for a in [0x7f,0xa4,0xa5,0xa9]}
    assert list(ids.values()) == [0x11,0xd3,2,32], ids
    report['identity'] = ids
    report['before'] = board.snapshot()
    saved = {a: board.read(a) for a in [0,0x37,0x40,0x6e]}
    # The test starts from a cleared state, not a fabricated power-on state.
    board.clear_events(32)
    board.write(0,8); board.write(0x37,0); board.write(0x40,1)
    board.write(0x6e,0)
    save()

    def case(name, test):
        try:
            detail = test()
            row = {'name': name, 'status': 'PASS', 'detail': detail}
        except Exception as error:
            row = {'name': name, 'status': 'FAIL', 'error': str(error)}
        finally:
            try:
                board.clear_events(32)
            except Exception as error:
                row = {'name': name, 'status': 'FAIL', 'cleanup_error': str(error)}
        report['cases'].append(row); save()
        print(name, row['status'], row.get('error', ''), flush=True)

    def silence():
        samples = board.capture('cleared_silence',2048)
        assert np.all(samples == 0), (int(samples.min()),int(samples.max()))
        return {'samples':2048,'all_zero':True,'condition':'after deliberate event clearing, not startup'}
    case('cleared_internal_silence',silence)

    def lifecycle():
        before = board.snapshot()
        for note in [36,60,69,96,127]:
            board.note(note,True,3)
            assert board.snapshot()['active'].bit_count() == 1
            board.note(note,False)
            assert board.snapshot()['active'] == 0
        after = board.snapshot()
        assert (after['ack']-before['ack']) & 65535 == 10
        board.note(127,True,3); board.note(60,True,3)
        assert board.snapshot()['active'].bit_count() == 2
        return {'notes':[36,60,69,96,127],'on_off_ack':10,'midi127_independent_of60':True}
    case('note_lifecycle_and127_boundary',lifecycle)

    def polyphony():
        for note in range(40,72): board.note(note,True,3)
        assert board.snapshot()['active'] == 0xffffffff
        board.note(84,True,3)
        assert board.snapshot()['active'] == 0xffffffff
        board.clear_events(32)
        assert board.snapshot()['active'] == 0
        return {'voices':32,'steal':True,'released_all':True}
    case('full32_allocation_and_release',polyphony)

    def pitch():
        board.note(69,True,12)
        base = board.capture('a4_base',2048)
        f0 = hw.peak(base)
        assert np.max(np.abs(base)) > 50
        assert abs(f0-440) < 12, f0
        group = board.snapshot()['last_group']
        board.finger(0,group,0,0)
        before = board.snapshot()
        board.finger(0,group,16,1)
        moved = board.capture('a4_plus75cents',2048)
        f1 = hw.peak(moved)
        assert abs(f1-440*2**(16/256)) < 12, f1
        assert board.snapshot()['on'] == before['on']
        return {'base_hz':f0,'moved_hz':f1,'move_note_on':0,'sample_stream_bytes':6145}
    case('real_fpga_internal_pitch_expression',pitch)

    def two_fingers():
        board.note(60,True,12); g0 = board.snapshot()['last_group']
        board.note(67,True,12); g1 = board.snapshot()['last_group']
        assert g0 != g1
        board.finger(0,g0,0,0); board.finger(1,g1,0,0)
        before = board.snapshot()
        board.finger(0,g0,16,1); board.finger(1,g1,-16,1)
        values = board.capture('two_fingers_opposite',2048)
        spectrum = np.abs(np.fft.rfft((values-values.mean())*np.hanning(len(values)),n=16384))
        axis = np.fft.rfftfreq(16384,1/hw.FS)
        expected = [440*2**((60-69)/12+16/256),440*2**((67-69)/12-16/256)]
        peaks = []
        for freq in expected:
            indices = np.flatnonzero((axis>freq-15)&(axis<freq+15))
            k = indices[np.argmax(spectrum[indices])]
            assert spectrum[k] > spectrum.max()*.1
            assert abs(axis[k]-freq) < 12
            peaks.append(float(axis[k]))
        assert board.snapshot()['on'] == before['on']
        return {'groups':[g0,g1],'expected_hz':expected,'observed_hz':peaks,'move_note_on':0}
    case('two_synthetic_contacts_independent_pitch',two_fingers)
except Exception as error:
    report['fatal_error'] = str(error)
    print('FATAL',str(error),flush=True)
finally:
    if board:
        try:
            board.clear_events(32)
            for address,value in saved.items(): board.write(address,value)
            report['after'] = board.snapshot()
            assert report['after']['active'] == 0
        except Exception as error:
            report['cleanup_error'] = str(error)
        finally:
            board.port.close()
    report['passed'] = sum(c['status']=='PASS' for c in report['cases'])
    report['status'] = 'PASS' if (len(report['cases'])==5 and report['passed']==5 and not any(k in report for k in ['fatal_error','cleanup_error'])) else 'FAIL'
    report['finished_at'] = datetime.now(timezone.utc).isoformat()
    save()
    print('RESULT session_check='+report['status'],flush=True)
sys.exit(0 if report['status']=='PASS' else 1)
