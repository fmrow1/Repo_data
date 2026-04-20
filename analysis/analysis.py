# -*- coding: utf-8 -*-
"""
Statistical analysis of Repo_non_treasury_2019_2020.csv.

- Total number of unique repos
- Number of repos with only one collateral type
- Average repo yield per collateral type
"""

import pandas as pd

df = pd.read_csv("../build/Repo_non_treasury_2019_2020.csv")
df["Return"] = pd.to_numeric(df["Return"], errors="coerce")
df["Collateral_value"] = pd.to_numeric(df["Collateral_value"], errors="coerce")

# Exclude observations with zero or missing collateral value
n_before = len(df)
df = df[df["Collateral_value"] > 0]
print(f"Dropped {n_before - len(df)} rows with zero/missing collateral value ({n_before} → {len(df)})\n")

# Add report month (YYYY-MM) derived from the Date column
df["Report_month"] = pd.to_datetime(df["Date"]).dt.to_period("M").astype(str)

# ── 1. TOTAL UNIQUE REPOS ─────────────────────────────────────────────────────
total_repos = df["Repo_id"].nunique()
print(f"=== TOTAL UNIQUE REPOS ===")
print(f"{total_repos}\n")

# ── 2. REPOS WITH ONLY ONE COLLATERAL TYPE ────────────────────────────────────
collateral_types_per_repo = df.groupby("Repo_id")["Collateral_category"].nunique()
single_collateral = (collateral_types_per_repo == 1).sum()
multi_collateral = (collateral_types_per_repo > 1).sum()

print(f"=== COLLATERAL TYPE MIX ===")
print(f"Repos with only one collateral type:      {single_collateral} ({single_collateral/total_repos*100:.1f}%)")
print(f"Repos with multiple collateral types:     {multi_collateral} ({multi_collateral/total_repos*100:.1f}%)")
print()

# Breakdown: how many repos have exactly N collateral types
print("Distribution of collateral type count per repo:")
print(collateral_types_per_repo.value_counts().sort_index().rename("Repo count").to_string())
print()

# ── 3. AVERAGE REPO YIELD PER COLLATERAL TYPE (single-collateral repos only) ──
# Filter to repos with exactly one collateral type (N=1), then deduplicate
# to one row per repo before averaging to avoid weighting by collateral count.
single_type_repo_ids = collateral_types_per_repo[collateral_types_per_repo == 1].index
df_single = df[df["Repo_id"].isin(single_type_repo_ids)]
df_single_unique = df_single.drop_duplicates(subset="Repo_id")[["Repo_id", "Collateral_category", "Return"]]

avg_yield = (
    df_single_unique.groupby("Collateral_category")["Return"]
    .mean()
    .sort_values()
    * 100  # convert to percentage
)

repo_counts = df_single_unique.groupby("Collateral_category")["Repo_id"].count().rename("N repos")

print(f"=== AVERAGE REPO YIELD BY COLLATERAL TYPE — single-collateral repos only (%) ===")
for cat, val in avg_yield.items():
    n = repo_counts[cat]
    print(f"  {cat:<50} {val:.4f}%  (n={n})")

# ── 4. AVERAGE HAIRCUT BY COLLATERAL TYPE (single-collateral repos only) ──────
# Haircut = (sum of collateral value - repo principal) / sum of collateral value
# Computed per repo, then averaged by collateral type.
df["Repo_principal"]     = pd.to_numeric(df["Repo_principal"],     errors="coerce")

df_single = df[df["Repo_id"].isin(single_type_repo_ids)]

repo_haircuts = (
    df_single.groupby("Repo_id")
    .apply(lambda x: pd.Series({
        "Collateral_category": x["Collateral_category"].iloc[0],
        "haircut": (x["Collateral_value"].sum() - x["Repo_principal"].iloc[0]) / x["Collateral_value"].sum()
    }))
    .reset_index(drop=True)
)

avg_haircut  = repo_haircuts.groupby("Collateral_category")["haircut"].mean().sort_values() * 100
haircut_counts = repo_haircuts.groupby("Collateral_category")["haircut"].count().rename("N repos")

