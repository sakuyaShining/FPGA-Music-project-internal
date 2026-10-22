"""Build a review BOM from immutable WorkBuddy input; blank costs stay unknown."""
import csv
import hashlib
import json
from decimal import Decimal, ROUND_HALF_UP
from pathlib import Path

ROOT = Path(__file__).parent
SOURCE = Path("D:/FPGA-Project/wb-worktree-20261019/FPGA-Music-project/docs/02-技术方案/88-硬件选型BOM表-2026-10-19.csv")


def main():
    source_bytes = SOURCE.read_bytes()
    source_hash = hashlib.sha256(source_bytes).hexdigest()
    expected = "29b3a00efbc637158d487d39d6ef2e5d504a969fe096c75780a3049e5bd9c95e"
    if source_hash != expected:
        raise RuntimeError("WorkBuddy BOM changed; review it before regenerating")
    with SOURCE.open(encoding="utf-8-sig", newline="") as stream:
        old = list(csv.DictReader(stream))
    catalog_file = ROOT / "evidence/catalog/summary.json"
    catalog = {row["code"]: row for row in json.loads(catalog_file.read_text(encoding="utf-8"))}
    rows = []
    for item in old:
        row = {"code": item["料号"], "mpn": item["型号"], "purchase_quantity": item["数量"],
               "historical_unit_cny": item["单价CNY"], "historical_line_cny": item["小计CNY"],
               "historical_source": item["价格来源"], "current_stock_lcsc": "", "current_usd_tiers": "",
               "review_status": "engineering_review_pending", "notes": item["备注"]}
        if row["code"] == "C179326":
            row.update({"historical_unit_cny": "2.89", "historical_line_cny": "17.34",
                        "historical_source": "WorkBuddy 1+ tier for six units; not fresh CNY quote"})
        if row["code"] in catalog:
            c = catalog[row["code"]]
            row["current_stock_lcsc"] = c.get("stock_lcsc", "")
            row["current_usd_tiers"] = json.dumps(c.get("price_usd_tiers", []), separators=(",", ":"))
            row["notes"] += "; exact supplier MPN checked; LCSC USD is not domestic CNY"
        if row["mpn"] == "ER-TFTM070-5V4":
            row["review_status"] = "hold_exact_CTP_SPI_configuration_and_delivered_quote"
            row["notes"] += "; base display price excludes selectable CTP; require MISO"
        if row["code"] == "C2841426":
            row["review_status"] = "hold_actual_TECH_PUBLIC_datasheet_and_sensor_noise_test"
        if row["code"] == "C370986":
            row["review_status"] = "superseded_encoder_source_mismatch"
            row["notes"] = ("Historical WorkBuddy line only. C370986 supplier PDF actually references EC11E15244G1. "
                            "ALPS confirms EC11E15244B2/C470754 HAS a push switch; the old rejection was incorrect. "
                            "Current native review uses C470754; see ../review-manufacturing-20261019/README.md.")
        rows.append(row)
    additions = [
        ("C503437", "74LVC1G157GV,125", "5", "dual-screen optional return mux; one used, first USD tier minimum5; lifecycle/alternative review pending"),
        ("TBD", "LCDWIKI MSP2401 ILI9341 320x240 module", "1", "dual-screen preferred; October17 inventory says no screen on hand; exact price, view angle and module pinout pending"),
        ("TBD", "3.3V DAC supply/filter network", "1 set", "existing PCM5122 perimeter estimate not a confirmed supply tree; avoid double-counting after schematic"),
        ("TBD", "display FFC/header and audio interconnects", "1 set", "exact module revision dictates connector and cable; verify what the module includes"),
        ("TBD", "5V power entry and distribution", "1 set if missing", "5V3A historic availability needs confirmation; screen supply not from FPGA GPIO"),
    ]
    for code, mpn, qty, note in additions:
        c = catalog.get(code, {})
        rows.append({"code": code, "mpn": mpn, "purchase_quantity": qty, "historical_unit_cny": "",
                     "historical_line_cny": "", "historical_source": "not_quoted",
                     "current_stock_lcsc": c.get("stock_lcsc", ""),
                     "current_usd_tiers": json.dumps(c.get("price_usd_tiers", []), separators=(",", ":")) if c else "",
                     "review_status": "hold_candidate_or_quote_pending", "notes": note})
    out = ROOT / "bom-reviewed.csv"
    with out.open("w", encoding="utf-8-sig", newline="") as stream:
        writer = csv.DictWriter(stream, fieldnames=list(rows[0]))
        writer.writeheader()
        writer.writerows(rows)
    total = sum((Decimal(row["historical_line_cny"]) for row in rows if row["historical_line_cny"]), Decimal(0))
    result = {"source_sha256": source_hash, "rows": len(rows), "priced_historical_rows": len(old),
              "same_scope_historical_model_cny": str(total), "unknown_new_rows": len(additions),
              "complete_quote": False, "not_order_ready": True}
    assert total == Decimal("652.76")
    (ROOT / "evidence/bom-check.json").write_text(json.dumps(result, indent=2) + "\n", encoding="utf-8")
    print(json.dumps(result))


if __name__ == "__main__":
    main()
