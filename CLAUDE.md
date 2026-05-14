# CLAUDE.md

This file provides guidance to Claude Code (claude.ai/code) when working with code in this repository.

## Commands

### Backend (run from `backend/`)
```bash
pip install -r requirements.txt

uvicorn main:app --reload

# Rebuild pickled LocalGraph from cached parquet
uvicorn main:app --reload -- --rebuild-rfm-graph
```

### Frontend (run from `frontend/`)
```bash
npm install
npm run dev # dev server on :5173
```

## Architecture

### Request flow
1. `POST /api/chat` receives `{message, history}`
2. `llm/claude.py::generate_pql()` -> Claude converts NL to a PQL string
3. `pql/parser.py::parse_pql()` -> structured plan dict (mode: factual | predictive)
4. `pql/executor.py::execute(pql_query, RFM_BUNDLE)` -> routes parsed plan to `rfm/` modules
5. **Factual** (`MATCH`): `rfm/factual.py::run_factual()` - pandas filters on cached **users / items / orders** parquet (aligned with `LocalGraph`)
6. **Predictive** (`PREDICT`): `rfm/predict.py::run_predictive()` - batch inference on the same graph
7. `llm/claude.py::summarize_results()` -> summary text

### Auth & schema
- **HTTP Basic** credentials come from **`BASIC_AUTH_USER`** / **`BASIC_AUTH_PASSWORD`** in `.env` (defaults: `1028@admin` / `1028@admin`). No SQLite.
- **`GET /api/schema`**: columns from loaded Parquet tables.

## PQL syntax reference
```
# Factual (data lookups)
MATCH <table>
WHERE <field> = 'value' [AND ...]
RETURN <fields>
ORDER BY <field> DESC
LIMIT <n>

# Predictive
PREDICT <churn_probability|purchase_likelihood|demand_forecast>
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
| `backend/rfm/cache.py` | Download/cache Kumo Parquet, pickle `LocalGraph`, load `RFMBundle` |
| `backend/rfm/predict.py` | Predictive plans -> Kumo PQL + `model.predict()` |
| `backend/rfm/factual.py` | Factual `MATCH` on parquet tables |
| `backend/rfm/user_profile.py` | `GET /api/user/{user_id}` - orders + churn score |
| `backend/rfm/viz.py` | Stats + sample graph payload for the UI |
| `backend/pql/parser.py` | PQL string -> structured plan dict |
| `backend/pql/executor.py` | Routes factual vs predictive |
| `backend/llm/claude.py` | Claude: NL-to-PQL and results-to-summary |
| `frontend/src/hooks/useChat.js` | Chat state + API communication |
| `frontend/src/components/CustomerDrawer.jsx` | User deep-dive panel with churn gauge |
| `frontend/src/components/ResultTable.jsx` | Results table with CSV export |

## Environment

```
# backend/.env
ANTHROPIC_API_KEY=sk-ant-...
KUMO_API_KEY=...
# optional - defaults shown
# BASIC_AUTH_USER=1028@admin
# BASIC_AUTH_PASSWORD=1028@admin
```

The server fails fast at startup if **`ANTHROPIC_API_KEY`** or **`KUMO_API_KEY`** is missing.
