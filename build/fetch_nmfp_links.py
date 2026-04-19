"""
Fetches links to all N-MFP2 and N-MFP2/A filings published on SEC EDGAR
between January 2019 and January 2021 (inclusive).

Iterates month by month to stay well within EDGAR's per-query result window.

The EDGAR search API returns N-MFP2/A hits when queried for "N-MFP2", but
does not expose form_type in the response payload.  To correctly label each
filing we therefore run three passes:
  Pass 1  Query N-MFP2/A month by month to collect all amendment accession
          numbers (no filing metadata needed here).
  Pass 2  Query N-MFP2 month by month to collect all filings (originals +
          amendments) with full metadata.  Each row is then labelled
          N-MFP2/A if its accession number appeared in Pass 1, otherwise
          N-MFP2.
  Pass 3  Derive report_date for each filing:
          - Originals: last business day (Mon–Fri) of the month prior to
            filed_at.  N-MFP2 is due within 5 business days of month-end,
            so the filing month reliably identifies the reporting month.
            Business-day adjustment is necessary because months ending on
            weekends (e.g. March 2019) have a last business day that
            differs from the last calendar day.
          - Amendments: fetch the primary_doc.xml and read <reportDate>
            directly (254 requests).

Outputs a single CSV and JSON file with form_type and report_date columns.
"""

import calendar
import csv
import json
import time
import xml.etree.ElementTree as ET
from datetime import date, timedelta
import requests

EDGAR_SEARCH_URL = "https://efts.sec.gov/LATEST/search-index"
FILING_BASE_URL  = "https://www.sec.gov/Archives/edgar/data"
OUTPUT_CSV       = "nmfp_links_2019_2020.csv"
OUTPUT_JSON      = "nmfp_links_2019_2020.json"

RANGE_START = date(2019, 1, 1)
RANGE_END   = date(2021, 1, 31)

HEADERS = {
    "User-Agent": "research-script filip.piotr.mrowiec@gmail.com",
    "Accept": "application/json",
}

PAGE_SIZE = 100


def month_windows(start: date, end: date):
    """Yield (month_start, month_end) date pairs from start to end, inclusive."""
    year, month = start.year, start.month
    while date(year, month, 1) <= end:
        last_day = calendar.monthrange(year, month)[1]
        month_start = date(year, month, 1)
        month_end   = min(date(year, month, last_day), end)
        yield month_start, month_end
        month += 1
        if month > 12:
            month, year = 1, year + 1


def fetch_accession_numbers(form_type: str, start: date, end: date) -> set[str]:
    """Return all accession numbers for the given form type and date window."""
    accessions: set[str] = set()
    offset = 0

    while True:
        params = {
            "forms":   form_type,
            "startdt": start.isoformat(),
            "enddt":   end.isoformat(),
            "from":    offset,
            "size":    PAGE_SIZE,
        }
        try:
            resp = requests.get(EDGAR_SEARCH_URL, params=params, headers=HEADERS, timeout=15)
            resp.raise_for_status()
        except requests.HTTPError as exc:
            print(f"  HTTP {exc.response.status_code} at offset {offset} — stopping.")
            break

        data = resp.json()
        hits = data.get("hits", {}).get("hits", [])
        if not hits:
            break

        for hit in hits:
            accessions.add(hit.get("_id", "").split(":")[0])

        total = data.get("hits", {}).get("total", {})
        total_value = total.get("value", 0) if isinstance(total, dict) else int(total)
        if offset + PAGE_SIZE >= total_value:
            break
        offset += PAGE_SIZE

    return accessions


def fetch_filings(form_type: str, start: date, end: date) -> list[dict]:
    """Return full filing records for the given form type and date window."""
    results: list[dict] = []
    offset = 0

    while True:
        params = {
            "forms":   form_type,
            "startdt": start.isoformat(),
            "enddt":   end.isoformat(),
            "from":    offset,
            "size":    PAGE_SIZE,
        }
        try:
            resp = requests.get(EDGAR_SEARCH_URL, params=params, headers=HEADERS, timeout=15)
            resp.raise_for_status()
        except requests.HTTPError as exc:
            print(f"  HTTP {exc.response.status_code} at offset {offset} — stopping.")
            break

        data = resp.json()
        hits = data.get("hits", {}).get("hits", [])
        if not hits:
            break

        for hit in hits:
            source = hit.get("_source", {})

            ciks_raw = source.get("ciks", [])
            cik = str(ciks_raw[0]).lstrip("0") if ciks_raw else ""

            raw_id         = hit.get("_id", "")
            accession_no   = raw_id.split(":")[0]
            accession_path = accession_no.replace("-", "")

            display_names = source.get("display_names", [])
            raw_name = display_names[0] if display_names else "Unknown"
            name = raw_name.split("(CIK")[0].strip() if "(CIK" in raw_name else raw_name

            filed_at = source.get("file_date", "")

            filing_url = (
                f"{FILING_BASE_URL}/{cik}/{accession_path}/{accession_no}-index.htm"
                if cik and accession_path else ""
            )

            results.append({
                "accession_no": accession_no,
                "cik":          cik,
                "name":         name,
                "filed_at":     filed_at,
                "filing_url":   filing_url,
            })

        total = data.get("hits", {}).get("total", {})
        total_value = total.get("value", 0) if isinstance(total, dict) else int(total)
        if offset + PAGE_SIZE >= total_value:
            break
        offset += PAGE_SIZE

    return results


