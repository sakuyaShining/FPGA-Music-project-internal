"""Independent ILI9341 command/GRAM subset model reading pin-decoded SPI bytes.

Not a complete analog/controller emulator. Supported test contract: portrait
MADCTL=0, RGB565, CASET/PASET/RAMWR, reset and minimum startup waits. Pixel
expectations are checked over the entire visible image, including unchanged
pixels after a partial write. The RTL's internal state is never inspected.
"""
import hashlib
import json
from pathlib import Path

ROOT = Path(__file__).resolve().parent


def expected_pattern():
    colors = (0xf800, 0x07e0, 0x001f, 0xffe0, 0xf81f, 0x07ff)
    pixels = [colors[x // 40] for y in range(320) for x in range(240)]
    pixels[0], pixels[239], pixels[319 * 240], pixels[-1] = 0xf800, 0x07e0, 0x001f, 0xffff
    return pixels


def parse_capture(path):
    gram = [None] * 76800
    expected = expected_pattern()
    command = None
    params = []
    window = [0, 239, 0, 319]
    cx = cy = 0
    hi = None
    reset_release = None
    reset_assert = None
    last_soft_reset = None
    sleep_out = None
    display_on = False
    rgb565 = False
    portrait = False
    frame_pixels = 0
    tag = None
    starts = {}
    frames = []
    timing = None
    invalid = False
    aborted = False
    total_bytes = 0
    for line in path.read_text(encoding='utf-8').splitlines():
        fields = line.split()
        kind = fields[0]
        when = float(fields[1])
        if kind == 'RESET':
            if tag == 0:
                aborted = True
            command, params, hi, tag = None, [], None, None
            reset_assert = when
            reset_release = last_soft_reset = sleep_out = None
            display_on = rgb565 = portrait = False
            gram = [None] * 76800
        elif kind == 'RELEASE':
            assert reset_assert is not None and when - reset_assert >= 10000
            reset_release = when
        elif kind == 'START':
            tag = int(fields[2]); frame_pixels = 0
            starts[tag] = when
        elif kind == 'BYTE':
            total_bytes += 1
            dc, value = int(fields[2]), int(fields[3], 16)
            assert reset_release is not None and when - reset_release >= 5e6, 'reset recovery wait'
            if last_soft_reset is not None:
                assert when - last_soft_reset >= 5e6, 'software reset recovery wait'
            if dc == 0:
                assert hi is None, 'new command splits a pixel'
                if command in (0x2a, 0x2b):
                    assert len(params) == 4, 'incomplete address command'
                command, params = value, []
                if value == 0x01:
                    last_soft_reset = when
                elif value == 0x11:
                    sleep_out = when
                elif value == 0x29:
                    assert sleep_out is not None and when - sleep_out >= 5e6, 'sleep-out wait'
                    display_on = True
                elif value == 0x2c:
                    assert display_on and rgb565 and portrait
                    cx, cy = window[0], window[2]
                else:
                    assert value in (0x3a, 0x36, 0x2a, 0x2b), f'unsupported command {value:02x}'
            elif command in (0x2a, 0x2b):
                params.append(value)
                assert len(params) <= 4
                if len(params) == 4:
                    a, b = params[0] * 256 + params[1], params[2] * 256 + params[3]
                    bound = 240 if command == 0x2a else 320
                    assert 0 <= a <= b < bound
                    offset = 0 if command == 0x2a else 2
                    window[offset:offset+2] = [a, b]
            elif command == 0x3a:
                assert value == 0x55
                rgb565 = True
            elif command == 0x36:
                assert value == 0
                portrait = True
            elif command == 0x2c:
                if hi is None:
                    hi = value
                else:
                    assert tag in (1, 2) and window[0] <= cx <= window[1] and window[2] <= cy <= window[3]
                    assert frame_pixels < (window[1]-window[0]+1) * (window[3]-window[2]+1), 'excess pixels'
                    gram[cy * 240 + cx] = hi * 256 + value
                    hi = None; frame_pixels += 1
                    if cx == window[1]:
                        cx = window[0]; cy += 1
                    else:
                        cx += 1
            else:
                raise AssertionError('unexpected parameter')
        elif kind == 'DONE':
            done_tag = int(fields[2])
            assert tag == done_tag and hi is None
            count = 76800 if tag == 1 else 143
            assert frame_pixels == count
            if tag == 2:
                assert window == [7, 19, 9, 19]
                for index in range(143):
                    x, y = 7 + index % 13, 9 + index // 13
                    expected[y * 240 + x] = 0x1234 if index % 2 == 0 else 0xabcd
            assert gram == expected, f'GRAM mismatch for frame {tag}'
            raw = b''.join(p.to_bytes(2, 'big') for p in gram)
            frames.append({'tag': tag, 'pixels_written': count, 'all_76800_pixels_match': True,
                           'transfer_ms': (when - starts[tag]) / 1e6,
                           'rgb565_sha256': hashlib.sha256(raw).hexdigest(), 'pixels': list(gram)})
            tag = None
        elif kind == 'INVALID_REJECTED':
            invalid = True
        elif kind == 'TIMING':
            timing = {'sck_period_ns': when, 'sck_high_ns': float(fields[2]),
                      'sck_low_ns': float(fields[3]), 'mosi_setup_ns': float(fields[4])}
            assert timing['sck_period_ns'] >= 100 and timing['sck_high_ns'] >= 40
            assert timing['sck_low_ns'] >= 40 and timing['mosi_setup_ns'] >= 30
    assert aborted and invalid and len(frames) == 2 and timing
    return {'status': 'PASS', 'scope': 'digital controller subset, not physical module or full visualization',
            'reset_during_byte_recovered': aborted, 'invalid_window_rejected': invalid,
            'decoded_bytes': total_bytes, 'pin_timing_minima': timing, 'frames': frames}


def save_png(pixels, path):
    from PIL import Image
    data = []
    for value in pixels:
        r, g, b = (value >> 11) & 31, (value >> 5) & 63, value & 31
        data.append((r * 255 // 31, g * 255 // 63, b * 255 // 31))
    image = Image.new('RGB', (240, 320))
    image.putdata(data)
    image.save(path)


def main():
    path = ROOT / 'spi-bytes.log'
    result = parse_capture(path)
    for frame in result['frames']:
        image_path = ROOT / f"frame-{frame['tag']}.png"
        save_png(frame.pop('pixels'), image_path)
        frame['image'] = image_path.name
    result['capture_sha256'] = hashlib.sha256(path.read_bytes()).hexdigest()
    (ROOT / 'evidence/capture-check.json').write_text(json.dumps(result, indent=2) + '\n', encoding='utf-8')
    print(json.dumps(result, indent=2))


if __name__ == '__main__':
    main()
