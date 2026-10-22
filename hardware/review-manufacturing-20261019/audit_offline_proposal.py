"""Independently check proposed copper, including all real-pad connections."""
import argparse
import hashlib
import json
from pathlib import Path
import sys


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("proposal", type=Path)
    parser.add_argument("--deps", type=Path, required=True)
    args = parser.parse_args()
    sys.path.insert(0, str(args.deps.resolve()))
    import shapely
    import grid_route as grid
    from shapely.geometry import Point, LineString
    from shapely.ops import unary_union
    from physical_geometry import actual_pad, connected_subset

    proposal = json.loads(args.proposal.read_text(encoding="utf-8"))
    source_path = Path(proposal["source_file"])
    if not source_path.is_absolute():
        source_path = source_path.resolve() if source_path.exists() else Path(__file__).resolve().parent / source_path
    assert hashlib.sha256(source_path.read_bytes()).hexdigest() == proposal["source_sha256"]
    source = json.loads(source_path.read_text(encoding="utf-8"))
    nets = set(proposal["nets"])
    assert all(p["net"] in nets for p in proposal["lines"] + proposal["vias"])
    combined = {**source,
                "lines": [p for p in source["lines"] if p["net"] not in nets] + proposal["lines"],
                "vias": [p for p in source["vias"] if p["net"] not in nets] + proposal["vias"]}
    grid.pad_shape = actual_pad
    violations, continuity, gaps = [], {}, {}
    for net in sorted(nets):
        lines = [p for p in proposal["lines"] if p["net"] == net]
        vias = [p for p in proposal["vias"] if p["net"] == net]
        result = connected_subset([p for p in source["pads"] if p["net"] == net], lines, vias)
        continuity[net] = {k: v for k, v in result.items() if k not in ["lines", "vias"]}
        foreign, pads, keepouts = grid.geometries(combined, net)
        copper = {layer: unary_union(foreign[layer]) for layer in [1, 2]}
        both, ko, allpads = unary_union(foreign[1] + foreign[2]), unary_union(keepouts), unary_union(pads)
        minimum = 999.
        for index, p in enumerate(lines):
            shape = LineString([(p["x1"] * grid.MM, p["y1"] * grid.MM),
                                (p["x2"] * grid.MM, p["y2"] * grid.MM)])
            radius = p["width"] * grid.MM / 2
            gap = shape.distance(copper[p["layer"]]) - radius
            minimum = min(minimum, gap)
            if gap < .158 or p["width"] < 5.9999 or shape.distance(ko) < radius + .15:
                violations.append({"net": net, "kind": "line", "index": index,
                                   "gap_mm": gap, "width_mil": p["width"]})
        for index, p in enumerate(vias):
            center = Point(p["x"] * grid.MM, p["y"] * grid.MM)
            radius = p["diameter"] * grid.MM / 2
            gap = center.distance(both) - radius
            minimum = min(minimum, gap)
            if (gap < .158 or p["hole"] < 11.9999 or p["diameter"] < 23.9999
                    or center.distance(ko) < radius + .15
                    or center.distance(allpads) < p["hole"] * grid.MM / 2 + .25):
                violations.append({"net": net, "kind": "via", "index": index, "gap_mm": gap})
        gaps[net] = minimum
    # Check drill separation independently of the raster planner, including
    # holes on the same net. Existing pairs are outside this proposal's scope.
    old_vias = [p for p in source["vias"] if p["net"] not in nets]
    all_vias = old_vias + proposal["vias"]
    for i in range(len(old_vias), len(all_vias)):
        a = all_vias[i]
        for j in range(i):
            b = all_vias[j]
            distance = ((a["x"] - b["x"]) ** 2 + (a["y"] - b["y"]) ** 2) ** .5 * grid.MM
            gap = distance - (a["hole"] + b["hole"]) * grid.MM / 2
            if gap < .3499:
                violations.append({"kind": "drill_spacing", "proposal_via": i-len(old_vias),
                                   "other_via": j, "gap_mm": gap})
    complete = all(v["complete"] for v in continuity.values())
    report = {"proposal_sha256": hashlib.sha256(args.proposal.read_bytes()).hexdigest(),
              "source_sha256": proposal["source_sha256"], "continuity": continuity,
              "minimum_copper_gaps_mm": gaps, "violations": violations,
              "offline_geometry_pass": complete and not violations,
              "native_imported": False, "native_drc_pass": False,
              "requires_native_recapture_and_drc": True, "manufacturing_release": False}
    target = args.proposal.with_name("audio-route-geometry-audit.json")
    target.write_text(json.dumps(report, indent=2), encoding="utf-8")
    print(json.dumps(report, indent=2), flush=True)


if __name__ == "__main__":
    main()
