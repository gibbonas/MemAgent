"""
FastAPI Main Application - MemAgent

Production-ready multi-agent AI application for memory preservation.
"""

from contextlib import asynccontextmanager

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware

from app.config import settings
from app.core.monitoring import logger, setup_logging
from app.storage.database import close_db, init_db


@asynccontextmanager
async def lifespan(app: FastAPI):
    """
    Application lifespan manager.
    
    Handles startup and shutdown events.
    """
    # Startup
    setup_logging(settings.log_level)
    logger.info("application_starting", version="0.1.0")
    
    # Initialize database
    await init_db()
    logger.info("database_initialized")
    
    # Create temp directories
    import os
    os.makedirs(settings.temp_image_dir, exist_ok=True)
    
    yield
    
    # Shutdown
    logger.info("application_shutting_down")
    await close_db()


# Create FastAPI app
app = FastAPI(
    title="MemAgent API",
    description="AI-powered memory preservation system",
    version="0.1.0",
    lifespan=lifespan
)

# Configure CORS - Secure configuration using environment variables
# IMPORTANT: In production, only allow your actual frontend domain(s)
# Never use allow_origins=["*"] with allow_credentials=True
app.add_middleware(
    CORSMiddleware,
    allow_origins=settings.cors_origins,  # Loaded from .env.local
    allow_credentials=True,  # Required for OAuth cookies/sessions
    allow_methods=["GET", "POST", "PUT", "DELETE", "OPTIONS"],  # Explicit methods only
    allow_headers=["*"],  # Can be restricted further in production
    max_age=3600,  # Cache preflight requests for 1 hour
)

# Import and include routers
from app.api.routes import auth, chat, photos

app.include_router(auth.router, prefix="/api/auth", tags=["authentication"])
app.include_router(chat.router, prefix="/api/chat", tags=["chat"])
app.include_router(photos.router, prefix="/api/photos", tags=["photos"])


@app.get("/")
async def root():
    """Root endpoint."""
    return {
        "name": "MemAgent API",
        "version": "0.1.0",
        "status": "running"
    }


@app.get("/health")
async def health():
    """Health check endpoint."""
    return {"status": "healthy"}


if __name__ == "__main__":
    import uvicorn
    uvicorn.run(app, host="0.0.0.0", port=8000)
