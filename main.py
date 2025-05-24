"""Main FastAPI application entry point."""

import logging
from contextlib import asynccontextmanager

from fastapi import FastAPI, HTTPException
from fastapi.middleware.cors import CORSMiddleware
from fastapi.exception_handlers import http_exception_handler
from fastapi.exceptions import RequestValidationError
from starlette.exceptions import HTTPException as StarletteHTTPException

from config.settings import get_config
from adapters.api.routers import create_api_router
from adapters.api.dependencies import cleanup_dependencies
from adapters.api.routers import (
    handle_validation_error, 
    handle_http_exception, 
    handle_general_exception
)


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
            "api_prefix": "/api/v1"
        }
    
    @app.get("/health")
    async def basic_health_check():
        """Basic health check endpoint."""
        return {
            "status": "healthy",
            "timestamp": "2024-01-01T00:00:00Z",
            "version": "1.0.0"
        }
    
    # Add exception handlers
    app.add_exception_handler(RequestValidationError, handle_validation_error)
    app.add_exception_handler(HTTPException, handle_http_exception)
    app.add_exception_handler(StarletteHTTPException, handle_http_exception)
    app.add_exception_handler(Exception, handle_general_exception)
    
    return app


# Create the FastAPI app instance
app = create_app()


if __name__ == "__main__":
    import uvicorn
    
    config = get_config()
    
    # Run the application
    uvicorn.run(
        "main:app",
        host="0.0.0.0",
        port=8000,
        reload=config.ENVIRONMENT == "development",
        log_level="info"
    )
