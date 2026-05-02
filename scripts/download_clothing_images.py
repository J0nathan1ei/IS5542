#!/usr/bin/env python3

import argparse
import csv
import re
import ssl
import subprocess
import sys
import tempfile
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


def gender_terms(gender: str) -> tuple[str, str]:
    if gender == "Female":
        positive = "women womens for women female"
        negative = "-men -male -man -mens -boy"
    else:
        positive = "men mens for men male"
        negative = "-women -female -woman -womens -ladies -girl"
    return positive, negative


def category_hint(row: dict[str, str]) -> str:
    category = row["Category"].lower()
    if row["Gender"] == "Female":
        if "shirt" in category and "t-shirt" not in category:
            return "blouse top"
        if "trousers" in category or "pants" in category:
            return "women outfit"
    else:
        if category == "shirt":
            return "button down"
        if "trousers" in category or "pants" in category:
            return "menswear outfit"
    return ""


def prefer_product_photo(row: dict[str, str]) -> bool:
    category = row["Category"].lower()
    product_categories = [
        "shirt",
        "blouse",
        "t-shirt",
        "tee",
        "hoodie",
        "sweater",
        "cardigan",
        "polo",
        "tank",
        "top",
        "vest",
        "henley",
    ]
    return any(token in category for token in product_categories)


def build_queries(row: dict[str, str]) -> list[str]:
    positive, negative = gender_terms(row["Gender"])
    hint = category_hint(row)
    name = row["Product Name"]
    category = row["Category"]
    color = row["Color"]
    style = row["Style"].split(",")[0].strip()
    occasion = row["Occasion"].split(",")[0].strip()
    shot_type = "product photo" if prefer_product_photo(row) else "outfit"
    queries = [
        f"{positive} {color} {category} {hint} {shot_type} {negative}",
        f"{positive} {name} {shot_type} {negative}",
        f"{positive} {category} {style} {occasion} {negative}",
    ]
    return [re.sub(r"\s+", " ", q).strip() for q in queries]


def find_bing_image_urls(row: dict[str, str], limit: int = 16) -> list[str]:
    seen: set[str] = set()
    results: list[str] = []
    for query in build_queries(row):
        params = {
            "q": query,
            "qft": "+filterui:imagesize-large",
        }
        url = "https://www.bing.com/images/search?" + urllib.parse.urlencode(params)
        try:
            html = fetch_text(url)
        except urllib.error.URLError:
            continue
        matches = re.findall(r'murl&quot;:&quot;(.*?)&quot;', html)
        for match in matches:
            cleaned = match.replace("\\/", "/").replace("&amp;", "&")
            if not cleaned.startswith("http") or cleaned in seen:
                continue
            seen.add(cleaned)
            results.append(cleaned)
            if len(results) >= limit:
                return results
    return results


def expected_keywords(row: dict[str, str]) -> list[str]:
    category = row["Category"].lower()
    keywords: list[str] = []
    mapping = {
        "shirt": ["shirt", "button", "oxford", "linen", "mandarin"],
        "blouse": ["blouse", "shirt", "top"],
        "sweatshirt": ["sweatshirt", "crewneck", "pullover"],
        "hoodie": ["hoodie", "hooded"],
        "sweater": ["sweater", "knit", "jumper"],
        "cardigan": ["cardigan", "knit"],
        "t-shirt": ["t-shirt", "tee", "shirt"],
        "tank": ["tank", "top"],
        "polo": ["polo", "shirt"],
        "jacket": ["jacket", "coat", "outerwear"],
        "blazer": ["blazer", "jacket"],
        "coat": ["coat", "outerwear"],
        "vest": ["vest", "gilet"],
        "dress": ["dress"],
        "skirt": ["skirt"],
        "trousers": ["trouser", "trousers", "pants", "pant"],
        "pants": ["pants", "pant", "trousers"],
        "shorts": ["shorts", "short"],
        "jogger": ["jogger", "joggers", "pants"],
        "leggings": ["leggings", "legging"],
        "jeans": ["jeans", "denim"],
        "jumpsuit": ["jumpsuit", "romper"],
        "skort": ["skort", "skirt"],
        "bra": ["bra", "sportsbra"],
    }
    for key, values in mapping.items():
        if key in category:
            keywords.extend(values)
    if not keywords:
        keywords.extend(re.findall(r"[a-z]+", category))
    return list(dict.fromkeys(keywords))


def strict_keywords(row: dict[str, str]) -> list[str]:
    lowered = f'{row["Product Name"]} {row["Category"]}'.lower()
    must_match: list[str] = []
    for token in ["mandarin", "henley", "turtleneck", "mock", "crochet", "seersucker"]:
        if token in lowered:
            must_match.append(token)
    return must_match


