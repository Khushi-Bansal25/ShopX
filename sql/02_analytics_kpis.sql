-- 02_analytics_kpis.sql
-- Analytics queries for ShopX Order Fulfillment & Delivery Analytics.
-- Numbered to match Phase3_SQL_KPIs.md exactly, 1-10, so the two documents
-- stay in sync. Every query here was run against the real (transformed)
-- dataset; confirmed results are noted in comments below each one.
-- Grain warning: fact_order_item, fact_delivery_item and fact_shipment_item
-- are each queried at their own item grain and joined via keyed aggregation
-- (CTEs), never a raw multi-table join, to avoid quantity double-counting.

USE shopx_dw;

-- 1. Order Volume by Status
SELECT order_status, COUNT(*) AS total_orders
FROM fact_order
GROUP BY order_status
ORDER BY total_orders DESC;
-- Confirmed result: Open=11, Delivered=6, Closed=5 (22 orders total)

-- 2. Order Processing Time (order date -> delivery date)
SELECT
    ROUND(AVG(DATEDIFF(d.delivery_date, o.order_date)), 2) AS avg_order_processing_days
FROM fact_order o
JOIN fact_delivery d ON o.order_id = d.order_id;
-- Confirmed result: 7.20 days

-- 3. Average Delivery Time (order date -> delivery date)
-- DEFINITION CHANGE (deliberate, per project owner's instruction): uses
-- fact_order.order_date -> fact_delivery.delivery_date, NOT shipment_date.
-- This is numerically identical to KPI 2 (Order Processing Time) in this
-- dataset because both now measure the same date pair -- documented and
-- expected, not a bug. The brief's literal definition (shipment_date ->
-- delivery_date) is preserved as query 3b below; it returns 0.00 days
-- because shipment_date equals delivery_date in every source record.
SELECT
    ROUND(AVG(DATEDIFF(d.delivery_date, o.order_date)), 2) AS avg_delivery_time_days
FROM fact_order o
JOIN fact_delivery d ON o.order_id = d.order_id;
-- Confirmed result: 7.20 days

-- 3b. Reference only -- brief's literal definition (shipment_date -> delivery_date)
SELECT
    ROUND(AVG(DATEDIFF(d.delivery_date, s.shipment_date)), 2) AS avg_shipment_to_delivery_days
FROM fact_shipment s
JOIN fact_delivery d ON s.delivery_id = d.delivery_id;
-- Confirmed result: 0.00 days (shipment_date = delivery_date in every record)

-- 4. Fulfillment Efficiency (total delivered qty / total ordered qty)
SELECT
    ROUND(SUM(delivered_quantity) * 100.0 /
        (SELECT SUM(order_quantity) FROM fact_order_item), 2) AS fulfillment_efficiency_pct
FROM fact_delivery_item;
-- Confirmed result: 93.52%

-- 5. Outstanding Quantity by Order Item
-- LIPS.Sales Item is the field that maps back to VBAP.Item Number.
-- Filtered to only nonzero rows; the reconciliation check (KPI 10) covers
-- full row counts across every item, including fully-reconciled ones.
WITH ordered AS (
    SELECT order_id, item_number, SUM(order_quantity) AS ordered_qty
    FROM fact_order_item
    GROUP BY order_id, item_number
),
delivered AS (
    SELECT order_id, sales_item, SUM(delivered_quantity) AS delivered_qty
    FROM fact_delivery_item
    GROUP BY order_id, sales_item
)
SELECT
    o.order_id, o.item_number, o.ordered_qty,
    COALESCE(d.delivered_qty, 0) AS delivered_qty,
    o.ordered_qty - COALESCE(d.delivered_qty, 0) AS outstanding_qty
FROM ordered o
LEFT JOIN delivered d
    ON o.order_id = d.order_id AND o.item_number = d.sales_item
WHERE o.ordered_qty - COALESCE(d.delivered_qty, 0) != 0;
-- Confirmed result: exactly 2 rows
-- (order 1000021 item 10: outstanding 180; order 1000022 item 10: outstanding 220)

