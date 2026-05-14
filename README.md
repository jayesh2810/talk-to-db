# Relational Predictive Analytics Demo

This project demonstrates a relational predictive analytics app. Users can ask factual and predictive questions in natural language, review generated PQL, inspect tabular results, and run a human-in-the-loop goal agent.

## Architecture

```text
Natural language question
        |
        v
Claude (NL -> PQL / agent planning)
        |
        v
PQL Parser
  |-- MATCH   -> cached users/items/orders tables
  |-- PREDICT -> relational prediction engine
        |
        v
Results + summary + optional goal-agent workflow
```

The app uses the sample online-shopping relational dataset: `users`, `items`, and `orders`. Cached Parquet files and the pickled `LocalGraph` live under `backend/data/`.

## Goal Agent

Use `/goal ...` in chat to start a human-in-the-loop workflow.

Example:

```text
/goal reduce churn by 2% in 60 days
```

Flow:

1. Claude receives the business goal plus sanitized schema/aggregate context.
2. Claude drafts a Kumo-style plan using only available data and allowed tools.
3. The user approves or revises the plan.
4. The backend executes approved tools: `schema_inspect`, `predict_execute`, `match_execute`, and `result_summarize`.
5. Claude proposes final actions from privacy-safe execution results.
6. The user approves final actions.

The agent does not send raw PII rows to the LLM. It uses schema metadata, aggregate metrics, risk buckets, and masked samples.

## Setup

### Prerequisites

- Python 3.11+
- Node.js 18+
- `ANTHROPIC_API_KEY`
- `KUMO_API_KEY`

### Backend

```bash
cd backend
python -m venv venv
source venv/bin/activate  # Windows: venv\Scripts\activate
pip install -r requirements.txt
cp .env.example .env
uvicorn main:app --reload
```

The backend starts on `http://localhost:8000`.

Optional login variables:

```text
BASIC_AUTH_USER=1028@admin
BASIC_AUTH_PASSWORD=1028@admin
```

Force rebuild of the cached graph:

```bash
uvicorn main:app --reload -- --rebuild-rfm-graph
```

### Frontend

```bash
cd frontend
npm install
npm run dev
```

The frontend starts on `http://localhost:5173`.

## Example Queries

### Factual

```text
MATCH users
WHERE active = true AND age < 40
RETURN user_id, age
LIMIT 20
```

```text
MATCH items
WHERE category = 'Trousers'
RETURN item_id, item_name, color
LIMIT 15
```

### Predictive

```text
PREDICT churn_probability
FOR EACH customer
USING orders
HORIZON 90 days
RETURN score
ORDER BY score DESC
LIMIT 20
```

```text
PREDICT demand_forecast
FOR EACH product
USING orders, items
HORIZON 90 days
RETURN category, score, predicted_revenue
ORDER BY score DESC
LIMIT 15
```

## Notes

- `fraud_risk` is not supported on the sample online-shopping dataset.
- If old local demo files exist (`ecommerce.db`, `auth.db`, `graph.graphml`, `kumo_online_shopping.db`), the app no longer reads them.
