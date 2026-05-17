"""
FILE: 02_eda.py
PURPOSE: Production script version of the EDA notebook.
         Runs the full EDA pipeline end-to-end without
         needing Jupyter — ideal for automation and CI/CD.
RUN: python scripts/python/02_eda.py
"""

import pandas as pd
import numpy as np
import matplotlib.pyplot as plt
import matplotlib.ticker as mticker
import seaborn as sns
from matplotlib.patches import Patch
from sqlalchemy import create_engine
from dotenv import load_dotenv
import os
import warnings

warnings.filterwarnings("ignore")

# ════════════════════════════════════════════════════════════
# SETUP
# ════════════════════════════════════════════════════════════

# ── Load credentials from .env ──
load_dotenv()
engine = create_engine(
    f"mysql+pymysql://{os.getenv('DB_USER')}:{os.getenv('DB_PASSWORD')}"
    f"@{os.getenv('DB_HOST')}:{os.getenv('DB_PORT')}/{os.getenv('DB_NAME')}",
    echo=False
)

# ── Global chart style ──
sns.set_theme(style="whitegrid", palette="muted", font_scale=1.2)
plt.rcParams["figure.dpi"]         = 150
plt.rcParams["figure.figsize"]     = (12, 5)
plt.rcParams["axes.spines.top"]    = False
plt.rcParams["axes.spines.right"]  = False

# ── Output directories ──
IMAGES_DIR    = "images/"
PROCESSED_DIR = "data/processed/"
os.makedirs(IMAGES_DIR,    exist_ok=True)
os.makedirs(PROCESSED_DIR, exist_ok=True)

# ════════════════════════════════════════════════════════════
# STEP 1: Load data from MySQL
# ════════════════════════════════════════════════════════════
print("📦 Loading data from MySQL...")

df = pd.read_sql("""
    SELECT
        fo.*,
        dc.customer_fname,
        dc.customer_lname,
        dc.customer_segment,
        dc.customer_city,
        dc.customer_country,
        dp.product_name,
        dp.product_category,
        dp.department_name,
        ds.market,
        ds.order_region,
        ds.shipping_mode
    FROM fact_orders fo
    JOIN dim_customer dc ON fo.customer_id = dc.customer_id
    JOIN dim_product  dp ON fo.product_id  = dp.product_id
    JOIN dim_supplier ds ON fo.supplier_id = ds.supplier_id
""", engine)

print(f"   ✅ Loaded {len(df):,} rows × {len(df.columns)} columns")

# ════════════════════════════════════════════════════════════
# STEP 2: Data cleaning & feature engineering
# ════════════════════════════════════════════════════════════
print("\n🔧 Cleaning data...")

df["order_date"]    = pd.to_datetime(df["order_date"])
df["shipping_date"] = pd.to_datetime(df["shipping_date"])

# Extract time features
df["order_year"]       = df["order_date"].dt.year
df["order_month"]      = df["order_date"].dt.month
df["order_month_name"] = df["order_date"].dt.strftime("%b")
df["order_quarter"]    = df["order_date"].dt.quarter
df["order_dayofweek"]  = df["order_date"].dt.day_name()

# Engineer key metrics
df["delay_days"] = (
    df["actual_ship_days"] - df["scheduled_ship_days"]
)
df["profit_margin_pct"] = (
    df["order_profit_per_order"] /
    df["sales_per_order"].replace(0, np.nan) * 100
).round(2)

df["revenue_band"] = pd.cut(
    df["sales_per_order"],
    bins=[0, 50, 150, 300, 500, float("inf")],
    labels=["<$50", "$50-150", "$150-300", "$300-500", "$500+"]
)

df["delivery_status"] = df["delivery_status"].str.strip().str.title()

# Drop null dates
before = len(df)
df = df.dropna(subset=["order_date", "shipping_date"])
print(f"   Dropped {before - len(df)} rows with null dates")
print(f"   ✅ Final shape: {df.shape[0]:,} rows × {df.shape[1]} columns")

# ════════════════════════════════════════════════════════════
# STEP 3: Chart 1 — Delay Rate by Shipping Mode
# ════════════════════════════════════════════════════════════
print("\n📊 Generating charts...")
print("   Chart 1: Delay Rate by Shipping Mode")

fig, ax = plt.subplots(figsize=(10, 5))

delay_by_mode = (
    df.groupby("shipping_mode")["is_delayed"]
    .mean().mul(100).round(2)
    .sort_values(ascending=True).reset_index()
)
delay_by_mode.columns = ["shipping_mode", "delay_rate_pct"]

