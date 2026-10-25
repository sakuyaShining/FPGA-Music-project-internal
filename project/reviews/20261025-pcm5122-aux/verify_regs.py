"""独立校验 pcm5122_init.v 的 ROM：按 SLAS763C 语义反算时钟树。

用法（任意目录均可）：
    python project/reviews/20261025-pcm5122-aux/verify_regs.py
"""
import re
from pathlib import Path

# 本文件在 project/reviews/<review>/ 下，向上三级即 authoritative-20261024
ROOT = Path(__file__).resolve().parents[3]
SRC = ROOT / 'fpga/current/engine/src/pcm5122_init.v'
src = SRC.read_text(encoding='utf-8')
print('源文件：%s' % SRC)
pairs = re.findall(r"5'd(\d+):\s*rom_entry = \{8'h([0-9A-Fa-f]{2}), 8'h([0-9A-Fa-f]{2})\};", src)
rom = {int(i): (int(r, 16), int(v, 16)) for i, r, v in pairs}
assert len(rom) == 17, rom

print('ROM（%d 条）' % len(rom))
for i in sorted(rom):
    print('  idx %-2d  reg 0x%02X = 0x%02X' % (i, rom[i][0], rom[i][1]))

reg = {r: v for r, v in rom.values()}

P   = (reg[0x14] & 0x0F) + 1
J   = reg[0x15] & 0x3F
D   = ((reg[0x16] & 0x3F) << 8) | reg[0x17]
R   = (reg[0x18] & 0x0F) + 1
K   = J + D / 16384.0
DSP   = (reg[0x1B] & 0x7F) + 1
DACCK = (reg[0x1C] & 0x7F) + 1
NCP   = (reg[0x1D] & 0x7F) + 1
DOSR  = (reg[0x1E] & 0x7F) + 1
SREF  = (reg[0x0D] >> 4) & 0x07
R37   = reg[0x25]
AFMT  = (reg[0x28] >> 4) & 0x03
ALEN  = reg[0x28] & 0x03

print('\n解码')
print('  P=%d  J=%d  D=%d  R=%d  -> K=J.D=%.4f  M=K*R=%.4f' % (P, J, D, R, K, K * R))
print('  DSP /%d   DAC /%d   NCP /%d   OSR /%d' % (DSP, DACCK, NCP, DOSR))
print('  SREF={:03b} ({})'.format(SREF, {0: 'SCK', 1: 'BCK'}.get(SREF, '?')))
print('  Reg37=0x%02X  DCAS(b1)=%d  IDCH(b3)=%d  IDSK(b4)=%d'
      % (R37, (R37 >> 1) & 1, (R37 >> 3) & 1, (R37 >> 4) & 1))
print('  AFMT={:02b} ({})  ALEN={:02b} ({})'.format(
    AFMT, 'I2S' if AFMT == 0 else '?', ALEN,
    {0: '16bit', 1: '20bit', 2: '24bit', 3: '32bit'}[ALEN]))

BCK = 27_000_000 / 18
fs  = BCK / 32
print('\n本板时钟（audio_clk_en.v: DIV_BCK=18, BCK_PER_LRCK=32）')
print('  BCK = %.0f Hz   fs = %.3f Hz   BCK/fs = %.0f' % (BCK, fs, BCK / fs))

PLLCK = BCK * R * K / P
print('\nPLLCK = BCK x R x J.D / P = %.3f MHz' % (PLLCK / 1e6))
for name, div in (('DSP', DSP), ('DAC/MOD', DACCK), ('NCP', NCP), ('OSR', DOSR)):
    f = PLLCK / div
    print('  %-8s /%-3d = %9.4f MHz = %8.1f fs' % (name, div, f / 1e6, f / fs))

ref = dict(P=1, J=32, R=2, DSP=2, DACCK=16, NCP=4, DOSR=8, PLL_fS=2048)
print('\n对照 Table 131 (fS=48k, RSCK=32, %ERROR=0)')
ok = True
for k, v in ref.items():
    got = {'P': P, 'J': J, 'R': R, 'DSP': DSP, 'DACCK': DACCK, 'NCP': NCP,
           'DOSR': DOSR, 'PLL_fS': PLLCK / fs}[k]
    same = abs(got - v) < 1e-6
    ok &= same
    print('  %-7s 手册=%-8s 本设计=%-10.4f %s' % (k, v, got, 'OK' if same else 'DIFF'))
print('\n结论：%s' % ('全部一致 —— 本设计是手册推荐行的等比缩放' if ok else '有差异，需复核'))

print('\n关键位检查')
for cond, msg in ((SREF == 1, 'SREF=BCK（不是接地的 SCK）'),
                  ((R37 >> 1) & 1 == 1, 'DCAS=1 关自动配置（否则分频寄存器被忽略）'),
                  ((R37 >> 3) & 1 == 1, 'IDCH=1 忽略 SCK 停振（SCK 接地不会报错）'),
                  ((R37 >> 4) & 1 == 1, 'IDSK=1 忽略 SCK 比值校验'),
                  (ALEN == 0, 'ALEN=16bit（对齐 32 BCK/帧的现帧）')):
    print('  [%s] %s' % ('PASS' if cond else 'FAIL', msg))
