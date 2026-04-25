"""
Seed the SQLite database with realistic e-commerce data.

Customer profiles are designed so scoring signals are unambiguous:
  - High churn (C001-C007): score 0.75+
  - Low churn (C008-C019): score 0.10-0.25
  - Ambiguous (C020-C027): score 0.35-0.55
  - Fraud signal (C028-C031): high fraud_risk score

Run normally (seed if DB doesn't exist):
    python data/seed.py

Force reseed:
    python data/seed.py --reseed
"""

import sqlite3
import datetime
import sys
from pathlib import Path

DB_PATH = Path(__file__).parent / "ecommerce.db"
GRAPH_PATH = Path(__file__).parent / "graph.graphml"
SCHEMA_PATH = Path(__file__).parent / "schema.sql"

today = datetime.date.today()


def d(days_back: int) -> str:
    """Return ISO date string for N days ago."""
    return (today - datetime.timedelta(days=days_back)).isoformat()


# ─── Customers ───────────────────────────────────────────────────────────────

CUSTOMERS = [
    # High churn risk (C001-C007): last order 72-110 days ago, high return/complaint rates
    ("C001", "Emma Rodriguez",    "emma.r@email.com",   d(380), "Chicago",      "IL", "at_risk",   "paid_search", 342.50),
    ("C002", "Marcus Thompson",   "m.thompson@mail.com", d(310), "Houston",     "TX", "at_risk",   "social",      418.20),
    ("C003", "Sofia Chen",        "sofia.c@email.com",  d(290), "Phoenix",      "AZ", "at_risk",   "paid_search", 287.90),
    ("C004", "Derek Williams",    "derek.w@mail.com",   d(420), "Philadelphia", "PA", "at_risk",   "organic",     521.00),
    ("C005", "Priya Patel",       "priya.p@email.com",  d(350), "San Antonio",  "TX", "at_risk",   "email",       394.75),
    ("C006", "Jason Kim",         "j.kim@mail.com",     d(400), "San Diego",    "CA", "at_risk",   "referral",    463.30),
    ("C007", "Lisa Nguyen",       "lisa.n@email.com",   d(330), "Dallas",       "TX", "at_risk",   "social",      312.60),

    # Low churn risk (C008-C019): last order 2-14 days ago, VIP/returning, high engagement
    ("C008", "James Anderson",    "j.anderson@mail.com", d(540), "New York",    "NY", "vip",       "organic",    2840.00),
    ("C009", "Sarah Johnson",     "s.johnson@email.com", d(720), "Los Angeles", "CA", "vip",       "referral",   3150.50),
    ("C010", "Michael Brown",     "m.brown@mail.com",   d(610), "Chicago",      "IL", "vip",       "organic",    2670.80),
    ("C011", "Jennifer Davis",    "j.davis@email.com",  d(480), "Houston",      "TX", "vip",       "email",      1920.40),
    ("C012", "Robert Martinez",   "r.martinez@mail.com", d(550), "Phoenix",     "AZ", "vip",       "paid_search", 2210.60),
    ("C013", "Emily Wilson",      "e.wilson@email.com", d(390), "Philadelphia", "PA", "vip",       "referral",   1780.90),
    ("C014", "David Taylor",      "d.taylor@mail.com",  d(460), "San Antonio",  "TX", "returning", "organic",    1150.20),
    ("C015", "Amanda Garcia",     "a.garcia@email.com", d(320), "San Diego",    "CA", "returning", "social",      987.40),
    ("C016", "Christopher Lee",   "c.lee@mail.com",     d(410), "Dallas",       "TX", "returning", "email",      1340.70),
    ("C017", "Ashley White",      "a.white@email.com",  d(580), "Jacksonville", "FL", "vip",       "referral",   2050.10),
    ("C018", "Daniel Harris",     "d.harris@mail.com",  d(275), "Columbus",     "OH", "returning", "organic",     876.30),
    ("C019", "Jessica Clark",     "j.clark@email.com",  d(365), "Charlotte",    "NC", "returning", "paid_search", 1105.80),

    # Ambiguous (C020-C027): mixed signals, moderate engagement
    ("C020", "Thomas Lewis",      "t.lewis@mail.com",   d(440), "Indianapolis", "IN", "returning", "email",      1680.90),
    ("C021", "Nicole Robinson",   "n.robinson@email.com", d(500),"San Francisco","CA", "returning", "social",    1240.50),
    ("C022", "Anthony Walker",    "a.walker@mail.com",  d(310), "Seattle",      "WA", "returning", "paid_search", 890.20),
    ("C023", "Megan Hall",        "m.hall@email.com",   d(65),  "Denver",       "CO", "new",       "social",      210.40),
    ("C024", "Kevin Allen",       "k.allen@mail.com",   d(280), "Nashville",    "TN", "returning", "referral",    760.80),
    ("C025", "Rachel Young",      "r.young@email.com",  d(350), "Louisville",   "KY", "returning", "organic",     934.60),
    ("C026", "Brian King",        "b.king@mail.com",    d(290), "Baltimore",    "MD", "returning", "email",       820.30),
    ("C027", "Stephanie Wright",  "s.wright@email.com", d(420), "Milwaukee",    "WI", "returning", "paid_search", 1050.70),

    # Fraud signal (C028-C031): new accounts, suspicious order patterns
    ("C028", "Alex Turner",       "alex.t@temp.com",    d(12),  "New York",     "NY", "new",       "paid_search",  450.00),
    ("C029", "Jordan Mitchell",   "j.mitchell@fast.com", d(8),  "Los Angeles",  "CA", "new",       "paid_search",  389.00),
    ("C030", "Sam Rivera",        "s.rivera@quick.com", d(5),   "Chicago",      "IL", "new",       "paid_search",  512.00),
    ("C031", "Casey Brooks",      "c.brooks@temp.com",  d(10),  "Houston",      "TX", "new",       "paid_search",  620.00),
]

# ─── Products (40 total) ──────────────────────────────────────────────────────
# P001-P010: Electronics (shared by high-churn peer group)
# P011-P020: Apparel
# P021-P027: Home
# P028-P034: Beauty
# P035-P037: Food
# P038-P040: Sports