colors = ["#2ecc71" if x < 40 else "#e67e22" if x < 60 else "#e74c3c"
          for x in delay_by_mode["delay_rate_pct"]]

bars = ax.barh(
    delay_by_mode["shipping_mode"],
    delay_by_mode["delay_rate_pct"],
    color=colors, edgecolor="white", height=0.5
)
for bar, val in zip(bars, delay_by_mode["delay_rate_pct"]):
    ax.text(
        bar.get_width() + 0.5,
        bar.get_y() + bar.get_height() / 2,
        f"{val}%", va="center", fontsize=11, fontweight="bold"
    )

ax.set_xlabel("Delay Rate (%)", fontsize=12)
ax.set_title("Delay Rate by Shipping Mode",
             fontsize=14, fontweight="bold", pad=15)
ax.set_xlim(0, 110)
ax.axvline(x=50, color="gray", linestyle="--",
           alpha=0.5, label="50% threshold")
ax.legend()
plt.tight_layout()
plt.savefig(f"{IMAGES_DIR}01_delay_by_shipping_mode.png",
            dpi=150, bbox_inches="tight")
plt.close()

# ════════════════════════════════════════════════════════════
# STEP 4: Chart 2 — Monthly Revenue & Delay Trend
# ════════════════════════════════════════════════════════════
print("   Chart 2: Monthly Revenue & Delay Trend")

fig, ax1 = plt.subplots(figsize=(14, 6))

monthly = (
    df.groupby(["order_year", "order_month"])
    .agg(
        total_revenue  = ("sales_per_order",       "sum"),
        delay_rate_pct = ("is_delayed",            "mean")
    ).reset_index()
)
monthly["delay_rate_pct"] = (monthly["delay_rate_pct"] * 100).round(2)
monthly["month_label"] = (
    monthly["order_year"].astype(str) + "-" +
    monthly["order_month"].astype(str).str.zfill(2)
)

ax1.bar(monthly["month_label"], monthly["total_revenue"],
        color="#3498db", alpha=0.6, label="Monthly Revenue")
ax1.set_ylabel("Revenue ($)", fontsize=12, color="#3498db")
ax1.tick_params(axis="x", rotation=45)
ax1.yaxis.set_major_formatter(
    mticker.FuncFormatter(lambda x, _: f"${x:,.0f}")
)

ax2 = ax1.twinx()
ax2.plot(monthly["month_label"], monthly["delay_rate_pct"],
         color="#e74c3c", linewidth=2.5,
         marker="o", markersize=4, label="Delay Rate %")
ax2.set_ylabel("Delay Rate (%)", fontsize=12, color="#e74c3c")
ax2.set_ylim(0, 100)

lines1, labels1 = ax1.get_legend_handles_labels()
lines2, labels2 = ax2.get_legend_handles_labels()
ax1.legend(lines1 + lines2, labels1 + labels2, loc="upper left")
ax1.set_title("Monthly Revenue vs Delay Rate Trend",
              fontsize=14, fontweight="bold", pad=15)

plt.tight_layout()
plt.savefig(f"{IMAGES_DIR}02_monthly_revenue_delay_trend.png",
            dpi=150, bbox_inches="tight")
plt.close()

# ════════════════════════════════════════════════════════════
# STEP 5: Chart 3 — Profit Margin by Customer Segment
# ════════════════════════════════════════════════════════════
print("   Chart 3: Profit Margin by Customer Segment")

fig, axes = plt.subplots(1, 2, figsize=(16, 6))

segment_margin = (
    df.groupby("customer_segment")
    .agg(
        total_revenue = ("sales_per_order",       "sum"),
        total_profit  = ("order_profit_per_order", "sum"),
        avg_discount  = ("order_item_discount",    "mean")
    ).reset_index()
)
segment_margin["profit_margin_pct"] = (
    segment_margin["total_profit"] /
    segment_margin["total_revenue"] * 100
).round(2)

colors = ["#2ecc71" if x > 0 else "#e74c3c"
          for x in segment_margin["profit_margin_pct"]]

bars = axes[0].bar(
    segment_margin["customer_segment"],
    segment_margin["profit_margin_pct"],
    color=colors, edgecolor="white", width=0.5
)
for bar, val in zip(bars, segment_margin["profit_margin_pct"]):
    axes[0].text(
        bar.get_x() + bar.get_width() / 2,
        bar.get_height() + 0.3,
        f"{val}%", ha="center",
        fontsize=11, fontweight="bold"
    )
axes[0].set_title("Profit Margin % by Customer Segment",
                  fontsize=13, fontweight="bold")
