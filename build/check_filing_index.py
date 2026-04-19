"""
Stress test #2: cross-check nmfp_links_jan2020.csv against the SEC EDGAR
full-index (form.idx) for Q1 2020 — a source entirely independent of the
search API used during collection.

The full-index is a fixed-width flat file that lists every filing disseminated
via EDGAR.  Filtering to N-MFP2 rows with a January 2020 date gives a ground-
truth count and set of accession numbers to compare against.
"""

import csv
import re
import sys
import requests

FULL_INDEX_URL = "https://www.sec.gov/Archives/edgar/full-index/2020/QTR1/form.idx"
LOCAL_CSV = "nmfp_links_jan2020.csv"
FORM_TYPE = "N-MFP2"
MONTH_PREFIX = "2020-01"

HEADERS = {"User-Agent": "research-script filip.piotr.mrowiec@gmail.com"}


def accession_from_path(file_path: str) -> str:
    """
    Convert an index file path like
      edgar/data/1234567/0001234567-20-000001.txt
    to the canonical hyphenated accession number
      0001234567-20-000001
    """
    basename = file_path.rstrip().rsplit("/", 1)[-1]
    return re.sub(r"\.txt$", "", basename)


def index_accessions() -> set[str]:
    """Download form.idx and return accession numbers for Jan-2020 N-MFP2 filings."""
    resp = requests.get(FULL_INDEX_URL, headers=HEADERS, timeout=30)
    resp.raise_for_status()

    accessions: set[str] = set()
    for line in resp.text.splitlines():
        if not line.startswith(FORM_TYPE):
            continue
        # Fixed-width columns; date filed starts at column 91 (0-indexed)
        date_filed = line[91:101].strip()
        if not date_filed.startswith(MONTH_PREFIX):
            continue
        file_path = line[102:].strip()
        accessions.add(accession_from_path(file_path))

    return accessions


def csv_accessions() -> set[str]:
    with open(LOCAL_CSV, newline="") as f:
        return {row["accession_no"] for row in csv.DictReader(f)}


def main() -> None:
    print(f"Comparing {LOCAL_CSV} against EDGAR full-index ({FORM_TYPE}, {MONTH_PREFIX})…\n")

    idx = index_accessions()
    csv_ = csv_accessions()

    print(f"  Full-index count : {len(idx)}")
    print(f"  CSV count        : {len(csv_)}")

    missing_from_csv = idx - csv_
    extra_in_csv = csv_ - idx

    if missing_from_csv:
        print(f"\nFAIL: {len(missing_from_csv)} accession(s) in full-index but NOT in CSV:")
        for a in sorted(missing_from_csv):
            print(f"  {a}")

    if extra_in_csv:
        print(f"\nFAIL: {len(extra_in_csv)} accession(s) in CSV but NOT in full-index:")
        for a in sorted(extra_in_csv):
            print(f"  {a}")

    if missing_from_csv or extra_in_csv:
        sys.exit(1)

    print(f"\nPASS: all {len(idx)} accession numbers match.")


if __name__ == "__main__":
    main()
