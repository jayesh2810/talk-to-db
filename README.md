# Relational Predictive Analytics Demo

This project demonstrates a relational predictive analytics pipeline end-to-end. It allows users to connect a relational database, ask predictive questions in natural language, and get answers without building complex ML pipelines.

## Architecture

```
Natural language question
        │
        ▼
  ┌───────────┐
  │  Claude   │  (NL → PQL generation)
  └───────────┘
        │
        ▼
  ┌─────────────────────────────────────────┐
  │           PQL Parser                    │
  │   MATCH (factual) │ PREDICT (predictive)│
  └─────────────────────────────────────────┘
        │                    │
        ▼                    ▼
  Graph Node         Multi-Hop Graph
  Lookup             Traversal
  (filter/sort)      │
                     ▼
                Signal Collection
                (recency, sentiment,
                 campaign engagement,
                 peer customer activity)
                     │
                     ▼
                Weighted Scoring
                Engine
                     │
                     ▼
   ┌──────────────────────────────┐
   │  Results + Traversal Steps  │
   └──────────────────────────────┘
        │
        ▼
  ┌───────────┐
  │  Claude   │  (Results → Plain English Summary)
  └───────────┘
        │
        ▼
  Chat UI: Summary + PQL Block + Traversal Steps + Results Table
```

## The Graph Layer — Why It Matters

Traditional text-to-SQL chatbots treat a database as a collection of flat tables joined by IDs. This project treats the database as a **graph of interrelated entities**, where each foreign key relationship becomes a typed edge.

**Node types:** `customer`, `product`, `order`, `interaction`, `campaign`

**Edge types:** `placed`, `contains`, `bought_by`, `had_interaction`, `received_campaign`

The critical architectural insight is the **multi-hop traversal**:

```
customer → orders → products → OTHER customers (peer customers)
```

If a customer bought the same products as several other customers who are now going inactive, that's a meaningful churn signal. Flat SQL joins cannot capture this because the signal lives **across three hops** in the entity graph — not within any single table.

## Prescriptive Intelligence

Beyond just predicting *who* is at risk, the system implements **Prescriptive Analysis**. By identifying "Positive Outliers"—customers who faced similar risk signals but managed to stay active—the agent autonomously extracts a "Recovery Path."

It analyzes the recent events (campaigns, products, or support resolutions) of these survivors to suggest a specific, data-backed action to save at-risk customers, including a success probability based on historical recovery rates.

## Setup

### 1. Prerequisites

- Python 3.11+
- Node.js 18+
- An `ANTHROPIC_API_KEY`

### 2. Backend

```bash
cd backend

# Create and activate a virtual environment
python -m venv venv
source venv/bin/activate  # Windows: venv\Scripts\activate

# Install dependencies
pip install -r requirements.txt

# Copy the env template and add your key
cp .env.example .env
# Edit .env: ANTHROPIC_API_KEY=sk-ant-...

# Start the server (seeds DB and builds graph automatically on first run)
uvicorn main:app --reload
```

The backend starts on `http://localhost:8000`.

**Graph persistence:** The NetworkX graph is built once from SQLite and cached to `data/graph.graphml`. Subsequent restarts load from the cache (fast). To force a rebuild:

```bash
uvicorn main:app --reload -- --rebuild-graph
```

**Reseed the database:**

```bash
python data/seed.py --reseed
# This deletes both ecommerce.db and graph.graphml, so the next startup rebuilds both
```

### 3. Frontend

```bash
cd frontend
npm install
npm run dev
```

The frontend starts on `http://localhost:5173`.

## Example Queries

### Factual (MATCH)

**"Show me our top 10 customers by lifetime value"**
```
MATCH customer
RETURN customer.name, customer.segment, customer.lifetime_value, customer.city
ORDER BY customer.lifetime_value DESC
LIMIT 10
```
→ Returns a ranked table of your most valuable customers.

**"Which electronics products have a rating above 4.5?"**
```
MATCH product
WHERE product.category = 'electronics'
AND product.avg_rating >= 4.5
RETURN product.name, product.price, product.avg_rating
ORDER BY product.avg_rating DESC
```

**"How many orders were placed last month?"**
```
MATCH order
WHERE order.order_date >= '2025-03-01'
AND order.order_date <= '2025-03-31'
RETURN order.order_id, order.customer_id, order.total_amount, order.status
```

