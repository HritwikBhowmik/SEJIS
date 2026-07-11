
from fastapi import FastAPI
from fastapi.staticfiles import StaticFiles
from fastapi.middleware.cors import CORSMiddleware
from typing import AsyncIterator
from contextlib import asynccontextmanager

from app.api.deps import redis_pool
from app.api.v1 import resume, interview, auth, candidate_evaluation, dashboard, download_report
from app.models.model import Base
from app.core.db import async_engine

# --- LIFESPAN (Startup / Shutdown) ---
@asynccontextmanager
async def lifespan(app: FastAPI) -> AsyncIterator[None]:

    async with async_engine.begin() as conn:
        # Scans your models.py files and safely creates tables if they don't exist
        await conn.run_sync(Base.metadata.create_all)
    
    yield  # The application runs while paused here
    
    # Gracefully shut down the pool when closing the application
    await redis_pool.disconnect()
    print("Redis connection pool closed.")

    await async_engine.dispose()



app = FastAPI(
    title="LLM Based Interview Simulator API",
    lifespan=lifespan,
    description="Asynchronous backend for real-time interview evaluation",
    version="1.0.0"
)

# Enable CORS for frontend dashboard
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],  # In production, specify frontend domain
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# Include Routers with Semantic Versioning (v1)
app.include_router(auth.router, prefix='/api/v1/auth', tags=["Authentication"])
app.include_router(resume.router, prefix="/api/v1/resume", tags=["Resume Processing"])
app.include_router(interview.router, prefix='/api/v1/interview', tags=["Interview Questioning"])
app.include_router(candidate_evaluation.router, prefix='/api/v1/eval', tags=["Candidate evaluation processing"])
app.include_router(dashboard.router, prefix='/api/v1/dashboard', tags=["Dashboard data fetching"])
app.include_router(download_report.router, prefix='/api/v1/download', tags=["Download pdf report"])

# Serve the frontend static files (HTML, CSS, JS)
# Mount AFTER API routes so API endpoints take priority over static file matching
app.mount("/", StaticFiles(directory="frontend", html=True), name="frontend")
