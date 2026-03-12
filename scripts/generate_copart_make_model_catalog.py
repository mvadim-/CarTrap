#!/usr/bin/env python3
"""Generate a static Copart make/model catalog using Copart keywords and NHTSA vPIC."""

from __future__ import annotations

import argparse
import json
import sys
from datetime import datetime, timezone
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
BACKEND_SRC = ROOT / "backend" / "src"
if str(BACKEND_SRC) not in sys.path:
    sys.path.insert(0, str(BACKEND_SRC))


from cartrap.modules.search.catalog_builder import (  # noqa: E402
    load_keyword_payload,
)
from cartrap.modules.search.catalog_refresh import generate_catalog_from_keyword_payload  # noqa: E402


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


def main() -> int:
    args = parse_args()
    keywords_path = Path(args.keywords).resolve()
    output_path = Path(args.output).resolve()
    overrides_path = Path(args.overrides).resolve()

    payload = load_keyword_payload(keywords_path)
    manual_overrides = {}
    if overrides_path.exists():
        manual_overrides = json.loads(overrides_path.read_text())
    catalog = generate_catalog_from_keyword_payload(payload, str(keywords_path), manual_overrides=manual_overrides)
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
