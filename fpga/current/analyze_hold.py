"""Expand every HOLD block of a build's board.timing_paths, plus the TNS summary.

Read-only: parses impl/pnr/board.timing_paths and impl/pnr/board_tr_content.html.
Never touches the bitstream, never programs hardware.
"""
import json
import re
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parent


def blocks(path):
    lines = [l.rstrip("\n") for l in path.read_text(encoding="utf-8", errors="replace").splitlines()]
    out = []
    i = 0
    while i < len(lines):
        if lines[i].strip() == "=====" and i + 1 < len(lines) and lines[i + 1].strip() in ("SETUP", "HOLD"):
            kind = lines[i + 1].strip()
            body = []
            k = i + 2
            while k < len(lines) and lines[k].strip() != "=====":
                body.append(lines[k].strip())
                k += 1
            out.append((kind, body))
            i = k
            continue
        i += 1
    return out


def tns_summary(html_path):
    text = re.sub(r"<[^>]+>", " ", html_path.read_text(encoding="utf-8", errors="replace"))
    text = re.sub(r"\s+", " ", text)
    out = {}
    m = re.search(r"Numbers of Setup Violated Endpoints\s+(\d+)", text)
    if m:
        out["setup_violated_endpoints"] = int(m.group(1))
    m = re.search(r"Numbers of Hold Violated Endpoints\s+(\d+)", text)
    if m:
        out["hold_violated_endpoints"] = int(m.group(1))
    m = re.search(r"Constraint\s+Actual Fmax\s+(.*?)Entity", text)
    if m:
        out["fmax"] = re.findall(r"(\d+\.\d+)\(MHz\)", m.group(1))
    # "core_clk Setup -2.308 5" triples
    rows = re.findall(r"([\w.]+) (Setup|Hold) (-?\d+\.\d+) (\d+)", text)
    out["tns"] = [
        {"clock": c, "type": t, "tns_ns": float(v), "endpoints": int(n)}
        for c, t, v, n in rows
        if float(v) != 0.0
    ]
    return out


def main():
    label = sys.argv[1]
    d = ROOT / label / "impl" / "pnr"
    tp = d / "board.timing_paths"
    html = d / "board_tr_content.html"
    if not tp.exists():
        raise SystemExit("no timing paths at " + str(tp))

    paths = []
    for kind, body in blocks(tp):
        if kind != "HOLD":
            continue
        nodes = [x for x in body if not re.fullmatch(r"-?\d+\.\d+", x)]
        nums = [float(x) for x in body if re.fullmatch(r"-?\d+\.\d+", x)]
        paths.append(
            {
                "slack_ns": float(body[0]),
                # dump order is: slack, data arrival at dest, required (clock+hold),
                # launch clock, data at source pin, data at dest pin.
                "arrival_ns": nums[1] if len(nums) > 1 else None,
                "required_ns": nums[2] if len(nums) > 2 else None,
                "source": nodes[0] if nodes else None,
                "dest": nodes[1] if len(nodes) > 1 else None,
                "launch_clock_ns": nums[3] if len(nums) > 3 else None,
                "data_at_source_ns": nums[4] if len(nums) > 4 else None,
                "data_at_dest_ns": nums[5] if len(nums) > 5 else None,
            }
        )
    paths.sort(key=lambda p: p["slack_ns"])

    result = {
        "label": label,
        "hold_paths_reported": len(paths),
        "hold_paths": paths,
        "violating": [p for p in paths if p["slack_ns"] < 0],
        "summary": tns_summary(html) if html.exists() else {},
        "bench_gate": False,
        "hardware_programmed": False,
    }
    out = ROOT / "evidence" / ("hold-" + label + ".json")
    out.parent.mkdir(exist_ok=True)
    out.write_text(json.dumps(result, indent=2), encoding="utf-8")

    print(json.dumps({k: v for k, v in result.items() if k != "hold_paths"}, indent=2)[:4000])
    print()
    print("%8s %8s  %-52s -> %s" % ("slack", "data@src", "source", "dest"))
    for p in paths:
        print(
            "%8.3f %8s  %-52s -> %s"
            % (p["slack_ns"], p["data_at_source_ns"], p["source"], p["dest"])
        )
    print()
    print("written:", out)


if __name__ == "__main__":
    main()
