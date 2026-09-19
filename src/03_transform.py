"""
03_transform.py

Turns the raw SAP extracts into business-friendly, analysis-ready tables:

  1. order_items       - VBAK + VBAP + KNA1 joined, one row per order item,
                          SAP column names mapped to friendly names.
  2. delivery_items     - LIPS + LIKP joined, one row per delivery item.
  3. shipment_items     - VTTP + VTTK joined, one row per shipment item.
  4. item_delivery_performance
                        - order_items joined to delivery_items at item grain,
                          with a delivery-time gap and an "on-time" proxy
                          flag. See the WARNING comment below before using
                          this for a real on-time KPI.
  5. order_summary      - one row per order, aggregating item counts,
                          quantities, delivery/shipment counts and statuses,
                          and average delivery gap. Built with groupby so it
                          stays correct even if an order later has more than
                          one delivery or shipment (it doesn't in this
                          dataset, but the logic doesn't assume that).

Grain safety: order_items/delivery_items/shipment_items each preserve their
source's natural item-level grain (verified: their row counts equal VBAP/
LIPS/VTTP respectively). Aggregation to order level happens ONLY through
groupby in order_summary, never through a wide multi-table join - a wide
join here would multiply quantities if an order ever has multiple
deliveries or shipments.

Run:
    python src/03_transform.py
"""
from pathlib import Path
import pandas as pd

BASE_DIR = Path(__file__).resolve().parents[1]
DATA_DIR = BASE_DIR / "data" / "processed"


def read_table(name):
    return pd.read_csv(DATA_DIR / f"{name}.csv")


def build_order_items(vbak, vbap, kna1):
    orders = vbak.rename(columns={
        "Sales Document": "order_id",
        "Customer ID": "customer_id",
        "Order Date": "order_date",
        "Order Type": "order_type",
        "Order Status": "order_status",
    })

    items = vbap.rename(columns={
        "Sales Document": "order_id",
        "Item Number": "item_number",
        "Material Number": "product_id",
        "Quantity": "order_quantity",
        "Net Price": "unit_price",
        "Item Status": "item_status",
        "Delivery Date": "requested_delivery_date",
    })

    customers = kna1.rename(columns={
        "Customer ID": "customer_id",
        "Customer Name": "customer_name",
        "Country": "country",
        "Region": "region",
        "City": "city",
    })[["customer_id", "customer_name", "country", "region", "city"]]

    order_items = orders.merge(items, on="order_id", how="left", validate="one_to_many")
    order_items = order_items.merge(customers, on="customer_id", how="left", validate="many_to_one")

    for col in ["order_date", "requested_delivery_date"]:
        order_items[col] = pd.to_datetime(order_items[col], errors="coerce")

    return order_items


def build_delivery_items(lips, likp):
    headers = likp.rename(columns={
        "Delivery Number": "delivery_id",
        "Sales Document": "order_id",
        "Customer ID": "customer_id",
        "Delivery Date": "delivery_header_date",
        "Delivery Status": "delivery_header_status",
        "Shipping Status": "shipping_status",
        "Shipping Point": "shipping_point",
        "Shipping Type": "shipping_type",
        "Route": "route",
        "Delivery Priority": "delivery_priority",
    })

    items = lips.rename(columns={
        "Delivery Number": "delivery_id",
        "Item Number": "item_number",
        "Material Number": "product_id",
        "Delivered Quantity": "delivered_quantity",
        "Net Price": "unit_price",
        "Delivery Status": "item_delivery_status",
        "Sales Document": "order_id",
        "Sales Item": "sales_item",
        "Delivery Date": "delivery_date",
    })

    delivery_items = items.merge(
        headers.drop(columns=["order_id", "customer_id"]),
        on="delivery_id", how="left", validate="many_to_one",
    )
    delivery_items["delivery_date"] = pd.to_datetime(delivery_items["delivery_date"], errors="coerce")
    return delivery_items


def build_shipment_items(vttp, vttk):
    headers = vttk.rename(columns={
        "Shipment Number": "shipment_id",
        "Delivery Number": "delivery_id",
        "Sales Document": "order_id",
        "Carrier": "carrier_name",
        "Shipment Date": "shipment_header_date",
        "Shipment Status": "shipment_header_status",
        "Route": "route",
        "Shipping Type": "shipping_type",
    })

    items = vttp.rename(columns={
        "Shipment Number": "shipment_id",
        "Item Number": "item_number",
        "Material Number": "product_id",
        "Delivery Number": "delivery_id",
        "Sales Document": "order_id",
        "Sales Item": "sales_item",
        "Shipped Quantity": "shipped_quantity",
        "Item Status": "item_shipment_status",
        "Shipment Date": "shipment_date",
    })

    shipment_items = items.merge(
        headers.drop(columns=["delivery_id", "order_id"]),
        on="shipment_id", how="left", validate="many_to_one",
    )
    shipment_items["shipment_date"] = pd.to_datetime(shipment_items["shipment_date"], errors="coerce")
    return shipment_items


