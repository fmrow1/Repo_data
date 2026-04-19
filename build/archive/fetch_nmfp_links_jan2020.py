"""
Fetches links to all N-MFP filings published on SEC EDGAR in January 2020.

Uses the EDGAR full-text search API to query for N-MFP form submissions
dated between 2020-01-01 and 2020-01-31, then saves the filing index URLs
to CSV and JSON output files.
"""

import csv
import json
import requests

EDGAR_SEARCH_URL = "https://efts.sec.gov/LATEST/search-index"
FILING_BASE_URL = "https://www.sec.gov/Archives/edgar/data"
OUTPUT_CSV = "nmfp_links_jan2020.csv"
OUTPUT_JSON = "nmfp_links_jan2020.json"

DATE_START = "2020-01-01"
DATE_END = "2020-01-31"

# N-MFP was retired in 2016; the updated form introduced under the revised MMF
# rules is filed as N-MFP2 on EDGAR.
FORM_TYPE = "N-MFP2"

HEADERS = {
    "User-Agent": "research-script contact@example.com",
    "Accept": "application/json",
}


def fetch_filing_links() -> list[dict]:
    results: list[dict] = []
    offset = 0
    page_size = 100

    while True:
        params = {
            "forms": FORM_TYPE,
            "startdt": DATE_START,
            "enddt": DATE_END,
            "from": offset,
            "size": page_size,
        }

        try:
            response = requests.get(EDGAR_SEARCH_URL, params=params, headers=HEADERS, timeout=15)
            response.raise_for_status()
        except requests.HTTPError as exc:
            print(f"EDGAR returned {exc.response.status_code} at offset {offset}; stopping.")
            break

        data = response.json()
        hits = data.get("hits", {}).get("hits", [])
        if not hits:
            break

        for hit in hits:
            source = hit.get("_source", {})

            ciks_raw = source.get("ciks", [])
            cik = str(ciks_raw[0]).lstrip("0") if ciks_raw else None

            # The accession number is stored in the hit _id, formatted as
            # "0001234567-20-000001:primary_doc.xml"; strip any filename suffix.
            raw_id = hit.get("_id", "")
            accession_no = raw_id.split(":")[0]  # e.g. "0001234567-20-000001"
            accession_path = accession_no.replace("-", "")  # "000123456720000001"

            display_names = source.get("display_names", [])
            raw_name = display_names[0] if display_names else "Unknown"
            name = raw_name.split("(CIK")[0].strip() if "(CIK" in raw_name else raw_name

            filed_at = source.get("file_date", "")

            if cik and accession_path:
                filing_url = f"{FILING_BASE_URL}/{cik}/{accession_path}/{accession_no}-index.htm"
            else:
                filing_url = ""

            results.append({
                "accession_no": accession_no,
                "cik": cik or "",
                "name": name,
                "filed_at": filed_at,
                "filing_url": filing_url,
            })

        print(f"  Fetched {len(results)} filings so far (offset {offset})…")

        total = data.get("hits", {}).get("total", {})
        total_value = total.get("value", 0) if isinstance(total, dict) else int(total)
        if offset + page_size >= total_value:
            break

        offset += page_size

    return results


def main() -> None:
    print(f"Querying SEC EDGAR for {FORM_TYPE} filings from {DATE_START} to {DATE_END}…\n")
    filings = fetch_filing_links()

    if not filings:
        print("No filings found. Check network access or EDGAR API availability.")
        return

    with open(OUTPUT_CSV, "w", newline="") as f:
        writer = csv.DictWriter(f, fieldnames=["accession_no", "cik", "name", "filed_at", "filing_url"])
        writer.writeheader()
        writer.writerows(filings)

    with open(OUTPUT_JSON, "w") as f:
        json.dump(filings, f, indent=2)

    print(f"\nSaved {len(filings)} filing link(s) to {OUTPUT_CSV} and {OUTPUT_JSON}")


if __name__ == "__main__":
    main()
