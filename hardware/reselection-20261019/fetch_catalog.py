"""Read-only LCSC exact-part lookup. Prices are USD, not domestic CNY quotes."""
import argparse
import json
import time
from datetime import datetime, timezone
from pathlib import Path
from urllib.request import Request, urlopen


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("codes", nargs="+")
    args = parser.parse_args()
    out = Path(__file__).parent / "evidence" / "catalog"
    out.mkdir(parents=True, exist_ok=True)
    rows = []
    for code in args.codes:
        if not (code.startswith("C") and code[1:].isdigit()):
            raise ValueError("Exact C-number required: " + code)
        url = "https://wmsc.lcsc.com/ftps/wm/product/detail?productCode=" + code
        row = {"code": code, "url": url, "checked_utc": datetime.now(timezone.utc).isoformat()}
        try:
            req = Request(url, headers={"User-Agent": "Mozilla/5.0"})
            with urlopen(req, timeout=15) as response:
                raw = response.read()
            (out / (code + ".json")).write_bytes(raw)
            data = json.loads(raw)
            part = data.get("result") or {}
            row.update({"api_code": data.get("code"), "mpn": part.get("productModel"),
                        "manufacturer": part.get("brandNameEn"), "stock_lcsc": part.get("stockNumber"),
                        "package": part.get("encapStandard"), "datasheet": part.get("pdfUrl"),
                        "price_usd_tiers": [{"minimum": p.get("ladder"), "usd": p.get("usdPrice")}
                                            for p in part.get("productPriceList", [])]})
            row["status"] = "exact_detail" if part.get("productCode") == code else "identity_not_confirmed"
        except Exception as exc:
            row.update({"status": "unavailable", "error": str(exc)})
        rows.append(row)
        print(json.dumps(row, ensure_ascii=True), flush=True)
        time.sleep(0.5)
    (out / "summary.json").write_text(json.dumps(rows, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")


if __name__ == "__main__":
    main()
