"""schema-2 乐器配置：激发模式作为音符属性的参考实现。

与 schema-1 的差别：
  · tone（进 88 位词）与 articulation（进寄存器）分开
  · strike 参数用 d_m / d_k_base / d_k_curve 三个绝对量，不继承音色的 d_k
  · 新增 strike_s_lvl：低次泛音留余音（Q3）
  · hybrid_parts 只用来生成 artic_mask 的预设值

本文件不导入 PyQt，可独立跑 `python articulation_v2.py selftest`。

合并进项目时的替换关系：
  gui/instrument_config.py  ← SCHEMA_VERSION / MODES / default_config /
                               validate_config / load_config / save_config
  host/config_adapter.py    ← encode / decode / part_ms / compile_tone /
                               compile_articulation / solve_dk_base
"""
import argparse
import copy
import json
import os
from pathlib import Path
import sys
import tempfile

SCHEMA_VERSION = 2
MODES = ("sustain", "strike", "hybrid")
MAX_FILE_BYTES = 65536

# 与 RTL 参数一致（tdm_top_owned.v:127 / tdm_engine_rh.v:148）
FS = 27000000 / 512          # 52734.375 Hz
PART = 16                    # 每音符泛音数
EPAR_FULL = 32768            # osc_env.v:80 FULL，满幅

# ---------------------------------------------------------------------------
# 包络步数模型（与 config_adapter.py 逐位一致，此处复制以便独立测试）
# ---------------------------------------------------------------------------


def exp_steps(floor, m, k):
    """从满幅衰减到 floor 需要多少拍。与 RTL 的 osc_env 推进规则一致。"""
    level = EPAR_FULL
    n = 0
    while level > floor:
        step = max(1, ((level * m) >> k) & 0xFFFF)
        level = floor if level <= floor + step else level - step
        n += 1
        if n > 32768:
            return 32768          # 饱和，不抛异常（原实现抛，上层无法区分）
    return max(1, n)


def part_ms(base, curve, d_m, k, shift=0):
    """单个泛音在 strike 下的衰减时长（毫秒）。

    shift 固定 0：strike 要短，而音色自带的 d_shift 会把时长放大 2^shift 倍。
    这个函数必须与 RTL 的
        k_curve_off = (k * curve) >> 4
        d_k         = max(0, base - k_curve_off)
    逐位一致，否则上位机显示与板子实际差一个数量级。
    """
    if not 0 <= k < PART:
        raise ValueError("k 必须在 0–15")
    if not 0 <= curve <= 15:
        raise ValueError("curve 必须在 0–15")
    d_k = max(0, base - ((k * curve) >> 4))
    return exp_steps(0, d_m, d_k) * (1 << shift) * 1000 / FS


def spectrum_span(spectrum):
    """最高有效泛音序号（amp>0 的最大 k）；全零返回 0。"""
    span = 0
    for i, amp in enumerate(spectrum):
        if amp > 0:
            span = i
    return span


def suggest_curve(span):
    """**仅供参考**的建议值，不参与默认编译，也不要求上位机在线。

    用途：用户在屏/菜单上把频谱改成 N 个泛音后，界面可以提示
    "梯度建议设为 X"。它不自动生效——因为"按泛音数猜意图"本身
    就不是通用乐器该做的事（那是在为钟/马林巴做特化）。

    实测依据：目标让最高泛音相对基频的倍率落在 20–40 倍（马林巴/钟区间），
    112/(span+1) 与逐点反解吻合（span=7→14, 11→9, 15→7）。
    泛音数 ≤ 4 时数学上达不到 20 倍（(k*curve)>>4 在 k=3 最多 2 档），
    这是限制不是 bug。
    """
    return max(0, min(15, round(112.0 / (span + 1))))


default_curve = suggest_curve   # 旧名兼容（上一版叫 default_curve）


# ---------------------------------------------------------------------------
# 默认配置与校验
# ---------------------------------------------------------------------------


