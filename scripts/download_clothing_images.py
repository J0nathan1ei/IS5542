#!/usr/bin/env python3

import csv
import re
import ssl
import sys
import time
import urllib.error
import urllib.parse
import urllib.request
from pathlib import Path


ROOT = Path("/Users/jona/Dev/CityU Maison Bot")
CSV_PATH = ROOT / "clothing_rag_dataset.csv"
PIC_DIR = ROOT / "pic"
SSL_CONTEXT = ssl._create_unverified_context()

def fetch_text(url: str) -> str:
    request = urllib.request.Request(
        url,
        headers={
            "User-Agent": "Mozilla/5.0",
            "Accept": "text/html,application/xhtml+xml,application/xml;q=0.9,*/*;q=0.8",
        },
    )
    with urllib.request.urlopen(request, timeout=30, context=SSL_CONTEXT) as response:
        return response.read().decode("utf-8", errors="ignore")


def find_bing_image_urls(row: dict[str, str], limit: int = 8) -> list[str]:
    primary_queries = [
        f'{row["Product Name"]} clothing',
        f'{row["Color"]} {row["Category"]} fashion',
        f'{row["Gender"]} {row["Category"]} outfit',
    ]
    seen: set[str] = set()
    results: list[str] = []
    for query in primary_queries:
        encoded = urllib.parse.urlencode({"q": query})
        url = f"https://www.bing.com/images/search?{encoded}"
        try:
            html = fetch_text(url)
        except urllib.error.URLError:
            continue
        matches = re.findall(r'murl&quot;:&quot;(.*?)&quot;', html)
        for match in matches:
            cleaned = match.replace("\\/", "/").replace("&amp;", "&")
            if cleaned in seen:
                continue
            seen.add(cleaned)
            if cleaned.startswith("http"):
                results.append(cleaned)
                if len(results) >= limit:
                    return results
    return results


def download_image(url: str, dest: Path) -> bool:
    request = urllib.request.Request(
        url,
        headers={
            "User-Agent": "Mozilla/5.0",
            "Accept": "image/avif,image/webp,image/apng,image/*,*/*;q=0.8",
        },
    )
    try:
        with urllib.request.urlopen(request, timeout=30, context=SSL_CONTEXT) as response:
            content_type = response.headers.get("Content-Type", "")
            if not content_type.startswith("image/"):
                return False
            data = response.read()
        dest.write_bytes(data)
        return True
    except (urllib.error.URLError, TimeoutError, ConnectionError):
        return False


def main() -> int:
    PIC_DIR.mkdir(exist_ok=True)

    with CSV_PATH.open(newline="", encoding="utf-8") as f:
        reader = csv.DictReader(f)
        fieldnames = reader.fieldnames
        if not fieldnames:
            raise RuntimeError("CSV header is missing.")
        rows = list(reader)

    if "Uri" not in fieldnames:
        fieldnames.append("Uri")

    success = 0
    failed: list[str] = []

    for row in rows:
        product_id = row["Product ID"].strip()
        product_name = row["Product Name"].strip()
        file_name = f"{product_id}.jpg"
        dest = PIC_DIR / file_name

        if row.get("Uri", "").strip() and dest.exists():
            success += 1
            continue

        if not dest.exists() or not row.get("Uri", "").strip():
            ok = False
            for image_url in find_bing_image_urls(row):
                if download_image(image_url, dest):
                    ok = True
                    break
            if not ok:
                failed.append(product_id)
                print(f"failed {product_id}: {product_name}")
                continue
            print(f"downloaded {product_id}: {product_name}")
            time.sleep(0.2)

        row["Uri"] = f"pic/{file_name}"
        success += 1

    with CSV_PATH.open("w", newline="", encoding="utf-8") as f:
        writer = csv.DictWriter(f, fieldnames=fieldnames)
        writer.writeheader()
        writer.writerows(rows)

    print(f"downloaded={success}")
    if failed:
        print("failed=" + ",".join(failed))
        return 1
    return 0


if __name__ == "__main__":
    sys.exit(main())
