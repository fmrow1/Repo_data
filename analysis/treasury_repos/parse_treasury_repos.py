# -*- coding: utf-8 -*-
"""
Parses N-MFP2 filings to extract U.S. Treasury repurchase agreement data.

Input  : ../../build/nmfp_link_2019_2020_ammended.csv — clean filing list
         covering January 2019 through January 2021.
Output : Repo_treasury_2019_2020.csv

For each filing the script fetches the primary_doc.xml, finds all
scheduleOfPortfolioSecuritiesInfo entries with investmentCategory ==
"U.S. Treasury Repurchase Agreement, if collateralized only by U.S.
Treasuries (including Strips) and cash", and extracts repo- and
collateral-level fields.
"""

import requests
import os
import pandas as pd
from bs4 import BeautifulSoup

HEADERS = {"User-Agent": "research-script filip.piotr.mrowiec@gmail.com"}

INVESTMENT_CATEGORY = (
    "U.S. Treasury Repurchase Agreement, if collateralized only by "
    "U.S. Treasuries (including Strips) and cash"
)

print(os.getcwd())
document_link = pd.read_csv("../../build/nmfp_link_2019_2020_ammended.csv")
collection = []
count_repo = 0
i = 0
j = 0

for filing_url in document_link["filing_url"]:
    base_dir = filing_url.rsplit("/", 1)[0]
    URL = base_dir + "/primary_doc.xml"

    response = requests.get(URL, headers=HEADERS)
    if response.status_code != 200:
        print(f"  [{j+1}] Skipping {URL} (status {response.status_code})")
        j += 1
        continue

    soup = BeautifulSoup(response.content, "xml")

    entries = soup.find_all("scheduleOfPortfolioSecuritiesInfo")
    df_cols = [
        "Repo_id", "Buyer", "SeriesID", "Category", "Repo_issuer",
        "Repo_principal", "Return", "Date", "Repo_maturity",
        "Weekly_liquid", "Daily_liquid",
        "Collateral_issuer", "Collateral_principal", "Collateral_value",
        "Collateral_maturity", "Collateral_yield", "Collateral_category",
    ]
    rows = []

    def _text(tag):
        return tag.text if tag else None

    for repo in entries:
        count_repo += 1
        if repo.find("investmentCategory").text != INVESTMENT_CATEGORY:
            continue

        for collateral in repo.find_all("collateralIssuers"):
            collateral_category = collateral.find("ctgryInvestmentsRprsntsCollateral").text

            C_issuer        = collateral.find("nameOfCollateralIssuer").text
            principal       = collateral.find("principalAmountToTheNearestCent").text
            collateralvalue = collateral.find("valueOfCollateralToTheNearestCent").text

            try:
                collateral_maturity = collateral.find("nmfp2common:from").text
            except AttributeError:
                try:
                    collateral_maturity = collateral.find("date").text
                except AttributeError:
                    collateral_maturity = False

            yield_tag        = collateral.find("couponOrYield")
            collateral_yield = yield_tag.text if yield_tag else False

            Issuer        = _text(repo.find("nameOfIssuer"))
            Return        = _text(repo.find("yieldOfTheSecurityAsOfReportingDate"))
            repo_principal = _text(repo.find("includingValueOfAnySponsorSupport"))
            repo_maturity  = _text(repo.find("finalLegalInvestmentMaturityDate"))
            weekly_liquid  = _text(repo.find("weeklyLiquidAssetSecurityFlag"))
            daily_liquid   = _text(repo.find("dailyLiquidAssetSecurityFlag"))

            buyer    = soup.find("cik").text
            date     = soup.find("reportDate").text
            SID      = soup.find("seriesId").text
            Category = soup.find("moneyMarketFundCategory").text

            rows.append({
                "Repo_id":              count_repo,
                "Buyer":                buyer,
                "SeriesID":             SID,
                "Category":             Category,
                "Repo_issuer":          Issuer,
                "Repo_principal":       repo_principal,
                "Return":               Return,
                "Date":                 date,
                "Repo_maturity":        repo_maturity,
                "Weekly_liquid":        weekly_liquid,
                "Daily_liquid":         daily_liquid,
                "Collateral_issuer":    C_issuer,
                "Collateral_principal": principal,
                "Collateral_value":     collateralvalue,
                "Collateral_maturity":  collateral_maturity,
                "Collateral_yield":     collateral_yield,
                "Collateral_category":  collateral_category,
            })

    i += 1
    full = pd.DataFrame(rows, columns=df_cols)
    collection.append(full)

    j += 1
    print(j)


if collection:
    df = pd.concat(collection, axis=0, join="outer")

    # Clean collateral issuer fields (same as non-treasury parser)
    c = []
    for x in df["Collateral_issuer"]:
        try:
            c.append(x.split()[0] + ";" + x.split()[1])
        except IndexError:
            c.append(x.split()[0])
    d = [x.split()[0] for x in df["Collateral_issuer"]]

    y = []
    for x in df["Collateral_yield"]:
        try:
            y.append(x.split()[0])
        except AttributeError:
            y.append(x)

    df["C_yield_eikon"]          = y
    df["Collateral_issuer_clear"] = c
    df["Collateral_issuer_1"]     = d

    df.to_csv("Repo_treasury_2019_2020.csv", index=False)
    print(f"\nDone. {len(df)} rows saved to Repo_treasury_2019_2020.csv")
    print("\nCollateral category breakdown:")
    print(df["Collateral_category"].value_counts().to_string())
else:
    print("No data collected.")
