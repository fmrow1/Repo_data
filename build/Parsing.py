# -*- coding: utf-8 -*-
"""
Parses N-MFP2 filings to extract non-treasury repurchase agreement data.

Input  : nmfp_link_2019_2020_ammended.csv — clean filing list covering
         January 2019 through January 2021, with superseded originals and
         earlier amendment chain entries already removed.
Output : Repo_non_treasury_2019_2020.csv

For each filing the script fetches the primary_doc.xml, finds all
scheduleOfPortfolioSecuritiesInfo entries with investmentCategory ==
"Other Repurchase Agreement, if any collateral falls outside Treasury,
Government Agency and cash", and extracts repo- and collateral-level fields.
"""

import requests
import os
import pandas as pd
import numpy as np
from bs4 import BeautifulSoup

HEADERS = {"User-Agent": "research-script filip.piotr.mrowiec@gmail.com"}

print(os.getcwd())
document_link = pd.read_csv("nmfp_link_2019_2020_ammended.csv")
collection = []
count_repo = 0
i = 0
j = 0

for filing_url in document_link["filing_url"]:
    # Derive the XML URL from the index URL, e.g.:
    # .../000114554920003465/0001145549-20-003465-index.htm
    # -> .../000114554920003465/primary_doc.xml
    base_dir = filing_url.rsplit("/", 1)[0]
    URL = base_dir + "/primary_doc.xml"

    response = requests.get(URL, headers=HEADERS)
    if response.status_code != 200:
        print(f"  [{j+1}] Skipping {URL} (status {response.status_code})")
        j += 1
        continue

    soup = BeautifulSoup(response.content, "xml")

    entries = soup.find_all("scheduleOfPortfolioSecuritiesInfo")
    df_cols = ["Repo_id", "Buyer", "SeriesID", "Category", "Repo_issuer", "Repo_principal", "Return", "Date", "Repo_maturity", "Weekly_liquid", "Daily_liquid", "Collateral_issuer", "Collateral_principal", "Collateral_value", "Collateral_maturity", "Collateral_yield", "Collateral_category"]
    rows = []

    for repo in entries:
        count_repo += 1
        if repo.find("investmentCategory").text == "Other Repurchase Agreement, if any collateral falls outside Treasury, Government Agency and cash":
            for collateral in repo.find_all("collateralIssuers"):
                # Capture the actual collateral category for all types
                collateral_category = collateral.find("ctgryInvestmentsRprsntsCollateral").text

                C_issuer = collateral.find("nameOfCollateralIssuer").text
                principal = collateral.find("principalAmountToTheNearestCent").text
                collateralvalue = collateral.find("valueOfCollateralToTheNearestCent").text

                # Try to extract maturity for all collateral types
                try:
                    collateral_maturity = collateral.find("nmfp2common:from").text
                except AttributeError:
                    try:
                        collateral_maturity = collateral.find("date").text
                    except AttributeError:
                        collateral_maturity = False

                # Try to extract yield for all collateral types
                yield_tag = collateral.find("couponOrYield")
                collateral_yield = yield_tag.text if yield_tag else False

                # Repo-level fields
                def _text(tag): return tag.text if tag else None
                Issuer = _text(repo.find("nameOfIssuer"))
                Return = _text(repo.find("yieldOfTheSecurityAsOfReportingDate"))
                repo_principal = _text(repo.find("includingValueOfAnySponsorSupport"))
                repo_maturity = _text(repo.find("finalLegalInvestmentMaturityDate"))
                weekly_liquid = _text(repo.find("weeklyLiquidAssetSecurityFlag"))
                daily_liquid = _text(repo.find("dailyLiquidAssetSecurityFlag"))

                # Fund-level fields from the filing header
                buyer = soup.find("cik").text
                date = soup.find("reportDate").text
                SID = soup.find("seriesId").text
                Category = soup.find("moneyMarketFundCategory").text

                rows.append({"Repo_id": count_repo, "Buyer": buyer, "SeriesID": SID, "Category": Category, "Repo_issuer": Issuer, "Repo_principal": repo_principal, "Return": Return, "Date": date, "Repo_maturity": repo_maturity, "Weekly_liquid": weekly_liquid, "Daily_liquid": daily_liquid, "Collateral_issuer": C_issuer, "Collateral_principal": principal, "Collateral_value": collateralvalue, "Collateral_maturity": collateral_maturity, "Collateral_yield": collateral_yield, "Collateral_category": collateral_category})

    i += 1

    full = pd.DataFrame(rows, columns=df_cols)
    collection.append(full)

    j += 1
    print(j)


if collection:
    df = pd.concat(collection, axis=0, join="outer")

    c = []
    for x in df["Collateral_issuer"]:
        try:
            c.append(x.split()[0] + ";" + x.split()[1])
        except IndexError:
            c.append(x.split()[0])
    d = []
    for x in df["Collateral_issuer"]:
        d.append(x.split()[0])

    y = []
    for x in df["Collateral_yield"]:
        try:
            y.append(x.split()[0])
        except AttributeError:
            y.append(x)

    df["C_yield_eikon"] = y
    df["Collateral_issuer_clear"] = c
    df["Collateral_issuer_1"] = d

    df.to_csv("Repo_non_treasury_2019_2020.csv", index=False)
    print(f"\nDone. {len(df)} rows saved to Repo_non_treasury_2019_2020.csv")
    print("\nCollateral category breakdown:")
    print(df["Collateral_category"].value_counts().to_string())
else:
    print("No data collected.")
