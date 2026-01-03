"""Main FastAPI application entry point."""

import sys
from contextlib import asynccontextmanager

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from loguru import logger

from app import __version__
from app.config import settings
from app.routers import generate_router
from app.services.session import get_session, close_session
from app.services.recaptcha import recaptcha_manager


# Configure loguru
logger.remove()
logger.add(
    sys.stdout,
    format="<green>{time:YYYY-MM-DD HH:mm:ss}</green> | <level>{level: <8}</level> | <cyan>{name}</cyan>:<cyan>{function}</cyan>:<cyan>{line}</cyan> - <level>{message}</level>",
    level="INFO",
)


@asynccontextmanager
async def lifespan(app: FastAPI):
    """Application lifespan manager."""
    logger.info(f"Starting Vertex AI to Gemini API v{__version__}")
    logger.info(f"Server running on {settings.host}:{settings.port}")
    logger.info(f"Proxy: {settings.proxy or 'None'}")
    logger.info(f"Timeout: {settings.timeout}s")
    logger.info(f"Max retries: {settings.max_retry}")
    logger.info(
        f"Token refresh: TTL={settings.token_ttl}s, interval={settings.token_refresh_interval}s"
    )

    # Initialize session and start background token refresh
    session = await get_session()
    await recaptcha_manager.start_background_refresh(session)

    yield

    logger.info("Shutting down...")
    await recaptcha_manager.stop_background_refresh()
    await close_session()
    logger.info("Shutdown complete")


# Create FastAPI application
app = FastAPI(
    title="Vertex AI Anonymous to Gemini API",
    description="A proxy service that converts Vertex AI Anonymous API to standard Google Gemini API format",
    version=__version__,
    lifespan=lifespan,
    docs_url="/docs",
    redoc_url="/redoc",
)


# Add CORS middleware
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)


# Include routers
app.include_router(generate_router, tags=["Generate"])


@app.get("/", tags=["Health"])
async def root():
    """Root endpoint for health check."""
    return {
        "service": "Vertex AI Anonymous to Gemini API",
        "version": __version__,
        "status": "healthy",
    }


@app.get("/health", tags=["Health"])
async def health():
    """Health check endpoint."""
    return {"status": "healthy"}


def run():
    """Run the application with uvicorn."""
    import uvicorn

    uvicorn.run(
        "app.main:app",
        host=settings.host,
        port=settings.port,
        reload=False,
        log_level="info",
    )


if __name__ == "__main__":
    run()