# Insurer Dashboard

Monorepo for the Insurer Dashboard application.

## Structure

| Folder     | Description                          |
| ---------- | ------------------------------------ |
| `frontend` | React + Vite + TypeScript UI         |
| `backend`  | Express + TypeScript REST API        |

## Getting started

### Frontend

```bash
cd frontend
npm install
npm run dev
```

Runs at [http://localhost:5173](http://localhost:5173).

### Backend

```bash
cd backend
cp .env.example .env
npm install
npm run dev
```

Runs at [http://localhost:3001](http://localhost:3001).

## Scripts

- **Frontend:** `dev`, `build`, `preview`, `lint`
- **Backend:** `dev`, `build`, `start`