def default_config(name="新音色", mode="sustain"):
    """schema-2 草稿。默认数值是文件初始值，不是已试听的产品默认配置。"""
    spectrum = [255] + [0] * 15
    result = {
        "schema_version": SCHEMA_VERSION,
        "name": name,
        "preset": 0,
        "spectrum_mode": "replace",
        "spectrum": spectrum,
        "tone": {
            "attack_ms": 5,
            "decay_ms": 1200,
            "decay_spread": 4,        # 高次泛音比基频快多少档（0=同步, 8=快 8 档）
            "sustain_level": 192,
            "release_ms": 200,
        },
        "articulation": {
            "mode": mode,
            "strike": {
                "d_m": 3,
                "d_k_base": 14,
                "d_k_curve": 8,           # 固定默认，不按频谱猜（通用乐器）
                "s_lvl": 0,               # 0 = 无余音。通用默认，钟类自己调高
            },
            "hybrid_parts": _default_hybrid_parts(),
            "auto_release": True,
            "auto_release_ms": None,      # None = 编译期按衰减时长自动定
        },
        "vibrato": {"enabled": False, "rate_millihz": 5500, "depth_cents": 0},
        "effects": {
            "dry_enabled": True,
            "delay": {"enabled": False, "time_ms": 30, "feedback_q8": 96},
            "chorus": {"enabled": False, "rate_millihz": 500, "depth_ms": 1},
            "reverb": {"enabled": False, "feedback_q8": 128, "damping": 3},
        },
    }
    return validate_config(result)


def _default_hybrid_parts():
    """前 8 sustain + 后 8 strike（中性默认值）。

    不做成"前 3 后 13"是因为那是钟琴的取向，不是通用乐器的取向。
    通用默认值应当尽量不带倾向，由用户在演奏/编辑时自己分组。
    """
    return ["sustain"] * 8 + ["strike"] * 8


class ConfigError(ValueError):
    """可直接展示给用户的配置错误。"""


def _object(value, keys, path):
    if not isinstance(value, dict):
        raise ConfigError("%s 必须是对象" % path)
    if any(type(key) is not str for key in value):
        raise ConfigError("%s 的字段名必须是字符串" % path)
    missing = set(keys) - set(value)
    extra = set(value) - set(keys)
    if missing:
        raise ConfigError("%s 缺少字段：%s" % (path, ", ".join(sorted(missing))))
    if extra:
        raise ConfigError("%s 存在不支持字段：%s" % (path, ", ".join(sorted(extra))))


def _integer(value, low, high, path):
    if type(value) is not int or not low <= value <= high:
        raise ConfigError("%s 必须是 %d–%d 的整数" % (path, low, high))


def _boolean(value, path):
    if type(value) is not bool:
        raise ConfigError("%s 必须是布尔值" % path)


