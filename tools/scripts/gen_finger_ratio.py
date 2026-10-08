"""Generate the prototype continuous-position to Q16 frequency-ratio table.

One calibrated position unit = 1200/256 cents. Range is +/- one octave.
This calibration is an interface convention, not an electrode dimension.
"""
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
out = ROOT / 'src/gowin/tdm_synth/finger_ratio.hex'
out.write_text(''.join(f'{round((2 ** (x / 256) - 1) * 65536) & 0x3ffff:05x}\n'
                       for x in range(-256, 257)), encoding='ascii')
print(out)
