#!/usr/bin/env python3
"""Generate a static Copart make/model catalog using Copart keywords and NHTSA vPIC."""

from __future__ import annotations

import argparse
import concurrent.futures
import json
import sys
import time
import urllib.parse
import urllib.request
from datetime import datetime, timezone
from json import JSONDecodeError
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
BACKEND_SRC = ROOT / "backend" / "src"
if str(BACKEND_SRC) not in sys.path:
    sys.path.insert(0, str(BACKEND_SRC))


from cartrap.modules.search.catalog_builder import (  # noqa: E402
    build_catalog,
    build_official_model_index,
    extract_catalog_candidates,
    load_keyword_payload,
)


VPIC_ENDPOINT = "https://vpic.nhtsa.dot.gov/api/vehicles/GetModelsForMake/{make}?format=json"


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument(
        "--keywords",
        default=str(ROOT / "111" / "mcs" / "v2" / "public" / "data" / "search" / "keywords"),
        help="Path to the Copart keywords response payload.",
    )
    parser.add_argument(
        "--output",
        default=str(ROOT / "backend" / "src" / "cartrap" / "modules" / "search" / "data" / "copart_make_model_catalog.json"),
        help="Output path for the generated catalog.",
    )
    parser.add_argument(
        "--overrides",
        default=str(ROOT / "backend" / "src" / "cartrap" / "modules" / "search" / "data" / "copart_make_model_overrides.json"),
        help="Optional JSON file with manual model_slug -> make_slug overrides.",
    )
    return parser.parse_args()


def fetch_models_for_make(make_name: str, retries: int = 3) -> list[str]:
    encoded_make = urllib.parse.quote(make_name)
    url = VPIC_ENDPOINT.format(make=encoded_make)
    last_error: Exception | None = None
    for attempt in range(retries):
        try:
            with urllib.request.urlopen(url, timeout=20) as response:
                payload = json.load(response)
            results = payload.get("Results") or []
            return sorted({str(item.get("Model_Name")).strip() for item in results if item.get("Model_Name")})
        except (OSError, ValueError, JSONDecodeError) as exc:
            last_error = exc
            if attempt == retries - 1:
                raise
            time.sleep(0.5 * (attempt + 1))
    raise RuntimeError(f"Failed to fetch models for {make_name}: {last_error}")


def main() -> int:
    args = parse_args()
    keywords_path = Path(args.keywords).resolve()
    output_path = Path(args.output).resolve()
    overrides_path = Path(args.overrides).resolve()

    payload = load_keyword_payload(keywords_path)
    candidates = extract_catalog_candidates(payload)
    manual_overrides = {}
    if overrides_path.exists():
        manual_overrides = json.loads(overrides_path.read_text())

    models_by_make: dict[str, list[str]] = {}
    make_names = {make["slug"]: make["name"] for make in candidates["makes"]}
    with concurrent.futures.ThreadPoolExecutor(max_workers=4) as executor:
        future_map = {
            executor.submit(fetch_models_for_make, make["name"]): make
            for make in candidates["makes"]
        }
        for future in concurrent.futures.as_completed(future_map):
            make = future_map[future]
            try:
                models_by_make[make["slug"]] = future.result()
            except (OSError, ValueError, JSONDecodeError) as exc:
                print(f"Skipping NHTSA lookup for {make['name']}: {exc}", file=sys.stderr)
                models_by_make[make["slug"]] = []

    official_index = build_official_model_index(models_by_make, make_names)
    catalog = build_catalog(candidates, official_index, str(keywords_path), manual_overrides=manual_overrides)
    catalog["generated_at"] = datetime.now(timezone.utc).isoformat().replace("+00:00", "Z")
    catalog["manual_overrides_path"] = str(overrides_path)
    catalog["manual_override_count"] = len(manual_overrides)

    output_path.parent.mkdir(parents=True, exist_ok=True)
    output_path.write_text(json.dumps(catalog, indent=2, sort_keys=False) + "\n")

    summary = catalog["summary"]
    print(
        "Generated catalog:",
        f"makes={summary['make_count']}",
        f"models={summary['model_count']}",
        f"assigned={summary['assigned_model_count']}",
        f"unassigned={summary['unassigned_model_count']}",
        sep=" ",
    )
    print(f"Wrote {output_path}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