PRODUCTS = [
    # Electronics — mostly bought by high-churn customers (C001-C007) creating peer signal
    ("P001", "ProBook Laptop 15\"",       "electronics", "computers",    849.99, 420.00, 3.8, 142, 28),
    ("P002", "TrueSound Wireless Earbuds","electronics", "audio",         89.99,  32.00, 4.1, 387, 94),
    ("P003", "Pixel HD Webcam 4K",        "electronics", "accessories",   79.99,  28.00, 3.9, 201, 65),
    ("P004", "StreamDeck Controller",     "electronics", "accessories",  149.99,  58.00, 4.0, 178, 43),
    ("P005", "UltraCharge 65W Hub",       "electronics", "accessories",   49.99,  14.00, 3.7, 296, 112),
    ("P006", "Nova Tab 10 Pro",           "electronics", "tablets",      399.99, 180.00, 3.6, 89,  37),
    ("P007", "SmartWatch Fit Pro",        "electronics", "wearables",    199.99,  82.00, 4.2, 312, 58),
    ("P008", "Gaming Mouse RGB",          "electronics", "accessories",   69.99,  22.00, 4.4, 445, 130),
    ("P009", "Mechanical Keyboard TKL",   "electronics", "accessories",  119.99,  48.00, 4.5, 523, 88),
    ("P010", "Portable SSD 1TB",          "electronics", "storage",       89.99,  35.00, 4.6, 634, 156),

    # Apparel
    ("P011", "Classic Oxford Shirt",      "apparel",     "tops",          59.99,  18.00, 4.3, 289, 200),
    ("P012", "Slim Fit Chinos",           "apparel",     "bottoms",       74.99,  22.00, 4.1, 198, 175),
    ("P013", "Merino Wool Sweater",       "apparel",     "tops",          89.99,  28.00, 4.5, 312, 140),
    ("P014", "Running Sneakers Air",      "apparel",     "footwear",     119.99,  42.00, 4.4, 456, 98),
    ("P015", "Leather Jacket Moto",       "apparel",     "outerwear",    189.99,  72.00, 4.2, 167, 65),
    ("P016", "Floral Wrap Dress",         "apparel",     "dresses",       64.99,  20.00, 4.0, 223, 118),
    ("P017", "Athletic Leggings Pro",     "apparel",     "activewear",    54.99,  16.00, 4.3, 378, 210),
    ("P018", "Canvas Tote Bag",           "apparel",     "accessories",   34.99,   9.00, 4.1, 445, 280),
    ("P019", "Wool Beanie Hat",           "apparel",     "accessories",   24.99,   7.00, 4.2, 567, 340),
    ("P020", "Cashmere Scarf",            "apparel",     "accessories",   69.99,  25.00, 4.6, 234, 95),

    # Home
    ("P021", "Bamboo Cutting Board Set",  "home",        "kitchen",       44.99,  14.00, 4.7, 789, 245),
    ("P022", "Weighted Blanket 15lb",     "home",        "bedding",       79.99,  28.00, 4.8, 1023, 180),
    ("P023", "Ceramic Pour-Over Kit",     "home",        "kitchen",       54.99,  18.00, 4.6, 456, 134),
    ("P024", "LED Desk Lamp Smart",       "home",        "lighting",      59.99,  20.00, 4.5, 378, 167),
    ("P025", "Linen Duvet Cover King",    "home",        "bedding",       89.99,  30.00, 4.4, 234, 78),
    ("P026", "Herb Garden Starter Kit",   "home",        "garden",        39.99,  12.00, 4.3, 567, 212),
    ("P027", "Stainless Steel Water Bottle","home",      "kitchen",       29.99,   8.00, 4.7, 1234, 380),

    # Beauty
    ("P028", "Vitamin C Serum 30ml",      "beauty",      "skincare",      45.99,  12.00, 4.5, 678, 234),
    ("P029", "Retinol Night Cream",       "beauty",      "skincare",      52.99,  15.00, 4.4, 456, 178),
    ("P030", "SPF 50 Daily Moisturizer",  "beauty",      "skincare",      38.99,  10.00, 4.6, 789, 312),
    ("P031", "Rose Clay Face Mask",       "beauty",      "skincare",      28.99,   7.00, 4.3, 567, 245),
    ("P032", "Volumizing Mascara Pro",    "beauty",      "makeup",        24.99,   6.00, 4.2, 890, 430),
    ("P033", "Argan Oil Hair Treatment",  "beauty",      "hair care",     34.99,   9.00, 4.5, 345, 198),
    ("P034", "Electric Face Cleanser",    "beauty",      "skincare",      79.99,  28.00, 4.1, 234, 89),

    # Food
    ("P035", "Single Origin Coffee 1kg",  "food",        "beverages",     42.99,  18.00, 4.8, 1456, 320),
    ("P036", "Dark Chocolate Variety Box","food",        "confectionery", 34.99,  14.00, 4.7, 890, 280),
    ("P037", "Matcha Ceremony Grade",     "food",        "beverages",     29.99,  11.00, 4.6, 567, 198),

    # Sports
    ("P038", "Resistance Band Set Pro",   "sports",      "fitness",       34.99,  10.00, 4.6, 789, 340),
    ("P039", "Foam Roller Density Grid",  "sports",      "recovery",      39.99,  12.00, 4.5, 456, 212),
    ("P040", "Jump Rope Speed Cable",     "sports",      "fitness",       24.99,   7.00, 4.4, 678, 390),
]

# ─── Orders ──────────────────────────────────────────────────────────────────
# Format: (order_id, customer_id, order_date, total_amount, discount,
#          shipping, status, delivery_days, promised_days)

