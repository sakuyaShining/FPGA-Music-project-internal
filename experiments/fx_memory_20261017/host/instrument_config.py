"""完整乐器配置文件：仅保存参数，不连接设备、不发送音符或 PCM。

数据采用与寄存器地址无关的物理单位，后续设备适配器负责量化和能力检查。
三种发声方式可保存，不表示当前 RTL 已实现这些方式。
"""
import argparse
import copy
import json
import os
from pathlib import Path
import tempfile


SCHEMA_VERSION = 1
MODES = ("sustain", "strike", "hybrid")
MAX_FILE_BYTES = 65536


class ConfigError(ValueError):
    """可直接展示给用户的配置错误。"""


def default_config(name="新音色", mode="sustain"):
    """返回独立草稿。默认数值是文件初始值，不是已试听的产品默认配置。"""
    result = {
        "schema_version": SCHEMA_VERSION,
        "name": name,
        "preset": 0,
        "spectrum_mode": "replace",
        "spectrum": [255] + [0] * 15,
        "articulation": {
            "mode": mode,
            "attack_ms": 5,
            "decay_ms": 300,
            "sustain_level": 192,
            "release_ms": 200,
            "hybrid_parts": ["sustain"] * 8 + ["strike"] * 8,
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
        # 不静默丢弃新版字段，以免用户误以为完整恢复了配置。
        raise ConfigError("%s 存在不支持字段：%s" % (path, ", ".join(sorted(extra))))


def _integer(value, low, high, path):
    # Python bool 是 int 的子类，必须明确排除。
    if type(value) is not int or not low <= value <= high:
        raise ConfigError("%s 必须是 %d–%d 的整数" % (path, low, high))


def _boolean(value, path):
    if type(value) is not bool:
        raise ConfigError("%s 必须是布尔值" % path)


def validate_config(value):
    """完整校验后返回深拷贝；失败时不修改调用方草稿。"""
    _object(value, ("schema_version", "name", "preset", "spectrum_mode", "spectrum", "articulation", "vibrato", "effects"), "配置")
    if type(value["schema_version"]) is not int or value["schema_version"] != SCHEMA_VERSION:
        raise ConfigError("不支持的 schema_version；当前仅支持 1")
    name = value["name"]
    if not isinstance(name, str) or not name.strip() or len(name) > 80 or any(ord(c) < 32 for c in name):
        raise ConfigError("name 必须是 1–80 字符的非空名称，不能包含控制字符")
    try:
        name.encode("utf-8")
    except UnicodeError as exc:
        raise ConfigError("name 包含不能编码为 UTF-8 的字符") from exc
    _integer(value["preset"], 0, 3, "preset")
    if type(value["spectrum_mode"]) is not str or value["spectrum_mode"] not in ("replace", "add"):
        raise ConfigError("spectrum_mode 必须是 replace 或 add")
    spectrum = value["spectrum"]
    if not isinstance(spectrum, list) or len(spectrum) != 16:
        raise ConfigError("spectrum 必须恰好包含 16 个分量")
    for index, amp in enumerate(spectrum):
        _integer(amp, 0, 255, "spectrum[%d]" % index)

    art = value["articulation"]
    _object(art, ("mode", "attack_ms", "decay_ms", "sustain_level", "release_ms", "hybrid_parts"), "articulation")
    if not isinstance(art["mode"], str) or art["mode"] not in MODES:
        raise ConfigError("articulation.mode 必须是 sustain、strike 或 hybrid")
    for field in ("attack_ms", "decay_ms", "release_ms"):
        _integer(art[field], 0, 60000, "articulation." + field)
    _integer(art["sustain_level"], 0, 255, "articulation.sustain_level")
    parts = art["hybrid_parts"]
    if not isinstance(parts, list) or len(parts) != 16 or any(type(p) is not str or p not in ("sustain", "strike") for p in parts):
        raise ConfigError("articulation.hybrid_parts 必须有 16 项，每项为 sustain 或 strike")

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


def _unique_pairs(pairs):
    result = {}
    for key, value in pairs:
        if key in result:
            raise ConfigError("JSON 字段重复：%s" % key)
        result[key] = value
    return result


def _reject_constant(value):
    raise ConfigError("JSON 不允许 %s" % value)


def load_config(path):
    """先完整验证，返回新对象；不触碰 GUI 草稿或设备。"""
    with open(path, "rb") as stream:
        data = stream.read(MAX_FILE_BYTES + 1)
    if len(data) > MAX_FILE_BYTES:
        raise ConfigError("配置文件超过 64 KiB")
    try:
        value = json.loads(data.decode("utf-8-sig"), object_pairs_hook=_unique_pairs,
                           parse_constant=_reject_constant)
    except (UnicodeError, json.JSONDecodeError, RecursionError) as exc:
        raise ConfigError("配置文件不是有效 UTF-8 JSON：%s" % exc) from exc
    return validate_config(value)


def save_config(path, value):
    """先校验，再原子替换；写入中途失败时保留已有文件。"""
    checked = validate_config(value)
    payload = (json.dumps(checked, ensure_ascii=False, indent=2, allow_nan=False) + "\n").encode("utf-8")
    target = Path(path)
    temporary = None
    try:
        with tempfile.NamedTemporaryFile(dir=str(target.parent), prefix="." + target.name + ".",
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


def main(argv=None):
    parser = argparse.ArgumentParser(description="创建或校验乐器配置草稿；不发送设备命令")
    commands = parser.add_subparsers(dest="command", required=True)
    create = commands.add_parser("new", help="创建本地配置草稿")
    create.add_argument("path")
    create.add_argument("--name", default="新音色")
    create.add_argument("--mode", choices=MODES, default="sustain")
    check = commands.add_parser("check", help="校验已有配置文件")
    check.add_argument("path")
    args = parser.parse_args(argv)
    try:
        if args.command == "new":
            save_config(args.path, default_config(args.name, args.mode))
            print("已保存本地配置草稿：%s（尚未应用到设备）" % args.path)
        else:
            cfg = load_config(args.path)
            print("配置有效：%s / %s（文件校验不代表硬件支持）" % (cfg["name"], cfg["articulation"]["mode"]))
        return 0
    except (ConfigError, OSError) as exc:
        print("配置失败：%s" % exc)
        return 1


if __name__ == "__main__":
    raise SystemExit(main())