def build_item_delivery_performance(order_items, delivery_items):
    """
    Item-level comparison of requested vs actual delivery date.

    WARNING - proxy, not a verified metric:
    'requested_delivery_date' comes from VBAP.Delivery Date and
    'delivery_date' comes from LIPS.Delivery Date. The case study brief
    does not confirm that LIPS.Delivery Date represents a *confirmed
    actual* delivery event (e.g. proof-of-delivery) rather than another
    planned/document date. On the current dataset, the actual date is
    ALWAYS 1-2 days after the requested date for every single item -
    that uniformity is itself worth flagging to a trainer: it may reflect
    genuine performance, or it may just be how the sample data was
    generated. Do not present the resulting on-time % as a confirmed
    business result without that confirmation.
    """
    perf = order_items.merge(
        delivery_items,
        left_on=["order_id", "item_number"],
        right_on=["order_id", "sales_item"],
        how="left",
        suffixes=("", "_delivery"),
    )
    perf["delivery_gap_days"] = (perf["delivery_date"] - perf["requested_delivery_date"]).dt.days
    perf["on_time_proxy"] = (perf["delivery_gap_days"] <= 0).astype("boolean")
    perf.loc[perf["delivery_date"].isna(), "on_time_proxy"] = pd.NA

    return perf[[
        "order_id", "item_number", "customer_id", "product_id",
        "requested_delivery_date", "delivery_date",
        "delivery_gap_days", "on_time_proxy",
    ]]


def build_order_summary(order_items, delivery_items, shipment_items, item_perf):
    order_agg = order_items.groupby("order_id").agg(
        customer_id=("customer_id", "first"),
        order_date=("order_date", "first"),
        order_status=("order_status", "first"),
        total_order_items=("item_number", "count"),
        total_ordered_qty=("order_quantity", "sum"),
    ).reset_index()

    delivery_agg = delivery_items.groupby("order_id").agg(
        total_deliveries=("delivery_id", "nunique"),
        total_delivered_qty=("delivered_quantity", "sum"),
        delivery_statuses=("item_delivery_status", lambda s: ", ".join(sorted(s.dropna().unique()))),
    ).reset_index()

    shipment_agg = shipment_items.groupby("order_id").agg(
        total_shipments=("shipment_id", "nunique"),
        total_shipped_qty=("shipped_quantity", "sum"),
        shipment_statuses=("item_shipment_status", lambda s: ", ".join(sorted(s.dropna().unique()))),
    ).reset_index()

    perf_agg = item_perf.groupby("order_id").agg(
        avg_delivery_gap_days=("delivery_gap_days", "mean"),
        pct_items_on_time_proxy=("on_time_proxy", "mean"),
    ).reset_index()

    summary = order_agg.merge(delivery_agg, on="order_id", how="left")
    summary = summary.merge(shipment_agg, on="order_id", how="left")
    summary = summary.merge(perf_agg, on="order_id", how="left")

    summary["outstanding_qty"] = summary["total_ordered_qty"] - summary["total_delivered_qty"].fillna(0)
    return summary


def build_delivery_analytics(item_perf, shipment_items):
    """
    Delivery_Analytics table requested by the case study brief.

    LIMITATION: the brief describes 'delivery_time (in minutes)', but the
    source data has no timestamps anywhere -- only dates. delivery_time_days
    is a day-level proxy (actual item delivery date minus requested item
    delivery date), not minutes. delay_reason has no source field at all in
    any of the 8 sheets, so it is always left NULL here rather than invented.
    """
    ship_map = shipment_items[["order_id", "sales_item", "shipment_id"]].rename(
        columns={"sales_item": "item_number"}
    ).drop_duplicates(subset=["order_id", "item_number"])

    analytics = item_perf.merge(ship_map, on=["order_id", "item_number"], how="left")
    analytics["delivery_time_days"] = analytics["delivery_gap_days"]
    analytics["on_time"] = analytics["on_time_proxy"]
    analytics["delay_reason"] = pd.NA

    return analytics[[
        "order_id", "item_number", "shipment_id",
        "delivery_time_days", "on_time", "delay_reason",
    ]]


def transform_data():
    vbak, vbap = read_table("VBAK"), read_table("VBAP")
    likp, lips = read_table("LIKP"), read_table("LIPS")
    vttk, vttp = read_table("VTTK"), read_table("VTTP")
    kna1 = read_table("KNA1")

    order_items = build_order_items(vbak, vbap, kna1)
    delivery_items = build_delivery_items(lips, likp)
    shipment_items = build_shipment_items(vttp, vttk)
    item_perf = build_item_delivery_performance(order_items, delivery_items)
    order_summary = build_order_summary(order_items, delivery_items, shipment_items, item_perf)
    delivery_analytics = build_delivery_analytics(item_perf, shipment_items)

    return {
        "order_items": order_items,
        "delivery_items": delivery_items,
        "shipment_items": shipment_items,
        "item_delivery_performance": item_perf,
        "order_summary": order_summary,
        "delivery_analytics": delivery_analytics,
    }


if __name__ == "__main__":
    result = transform_data()
    for name, df in result.items():
        df.to_csv(DATA_DIR / f"{name}.csv", index=False)
        print(name, df.shape)

    print("\norder_summary preview:")
    print(result["order_summary"].head(5).to_string(index=False))

    on_time_rate = result["item_delivery_performance"]["on_time_proxy"].mean()
    print(f"\nOn-time proxy rate across all items: {on_time_rate:.1%}")
    print("Reminder: this is a proxy pending trainer confirmation of what")
    print("VBAP.Delivery Date and LIPS.Delivery Date actually represent.")
