"""Main FastAPI application entry point."""

import logging
from contextlib import asynccontextmanager
from datetime import datetime, UTC

from fastapi import FastAPI, HTTPException
from fastapi.middleware.cors import CORSMiddleware
from fastapi.exception_handlers import http_exception_handler
from fastapi.exceptions import RequestValidationError
from starlette.exceptions import HTTPException as StarletteHTTPException

from config.settings import get_config
from adapters.api.routers import create_api_router
from adapters.api.dependencies import cleanup_dependencies


# Configure logging
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s'
)

logger = logging.getLogger(__name__)


@asynccontextmanager
async def lifespan(app: FastAPI):
    """Application lifespan manager."""
    # Startup
    logger.info("Starting GraphAPI Query application...")
    
    # Initialize configuration
    config = get_config()
    logger.info(f"Environment: {config.ENVIRONMENT}")
    logger.info(f"Database URL: {config.DATABASE_URL.split('@')[-1] if '@' in config.DATABASE_URL else 'Not configured'}")
    logger.info(f"Graph API Endpoint: {config.GRAPH_API_ENDPOINT}")
    logger.info(f"External API URL: {config.EXTERNAL_API_URL}")
    
    yield
    
    # Shutdown
    logger.info("Shutting down GraphAPI Query application...")
    try:
        await cleanup_dependencies()
        logger.info("Dependencies cleaned up successfully")
    except Exception as e:
        logger.error(f"Error during cleanup: {e}")


def create_app() -> FastAPI:
    """Create and configure FastAPI application."""
    config = get_config()
    
    # Create FastAPI application
    app = FastAPI(
        title="GraphAPI Query System",
        description="Microsoft Graph API Email Detection and Transmission System",
        version="1.0.0",
        docs_url="/docs" if config.ENVIRONMENT == "development" else None,
        redoc_url="/redoc" if config.ENVIRONMENT == "development" else None,
        lifespan=lifespan
    )
    
    # Add CORS middleware
    app.add_middleware(
        CORSMiddleware,
        allow_origins=["*"] if config.ENVIRONMENT == "development" else [],
        allow_credentials=True,
        allow_methods=["*"],
        allow_headers=["*"],
    )
    
    # Include API routers
    api_router = create_api_router()
    app.include_router(api_router, prefix="/api/v1")
    
    # Root endpoints
    @app.get("/")
    async def root():
        """Root endpoint."""
        return {
            "message": "GraphAPI Query System",
            "version": "1.0.0",
            "status": "running",
            "environment": config.ENVIRONMENT,
            "docs_url": "/docs" if config.ENVIRONMENT == "development" else None,
            "api_prefix": "/api/v1",
            "timestamp": datetime.now(UTC).isoformat()
        }
    
    @app.get("/health")
    async def basic_health_check():
        """Basic health check endpoint."""
        return {
            "status": "healthy",
            "timestamp": datetime.now(UTC).isoformat(),
            "version": "1.0.0"
        }
    
    return app


# Create the FastAPI app instance
app = create_app()


if __name__ == "__main__":
    import uvicorn
    
    config = get_config()
    
    # Run the application
    uvicorn.run(
        "main:app",
        host=config.API_HOST,
        port=config.API_PORT,
        reload=config.API_RELOAD,
        log_level="info"
    )