axes[0].set_xlabel("Customer Segment", fontsize=11)
axes[0].set_ylabel("Profit Margin (%)", fontsize=11)
axes[0].axhline(y=0, color="black", linewidth=0.8)

axes[1].bar(
    segment_margin["customer_segment"],
    segment_margin["avg_discount"],
    color="#e67e22", edgecolor="white", width=0.5
)
for i, (_, disc) in enumerate(
    zip(segment_margin["customer_segment"],
        segment_margin["avg_discount"])
):
    axes[1].text(
        i, disc + 0.2, f"${disc:.1f}",
        ha="center", fontsize=11, fontweight="bold"
    )
axes[1].set_title("Average Discount by Customer Segment",
                  fontsize=13, fontweight="bold")
axes[1].set_xlabel("Customer Segment", fontsize=11)
axes[1].set_ylabel("Average Discount ($)", fontsize=11)

plt.suptitle("Customer Segment: Profitability vs Discount Analysis",
             fontsize=15, fontweight="bold", y=1.02)
plt.tight_layout()
plt.savefig(f"{IMAGES_DIR}03_profit_margin_by_segment.png",
            dpi=150, bbox_inches="tight")
plt.close()

# ════════════════════════════════════════════════════════════
# STEP 6: Chart 4 — Delay Heatmap
# ════════════════════════════════════════════════════════════
print("   Chart 4: Delay Heatmap by Market & Shipping")

fig, ax = plt.subplots(figsize=(12, 6))

heatmap_data = (
    df.groupby(["market", "shipping_mode"])["is_delayed"]
    .mean().mul(100).round(2).reset_index()
    .pivot(index="market", columns="shipping_mode",
           values="is_delayed")
)

sns.heatmap(
    heatmap_data, annot=True, fmt=".1f",
    cmap="RdYlGn_r", linewidths=0.5,
    linecolor="white",
    cbar_kws={"label": "Delay Rate (%)"},
    ax=ax, vmin=0, vmax=100
)
ax.set_title("Delay Rate Heatmap — Market vs Shipping Mode",
             fontsize=14, fontweight="bold", pad=15)
ax.set_xlabel("Shipping Mode", fontsize=12)
ax.set_ylabel("Market", fontsize=12)
ax.tick_params(axis="x", rotation=30)
ax.tick_params(axis="y", rotation=0)

plt.tight_layout()
plt.savefig(f"{IMAGES_DIR}04_delay_heatmap_market_shipping.png",
            dpi=150, bbox_inches="tight")
plt.close()

# ════════════════════════════════════════════════════════════
# STEP 7: Chart 5 — Top 10 High Risk Supplier Routes
# FIX: Switched to horizontal bar chart — bubble chart was
#      unreadable due to all points clustering at 100% delay
# CHART TYPE: Dual horizontal bar chart
# ════════════════════════════════════════════════════════════
print("   Chart 5: Top 10 High Risk Supplier Routes")

fig, axes = plt.subplots(1, 2, figsize=(18, 8))

# ── Aggregate supplier route metrics ──
supplier_risk = (
    df.groupby(["market", "order_region", "shipping_mode"])
    .agg(
        total_orders   = ("order_id",        "count"),
        delay_rate_pct = ("is_delayed",      "mean"),
        total_revenue  = ("sales_per_order", "sum"),
        avg_days_late  = ("delay_days",      "mean")
    ).reset_index()
)
supplier_risk["delay_rate_pct"] = (
    supplier_risk["delay_rate_pct"] * 100
).round(2)

# Risk score = delay rate × log(volume)
# Penalises high-volume delays more than low-volume ones
supplier_risk["risk_score"] = (
    supplier_risk["delay_rate_pct"] *
    np.log(supplier_risk["total_orders"])
).round(2)

# Revenue at risk = revenue × delay rate
supplier_risk["revenue_at_risk"] = (
    supplier_risk["total_revenue"] *
    supplier_risk["delay_rate_pct"] / 100
).round(2)

# Filter high volume routes only
supplier_risk = supplier_risk[supplier_risk["total_orders"] > 100]

# Top 10 by risk score
top10 = supplier_risk.nlargest(10, "risk_score").copy()
top10["route_label"] = (
    top10["order_region"] + " — " + top10["shipping_mode"]
)
# Sort ascending so highest risk appears at top
top10 = top10.sort_values("risk_score", ascending=True)

# Color by market
markets   = top10["market"].unique()
palette   = ["#e74c3c", "#3498db", "#2ecc71", "#f39c12", "#9b59b6"]
color_map = {m: palette[i] for i, m in enumerate(markets)}
colors    = top10["market"].map(color_map)

