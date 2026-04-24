# CLAUDE.md

This file provides guidance to Claude Code (claude.ai/code) when working with code in this repository.

## Commands

### Backend (run from `backend/`)
```bash
# Install dependencies
pip install -r requirements.txt

# Start server (auto-seeds DB and loads/builds graph)
uvicorn main:app --reload

# Force graph rebuild from scratch
uvicorn main:app --reload -- --rebuild-graph

# Reseed the database (also deletes cached graph)
python data/seed.py --reseed

# Run a single module directly
python -m data.seed --reseed
```

### Frontend (run from `frontend/`)
```bash
npm install
npm run dev      # dev server on :5173
npm run build    # production build
```

## Architecture

### Request flow
1. `POST /api/chat` receives `{message, history}`
2. `llm/claude.py::generate_pql()` → Claude converts NL → PQL string
3. `pql/parser.py::parse_pql()` → structured plan dict (mode: factual | predictive)
4. `pql/executor.py::execute()` → routes to graph lookup or prediction pipeline
5. Factual: iterate graph nodes, apply WHERE filters, sort, limit
6. Predictive: `graph/traversal.py` → `prediction/engine.py` → scored + ranked rows
7. `llm/claude.py::summarize_results()` → Claude writes plain English summary
8. Response includes: `pql_query`, `query_type`, `results`, `traversal_steps`, `summary`, `columns`

### Graph persistence
- Built once from SQLite → saved to `data/graph.graphml`
- Loaded from file on subsequent startups (fast path)
- GraphML constraint: all node/edge attributes must be `str | int | float | bool`
- `None` values stored as `""`, booleans stored as `"True"`/`"False"` strings
- `graph/builder.py::cast_graph_attributes()` normalizes types after loading

### Prediction pipeline (the key differentiator)
The 3-hop traversal in `graph/traversal.py::collect_churn_signals()`:
- Hop 1: customer → orders (recency, return rate, order value)
- Hop 2: orders → products (category diversity)
- Hop 3: products → **peer customers** (who bought same products) → their inactivity = peer_churn_rate

This peer signal is what separates graph-native prediction from SQL-based churn models. It's weighted at 0.12 in `prediction/engine.py::score_churn()`.

### Seed data profiles
- **C001–C007** (high churn risk): last order 72–130 days ago, return rate >35%, 2+ negative interactions, campaign open rate <20%, shared electronics products
- **C008–C019** (low churn risk): last order 2–14 days ago, VIP segment, praise-only interactions, open rate >60%, shared home/beauty products
- **C020–C027** (ambiguous): mixed signals, last order 22–45 days ago
- **C028–C031** (fraud signal): new accounts (<14 days), large orders (>$400), rapid velocity, zero campaign engagement

### PQL syntax reference
```
# Factual
MATCH <entity>
WHERE <field> = 'value' [AND ...]
RETURN <fields>
ORDER BY <field> DESC
LIMIT <n>

# Predictive
PREDICT <churn_probability|purchase_likelihood|fraud_risk|demand_forecast>
FOR EACH <entity>
[WHERE ...]
USING <tables>
HORIZON <n> days
RETURN <fields>
ORDER BY score DESC
LIMIT <n>
```

## Key Files

| File | Purpose |
|------|---------|
| `backend/graph/traversal.py` | Multi-hop traversal — the architectural core |
| `backend/prediction/engine.py` | Weighted scoring functions for all prediction types |
| `backend/pql/parser.py` | PQL string → structured plan dict |
| `backend/pql/executor.py` | Routes plan to graph lookup or prediction pipeline |
| `backend/graph/builder.py` | Graph construction + GraphML persistence |
| `backend/data/seed.py` | All seed data — customer profiles, orders, interactions, campaigns |
| `backend/llm/claude.py` | Two Claude API calls: NL→PQL and results→summary |
| `frontend/src/hooks/useChat.js` | Chat state + API communication |
| `frontend/src/components/TraversalSteps.jsx` | Renders the multi-hop traversal visualization |

## Environment

```
# backend/.env
ANTHROPIC_API_KEY=sk-ant-...
```

The server fails fast at startup with a clear error if `ANTHROPIC_API_KEY` is not set.