print()
print(f"=== AVERAGE HAIRCUT BY COLLATERAL TYPE — single-collateral repos only (%) ===")
for cat, val in avg_haircut.items():
    n = haircut_counts[cat]
    print(f"  {cat:<50} {val:.4f}%  (n={n})")

# ── SUMMARY TABLE (steps 2-4) ─────────────────────────────────────────────────
summary = pd.DataFrame({
    "N repos (single-type)": repo_counts,
    "Avg Yield (%)":         avg_yield.round(4),
    "Avg Haircut (%)":       avg_haircut.round(4),
}).sort_values("Avg Haircut (%)")

print()
print("=== SUMMARY TABLE ===")
print(summary.to_string())

summary.to_csv("summary_stats.csv")
print("\nSaved to summary_stats.csv")

# ── EXPORT TABLE AS IMAGE AND PDF ─────────────────────────────────────────────
import matplotlib
matplotlib.use("Agg")  # non-interactive backend
import matplotlib.pyplot as plt

fig = plt.figure(figsize=(12, 5))
gs = fig.add_gridspec(2, 1, height_ratios=[5, 1], hspace=0)
ax_table = fig.add_subplot(gs[0])
ax_notes = fig.add_subplot(gs[1])

ax_table.axis("off")
ax_notes.axis("off")

table = ax_table.table(
    cellText=summary.reset_index().values,
    colLabels=["Collateral Type", "N Repos", "Avg Yield (%)", "Avg Haircut (%)"],
    cellLoc="center",
    loc="center",
)
table.auto_set_font_size(False)
table.set_fontsize(9)
table.auto_set_column_width(col=list(range(4)))

# Style header row
for col in range(4):
    table[(0, col)].set_facecolor("#2c3e50")
    table[(0, col)].set_text_props(color="white", fontweight="bold")

# Alternate row shading
for row in range(1, len(summary) + 1):
    colour = "#f2f2f2" if row % 2 == 0 else "white"
    for col in range(4):
        table[(row, col)].set_facecolor(colour)

ax_table.set_title(
    "Non-Treasury Repurchase Agreements from 2019–2020 Filings (N-MFP2)",
    fontsize=11, fontweight="bold", pad=12
)

footnotes = (
    "1. Only repurchase agreements with a single collateral type are considered.\n"
    "2. Haircut is calculated as the difference between sum of the collateral value "
    "and repo value over sum of collateral value.\n"
    "3. Observations with zero collateral value (n=76) are excluded.\n"
    "4. Observations with only U.S. Treasury collateral appear erroneous since parsing "
    "code should have explicitly filtered to repo agreements that were designated as Non-Treasury Repos."
)
ax_notes.text(0, 1, footnotes, fontsize=7.5, color="black",
              verticalalignment="top", transform=ax_notes.transAxes)

plt.tight_layout()

fig.savefig("summary_stats.png", dpi=150, bbox_inches="tight")
print("Saved to summary_stats.png")

# ── 5a. INTEREST RATE DISTRIBUTION OVER TIME — Corporate Debt Securities ──────
# Single-collateral Corporate Debt repos only; one row per repo.
df_cds = df_single[df_single["Collateral_category"] == "Corporate Debt Securities"]
df_cds_unique = (
    df_cds.drop_duplicates(subset="Repo_id")
    [["Repo_id", "Report_month", "Return"]]
)

monthly_stats = (
    df_cds_unique.groupby("Report_month")["Return"]
    .agg(
        avg=lambda x: x.mean() * 100,
        p5=lambda x: x.quantile(0.05) * 100,
        p95=lambda x: x.quantile(0.95) * 100,
    )
    .reset_index()
    .sort_values("Report_month")
)

fig2, ax = plt.subplots(figsize=(12, 5))

ax.plot(monthly_stats["Report_month"], monthly_stats["avg"],
        color="#2c3e50", linewidth=2, marker="o", markersize=4, label="Average")
ax.plot(monthly_stats["Report_month"], monthly_stats["p5"],
        color="#2980b9", linewidth=1.5, linestyle="--", marker="o", markersize=3, label="5th percentile")
ax.plot(monthly_stats["Report_month"], monthly_stats["p95"],
        color="#e74c3c", linewidth=1.5, linestyle="--", marker="o", markersize=3, label="95th percentile")

