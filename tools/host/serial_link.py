# -*- coding: utf-8 -*-
"""
serial_link.py —— 上位机通信层（GUI 只认这一层，不直接碰 pyserial）

【为什么要有"模拟设备"后端】
  板子还没到手时，GUI 的每一处逻辑（写寄存器、A3 回读、电极遥测柱、判定颜色）
  都要能跑起来自测 ✓。所以这里给两种后端：
    · SerialLink —— 真串口（需要 pyserial；板上用）
    · SimLink    —— 进程内模拟 FPGA 的寄存器堆 + A3 回读应答（离线自测、现场兜底演示用）
  GUI 顶部会**明确显示当前是"真实串口"还是"模拟设备"** ✗ 绝不让人误以为在跟板子说话。

【防分叉（项目纪律）】
  地址表一律从 `dsp_host.py` 的 REG / REG_V2 取 ✓，本文件**不另抄一份** ✗。
  帧的构造也复用 `dsp_host.Frames` ✓ —— 这样 GUI 发出的字节与命令行/仿真是同一套 ✓。

【A3 回读协议（19 号 修正案 A3，冻结）】
  主机写 [0x0F][src] ⇒ FPGA 从 tx 回 [src][value] 两字节。
"""

import os
import sys
import time

_HERE = os.path.dirname(os.path.abspath(__file__))


def frozen():
    """是否跑在 PyInstaller 打出来的 exe 里"""
    return bool(getattr(sys, "frozen", False))


def res_dir():
    """资源（数据文件）目录：源码运行=本目录；onefile 运行=_MEIPASS"""
    if frozen():
        return getattr(sys, "_MEIPASS", os.path.dirname(sys.executable))
    return _HERE


def exe_dir():
    return os.path.dirname(sys.executable) if frozen() else _HERE


def find_file(name, extra_dirs=()):
    """在若干候选目录里找文件（源码运行与打包运行都能找到 ✓）"""
    cands = [res_dir(), exe_dir(), os.getcwd(),
             os.path.normpath(os.path.join(_HERE, "..", ".."))]
    cands += list(extra_dirs)
    for d in cands:
        if d and os.path.isfile(os.path.join(d, name)):
            return os.path.join(d, name)
    return None


def ensure_import_paths():
    """让 `import dsp_host` 在源码运行与 onefile 运行下都成功 ✓
    源码：tools/scripts/ ；打包：dsp_host.py 作为 data 打进 _MEIPASS ✓"""
    cands = [_HERE,
             os.path.normpath(os.path.join(_HERE, "..", "scripts")),
             res_dir(), os.path.join(res_dir(), "scripts"), exe_dir()]
    for d in cands:
        if d and os.path.isdir(d) and d not in sys.path:
            sys.path.insert(0, d)


ensure_import_paths()
import dsp_host as dh                      # noqa: E402  （REG / REG_V2 / Frames / RD_REQ）

RD_REQ = dh.REG["RD_REQ"]                  # 0x0F
PROTO_VER = dh.REG["PROTO_VER"]            # 0x7F

# 遥测寄存器（第 7 轮加的，见挂账清单 ⑤）
TEL = {
    "PAD_BASE_LO": dh.REG["PAD_BASE_LO"],
    "PAD_BASE_HI": dh.REG["PAD_BASE_HI"],
    "PAD_SEL": dh.REG["PAD_SEL"],
    "PAD_RAW_LO": dh.REG["PAD_RAW_LO"],
    "PAD_RAW_HI": dh.REG["PAD_RAW_HI"],
    "PAD_ST_LO": dh.REG["PAD_ST_LO"],
    "PAD_ST_HI": dh.REG["PAD_ST_HI"],
}

# 名字反查（界面显示用）
NAME_OF = {}
for _n, _a in list(dh.REG.items()) + list(getattr(dh, "REG_V2", {}).items()):
    NAME_OF.setdefault(_a, _n)


def addr_name(a):
    return NAME_OF.get(a, "--")