def validate_config(value):
    """完整校验后返回深拷贝；失败时不修改调用方草稿。"""
    _object(value, ("schema_version", "name", "preset", "spectrum_mode",
                    "spectrum", "tone", "articulation", "vibrato", "effects"), "配置")
    if type(value["schema_version"]) is not int or value["schema_version"] != SCHEMA_VERSION:
        raise ConfigError("不支持的 schema_version；当前仅支持 2（schema-1 请先 migrate_v1_to_v2）")
    name = value["name"]
    if not isinstance(name, str) or not name.strip() or len(name) > 80 \
            or any(ord(c) < 32 for c in name):
        raise ConfigError("name 必须是 1–80 字符的非空名称，不能包含控制字符")
    try:
        name.encode("utf-8")
    except UnicodeError as exc:
        raise ConfigError("name 包含不能编码为 UTF-8 的字符") from exc
    _integer(value["preset"], 0, 3, "preset")
    if type(value["spectrum_mode"]) is not str or value["spectrum_mode"] not in ("replace", "add"):
        raise ConfigError("spectrum_mode 必须是 replace 或 add")
    spectrum = value["spectrum"]
    if not isinstance(spectrum, list) or len(spectrum) != PART:
        raise ConfigError("spectrum 必须恰好包含 %d 个分量" % PART)
    for index, amp in enumerate(spectrum):
        _integer(amp, 0, 255, "spectrum[%d]" % index)

    tone = value["tone"]
    _object(tone, ("attack_ms", "decay_ms", "decay_spread",
                   "sustain_level", "release_ms"), "tone")
    for field in ("attack_ms", "decay_ms", "release_ms"):
        _integer(tone[field], 0, 60000, "tone." + field)
    _integer(tone["decay_spread"], 0, 8, "tone.decay_spread")
    _integer(tone["sustain_level"], 0, 255, "tone.sustain_level")
    # sustain_level=255 意味着衰减到满幅=不衰减，fit_exp 会退化成 shift=14 的假值
    if tone["sustain_level"] == 255 and tone["decay_ms"] > 0:
        raise ConfigError("tone.sustain_level=255 与 decay_ms>0 冲突："
                          "衰减到满幅等于不衰减，请改用 254 或把 decay_ms 设为 0")

    art = value["articulation"]
    _object(art, ("mode", "strike", "hybrid_parts", "auto_release", "auto_release_ms"),
            "articulation")
    if not isinstance(art["mode"], str) or art["mode"] not in MODES:
        raise ConfigError("articulation.mode 必须是 sustain、strike 或 hybrid")

    strike = art["strike"]
    _object(strike, ("d_m", "d_k_base", "d_k_curve", "s_lvl"), "articulation.strike")
    _integer(strike["d_m"], 1, 3, "articulation.strike.d_m")      # 0 非法（除零）
    _integer(strike["d_k_base"], 0, 31, "articulation.strike.d_k_base")
    # d_k_curve = None 表示"按频谱自动算"，编译期用 default_curve(span) 填充。
    # 存绝对值会与 spectrum 自相矛盾：spectrum 从 1 个泛音改成 16 个时，
    # 旧 curve 可能过大，导致高次泛音 0 ms 就消失。
    if strike["d_k_curve"] is not None:
        _integer(strike["d_k_curve"], 0, 15, "articulation.strike.d_k_curve")
    _integer(strike["s_lvl"], 0, 15, "articulation.strike.s_lvl")
    if strike["d_k_base"] == 0 and strike["d_m"] == 0:
        raise ConfigError("articulation.strike 的 d_m 与 d_k_base 不能同时为 0")

    parts = art["hybrid_parts"]
    if not isinstance(parts, list) or len(parts) != PART \
            or any(type(p) is not str or p not in ("sustain", "strike") for p in parts):
        raise ConfigError("articulation.hybrid_parts 必须有 %d 项，每项为 sustain 或 strike" % PART)

    _boolean(art["auto_release"], "articulation.auto_release")
    hold = art["auto_release_ms"]
    if hold is not None:
        # 硬件 20 位拍数：0xFFFFF / 52734.375 ≈ 19.9 s
        _integer(hold, 0, 19000, "articulation.auto_release_ms")

    vib = value["vibrato"]
    _object(vib, ("enabled", "rate_millihz", "depth_cents"), "vibrato")
    _boolean(vib["enabled"], "vibrato.enabled")
    _integer(vib["rate_millihz"], 0, 20000, "vibrato.rate_millihz")
    _integer(vib["depth_cents"], 0, 200, "vibrato.depth_cents")

    fx = value["effects"]
    _object(fx, ("dry_enabled", "delay", "chorus", "reverb"), "effects")
    _boolean(fx["dry_enabled"], "effects.dry_enabled")
    rules = {
        "delay": {"time_ms": (0, 2000), "feedback_q8": (0, 255)},
        "chorus": {"rate_millihz": (0, 20000), "depth_ms": (0, 100)},
        "reverb": {"feedback_q8": (0, 255), "damping": (0, 7)},
    }
    for effect, fields in rules.items():
        entry = fx[effect]
        path = "effects." + effect
        _object(entry, ("enabled",) + tuple(fields), path)
        _boolean(entry["enabled"], path + ".enabled")
        for field, limits in fields.items():
            _integer(entry[field], limits[0], limits[1], path + "." + field)
    return copy.deepcopy(value)


# ---------------------------------------------------------------------------
# schema-1 → schema-2 迁移
# ---------------------------------------------------------------------------


def migrate_v1_to_v2(old):
    """把 schema-1 文档升级成 schema-2。不改调用方对象。

    schema-1 的 articulation 混着音色参数与演奏参数，这里按语义拆开：
      attack_ms / decay_ms / sustain_level / release_ms → tone
      mode / hybrid_parts                               → articulation
      strike / auto_release / auto_release_ms           → 新增默认值
    """
    if old.get("schema_version") != 1:
        raise ConfigError("migrate_v1_to_v2 只接受 schema_version=1")
    art = old["articulation"]
    spectrum = list(old["spectrum"])
    new = {
        "schema_version": 2,
        "name": old["name"],
        "preset": old["preset"],
        "spectrum_mode": old["spectrum_mode"],
        "spectrum": spectrum,
        "tone": {
            "attack_ms": art["attack_ms"],
            "decay_ms": art["decay_ms"],
            "decay_spread": 4,
            "sustain_level": art["sustain_level"],
            "release_ms": art["release_ms"],
        },
        "articulation": {
            "mode": art["mode"],
            "strike": {
                "d_m": 3,
                "d_k_base": 14,
                "d_k_curve": 8,
                "s_lvl": 0,
            },
            "hybrid_parts": list(art["hybrid_parts"]),
            "auto_release": True,
            "auto_release_ms": None,
        },
        "vibrato": copy.deepcopy(old["vibrato"]),
        "effects": copy.deepcopy(old["effects"]),
    }
    # schema-1 的 decay_ms=300 是风琴感的来源之一；不擅自改，只提示
    return validate_config(new)


