# ShopX Order Fulfillment & Delivery Analytics

A working ETL pipeline (Excel → validate → transform → MySQL) built and tested
against the actual `SAP-DataSet.xlsx` provided with the case study.

## What was actually verified (not assumed)

- **Source**: 8 sheets — KNA1 (30 rows), LFA1 (30), VBAK (22), VBAP (23),
  LIKP (20), LIPS (21), VTTK (20), VTTP (21).
- **Data quality**: no nulls, no duplicate keys, and perfect referential
  integrity across all sheets (every child key resolves to a parent). See
  `outputs/validation_report.csv` after running the pipeline.
- **Confirmed data gap**: `VTTK.Carrier` (`Carrier1`/`Carrier2`/`Carrier3`)
  does **not** correspond to any `LFA1.Vendor Number` or `Vendor Name`. There
  is no reliable way to join shipments to the vendor master with this data.
  The schema treats carrier as its own flat dimension (`dim_carrier`),
  built from the shipment data itself, and keeps `dim_vendor`/LFA1 separate.
- **Grain safety**: the transform step keeps order/delivery/shipment items at
  their own natural grain (verified: `order_items.csv` has 23 rows, exactly
  matching source VBAP — no row multiplication from the customer join).
- **KPI reality check**: ordered vs. delivered quantity reconciles to 0
  outstanding on every item in this dataset. There is still no promised
  delivery date vs. actual delivery timestamp distinction in the source, so
  a true "on-time delivery %" KPI **cannot** be computed — only date-gap
  proxies (documented as such in `sql/02_analytics_kpis.sql`).

## Setup

```bash
python -m venv .venv
source .venv/bin/activate        # Windows: .venv\Scripts\activate
pip install -r requirements.txt
cp .env.example .env             # fill in your MySQL credentials
```

## Run the pipeline

```bash
python src/01_extract.py     # Excel -> data/processed/*.csv
python src/02_validate.py    # profiling -> outputs/validation_report.csv
python src/03_transform.py   # grain-safe joins -> order_items/delivery_items/shipment_items.csv
mysql -u root -p < sql/01_create_schema.sql   # create shopx_dw and all tables
python src/04_load.py --target mysql          # load the warehouse
```

No MySQL server available? Test the whole thing against a local SQLite file first:

```bash
python src/04_load.py --target sqlite
```

This creates `outputs/shopx_dw.sqlite` you can inspect with any SQLite client
before pointing at real MySQL.

## Run the SQL analytics

```bash
mysql -u root -p shopx_dw < sql/02_analytics_kpis.sql
```

## Run the tests

```bash
pytest tests/test_pipeline.py -v
```

All 8 tests pass against the current dataset (verified during development).

## Known limitations / questions for your trainer

1. Is the Excel workbook the only source, or is direct SAP extraction required?
2. Is there a promised/planned delivery date field anywhere, to compute a true
   on-time rate? Currently only `VBAP.Delivery Date` (requested) exists.
3. How should `VTTK.Carrier` map to `LFA1.Vendor Number` — confirmed they
   don't match in the current data. Is a crosswalk table coming, or should
   carrier stay a standalone dimension?
4. Where would customer satisfaction / rating data come from, if required
   by the dashboard?
