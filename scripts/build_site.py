#!/usr/bin/env python3
"""
Builds the static GitHub Pages dashboard (`dist/index.html` and `dist/data.json`)
by downloading the latest 3Y daily ICE BofA OAS series directly from FRED.

Uses only the Python standard library + curl fallback with automatic retries
so GitHub Actions handles transient FRED timeouts reliably.
"""

from __future__ import annotations

import argparse
import csv
import io
import json
import math
import random
import shutil
import subprocess
import time
import urllib.request
from datetime import date, datetime, timedelta, timezone
from pathlib import Path

FRED_CSV_URL = "https://fred.stlouisfed.org/graph/fredgraph.csv?id={series_id}&cosd={start_date}"
KST = timezone(timedelta(hours=9))
ROOT = Path(__file__).resolve().parent.parent
TEMPLATE_PATH = ROOT / "template" / "index.html"
DIST_DIR = ROOT / "dist"

HEADERS = {
    "User-Agent": (
        "Mozilla/5.0 (X11; Linux x86_64) AppleWebKit/537.36 "
        "(KHTML, like Gecko) Chrome/128.0.0.0 Safari/537.36"
    ),
    "Accept": "text/csv,text/plain,*/*;q=0.8",
    "Accept-Language": "en-US,en;q=0.9",
    "Connection": "close",
}


def download_text(url: str, max_attempts: int = 4, timeout_sec: int = 60) -> str:
    """Download URL text using curl (preferred on GitHub Actions) with urllib fallback and retries."""
    last_err: Exception | None = None
    curl_bin = shutil.which("curl")

    for attempt in range(1, max_attempts + 1):
        # 1) Try curl first (avoids Python urllib TLS/read stalls on FRED)
        if curl_bin:
            try:
                cmd = [
                    curl_bin,
                    "-fsSL",
                    "--http1.1",
                    "--connect-timeout",
                    "20",
                    "--max-time",
                    str(timeout_sec),
                    "-A",
                    HEADERS["User-Agent"],
                    "-H",
                    f"Accept: {HEADERS['Accept']}",
                    url,
                ]
                res = subprocess.run(
                    cmd,
                    capture_output=True,
                    text=True,
                    timeout=timeout_sec + 10,
                    check=True,
                )
                if res.stdout.strip():
                    return res.stdout
            except Exception as exc:
                last_err = exc
                print(f"[attempt {attempt}/{max_attempts}] curl failed for {url}: {exc}")

        # 2) Fallback to urllib
        try:
            req = urllib.request.Request(url, headers=HEADERS)
            with urllib.request.urlopen(req, timeout=timeout_sec) as resp:
                text = resp.read().decode("utf-8", errors="replace")
                if text.strip():
                    return text
        except Exception as exc:
            last_err = exc
            print(f"[attempt {attempt}/{max_attempts}] urllib failed for {url}: {exc}")

        if attempt < max_attempts:
            wait = 5 * attempt
            print(f"Retrying in {wait}s...")
            time.sleep(wait)

    raise RuntimeError(f"Failed to download {url} after {max_attempts} attempts: {last_err}")


def fetch_fred_csv(series_id: str, years: int = 3) -> list[dict[str, object]]:
    """Download a FRED CSV series and return sorted [{date, value}] rows."""
    today = date.today()
    start_dt = today - timedelta(days=366 * years + 14)
    url = FRED_CSV_URL.format(series_id=series_id, start_date=start_dt.isoformat())
    text = download_text(url)

    rows: list[dict[str, object]] = []
    reader = csv.reader(io.StringIO(text))
    for parts in reader:
        if len(parts) < 2:
            continue
        ds = parts[0].strip()
        raw_val = parts[1].strip()
        if len(ds) != 10 or ds[4] != "-" or ds[7] != "-":
            continue
        try:
            val = float(raw_val)
        except ValueError:
            continue
        if math.isfinite(val):
            rows.append({"date": ds, "value": round(val, 4)})

    rows.sort(key=lambda r: str(r["date"]))
    if not rows:
        raise RuntimeError(f"No valid observations returned for {series_id}")

    if years > 0:
        last_dt = date.fromisoformat(str(rows[-1]["date"]))
        try:
            cutoff_dt = last_dt.replace(year=last_dt.year - years)
        except ValueError:
            cutoff_dt = last_dt.replace(year=last_dt.year - years, day=28)
        cutoff_str = cutoff_dt.isoformat()
        rows = [r for r in rows if str(r["date"]) >= cutoff_str]

    return rows


def build_demo_data() -> tuple[list[dict[str, object]], list[dict[str, object]]]:
    """Generate offline test data for `--demo` verification only."""
    rng = random.Random(42)
    end = date(2026, 11, 17)
    start = date(2023, 11, 20)
    cur = start
    hy_rows: list[dict[str, object]] = []
    ig_rows: list[dict[str, object]] = []
    hy_v, ig_v = 3.50, 1.05
    while cur <= end:
        if cur.weekday() < 5:
            hy_v = min(4.65, max(2.60, hy_v + rng.uniform(-0.06, 0.06)))
            ig_v = min(1.25, max(0.72, ig_v + rng.uniform(-0.015, 0.015)))
            hy_rows.append({"date": cur.isoformat(), "value": round(hy_v, 3)})
            ig_rows.append({"date": cur.isoformat(), "value": round(ig_v, 3)})
        cur += timedelta(days=1)
    return hy_rows, ig_rows


def build_site(demo: bool = False) -> None:
    if demo:
        hy_rows, ig_rows = build_demo_data()
        source_mode = "demo"
    else:
        print("Fetching BAMLH0A0HYM2 (HY OAS) and BAMLC0A0CM (IG OAS) from FRED...")
        hy_rows = fetch_fred_csv("BAMLH0A0HYM2", years=3)
        ig_rows = fetch_fred_csv("BAMLC0A0CM", years=3)
        source_mode = "fred-live"

    now_kst = datetime.now(KST)
    payload = {
        "mode": source_mode,
        "updatedAtKst": now_kst.strftime("%Y-%m-%d %H:%M KST"),
        "hy": hy_rows,
        "ig": ig_rows,
    }

    DIST_DIR.mkdir(parents=True, exist_ok=True)
    data_json_path = DIST_DIR / "data.json"
    data_json_path.write_text(
        json.dumps(payload, ensure_ascii=False, separators=(",", ":")),
        encoding="utf-8",
    )

    template_html = TEMPLATE_PATH.read_text(encoding="utf-8")
    placeholder = "__FRED_DATA_PAYLOAD__"
    if placeholder not in template_html:
        raise RuntimeError(f"Template missing {placeholder} marker")

    safe_json = json.dumps(payload, ensure_ascii=False, separators=(",", ":")).replace("</", "<\\/")
    output_html = template_html.replace(placeholder, safe_json)

    index_path = DIST_DIR / "index.html"
    index_path.write_text(output_html, encoding="utf-8")
    print(
        f"Built {index_path} ({len(hy_rows)} HY rows, {len(ig_rows)} IG rows, "
        f"latest HY={hy_rows[-1]['date']}, updated={payload['updatedAtKst']})"
    )


def main() -> None:
    parser = argparse.ArgumentParser(description="Build auto-updating Credit Spread Pages site.")
    parser.add_argument("--demo", action="store_true", help="Build using offline demo data")
    args = parser.parse_args()
    build_site(demo=args.demo)


if __name__ == "__main__":
    main()
