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
