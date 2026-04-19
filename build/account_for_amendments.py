"""
Resolves N-MFP2/A amendments against their superseded N-MFP2 originals and
produces a clean filing list with superseded originals removed.

Matching logic
--------------
An amendment supersedes the original with the same (cik, seriesId, report_date).
A CIK can have multiple series — each files its own N-MFP2 — so matching on
(cik, report_date) alone would wrongly remove sibling series' originals.
seriesId is therefore read from the primary_doc.xml of:
  - every N-MFP2/A amendment (254 requests), and
  - every N-MFP2 original that shares (cik, report_date) with any amendment
    (384 requests).

Amendment chains
----------------
Occasionally a series files two or more amendments for the same reporting
period.  Each amendment is a full refile, not an incremental patch, so the
later amendment entirely replaces the earlier one.  Within each
(cik, seriesId, report_date) group of amendments only the most recently
filed is retained; earlier ones are discarded.

Output
------
nmfp_links_2019_2021_clean.csv  — original CSV minus superseded rows, plus a
                                   new series_id column for all fetched filings.
A summary of what was removed is printed to stdout.
"""

import csv
import time
import xml.etree.ElementTree as ET
from collections import defaultdict

import requests

INPUT_CSV  = "nmfp_links_2019_2021.csv"
OUTPUT_CSV = "nmfp_link_2019_2020_ammended.csv"

FILING_BASE_URL = "https://www.sec.gov/Archives/edgar/data"
HEADERS = {
    "User-Agent": "research-script filip.piotr.mrowiec@gmail.com",
    "Accept":     "application/xml",
}


# ── XML helpers ───────────────────────────────────────────────────────────────

def xml_url(cik: str, accession_no: str) -> str:
    return f"{FILING_BASE_URL}/{cik}/{accession_no.replace('-', '')}/primary_doc.xml"


def fetch_series_id(cik: str, accession_no: str) -> str:
    """Return the <seriesId> from a filing's primary_doc.xml, or '' on failure."""
    try:
        resp = requests.get(xml_url(cik, accession_no), headers=HEADERS, timeout=15)
        resp.raise_for_status()
        root = ET.fromstring(resp.content)
        for el in root.iter():
            if el.tag.split("}")[-1] == "seriesId":
                return el.text or ""
    except Exception as exc:
        print(f"  Warning: could not fetch seriesId for {accession_no}: {exc}")
    return ""


def fetch_series_ids(rows: list[dict], label: str) -> dict[str, str]:
    """
    Fetch seriesId for a list of filing rows.
    Returns {accession_no: series_id}.
    """
    result: dict[str, str] = {}
    total = len(rows)
    for i, row in enumerate(rows, 1):
        sid = fetch_series_id(row["cik"], row["accession_no"])
        result[row["accession_no"]] = sid
        if i % 50 == 0 or i == total:
            print(f"  {label}: {i}/{total}")
        time.sleep(0.15)
    return result


# ── Main ──────────────────────────────────────────────────────────────────────

def main() -> None:
    with open(INPUT_CSV, newline="") as f:
        rows = list(csv.DictReader(f))

    amendments = [r for r in rows if r["form_type"] == "N-MFP2/A"]
    originals  = [r for r in rows if r["form_type"] == "N-MFP2"]

    print(f"Loaded {len(rows)} filings ({len(originals)} originals, {len(amendments)} amendments).\n")

    # ── Step 1: fetch seriesId for all amendments ─────────────────────────────
    print(f"Step 1 — fetching seriesId for {len(amendments)} amendments…")
    amend_series = fetch_series_ids(amendments, "amendments")

    # ── Step 2: identify originals that need seriesId ─────────────────────────
    amend_keys = {(r["cik"], r["report_date"]) for r in amendments}
    affected_originals = [r for r in originals if (r["cik"], r["report_date"]) in amend_keys]

    print(f"\nStep 2 — fetching seriesId for {len(affected_originals)} affected originals…")
    orig_series = fetch_series_ids(affected_originals, "originals")

    # ── Step 3a: within amendment chains keep only the latest filing ─────────
    # Group amendments by (cik, seriesId, report_date); where >1 exist, discard
    # all but the most recently filed (they are full refiles, not incremental).
    amend_chains: dict[tuple, list[dict]] = defaultdict(list)
    for r in amendments:
        sid = amend_series.get(r["accession_no"], "")
        amend_chains[(r["cik"], sid, r["report_date"])].append(r)

    superseded_amendments: set[str] = set()
    for chain in amend_chains.values():
        if len(chain) > 1:
            chain.sort(key=lambda x: x["filed_at"])
            for earlier in chain[:-1]:
                superseded_amendments.add(earlier["accession_no"])

    # ── Step 3b: build superseded originals set ───────────────────────────────
    # Index originals by (cik, seriesId, report_date)
    orig_index: dict[tuple, list[str]] = defaultdict(list)
    for r in affected_originals:
        sid = orig_series.get(r["accession_no"], "")
        orig_index[(r["cik"], sid, r["report_date"])].append(r["accession_no"])

    superseded_originals: set[str] = set()
    unmatched_amendments: list[str] = []

    for r in amendments:
        if r["accession_no"] in superseded_amendments:
            continue  # already being discarded; don't count as unmatched
        sid = amend_series.get(r["accession_no"], "")
        key = (r["cik"], sid, r["report_date"])
        originals_for_key = orig_index.get(key, [])
        if originals_for_key:
            superseded_originals.update(originals_for_key)
        else:
            unmatched_amendments.append(r["accession_no"])

    # ── Step 4: write clean output ────────────────────────────────────────────
    # Attach series_id to all rows (empty string for unaffected originals).
    # Drop amendment filings whose report_date is before 2019.
    all_series = {**amend_series, **orig_series}
    clean_rows = []
    dropped_pre2019 = 0
    for r in rows:
        if r["accession_no"] in superseded_originals:
            continue
        if r["accession_no"] in superseded_amendments:
            continue
        if r["form_type"] == "N-MFP2/A" and r["report_date"] < "2019-01-01":
            dropped_pre2019 += 1
            continue
        r["series_id"] = all_series.get(r["accession_no"], "")
        clean_rows.append(r)

    fieldnames = ["accession_no", "form_type", "cik", "name", "filed_at",
                  "report_date", "series_id", "filing_url"]
    with open(OUTPUT_CSV, "w", newline="") as f:
        writer = csv.DictWriter(f, fieldnames=fieldnames)
        writer.writeheader()
        writer.writerows(clean_rows)

    # ── Summary ───────────────────────────────────────────────────────────────
    print(f"\n{'─'*60}")
    retained_amendments = len(amendments) - len(superseded_amendments) - dropped_pre2019
    print(f"Superseded originals removed : {len(superseded_originals)}")
    print(f"Superseded amendments removed: {len(superseded_amendments)}  (earlier filings in chains)")
    print(f"Amendments pre-2019 dropped  : {dropped_pre2019}")
    print(f"Amendments retained          : {retained_amendments}")
    print(f"Unmatched amendments         : {len(unmatched_amendments)}")
    if unmatched_amendments:
        print("  (no original found — original likely pre-dates 2019-01-01 window)")
        for a in unmatched_amendments[:10]:
            print(f"  {a}")
        if len(unmatched_amendments) > 10:
            print(f"  … and {len(unmatched_amendments) - 10} more")
    print(f"Clean filing count           : {len(clean_rows)}")
    print(f"Saved to {OUTPUT_CSV}")


if __name__ == "__main__":
    main()
