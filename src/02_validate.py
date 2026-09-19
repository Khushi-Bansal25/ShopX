"""
02_validate.py
Profiles each extracted sheet:
  - row counts, nulls per column
  - duplicate primary keys AND duplicate full rows
  - referential integrity between related sheets
  - date fields that fail to parse
  - numeric fields that look corrupted (e.g. plain negative numbers where a
    formatted value like a phone number is expected)
Writes outputs/validation_report.csv. Does NOT delete or modify data.

Run:
    python src/02_validate.py
"""
from pathlib import Path
import pandas as pd

BASE_DIR = Path(__file__).resolve().parents[1]
DATA_DIR = BASE_DIR / "data" / "processed"
OUTPUT_DIR = BASE_DIR / "outputs"

ALL_SHEETS = ["KNA1", "LFA1", "VBAK", "VBAP", "LIKP", "LIPS", "VTTK", "VTTP"]

# Primary keys confirmed against the actual columns in the workbook
PRIMARY_KEYS = {
    "KNA1": ["Customer ID"],
    "LFA1": ["Vendor Number"],
    "VBAK": ["Sales Document"],
    "VBAP": ["Sales Document", "Item Number"],
    "LIKP": ["Delivery Number"],
    "LIPS": ["Delivery Number", "Item Number"],
    "VTTK": ["Shipment Number"],
    "VTTP": ["Shipment Number", "Item Number"],
}

# Referential integrity checks: (child_table, child_col, parent_table, parent_col)
REFERENTIAL_CHECKS = [
    ("VBAK", "Customer ID", "KNA1", "Customer ID"),
    ("VBAP", "Sales Document", "VBAK", "Sales Document"),
    ("LIKP", "Sales Document", "VBAK", "Sales Document"),
    ("LIPS", "Delivery Number", "LIKP", "Delivery Number"),
    ("VTTK", "Delivery Number", "LIKP", "Delivery Number"),
    ("VTTP", "Shipment Number", "VTTK", "Shipment Number"),
]

# Date fields to check for unparseable values
DATE_FIELDS = {
    "VBAK": "Order Date",
    "VBAP": "Delivery Date",
    "LIKP": "Delivery Date",
    "VTTK": "Shipment Date",
}

# Fields that should never be a plain negative integer. LFA1.Phone Number is
# a confirmed real example: hyphenated numbers like "44-20-5551445" were
# corrupted upstream into a subtraction result ("-5551445"). We flag this;
# we do NOT attempt to reconstruct the original value.
SUSPECT_NUMERIC_FIELDS = {
    "KNA1": "Phone Number",
    "LFA1": "Phone Number",
}


def load_csv(name):
    path = DATA_DIR / f"{name}.csv"
    if not path.exists():
        raise FileNotFoundError(f"{path} not found. Run 01_extract.py first.")
    return pd.read_csv(path)


def key_and_null_checks(data):
    report = []
    for name, df in data.items():
        keys = PRIMARY_KEYS[name]
        report.append({"table": name, "check": "row_count", "issue_count": len(df)})
        report.append({
            "table": name, "check": "missing_primary_key",
            "issue_count": int(df[keys].isna().any(axis=1).sum()),
        })
        report.append({
            "table": name, "check": "duplicate_primary_key",
            "issue_count": int(df.duplicated(keys, keep=False).sum()),
        })
        report.append({
            "table": name, "check": "full_row_duplicate",
            "issue_count": int(df.duplicated().sum()),
        })
        for column in df.columns:
            report.append({
                "table": name, "check": f"missing_{column}",
                "issue_count": int(df[column].isna().sum()),
            })
    return report


def referential_integrity_checks(data):
    report = []
    for child, child_col, parent, parent_col in REFERENTIAL_CHECKS:
        child_values = set(data[child][child_col].dropna())
        parent_values = set(data[parent][parent_col].dropna())
        missing = child_values - parent_values
        report.append({
            "table": child, "check": f"orphan_{child_col}_to_{parent}",
            "issue_count": len(missing),
        })
    return report


def format_and_type_checks(data):
    report = []

    for name, col in DATE_FIELDS.items():
        df = data[name]
        unparseable = pd.to_datetime(df[col], errors="coerce").isna().sum()
        report.append({
            "table": name, "check": f"unparseable_date_{col}",
            "issue_count": int(unparseable),
        })

    for name, col in SUSPECT_NUMERIC_FIELDS.items():
        df = data[name]
        bad = df[col].astype(str).str.match(r"^-\d+$")
        report.append({
            "table": name, "check": f"corrupted_{col.replace(' ', '_')}",
            "issue_count": int(bad.sum()),
        })

    return report


def business_rule_notes(data):
    """Data-quality notes confirmed by manual inspection, not a generic
    formula check. Documented here so they show up in the same report."""
    report = []
    report.append({
        "table": "VTTK",
        "check": "carrier_not_mappable_to_LFA1_vendor",
        "issue_count": data["VTTK"]["Carrier"].nunique(),
    })

    # Orders marked "Delivered" with zero matching delivery/shipment item
    # records anywhere in LIPS/VTTP. Confirmed real case: order 1000021.
    delivered_orders = set(
        data["VBAK"].loc[data["VBAK"]["Order Status"] == "Delivered", "Sales Document"]
    )
    orders_with_delivery_items = set(data["LIPS"]["Sales Document"].dropna())
    orders_with_shipment_items = set(data["VTTP"]["Sales Document"].dropna())
    orphaned_delivered = delivered_orders - orders_with_delivery_items - orders_with_shipment_items
    report.append({
        "table": "VBAK",
        "check": "order_status_delivered_but_no_delivery_or_shipment_record",
        "issue_count": len(orphaned_delivered),
    })

    return report


def validate_data():
    OUTPUT_DIR.mkdir(parents=True, exist_ok=True)
    data = {name: load_csv(name) for name in ALL_SHEETS}

    report = []
    report.extend(key_and_null_checks(data))
    report.extend(referential_integrity_checks(data))
    report.extend(format_and_type_checks(data))
    report.extend(business_rule_notes(data))

    result = pd.DataFrame(report)
    result.to_csv(OUTPUT_DIR / "validation_report.csv", index=False)
    print(result.to_string(index=False))
    return result


if __name__ == "__main__":
    validate_data()
