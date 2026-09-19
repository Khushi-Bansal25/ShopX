-- 01_create_schema.sql
-- Star-schema-oriented warehouse for ShopX Order Fulfillment & Delivery Analytics
-- Column choices trace directly to the actual SAP-DataSet.xlsx columns confirmed
-- by inspection (see outputs/validation_report.csv for the source profiling).

CREATE DATABASE IF NOT EXISTS shopx_dw;
USE shopx_dw;

CREATE TABLE IF NOT EXISTS dim_customer (
    customer_id VARCHAR(30) PRIMARY KEY,      -- KNA1.Customer ID
    customer_name VARCHAR(150),
    country VARCHAR(50),
    region VARCHAR(100),
    city VARCHAR(100),
    postal_code VARCHAR(30),
    street_address VARCHAR(200),
    phone_number VARCHAR(50),
    email_address VARCHAR(150),
    language VARCHAR(10),
    tax_number VARCHAR(50),
    customer_group INT,
    sales_organization INT,
    distribution_channel INT,
    division INT
);

-- NOTE: VTTK.Carrier ('Carrier1','Carrier2','Carrier3') does NOT match
-- LFA1.Vendor Number/Vendor Name in the source data. dim_carrier is built
-- from the carrier values actually used in shipments, not from LFA1.
-- LFA1 is kept as its own reference table in case a future mapping is approved.
CREATE TABLE IF NOT EXISTS dim_carrier (
    carrier_name VARCHAR(50) PRIMARY KEY      -- distinct VTTK.Carrier values
);

CREATE TABLE IF NOT EXISTS dim_vendor (
    vendor_number BIGINT PRIMARY KEY,         -- LFA1.Vendor Number
    vendor_name VARCHAR(150),
    country VARCHAR(50),
    region VARCHAR(100),
    city VARCHAR(100),
    postal_code VARCHAR(30),
    street_address VARCHAR(200),
    phone_number VARCHAR(50),
    email_address VARCHAR(150),
    language VARCHAR(10),
    tax_number VARCHAR(50),
    payment_terms VARCHAR(30)
);

CREATE TABLE IF NOT EXISTS dim_product (
    product_id VARCHAR(50) PRIMARY KEY        -- Material Number, union of VBAP/LIPS/VTTP
);

CREATE TABLE IF NOT EXISTS fact_order (
    order_id BIGINT PRIMARY KEY,              -- VBAK.Sales Document
    customer_id VARCHAR(30),
    order_date DATE,
    order_type VARCHAR(30),
    sales_organization INT,
    distribution_channel INT,
    division INT,
    order_status VARCHAR(50),
    FOREIGN KEY (customer_id) REFERENCES dim_customer(customer_id)
);

CREATE TABLE IF NOT EXISTS fact_order_item (
    order_id BIGINT,
    item_number INT,
    product_id VARCHAR(50),
    order_quantity DECIMAL(18,3),             -- VBAP.Quantity
    net_price DECIMAL(18,2),                  -- VBAP.Net Price
    item_status VARCHAR(50),
    requested_delivery_date DATE,             -- VBAP.Delivery Date (item-level, NOT actual)
    PRIMARY KEY (order_id, item_number),
    FOREIGN KEY (order_id) REFERENCES fact_order(order_id),
    FOREIGN KEY (product_id) REFERENCES dim_product(product_id)
);

CREATE TABLE IF NOT EXISTS fact_delivery (
    delivery_id BIGINT PRIMARY KEY,           -- LIKP.Delivery Number
    order_id BIGINT,
    customer_id VARCHAR(30),
    delivery_date DATE,
    delivery_status VARCHAR(50),
    shipping_status VARCHAR(50),
    shipping_point VARCHAR(50),
    shipping_type VARCHAR(50),
    route INT,
    delivery_priority VARCHAR(30),
    FOREIGN KEY (order_id) REFERENCES fact_order(order_id),
    FOREIGN KEY (customer_id) REFERENCES dim_customer(customer_id)
);

