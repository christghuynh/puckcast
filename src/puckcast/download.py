from __future__ import annotations

import argparse
import hashlib
import json
from datetime import UTC, datetime
from pathlib import Path

import requests

BASE = "https://peter-tanner.com/moneypuck/downloads"
ROOT = Path(__file__).resolve().parents[2]
RAW = ROOT / "data" / "raw"
MANIFEST = ROOT / "data" / "manifest.json"

KINDS = {
    "shots": "shots_{season}.zip",
    "skaters": "seasonPlayersSummary/skaters/{season}.zip",
    "goalies": "seasonPlayersSummary/goalies/{season}.zip",
}


def parse_seasons(spec: str) -> list[int]:
    if "-" in spec:
        lo, hi = spec.split("-")
        return list(range(int(lo), int(hi) + 1))
    return [int(s) for s in spec.split(",")]


def sha256_of(path: Path) -> str:
    h = hashlib.sha256()
    with path.open("rb") as f:
        for chunk in iter(lambda: f.read(1 << 20), b""):
            h.update(chunk)
    return h.hexdigest()


def download(url: str, dest: Path) -> dict[str, str | int]:
    dest.parent.mkdir(parents=True, exist_ok=True)
    with requests.get(url, stream=True, timeout=60) as r:
        r.raise_for_status()
        with dest.open("wb") as f:
            for chunk in r.iter_content(1 << 20):
                f.write(chunk)
        last_modified = r.headers.get("Last-Modified", "")
    return {
        "url": url,
        "bytes": dest.stat().st_size,
        "sha256": sha256_of(dest),
        "last_modified": last_modified,
        "downloaded_at": datetime.now(UTC).isoformat(timespec="seconds"),
    }


def main() -> None:
    ap = argparse.ArgumentParser()
    ap.add_argument("--seasons", required=True, help="e.g. 2015-2026 or 2024,2025")
    ap.add_argument("--kinds", default=",".join(KINDS), help="comma list of: shots,skaters,goalies")
    ap.add_argument("--refresh", action="store_true", help="re-download files already present")
    args = ap.parse_args()

    manifest = json.loads(MANIFEST.read_text()) if MANIFEST.exists() else {}
    for season in parse_seasons(args.seasons):
        for kind in args.kinds.split(","):
            rel = f"{kind}/{season}.zip"
            dest = RAW / rel
            if dest.exists() and not args.refresh:
                print(f"skip {rel} (exists; use --refresh to re-download)")
                continue
            url = f"{BASE}/{KINDS[kind].format(season=season)}"
            print(f"get  {rel}")
            manifest[rel] = download(url, dest)
            MANIFEST.parent.mkdir(parents=True, exist_ok=True)
            MANIFEST.write_text(json.dumps(manifest, indent=2, sort_keys=True) + "\n", newline="\n")


if __name__ == "__main__":
    main()