ORDERS = [
    # High-churn customers: old last orders, returns, late deliveries
    ("O001", "C001", d(110), 234.98, 0,     "standard", "returned",   9, 5),
    ("O002", "C001", d(85),   98.48, 10,    "standard", "completed",  8, 5),
    ("O003", "C001", d(72),  156.47, 0,     "express",  "completed",  7, 3),  # last order

    ("O011", "C002", d(120), 312.97, 15,    "standard", "returned",   10, 5),
    ("O012", "C002", d(95),   87.48, 0,     "standard", "completed",  9, 5),
    ("O013", "C002", d(78),  199.99, 0,     "express",  "returned",   8, 3),  # last order

    ("O021", "C003", d(105), 479.97, 0,     "standard", "returned",   11, 5),
    ("O022", "C003", d(82),  129.98, 5,     "standard", "completed",  10, 5),
    ("O023", "C003", d(74),   89.99, 0,     "standard", "completed",  9, 5),  # last order

    ("O031", "C004", d(130), 399.98, 0,     "express",  "returned",   8, 3),
    ("O032", "C004", d(100), 219.97, 10,    "standard", "completed",  11, 5),
    ("O033", "C004", d(88),  149.99, 0,     "standard", "completed",  10, 5),
    ("O034", "C004", d(76),  289.96, 0,     "standard", "returned",   12, 5),  # last order

    ("O041", "C005", d(115), 269.97, 0,     "standard", "returned",   9, 5),
    ("O042", "C005", d(91),  139.98, 8,     "standard", "completed",  8, 5),
    ("O043", "C005", d(80),   79.99, 0,     "standard", "completed",  9, 5),  # last order

    ("O051", "C006", d(125), 449.97, 0,     "express",  "returned",   7, 3),
    ("O052", "C006", d(98),  189.98, 12,    "standard", "completed",  10, 5),
    ("O053", "C006", d(77),  259.97, 0,     "standard", "returned",   11, 5),  # last order

    ("O061", "C007", d(108), 199.97, 0,     "standard", "returned",   10, 5),
    ("O062", "C007", d(86),  119.98, 0,     "standard", "completed",  9, 5),
    ("O063", "C007", d(73),   89.99, 5,     "standard", "completed",  8, 5),  # last order

    # Low-churn VIP customers: recent orders, low returns, fast delivery
    ("O101", "C008", d(90),  389.97, 20,    "express",  "completed",  2, 3),
    ("O102", "C008", d(60),  245.96, 15,    "express",  "completed",  2, 3),
    ("O103", "C008", d(30),  419.95, 25,    "express",  "completed",  2, 3),
    ("O104", "C008", d(3),   289.97, 10,    "same_day", "completed",  1, 1),  # last order

    ("O111", "C009", d(85),  512.96, 30,    "express",  "completed",  2, 3),
    ("O112", "C009", d(55),  378.95, 20,    "express",  "completed",  2, 3),
    ("O113", "C009", d(25),  445.97, 25,    "express",  "completed",  2, 3),
    ("O114", "C009", d(7),   312.96, 15,    "same_day", "completed",  1, 1),

    ("O121", "C010", d(80),  278.96, 15,    "express",  "completed",  2, 3),
    ("O122", "C010", d(50),  334.95, 20,    "express",  "completed",  2, 3),
    ("O123", "C010", d(20),  389.97, 18,    "express",  "completed",  2, 3),
    ("O124", "C010", d(5),   256.96, 10,    "same_day", "completed",  1, 1),

    ("O131", "C011", d(75),  189.97, 10,    "standard", "completed",  4, 5),
    ("O132", "C011", d(45),  234.96, 12,    "express",  "completed",  2, 3),
    ("O133", "C011", d(15),  312.95, 15,    "express",  "completed",  2, 3),
    ("O134", "C011", d(2),   198.97, 8,     "same_day", "completed",  1, 1),

    ("O141", "C012", d(70),  445.96, 25,    "express",  "completed",  2, 3),
    ("O142", "C012", d(40),  289.95, 15,    "express",  "completed",  2, 3),
    ("O143", "C012", d(10),  367.97, 20,    "express",  "completed",  2, 3),

    ("O151", "C013", d(65),  234.97, 12,    "standard", "completed",  4, 5),
    ("O152", "C013", d(35),  312.96, 18,    "express",  "completed",  2, 3),
    ("O153", "C013", d(4),   278.95, 14,    "express",  "completed",  2, 3),

    ("O161", "C014", d(60),  189.97, 8,     "standard", "completed",  5, 5),
    ("O162", "C014", d(30),  245.96, 10,    "standard", "completed",  4, 5),
    ("O163", "C014", d(8),   198.95, 5,     "express",  "completed",  3, 3),

    ("O171", "C015", d(55),  156.97, 5,     "standard", "completed",  5, 5),
    ("O172", "C015", d(25),  212.96, 8,     "standard", "completed",  4, 5),
    ("O173", "C015", d(12),  178.95, 6,     "express",  "completed",  3, 3),

    ("O181", "C016", d(50),  289.97, 15,    "standard", "completed",  5, 5),
    ("O182", "C016", d(20),  334.96, 18,    "express",  "completed",  3, 3),
    ("O183", "C016", d(6),   256.95, 12,    "express",  "completed",  2, 3),

    ("O191", "C017", d(75),  512.96, 30,    "express",  "completed",  2, 3),
    ("O192", "C017", d(45),  467.95, 25,    "express",  "completed",  2, 3),
    ("O193", "C017", d(15),  389.97, 20,    "express",  "completed",  2, 3),
    ("O194", "C017", d(9),   312.96, 15,    "same_day", "completed",  1, 1),

    ("O201", "C018", d(65),  198.97, 8,     "standard", "completed",  5, 5),
    ("O202", "C018", d(35),  234.96, 10,    "standard", "completed",  4, 5),
    ("O203", "C018", d(11),  189.95, 7,     "express",  "completed",  3, 3),

    ("O211", "C019", d(70),  245.97, 12,    "standard", "completed",  5, 5),
    ("O212", "C019", d(40),  289.96, 14,    "standard", "completed",  4, 5),
    ("O213", "C019", d(14),  212.95, 9,     "express",  "completed",  3, 3),

    # Ambiguous customers: mixed recency, some returns
    ("O301", "C020", d(200), 789.97, 40,    "express",  "completed",  2, 3),
    ("O302", "C020", d(120), 456.96, 25,    "express",  "completed",  3, 3),
    ("O303", "C020", d(32),  234.95, 12,    "standard", "completed",  6, 5),  # last order, late

    ("O311", "C021", d(400), 312.97, 15,    "standard", "completed",  5, 5),
    ("O312", "C021", d(370), 278.96, 12,    "standard", "completed",  4, 5),
    # seasonal pattern - nothing for 11 months, then active Q4
    ("O313", "C021", d(28),  198.95, 8,     "standard", "completed",  5, 5),

    ("O321", "C022", d(150), 189.97, 8,     "standard", "completed",  6, 5),
    ("O322", "C022", d(95),  234.96, 10,    "standard", "completed",  7, 5),
    ("O323", "C022", d(45),  156.95, 5,     "standard", "completed",  6, 5),  # last order

    ("O331", "C023", d(50),  178.97, 0,     "standard", "completed",  5, 5),
    ("O332", "C023", d(22),  134.96, 0,     "standard", "completed",  5, 5),  # last order, new customer

    ("O341", "C024", d(180), 256.97, 12,    "standard", "completed",  5, 5),
    ("O342", "C024", d(100), 189.96, 8,     "standard", "returned",   8, 5),
    ("O343", "C024", d(38),  145.95, 0,     "standard", "completed",  6, 5),  # last order

    ("O351", "C025", d(130), 334.97, 18,    "express",  "completed",  3, 3),
    ("O352", "C025", d(80),  245.96, 12,    "standard", "completed",  5, 5),
    ("O353", "C025", d(25),  198.95, 8,     "standard", "completed",  5, 5),  # last order

    ("O361", "C026", d(160), 212.97, 10,    "standard", "completed",  5, 5),
    ("O362", "C026", d(90),  178.96, 8,     "standard", "returned",   9, 5),
    ("O363", "C026", d(42),  134.95, 0,     "standard", "completed",  6, 5),  # last order

    ("O371", "C027", d(190), 289.97, 15,    "express",  "completed",  3, 3),
    ("O372", "C027", d(110), 234.96, 12,    "standard", "returned",   8, 5),
    ("O373", "C027", d(35),  189.95, 8,     "standard", "completed",  5, 5),  # last order

    # Fraud-signal customers: large orders, new accounts
    ("O401", "C028", d(11),  449.97, 0,     "express",  "completed",  2, 3),  # large order, new account
    ("O402", "C028", d(9),   389.98, 0,     "express",  "returned",   2, 3),  # immediate return

    ("O411", "C029", d(7),   312.97, 0,     "express",  "completed",  2, 3),  # 3-day order flurry
    ("O412", "C029", d(6),   278.98, 0,     "express",  "completed",  2, 3),
    ("O413", "C029", d(5),   445.97, 0,     "express",  "pending",    2, 3),

    ("O421", "C030", d(4),   512.97, 0,     "express",  "completed",  2, 3),  # huge order, new account
    ("O422", "C030", d(3),   489.98, 0,     "express",  "returned",   1, 3),  # immediate full return

    ("O431", "C031", d(9),   289.97, 0,     "express",  "completed",  2, 3),
    ("O432", "C031", d(7),   620.98, 0,     "express",  "completed",  2, 3),  # high-value order
    ("O433", "C031", d(5),   534.97, 0,     "express",  "pending",    2, 3),
]

