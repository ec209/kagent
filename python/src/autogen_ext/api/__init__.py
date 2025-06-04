"""API endpoints for autogen-ext."""

from fastapi import FastAPI

from autogen_ext.api.models import router as models_router

app = FastAPI(title="autogen-ext API")

# Register routers
app.include_router(models_router, prefix="/api") 