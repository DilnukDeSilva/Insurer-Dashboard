# Insurer Dashboard

Monorepo for property capture and 3D reconstruction for insurers.

## Structure

| Folder     | Description |
| ---------- | ----------- |
| `frontend` | React + Vite + TypeScript UI |
| `backend`  | Python FastAPI — Zero-DCE → OpenMVG → OpenMVS pipeline |

## Pipeline

1. **Zero-DCE** — enhance low-light photos before reconstruction  
2. **OpenMVG** — structure from motion, sparse point cloud and camera poses  
3. **OpenMVS** — dense point cloud and mesh  

Configure tool paths in `backend/.env` (see `backend/.env.example`).

## Getting started

### Backend (FastAPI)

```bash
cd backend
python3 -m venv .venv
source .venv/bin/activate   # Windows: .venv\Scripts\activate
pip install -r requirements.txt
cp .env.example .env
uvicorn app.main:app --reload --host 0.0.0.0 --port 8000
```

- API: [http://localhost:8000](http://localhost:8000)  
- Docs: [http://localhost:8000/docs](http://localhost:8000/docs)  
- Health: `GET /api/health` — shows whether each tool is configured  

### Frontend

```bash
cd frontend
npm install
npm run dev
```

Runs at [http://localhost:5173](http://localhost:5173) and proxies `/api` to the backend.

## External tools

Build and install separately, then point `.env` at the binaries:

- [OpenMVG](https://github.com/openMVG/openMVG) — `OPENMVG_BIN_DIR`  
- [OpenMVS](https://github.com/cdcseacave/openMVS) — `OPENMVS_BIN_DIR`  
- [Zero-DCE](https://github.com/Li-Chongyi/Zero-DCE) — `ZERO_DCE_REPO_DIR`, `ZERO_DCE_WEIGHTS`  

Pipeline service stubs live under `backend/app/services/`. Implement CLI / inference calls there as you wire up each stage.

## API (pipeline)

| Method | Path | Description |
| ------ | ---- | ----------- |
| `GET` | `/api/health` | API and tool configuration status |
| `GET` | `/api/pipeline/stages` | List pipeline stages |
| `POST` | `/api/pipeline/jobs` | Create a job workspace |
| `POST` | `/api/pipeline/jobs/{id}/run` | Run Zero-DCE → OpenMVG → OpenMVS |
