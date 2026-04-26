# Running the app

Run the **backend** and **frontend** in two terminals. The Vite dev server proxies `/api` to the backend on port 8000.

## Backend (FastAPI)

From the repository root:

```bash
cd backend
pip install -r requirements.txt   # first time only
uvicorn main:app --reload
```

- **API base:** [http://localhost:8000](http://localhost:8000)
- **Interactive docs (Swagger):** [http://localhost:8000/docs](http://localhost:8000/docs)
- **Health check:** [http://localhost:8000/api/health](http://localhost:8000/api/health)

Ensure `backend/.env` exists with `ANTHROPIC_API_KEY` set (see backend startup in `main.py`).

## Frontend (Vite + React)

From the repository root:

```bash
cd frontend
npm install   # first time only
npm run dev
```

- **App:** [http://localhost:5173](http://localhost:5173)

API calls from the browser go to `/api/...` on the same origin and are proxied to `http://localhost:8000`.