ax.fill_between(monthly_stats["Report_month"], monthly_stats["p5"], monthly_stats["p95"],
                alpha=0.08, color="#2c3e50")

ax.set_title("Corporate Debt Securities Repos — Interest Rate Distribution by Month",
             fontsize=11, fontweight="bold", pad=12)
ax.set_xlabel("Report Month", fontsize=9)
ax.set_ylabel("Interest Rate (%)", fontsize=9)
ax.tick_params(axis="x", rotation=45, labelsize=8)
ax.tick_params(axis="y", labelsize=8)
ax.legend(fontsize=9)
ax.grid(axis="y", linestyle="--", alpha=0.4)

plt.tight_layout()
fig2.savefig("cds_rate_by_month.png", dpi=150, bbox_inches="tight")
print("Saved to cds_rate_by_month.png")

# ── 5b. SPREAD (95th − 5th percentile) OVER TIME ─────────────────────────────
monthly_stats["spread"] = monthly_stats["p95"] - monthly_stats["p5"]

fig3, ax3 = plt.subplots(figsize=(12, 4))

ax3.bar(monthly_stats["Report_month"], monthly_stats["spread"],
        color="#2c3e50", alpha=0.75, width=0.6)

ax3.set_title("Corporate Debt Securities Repos — 95th–5th Percentile Rate Spread by Month",
              fontsize=11, fontweight="bold", pad=12)
ax3.set_xlabel("Report Month", fontsize=9)
ax3.set_ylabel("Spread (pp)", fontsize=9)
ax3.tick_params(axis="x", rotation=45, labelsize=8)
ax3.tick_params(axis="y", labelsize=8)
ax3.grid(axis="y", linestyle="--", alpha=0.4)

plt.tight_layout()
fig3.savefig("cds_spread_by_month.png", dpi=150, bbox_inches="tight")
print("Saved to cds_spread_by_month.png")

# ── 6a. INTEREST RATE DISTRIBUTION OVER TIME — Asset-Backed Securities ───────
df_abs = df_single[df_single["Collateral_category"] == "Asset-Backed Securities"]
df_abs_unique = (
    df_abs.drop_duplicates(subset="Repo_id")
    [["Repo_id", "Report_month", "Return"]]
)

monthly_abs = (
    df_abs_unique.groupby("Report_month")["Return"]
    .agg(
        avg=lambda x: x.mean() * 100,
        p5=lambda x: x.quantile(0.05) * 100,
        p95=lambda x: x.quantile(0.95) * 100,
    )
    .reset_index()
    .sort_values("Report_month")
)

fig4, ax4 = plt.subplots(figsize=(12, 5))

ax4.plot(monthly_abs["Report_month"], monthly_abs["avg"],
         color="#2c3e50", linewidth=2, marker="o", markersize=4, label="Average")
ax4.plot(monthly_abs["Report_month"], monthly_abs["p5"],
         color="#2980b9", linewidth=1.5, linestyle="--", marker="o", markersize=3, label="5th percentile")
ax4.plot(monthly_abs["Report_month"], monthly_abs["p95"],
         color="#e74c3c", linewidth=1.5, linestyle="--", marker="o", markersize=3, label="95th percentile")

ax4.fill_between(monthly_abs["Report_month"], monthly_abs["p5"], monthly_abs["p95"],
                 alpha=0.08, color="#2c3e50")

ax4.set_title("Asset-Backed Securities Repos — Interest Rate Distribution by Month",
              fontsize=11, fontweight="bold", pad=12)
ax4.set_xlabel("Report Month", fontsize=9)
ax4.set_ylabel("Interest Rate (%)", fontsize=9)
ax4.tick_params(axis="x", rotation=45, labelsize=8)
ax4.tick_params(axis="y", labelsize=8)
ax4.legend(fontsize=9)
ax4.grid(axis="y", linestyle="--", alpha=0.4)

plt.tight_layout()
fig4.savefig("abs_rate_by_month.png", dpi=150, bbox_inches="tight")
print("Saved to abs_rate_by_month.png")

# ── 6b. ABS SPREAD (95th − 5th percentile) OVER TIME ─────────────────────────
monthly_abs["spread"] = monthly_abs["p95"] - monthly_abs["p5"]