# ─── Order Items ──────────────────────────────────────────────────────────────
# High-churn customers share electronics products (P001-P008) creating peer signal
# Low-churn VIP customers share home/beauty/apparel products (P021-P035)

ORDER_ITEMS = [
    # C001 (Emma Rodriguez) - high churn
    ("I001", "O001", "P001", 1, 849.99, False),  # laptop (shared with other high-churn)
    ("I002", "O001", "P002", 1,  89.99, True),   # earbuds (returned)
    ("I003", "O002", "P003", 1,  79.99, False),  # webcam
    ("I004", "O002", "P005", 1,  49.99, False),  # USB hub
    ("I005", "O003", "P004", 1, 149.99, False),  # StreamDeck
    ("I006", "O003", "P002", 1,  89.99, False),  # earbuds (again)

    # C002 (Marcus Thompson) - high churn, shares P001, P003, P006 with C001 peer group
    ("I011", "O011", "P001", 1, 849.99, True),   # laptop (returned)
    ("I012", "O011", "P006", 1, 399.99, False),  # tablet
    ("I013", "O012", "P003", 1,  79.99, False),  # webcam (shared with C001)
    ("I014", "O012", "P005", 1,  49.99, False),  # hub
    ("I015", "O013", "P007", 1, 199.99, True),   # smartwatch (returned)

    # C003 (Sofia Chen) - high churn, shares P001, P002, P004 with peer group
    ("I021", "O021", "P006", 1, 399.99, True),   # tablet (returned)
    ("I022", "O021", "P004", 1, 149.99, False),  # StreamDeck
    ("I023", "O021", "P002", 1,  89.99, False),  # earbuds (shared with C001)
    ("I024", "O022", "P001", 1, 849.99, False),  # laptop (shared with C001)
    ("I025", "O023", "P005", 1,  49.99, False),  # hub

    # C004 (Derek Williams) - high churn, shares P003, P006, P007
    ("I031", "O031", "P007", 1, 199.99, True),   # smartwatch (returned)
    ("I032", "O031", "P006", 1, 399.99, False),  # tablet (shared with C002)
    ("I033", "O032", "P003", 1,  79.99, False),  # webcam (shared peer)
    ("I034", "O032", "P008", 2,  69.99, False),  # gaming mice x2
    ("I035", "O033", "P009", 1, 119.99, False),  # keyboard
    ("I036", "O034", "P001", 1, 849.99, True),   # laptop (returned, shared)

    # C005 (Priya Patel) - high churn, shares P001, P002
    ("I041", "O041", "P001", 1, 849.99, True),   # laptop (returned, shared with C001)
    ("I042", "O041", "P005", 2,  49.99, False),  # USB hubs
    ("I043", "O042", "P002", 1,  89.99, False),  # earbuds (shared with C001)
    ("I044", "O042", "P003", 1,  79.99, False),  # webcam
    ("I045", "O043", "P004", 1, 149.99, False),  # StreamDeck

    # C006 (Jason Kim) - high churn, shares P006, P007, P008
    ("I051", "O051", "P006", 1, 399.99, True),   # tablet (returned, shared)
    ("I052", "O051", "P007", 1, 199.99, False),  # smartwatch (shared with C004)
    ("I053", "O052", "P008", 2,  69.99, False),  # gaming mice (shared with C004)
    ("I054", "O052", "P009", 1, 119.99, False),  # keyboard
    ("I055", "O053", "P002", 1,  89.99, True),   # earbuds (returned, shared)
    ("I056", "O053", "P005", 2,  49.99, False),  # hubs

    # C007 (Lisa Nguyen) - high churn, shares P003, P004, P007
    ("I061", "O061", "P003", 1,  79.99, True),   # webcam (returned, shared)
    ("I062", "O061", "P004", 1, 149.99, False),  # StreamDeck (shared with C001)
    ("I063", "O062", "P007", 1, 199.99, False),  # smartwatch (shared with C004/C006)
    ("I064", "O062", "P005", 1,  49.99, False),  # hub
    ("I065", "O063", "P009", 1, 119.99, False),  # keyboard

    # C008 (James Anderson) - VIP, shares home/beauty products
    ("I101", "O101", "P021", 2,  44.99, False),  # cutting boards
    ("I102", "O101", "P022", 1,  79.99, False),  # weighted blanket
    ("I103", "O101", "P027", 3,  29.99, False),  # water bottles
    ("I104", "O102", "P023", 1,  54.99, False),  # pour-over
    ("I105", "O102", "P028", 2,  45.99, False),  # serum
    ("I106", "O103", "P022", 1,  79.99, False),  # blanket (gift)
    ("I107", "O103", "P035", 2,  42.99, False),  # coffee
    ("I108", "O104", "P024", 1,  59.99, False),  # lamp
    ("I109", "O104", "P036", 2,  34.99, False),  # chocolate

    # C009 (Sarah Johnson) - VIP, shares P022, P028, P035
    ("I111", "O111", "P022", 1,  79.99, False),  # weighted blanket (shared with C008)
    ("I112", "O111", "P028", 2,  45.99, False),  # serum (shared with C008)
    ("I113", "O111", "P013", 1,  89.99, False),  # sweater
    ("I114", "O112", "P029", 2,  52.99, False),  # retinol cream
    ("I115", "O112", "P030", 1,  38.99, False),  # SPF
    ("I116", "O113", "P035", 2,  42.99, False),  # coffee (shared)
    ("I117", "O113", "P021", 1,  44.99, False),  # cutting board
    ("I118", "O114", "P033", 2,  34.99, False),  # argan oil

    # C010 (Michael Brown) - VIP
    ("I121", "O121", "P025", 1,  89.99, False),
    ("I122", "O121", "P035", 2,  42.99, False),  # coffee
    ("I123", "O122", "P038", 1,  34.99, False),
    ("I124", "O122", "P039", 1,  39.99, False),
    ("I125", "O123", "P021", 1,  44.99, False),
    ("I126", "O123", "P027", 2,  29.99, False),
    ("I127", "O124", "P030", 2,  38.99, False),

    # C011 (Jennifer Davis) - VIP
    ("I131", "O131", "P028", 2,  45.99, False),
    ("I132", "O131", "P031", 2,  28.99, False),
    ("I133", "O132", "P016", 2,  64.99, False),
    ("I134", "O132", "P017", 1,  54.99, False),
    ("I135", "O133", "P029", 1,  52.99, False),
    ("I136", "O133", "P033", 2,  34.99, False),
    ("I137", "O134", "P020", 1,  69.99, False),

    # C012 (Robert Martinez) - VIP
    ("I141", "O141", "P022", 1,  79.99, False),
    ("I142", "O141", "P013", 2,  89.99, False),
    ("I143", "O141", "P014", 1, 119.99, False),
    ("I144", "O142", "P035", 3,  42.99, False),
    ("I145", "O142", "P036", 2,  34.99, False),
    ("I146", "O143", "P038", 2,  34.99, False),
    ("I147", "O143", "P027", 3,  29.99, False),

    # C013 (Emily Wilson) - VIP
    ("I151", "O151", "P028", 2,  45.99, False),
    ("I152", "O151", "P030", 2,  38.99, False),
    ("I153", "O152", "P016", 2,  64.99, False),
    ("I154", "O152", "P020", 1,  69.99, False),
    ("I155", "O153", "P031", 2,  28.99, False),
    ("I156", "O153", "P034", 1,  79.99, False),

    # C014-C019 (returning customers) - simplified
    ("I161", "O161", "P011", 2,  59.99, False),
    ("I162", "O161", "P026", 1,  39.99, False),
    ("I163", "O162", "P037", 2,  29.99, False),
    ("I164", "O162", "P040", 1,  24.99, False),
    ("I165", "O163", "P012", 1,  74.99, False),

    ("I171", "O171", "P015", 1, 189.99, False),
    ("I172", "O171", "P018", 2,  34.99, False),
    ("I173", "O172", "P019", 3,  24.99, False),
    ("I174", "O172", "P040", 2,  24.99, False),
    ("I175", "O173", "P011", 1,  59.99, False),

    ("I181", "O181", "P023", 1,  54.99, False),
    ("I182", "O181", "P024", 2,  59.99, False),
    ("I183", "O182", "P026", 2,  39.99, False),
    ("I184", "O182", "P027", 3,  29.99, False),
    ("I185", "O183", "P021", 2,  44.99, False),

    ("I191", "O191", "P022", 2,  79.99, False),
    ("I192", "O191", "P013", 2,  89.99, False),
    ("I193", "O192", "P035", 3,  42.99, False),
    ("I194", "O192", "P036", 3,  34.99, False),
    ("I195", "O193", "P029", 2,  52.99, False),
    ("I196", "O193", "P030", 2,  38.99, False),
    ("I197", "O194", "P033", 2,  34.99, False),

    ("I201", "O201", "P038", 1,  34.99, False),
    ("I202", "O201", "P039", 2,  39.99, False),
    ("I203", "O202", "P040", 3,  24.99, False),
    ("I204", "O202", "P026", 1,  39.99, False),
    ("I205", "O203", "P027", 2,  29.99, False),

    ("I211", "O211", "P011", 2,  59.99, False),
    ("I212", "O211", "P012", 1,  74.99, False),
    ("I213", "O212", "P013", 1,  89.99, False),
    ("I214", "O212", "P018", 2,  34.99, False),
    ("I215", "O213", "P019", 2,  24.99, False),

    # Ambiguous customers
    ("I301", "O301", "P010", 1,  89.99, False),  # SSD
    ("I302", "O301", "P009", 2, 119.99, False),  # keyboards
    ("I303", "O302", "P008", 2,  69.99, False),  # gaming mice (shared with high-churn!)
    ("I304", "O302", "P004", 1, 149.99, False),  # StreamDeck (shared with C001!)
    ("I305", "O303", "P011", 1,  59.99, False),

    ("I311", "O311", "P014", 1, 119.99, False),
    ("I312", "O311", "P015", 1, 189.99, False),
    ("I313", "O312", "P016", 2,  64.99, False),
    ("I314", "O313", "P017", 2,  54.99, False),

    ("I321", "O321", "P023", 1,  54.99, False),
    ("I322", "O321", "P024", 2,  59.99, False),
    ("I323", "O322", "P026", 1,  39.99, False),
    ("I324", "O322", "P027", 2,  29.99, False),
    ("I325", "O323", "P021", 1,  44.99, False),

    ("I331", "O331", "P028", 1,  45.99, False),
    ("I332", "O331", "P031", 1,  28.99, False),
    ("I333", "O332", "P030", 2,  38.99, False),

    ("I341", "O341", "P003", 1,  79.99, False),  # webcam (shared with high-churn!)
    ("I342", "O341", "P005", 2,  49.99, False),
    ("I343", "O342", "P007", 1, 199.99, True),   # smartwatch (returned, shared with C004)
    ("I344", "O343", "P012", 1,  74.99, False),

    ("I351", "O351", "P022", 1,  79.99, False),
    ("I352", "O351", "P013", 2,  89.99, False),
    ("I353", "O352", "P035", 2,  42.99, False),
    ("I354", "O352", "P021", 1,  44.99, False),
    ("I355", "O353", "P027", 2,  29.99, False),

    ("I361", "O361", "P011", 2,  59.99, False),
    ("I362", "O361", "P018", 2,  34.99, False),
    ("I363", "O362", "P014", 1, 119.99, True),   # returned
    ("I364", "O363", "P019", 2,  24.99, False),

    ("I371", "O371", "P038", 2,  34.99, False),
    ("I372", "O371", "P039", 1,  39.99, False),
    ("I373", "O372", "P040", 2,  24.99, True),   # returned
    ("I374", "O373", "P012", 1,  74.99, False),

    # Fraud customers — high-value items
    ("I401", "O401", "P001", 1, 849.99, False),  # laptop
    ("I402", "O401", "P006", 1, 399.99, False),  # tablet
    ("I403", "O402", "P001", 1, 849.99, True),   # laptop returned
    ("I404", "O402", "P006", 1, 399.99, True),   # tablet returned

    ("I411", "O411", "P009", 1, 119.99, False),
    ("I412", "O411", "P010", 2,  89.99, False),
    ("I413", "O412", "P001", 1, 849.99, False),  # laptop again
    ("I414", "O413", "P007", 2, 199.99, False),  # smartwatches

    ("I421", "O421", "P001", 1, 849.99, False),  # laptop
    ("I422", "O421", "P006", 1, 399.99, False),  # tablet
    ("I423", "O422", "P001", 1, 849.99, True),   # immediate return
    ("I424", "O422", "P006", 1, 399.99, True),   # immediate return

    ("I431", "O431", "P007", 2, 199.99, False),
    ("I432", "O432", "P001", 1, 849.99, False),
    ("I433", "O432", "P006", 1, 399.99, False),
    ("I434", "O432", "P009", 2, 119.99, False),
    ("I435", "O433", "P010", 3,  89.99, False),
]

