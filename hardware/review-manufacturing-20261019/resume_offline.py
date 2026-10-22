"""Audit recovered native copper and plan audio routes without an EDA session.

The output is a proposal bound to the exact saved PCB and API capture. It does
not edit the native project, run native DRC, or authorize manufacturing.
Run with a Python environment containing numpy, Pillow and Shapely.
"""
import argparse
from collections import Counter
import hashlib
import json
import math
from pathlib import Path
import sys
import time


def digest(path):
    return hashlib.sha256(path.read_bytes()).hexdigest()


def read_native(path):
    """Replay native records, including deletion tombstones, in file order."""
    live = {}
    active = False
    for line in path.read_text(encoding="utf-8").splitlines():
        if "||" not in line:
            continue
        header, raw = line.split("||", 1)
        if not header.startswith("{"):
            continue
        header = json.loads(header)
        raw = raw.rstrip("|")
        body = json.loads(raw) if raw.strip() else None
        if header["type"] == "DOCHEAD":
            active = body is not None and body.get("docType") == "PCB"
        if active:
            live[(header["type"], header.get("id"))] = body
    return {key: value for key, value in live.items() if value is not None}


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--deps", type=Path)
    parser.add_argument("--plan-audio", action="store_true")
    parser.add_argument("--grid-step", type=float, default=.05,
                        help="Search grid in mm; continuous geometry is checked afterwards")
    parser.add_argument("--pcb", type=Path, default=Path(
        "C:/Users/Sakuya/Documents/LCEDA-Pro/projects/"
        "FPGA-Music-Dualscreen-Review-20261019/pcb/PCB1.epcb2"))
    parser.add_argument("--output", type=Path)
    args = parser.parse_args()
    if args.deps:
        sys.path.insert(0, str(args.deps.resolve()))
    # Import the available binary package before the legacy router adds its
    # historical dependency directory, which may contain incomplete recovery.
    import shapely
    import grid_route as grid
    import reserve_escape as escape
    from physical_geometry import actual_pad, connected_subset

    root = Path(__file__).resolve().parent
    output = (args.output or root / "offline-resume-20261020").resolve()
    output.mkdir(parents=True, exist_ok=True)
    source_path = root / "grid-source-core-fanouts.json"
    source = json.loads(source_path.read_text(encoding="utf-8"))
    native = read_native(args.pcb)
    native_lines = {identity: value for (kind, identity), value in native.items()
                    if kind == "LINE" and value.get("layerId") in [1, 2]}
    native_vias = {identity: value for (kind, identity), value in native.items()
                   if kind == "VIA"}
    differences = []
    native_only_short_lines = []
    fields = {"lines": {"net": "netName", "layer": "layerId", "x1": "startX",
                         "y1": "startY", "x2": "endX", "y2": "endY", "width": "width"},
              "vias": {"net": "netName", "x": "centerX", "y": "centerY",
                        "diameter": "viaDiameter", "hole": "holeDiameter"}}
    for kind, actual in [("lines", native_lines), ("vias", native_vias)]:
        expected = {p["id"]: p for p in source[kind]}
        missing = expected.keys() - actual.keys()
        extra = actual.keys() - expected.keys()
        if kind == "lines":
            for identity in sorted(extra):
                value = actual[identity]
                length = math.hypot(value["endX"] - value["startX"],
                                    value["endY"] - value["startY"]) * .0254
                if length <= .003:
                    native_only_short_lines.append({"id": identity, **{
                        field: value[native_field] for field, native_field in fields[kind].items()}})
                else:
                    differences.append({"kind": kind, "unexpected_extra_id": identity})
        elif extra:
            differences.append({"kind": kind, "unexpected_extra_ids": sorted(extra)})
        if missing:
            differences.append({"kind": kind, "missing_ids": sorted(missing)})
        for identity in expected.keys() & actual.keys():
            for field, native_field in fields[kind].items():
                a, b = expected[identity][field], actual[identity][native_field]
                equal = abs(a - b) < 0.00011 if isinstance(a, (int, float)) else a == b
                if not equal:
                    differences.append({"kind": kind, "id": identity, "field": field,
                                        "capture": a, "native": b})
    drc = json.loads((root / "pcb-drc.json").read_text(encoding="utf-8"))
    report = {"pcb_file": str(args.pcb.resolve()), "pcb_sha256": digest(args.pcb),
              "capture_file": str(source_path), "capture_sha256": digest(source_path),
              "capture_copper_matches_saved_native": not differences and not native_only_short_lines,
              "capture_is_subset_of_saved_native": not differences,
              "native_only_short_lines": native_only_short_lines,
              "differences": differences,
              "native_live_counts": dict(Counter(k[0] for k in native)),
              "signal_copper_counts": {"lines": len(native_lines), "vias": len(native_vias)},
              "historical_drc_counts": {c["name"]: c.get("count", 0) for c in drc},
              "historical_drc_is_fresh": False,
              "pending_nets_from_historical_drc": [n["name"] for c in drc
                  if c["name"] == "Connection Error" for n in c["list"]],
              "shapely_version": shapely.__version__, "native_modified": False,
              "manufacturing_release": False}
    (output / "recovery-audit.json").write_text(json.dumps(report, indent=2), encoding="utf-8")
    print(json.dumps({k: v for k, v in report.items()
                      if k not in ["native_only_short_lines", "pending_nets_from_historical_drc"]}, indent=2), flush=True)
    if differences:
        raise RuntimeError("Saved copper differs from API capture; recapture before planning")
    # The API capture omits native sub-3-micron line fragments. Preserve all of
    # them as real obstacles in a separate source, without changing old evidence.
    source = {**source, "lines": source["lines"] + native_only_short_lines}
    source_path = output / "routing-source.json"
    source_path.write_text(json.dumps(source, indent=2), encoding="utf-8")
    if not args.plan_audio:
        return

    nets = ["I2S_BCK", "I2S_DIN", "I2S_LRCK", "DAC_XSMT"]
    working = {**source, "pads": [dict(p) for p in source["pads"]],
               "lines": [p for p in source["lines"] if p["net"] not in nets],
               "vias": [p for p in source["vias"] if p["net"] not in nets]}
    grid.pad_shape = actual_pad
    grid.GAP = .17
    if not .025 <= args.grid_step <= .1:
        raise ValueError("Grid step must be between .025 and .1 mm")
    grid.GRID = escape.GRID = args.grid_step
    # Pillow rasterizes polygon edges onto integer pixels. Inflate obstacles by
    # a half-pixel diagonal so coarse searches cannot mistake the pixel boundary
    # for adequate continuous clearance. The exact geometry check still decides.
    original_raster = grid.raster
    def conservative_raster(geometries, bounds, inflate, shape):
        return original_raster(geometries, bounds,
                               inflate + args.grid_step / math.sqrt(2), shape)
    grid.raster = escape.raster = conservative_raster
    escape.pad_shape = actual_pad
    escape.GAP = .17
    first = escape.new_mux_fanouts(working, nets, refs={"U12"})
    second = escape.grid_mux_fanouts(working, nets, refs={"U12"})
    print("AUDIO FANOUTS", first["new_fanouts"], second["new_fanouts"], flush=True)
    routes, failures = [], []
    # Save the complete evolving proposal after each net. All fanouts must be
    # included in continuity checks; virtual anchor pads are never exported.
    def save():
        proposal = {"nets": nets, "routes": routes, "failed_planning": failures,
                    "lines": [p for p in working["lines"] if p["net"] in nets],
                    "vias": [p for p in working["vias"] if p["net"] in nets],
                    "source_file": str(source_path), "source_sha256": digest(source_path),
                    "native_pcb_sha256": report["pcb_sha256"],
                    "search_grid_mm": args.grid_step,
                    "native_imported": False, "requires_independent_geometry_audit": True,
                    "requires_native_recapture_and_drc": True, "manufacturing_release": False}
        (output / "audio-route-proposal.json").write_text(json.dumps(proposal, indent=2), encoding="utf-8")
    save()
    for net in nets:
        started = time.monotonic()
        try:
            route = grid.plan(working, net)
            lines = [p for p in working["lines"] if p["net"] == net] + route["lines"]
            vias = [p for p in working["vias"] if p["net"] == net] + route["vias"]
            continuity = connected_subset([p for p in source["pads"] if p["net"] == net], lines, vias)
            if not continuity["complete"]:
                raise RuntimeError("Independent real-pad continuity failed: " + str(continuity))
            working["lines"] += route["lines"]
            working["vias"] += route["vias"]
            routes.append(route)
            print("PLANNED", net, len(lines), len(vias), flush=True)
        except Exception as error:
            failures.append({"net": net, "error": str(error)})
            print("PENDING", net, type(error).__name__, str(error), flush=True)
        save()
        print("ELAPSED", net, round(time.monotonic() - started, 1), flush=True)
    assert digest(args.pcb) == report["pcb_sha256"], "PCB changed while offline planning"


if __name__ == "__main__":
    main()