class LinkBase(object):
    """通信后端接口：GUI 只调这四个方法 ✓"""

    kind = "?"
    detail = ""

    def open(self):
        raise NotImplementedError

    def close(self):
        raise NotImplementedError

    def send(self, frames):
        """发送一串帧（dsp_host.Frames），返回实际写出的字节数"""
        raise NotImplementedError

    def read_reg(self, addr, timeout=0.5):
        """A3 回读：写 [0x0F][addr]，取回该寄存器值；失败返回 None"""
        raise NotImplementedError


# =============================================================================
#  真串口
# =============================================================================
class SerialLink(LinkBase):
    def __init__(self, port, baud=115200):
        self.port = port
        self.baud = baud
        self.ser = None
        self._sent = 0

    def open(self):
        try:
            import serial                       # 延迟导入：没装 pyserial 也能用 SimLink
        except ImportError:
            # 打包成 exe 后**不能再**用系统里的 pyserial ✗ ⇒ 必须在打包时已安装 ✓
            # （本机 pip 因系统代理不可用而装不上，所以 exe 可能只有"模拟设备"能力 ✗）
            raise RuntimeError(
                "本程序包里没有 pyserial ⇒ 无法使用真实串口 ✗\n\n"
                "· 想连板子：先在【有网/无代理】的终端执行\n"
                "      python -m pip install pyserial\n"
                "  然后重新打包：\n"
                "      python tools/host/build_exe.py\n"
                "· 现在可以先用「模拟设备」体验界面 ✓")
        self.ser = serial.Serial(self.port, self.baud, timeout=0.5)
        self.kind = "真实串口"
        self.detail = "%s @ %d 8N1" % (self.port, self.baud)
        return True

    def close(self):
        if self.ser is not None:
            try:
                self.ser.close()
            finally:
                self.ser = None

    def send(self, frames):
        if self.ser is None:
            return 0
        buf = bytearray()
        for a, d, _note in frames.items:
            buf.append(a & 0xFF)
            buf.append(d & 0xFF)
        n = self.ser.write(bytes(buf))
        self.ser.flush()
        self._sent += n
        return n

    def read_reg(self, addr, timeout=0.5):
        if self.ser is None:
            return None
        try:
            self.ser.reset_input_buffer()
            self.ser.write(bytes([RD_REQ, addr & 0xFF]))
            self.ser.flush()
            old = self.ser.timeout
            self.ser.timeout = timeout
            r = self.ser.read(2)
            self.ser.timeout = old
            self._sent += 2
        except Exception:
            return None
        if len(r) < 2:
            return None
        return r[1]                        # 第 1 字节是回显地址，第 2 字节才是值


