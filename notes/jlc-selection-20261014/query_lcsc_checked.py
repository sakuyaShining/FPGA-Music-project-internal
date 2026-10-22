"""Read-only catalog lookup with an explicit exact-MPN/C-code identity filter.

Run with Python >= 3.10. Requires the separately installed lcsc skill.
Passing this filter is catalog identity checking, not electrical qualification.
"""

import argparse
import datetime
import importlib.util
import json
from pathlib import Path
import sys


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("query")
    parser.add_argument("--skill-dir", type=Path, default=Path.home() / ".codex/skills/lcsc")
    parser.add_argument("--expected-mpn", help="Exact manufacturer part number; defaults to query")
    parser.add_argument("--output", type=Path, required=True)
    args = parser.parse_args()
    if sys.version_info < (3, 10):
        parser.error("Python >= 3.10 is required by the upstream lcsc skill")
    script = args.skill_dir / "scripts/search_lcsc.py"
    sys.path.insert(0, str(script.parent))
    spec = importlib.util.spec_from_file_location("lcsc_skill_search", script)
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    result = {
        "query": args.query,
        "expected_mpn": args.expected_mpn or args.query,
        "retrieved_at_utc": datetime.datetime.now(datetime.timezone.utc).isoformat(),
        "source": "https://jlcsearch.tscircuit.com",
        "source_kind": "community_JLCPCB_assembly_catalog",
        "currency": "USD",
        "domestic_quote_verified": False,
        "electrically_qualified": False,
        "manufacturing_release": False,
        "accepted": [],
        "rejected": [],
    }
    try:
        rows = module.search_jlcsearch(args.query, limit=20)
        expected = (args.expected_mpn or args.query).strip().upper()
        is_code = args.query.upper().startswith("C") and args.query[1:].isdigit()
        for row in rows:
            item = module.normalize_component(row)
            actual = item["lcsc_code"] if is_code and not args.expected_mpn else item["mpn"]
            if str(actual).strip().upper() == expected:
                result["accepted"].append(item)
            else:
                result["rejected"].append({"reason": "identity_mismatch", "item": item})
        result["status"] = "identity_matches_only_not_qualified" if result["accepted"] else "no_verified_identity_match"
        exit_code = 0 if result["accepted"] else 1
    except Exception as exc:
        result["status"] = "lookup_failed"
        result["error"] = f"{type(exc).__name__}: {exc}"
        exit_code = 2
    args.output.parent.mkdir(parents=True, exist_ok=True)
    args.output.write_text(json.dumps(result, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    print(json.dumps({"status": result["status"], "accepted": len(result["accepted"]),
                      "rejected": len(result["rejected"]), "output": str(args.output)}, ensure_ascii=False))
    return exit_code


if __name__ == "__main__":
    raise SystemExit(main())
