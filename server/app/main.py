from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from server.app.config import settings
from server.app.routers import auth
from server.app.utils.responses import success_response

app = FastAPI(
    title="MAPLE A1 Code Evaluator",
    description="Automated code evaluation system for Marist College",
    version="1.0.0",
    docs_url="/api/v1/code-eval/docs",
    openapi_url="/api/v1/code-eval/openapi.json"
)

# Configure CORS
app.add_middleware(
    CORSMiddleware,
    allow_origins=settings.cors_origins_list,
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# Include routers
app.include_router(auth.router, prefix="/api/v1/code-eval")

@app.get("/api/v1/code-eval/health")
async def health_check():
    return success_response({"status": "ok", "environment": settings.APP_ENV})