# ---------------------------------------------------------------------------
# 88 位词编解码（与 schema-1 完全一致，未改动）
# ---------------------------------------------------------------------------

FIELDS = ('ratio_q8', 'amplitude', 'sustain_q15', 'decay_m', 'decay_k', 'decay_shift',
          'attack_inc', 'attack_shift', 'release_m', 'release_k', 'release_shift')

LIMITS = {
    'ratio_q8': (1, 65535), 'amplitude': (0, 255), 'sustain_q15': (0, 32768),
    'decay_m': (1, 3), 'decay_k': (0, 31), 'decay_shift': (0, 15),
    'attack_inc': (1, 32768), 'attack_shift': (0, 15),
    'release_m': (1, 3), 'release_k': (0, 31), 'release_shift': (0, 15),
}


def _int(v, lo, hi, name):
    if type(v) is not int or not lo <= v <= hi:
        raise ValueError(name + ' out of range')
    return v


def encode(parts):
    if type(parts) is not list or len(parts) != PART:
        raise ValueError('exactly %d partials' % PART)
    words = []
    for p in parts:
        if type(p) is not dict or set(p) != set(FIELDS):
            raise ValueError('unknown/missing partial field')
        for k, (lo, hi) in LIMITS.items():
            _int(p[k], lo, hi, k)
        env = ((1 << 35) | (p['attack_shift'] << 31) | (p['attack_inc'] << 15)
               | (p['decay_shift'] << 11) | (p['release_shift'] << 7)
               | (p['release_m'] << 5) | p['release_k'])
        base = ((p['ratio_q8'] << 32) | (p['amplitude'] << 24)
                | (p['sustain_q15'] << 7) | (p['decay_m'] << 5) | p['decay_k'])
        words.append((env << 48) | base)
    return words


def decode(words):
    if type(words) is not list or len(words) != PART:
        raise ValueError('exactly %d words' % PART)
    parts = []
    for w in words:
        _int(w, 0, (1 << 88) - 1, 'word')
        if w >> 84 or not w & (1 << 83) or w & (1 << 23):
            raise ValueError('reserved/format bits')
        e = w >> 48
        parts.append(dict(
            ratio_q8=(w >> 32) & 65535, amplitude=(w >> 24) & 255,
            sustain_q15=(w >> 7) & 65535, decay_m=(w >> 5) & 3, decay_k=w & 31,
            decay_shift=(e >> 11) & 15, attack_inc=(e >> 15) & 65535,
            attack_shift=(e >> 31) & 15, release_m=(e >> 5) & 3,
            release_k=e & 31, release_shift=(e >> 7) & 15))
    assert encode(parts) == words
    return parts


# ---------------------------------------------------------------------------
# 编译：音色 → 88 位词；演奏属性 → 寄存器
# ---------------------------------------------------------------------------


def fit_exp(ms, floor, fixed_m=None):
    """找最接近目标时长的 (m, k, shift)。

    fixed_m：强制 d_m。16 个泛音必须共用同一个 m，否则衰减【曲线形状】不同
    （m=3 初期衰减比 m=1 快），频谱演化会不自然。实测逐泛音独立搜索时
    m 在 1 和 3 之间跳、jitter 最高到 78ms。
    """
    target = round(FS * ms / 1000)
    best = None
    for m in ((fixed_m,) if fixed_m else (1, 2, 3)):
        for k in range(22):
            if k == 0 and m != 1:
                continue
            steps = exp_steps(floor, m, k)
            for shift in range(16):
                duration = steps * (1 << shift)
                cand = (abs(duration - target), shift, k, m, steps)
                if best is None or cand < best:
                    best = cand
    error, shift, k, m, steps = best
    return dict(m=m, k=k, shift=shift,
                nominal_ms=steps * (1 << shift) * 1000 / FS,
                phase_jitter_bound_ms=((1 << shift) - 1) * 1000 / FS,
                requested_ms=ms,
                saturated=steps >= 32768)


def fit_attack(ms):
    target = round(FS * ms / 1000)
    best = None
    for shift in range(16):
        ideal = EPAR_FULL * (1 << shift) / max(1, target)
        for inc in {max(1, min(EPAR_FULL, int(ideal) + d)) for d in (-2, -1, 0, 1, 2)}:
            steps = (EPAR_FULL + inc - 1) // inc
            duration = steps * (1 << shift)
            cand = (abs(duration - target), shift, inc, steps)
            if best is None or cand < best:
                best = cand
    error, shift, inc, steps = best
    return dict(inc=inc, shift=shift,
                nominal_ms=steps * (1 << shift) * 1000 / FS,
                phase_jitter_bound_ms=((1 << shift) - 1) * 1000 / FS,
                requested_ms=ms)


