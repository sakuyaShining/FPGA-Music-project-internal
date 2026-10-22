"""Download only from the LCEDA official download page and its HTTPS CDN links."""

import argparse
from html.parser import HTMLParser
import json
from pathlib import Path
import urllib.parse
import urllib.request


class Links(HTMLParser):
    def __init__(self):
        super().__init__()
        self.links = []

    def handle_starttag(self, tag, attrs):
        if tag == "a":
            value = dict(attrs).get("href", "")
            if value:
                self.links.append(value)


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--download-dir", type=Path)
    args = parser.parse_args()
    page_url = "https://lceda.cn/page/download"
    with urllib.request.urlopen(page_url, timeout=25) as response:
        page = response.read().decode("utf-8")
    links = Links()
    links.feed(page)
    matches = []
    for href in links.links:
        url = urllib.parse.urljoin(page_url, href)
        parts = urllib.parse.urlparse(url)
        name = Path(parts.path).name
        if (parts.scheme == "https" and parts.hostname in ("image.lceda.cn", "lceda.cn")
                and name.startswith("lceda-pro-windows-x64-") and name.endswith(".exe")):
            if url not in matches:
                matches.append(url)
    print(json.dumps({"page": page_url, "installers": matches}, ensure_ascii=False), flush=True)
    if not args.download_dir:
        return
    if len(matches) != 1:
        raise SystemExit("Expected exactly one official Windows x64 professional installer")
    url = matches[0]
    destination = args.download_dir / Path(urllib.parse.urlparse(url).path).name
    if destination.exists():
        raise SystemExit("Destination already exists; verify the existing file before retrying")
    args.download_dir.mkdir(parents=True, exist_ok=True)
    partial = destination.with_suffix(".exe.partial")
    with urllib.request.urlopen(url, timeout=30) as response:
        final_url = urllib.parse.urlparse(response.geturl())
        if final_url.scheme != "https" or final_url.hostname not in ("image.lceda.cn", "lceda.cn"):
            raise SystemExit("Unexpected redirect outside official HTTPS download hosts")
        total = int(response.headers.get("Content-Length", "0"))
        print(json.dumps({"url": response.geturl(), "bytes_expected": total, "destination": str(destination)}), flush=True)
        count = 0
        next_report = 32 * 1024 * 1024
        with partial.open("wb") as output:
            while True:
                block = response.read(1024 * 1024)
                if not block:
                    break
                output.write(block)
                count += len(block)
                if count >= next_report:
                    print(json.dumps({"bytes_downloaded": count, "bytes_expected": total}), flush=True)
                    next_report += 32 * 1024 * 1024
    if total and count != total:
        raise SystemExit("Download size mismatch; installer not finalized")
    partial.rename(destination)
    print(json.dumps({"complete": str(destination), "bytes": count}), flush=True)


if __name__ == "__main__":
    main()