def url_allowed_basic(image_url: str) -> bool:
    lowered = image_url.lower()
    blocked_domains = [
        "shutterstock",
        "depositphotos",
        "dreamstime",
        "alamy",
        "123rf",
        "whitelabel.ph",
    ]
    blocked_terms = [
        "football",
        "soccer",
        "basketball",
        "hijab",
        "wedding",
    ]
    if any(term in lowered for term in blocked_domains):
        return False
    if any(term in lowered for term in blocked_terms):
        return False
    return True


def url_matches_item(row: dict[str, str], image_url: str) -> bool:
    lowered = image_url.lower()
    if not url_allowed_basic(image_url):
        return False
    strict = strict_keywords(row)
    if strict and not any(keyword in lowered for keyword in strict):
        return False
    return any(keyword in lowered for keyword in expected_keywords(row))


def download_bytes(url: str) -> bytes | None:
    url = urllib.parse.quote(url, safe=":/?&=%#._-+")
    request = urllib.request.Request(
        url,
        headers={
            "User-Agent": "Mozilla/5.0",
            "Accept": "image/avif,image/webp,image/apng,image/*,*/*;q=0.8",
            "Referer": "https://www.bing.com/",
        },
    )
    try:
        with urllib.request.urlopen(request, timeout=30, context=SSL_CONTEXT) as response:
            content_type = response.headers.get("Content-Type", "")
            if not content_type.startswith("image/"):
                return None
            data = response.read()
            if len(data) < 30_000:
                return None
            return data
    except (urllib.error.URLError, TimeoutError, ConnectionError, ValueError):
        return None


def image_dimensions(path: Path) -> tuple[int, int] | None:
    result = subprocess.run(
        ["sips", "-g", "pixelWidth", "-g", "pixelHeight", str(path)],
        capture_output=True,
        text=True,
        check=False,
    )
    if result.returncode != 0:
        return None
    width_match = re.search(r"pixelWidth:\s+(\d+)", result.stdout)
    height_match = re.search(r"pixelHeight:\s+(\d+)", result.stdout)
    if not width_match or not height_match:
        return None
    return int(width_match.group(1)), int(height_match.group(1))


def convert_to_jpeg(src: Path, dest: Path) -> bool:
    result = subprocess.run(
        ["sips", "-s", "format", "jpeg", str(src), "--out", str(dest)],
        capture_output=True,
        text=True,
        check=False,
    )
    return result.returncode == 0 and dest.exists() and dest.stat().st_size > 20_000


def dimensions_are_large_enough(width: int, height: int) -> bool:
    return width >= 780 and height >= 780 and max(width, height) >= 900


def try_candidate_urls(row: dict[str, str], dest: Path, relaxed: bool = False) -> bool:
    for image_url in find_bing_image_urls(row):
        if relaxed:
            if not url_allowed_basic(image_url):
                continue
        else:
            if not url_matches_item(row, image_url):
                continue
        with tempfile.TemporaryDirectory() as tmp_dir:
            tmp_path = Path(tmp_dir) / "candidate.img"
            data = download_bytes(image_url)
            if not data:
                continue
            tmp_path.write_bytes(data)
            dims = image_dimensions(tmp_path)
            if not dims:
                continue
            width, height = dims
            if not dimensions_are_large_enough(width, height):
                continue
            if not convert_to_jpeg(tmp_path, dest):
                continue
            final_dims = image_dimensions(dest)
            if not final_dims:
                dest.unlink(missing_ok=True)
                continue
            final_width, final_height = final_dims
            if not dimensions_are_large_enough(final_width, final_height):
                dest.unlink(missing_ok=True)
                continue
            return True
    return False


def download_best_image(row: dict[str, str], dest: Path) -> bool:
    if try_candidate_urls(row, dest, relaxed=False):
        return True
    return try_candidate_urls(row, dest, relaxed=True)


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser()
    parser.add_argument("--start-id", type=int, default=1)
    parser.add_argument("--end-id", type=int, default=150)
    parser.add_argument("--force", action="store_true")
    return parser.parse_args()


def main() -> int:
    args = parse_args()
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
        product_id = int(row["Product ID"].strip())
        if product_id < args.start_id or product_id > args.end_id:
            continue

        product_name = row["Product Name"].strip()
        file_name = f"{product_id}.jpg"
        dest = PIC_DIR / file_name

        if args.force and dest.exists():
            dest.unlink()

        if dest.exists() and not args.force:
            row["Uri"] = f"pic/{file_name}"
            success += 1
            continue

        ok = download_best_image(row, dest)
        if not ok:
            failed.append(str(product_id))
            print(f"failed {product_id}: {product_name}")
            continue

        row["Uri"] = f"pic/{file_name}"
        print(f"downloaded {product_id}: {product_name}")
        success += 1
        time.sleep(0.2)

    for row in rows:
        product_id = int(row["Product ID"].strip())
        if args.start_id <= product_id <= args.end_id:
            row["Uri"] = f"pic/{product_id}.jpg"

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
