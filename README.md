🛒 ShopX — Order Fulfillment & Delivery Analytics
![Python](https://img.shields.io/badge/Python-3.10+-3776AB?logo=python&logoColor=white)
![MySQL](https://img.shields.io/badge/MySQL-8.0-4479A1?logo=mysql&logoColor=white)
![Power BI](https://img.shields.io/badge/Power%20BI-Dashboard-F2C811?logo=powerbi&logoColor=black)
[![Status](https://img.shields.io/badge/Status-Complete-2EA44F)]()
An end-to-end analytics pipeline built on a simulated SAP ERP export, covering order processing, delivery performance, and carrier analysis for a fictional e-commerce company, ShopX. Built as part of the ADMM Foundation Training case study.
> **Pipeline:** SAP source data → Python ETL → MySQL star-schema warehouse → SQL KPIs → Power BI dashboard
---
📋 Table of Contents
Overview
Architecture
Repository Structure
Getting Started
Data Warehouse Schema
Key Performance Indicators
Power BI Dashboard
Known Limitations
Full Documentation
---
🔍 Overview
ShopX has SAP ERP for managing sales orders, inventory, shipments, and customer data. This project builds an analytics layer on top of that data to answer four core business questions:
Question	Answered by
How long does order processing take?	`Avg Order Processing Days` — 7.20 days
How efficiently are orders fulfilled?	`Fulfillment Efficiency %` — 93.52%
How satisfied are customers (proxy)?	`Customer Order Fulfillment Rate %` — 27.27%
Which carriers perform best?	`Avg Order-to-Delivery Days by Carrier`
All figures above are real, verified results — run against the actual warehouse, not illustrative placeholders.
---
🏗 Architecture
```
SAP Source Data  →  Python ETL  →  MySQL Warehouse  →  SQL KPIs  →  Power BI Dashboard
 (8 sheets)         (pandas)       (11 tables,          (10 queries)   (2 pages,
                                    star schema)                        15+ visuals)
```
Extract — 8 SAP-style sheets (customers, vendors, orders, deliveries, shipments) pulled from a single Excel export.
Validate — completeness, duplicate, referential integrity, and business-rule checks — all run and logged.
Transform — SAP field names mapped to business-friendly names; grain-safe joins (verified: zero row multiplication).
Load — 11-table MySQL star schema, loaded and reconciled row-for-row against source.
Analyze — 10 SQL KPI queries, each with a documented, verified result.
Visualize — Power BI model with DAX measures and a two-page interactive dashboard.
---
📁 Repository Structure
```
ShopX/
├── data/
│   ├── raw/              # Original SAP-DataSet.xlsx
│   └── processed/        # Cleaned, transformed CSVs
├── sql/
│   ├── 01_create_schema.sql
│   ├── 02_analytics_kpis.sql
│   └── 03_load_data.sql
├── src/
│   ├── 01_extract.py
│   ├── 02_validate.py
│   ├── 03_transform.py
│   └── 04_load.py
├── tests/
│   └── test_pipeline.py
├── powerbi_import/       # CSV exports for Power BI (no-connector fallback)
├── outputs/
│   └── validation_report.csv
├── ShopX_CaseStudy_Report.docx
├── requirements.txt
└── README.md
```
---
🚀 Getting Started
```bash
# 1. Install dependencies
pip install -r requirements.txt

# 2. Run the pipeline
python src/01_extract.py
python src/02_validate.py
python src/03_transform.py

# 3a. Load into MySQL (recommended)
mysql -u root -p < sql/01_create_schema.sql
python src/04_load.py --target mysql

# 3b. Or test locally with SQLite first — no MySQL server required
python src/04_load.py --target sqlite
```
Then run the KPI queries:
```bash
mysql -u root -p shopx_dw < sql/02_analytics_kpis.sql
```
Or run the test suite:
```bash
pytest tests/test_pipeline.py -v
```
---
🗂 Data Warehouse Schema
A star schema with 4 dimension tables and 7 fact tables, built on natural (source-system) keys rather than surrogate keys — see the full report for the reasoning.
Type	Tables
Dimensions	`dim_customer`, `dim_vendor`, `dim_carrier`, `dim_product`
Facts	`fact_order`, `fact_order_item`, `fact_delivery`, `fact_delivery_item`, `fact_shipment`, `fact_shipment_item`, `fact_delivery_analytics`
---
📊 Key Performance Indicators
#	KPI	Result
1	Order Volume by Status	Open: 11 · Delivered: 6 · Closed: 5
2	Order Processing Time	7.20 days
3	Average Delivery Time	7.20 days
4	Fulfillment Efficiency	93.52%
5	Outstanding Quantity	2 items, 400 units total
6	Delivery & Shipping Status	10 Delivered/Shipped, 10 Open/Not Shipped
7	Carrier Performance	Carrier3: 7.00d · Carrier1: 7.25d · Carrier2: 7.33d
8	Customer Fulfillment Rate (proxy)	27.27%
9	On-Time Delivery Rate	0.00% (see Limitations)
10	Reconciliation Check	✅ Row counts match source exactly
Full query definitions, real outputs, and interpretation notes: `sql/02_analytics_kpis.sql`
---
📈 Power BI Dashboard
Two interactive pages, built on the warehouse via the `powerbi_import/` CSVs:
Order Fulfillment & Performance Overview — KPI cards, order status breakdown, country × status matrix, outstanding quantity table, carrier comparison
ShopX Fulfillment Command Center — order trend over time, geographic map, bubble chart, on-time delivery gauge vs. target
---
⚠️ Known Limitations
This project treats data honesty as a hard requirement — no invented fields, no fabricated results. Genuine limitations encountered:
No customer satisfaction field exists in the source data. `Customer Order Fulfillment Rate %` is used as a clearly labeled proxy, not a substitute claim.
`shipment_date` equals `delivery_date` in every record, and every item's actual delivery date is 1–2 days after its requested date — both suspiciously uniform patterns, more likely artifacts of sample data generation than real operational findings.
Order `1000021` is marked `Delivered` with zero matching delivery/shipment records — a genuine source data inconsistency.
`LFA1.Phone Number` is corrupted for all 30 vendors (stored as negative integers) — excluded rather than guessed at.
MARA / MKPF (Material Master, Document Header) tables referenced in general project material do not exist in the actual dataset.
Data was loaded to MySQL manually via Workbench, and Power BI connects via exported CSVs, due to a local network/connector restriction — full pipeline logic is still authored and tested in Python end-to-end.
Full details on every limitation, with exact locations: see the Notes and Limitations section of the report.
---
📄 Full Documentation
The complete project report — architecture, all 5 phases, every KPI and DAX measure with results, dashboard walkthrough, and notes — is available here:
`ShopX_CaseStudy_Report.docx`
---
<p align="center">
  <sub>Built as part of the ADMM Foundation Training Case Study — E-commerce Order Fulfillment & Delivery Analytics</sub>
</p>