fig5, ax5 = plt.subplots(figsize=(12, 4))

ax5.bar(monthly_abs["Report_month"], monthly_abs["spread"],
        color="#2c3e50", alpha=0.75, width=0.6)

ax5.set_title("Asset-Backed Securities Repos — 95th–5th Percentile Rate Spread by Month",
              fontsize=11, fontweight="bold", pad=12)
ax5.set_xlabel("Report Month", fontsize=9)
ax5.set_ylabel("Spread (pp)", fontsize=9)
ax5.tick_params(axis="x", rotation=45, labelsize=8)
ax5.tick_params(axis="y", labelsize=8)
ax5.grid(axis="y", linestyle="--", alpha=0.4)

plt.tight_layout()
fig5.savefig("abs_spread_by_month.png", dpi=150, bbox_inches="tight")
print("Saved to abs_spread_by_month.png")

# ── 7. REPO COUNT BY COLLATERAL TYPE OVER TIME ────────────────────────────────
# One row per repo (deduplicate on Repo_id), pivot to a shared time axis so all
# lines are aligned, then drop categories with an average < 15 repos/month.
repo_type_month = (
    df_single.drop_duplicates(subset="Repo_id")
    .groupby(["Report_month", "Collateral_category"])["Repo_id"]
    .count()
    .reset_index(name="N_repos")
)

pivot = (
    repo_type_month.pivot(index="Report_month", columns="Collateral_category", values="N_repos")
    .fillna(0)
    .sort_index()
)

# Keep only categories that average >= 15 repos/month
pivot = pivot.loc[:, pivot.mean() >= 15]

fig6, ax6 = plt.subplots(figsize=(13, 6))

for cat in pivot.columns:
    ax6.plot(pivot.index, pivot[cat],
             linewidth=2, marker="o", markersize=4, label=cat)

ax6.set_title("Number of Repos by Collateral Type Over Time",
              fontsize=11, fontweight="bold", pad=12)
ax6.set_xlabel("Report Month", fontsize=9)
ax6.set_ylabel("Number of Repos", fontsize=9)
ax6.tick_params(axis="x", rotation=45, labelsize=8)
ax6.tick_params(axis="y", labelsize=8)
ax6.legend(fontsize=8, bbox_to_anchor=(1.01, 1), loc="upper left")
ax6.grid(axis="y", linestyle="--", alpha=0.4)

footnotes6 = (
    "1. Only repurchase agreements with a single collateral type are considered.\n"
    "2. Only collateral categories with an average of at least 15 observations per month are shown."
)

plt.tight_layout()
fig6.subplots_adjust(bottom=0.22)
fig6.text(0.01, 0.01, footnotes6, fontsize=7.5, color="black",
          verticalalignment="bottom", transform=fig6.transFigure)

fig6.savefig("repo_count_by_type.png", dpi=150, bbox_inches="tight")
print("Saved to repo_count_by_type.png")

# ── 8. COUNTERPARTY NAME EXHIBIT ──────────────────────────────────────────────
import re

raw_names = df.drop_duplicates(subset="Repo_id")["Repo_issuer"].dropna().unique()
raw_names = sorted(raw_names)

def normalise(name: str) -> str:
    """
    Normalise a raw counterparty name for grouping:
      1. Lowercase
      2. Strip parenthetical content (closed and unclosed)
      3. Replace separators (/ - ) with spaces so tokens split correctly
      4. Remove remaining punctuation
      5. Remove 'tri party repo' and 'non gov repo/rp' annotations
      6. Replace '&' with 'and'
      7. Drop standalone geographic qualifiers
      8. Drop legal-entity type suffixes
      9. Collapse whitespace
    """
    name = name.lower()
    name = re.sub(r"\(.*?\)", "", name)          # drop closed parentheticals
    name = re.sub(r"\([^)]*$", "", name)         # drop unclosed parentheticals
    name = re.sub(r"[/\-]", " ", name)           # / and - → space (word separators)
    name = re.sub(r"[.,;:()\\]", "", name)       # drop remaining punctuation
    name = re.sub(r"\btri\s*party\s*repo\b", "", name)
    name = re.sub(r"\bnon\s*gov\s*r[ep]+o?\b", "", name)
    name = re.sub(r"&", "and", name)
    name = re.sub(r"\b(paris|new york|york|toronto|london|ibf|branch)\b", "", name)
    name = re.sub(r"\b(llc|inc|incorporated|sa|plc|corp|ltd|limited|lp|na|ag)\b", "", name)
    name = re.sub(r"\s+", " ", name).strip()
    return name

