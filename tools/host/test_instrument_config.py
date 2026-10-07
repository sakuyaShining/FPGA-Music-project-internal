"""配置文件边界、往返和写入失败验证；不连接设备。"""
import copy
import json
from pathlib import Path
import tempfile
import unittest
from unittest.mock import patch

from instrument_config import ConfigError, MODES, default_config, load_config, main, save_config, validate_config


class ConfigTests(unittest.TestCase):
    def test_complete_roundtrip_all_modes(self):
        with tempfile.TemporaryDirectory() as directory:
            for mode in MODES:
                with self.subTest(mode=mode):
                    cfg = default_config("钟声 Ω 中文", mode)
                    cfg["spectrum"] = list(range(16))
                    cfg["preset"] = 2
                    cfg["spectrum_mode"] = "add"
                    cfg["vibrato"].update(enabled=True, depth_cents=35)
                    cfg["effects"]["delay"].update(enabled=True, time_ms=48)
                    path = Path(directory) / (mode + ".json")
                    save_config(path, cfg)
                    self.assertEqual(load_config(path), cfg)

    def test_invalid_fields_preserve_input_and_file(self):
        with tempfile.TemporaryDirectory() as directory:
            path = Path(directory) / "config.json"
            valid = default_config()
            save_config(path, valid)
            original = path.read_bytes()
            invalids = []
            for field, value in (("schema_version", 2), ("schema_version", True),
                                 ("spectrum", [0] * 15), ("spectrum", [True] * 16),
                                 ("spectrum", [256] * 16), ("name", " "),
                                 ("name", "\ud800"), ("preset", 4), ("spectrum_mode", "bad")):
                cfg = copy.deepcopy(valid)
                cfg[field] = value
                invalids.append(cfg)
            cfg = copy.deepcopy(valid)
            cfg["effects"]["delay"]["time_ms"] = -1
            invalids.append(cfg)
            cfg = copy.deepcopy(valid)
            cfg["vibrato"]["enabled"] = 1
            invalids.append(cfg)
            cfg = copy.deepcopy(valid)
            cfg["unknown"] = "not silently discarded"
            invalids.append(cfg)
            for cfg in invalids:
                before = copy.deepcopy(cfg)
                with self.subTest(config=cfg):
                    with self.assertRaises(ConfigError):
                        save_config(path, cfg)
                    self.assertEqual(cfg, before)
                    self.assertEqual(path.read_bytes(), original)

    def test_bad_json_and_duplicates(self):
        with tempfile.TemporaryDirectory() as directory:
            path = Path(directory) / "bad.json"
            for data in (b"{", b"\xff", b'{"name":"a","name":"b"}', b'{"name":NaN}', b"[]", b" " * 65537,
                         b"[" * 2000 + b"0" + b"]" * 2000):
                with self.subTest(data=data[:30]):
                    path.write_bytes(data)
                    with self.assertRaises(ConfigError):
                        load_config(path)

    def test_failed_replace_preserves_old_file_and_cleans_temporary(self):
        with tempfile.TemporaryDirectory() as directory:
            path = Path(directory) / "config.json"
            save_config(path, default_config("原音色"))
            original = path.read_bytes()
            with patch("instrument_config.os.replace", side_effect=OSError("模拟替换失败")):
                with self.assertRaises(OSError):
                    save_config(path, default_config("新音色"))
            self.assertEqual(path.read_bytes(), original)
            self.assertEqual(list(Path(directory).iterdir()), [path])

    def test_validated_copy_is_independent(self):
        cfg = default_config()
        checked = validate_config(cfg)
        checked["spectrum"][0] = 0
        checked["effects"]["delay"]["enabled"] = True
        self.assertEqual(cfg["spectrum"][0], 255)
        self.assertFalse(cfg["effects"]["delay"]["enabled"])

    def test_bom_is_accepted(self):
        with tempfile.TemporaryDirectory() as directory:
            path = Path(directory) / "bom.json"
            cfg = default_config()
            path.write_bytes(b"\xef\xbb\xbf" + json.dumps(cfg).encode("utf-8"))
            self.assertEqual(load_config(path), cfg)

    def test_cli_errors_have_nonzero_exit(self):
        with tempfile.TemporaryDirectory() as directory:
            path = Path(directory) / "config.json"
            self.assertEqual(main(["new", str(path), "--mode", "hybrid"]), 0)
            self.assertEqual(main(["check", str(path)]), 0)
            path.write_text("{}", encoding="utf-8")
            self.assertEqual(main(["check", str(path)]), 1)
            self.assertEqual(main(["check", str(path) + ".missing"]), 1)


if __name__ == "__main__":
    unittest.main()
