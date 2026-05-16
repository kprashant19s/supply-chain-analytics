-- ============================================================
-- FILE: 01_schema.sql
-- PURPOSE: Create all 4 tables for our star schema
-- ============================================================

USE supply_chain_dw;

CREATE TABLE IF NOT EXISTS dim_customer (
    customer_id       INT AUTO_INCREMENT PRIMARY KEY,
    customer_fname    VARCHAR(100),
    customer_lname    VARCHAR(100),
    customer_segment  VARCHAR(50),
    customer_city     VARCHAR(100),
    customer_state    VARCHAR(100),
    customer_country  VARCHAR(100),
    customer_zipcode  VARCHAR(20)
);

CREATE TABLE IF NOT EXISTS dim_product (
    product_id        INT AUTO_INCREMENT PRIMARY KEY,
    product_name      VARCHAR(200),
    product_category  VARCHAR(100),
    product_price     DECIMAL(10,2),
    department_name   VARCHAR(100)
);

CREATE TABLE IF NOT EXISTS dim_supplier (
    supplier_id   INT AUTO_INCREMENT PRIMARY KEY,
    market        VARCHAR(50),
    order_region  VARCHAR(100),
    shipping_mode VARCHAR(50)
);

CREATE TABLE IF NOT EXISTS fact_orders (
    order_item_id          INT AUTO_INCREMENT PRIMARY KEY,
    order_id               INT           NOT NULL,
    customer_id            INT,
    product_id             INT,
    supplier_id            INT,
    order_date             DATE,
    shipping_date          DATE,
    scheduled_ship_days    INT,
    actual_ship_days       INT,
    sales_per_order        DECIMAL(12,2),
    order_profit_per_order DECIMAL(12,2),
    order_item_discount    DECIMAL(5,4),
    order_item_quantity    INT,
    is_delayed             TINYINT(1)    DEFAULT 0,
    delivery_status        VARCHAR(50),
    late_delivery_risk     TINYINT(1)    DEFAULT 0,

    CONSTRAINT fk_customer FOREIGN KEY (customer_id)
        REFERENCES dim_customer(customer_id),
    CONSTRAINT fk_product  FOREIGN KEY (product_id)
        REFERENCES dim_product(product_id),
    CONSTRAINT fk_supplier FOREIGN KEY (supplier_id)
        REFERENCES dim_supplier(supplier_id)
);