# Priority-ordered rules: first match wins.
# More specific phrases must appear before shorter substrings (e.g. "bnp paribas" before "bnp").
ENTITY_RULES = [
    ("wells fargo",           "Wells Fargo"),
    ("wella fargo",           "Wells Fargo"),       # typo in source data
    ("barclays",              "Barclays"),
    ("bnp paribas",           "BNP Paribas"),
    ("bnp",                   "BNP Paribas"),
    ("citigroup",             "Citigroup"),
    ("jp morgan",             "JP Morgan"),
    ("jpm chase",             "JP Morgan"),
    ("hsbc",                  "HSBC"),
    ("societe generale",      "Societe Generale"),
    ("sg americas",           "Societe Generale"),
    ("bmo",                   "BMO"),
    ("mizuho",                "Mizuho"),
    ("mufg",                  "MUFG"),
    ("mitsubishi ufj",        "MUFG"),
    ("merrill lynch",         "Bank of America"),
    ("bofa",                  "Bank of America"),
    ("bank of america",       "Bank of America"),
    ("credit suisse",         "Credit Suisse"),
    ("credit agricole",       "Credit Agricole"),
    ("credit ag",             "Credit Agricole"),
    ("credit cib",            "Credit Agricole"),
    ("royal bank of canada",  "RBC"),
    ("rbc",                   "RBC"),
    ("dominion bank",         "TD"),
    ("td securities",         "TD"),
    ("td",                    "TD"),
    ("scotia capital",        "Scotiabank"),
    ("bank of nova scotia",   "Scotiabank"),
    ("ubs",                   "UBS"),
    ("morgan stanley",        "Morgan Stanley"),
    ("abn amro",              "ABN AMRO"),
    ("deutsche bank",         "Deutsche Bank"),
    ("standard chartered",    "Standard Chartered"),
    ("pershing",              "Pershing"),
    ("ing financial",         "ING"),
    ("ing funding",           "ING"),
    ("bank of montreal",      "BMO"),
    ("rbs securities",        "RBS"),
    ("fcstone",               "FCStone"),
    ("wachovia",              "Wachovia"),
    ("fixed income clearing", "FICC"),
    ("canadian imperial",     "CIBC"),
]
# Word-boundary matches for tokens that risk false substring hits
ENTITY_WB_RULES = [
    (r"\bbnp\b", "BNP Paribas"),
    (r"\bing\b",  "ING"),
]

def entity_name(normalised: str) -> str:
    for keyword, label in ENTITY_RULES:
        if keyword in normalised:
            return label
    for pattern, label in ENTITY_WB_RULES:
        if re.search(pattern, normalised):
            return label
    return normalised  # fallback: keep normalised form

counterparty_exhibit = pd.DataFrame({
    "Raw_name":        raw_names,
    "Normalised_name": [normalise(n) for n in raw_names],
})
counterparty_exhibit["Entity"] = counterparty_exhibit["Normalised_name"].apply(entity_name)
counterparty_exhibit = counterparty_exhibit.sort_values(["Entity", "Raw_name"]).reset_index(drop=True)

counterparty_exhibit.to_csv("counterparty_names.csv", index=False)
print(f"Saved to counterparty_names.csv ({len(counterparty_exhibit)} entries)")

# ── 9. AVERAGE EQUITIES INTEREST RATE BY ENTITY-MONTH ─────────────────────────
# Map raw Repo_issuer names to canonical entity labels, then compute average
# interest rate per entity per month. Missing months are left as NaN so the
# line chart shows a natural gap rather than interpolating.

issuer_to_entity = dict(zip(counterparty_exhibit["Raw_name"], counterparty_exhibit["Entity"]))

df_eq = df_single[df_single["Collateral_category"] == "Equities"]
df_eq_entity = df_eq.drop_duplicates(subset="Repo_id").copy()
df_eq_entity["Entity"] = df_eq_entity["Repo_issuer"].map(issuer_to_entity)