### Predictive (PREDICT)

**"Which customers are most likely to churn?"**
```
PREDICT churn_probability
FOR EACH customer
WHERE customer.segment != 'new'
USING orders, interactions, campaign_touchpoints
HORIZON 90 days
RETURN customer.name, score, confidence, top_factors
ORDER BY score DESC
LIMIT 20
```
→ Traverses 3 hops: customer→orders→products→peer customers. Peer inactivity rate is the multi-hop signal that differentiates this from SQL-based churn models. High-risk customers score 0.75+.

**"Which recent orders have the highest fraud risk?"**
```
PREDICT fraud_risk
FOR EACH order
WHERE order.order_date >= '2026-04-10'
USING customers, order_items
RETURN order.order_id, score, confidence, top_factors
ORDER BY score DESC
LIMIT 10
```
→ Scores based on: new account age, order value, rapid order velocity (3-day window), and immediate returns.

**"Forecast demand by product category for the next quarter"**
```
PREDICT demand_forecast
FOR EACH product.category
USING orders, order_items
HORIZON 90 days
RETURN category, predicted_units, predicted_revenue, confidence
```
→ Uses trend extrapolation from 30-day vs 60-day sales windows.


## Setup

### 1. Prerequisites

- Python 3.11+
- Node.js 18+
- An `ANTHROPIC_API_KEY`

### 2. Backend

```bash
cd backend

# Create and activate a virtual environment
python -m venv venv
source venv/bin/activate  # Windows: venv\Scripts\activate

# Install dependencies
pip install -r requirements.txt

# Copy the env template and add your key
cp .env.example .env
# Edit .env: ANTHROPIC_API_KEY=sk-ant-...

# Start the server (seeds DB and builds graph automatically on first run)
uvicorn main:app --reload
```

The backend starts on `http://localhost:8000`.

**Graph persistence:** The NetworkX graph is built once from SQLite and cached to `data/graph.graphml`. Subsequent restarts load from the cache (fast). To force a rebuild:

```bash
uvicorn main:app --reload -- --rebuild-graph
```

**Reseed the database:**

```bash
python data/seed.py --reseed
# This deletes both ecommerce.db and graph.graphml, so the next startup rebuilds both
```

### 3. Frontend

```bash
cd frontend
npm install
npm run dev
```

The frontend starts on `http://localhost:5173`.

## Example Queries

### Factual (MATCH)

**"Show me our top 10 customers by lifetime value"**
```
MATCH customer
RETURN customer.name, customer.segment, customer.lifetime_value, customer.city
ORDER BY customer.lifetime_value DESC
LIMIT 10
```
→ Returns a ranked table of your most valuable customers.

**"Which electronics products have a rating above 4.5?"**
```
MATCH product
WHERE product.category = 'electronics'
AND product.avg_rating >= 4.5
RETURN product.name, product.price, product.avg_rating
ORDER BY product.avg_rating DESC
```

**"How many orders were placed last month?"**
```
MATCH order
WHERE order.order_date >= '2025-03-01'
AND order.order_date <= '2025-03-31'
RETURN order.order_id, order.customer_id, order.total_amount, order.status
```

### Predictive (PREDICT)

**"Which customers are most likely to churn?"**
```
PREDICT churn_probability
FOR EACH customer
WHERE customer.segment != 'new'
USING orders, interactions, campaign_touchpoints
HORIZON 90 days
RETURN customer.name, score, confidence, top_factors
ORDER BY score DESC
LIMIT 20
```
→ Traverses 3 hops: customer→orders→products→peer customers. Peer inactivity rate is the multi-hop signal that differentiates this from SQL-based churn models. High-risk customers score 0.75+.

**"Which recent orders have the highest fraud risk?"**
```
PREDICT fraud_risk
FOR EACH order
WHERE order.order_date >= '2026-04-10'
USING customers, order_items
RETURN order.order_id, score, confidence, top_factors
ORDER BY score DESC
LIMIT 10
```
→ Scores based on: new account age, order value, rapid order velocity (3-day window), and immediate returns.

**"Forecast demand by product category for the next quarter"**
```
PREDICT demand_forecast
FOR EACH product.category
USING orders, order_items
HORIZON 90 days
RETURN category, predicted_units, predicted_revenue, confidence
```
→ Uses trend extrapolation from 30-day vs 60-day sales windows.
