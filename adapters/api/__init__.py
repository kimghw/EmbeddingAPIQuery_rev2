"""API adapters package."""

from .routers import create_api_router
from .dependencies import get_dependencies

__all__ = ["create_api_router", "get_dependencies"]