CREATE TABLE IF NOT EXISTS fact_delivery_item (
    delivery_id BIGINT,
    item_number INT,
    product_id VARCHAR(50),
    order_id BIGINT,
    customer_id VARCHAR(30),                   -- LIPS.Customer ID (redundant with fact_delivery, kept for full source fidelity)
    sales_item INT,                            -- LIPS.Sales Item -> maps to VBAP.Item Number
    delivered_quantity DECIMAL(18,3),
    net_price DECIMAL(18,2),
    item_delivery_status VARCHAR(50),          -- LIPS.Delivery Status (item-level, distinct from fact_delivery.delivery_status)
    delivery_date DATE,
    PRIMARY KEY (delivery_id, item_number),
    FOREIGN KEY (delivery_id) REFERENCES fact_delivery(delivery_id),
    FOREIGN KEY (product_id) REFERENCES dim_product(product_id)
);

CREATE TABLE IF NOT EXISTS fact_shipment (
    shipment_id BIGINT PRIMARY KEY,           -- VTTK.Shipment Number
    delivery_id BIGINT,
    order_id BIGINT,
    customer_id VARCHAR(30),                  -- VTTK.Customer ID (redundant with fact_delivery, kept for full source fidelity)
    carrier_name VARCHAR(50),
    shipping_point VARCHAR(50),
    shipment_date DATE,
    shipment_status VARCHAR(50),
    route INT,
    shipping_type VARCHAR(50),
    FOREIGN KEY (delivery_id) REFERENCES fact_delivery(delivery_id),
    FOREIGN KEY (carrier_name) REFERENCES dim_carrier(carrier_name)
);

CREATE TABLE IF NOT EXISTS fact_shipment_item (
    shipment_id BIGINT,
    item_number INT,
    product_id VARCHAR(50),
    delivery_id BIGINT,
    order_id BIGINT,
    customer_id VARCHAR(30),                  -- VTTP.Customer ID (redundant with fact_delivery/fact_shipment, kept for full source fidelity)
    sales_item INT,
    shipped_quantity DECIMAL(18,3),
    item_status VARCHAR(50),
    shipment_date DATE,
    PRIMARY KEY (shipment_id, item_number),
    FOREIGN KEY (shipment_id) REFERENCES fact_shipment(shipment_id),
    FOREIGN KEY (product_id) REFERENCES dim_product(product_id)
);

CREATE INDEX idx_order_date ON fact_order(order_date);
CREATE INDEX idx_delivery_order ON fact_delivery(order_id);
CREATE INDEX idx_shipment_delivery ON fact_shipment(delivery_id);
CREATE INDEX idx_orderitem_product ON fact_order_item(product_id);

-- Delivery_Analytics: requested by the case study brief as a custom table
-- storing delivery performance metrics (delivery_time, on_time, delay_reason).
--
-- IMPORTANT LIMITATION (documented, not silently worked around):
-- The source data (VBAP/LIPS/VTTK/VTTP) only contains DATE fields, never
-- timestamps. "delivery_time in minutes" as literally described in the
-- brief cannot be computed from this data. delivery_time_days is a
-- day-level proxy instead: (LIPS.Delivery Date - VBAP.Delivery Date),
-- i.e. actual item delivery date minus requested item delivery date.
-- on_time is TRUE when that gap is <= 0 days. delay_reason has no source
-- field anywhere in the workbook, so it is always NULL here -- this is a
-- genuine data gap, not a bug, and should be raised with the trainer if
-- delay-reason reporting is a required KPI.
CREATE TABLE IF NOT EXISTS fact_delivery_analytics (
    analytics_id INT AUTO_INCREMENT PRIMARY KEY,
    order_id BIGINT,
    item_number INT,
    shipment_id BIGINT,
    delivery_time_days INT,
    on_time BOOLEAN,
    delay_reason VARCHAR(200),
    FOREIGN KEY (order_id, item_number) REFERENCES fact_order_item(order_id, item_number),
    FOREIGN KEY (shipment_id) REFERENCES fact_shipment(shipment_id)
);