def compile_tone(document, preset_words=None):
    """只编 tone。16 个泛音的 s_lvl 全相同，不再把 strike 烘进词里。"""
    doc = validate_config(document)
    tone = doc["tone"]
    attack = fit_attack(tone["attack_ms"])
    release = fit_exp(tone["release_ms"], 100)
    sustain = round(tone["sustain_level"] * EPAR_FULL / 255)

    # ── 衰减：只 fit 基频，其余泛音按梯度递减 ────────────────────────────
    # 为什么不是每个泛音独立 fit：
    #   实测逐泛音搜索会让 d_m 在 1 和 3 之间跳（衰减【曲线形状】不同）、
    #   d_k 不单调、jitter 最高 78ms。16 个泛音必须共用 (m, shift)，
    #   只有 d_k 递减，这样频谱演化才连续。
    # 实测（钢琴中音 2500ms, spread=4, m=3）：2504.9 → 155.3ms，16 倍跨度。
    decay0 = fit_exp(tone["decay_ms"], sustain)
    spread = tone["decay_spread"]
    if preset_words is None:
        preset_words = [int(w, 16) for w in
                        (Path(__file__).resolve().parents[1] / 'src/preset_part.hex')
                        .read_text(encoding='ascii').split()]
    if len(preset_words) != 64:
        raise ValueError('preset ROM must contain 64 words')

    parts, timing = [], []
    for i in range(PART):
        base = preset_words[doc["preset"] * PART + i]
        amp = doc["spectrum"][i] if doc["spectrum_mode"] == "replace" \
            else min(255, doc["spectrum"][i] + ((base >> 24) & 255))
        d_k = max(0, decay0['k'] - round(spread * i / (PART - 1)))
        parts.append(dict(
            ratio_q8=(base >> 32) & 65535, amplitude=amp,
            sustain_q15=sustain,
            decay_m=decay0['m'], decay_k=d_k, decay_shift=decay0['shift'],
            attack_inc=attack['inc'], attack_shift=attack['shift'],
            release_m=release['m'], release_k=release['k'],
            release_shift=release['shift']))
        timing.append(dict(part=i, amplitude=amp, d_k=d_k,
                           ms=exp_steps(sustain, decay0['m'], d_k)
                              * (1 << decay0['shift']) * 1000 / FS))
    return encode(parts), dict(
        format='slot-v1/88-bit', sample_rate_nominal=FS,
        sustain_q15=sustain, decay=decay0, decay_spread=spread,
        attack=attack, release=release, partials=timing)


def compile_articulation(document):
    """演奏属性 → 寄存器。返回的 dict 字段名与 RTL 端口一致。"""
    doc = validate_config(document)
    a = doc["articulation"]
    mode = a["mode"]
    if mode == "sustain":
        enable, mask = 0, 0x0000
    elif mode == "strike":
        enable, mask = 1, 0xFFFF
    else:
        enable = 1
        mask = sum(1 << i for i, p in enumerate(a["hybrid_parts"]) if p == "strike")

    s = a["strike"]
    span = spectrum_span(doc["spectrum"])
    curve = s["d_k_curve"] if s["d_k_curve"] is not None else default_curve(span)
    base_ms = part_ms(s["d_k_base"], curve, s["d_m"], 0)
    if a["auto_release_ms"] is not None:
        hold_ms = a["auto_release_ms"]
    elif s["s_lvl"] > 0:
        hold_ms = max(1500.0, 3.0 * base_ms)     # 有余音：留出尾巴
    else:
        hold_ms = 2.0 * base_ms                  # 无余音：衰减完就回收

    # 20 位拍数。16 位只有 1243 ms，装不下 1.5 s 的余音尾巴（实测踩过）。
    hold_ticks = min(0xFFFFF, round(hold_ms * FS / 1000))

    return dict(
        artic_enable=enable,
        artic_mask=mask,
        strike_d_m=s["d_m"],
        strike_d_k_base=s["d_k_base"],
        strike_d_k_curve=curve,
        strike_s_lvl=s["s_lvl"],
        strike_auto_rel=1 if a["auto_release"] else 0,
        strike_hold_ticks=hold_ticks,
        strike_hold_ms_actual=hold_ticks * 1000 / FS,
        # 以下仅供上位机显示，不进硬件
        _curve_source="auto(span=%d)" % span if s["d_k_curve"] is None else "explicit",
        _base_part_ms=base_ms,
        _top_part_ms=part_ms(s["d_k_base"], curve, s["d_m"], span),
    )