all_months = sorted(df_eq_entity["Report_month"].unique())

entity_monthly_rate = (
    df_eq_entity.groupby(["Entity", "Report_month"])["Return"]
    .mean()
    .mul(100)
    .unstack("Report_month")          # entities × months
    .reindex(columns=all_months)      # ensure full month range; missing → NaN
)

# Keep only entities present in both March and April 2020
entity_monthly_rate = entity_monthly_rate[
    entity_monthly_rate["2020-03"].notna() & entity_monthly_rate["2020-04"].notna()
]

fig10, ax10 = plt.subplots(figsize=(14, 6))

for entity, row in entity_monthly_rate.iterrows():
    ax10.plot(all_months, row.values,
              linewidth=1.8, marker="o", markersize=4, label=entity)

ax10.set_title("Average Equities Repo Interest Rate by Counterparty and Month",
               fontsize=11, fontweight="bold", pad=12)
ax10.set_xlabel("Report Month", fontsize=9)
ax10.set_ylabel("Average Interest Rate (%)", fontsize=9)
ax10.tick_params(axis="x", rotation=45, labelsize=8)
ax10.tick_params(axis="y", labelsize=8)
ax10.legend(fontsize=7.5, bbox_to_anchor=(1.01, 1), loc="upper left")
ax10.grid(axis="y", linestyle="--", alpha=0.4)

plt.tight_layout()
fig10.savefig("eq_rate_by_entity.png", dpi=150, bbox_inches="tight")
print("Saved to eq_rate_by_entity.png")

# ── 10. AVERAGE CDS INTEREST RATE BY ENTITY-MONTH ─────────────────────────────
df_cds_entity = df_single[df_single["Collateral_category"] == "Corporate Debt Securities"]
df_cds_entity = df_cds_entity.drop_duplicates(subset="Repo_id").copy()
df_cds_entity["Entity"] = df_cds_entity["Repo_issuer"].map(issuer_to_entity)

all_months_cds = sorted(df_cds_entity["Report_month"].unique())

entity_monthly_rate_cds = (
    df_cds_entity.groupby(["Entity", "Report_month"])["Return"]
    .mean()
    .mul(100)
    .unstack("Report_month")
    .reindex(columns=all_months_cds)
)

# Keep only entities present in both March and April 2020
entity_monthly_rate_cds = entity_monthly_rate_cds[
    entity_monthly_rate_cds["2020-03"].notna() & entity_monthly_rate_cds["2020-04"].notna()
]

fig11, ax11 = plt.subplots(figsize=(14, 6))

for entity, row in entity_monthly_rate_cds.iterrows():
    ax11.plot(all_months_cds, row.values,
              linewidth=1.8, marker="o", markersize=4, label=entity)

ax11.set_title("Average Corporate Debt Securities Repo Interest Rate by Counterparty and Month",
               fontsize=11, fontweight="bold", pad=12)
ax11.set_xlabel("Report Month", fontsize=9)
ax11.set_ylabel("Average Interest Rate (%)", fontsize=9)
ax11.tick_params(axis="x", rotation=45, labelsize=8)
ax11.tick_params(axis="y", labelsize=8)
ax11.legend(fontsize=7.5, bbox_to_anchor=(1.01, 1), loc="upper left")
ax11.grid(axis="y", linestyle="--", alpha=0.4)

plt.tight_layout()
fig11.savefig("cds_rate_by_entity.png", dpi=150, bbox_inches="tight")
print("Saved to cds_rate_by_entity.png")

# ── 10b. MAX−MIN AVERAGE RATE SPREAD ACROSS ENTITIES — CDS ───────────────────
cds_max_min = pd.DataFrame({
    "max": entity_monthly_rate_cds.max(),
    "min": entity_monthly_rate_cds.min(),
}).reindex(all_months_cds)
cds_max_min["spread"] = cds_max_min["max"] - cds_max_min["min"]

fig12, ax12 = plt.subplots(figsize=(13, 5))

ax12.plot(cds_max_min.index, cds_max_min["spread"],
          color="#2c3e50", linewidth=2, marker="o", markersize=4)