# ─── Interactions ─────────────────────────────────────────────────────────────

INTERACTIONS = [
    # High-churn customers: negative interactions, unresolved issues
    ("INT001", "C001", d(95),  "chat",       "complaint",      "negative", False, 72.5),
    ("INT002", "C001", d(78),  "email",      "order_issue",    "negative", False, 48.0),
    ("INT003", "C001", d(60),  "chat",       "return_request", "neutral",  True,  12.0),

    ("INT011", "C002", d(100), "phone",      "complaint",      "negative", False, 96.0),
    ("INT012", "C002", d(85),  "email",      "refund",         "negative", True,  24.0),
    ("INT013", "C002", d(70),  "chat",       "order_issue",    "negative", False, 52.0),

    ("INT021", "C003", d(90),  "chat",       "complaint",      "negative", True,  18.0),
    ("INT022", "C003", d(75),  "email",      "return_request", "negative", False, 60.0),
    ("INT023", "C003", d(65),  "phone",      "order_issue",    "negative", False, 84.0),

    ("INT031", "C004", d(105), "email",      "complaint",      "negative", False, 120.0),
    ("INT032", "C004", d(88),  "chat",       "refund",         "negative", True,  36.0),
    ("INT033", "C004", d(72),  "phone",      "order_issue",    "negative", False, 96.0),

    ("INT041", "C005", d(98),  "chat",       "complaint",      "negative", False, 72.0),
    ("INT042", "C005", d(82),  "email",      "order_issue",    "negative", False, 48.0),
    ("INT043", "C005", d(75),  "chat",       "return_request", "neutral",  True,  8.0),

    ("INT051", "C006", d(110), "phone",      "complaint",      "negative", False, 96.0),
    ("INT052", "C006", d(90),  "email",      "refund",         "negative", True,  24.0),
    ("INT053", "C006", d(78),  "app_review", "complaint",      "negative", False, 0.0),

    ("INT061", "C007", d(95),  "chat",       "order_issue",    "negative", False, 60.0),
    ("INT062", "C007", d(80),  "email",      "complaint",      "negative", False, 72.0),
    ("INT063", "C007", d(70),  "phone",      "return_request", "neutral",  True,  12.0),

    # Low-churn VIP customers: positive/praise interactions, all resolved
    ("INT101", "C008", d(45),  "chat",       "praise",         "positive", True,  1.0),
    ("INT102", "C008", d(15),  "email",      "praise",         "positive", True,  0.5),

    ("INT111", "C009", d(40),  "app_review", "praise",         "positive", True,  0.0),
    ("INT112", "C009", d(10),  "chat",       "praise",         "positive", True,  0.5),

    ("INT121", "C010", d(35),  "chat",       "praise",         "positive", True,  1.0),

    ("INT131", "C011", d(50),  "email",      "praise",         "positive", True,  2.0),
    ("INT132", "C011", d(20),  "chat",       "order_issue",    "positive", True,  3.0),  # resolved quickly

    ("INT141", "C012", d(25),  "app_review", "praise",         "positive", True,  0.0),

    ("INT151", "C013", d(30),  "chat",       "praise",         "positive", True,  1.0),
    ("INT152", "C013", d(8),   "email",      "praise",         "positive", True,  0.5),

    ("INT161", "C014", d(20),  "chat",       "praise",         "positive", True,  2.0),

    ("INT171", "C015", d(15),  "chat",       "praise",         "positive", True,  1.0),

    ("INT181", "C016", d(18),  "email",      "praise",         "positive", True,  0.5),

    ("INT191", "C017", d(30),  "app_review", "praise",         "positive", True,  0.0),
    ("INT192", "C017", d(5),   "chat",       "praise",         "positive", True,  0.5),

    ("INT201", "C018", d(25),  "chat",       "praise",         "positive", True,  1.0),

    ("INT211", "C019", d(20),  "email",      "praise",         "positive", True,  2.0),

    # Ambiguous customers: mixed signals
    ("INT301", "C020", d(25),  "chat",       "complaint",      "negative", False, 48.0),  # recent unresolved!
    ("INT302", "C020", d(120), "email",      "praise",         "positive", True,  1.0),
    ("INT303", "C020", d(200), "chat",       "order_issue",    "positive", True,  4.0),

    ("INT311", "C021", d(30),  "email",      "order_issue",    "neutral",  True,  12.0),
    ("INT312", "C021", d(380), "chat",       "praise",         "positive", True,  1.0),

    ("INT321", "C022", d(50),  "chat",       "order_issue",    "neutral",  True,  6.0),
    ("INT322", "C022", d(100), "email",      "complaint",      "negative", True,  24.0),  # resolved

    ("INT331", "C023", d(20),  "chat",       "order_issue",    "neutral",  True,  3.0),

    ("INT341", "C024", d(40),  "email",      "refund",         "neutral",  True,  8.0),
    ("INT342", "C024", d(95),  "phone",      "complaint",      "negative", True,  36.0),

    ("INT351", "C025", d(30),  "chat",       "order_issue",    "neutral",  True,  6.0),
    ("INT352", "C025", d(85),  "email",      "praise",         "positive", True,  0.5),

    ("INT361", "C026", d(45),  "chat",       "complaint",      "negative", False, 60.0),  # unresolved
    ("INT362", "C026", d(95),  "email",      "order_issue",    "neutral",  True,  12.0),

    ("INT371", "C027", d(38),  "email",      "return_request", "neutral",  True,  8.0),
    ("INT372", "C027", d(115), "chat",       "complaint",      "negative", True,  36.0),
]

