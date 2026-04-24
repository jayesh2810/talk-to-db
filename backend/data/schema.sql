CREATE TABLE IF NOT EXISTS customers (
    customer_id    TEXT PRIMARY KEY,
    name           TEXT NOT NULL,
    email          TEXT,
    signup_date    DATE,
    city           TEXT,
    state          TEXT,
    segment        TEXT,
    acq_channel    TEXT,
    lifetime_value REAL
);

CREATE TABLE IF NOT EXISTS products (
    product_id    TEXT PRIMARY KEY,
    name          TEXT NOT NULL,
    category      TEXT,
    subcategory   TEXT,
    price         REAL,
    cost          REAL,
    avg_rating    REAL,
    review_count  INTEGER,
    stock_level   INTEGER
);

CREATE TABLE IF NOT EXISTS orders (
    order_id      TEXT PRIMARY KEY,
    customer_id   TEXT REFERENCES customers(customer_id),
    order_date    DATE,
    total_amount  REAL,
    discount      REAL DEFAULT 0,
    shipping      TEXT,
    status        TEXT,
    delivery_days INTEGER,
    promised_days INTEGER
);

CREATE TABLE IF NOT EXISTS order_items (
    item_id    TEXT PRIMARY KEY,
    order_id   TEXT REFERENCES orders(order_id),
    product_id TEXT REFERENCES products(product_id),
    quantity   INTEGER,
    unit_price REAL,
    returned   BOOLEAN DEFAULT FALSE
);

CREATE TABLE IF NOT EXISTS interactions (
    interaction_id   TEXT PRIMARY KEY,
    customer_id      TEXT REFERENCES customers(customer_id),
    interaction_date DATE,
    channel          TEXT,
    topic            TEXT,
    sentiment        TEXT,
    resolved         BOOLEAN,
    resolution_hours REAL
);

CREATE TABLE IF NOT EXISTS campaign_touchpoints (
    touchpoint_id TEXT PRIMARY KEY,
    customer_id   TEXT REFERENCES customers(customer_id),
    campaign_id   TEXT,
    campaign_name TEXT,
    campaign_type TEXT,
    sent_date     DATE,
    opened        BOOLEAN,
    clicked       BOOLEAN,
    converted     BOOLEAN
);
