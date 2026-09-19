"""
04_load.py
Loads the transformed CSVs into the warehouse schema (sql/01_create_schema.sql).

Two modes:
  --target mysql   (default) Reads DB_* vars from .env and loads into MySQL.
  --target sqlite  Loads into a local SQLite file (outputs/shopx_dw.sqlite).
                    Useful for testing the pipeline end-to-end without a
                    MySQL server available (e.g. this sandbox has no network
                    access to a database).

Run:
    python src/04_load.py --target mysql
    python src/04_load.py --target sqlite
"""
import argparse
import os
from pathlib import Path

import pandas as pd
from sqlalchemy import create_engine, text

BASE_DIR = Path(__file__).resolve().parents[1]
DATA_DIR = BASE_DIR / "data" / "processed"
SQL_DIR = BASE_DIR / "sql"
OUTPUT_DIR = BASE_DIR / "outputs"


def get_engine(target):
    if target == "sqlite":
        OUTPUT_DIR.mkdir(parents=True, exist_ok=True)
        db_path = OUTPUT_DIR / "shopx_dw.sqlite"
        db_path.unlink(missing_ok=True)  # fresh file each run
        return create_engine(f"sqlite:///{db_path}")

    from dotenv import load_dotenv
    load_dotenv(BASE_DIR / ".env")
    host = os.getenv("DB_HOST")
    port = os.getenv("DB_PORT", "3306")
    database = os.getenv("DB_NAME")
    user = os.getenv("DB_USER")
    password = os.getenv("DB_PASSWORD")
    if not all([host, database, user, password]):
        raise ValueError(
            "Missing DB_HOST / DB_NAME / DB_USER / DB_PASSWORD in .env"
        )
    return create_engine(
        f"mysql+pymysql://{user}:{password}@{host}:{port}/{database}"
    )


def strip_sql_comments(sql_text):
    """Remove '--' comments BEFORE splitting on ';' -- both full comment
    lines and inline trailing comments. Doing this after splitting, or only
    handling full-line comments, is a bug: a comment containing a literal
    semicolon (e.g. '-- see order_date; delivery_date') would otherwise
    split a statement in the wrong place. Confirmed this exact bug during
    testing when a schema comment used a semicolon."""
    lines = []
    for line in sql_text.splitlines():
        idx = line.find("--")
        lines.append(line[:idx] if idx != -1 else line)
    return "\n".join(lines)


def run_schema(engine, target):
    ddl_file = SQL_DIR / "01_create_schema.sql"
    clean_sql = strip_sql_comments(ddl_file.read_text())
    statements = clean_sql.split(";")
    with engine.begin() as conn:
        for stmt in statements:
            stmt = stmt.strip()
            if not stmt:
                continue
            if target == "sqlite" and (
                "CREATE DATABASE" in stmt.upper() or "USE " in stmt.upper()
            ):
                continue  # SQLite has no CREATE DATABASE / USE
            if target == "sqlite":
                stmt = stmt.replace("AUTO_INCREMENT", "")
            conn.execute(text(stmt))