# ─── Campaign Touchpoints ──────────────────────────────────────────────────────

CAMPAIGNS = [
    # High-churn: sent many campaigns, very low open/click/convert rates
    ("TP001", "C001", "CAM001", "Win-Back Spring",    "email_promo",       d(90),  False, False, False),
    ("TP002", "C001", "CAM002", "Loyalty Rewards Q1", "loyalty_reward",    d(75),  False, False, False),
    ("TP003", "C001", "CAM003", "Electronics Sale",   "retargeting_ad",    d(60),  False, False, False),
    ("TP004", "C001", "CAM004", "Re-engage Promo",    "email_promo",       d(45),  False, False, False),
    ("TP005", "C001", "CAM005", "Summer Preview",     "push_notification", d(30),  True,  False, False),  # one open

    ("TP011", "C002", "CAM001", "Win-Back Spring",    "email_promo",       d(88),  False, False, False),
    ("TP012", "C002", "CAM002", "Loyalty Rewards Q1", "loyalty_reward",    d(72),  False, False, False),
    ("TP013", "C002", "CAM003", "Electronics Sale",   "retargeting_ad",    d(58),  False, False, False),
    ("TP014", "C002", "CAM004", "Re-engage Promo",    "email_promo",       d(42),  False, False, False),
    ("TP015", "C002", "CAM006", "Flash Sale",         "push_notification", d(28),  False, False, False),

    ("TP021", "C003", "CAM001", "Win-Back Spring",    "email_promo",       d(86),  False, False, False),
    ("TP022", "C003", "CAM002", "Loyalty Rewards Q1", "loyalty_reward",    d(70),  False, False, False),
    ("TP023", "C003", "CAM003", "Electronics Sale",   "retargeting_ad",    d(56),  True,  False, False),  # one open
    ("TP024", "C003", "CAM004", "Re-engage Promo",    "email_promo",       d(40),  False, False, False),
    ("TP025", "C003", "CAM005", "Summer Preview",     "push_notification", d(25),  False, False, False),

    ("TP031", "C004", "CAM001", "Win-Back Spring",    "email_promo",       d(84),  False, False, False),
    ("TP032", "C004", "CAM004", "Re-engage Promo",    "email_promo",       d(55),  False, False, False),
    ("TP033", "C004", "CAM006", "Flash Sale",         "push_notification", d(35),  False, False, False),
    ("TP034", "C004", "CAM002", "Loyalty Rewards Q1", "loyalty_reward",    d(20),  False, False, False),

    ("TP041", "C005", "CAM001", "Win-Back Spring",    "email_promo",       d(82),  False, False, False),
    ("TP042", "C005", "CAM003", "Electronics Sale",   "retargeting_ad",    d(65),  False, False, False),
    ("TP043", "C005", "CAM004", "Re-engage Promo",    "email_promo",       d(48),  False, False, False),
    ("TP044", "C005", "CAM005", "Summer Preview",     "push_notification", d(30),  True,  False, False),
    ("TP045", "C005", "CAM006", "Flash Sale",         "push_notification", d(15),  False, False, False),

    ("TP051", "C006", "CAM001", "Win-Back Spring",    "email_promo",       d(80),  False, False, False),
    ("TP052", "C006", "CAM002", "Loyalty Rewards Q1", "loyalty_reward",    d(65),  False, False, False),
    ("TP053", "C006", "CAM004", "Re-engage Promo",    "email_promo",       d(50),  False, False, False),
    ("TP054", "C006", "CAM005", "Summer Preview",     "push_notification", d(35),  False, False, False),

    ("TP061", "C007", "CAM001", "Win-Back Spring",    "email_promo",       d(78),  False, False, False),
    ("TP062", "C007", "CAM003", "Electronics Sale",   "retargeting_ad",    d(62),  False, False, False),
    ("TP063", "C007", "CAM004", "Re-engage Promo",    "email_promo",       d(46),  False, False, False),
    ("TP064", "C007", "CAM006", "Flash Sale",         "push_notification", d(28),  False, False, False),

    # Low-churn VIP: high open/click/convert rates
    ("TP101", "C008", "CAM007", "VIP Exclusive",      "loyalty_reward",    d(60),  True,  True,  True),
    ("TP102", "C008", "CAM008", "New Arrivals",       "email_promo",       d(45),  True,  True,  True),
    ("TP103", "C008", "CAM009", "Restock Alert",      "push_notification", d(25),  True,  True,  False),
    ("TP104", "C008", "CAM010", "Personalized Picks", "email_promo",       d(10),  True,  True,  True),

    ("TP111", "C009", "CAM007", "VIP Exclusive",      "loyalty_reward",    d(58),  True,  True,  True),
    ("TP112", "C009", "CAM008", "New Arrivals",       "email_promo",       d(43),  True,  True,  True),
    ("TP113", "C009", "CAM009", "Restock Alert",      "push_notification", d(23),  True,  True,  True),
    ("TP114", "C009", "CAM010", "Personalized Picks", "email_promo",       d(8),   True,  True,  True),

    ("TP121", "C010", "CAM007", "VIP Exclusive",      "loyalty_reward",    d(55),  True,  True,  False),
    ("TP122", "C010", "CAM008", "New Arrivals",       "email_promo",       d(40),  True,  True,  True),
    ("TP123", "C010", "CAM009", "Restock Alert",      "push_notification", d(20),  True,  False, False),
    ("TP124", "C010", "CAM010", "Personalized Picks", "email_promo",       d(7),   True,  True,  True),

    ("TP131", "C011", "CAM007", "VIP Exclusive",      "loyalty_reward",    d(52),  True,  True,  True),
    ("TP132", "C011", "CAM008", "New Arrivals",       "email_promo",       d(38),  True,  True,  True),
    ("TP133", "C011", "CAM010", "Personalized Picks", "email_promo",       d(5),   True,  True,  True),

    ("TP141", "C012", "CAM007", "VIP Exclusive",      "loyalty_reward",    d(50),  True,  True,  True),
    ("TP142", "C012", "CAM008", "New Arrivals",       "email_promo",       d(35),  True,  True,  False),
    ("TP143", "C012", "CAM010", "Personalized Picks", "email_promo",       d(12),  True,  True,  True),

    ("TP151", "C013", "CAM007", "VIP Exclusive",      "loyalty_reward",    d(48),  True,  True,  True),
    ("TP152", "C013", "CAM010", "Personalized Picks", "email_promo",       d(10),  True,  True,  True),

    ("TP161", "C014", "CAM008", "New Arrivals",       "email_promo",       d(40),  True,  True,  False),
    ("TP162", "C014", "CAM009", "Restock Alert",      "push_notification", d(18),  True,  True,  True),

    ("TP171", "C015", "CAM008", "New Arrivals",       "email_promo",       d(35),  True,  False, False),
    ("TP172", "C015", "CAM009", "Restock Alert",      "push_notification", d(15),  True,  True,  True),

    ("TP181", "C016", "CAM008", "New Arrivals",       "email_promo",       d(30),  True,  True,  True),
    ("TP182", "C016", "CAM010", "Personalized Picks", "email_promo",       d(8),   True,  True,  False),

    ("TP191", "C017", "CAM007", "VIP Exclusive",      "loyalty_reward",    d(45),  True,  True,  True),
    ("TP192", "C017", "CAM008", "New Arrivals",       "email_promo",       d(30),  True,  True,  True),
    ("TP193", "C017", "CAM010", "Personalized Picks", "email_promo",       d(6),   True,  True,  True),

    ("TP201", "C018", "CAM008", "New Arrivals",       "email_promo",       d(28),  True,  True,  False),
    ("TP202", "C018", "CAM009", "Restock Alert",      "push_notification", d(12),  True,  True,  True),

    ("TP211", "C019", "CAM008", "New Arrivals",       "email_promo",       d(32),  True,  False, False),
    ("TP212", "C019", "CAM009", "Restock Alert",      "push_notification", d(14),  True,  True,  True),

    # Ambiguous customers: moderate engagement
    ("TP301", "C020", "CAM007", "VIP Exclusive",      "loyalty_reward",    d(90),  True,  True,  True),
    ("TP302", "C020", "CAM001", "Win-Back Spring",    "email_promo",       d(50),  True,  False, False),
    ("TP303", "C020", "CAM004", "Re-engage Promo",    "email_promo",       d(20),  False, False, False),

    ("TP311", "C021", "CAM008", "New Arrivals",       "email_promo",       d(60),  True,  True,  False),
    ("TP312", "C021", "CAM001", "Win-Back Spring",    "email_promo",       d(35),  True,  False, False),
    ("TP313", "C021", "CAM004", "Re-engage Promo",    "email_promo",       d(15),  False, False, False),

    ("TP321", "C022", "CAM004", "Re-engage Promo",    "email_promo",       d(55),  True,  False, False),
    ("TP322", "C022", "CAM001", "Win-Back Spring",    "email_promo",       d(35),  False, False, False),
    ("TP323", "C022", "CAM006", "Flash Sale",         "push_notification", d(18),  True,  True,  False),

    ("TP331", "C023", "CAM011", "Welcome Series",     "email_promo",       d(60),  True,  True,  True),
    ("TP332", "C023", "CAM012", "New Customer Offer", "email_promo",       d(40),  True,  False, False),
    ("TP333", "C023", "CAM009", "Restock Alert",      "push_notification", d(18),  True,  True,  False),

    ("TP341", "C024", "CAM004", "Re-engage Promo",    "email_promo",       d(50),  True,  False, False),
    ("TP342", "C024", "CAM001", "Win-Back Spring",    "email_promo",       d(30),  True,  True,  False),
    ("TP343", "C024", "CAM006", "Flash Sale",         "push_notification", d(12),  False, False, False),

    ("TP351", "C025", "CAM008", "New Arrivals",       "email_promo",       d(55),  True,  True,  True),
    ("TP352", "C025", "CAM004", "Re-engage Promo",    "email_promo",       d(30),  True,  False, False),
    ("TP353", "C025", "CAM006", "Flash Sale",         "push_notification", d(12),  False, False, False),

    ("TP361", "C026", "CAM004", "Re-engage Promo",    "email_promo",       d(50),  True,  False, False),
    ("TP362", "C026", "CAM001", "Win-Back Spring",    "email_promo",       d(32),  False, False, False),
    ("TP363", "C026", "CAM006", "Flash Sale",         "push_notification", d(15),  True,  False, False),

    ("TP371", "C027", "CAM004", "Re-engage Promo",    "email_promo",       d(55),  True,  True,  False),
    ("TP372", "C027", "CAM001", "Win-Back Spring",    "email_promo",       d(35),  True,  False, False),
    ("TP373", "C027", "CAM006", "Flash Sale",         "push_notification", d(18),  False, False, False),

    # Fraud customers: zero campaign engagement (paid acquisition, no organic interest)
    ("TP401", "C028", "CAM013", "New Customer Retarget", "retargeting_ad", d(11), False, False, False),
    ("TP411", "C029", "CAM013", "New Customer Retarget", "retargeting_ad", d(7),  False, False, False),
    ("TP421", "C030", "CAM013", "New Customer Retarget", "retargeting_ad", d(4),  False, False, False),
    ("TP431", "C031", "CAM013", "New Customer Retarget", "retargeting_ad", d(9),  False, False, False),
]


