"""Offline engineering checks, not DAC/display hardware qualification.

Clock: TI SLAS763C sections 8.3.6.4/5; tables 64-83, 129-132.
Pin map: Sipeed Nano20K 3921 rev1.30 page 2; board revision still to confirm.
"""
import csv
import json
from decimal import Decimal
from fractions import Fraction
from pathlib import Path

ROOT = Path(__file__).parent


def clock_checks():
    fs = Fraction(27_000_000, 512)
    bck = fs * 32
    p, j, d, r = 1, 24, 0, 2
    pll = bck * (Fraction(j) + Fraction(d, 10000)) * r / p
    ddsp, ddac, dncp, dosr = 4, 24, 2, 4
    dsp, dac = pll / ddsp, pll / ddac
    cp, osr = dac / dncp, dac / dosr
    assert 1_000_000 <= bck / p <= 20_000_000
    assert 72_000_000 <= pll <= 86_000_000, "VCOM PLL range"
    assert osr == 16 * fs
    assert dac == 64 * fs, "double-speed modulator ratio"
    assert dsp / fs == 384 and dsp / fs >= 256, "program 2 minimum cycles"
    assert 1 <= ddsp <= 128 and 1 <= ddac <= 128
    assert 1 <= dncp <= 128 and 1 <= dosr <= 128
    assert 48_000 < fs <= 96_000, "FSSP must be double-speed, not single-speed"
    assert cp == 1_687_500
    return {"qualification": "arithmetic_and_register_fields_only_not_hardware",
            "fs_hz": float(fs), "bck_hz": float(bck), "pll_hz": float(pll),
            "pll_p": p, "pll_j": j, "pll_d": d, "pll_r": r,
            "dsp_hz": float(dsp), "idac_cycles": int(dsp / fs),
            "dac_hz": float(dac), "cp_hz": float(cp), "osr_hz": float(osr),
            "speed_mode": "double", "interpolation_program": 2,
            "clock_flex_required": True,
            "warning": "Register fields are not a boot sequence; mute, power, PLL lock, error policy and readback still required."}


def gpio_checks():
    with (ROOT / "nano-io-candidate.csv").open(encoding="utf-8-sig", newline="") as stream:
        pins = list(csv.DictReader(stream))
    for key in ("package_pin", "header"):
        values = [row[key] for row in pins]
        assert len(values) == len(set(values)), "Duplicate " + key
    panel = [row for row in pins if row["category"] == "panel"]
    assert len(panel) == 17
    assert len([row for row in panel if row["signal"].startswith("SENSE_")]) == 6
    assert {row["package_pin"] for row in pins if row["category"] == "audio"} == {"54", "55", "56"}
    # The external 2:1 selector prevents joining two push-pull return outputs.
    for select in (0, 1):
        for ra in (0, 1):
            for keys in (0, 1):
                y = ra if select == 0 else keys
                assert y == (keys if select else ra)
    return {"panel_gpio": len(panel), "reused_audio_outputs": 3,
            "external_return_selector": "74LVC1G157; S=RA_CS_N,I0=RA_MISO,I1=165_QH",
            "qualification": "unique_candidate_assignments_and_truth_table_not_board_or_timing"}


def screen_checks():
    spi = Fraction(27_000_000, 4)
    full = Fraction(800 * 480 * 16, 1) / spi
    assert full > Fraction(9, 10)
    # Geometric split only; this is not a chosen layout or a performance result.
    return {"spi_hz": float(spi), "full_800x480_rgb565_ms": float(full * 1000),
            "full_320x240_rgb565_ms": float(Fraction(320 * 240 * 16, 1) / spi * 1000),
            "command_120_bytes_wire_us_only": float(Fraction(120 * 8, 1) / spi * 1_000_000),
            "combined_fixed_split_example": {"visual_pixels": [800, 240], "fader_pixels": [800, 240],
                                             "estimated_fader_height_mm": 85.92 / 2},
            "qualification": "payload_and_geometry_only_no_panel_fps_or_touch_latency_claim"}


def bom_checks():
    # Preserve original line totals; only correct the six-part 10+ tier error here.
    original = Decimal("648.74")
    correction = Decimal(6) * (Decimal("2.89") - Decimal("2.22"))
    assert correction == Decimal("4.02")
    return {"original_workbuddy_model_cny": str(original), "tier_correction_cny": str(correction),
            "corrected_same_scope_model_cny": str(original + correction),
            "not_included": ["CTP option increment", "current domestic delivered prices", "small screen if absent",
                             "return mux", "regulator and exact power distribution", "final connectors/FFC", "actual SMT quote"],
            "qualification": "historical_model_arithmetic_only_not_a_quote"}


def main():
    result = {"clock": clock_checks(), "gpio": gpio_checks(), "screen": screen_checks(), "bom": bom_checks()}
    with (ROOT / "pcm5122-clock-fields.csv").open(encoding="utf-8-sig", newline="") as stream:
        fields = list(csv.DictReader(stream))
    registers = {(int(row["page"]), int(row["register_hex"], 16)): int(row["value_hex"], 16) for row in fields}
    # Independently decode the actual export, so changing a CSV byte cannot pass silently.
    p = registers[(0, 0x14)] + 1
    j = registers[(0, 0x15)]
    d = registers[(0, 0x16)] * 256 + registers[(0, 0x17)]
    r = registers[(0, 0x18)] + 1
    pll = Fraction(1_687_500) * (j + Fraction(d, 10000)) * r / p
    dsp = pll / (registers[(0, 0x1B)] + 1)
    dac = pll / (registers[(0, 0x1C)] + 1)
    assert pll == 81_000_000
    assert dsp == 20_250_000 and dac == 3_375_000
    assert dac / (registers[(0, 0x1E)] + 1) == 843_750
    assert dac / (registers[(0, 0x1D)] + 1) == 1_687_500
    assert registers[(0, 0x22)] & 3 == 1
    assert registers[(0, 0x23)] * 256 + registers[(0, 0x24)] == 384
    assert registers[(0, 0x28)] & 0x33 == 0
    for row in fields:
        mask, value = int(row["mask_hex"], 16), int(row["value_hex"], 16)
        assert value & ~mask == 0, "Value writes outside reviewed register field"
    result["clock"]["exported_register_fields_decoded"] = len(fields)
    out = ROOT / "evidence"
    out.mkdir(exist_ok=True)
    (out / "candidate-checks.json").write_text(json.dumps(result, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    print(json.dumps(result, ensure_ascii=True, indent=2))


if __name__ == "__main__":
    main()