# ── LEFT: Risk Score bar chart ──
bars1 = axes[0].barh(
    top10["route_label"],
    top10["risk_score"],
    color=colors, edgecolor="white", height=0.6
)
for bar, val in zip(bars1, top10["risk_score"]):
    axes[0].text(
        bar.get_width() + 0.5,
        bar.get_y() + bar.get_height() / 2,
        f"{val:.1f}",
        va="center", fontsize=9, fontweight="bold"
    )
axes[0].set_xlabel("Risk Score", fontsize=11)
axes[0].set_title(
    "Top 10 Routes by Risk Score",
    fontsize=13, fontweight="bold"
)
axes[0].tick_params(axis="y", labelsize=9)
legend_elements = [
    Patch(facecolor=color_map[m], label=m) for m in markets
]
axes[0].legend(
    handles=legend_elements,
    title="Market", loc="lower right", fontsize=9
)

# ── RIGHT: Revenue at Risk bar chart ──
bars2 = axes[1].barh(
    top10["route_label"],
    top10["revenue_at_risk"] / 1_000_000,
    color=colors, edgecolor="white", height=0.6
)
for bar, val in zip(bars2, top10["revenue_at_risk"]):
    axes[1].text(
        bar.get_width() + 0.01,
        bar.get_y() + bar.get_height() / 2,
        f"${val/1_000_000:.2f}M",
        va="center", fontsize=9, fontweight="bold"
    )
axes[1].set_xlabel("Revenue at Risk ($M)", fontsize=11)
axes[1].set_title(
    "Top 10 Routes by Revenue at Risk",
    fontsize=13, fontweight="bold"
)
axes[1].tick_params(axis="y", labelsize=9)

plt.suptitle(
    "High Risk Supplier Route Analysis",
    fontsize=15, fontweight="bold", y=1.02
)
plt.tight_layout()
plt.savefig(
    f"{IMAGES_DIR}05_top10_high_risk_supplier_routes.png",
    dpi=150, bbox_inches="tight"
)
plt.close()

# ════════════════════════════════════════════════════════════
# STEP 8: Chart 6 — Discount vs Profit Correlation
# ════════════════════════════════════════════════════════════
print("   Chart 6: Discount vs Profit Correlation")

fig, axes = plt.subplots(1, 2, figsize=(20, 8))

sample = df.sample(n=5000, random_state=42)
colors = sample["is_delayed"].map({0: "#2ecc71", 1: "#e74c3c"})

axes[0].scatter(
    sample["order_item_discount"],
    sample["order_profit_per_order"],
    c=colors, alpha=0.4, s=15
)
z = np.polyfit(
    sample["order_item_discount"],
    sample["order_profit_per_order"], 1
)
p = np.poly1d(z)
x_line = np.linspace(
    sample["order_item_discount"].min(),
    sample["order_item_discount"].max(), 100
)
axes[0].plot(x_line, p(x_line), color="#2c3e50",
             linewidth=2, linestyle="--", label="Trend line")

corr = sample["order_item_discount"].corr(
    sample["order_profit_per_order"]
)
axes[0].text(
    0.05, 0.95, f"Correlation: {corr:.3f}",
    transform=axes[0].transAxes,
    fontsize=11, fontweight="bold",
    verticalalignment="top",
    bbox=dict(boxstyle="round", facecolor="wheat", alpha=0.5)
)
legend_elements = [
    Patch(facecolor="#2ecc71", label="On Time"),
    Patch(facecolor="#e74c3c", label="Delayed")
]
axes[0].legend(handles=legend_elements, loc="upper right")
axes[0].set_xlabel("Discount Amount ($)", fontsize=11)
axes[0].set_ylabel("Profit per Order ($)", fontsize=11)
axes[0].set_title("Discount vs Profit Correlation",
                  fontsize=13, fontweight="bold")
axes[0].axhline(y=0, color="black", linewidth=0.8, alpha=0.5)

cat_margin = (
    df.groupby("product_category")
    .agg(
        total_revenue = ("sales_per_order",       "sum"),
        total_profit  = ("order_profit_per_order", "sum")
    ).reset_index()
)
cat_margin["profit_margin_pct"] = (
    cat_margin["total_profit"] /
    cat_margin["total_revenue"] * 100
).round(2)
cat_margin = cat_margin.sort_values("profit_margin_pct", ascending=True)
cat_margin["product_category"] = (
    cat_margin["product_category"].str[:25]
)