def seed(conn: sqlite3.Connection) -> None:
    """Insert all seed data into the database."""
    schema_sql = SCHEMA_PATH.read_text()
    conn.executescript(schema_sql)

    # Create and seed admin table
    conn.execute("CREATE TABLE admin (user_id TEXT PRIMARY KEY, password TEXT)")
    conn.execute("INSERT INTO admin (user_id, password) VALUES (?, ?)", ("1028@admin", "1028@admin"))

    conn.executemany(
        "INSERT INTO customers VALUES (?,?,?,?,?,?,?,?,?)", CUSTOMERS
    )
    conn.executemany(
        "INSERT INTO products VALUES (?,?,?,?,?,?,?,?,?)", PRODUCTS
    )
    conn.executemany(
        "INSERT INTO orders VALUES (?,?,?,?,?,?,?,?,?)", ORDERS
    )
    conn.executemany(
        "INSERT INTO order_items VALUES (?,?,?,?,?,?)", ORDER_ITEMS
    )
    conn.executemany(
        "INSERT INTO interactions VALUES (?,?,?,?,?,?,?,?)", INTERACTIONS
    )
    conn.executemany(
        "INSERT INTO campaign_touchpoints VALUES (?,?,?,?,?,?,?,?,?)", CAMPAIGNS
    )
    conn.commit()
    print(f"Seeded database at {DB_PATH}")
    print(f"  {len(CUSTOMERS)} customers, {len(PRODUCTS)} products, {len(ORDERS)} orders")
    print(f"  {len(ORDER_ITEMS)} order items, {len(INTERACTIONS)} interactions, {len(CAMPAIGNS)} campaigns")


def main() -> None:
    reseed = "--reseed" in sys.argv

    if DB_PATH.exists() and not reseed:
        print(f"Database already exists at {DB_PATH}. Use --reseed to regenerate.")
        return

    if DB_PATH.exists():
        DB_PATH.unlink()
        print(f"Removed existing database at {DB_PATH}")

    # Also remove graph so it gets rebuilt on next startup
    if GRAPH_PATH.exists():
        GRAPH_PATH.unlink()
        print(f"Removed cached graph at {GRAPH_PATH}")

    conn = sqlite3.connect(str(DB_PATH))
    conn.row_factory = sqlite3.Row
    try:
        seed(conn)
    finally:
        conn.close()


if __name__ == "__main__":
    main()