def solve_dk_base(target_ms, curve=10, d_m=3, span=15):
    """GUI 反解：想让最高泛音在 target_ms 衰减完，d_k_base 该取多少。

    保持 curve 不变（它决定梯度形状），只动基准值（它决定整体快慢）。
    """
    best = None
    for base in range(32):
        ms = part_ms(base, curve, d_m, span)
        cand = (abs(ms - target_ms), base)
        if best is None or cand < best:
            best = cand
    return best[1]


# ---------------------------------------------------------------------------
# 文件读写
# ---------------------------------------------------------------------------


def _unique_pairs(pairs):
    result = {}
    for key, value in pairs:
        if key in result:
            raise ConfigError("JSON 字段重复：%s" % key)
        result[key] = value
    return result


def _reject_constant(value):
    raise ConfigError("JSON 不允许 %s" % value)


def load_config(path, on_migrate=None):
    """读文件。遇到 schema-1 自动升级，并通过 on_migrate 回调告知调用方。"""
    with open(path, "rb") as stream:
        data = stream.read(MAX_FILE_BYTES + 1)
    if len(data) > MAX_FILE_BYTES:
        raise ConfigError("配置文件超过 64 KiB")
    try:
        value = json.loads(data.decode("utf-8-sig"), object_pairs_hook=_unique_pairs,
                           parse_constant=_reject_constant)
    except (UnicodeError, json.JSONDecodeError, RecursionError) as exc:
        raise ConfigError("配置文件不是有效 UTF-8 JSON：%s" % exc) from exc
    if isinstance(value, dict) and value.get("schema_version") == 1:
        upgraded = migrate_v1_to_v2(value)
        if on_migrate is not None:
            on_migrate(value, upgraded)
        return upgraded
    return validate_config(value)


def save_config(path, value):
    checked = validate_config(value)
    payload = (json.dumps(checked, ensure_ascii=False, indent=2, allow_nan=False)
               + "\n").encode("utf-8")
    target = Path(path)
    temporary = None
    try:
        with tempfile.NamedTemporaryFile(dir=str(target.parent),
                                         prefix="." + target.name + ".",
                                         suffix=".tmp", delete=False) as stream:
            temporary = stream.name
            stream.write(payload)
            stream.flush()
            os.fsync(stream.fileno())
        os.replace(temporary, target)
        temporary = None
    finally:
        if temporary is not None:
            os.unlink(temporary)


# ---------------------------------------------------------------------------
# 自测
# ---------------------------------------------------------------------------


