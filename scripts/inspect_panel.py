"""Quick inspection of topic1_panel.csv for the thesis data section."""
import pandas as pd

pd.set_option("display.width", 200)
pd.set_option("display.max_columns", 100)

df = pd.read_csv("topic1_battery_arbitrage/data/topic1_panel.csv", index_col=0, parse_dates=True)

print("SHAPE:", df.shape)
print("RANGE:", df.index.min(), "->", df.index.max())
print("\nCOLUMNS:")
for c in df.columns:
    print(" ", c)

print("\nMISSING %:")
print((df.isnull().mean() * 100).round(2).sort_values(ascending=False).to_string())

price = df["ote_price_eur_mwh"]
print("\nOTE PRICE STATS:")
print(price.describe().round(2).to_string())

neg = price < 0
print("\nNEGATIVE PRICE HOURS BY YEAR:")
print(neg.groupby(df.index.year).sum().to_string())
print("\nNEG SHARE BY YEAR (%):")
print((neg.groupby(df.index.year).mean() * 100).round(2).to_string())

print("\nNEG HOURS BY MONTH (all years):")
print(neg.groupby(df.index.month).sum().to_string())

print("\nNEG HOURS BY HOUR OF DAY (all years):")
print(neg.groupby(df.index.hour).sum().to_string())

# price percentiles by year
print("\nPRICE STATS BY YEAR:")
print(df.groupby(df.index.year)["ote_price_eur_mwh"].agg(["mean", "std", "min", "max", lambda s: (s < 0).sum()]).round(1).to_string())

# cross-check OTE vs ENTSO-E CZ
if "entsoe_cz_da_eur_mwh" in df.columns:
    both = df[["ote_price_eur_mwh", "entsoe_cz_da_eur_mwh"]].dropna()
    print("\nOTE vs ENTSOE CZ corr:", both.corr().iloc[0, 1].round(5), " n =", len(both))
    print("mean abs diff:", (both["ote_price_eur_mwh"] - both["entsoe_cz_da_eur_mwh"]).abs().mean().round(3))

# DE correlation
if "entsoe_de_da_eur_mwh" in df.columns:
    both = df[["ote_price_eur_mwh", "entsoe_de_da_eur_mwh"]].dropna()
    print("CZ vs DE corr:", both.corr().iloc[0, 1].round(4), " n =", len(both))

# solar stats
for c in ["ceps_res_fve_mw", "ceps_res_vte_mw"]:
    if c in df.columns:
        print(f"\n{c} max by year:")
        print(df.groupby(df.index.year)[c].max().round(0).to_string())

# residual load feasibility
load_cols = [c for c in df.columns if "load" in c]
print("\nLOAD COLUMNS:", load_cols)
