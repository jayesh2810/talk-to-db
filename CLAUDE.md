# CLAUDE.md

This file provides guidance to Claude Code (claude.ai/code) when working with code in this repository.

## Commands

### Backend (run from `backend/`)
```bash
# Install dependencies
pip install -r requirements.txt

# Start server (downloads data from S3, builds KumoRFM graph on first run)
uvicorn main:app --reload
```

### Frontend (run from `frontend/`)
```bash
npm install
npm run dev # dev server on :5173
```

## Architecture

### Request flow
1. `POST /api/chat` receives `{message, history}`
2. `llm/claude.py::generate_pql()` → Claude converts NL → PQL string
3. `pql/parser.py::parse_pql()` → structured plan dict (mode: factual | predictive)
4. `kumo_rfm/executor.py::execute()` → routes to pandas lookup or KumoRFM prediction
5. Factual: pandas DataFrame filter/sort/limit on cached e-commerce data
6. Predictive: `kumo_rfm/client.py::predict()` → KumoRFM foundation model
7. `llm/claude.py::summarize_results()` → Claude writes plain English summary
8. Response includes: `pql_query`, `query_type`, `results`, `summary`, `columns`

### KumoRFM integration
- Data loaded from `s3://kumo-sdk-public/rfm-datasets/online-shopping` (users, items, orders)
- Graph auto-inferred via `rfm.LocalGraph.from_data()` (PK/FK relationship detection)
- Model initialized via `rfm.KumoRFM(graph)` — no training required
- Predictions via `model.predict(pql_query)` — uses the pre-trained relational foundation model

### PQL syntax reference
```
# Factual (data lookups)
MATCH <table>
WHERE <field> = 'value' [AND ...]
RETURN <fields>
ORDER BY <field> DESC
LIMIT <n>

# Predictive (KumoRFM PQL)
PREDICT <target_expression> FOR <table>.<primary_key>=<value>
PREDICT <target_expression> FOR <table>.<primary_key> IN (<id1>, <id2>, ...)

# Target expressions:
COUNT(orders.*, 0, 90, days)=0          — churn prediction
SUM(orders.price, 0, 30, days)          — revenue forecast
LIST_DISTINCT(orders.item_id, 0, 30, days) RANK TOP 10  — recommendations
users.age                                — missing value imputation
```

## Key Files

| File | Purpose |
|------|---------|
| `backend/kumo_rfm/client.py` | KumoRFM SDK wrapper — data loading, graph creation, model init |
| `backend/kumo_rfm/executor.py` | Routes PQL to pandas (factual) or KumoRFM (predictive) |
| `backend/pql/parser.py` | PQL string → structured plan dict |
| `backend/llm/claude.py` | Two Claude API calls: NL→PQL and results→summary |
| `backend/llm/prompts.py` | System prompts for Claude with KumoRFM PQL syntax |
| `backend/main.py` | FastAPI app with /api/chat endpoint |
| `frontend/src/hooks/useChat.js` | Chat state + API communication |
| `frontend/src/components/ExampleQuestions.jsx` | Example KumoRFM queries |

## Environment

```
# backend/.env
ANTHROPIC_API_KEY=sk-ant-...
KUMO_API_KEY=...           # Get free at https://kumorfm.ai
```

The server fails fast at startup if either API key is missing.