def load_warehouse(engine):
    kna1 = pd.read_csv(DATA_DIR / "KNA1.csv")
    lfa1 = pd.read_csv(DATA_DIR / "LFA1.csv")
    vbak = pd.read_csv(DATA_DIR / "VBAK.csv")
    vbap = pd.read_csv(DATA_DIR / "VBAP.csv")
    likp = pd.read_csv(DATA_DIR / "LIKP.csv")
    lips = pd.read_csv(DATA_DIR / "LIPS.csv")
    vttk = pd.read_csv(DATA_DIR / "VTTK.csv")
    vttp = pd.read_csv(DATA_DIR / "VTTP.csv")

    dim_customer = kna1.rename(columns={
        "Customer ID": "customer_id", "Customer Name": "customer_name",
        "Country": "country", "Region": "region", "City": "city",
        "Postal Code": "postal_code", "Street Address": "street_address",
        "Phone Number": "phone_number", "Email Address": "email_address",
        "Language": "language", "Tax Number": "tax_number",
        "Customer Group": "customer_group",
        "Sales Organization": "sales_organization",
        "Distribution Channel": "distribution_channel", "Division": "division",
    })[["customer_id", "customer_name", "country", "region", "city",
        "postal_code", "street_address", "phone_number", "email_address",
        "language", "tax_number", "customer_group", "sales_organization",
        "distribution_channel", "division"]]

    dim_vendor = lfa1.rename(columns={
        "Vendor Number": "vendor_number", "Vendor Name": "vendor_name",
        "Country": "country", "Region": "region", "City": "city",
        "Postal Code": "postal_code", "Street Address": "street_address",
        "Phone Number": "phone_number", "Email Address": "email_address",
        "Language": "language", "Tax Number": "tax_number",
        "Payment Terms": "payment_terms",
    })[["vendor_number", "vendor_name", "country", "region", "city",
        "postal_code", "street_address", "phone_number", "email_address",
        "language", "tax_number", "payment_terms"]]

    dim_carrier = pd.DataFrame({
        "carrier_name": sorted(vttk["Carrier"].dropna().unique())
    })

    dim_product = pd.DataFrame({
        "product_id": sorted(set(vbap["Material Number"]) |
                              set(lips["Material Number"]) |
                              set(vttp["Material Number"]))
    })

    fact_order = vbak.rename(columns={
        "Sales Document": "order_id", "Customer ID": "customer_id",
        "Order Date": "order_date", "Order Type": "order_type",
        "Sales Organization": "sales_organization",
        "Distribution Channel": "distribution_channel", "Division": "division",
        "Order Status": "order_status",
    })[["order_id", "customer_id", "order_date", "order_type",
        "sales_organization", "distribution_channel", "division", "order_status"]]

    fact_order_item = vbap.rename(columns={
        "Sales Document": "order_id", "Item Number": "item_number",
        "Material Number": "product_id", "Quantity": "order_quantity",
        "Net Price": "net_price", "Item Status": "item_status",
        "Delivery Date": "requested_delivery_date",
    })[["order_id", "item_number", "product_id", "order_quantity",
        "net_price", "item_status", "requested_delivery_date"]]

    fact_delivery = likp.rename(columns={
        "Delivery Number": "delivery_id", "Sales Document": "order_id",
        "Customer ID": "customer_id", "Delivery Date": "delivery_date",
        "Delivery Status": "delivery_status", "Shipping Status": "shipping_status",
        "Shipping Point": "shipping_point", "Shipping Type": "shipping_type",
        "Route": "route", "Delivery Priority": "delivery_priority",
    })[["delivery_id", "order_id", "customer_id", "delivery_date",
        "delivery_status", "shipping_status", "shipping_point",
        "shipping_type", "route", "delivery_priority"]]

    fact_delivery_item = lips.rename(columns={
        "Delivery Number": "delivery_id", "Item Number": "item_number",
        "Material Number": "product_id", "Delivered Quantity": "delivered_quantity",
        "Net Price": "net_price", "Sales Document": "order_id",
        "Customer ID": "customer_id",
        "Sales Item": "sales_item", "Delivery Status": "item_delivery_status",
        "Delivery Date": "delivery_date",
    })[["delivery_id", "item_number", "product_id", "order_id", "customer_id",
        "sales_item", "delivered_quantity", "net_price", "item_delivery_status",
        "delivery_date"]]

    fact_shipment = vttk.rename(columns={
        "Shipment Number": "shipment_id", "Delivery Number": "delivery_id",
        "Sales Document": "order_id", "Customer ID": "customer_id",
        "Carrier": "carrier_name", "Shipping Point": "shipping_point",
        "Shipment Date": "shipment_date", "Shipment Status": "shipment_status",
        "Route": "route", "Shipping Type": "shipping_type",
    })[["shipment_id", "delivery_id", "order_id", "customer_id", "carrier_name",
        "shipping_point", "shipment_date", "shipment_status", "route", "shipping_type"]]

    fact_shipment_item = vttp.rename(columns={
        "Shipment Number": "shipment_id", "Item Number": "item_number",
        "Material Number": "product_id", "Delivery Number": "delivery_id",
        "Sales Document": "order_id", "Customer ID": "customer_id",
        "Sales Item": "sales_item",
        "Shipped Quantity": "shipped_quantity", "Item Status": "item_status",
        "Shipment Date": "shipment_date",
    })[["shipment_id", "item_number", "product_id", "delivery_id", "order_id",
        "customer_id", "sales_item", "shipped_quantity", "item_status", "shipment_date"]]

    load_order = [
        ("dim_customer", dim_customer), ("dim_vendor", dim_vendor),
        ("dim_carrier", dim_carrier), ("dim_product", dim_product),
        ("fact_order", fact_order), ("fact_order_item", fact_order_item),
        ("fact_delivery", fact_delivery), ("fact_delivery_item", fact_delivery_item),
        ("fact_shipment", fact_shipment), ("fact_shipment_item", fact_shipment_item),
    ]
    for table_name, df in load_order:
        df.to_sql(table_name, con=engine, if_exists="append", index=False)
        print(f"Loaded {len(df)} rows into {table_name}")

    # fact_delivery_analytics is built in 03_transform.py (needs cross-table
    # joins not available from the raw sheets alone) and read from its own
    # processed CSV rather than rebuilt here.
    da_path = DATA_DIR / "delivery_analytics.csv"
    if da_path.exists():
        da = pd.read_csv(da_path)
        da.to_sql("fact_delivery_analytics", con=engine, if_exists="append", index=False)
        print(f"Loaded {len(da)} rows into fact_delivery_analytics")
    else:
        print("WARNING: data/processed/delivery_analytics.csv not found - "
              "run 03_transform.py before loading, or fact_delivery_analytics "
              "will stay empty.")


if __name__ == "__main__":
    parser = argparse.ArgumentParser()
    parser.add_argument("--target", choices=["mysql", "sqlite"], default="mysql")
    args = parser.parse_args()

    engine = get_engine(args.target)
    run_schema(engine, args.target)
    load_warehouse(engine)
    print(f"\nWarehouse loaded successfully (target={args.target}).")