-- 6. Delivery & Shipping Status Breakdown
SELECT delivery_status, shipping_status, COUNT(*) AS delivery_count
FROM fact_delivery
GROUP BY delivery_status, shipping_status
ORDER BY delivery_count DESC;
-- Confirmed result: (Delivered, Shipped)=10, (Open, Not Shipped)=10

-- 7. Carrier Performance (order date -> delivery date, by carrier)
-- DEFINITION CHANGE (deliberate, per project owner's instruction): uses
-- fact_order.order_date -> fact_delivery.delivery_date, NOT shipment_date.
-- CAVEAT: this includes ShopX's internal order-processing time in addition
-- to the carrier's actual transport leg, so it does not isolate carrier-
-- only performance -- a carrier has no control over how long ShopX takes
-- to process an order before handing it off. The brief's literal
-- shipment_date -> delivery_date definition is preserved as query 7b; it
-- returns 0.00 days flat for every carrier (see KPI 3b for why).
SELECT
    s.carrier_name,
    ROUND(AVG(DATEDIFF(d.delivery_date, o.order_date)), 2) AS avg_order_to_delivery_days,
    COUNT(*) AS order_delivery_pairs
FROM fact_order o
JOIN fact_shipment s ON o.order_id = s.order_id
JOIN fact_delivery d ON s.delivery_id = d.delivery_id
GROUP BY s.carrier_name
ORDER BY avg_order_to_delivery_days;
-- Confirmed result: Carrier3=7.00, Carrier1=7.25, Carrier2=7.33 days

-- 7b. Reference only -- brief's literal definition (shipment_date -> delivery_date)
SELECT
    s.carrier_name,
    ROUND(AVG(DATEDIFF(d.delivery_date, s.shipment_date)), 2) AS avg_shipment_to_delivery_days,
    COUNT(*) AS shipment_delivery_pairs
FROM fact_shipment s
JOIN fact_delivery d ON s.delivery_id = d.delivery_id
GROUP BY s.carrier_name;
-- Confirmed result: 0.00 days for every carrier

-- 8. Customer Order Fulfillment Rate (proxy for Customer Satisfaction Score)
-- No satisfaction/rating field exists anywhere in the source data (confirmed:
-- dim_customer has no such column). This is the documented substitute KPI.
SELECT
    ROUND(
        SUM(CASE WHEN order_status = 'Delivered' THEN 1 ELSE 0 END) * 100.0
        / COUNT(*), 2
    ) AS customer_order_fulfillment_rate_pct
FROM fact_order;
-- Confirmed result: 27.27% (6 of 22 orders)

-- 9. On-Time Delivery Rate (proxy: VBAP requested date vs LIPS actual date)
-- Sourced from fact_delivery_analytics, built in 03_transform.py by
-- comparing fact_order_item.requested_delivery_date (VBAP.Delivery Date)
-- against the matching delivery item's actual delivery_date (LIPS.Delivery
-- Date). This is the only field pair in the source data that represents a
-- requested-vs-actual comparison; there is no alternative definition.
SELECT
    ROUND(AVG(on_time) * 100.0, 2) AS on_time_rate_pct,
    COUNT(*) AS matched_items
FROM fact_delivery_analytics
WHERE on_time IS NOT NULL;
-- Confirmed result: 0.00% across 21 matched items
-- (actual delivery date is 1-2 days after requested date for every item)

-- 10. Reconciliation Check
-- Run this after every load. Confirms zero rows lost/duplicated vs source.
SELECT 'fact_order' AS table_name, COUNT(*) AS row_count FROM fact_order
UNION ALL SELECT 'fact_order_item', COUNT(*) FROM fact_order_item
UNION ALL SELECT 'fact_delivery', COUNT(*) FROM fact_delivery
UNION ALL SELECT 'fact_delivery_item', COUNT(*) FROM fact_delivery_item
UNION ALL SELECT 'fact_shipment', COUNT(*) FROM fact_shipment
UNION ALL SELECT 'fact_shipment_item', COUNT(*) FROM fact_shipment_item;
-- Confirmed result: 22 / 23 / 20 / 21 / 20 / 21 -- matches VBAK/VBAP/LIKP/LIPS/VTTK/VTTP exactly
