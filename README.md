# 🚚 Global Supply Chain Risk & Delay Analytics

![Python](https://img.shields.io/badge/Python-3.12-blue)
![MySQL](https://img.shields.io/badge/MySQL-9.4-orange)
![Pandas](https://img.shields.io/badge/Pandas-3.0.3-green)
![Seaborn](https://img.shields.io/badge/Seaborn-0.13.2-teal)
![Status](https://img.shields.io/badge/Status-Complete-brightgreen)

## 📌 Project Overview

An end-to-end data analytics project analyzing **180,519 supply chain orders** across 5 global markets to identify delivery bottlenecks, revenue at risk, and supplier performance gaps.

**Key Finding:** 57.3% of all shipments are delayed — costing an estimated **$21M in revenue at risk.**

---

## 🎯 Business Questions Answered

- Which shipping modes and markets have the worst on-time delivery rate?
- How does delay rate correlate with revenue and profit over time?
- Which customer segments are most profitable after discounts?
- Which supplier routes pose the highest operational risk?
- Do higher discounts actually destroy profit margins?

---

## 🛠️ Tech Stack

| Layer | Tool |
|---|---|
| Database | MySQL 9.4 |
| Ingestion | Python 3.12 + SQLAlchemy |
| EDA & Cleaning | Pandas, NumPy |
| Visualization | Seaborn, Matplotlib |
| IDE | VS Code |
| Version Control | Git + GitHub |

---

## 📁 Project Structure 

supply_chain_analytics/
├── data/
│   ├── raw/                          ← original Kaggle CSV
│   └── processed/
│       ├── supply_chain_cleaned.csv  ← cleaned dataset
│       ├── monthly_kpi.csv           ← monthly KPI summary
│       ├── supplier_scorecard.csv    ← supplier risk scores
│       └── segment_summary.csv      ← customer segments
├── scripts/
│   ├── sql/
│   │   ├── 01_schema.sql            ← star schema DDL
│   │   └── 02_queries.sql           ← analytical queries
│   └── python/
│       ├── 01_ingest.py             ← CSV → MySQL pipeline
│       └── 02_eda.py                ← EDA script
├── notebooks/
│   └── eda_notebook.ipynb           ← full EDA notebook
├── images/                          ← all chart exports
├── reports/                         ← final reports
├── .gitignore
└── README.md

---

## 🗄️ Database Schema (Star Schema)

dim_customer ──┐
dim_product  ──┤── fact_orders
dim_supplier ──┘

| Table | Rows | Description |
|---|---|---|
| dim_customer | 18,963 | Unique customer profiles |
| dim_product | 118 | Product SKUs and categories |
| dim_supplier | 92 | Market + region + shipping mode |
| fact_orders | 180,519 | Order line items (grain) |

---

## 📊 Key Findings

### 1. Delay Rate by Shipping Mode

| Shipping Mode | Delay Rate |
|---|---|
| First Class | 100% 🚨 |
| Second Class | 79.7% 🔴 |
| Same Day | 47.8% 🟡 |
| Standard Class | 39.8% 🟢 |

### 2. Financial Summary

| Metric | Value |
|---|---|
| Total Revenue | $36.8M |
| Total Profit | $3.97M |
| Overall Delay Rate | 57.3% |
| Revenue at Risk | $21.1M |

### 3. Top Insight

First Class shipping — despite being premium priced — has a **100% delay rate** across all markets. Immediate operational review recommended.

---

## 📈 Charts Generated

| # | Chart | Insight |
|---|---|---|
| 1 | Delay Rate by Shipping Mode | First Class = 100% delayed |
| 2 | Monthly Revenue vs Delay Trend | Delay rate stable at 57% |
| 3 | Profit Margin by Segment | Consumer segment most profitable |
| 4 | Delay Heatmap by Market | Africa + Second Class = highest risk |
| 5 | Top 10 High Risk Supplier Routes | LATAM routes highest risk score |
| 6 | Discount vs Profit Correlation | Weak negative correlation (r = 0.049) |

---

## 🚀 How to Run

### Prerequisites

- Python 3.12
- MySQL 9.4
- VS Code

### Setup

```bash
# Clone the repo
git clone https://github.com/yourusername/supply_chain_analytics.git
cd supply_chain_analytics

# Create virtual environment
python3 -m venv .venv
source .venv/bin/activate

# Install dependencies
pip install -r requirements.txt

# Set up environment variables
cp .env.example .env
# Edit .env with your MySQL credentials
```

### Run the pipeline

```bash
# Step 1: Create MySQL schema
mysql -u root -p supply_chain_dw < scripts/sql/01_schema.sql

# Step 2: Ingest data
python scripts/python/01_ingest.py

# Step 3: Run EDA
jupyter notebook notebooks/eda_notebook.ipynb
```

---

## 📋 SQL Concepts Covered

- ✅ Multi-table JOINs (4 tables)
- ✅ CTEs (Common Table Expressions)
- ✅ Window Functions (RANK, DENSE_RANK, LAG, LEAD, NTILE, PERCENT_RANK)
- ✅ Rolling averages
- ✅ CASE WHEN classification
- ✅ Subqueries and derived tables

---

## 🔍 Data Source

**DataCo Smart Supply Chain Dataset**
- Source: [Kaggle](https://www.kaggle.com/datasets/shashwatwork/dataco-smart-supply-chain-for-big-data-analysis)
- Rows: 180,519
- Columns: 53
- Markets: Africa, Europe, LATAM, Pacific Asia, USCA

---

## 👤 Author

**Prashant Kumar**
- GitHub: [Prashant Kumar](https://github.com/kprashant19s)
- LinkedIn: [Prashant Kumar](https://www.linkedin.com/in/prashant-kumar-19s/)

---

## 📄 License

This project is licensed under the MIT License.