bar_colors = [
    "#e74c3c" if x < 0 else "#3498db"
    for x in cat_margin["profit_margin_pct"]
]
axes[1].barh(
    cat_margin["product_category"],
    cat_margin["profit_margin_pct"],
    color=bar_colors, edgecolor="white", height=0.6
)
axes[1].axvline(x=0, color="black", linewidth=0.8)
axes[1].set_xlabel("Profit Margin (%)", fontsize=11)
axes[1].set_title("Profit Margin % by Product Category",
                  fontsize=13, fontweight="bold")
axes[1].tick_params(axis="y", labelsize=9)

plt.suptitle("Pricing & Profitability Deep Dive",
             fontsize=15, fontweight="bold", y=1.02)
plt.tight_layout()
plt.savefig(f"{IMAGES_DIR}06_discount_profit_correlation.png",
            dpi=150, bbox_inches="tight")
plt.close()

# ════════════════════════════════════════════════════════════
# STEP 9: Export summary CSVs
# ════════════════════════════════════════════════════════════
print("\n💾 Exporting summary CSVs...")

# Monthly KPI
monthly_kpi = (
    df.groupby(["order_year", "order_month", "order_month_name"])
    .agg(
        total_revenue  = ("sales_per_order",       "sum"),
        total_profit   = ("order_profit_per_order", "sum"),
        total_orders   = ("order_id",              "count"),
        delay_rate_pct = ("is_delayed",            "mean"),
        avg_days_late  = ("delay_days",            "mean")
    ).reset_index()
)
monthly_kpi["delay_rate_pct"] = (
    monthly_kpi["delay_rate_pct"] * 100
).round(2)
monthly_kpi["profit_margin_pct"] = (
    monthly_kpi["total_profit"] /
    monthly_kpi["total_revenue"] * 100
).round(2)
monthly_kpi.to_csv(f"{PROCESSED_DIR}monthly_kpi.csv", index=False)
print("   ✅ monthly_kpi.csv saved")

# Supplier scorecard
supplier_scorecard = (
    df.groupby(["market", "order_region", "shipping_mode"])
    .agg(
        total_orders   = ("order_id",               "count"),
        delay_rate_pct = ("is_delayed",             "mean"),
        total_revenue  = ("sales_per_order",        "sum"),
        total_profit   = ("order_profit_per_order", "sum"),
        avg_days_late  = ("delay_days",             "mean")
    ).reset_index()
)
supplier_scorecard["delay_rate_pct"] = (
    supplier_scorecard["delay_rate_pct"] * 100
).round(2)
supplier_scorecard["revenue_at_risk"] = (
    supplier_scorecard["total_revenue"] *
    supplier_scorecard["delay_rate_pct"] / 100
).round(2)
supplier_scorecard["risk_score"] = (
    supplier_scorecard["delay_rate_pct"] *
    np.log(supplier_scorecard["total_orders"])
).round(2)
supplier_scorecard["risk_category"] = pd.cut(
    supplier_scorecard["delay_rate_pct"],
    bins=[0, 30, 50, 70, 100],
    labels=["Low", "Medium", "High", "Critical"]
)
supplier_scorecard.to_csv(
    f"{PROCESSED_DIR}supplier_scorecard.csv", index=False
)
print("   ✅ supplier_scorecard.csv saved")

# Segment summary
segment_summary = (
    df.groupby(["customer_segment", "product_category"])
    .agg(
        total_orders   = ("order_id",               "count"),
        total_revenue  = ("sales_per_order",        "sum"),
        total_profit   = ("order_profit_per_order", "sum"),
        avg_discount   = ("order_item_discount",    "mean"),
        delay_rate_pct = ("is_delayed",             "mean")
    ).reset_index()
)
segment_summary["delay_rate_pct"] = (
    segment_summary["delay_rate_pct"] * 100
).round(2)
segment_summary["profit_margin_pct"] = (
    segment_summary["total_profit"] /
    segment_summary["total_revenue"] * 100
).round(2)
segment_summary.to_csv(
    f"{PROCESSED_DIR}segment_summary.csv", index=False
)
print("   ✅ segment_summary.csv saved")

# Full cleaned dataset
df.to_csv(f"{PROCESSED_DIR}supply_chain_cleaned.csv", index=False)
print("   ✅ supply_chain_cleaned.csv saved")

# ════════════════════════════════════════════════════════════
# FINAL SUMMARY
# ════════════════════════════════════════════════════════════
print("\n" + "=" * 55)
print("✅ EDA PIPELINE COMPLETE")
print("=" * 55)
print(f"   Rows processed:   {len(df):,}")
print(f"   Charts generated: 6")
print(f"   CSVs exported:    4")
print(f"   Images saved to:  {IMAGES_DIR}")
print(f"   Data saved to:    {PROCESSED_DIR}")