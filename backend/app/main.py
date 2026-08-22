import logging
from contextlib import asynccontextmanager

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware

from app.api.router import api_router
from app.config import settings

logging.basicConfig(level=logging.WARNING)
logging.getLogger("app").setLevel(logging.DEBUG)


@asynccontextmanager
async def lifespan(_app: FastAPI):
    settings.data_dir.mkdir(parents=True, exist_ok=True)
    settings.uploads_dir.mkdir(parents=True, exist_ok=True)
    settings.jobs_dir.mkdir(parents=True, exist_ok=True)
    yield
    from app.db.mongo import close_client
    await close_client()


app = FastAPI(
    title="Insurer Dashboard API",
    description="Photogrammetry API: Zero-DCE → OpenMVG → OpenMVS",
    version="0.1.0",
    lifespan=lifespan,
)

app.add_middleware(
    CORSMiddleware,
    allow_origins=["http://localhost:5173"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

app.include_router(api_router, prefix="/api")


@app.get("/")
def root() -> dict:
    return {"docs": "/docs", "health": "/api/health"}
