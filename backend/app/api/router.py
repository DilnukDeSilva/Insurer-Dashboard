from fastapi import APIRouter

from app.api.routes import health, pipeline
from app.api.routes.claims import router as claims_router

api_router = APIRouter()
api_router.include_router(health.router, tags=["health"])
api_router.include_router(pipeline.router)
api_router.include_router(claims_router)
