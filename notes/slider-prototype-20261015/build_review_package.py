"""Generate review-only BOM and logical pin connectivity for a four-strip coupon.

This is NOT an EDA project, ERC/DRC result, PCB, Gerber or purchasing release.
Pin numbering follows the linked manufacturer datasheets; footprints still need
verification in the connected editor. No FPGA package pins are allocated here.
"""
import csv
import json
from pathlib import Path

ROOT = Path(__file__).resolve().parent
ROWS = []
BOM = []


def pin(ref, number, name, net, comment=''):
    ROWS.append([ref, number, name, net, comment])


def part(ref, qty, mpn, code, package, purpose, source):
    BOM.append([ref, qty, mpn, code, package, purpose, source, 'REVIEW_ONLY'])


def main():
    for bank, ref in enumerate(('U1', 'U2')):
        lane = 'AB'[bank]
        part(ref, 1, 'CD74HC4067M96', 'C496123', 'SOIC-24-300mil', '16:1 raw electrode selection',
             'https://www.ti.com/lit/ds/symlink/cd74hc4067.pdf')
        common = f'SENSE_{lane}'
        pin(ref, 1, 'COM', common)
        pin(ref, 24, 'VCC', '3V3')
        pin(ref, 12, 'GND', 'GND')
        pin(ref, 15, 'E', 'MUX_DISABLE')
        for bit, number in enumerate((10, 11, 14, 13)):
            pin(ref, number, f'S{bit}', f'ADDR{bit}')
        channels = [9, 8, 7, 6, 5, 4, 3, 2, 23, 22, 21, 20, 19, 18, 17, 16]
        for ch, number in enumerate(channels):
            if ch < 6:
                strip = bank * 2 + ch // 3
                enet = f'STRIP{strip}_E{ch % 3}'
                mnet = f'{enet}_MUX'
                pin(ref, number, f'I{ch}', mnet)
                resistor = f'R{21 + bank * 6 + ch}'
                pin(resistor, 1, '1', enet)
                pin(resistor, 2, '2', mnet)
                part(resistor, 1, '1k 1% 0603', '', '0603', 'electrode series resistor candidate', '')
                pin(f'E{strip}_{ch % 3}', 1, 'COPPER', enet, 'PCB electrode; geometry unvalidated')
            elif ch < 9:
                cnet = f'CAL_{lane}_{ch}'
                pin(ref, number, f'I{ch}', cnet)
                cref = f'C{16 + bank * 3 + ch - 6}'
                value = (10, 47, 100)[ch - 6]
                part(cref, 1, f'{value}pF C0G 0603', '', '0603', 'reference load, not a touch stimulus', '')
                pin(cref, 1, '1', cnet)
                pin(cref, 2, '2', 'GND')
            else:
                pin(ref, number, f'I{ch}', f'NC_{ref}_{number}', 'unpopulated analog test pad; still scan all 16 addresses')
        rref = f'R{bank + 1}'
        part(rref, 1, '47k 1% 0603', '', '0603', 'initial RC resistor; evaluate 100k/220k replacements', '')
        pin(rref, 1, '1', 'RC_DRIVE')
        pin(rref, 2, '2', common)
    part('U3', 1, 'SN74LVC14ADR', 'C133541', 'SOIC-14', 'Schmitt input edge conversion',
         'https://www.ti.com/lit/ds/symlink/sn74lvc14a.pdf')
    for n, name, net in ((14, 'VCC', '3V3'), (7, 'GND', 'GND'), (1, '1A', 'SENSE_A'),
                         (2, '1Y', 'SENSE_A_INV'), (3, '2A', 'SENSE_B'), (4, '2Y', 'SENSE_B_INV')):
        pin('U3', n, name, net)
    for n in (5, 9, 11, 13):
        pin('U3', n, 'UNUSED_INPUT', 'GND')
    for n in (6, 8, 10, 12):
        pin('U3', n, 'UNUSED_OUTPUT', f'NC_U3_{n}')
    for lane, ref in zip('AB', ('R3', 'R4')):
        part(ref, 1, '220R 0603', '', '0603', 'digital output series termination candidate', '')
        pin(ref, 1, '1', f'SENSE_{lane}_INV')
        pin(ref, 2, '2', f'FPGA_SENSE_{lane}')
    part('U4', 1, 'SN74LV595ADR', 'C205940', 'SOIC-16', 'latched scan-address and RC drive outputs',
         'https://www.ti.com/lit/ds/symlink/sn74lv595a.pdf')
    for n, name, net in ((16, 'VCC', '3V3'), (8, 'GND', 'GND'), (14, 'SER', 'BUS_MOSI'),
                         (11, 'SRCLK', 'BUS_SCK'), (12, 'RCLK', 'SCAN_LATCH'),
                         (13, 'OE_N', 'GND'), (10, 'SRCLR_N', '3V3'), (9, 'QH_PRIME', 'NC_U4_9')):
        pin('U4', n, name, net)
    for bit, number in enumerate((15, 1, 2, 3, 4, 5, 6, 7)):
        net = f'ADDR{bit}' if bit < 4 else ('MUX_DISABLE' if bit == 4 else ('RC_DRIVE' if bit == 5 else f'NC_U4_{number}'))
        pin('U4', number, f'Q{bit}', net)
    part('U5', 1, 'SN74LV165ADR', 'C273656', 'SOIC-16', 'read 4 presets + edit + encoder A/B/push',
         'https://www.ti.com/lit/ds/symlink/sn74lv165a.pdf')
    for n, name, net in ((16, 'VCC', '3V3'), (8, 'GND', 'GND'), (1, 'SH_LD_N', 'INPUT_LOAD_N'),
                         (2, 'CLK', 'BUS_SCK'), (15, 'CLK_INH', 'GND'), (10, 'SER', 'GND'),
                         (9, 'QH', 'INPUT_DATA'), (7, 'QH_N', 'NC_U5_7')):
        pin('U5', n, name, net)
    inputs = ('ENC_A', 'ENC_B', 'ENC_PUSH', 'PRESET_0', 'PRESET_1', 'PRESET_2', 'PRESET_3', 'EDIT')
    for i, (n, net) in enumerate(zip((11, 12, 13, 14, 3, 4, 5, 6), inputs)):
        pin('U5', n, chr(65 + i), net)
        ref = f'R{41+i}'
        part(ref, 1, '10k 0603', '', '0603', 'input pull-up; switches/encoder close to GND', '')
        pin(ref, 1, '1', '3V3')
        pin(ref, 2, '2', net)
    part('U6', 1, '24LC256-I/SN', 'C411625', 'SOIC-8', 'candidate 32KiB nonvolatile instrument storage',
         'https://www.microchip.com/content/dam/mchp/documents/MPD/ProductDocuments/DataSheets/24AA256-24LC256-24FC256-Data-Sheet-20001203W.pdf')
    for n, name, net in ((1, 'A0', 'GND'), (2, 'A1', 'GND'), (3, 'A2', 'GND'), (4, 'VSS', 'GND'),
                         (5, 'SDA', 'STORE_SDA'), (6, 'SCL', 'STORE_SCL'), (7, 'WP', 'GND'), (8, 'VCC', '3V3')):
        pin('U6', n, name, net)
    for i, net in enumerate(('STORE_SDA', 'STORE_SCL')):
        ref = f'R{51+i}'
        part(ref, 1, '4.7k 0603', '', '0603', 'I2C initial pull-up; verify bus capacitance', '')
        pin(ref, 1, '1', '3V3')
        pin(ref, 2, '2', net)
    for i in range(1, 7):
        part(f'C{i}', 1, '100nF X7R 0603', '', '0603', f'local bypass for U{i}', '')
        pin(f'C{i}', 1, '1', '3V3')
        pin(f'C{i}', 2, '2', 'GND')
    part('C7', 1, '4.7uF X7R 0805', '', '0805', 'local bulk candidate', '')
    pin('C7', 1, '1', '3V3')
    pin('C7', 2, '2', 'GND')
    signals = ['BUS_SCK', 'BUS_MOSI', 'SCAN_LATCH', 'INPUT_LOAD_N', 'INPUT_DATA',
               'FPGA_SENSE_A', 'FPGA_SENSE_B', 'STORE_SDA', 'STORE_SCL', 'LCD_CS_N', 'LCD_DC', 'LCD_RST_N']
    signals += [f'FPGA_SENSE_{x}' for x in 'CDEFGH']
    for number, net in enumerate(['3V3', 'GND'] + signals, 1):
        pin('J_FPGA', number, 'LOGICAL', net, 'candidate connector numbering ONLY; not FPGA package or board-header numbering')
    for name, header, rows in (
        ('bom-review.csv', ['Reference', 'Quantity', 'MPN_or_value', 'LCSC', 'Package', 'Purpose', 'Source', 'Status'], BOM),
        ('connections-review.csv', ['Reference', 'Pin', 'Name', 'Net', 'Comment'], ROWS),
    ):
        with (ROOT / name).open('w', encoding='utf-8-sig', newline='') as f:
            writer = csv.writer(f)
            writer.writerow(header)
            writer.writerows(rows)
    duplicates = len({(r[0], str(r[1])) for r in ROWS}) != len(ROWS)
    checks = {'status': 'logical list consistency only, not ERC or electrical qualification',
              'no_duplicate_component_pins': not duplicates, 'fpga_signal_count_candidate': len(signals),
              'prototype_lanes': 2, 'future_full_lanes': 8, 'physical_sliders_on_coupon': 4,
              'electrodes_per_slider_candidate': 3, 'physical_electrode_nodes': 12,
              'scan_addresses_per_frame': 16, 'board_dimensions_candidate_mm': [90, 100],
              'release_for_manufacture': False, 'missing': ['connected EDA project and ERC/DRC',
              'exact display model', 'exact encoder footprint', 'ESD selection and validation',
              'physical pin assignment', 'measured sensing data', 'domestic CNY quote']}
    (ROOT / 'review-status.json').write_text(json.dumps(checks, indent=2) + '\n', encoding='utf-8')
    print(json.dumps(checks))
    return 1 if duplicates else 0


if __name__ == '__main__':
    raise SystemExit(main())