# =============================================================================
#  模拟设备（离线自测 / 现场兜底）
# =============================================================================
class SimLink(LinkBase):
    """进程内模拟一台"理想 FPGA"：

      · 寄存器堆：初值尽量取 RTL 的引导默认值（从 regmap 基线 CSV 读 ✓，
        读不到就全 0 —— 界面上会标明是模拟值 ✗）
      · A3 回读：按冻结协议应答 ✓
      · 电极遥测：合成 base/raw（可被"模拟触摸"改变），让遥测柱与判定逻辑可演示 ✓
    """

    def __init__(self, baseline_csv=None):
        self.regs = {}
        self._sent = 0
        self.kind = "模拟设备"
        self.detail = "进程内模拟（无硬件 ✓ 用于离线自测）"
        self.touch = False                 # 界面上的"模拟触摸"开关
        self.sel = 0                       # PAD_SEL
        self._base = {}
        self._load_defaults(baseline_csv)

    # ---- 初值：优先取 RTL 抽取的基线 ✓（打包后靠 --add-data 带进来，find_file 找得到 ✓）----
    def _load_defaults(self, path):
        docs = os.path.normpath(os.path.join(_HERE, "..", "..", "docs", "02-技术方案"))
        cands = ([path] if path else []) + [find_file("regmap_baseline.csv", extra_dirs=[docs])]
        for p in cands:
            if not p or not os.path.isfile(p):
                continue
            try:
                import csv
                with open(p, encoding="utf-8") as fh:
                    for row in csv.DictReader(fh):
                        a = str(row.get("addr", "")).strip()
                        if not a:
                            continue
                        ai = int(a, 16) if a.lower().startswith("0x") else int(a)
                        # regmap_baseline.csv 的列名实测是 addr,width,rd,wr_host,wr_boot ✓
                        #   （引导默认值在 wr_boot ✓；"-" = 无默认值）
                        df = ""
                        for col in ("wr_boot", "default", "boot", "value"):
                            v = str(row.get(col, "") or "").strip()
                            if v and v != "-":
                                df = v
                                break
                        if df:
                            try:
                                self.regs[ai] = int(df, 16) if df.lower().startswith("0x") else int(df, 16)
                            except ValueError:
                                pass
                self.detail = "进程内模拟（初值取自 %s ✓）" % os.path.basename(p)
                return
            except Exception:
                continue
        self.detail = "进程内模拟（未读到基线，初值全 0 ✗）"

    def open(self):
        return True

    def close(self):
        pass

    def send(self, frames):
        n = 0
        for a, d, _note in frames.items:
            self.regs[a & 0xFF] = d & 0xFF
            n += 2
            if (a & 0xFF) == TEL["PAD_SEL"]:
                self.sel = (d & 0x0F)
        self._sent += n
        self._refresh_telemetry()
        return n

    def read_reg(self, addr, timeout=0.5):
        self._sent += 2                    # 回读也要发 2 字节（与真实链路一致 ✓）
        if (addr & 0xFF) == RD_REQ:
            return None
        self._refresh_telemetry()
        return self.regs.get(addr & 0xFF, 0)

    # ---- 合成遥测：让"量程判定"这套逻辑在无板时也能演示 ✓ ----
    def _refresh_telemetry(self):
        ch = self.sel & 0x0F
        if ch not in self._base:
            # 每根电极给一个略有差异的基线（模拟真实电极电容不一致 ✓）
            self._base[ch] = 24 + (ch * 7) % 40
        b = self._base[ch]
        r = b + (58 if self.touch else 0)   # 触摸 ⇒ 放电变慢 ⇒ 计数变大 ✓
        self.regs[TEL["PAD_BASE_LO"]] = b & 0xFF
        self.regs[TEL["PAD_BASE_HI"]] = (b >> 8) & 0x0F
        self.regs[TEL["PAD_RAW_LO"]] = r & 0xFF
        self.regs[TEL["PAD_RAW_HI"]] = (r >> 8) & 0x0F
        st = 0
        if self.touch:
            st = 1 << ch
        self.regs[TEL["PAD_ST_LO"]] = st & 0xFF
        self.regs[TEL["PAD_ST_HI"]] = (st >> 8) & 0xFF

    def set_touch(self, on):
        self.touch = bool(on)
        self._refresh_telemetry()


# =============================================================================
#  量程判定（照着 步骤16 §1 的判据 ✓，界面直接显示结论）
# =============================================================================
def verdict(base, raw):
    """返回 (文字, 颜色键)。判据来自 refs/素材库/步骤16_上板风险审计.md §1：
       松手时 raw 应落在 [20, 2000]（既没快到底、也没计数器封顶）
       按住时 raw ≥ 1.3 × base
    """
    if base is None or raw is None:
        return "无数据", "gray"
    if raw > 2000:
        return "封顶风险(RC太慢)", "red"
    if base < 20 and raw < 20:
        return "太快(分辨率不足)", "red"
    if base > 0 and raw >= 1.3 * base:
        return "触摸 ✓ (%.2f×)" % (raw / float(base)), "green"
    return "静止 (%.2f×)" % (raw / float(base) if base else 0), "dim"


def list_ports():
    try:
        import serial.tools.list_ports as lp
        return [p.device for p in lp.comports()]
    except Exception:
        return []
