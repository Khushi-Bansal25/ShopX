"""
Unit tests for the ShopX ETL pipeline.
Run after 01_extract.py and 03_transform.py have produced data/processed/*.csv:

    pytest tests/test_pipeline.py -v
"""
from pathlib import Path
import pandas as pd
import pytest

DATA_DIR = Path(__file__).resolve().parents[1] / "data" / "processed"


def _read(name):
    path = DATA_DIR / f"{name}.csv"
    if not path.exists():
        pytest.skip(f"{path} not found - run 01_extract.py / 03_transform.py first")
    return pd.read_csv(path)


def test_order_header_has_unique_sales_document():
    df = _read("VBAK")
    assert df["Sales Document"].notna().all()
    assert not df["Sales Document"].duplicated().any()


def test_order_items_reference_existing_orders():
    orders = _read("VBAK")
    items = _read("VBAP")
    valid_orders = set(orders["Sales Document"])
    assert set(items["Sales Document"]).issubset(valid_orders)


def test_order_quantity_is_nonnegative():
    df = _read("VBAP")
    assert (df["Quantity"].dropna() >= 0).all()


def test_customer_id_is_populated():
    df = _read("KNA1")
    assert df["Customer ID"].notna().all()


def test_delivery_item_references_delivery_header():
    headers = _read("LIKP")
    items = _read("LIPS")
    valid_deliveries = set(headers["Delivery Number"])
    assert set(items["Delivery Number"]).issubset(valid_deliveries)


def test_shipment_item_references_shipment_header():
    headers = _read("VTTK")
    items = _read("VTTP")
    valid_shipments = set(headers["Shipment Number"])
    assert set(items["Shipment Number"]).issubset(valid_shipments)


def test_transform_does_not_duplicate_order_items():
    """order_items.csv must have the same row count as source VBAP - a
    row-count increase here would mean the join multiplied rows
    (double-counting), which is the #1 risk called out in the case study."""
    vbap = _read("VBAP")
    order_items = _read("order_items")
    assert len(order_items) == len(vbap)


def test_carrier_values_do_not_match_vendor_master():
    """Documents the confirmed data gap: VTTK.Carrier cannot be joined to
    LFA1. If this test ever starts failing, the source data has changed
    and the carrier/vendor mapping assumption should be revisited."""
    vttk = _read("VTTK")
    lfa1 = _read("LFA1")
    carriers = set(vttk["Carrier"].dropna())
    vendor_names = set(lfa1["Vendor Name"].dropna())
    assert carriers.isdisjoint(vendor_names)
