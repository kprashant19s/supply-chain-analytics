"""
FILE: 01_ingest.py
PURPOSE: Read the raw DataCo CSV, normalize it into our 4-table
         star schema, and load it into MySQL.
RUN: python scripts/python/01_ingest.py
"""

import pandas as pd
from sqlalchemy import create_engine
from dotenv import load_dotenv
import os

# ── Load credentials from .env ──
load_dotenv()
engine = create_engine(
    f"mysql+pymysql://{os.getenv('DB_USER')}:{os.getenv('DB_PASSWORD')}"
    f"@{os.getenv('DB_HOST')}:{os.getenv('DB_PORT')}/{os.getenv('DB_NAME')}",
    echo=False
)

# ════════════════════════════════════════════════════════════
# STEP 1: Load raw CSV
# ════════════════════════════════════════════════════════════
print("📦 Loading CSV...")
df = pd.read_csv(
    "data/raw/DataCoSupplyChainDataset.csv",
    encoding="latin-1",
    low_memory=False
)
print(f"   Loaded {len(df):,} rows × {len(df.columns)} columns")

# Standardise column names
df.columns = (
    df.columns
    .str.strip()
    .str.lower()
    .str.replace(" ", "_", regex=False)
    .str.replace(r"[^a-z0-9_]", "", regex=True)
)

# ════════════════════════════════════════════════════════════
# STEP 2: Parse dates
# ════════════════════════════════════════════════════════════
df["order_date_dateorders"] = pd.to_datetime(
    df["order_date_dateorders"], errors="coerce"
)
df["shipping_date_dateorders"] = pd.to_datetime(
    df["shipping_date_dateorders"], errors="coerce"
)

# ════════════════════════════════════════════════════════════
# STEP 3: Build is_delayed flag
# ════════════════════════════════════════════════════════════
df["is_delayed"] = (
    df["days_for_shipping_real"] > df["days_for_shipment_scheduled"]
).astype(int)
print(f"   Delay rate: {df['is_delayed'].mean():.1%}")

# ════════════════════════════════════════════════════════════
# STEP 4: Build dimension tables
# Drop original IDs from raw CSV to avoid conflicts with
# our auto-increment primary keys
# ════════════════════════════════════════════════════════════
print("\n🔧 Building dimension tables...")

# ── dim_customer ──
# Drop raw customer_id — we generate our own auto-increment ID
dim_customer = df[[
    "customer_fname", "customer_lname", "customer_segment",
    "customer_city", "customer_state",
    "customer_country", "customer_zipcode"
]].drop_duplicates().reset_index(drop=True)
dim_customer.index += 1
dim_customer.index.name = "customer_id"
dim_customer = dim_customer.reset_index()
print(f"   dim_customer: {len(dim_customer):,} unique customers")

# ── dim_product ──
dim_product = df[[
    "product_name", "category_name",
    "product_price", "department_name"
]].drop_duplicates().reset_index(drop=True)
dim_product = dim_product.rename(columns={"category_name": "product_category"})
dim_product.index += 1
dim_product.index.name = "product_id"
dim_product = dim_product.reset_index()
print(f"   dim_product: {len(dim_product):,} unique products")

# ── dim_supplier ──
dim_supplier = df[[
    "market", "order_region", "shipping_mode"
]].drop_duplicates().reset_index(drop=True)
dim_supplier.index += 1
dim_supplier.index.name = "supplier_id"
dim_supplier = dim_supplier.reset_index()
print(f"   dim_supplier: {len(dim_supplier):,} unique supplier routes")

# ════════════════════════════════════════════════════════════
# STEP 5: Build fact table using manual lookups
# We avoid merge conflicts by doing explicit lookup joins
# ════════════════════════════════════════════════════════════
print("\n🔗 Building fact table...")

# Create lookup dictionaries for fast FK resolution
cust_lookup = dim_customer.set_index([
    "customer_fname", "customer_lname", "customer_segment",
    "customer_city", "customer_state",
    "customer_country", "customer_zipcode"
])["customer_id"]

prod_lookup = dim_product.set_index([
    "product_name", "product_category",
    "product_price", "department_name"
])["product_id"]

supp_lookup = dim_supplier.set_index([
    "market", "order_region", "shipping_mode"
])["supplier_id"]

# Resolve customer FK
df["cust_fk"] = pd.MultiIndex.from_frame(df[[
    "customer_fname", "customer_lname", "customer_segment",
    "customer_city", "customer_state",
    "customer_country", "customer_zipcode"
]]).map(cust_lookup.to_dict())

# Resolve product FK
df["prod_fk"] = pd.MultiIndex.from_frame(df[[
    "product_name", "category_name",
    "product_price", "department_name"
]].rename(columns={"category_name": "product_category"})).map(
    prod_lookup.to_dict()
)

# Resolve supplier FK
df["supp_fk"] = pd.MultiIndex.from_frame(df[[
    "market", "order_region", "shipping_mode"
]]).map(supp_lookup.to_dict())

# Build final fact table with clean column names
fact_orders = pd.DataFrame({
    "order_id":               df["order_id"],
    "customer_id":            df["cust_fk"],
    "product_id":             df["prod_fk"],
    "supplier_id":            df["supp_fk"],
    "order_date":             df["order_date_dateorders"],
    "shipping_date":          df["shipping_date_dateorders"],
    "scheduled_ship_days":    df["days_for_shipment_scheduled"],
    "actual_ship_days":       df["days_for_shipping_real"],
    "sales_per_order":        df["sales"],
    "order_profit_per_order": df["order_profit_per_order"],
    "order_item_discount":    df["order_item_discount"],
    "order_item_quantity":    df["order_item_quantity"],
    "is_delayed":             df["is_delayed"],
    "delivery_status":        df["delivery_status"],
    "late_delivery_risk":     df["late_delivery_risk"],
})
print(f"   fact_orders: {len(fact_orders):,} rows ready")

# ════════════════════════════════════════════════════════════
# STEP 6: Write to MySQL
# ════════════════════════════════════════════════════════════
print("\n💾 Writing to MySQL...")

dim_customer.to_sql("dim_customer", engine,
    if_exists="append", index=False)
print("   ✓ dim_customer loaded")

dim_product.to_sql("dim_product", engine,
    if_exists="append", index=False)
print("   ✓ dim_product loaded")

dim_supplier.to_sql("dim_supplier", engine,
    if_exists="append", index=False)
print("   ✓ dim_supplier loaded")

# Load fact table in chunks to avoid timeout
CHUNK = 10_000
for i in range(0, len(fact_orders), CHUNK):
    fact_orders.iloc[i:i+CHUNK].to_sql(
        "fact_orders", engine,
        if_exists="append", index=False
    )
    print(
        f"   fact_orders: "
        f"{min(i+CHUNK, len(fact_orders)):,} / {len(fact_orders):,} rows",
        end="\r"
    )

print("\n   ✓ fact_orders loaded")
print("\n✅ Ingestion complete. All 4 tables populated.")