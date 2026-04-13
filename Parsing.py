# -*- coding: utf-8 -*-
"""
Created on Fri May 29 17:40:07 2020

@author: Filip
"""

import requests
import os
import pandas as pd
import numpy as np
from bs4 import BeautifulSoup
print(os.getcwd()) 
document_link=pd.read_csv("link2020NW.csv")
collection=[]
collectionA=[]
count_repo=0
i=0
j=0
for link in document_link["link"]:
    
    URL = link
    response = requests.get(URL)
    soup = BeautifulSoup(response.content, 'xml')
    # Let the user know it was successful.
    
    # find all the entry tags
    entries = soup.find_all('scheduleOfPortfolioSecuritiesInfo')
    df_cols = ["Repo_id","Buyer", "SeriesID", "Category", "Repo_issuer", "Repo_principal", "Return", "Date","Repo_maturity", "Weekly_liquid", "Daily_liquid", "Collateral_issuer", "Collateral_principal", "Collateral_value", "Collateral_maturity", "Collateral_yield", "indicator"]
    rows = []
    rowsA = []
    for repo in entries:
        count_repo+=1
        if repo.find("investmentCategory").text=="Other Repurchase Agreement, if any collateral falls outside Treasury, Government Agency and cash":
            for collateral in repo.find_all("collateralIssuers"):
                if collateral.find("ctgryInvestmentsRprsntsCollateral").text=="Corporate Debt Securities":
                      indicator=0
                      C_issuer=collateral.find("nameOfCollateralIssuer").text
                      Issuer=repo.find("nameOfIssuer").text
                      Return=repo.find("yieldOfTheSecurityAsOfReportingDate").text
                      buyer=soup.find("cik").text
                      date=soup.find("reportDate").text
                      SID=soup.find("seriesId").text
                      Category=soup.find("moneyMarketFundCategory").text
                      principal=collateral.find("principalAmountToTheNearestCent").text
                      collateralvalue=collateral.find("valueOfCollateralToTheNearestCent").text
                      repo_principal=repo.find("includingValueOfAnySponsorSupport").text
                      repo_maturity=repo.find("finalLegalInvestmentMaturityDate").text
                      weekly_liquid=repo.find("weeklyLiquidAssetSecurityFlag").text
                      daily_liquid=repo.find("dailyLiquidAssetSecurityFlag").text
                      try:
                          collateral_maturity=collateral.find("nmfp2common:from").text
                      except AttributeError:
                          try:
                              collateral_maturity=collateral.find("date").text
                          except AttributeError:
                              collateral_maturity=False
                                  
                      collateral_yield=collateral.find("couponOrYield").text
                      rows.append({"Repo_id":count_repo, "Buyer": buyer, "SeriesID":SID, "Category":Category, "Repo_issuer": Issuer, "Repo_principal":repo_principal,"Return": Return, "Date": date,"Repo_maturity":repo_maturity, "Weekly_liquid": weekly_liquid, "Daily_liquid":daily_liquid, "Collateral_issuer": C_issuer,"Collateral_principal": principal, "Collateral_value":collateralvalue,   "Collateral_maturity":collateral_maturity, "Collateral_yield":collateral_yield, "indicator": indicator})
                          
                      
                else:
                      indicator=1
                      C_issuer=collateral.find("nameOfCollateralIssuer").text
                      Issuer=repo.find("nameOfIssuer").text
                      Return=repo.find("yieldOfTheSecurityAsOfReportingDate").text
                      buyer=soup.find("cik").text
                      SID=soup.find("seriesId").text
                      Category=soup.find("moneyMarketFundCategory").text
                      date=soup.find("reportDate").text
                      principal=collateral.find("principalAmountToTheNearestCent").text
                      collateralvalue=collateral.find("valueOfCollateralToTheNearestCent").text
                      collateral_maturity=False
                      collateral_yield=False
                      repo_principal=repo.find("includingValueOfAnySponsorSupport").text
                      repo_maturity=repo.find("finalLegalInvestmentMaturityDate").text
                      weekly_liquid=repo.find("weeklyLiquidAssetSecurityFlag").text
                      daily_liquid=repo.find("dailyLiquidAssetSecurityFlag").text
                      rows.append({"Repo_id":count_repo, "Buyer": buyer, "SeriesID":SID, "Category":Category, "Repo_issuer": Issuer, "Repo_principal":repo_principal,"Return": Return, "Date": date,"Repo_maturity":repo_maturity, "Weekly_liquid": weekly_liquid, "Daily_liquid":daily_liquid, "Collateral_issuer": C_issuer,"Collateral_principal": principal, "Collateral_value":collateralvalue,   "Collateral_maturity":collateral_maturity, "Collateral_yield":collateral_yield, "indicator": indicator})
                                            
        i+=1
    
    full=pd.DataFrame(rows, columns = df_cols) 
    #full['indicator']=full['indicator'].replace(np.nan, 0)
    ##grouped.filter returns data frame with repos that only contain corporate bonds
    full1=full.groupby("Repo_id").filter(lambda x: x["indicator"].mean()==0)

    
    collection.append(full1)

    j+=1
    print(j)
    
    
df=pd.concat(collection, axis=0, join="outer")

c=[]
for x in df["Collateral_issuer"]:
    try:
        c.append(x.split()[0]+";"+x.split()[1])
    except IndexError:
        c.append(x.split()[0])
d=[]
for x in df["Collateral_issuer"]:
    d.append(x.split()[0])
              
        
y=[]
for x in df["Collateral_yield"]:
    try:
        y.append(x.split()[0])
    except AttributeError:
        y.append(x)
df["C_yield_eikon"]=y
        
df["Collateral_issuer_clear"]=c
df["Collateral_issuer_1"]=d


df.to_excel("Repo2020NW.xlsx")