def _selftest():
    fails = []

    def check(name, cond, detail=""):
        print(("  PASS  " if cond else "  FAIL  ") + name + ("   " + detail if detail else ""))
        if not cond:
            fails.append(name)

    print("[1] 默认配置（通用乐器的中性默认，不带钟琴倾向）")
    cfg = default_config()
    check("schema_version=2", cfg["schema_version"] == 2)
    check("hybrid 前 8 / 后 8",
          cfg["articulation"]["hybrid_parts"] == ["sustain"] * 8 + ["strike"] * 8)
    check("s_lvl=0（默认无余音）", cfg["articulation"]["strike"]["s_lvl"] == 0)
    check("d_k_curve=8（固定，不按频谱猜）",
          cfg["articulation"]["strike"]["d_k_curve"] == 8)
    check("auto_release_ms=null（编译器自动定）",
          cfg["articulation"]["auto_release_ms"] is None)
    check("tone.decay_ms=1200（钢琴量级）", cfg["tone"]["decay_ms"] == 1200)

    print("[2] 校验")
    bad = copy.deepcopy(cfg)
    bad["articulation"]["strike"]["d_m"] = 0
    try:
        validate_config(bad)
        check("d_m=0 应被拒", False)
    except ConfigError:
        check("d_m=0 应被拒", True)
    bad = copy.deepcopy(cfg)
    bad["tone"]["sustain_level"] = 255
    try:
        validate_config(bad)
        check("sustain_level=255 应被拒", False)
    except ConfigError:
        check("sustain_level=255 应被拒", True)

    print("[3] 梯度单调性（curve=10, base=14, d_m=3）")
    times = [part_ms(14, 10, 3, k) for k in range(16)]
    check("基频 340ms", abs(times[0] - 340.0) < 1.0, "%.1f" % times[0])
    check("k=15 约 1.9ms", abs(times[15] - 1.9) < 0.2, "%.1f" % times[15])
    check("严格单调递减", all(times[i] >= times[i + 1] for i in range(15)))
    check("跨度 > 100 倍", times[0] / times[15] > 100, "%.1f 倍" % (times[0] / times[15]))

    print("[4] default_curve 反解")
    for span in (7, 11, 15):
        c = default_curve(span)
        lo, hi = part_ms(14, c, 3, 0), part_ms(14, c, 3, span)
        ratio = lo / hi
        check("span=%2d curve=%2d 倍率 %.1f (目标 20–40)" % (span, c, ratio),
              20 <= ratio <= 40)
    # 泛音 ≤4 时 (k*curve)>>4 最多 2 档，倍率上不去；这是数学限制，不是 bug。
    # 泛音 =2（span=1）时 (1*15)>>4 = 0，梯度恒为 0 —— 两个泛音本来也谈不上
    # 「频谱演化」，物理上不需要。
    for span, floor_ratio in ((1, 1.0), (3, 1.5)):
        c = default_curve(span)
        lo, hi = part_ms(14, c, 3, 0), part_ms(14, c, 3, span)
        check("span=%2d curve=%2d 倍率 %.1f (>=%.1f)" % (span, c, lo / hi, floor_ratio),
              lo / hi >= floor_ratio)

    print("[5] 编译一致性：compile_articulation 与 part_ms 对得上")
    reg = compile_articulation(cfg)
    check("artic_enable=0 (sustain)", reg["artic_enable"] == 0)
    strike_cfg = default_config(mode="strike")
    reg_s = compile_articulation(strike_cfg)
    check("artic_mask=0xFFFF (strike)", reg_s["artic_mask"] == 0xFFFF)
    check("s_lvl=0 时 hold = 2×基频（约 680ms）",
          600 <= reg_s["strike_hold_ms_actual"] <= 750,
          "%.0fms" % reg_s["strike_hold_ms_actual"])
    # 显式开余音后，hold 应拉到 1500ms（16 位装不下，故必须 20 位）
    tail_cfg = default_config(mode="strike")
    tail_cfg["articulation"]["strike"]["s_lvl"] = 2
    reg_t = compile_articulation(tail_cfg)
    check("s_lvl=2 时 hold >= 1500ms",
          reg_t["strike_hold_ms_actual"] >= 1500,
          "%.0fms" % reg_t["strike_hold_ms_actual"])
    check("hold_ticks 装得下 20 位", reg_t["strike_hold_ticks"] <= 0xFFFFF,
          "%d ticks" % reg_t["strike_hold_ticks"])

    print("[6] 88 位词往返")
    # 构造合法预设词：ratio=0x100, amp=200, s_lvl=30000, d_m=3, d_k=20, env=0
    legal = [((0x100 << 32) | (200 << 24) | (30000 << 7) | (3 << 5) | 20)] * 64
    words, report = compile_tone(cfg, preset_words=legal)
    check("16 词", len(words) == 16)
    check("s_lvl 全相同", len({p["sustain_q15"] for p in decode(words)}) == 1)
    check("encode/decode 往返", encode(decode(words)) == words)
    check("amp 走 spectrum（replace 模式）",
          decode(words)[0]["amplitude"] == cfg["spectrum"][0])

    print("[7] schema-1 迁移")
    v1 = {
        "schema_version": 1, "name": "旧", "preset": 0,
        "spectrum_mode": "replace", "spectrum": [100, 40] + [0] * 14,
        "articulation": {"mode": "hybrid", "attack_ms": 1, "decay_ms": 1,
                         "sustain_level": 160, "release_ms": 10,
                         "hybrid_parts": ["sustain"] + ["strike"] * 15},
        "vibrato": {"enabled": False, "rate_millihz": 5500, "depth_cents": 0},
        "effects": {"dry_enabled": True,
                    "delay": {"enabled": False, "time_ms": 30, "feedback_q8": 96},
                    "chorus": {"enabled": False, "rate_millihz": 500, "depth_ms": 1},
                    "reverb": {"enabled": False, "feedback_q8": 128, "damping": 3}},
    }
    v2 = migrate_v1_to_v2(v1)
    check("升到 2", v2["schema_version"] == 2)
    check("tone.decay_ms 保留", v2["tone"]["decay_ms"] == 1)
    check("hybrid_parts 保留", v2["articulation"]["hybrid_parts"] == v1["articulation"]["hybrid_parts"])
    check("mask = 0xFFFE", compile_articulation(v2)["artic_mask"] == 0xFFFE)

    print("[8] solve_dk_base 往返")
    for target in (50, 100, 200, 340, 600):
        b = solve_dk_base(target, curve=10, d_m=3, span=15)
        got = part_ms(b, 10, 3, 15)
        check("目标 %3dms -> base=%2d 实得 %6.1fms" % (target, b, got),
              abs(got - target) / target < 0.35)

    print("[9] 衰减梯度（钢琴中音：decay 2500ms, spread 4, s_lvl 120）")
    piano = default_config("钢琴", "sustain")
    piano["tone"].update(decay_ms=2500, decay_spread=4, sustain_level=120, attack_ms=3)
    words_p, rep_p = compile_tone(piano, preset_words=legal)
    dec_p = decode(words_p)
    check("16 个泛音共用同一个 decay_m",
          len({p["decay_m"] for p in dec_p}) == 1,
          "m=%d" % dec_p[0]["decay_m"])
    check("16 个泛音共用同一个 decay_shift",
          len({p["decay_shift"] for p in dec_p}) == 1,
          "shift=%d" % dec_p[0]["decay_shift"])
    dks = [p["decay_k"] for p in dec_p]
    check("d_k 单调不增（高次衰减更快）",
          all(dks[i] >= dks[i + 1] for i in range(15)), str(dks))
    ms_list = [t["ms"] for t in rep_p["partials"]]
    check("基频 2.0–3.0 s", 2000 <= ms_list[0] <= 3000, "%.0fms" % ms_list[0])
    check("第 16 泛音 < 300 ms", ms_list[15] < 300, "%.0fms" % ms_list[15])
    check("跨度 >= 8 倍", ms_list[0] / max(1e-9, ms_list[15]) >= 8,
          "%.1f 倍" % (ms_list[0] / max(1e-9, ms_list[15])))
    check("s_lvl 全相同", len({p["sustain_q15"] for p in dec_p}) == 1)

    print("[10] spread=0 时 16 个泛音时长应完全相同")
    flat = default_config("平", "sustain")
    flat["tone"].update(decay_ms=1200, decay_spread=0)
    _, rep_f = compile_tone(flat, preset_words=legal)
    ms_f = [t["ms"] for t in rep_f["partials"]]
    check("全部相等", max(ms_f) - min(ms_f) < 1.0, "%.1f–%.1f" % (min(ms_f), max(ms_f)))

    print()
    if fails:
        print("失败 %d 项：%s" % (len(fails), ", ".join(fails)))
        return 1
    print("全部通过")
    return 0