ax12.fill_between(cds_max_min.index, 0, cds_max_min["spread"],
                  alpha=0.12, color="#2c3e50")

ax12.set_title("Corporate Debt Securities Repos — Max−Min Average Rate Spread Across Counterparties by Month",
               fontsize=11, fontweight="bold", pad=12)
ax12.set_xlabel("Report Month", fontsize=9)
ax12.set_ylabel("Spread (pp)", fontsize=9)
ax12.tick_params(axis="x", rotation=45, labelsize=8)
ax12.tick_params(axis="y", labelsize=8)
ax12.grid(axis="y", linestyle="--", alpha=0.4)

plt.tight_layout()
fig12.savefig("cds_entity_spread_by_month.png", dpi=150, bbox_inches="tight")
print("Saved to cds_entity_spread_by_month.png")

# ── 11b. MAX−MIN AVERAGE RATE SPREAD ACROSS ENTITIES — Equities ──────────────
eq_max_min = pd.DataFrame({
    "max": entity_monthly_rate.max(),
    "min": entity_monthly_rate.min(),
}).reindex(all_months)
eq_max_min["spread"] = eq_max_min["max"] - eq_max_min["min"]

fig13, ax13 = plt.subplots(figsize=(13, 5))

ax13.plot(eq_max_min.index, eq_max_min["spread"],
          color="#e74c3c", linewidth=2, marker="o", markersize=4)
ax13.fill_between(eq_max_min.index, 0, eq_max_min["spread"],
                  alpha=0.12, color="#e74c3c")

ax13.set_title("Equities Repos — Max−Min Average Rate Spread Across Counterparties by Month",
               fontsize=11, fontweight="bold", pad=12)
ax13.set_xlabel("Report Month", fontsize=9)
ax13.set_ylabel("Spread (pp)", fontsize=9)
ax13.tick_params(axis="x", rotation=45, labelsize=8)
ax13.tick_params(axis="y", labelsize=8)
ax13.grid(axis="y", linestyle="--", alpha=0.4)

plt.tight_layout()
fig13.savefig("eq_entity_spread_by_month.png", dpi=150, bbox_inches="tight")
print("Saved to eq_entity_spread_by_month.png")

# ── 12. CDS ENTITY RATE DEVIATION FROM MONTHLY CROSS-ENTITY AVERAGE ──────────
# Monthly average across all entities (equal-weighted across entities, not repos)
cds_monthly_mean = entity_monthly_rate_cds.mean(axis=0)

# Deviation = entity rate − cross-entity mean
cds_deviations = entity_monthly_rate_cds.subtract(cds_monthly_mean, axis=1)

fig14, ax14 = plt.subplots(figsize=(14, 6))

for entity, row in cds_deviations.iterrows():
    ax14.plot(all_months_cds, row.values,
              linewidth=1.8, marker="o", markersize=4, label=entity)

ax14.axhline(0, color="black", linewidth=1, linestyle="--", alpha=0.5)

ax14.set_title("Corporate Debt Securities Repos — Entity Rate Deviation from Monthly Cross-Entity Average",
               fontsize=11, fontweight="bold", pad=12)
ax14.set_xlabel("Report Month", fontsize=9)
ax14.set_ylabel("Deviation from Monthly Mean (pp)", fontsize=9)
ax14.tick_params(axis="x", rotation=45, labelsize=8)
ax14.tick_params(axis="y", labelsize=8)
ax14.legend(fontsize=7.5, bbox_to_anchor=(1.01, 1), loc="upper left")
ax14.grid(axis="y", linestyle="--", alpha=0.4)

plt.tight_layout()
fig14.savefig("cds_entity_deviation_by_month.png", dpi=150, bbox_inches="tight")
print("Saved to cds_entity_deviation_by_month.png")

# ── 13. EQUITIES ENTITY RATE DEVIATION FROM MONTHLY CROSS-ENTITY AVERAGE ─────
eq_monthly_mean = entity_monthly_rate.mean(axis=0)
eq_deviations = entity_monthly_rate.subtract(eq_monthly_mean, axis=1)

fig15, ax15 = plt.subplots(figsize=(14, 6))

