# Relational Predictive Analytics Demo

This project demonstrates a relational predictive analytics pipeline end-to-end. It allows users to connect a relational database, ask predictive questions in natural language, and get answers without building complex ML pipelines.

## Architecture

```
Natural language question
        │
        ▼
  ┌───────────┐
  │  Claude   │  NL → PQL
  └───────────┘
        │
        ▼
  ┌─────────────────────────────────────────┐
  │  PQL Parser (MATCH factual | PREDICT)   │
  └─────────────────────────────────────────┘
        │
        ▼
  ┌─────────────────────────────────────────┐
  │  Kumo online-shopping dataset           │
  │  Parquet users / items / orders       │
  │  → LocalGraph / KumoRFM               │
  └─────────────────────────────────────────┘
        │
        ├── MATCH → pandas filter/sort on tables
        └── PREDICT → KumoRFM model.predict(...)
        │
        ▼
  ┌───────────┐
  │  Claude   │  Results → summary
  └───────────┘
```

Relational structure (**users** buy **items** via **orders**) is the graph KumoRFM reasons over. Chat and graph endpoints use only that cached quickstart data; login is HTTP Basic via **`BASIC_AUTH_*`** in `.env` (no database).

## Prescriptive-style responses

Predictive rows may include **`recommended_action`** and **`success_probability`** templates produced by the KumoRFM integration layer (`rfm/predict.py`), framed for analysts in the summarization prompt—not from a separate handcrafted scoring engine.

## Setup

### 1. Prerequisites

- Python 3.11+
- Node.js 18+
- `ANTHROPIC_API_KEY` and `KUMO_API_KEY` (see `backend/.env.example`)

### 2. Backend

```bash
cd backend

# Create and activate a virtual environment
python -m venv venv
source venv/bin/activate  # Windows: venv\Scripts\activate

# Install dependencies
pip install -r requirements.txt

# Copy the env template and add your keys
cp .env.example .env
# Edit .env: ANTHROPIC_API_KEY=..., KUMO_API_KEY=...

# Start the server (downloads/caches Kumo quickstart Parquet on first run if needed)
uvicorn main:app --reload
```

The backend starts on `http://localhost:8000`.

**Login:** set `BASIC_AUTH_USER` and `BASIC_AUTH_PASSWORD` in `backend/.env` if you do not want the defaults (`1028@admin` / `1028@admin`). No SQLite file is used.

**KumoRFM cache:** Parquet + pickled `LocalGraph` live under `data/kumo_rfm_cache/`. Force rebuild of the pickle:

```bash
uvicorn main:app --reload -- --rebuild-rfm-graph
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

**"Show active users under 40"**
```
MATCH users
WHERE active = true AND age < 40
RETURN user_id, age
LIMIT 20
```

**"Items in category Trousers"**
```
MATCH items
WHERE category = 'Trousers'
RETURN item_id, item_name, color
LIMIT 15
```

**"Recent high-value orders"**
```
MATCH orders
WHERE date >= '2023-01-01'
RETURN order_id, user_id, price
ORDER BY price DESC
LIMIT 10
```

### Predictive (PREDICT)

**"Which users are most likely to churn?"**
```
PREDICT churn_probability
FOR EACH customer
USING orders
HORIZON 90 days
RETURN score
ORDER BY score DESC
LIMIT 20
```
→ **KumoRFM** on online-shopping **`users`** / **`orders`**.

**"Forecast demand by item"**
```
PREDICT demand_forecast
FOR EACH product
USING orders, items
HORIZON 90 days
RETURN category, score, predicted_revenue
ORDER BY score DESC
LIMIT 15
```
→ Item-level demand-style predictions (`backend/rfm/predict.py`). **`fraud_risk`** is not supported on this dataset.

## Data sources

All analytics come from the **Kumo RFM quickstart** online-shopping dataset: Parquet files under `backend/data/kumo_rfm_cache/` (same source as [Kumo’s quickstart](https://kumo.ai/docs/quick-start/rfm/)), plus a pickled `LocalGraph` for fast restarts.

Set **`ANTHROPIC_API_KEY`**, **`KUMO_API_KEY`**, and optionally **`BASIC_AUTH_*`**, in `backend/.env`.

If you still have old local files from earlier demos (`ecommerce.db`, `auth.db`, `graph.graphml`, `kumo_online_shopping.db`), you can delete them — the app no longer reads them.
