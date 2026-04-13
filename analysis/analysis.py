# -*- coding: utf-8 -*-
"""
Statistical analysis of Repo_non_treasury.csv.

- Total number of unique repos
- Number of repos with only one collateral type
- Average repo yield per collateral type
"""

import pandas as pd

df = pd.read_csv("Repo_non_treasury.csv")
df["Return"] = pd.to_numeric(df["Return"], errors="coerce")

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
df["Collateral_value"]   = pd.to_numeric(df["Collateral_value"],   errors="coerce")
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
