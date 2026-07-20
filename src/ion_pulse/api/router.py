from fastapi import APIRouter

from ion_pulse.api.routes import health

api_router = APIRouter()
api_router.include_router(health.router, tags=["system"])