def derive_report_date(filed_at: str) -> str:
    """Last business day of the month prior to the filing month.

    N-MFP2 is due within 5 business days of month-end, so the filing month
    reliably identifies the reporting month.  The report date is the last
    business day (Mon–Fri) of that prior month — not the last calendar day,
    which can fall on a weekend (e.g. March 2019 ended on Sunday, so the
    correct report date is 2019-03-29, not 2019-03-31).
    """
    d = date.fromisoformat(filed_at)
    last_cal = date(d.year, d.month, 1) - timedelta(days=1)
    while last_cal.weekday() >= 5:   # 5 = Saturday, 6 = Sunday
        last_cal -= timedelta(days=1)
    return last_cal.isoformat()


def fetch_report_date_from_xml(cik: str, accession_no: str) -> str:
    """Fetch the primary_doc.xml for an amendment and return its <reportDate>."""
    accession_path = accession_no.replace("-", "")
    url = f"{FILING_BASE_URL}/{cik}/{accession_path}/primary_doc.xml"
    try:
        resp = requests.get(url, headers=HEADERS, timeout=15)
        resp.raise_for_status()
        root = ET.fromstring(resp.content)
        for el in root.iter():
            if el.tag.split("}")[-1] == "reportDate":
                return el.text or ""
    except Exception as exc:
        print(f"  Warning: could not fetch report date for {accession_no}: {exc}")
    return ""


def main() -> None:
    # ── Pass 1: collect amendment accession numbers ───────────────────────────
    print(f"Pass 1 — collecting N-MFP2/A accession numbers ({RANGE_START} – {RANGE_END})…")
    amendment_accessions: set[str] = set()
    for month_start, month_end in month_windows(RANGE_START, RANGE_END):
        batch = fetch_accession_numbers("N-MFP2/A", month_start, month_end)
        amendment_accessions |= batch
        if batch:
            print(f"  {month_start.strftime('%Y-%m')}: {len(batch)} amendment(s) found")
    print(f"Total amendment accessions: {len(amendment_accessions)}\n")

    # ── Pass 2: fetch all filings and label form_type ─────────────────────────
    print(f"Pass 2 — fetching all N-MFP2 filings ({RANGE_START} – {RANGE_END})…")
    all_filings: list[dict] = []
    seen: set[str] = set()

    for month_start, month_end in month_windows(RANGE_START, RANGE_END):
        batch = fetch_filings("N-MFP2", month_start, month_end)
        new = [r for r in batch if r["accession_no"] not in seen]
        seen.update(r["accession_no"] for r in new)
        for r in new:
            r["form_type"] = "N-MFP2/A" if r["accession_no"] in amendment_accessions else "N-MFP2"
        all_filings.extend(new)
        print(f"  {month_start.strftime('%Y-%m')}: {len(batch)} fetched → running total {len(all_filings)}")

    if not all_filings:
        print("\nNo filings found.")
        return

    # ── Pass 3: add report_date column ────────────────────────────────────────
    print("\nPass 3 — deriving report dates…")
    amendments_to_fetch = [r for r in all_filings if r["form_type"] == "N-MFP2/A"]
    print(f"  Originals: deriving from filed_at (no network)")
    print(f"  Amendments: fetching XML for {len(amendments_to_fetch)} filings…")

    for r in all_filings:
        if r["form_type"] == "N-MFP2":
            r["report_date"] = derive_report_date(r["filed_at"])
        else:
            r["report_date"] = fetch_report_date_from_xml(r["cik"], r["accession_no"])
            time.sleep(0.15)  # be polite to EDGAR

    print("  Done.")

    fieldnames = ["accession_no", "form_type", "cik", "name", "filed_at", "report_date", "filing_url"]
    with open(OUTPUT_CSV, "w", newline="") as f:
        writer = csv.DictWriter(f, fieldnames=fieldnames)
        writer.writeheader()
        writer.writerows(all_filings)

    with open(OUTPUT_JSON, "w") as f:
        json.dump(all_filings, f, indent=2)

    originals  = sum(1 for r in all_filings if r["form_type"] == "N-MFP2")
    amendments = sum(1 for r in all_filings if r["form_type"] == "N-MFP2/A")
    print(f"\nSaved {len(all_filings)} filings to {OUTPUT_CSV}")
    print(f"  N-MFP2:    {originals}")
    print(f"  N-MFP2/A:  {amendments}")


if __name__ == "__main__":
    main()
