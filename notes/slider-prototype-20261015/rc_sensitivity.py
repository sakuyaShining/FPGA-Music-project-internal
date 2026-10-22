"""Illustrative lumped-RC sensitivity, NOT SPICE, measured data or qualification.

Leakage cases are sensitivity stresses. TI's limits have different VCC/temperature
conditions; their arithmetic sum is not a guaranteed 3.3V total-front-end limit.
Mux channel leakage aggregation, charge injection and coupled electrodes are not
fully modelled. Thresholds below are explicit assumptions, not a 3.3V guarantee.
"""
import json
import math
from pathlib import Path

ROOT = Path(__file__).resolve().parent


def main():
    rows = []
    vcc, vt_high, vt_low = 3.3, 2.0, 0.6
    for resistance in (10000, 22000, 47000, 100000, 220000):
        for leak_ua in (0, 1.8, 13, 28):
            leakage = leak_ua * 1e-6
            charge_asymptote = vcc - resistance * leakage
            discharge_asymptote = resistance * leakage
            charge_possible = charge_asymptote > vt_high
            discharge_possible = discharge_asymptote < vt_low
            def charge_time(cap_pf):
                if not charge_possible:
                    return None
                return -resistance * cap_pf * 1e-12 * math.log(1 - vt_high / charge_asymptote)
            t0, t1 = charge_time(100), charge_time(105)
            rows.append({'resistor_ohms': resistance, 'leakage_stress_ua': leak_ua,
                         'charge_asymptote_v': charge_asymptote,
                         'discharge_asymptote_v': discharge_asymptote,
                         'crosses_assumed_high': charge_possible,
                         'crosses_assumed_low': discharge_possible,
                         'charge_100pf_us': None if t0 is None else t0 * 1e6,
                         'delta_5pf_ticks_27mhz': None if t0 is None else (t1 - t0) * 27e6})
    output = {'kind': 'illustrative lumped-RC arithmetic, not hardware acceptance',
              'assumptions': {'vcc_v': vcc, 'vt_high_v': vt_high, 'vt_low_v': vt_low,
                              'baseline_cap_pf': 100, 'touch_delta_pf': 5, 'clock_hz': 27000000},
              'stress_sources': {
                  'LVC14A_input': 'datasheet II at 3.6V: 1uA/5uA/20uA for listed temperature columns',
                  '4067_off': 'datasheet at 6V: 0.8uA at 25C and 8uA over listed ranges',
                  'caution': 'sums 1.8/13/28uA are illustrative; not guaranteed combined 3.3V bounds'},
              'rows': rows, 'manufacturing_release': False}
    (ROOT / 'rc-sensitivity.json').write_text(json.dumps(output, indent=2) + '\n', encoding='utf-8')
    print(json.dumps({'cases': len(rows), 'output': str(ROOT / 'rc-sensitivity.json'),
                      'conclusion': 'larger R increases count sensitivity but leakage can prevent threshold crossing'}))


if __name__ == '__main__':
    main()
