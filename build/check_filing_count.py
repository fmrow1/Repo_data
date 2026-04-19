"""
Stress test #1: verify that nmfp_links_jan2020.csv captured all N-MFP2
filings reported by SEC EDGAR for January 2020.

Cross-checks the row count of the local CSV against the total returned by
the EDGAR full-text search API (the same endpoint used during collection).
"""

import csv
import sys
import requests

EDGAR_SEARCH_URL = "https://efts.sec.gov/LATEST/search-index"
LOCAL_CSV = "nmfp_links_jan2020.csv"
FORM_TYPE = "N-MFP2"
DATE_START = "2020-01-01"
DATE_END = "2020-01-31"

HEADERS = {
    "User-Agent": "research-script filip.piotr.mrowiec@gmail.com",
    "Accept": "application/json",
}


def edgar_total() -> tuple[int, str]:
    """Return (count, relation) from EDGAR for the target period."""
    params = {
        "forms": FORM_TYPE,
        "startdt": DATE_START,
        "enddt": DATE_END,
        "from": 0,
        "size": 1,  # we only need the total, not the hits themselves
    }
    resp = requests.get(EDGAR_SEARCH_URL, params=params, headers=HEADERS, timeout=15)
    resp.raise_for_status()
    total = resp.json()["hits"]["total"]
    if isinstance(total, dict):
        return total["value"], total.get("relation", "eq")
    return int(total), "eq"


def local_count() -> int:
    with open(LOCAL_CSV, newline="") as f:
        return sum(1 for _ in csv.DictReader(f))


def main() -> None:
    print(f"Checking {LOCAL_CSV} against EDGAR ({FORM_TYPE}, {DATE_START} – {DATE_END})…\n")

    api_count, relation = edgar_total()
    csv_count = local_count()

    print(f"  EDGAR total  : {api_count}  (relation={relation})")
    print(f"  CSV rows     : {csv_count}")

    if relation != "eq":
        print("\nWARNING: EDGAR returned a non-exact total — result is a lower bound.")

    if csv_count == api_count:
        print("\nPASS: counts match.")
    else:
        diff = csv_count - api_count
        direction = "extra" if diff > 0 else "missing"
        print(f"\nFAIL: counts differ by {abs(diff)} ({direction} rows in CSV).")
        sys.exit(1)


if __name__ == "__main__":
    main()