def main(argv=None):
    parser = argparse.ArgumentParser(description="schema-2 乐器配置；不发送设备命令")
    sub = parser.add_subparsers(dest="command", required=True)

    create = sub.add_parser("new", help="创建本地配置草稿")
    create.add_argument("path")
    create.add_argument("--name", default="新音色")
    create.add_argument("--mode", choices=MODES, default="sustain")

    check = sub.add_parser("check", help="校验已有配置文件（schema-1 自动升级并提示）")
    check.add_argument("path")

    sub.add_parser("selftest", help="跑内置回归")

    dump = sub.add_parser("dump", help="打印编译结果")
    dump.add_argument("path")

    args = parser.parse_args(argv)
    try:
        if args.command == "new":
            save_config(args.path, default_config(args.name, args.mode))
            print("已保存本地配置草稿：%s（尚未应用到设备）" % args.path)
        elif args.command == "check":
            def warn(old, new):
                print("注意：文件是 schema-1，已升级到 schema-2（未写回）")
                print("      tone.decay_ms=%d 建议改为 1200 左右（钟/钢琴量级）"
                      % new["tone"]["decay_ms"])
            cfg = load_config(args.path, on_migrate=warn)
            print("配置有效：%s / %s（文件校验不代表硬件支持）"
                  % (cfg["name"], cfg["articulation"]["mode"]))
        elif args.command == "dump":
            cfg = load_config(args.path)
            reg = compile_articulation(cfg)
            print("寄存器：")
            for k, v in reg.items():
                print("  %-20s %s" % (k, v))
            print("每泛音 strike 时长：")
            s = cfg["articulation"]["strike"]
            for k in range(PART):
                print("  k=%2d  %7.1f ms" % (k, part_ms(reg["strike_d_k_base"],
                                                        reg["strike_d_k_curve"],
                                                        reg["strike_d_m"], k)))
        else:
            return _selftest()
        return 0
    except (ConfigError, OSError, ValueError) as exc:
        print("失败：%s" % exc)
        return 1


if __name__ == "__main__":
    raise SystemExit(main())