for entity, row in eq_deviations.iterrows():
    ax15.plot(all_months, row.values,
              linewidth=1.8, marker="o", markersize=4, label=entity)

ax15.axhline(0, color="black", linewidth=1, linestyle="--", alpha=0.5)

ax15.set_title("Equities Repos — Entity Rate Deviation from Monthly Cross-Entity Average",
               fontsize=11, fontweight="bold", pad=12)
ax15.set_xlabel("Report Month", fontsize=9)
ax15.set_ylabel("Deviation from Monthly Mean (pp)", fontsize=9)
ax15.tick_params(axis="x", rotation=45, labelsize=8)
ax15.tick_params(axis="y", labelsize=8)
ax15.legend(fontsize=7.5, bbox_to_anchor=(1.01, 1), loc="upper left")
ax15.grid(axis="y", linestyle="--", alpha=0.4)

plt.tight_layout()
fig15.savefig("eq_entity_deviation_by_month.png", dpi=150, bbox_inches="tight")
print("Saved to eq_entity_deviation_by_month.png")

# ── ANALYSIS OVERVIEW TABLE ───────────────────────────────────────────────────
overview_rows = [
    ("Setup",   "Load data; exclude zero collateral value (n=76); add Report_month",      "—"),
    ("1",       "Total unique repos",                                                       "Console"),
    ("2",       "Single- vs multi-collateral repos",                                        "Console"),
    ("3",       "Average yield by collateral type (single-type repos)",                     "Console"),
    ("4",       "Average haircut by collateral type (single-type repos)",                   "Console"),
    ("Table",   "Summary: N repos, avg yield, avg haircut by collateral type",              "summary_stats.png / .csv"),
    ("5a",      "CDS interest rate distribution over time (avg, p5, p95)",                  "cds_rate_by_month.png"),
    ("5b",      "CDS 95th−5th percentile rate spread over time",                            "cds_spread_by_month.png"),
    ("6a",      "ABS interest rate distribution over time (avg, p5, p95)",                  "abs_rate_by_month.png"),
    ("6b",      "ABS 95th−5th percentile rate spread over time",                            "abs_spread_by_month.png"),
    ("7",       "Repo count by collateral type over time (≥15 obs/month shown)",            "repo_count_by_type.png"),
    ("8",       "Counterparty name normalisation exhibit (raw → normalised → entity)",      "counterparty_names.csv"),
    ("9",       "Equities: avg interest rate by entity and month",                          "eq_rate_by_entity.png"),
    ("10",      "CDS: avg interest rate by entity and month",                               "cds_rate_by_entity.png"),
    ("10b",     "CDS: max−min average rate spread across entities by month",                "cds_entity_spread_by_month.png"),
    ("11b",     "Equities: max−min average rate spread across entities by month",           "eq_entity_spread_by_month.png"),
    ("12",      "CDS: entity rate deviation from monthly cross-entity average",             "cds_entity_deviation_by_month.png"),
    ("13",      "Equities: entity rate deviation from monthly cross-entity average",        "eq_entity_deviation_by_month.png"),
]

col_labels = ["Section", "Description", "Output"]
col_widths = [0.07, 0.62, 0.31]

fig_ov, ax_ov = plt.subplots(figsize=(16, 7))
ax_ov.axis("off")

tbl = ax_ov.table(
    cellText=overview_rows,
    colLabels=col_labels,
    cellLoc="left",
    loc="center",
    colWidths=col_widths,
)
tbl.auto_set_font_size(False)
tbl.set_fontsize(8.5)

for col in range(3):
    tbl[(0, col)].set_facecolor("#2c3e50")
    tbl[(0, col)].set_text_props(color="white", fontweight="bold")

for row in range(1, len(overview_rows) + 1):
    colour = "#f2f2f2" if row % 2 == 0 else "white"
    for col in range(3):
        tbl[(row, col)].set_facecolor(colour)
        tbl[(row, col)].set_text_props(ha="left")

ax_ov.set_title("Analysis Overview — Non-Treasury Repo Study (N-MFP2, 2019–2020)",
                fontsize=12, fontweight="bold", pad=14)

plt.tight_layout()
fig_ov.savefig("analysis_overview.png", dpi=150, bbox_inches="tight")
print("Saved to analysis_overview.png")
