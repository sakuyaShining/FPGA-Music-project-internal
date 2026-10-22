"""Validate manifest completeness against the actual Gowin project, then check blob hashes."""
import argparse
from pathlib import Path
import re
import subprocess
import xml.etree.ElementTree as ET


def main():
    p = argparse.ArgumentParser()
    p.add_argument("--root", type=Path, default=Path(__file__).resolve().parents[2])
    p.add_argument("--doc", type=Path)
    args = p.parse_args()
    root = args.root.resolve()
    doc = args.doc or root / "docs/02-技术方案/34-当前版本规格-基线v1.md"
    project = root / "src/gowin/tdm_synth/tdm_synth.gprj"
    text = doc.read_text(encoding="utf-8-sig")
    rows = re.findall(r"\|\s*`(src/rtl/[\w_]+\.v)`\s*\|\s*`([0-9a-f]{12})`\s*\|", text)
    tables = re.findall(r"`([\w_]+\.hex)\s+([0-9a-f]{12})`", text)
    required_rtl = {(project.parent / f.attrib["path"]).resolve().relative_to(root).as_posix()
                    for f in ET.parse(project).findall(".//File")
                    if f.attrib.get("type") == "file.verilog" and f.attrib.get("enable", "1") == "1"}
    required_tables = {"sine256.hex", "note_inc.hex", "preset_part.hex", "recip_inc.hex", "vel_wtab.hex", "tilt_wtab.hex"}
    errors = []
    for title, entries, required in (("RTL", rows, required_rtl), ("tables", tables, required_tables)):
        names = [name for name, _ in entries]
        if len(names) != len(set(names)):
            errors.append(title + ": duplicate entries")
        for missing in sorted(required - set(names)):
            errors.append(title + ": missing " + missing)
    for name, want in rows + [("src/gowin/tdm_synth/" + n, h) for n, h in tables]:
        result = subprocess.run(["git", "hash-object", str(root / name)], capture_output=True, text=True)
        if result.returncode != 0 or result.stdout.strip()[:12] != want:
            errors.append("hash mismatch: " + name)
    for error in errors:
        print("FAIL", error)
    print("RESULT source_manifest=" + ("FAIL" if errors else "PASS"))
    return int(bool(errors))


if __name__ == "__main__":
    raise SystemExit(main())
