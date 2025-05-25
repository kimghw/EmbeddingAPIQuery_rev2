"""FastAPI dependencies for dependency injection."""

import logging
from typing import AsyncGenerator

from fastapi import Depends
from sqlalchemy.ext.asyncio import AsyncSession

from config.settings import get_config
from adapters.config import ConfigAdapter
from adapters.db.database import initialize_database
from adapters.db.repositories import (
    SQLUserRepository, SQLAccountRepository,
    SQLEmailRepository, SQLTransmissionRecordRepository
)
from adapters.graph_api import GraphAPIAdapter
from adapters.external_api import ExternalAPIAdapter

from core.usecases.account_management import AccountManagementUseCase
from core.usecases.email_detection import EmailDetectionUseCase
from core.usecases.external_transmission import ExternalTransmissionUseCase


logger = logging.getLogger(__name__)

# Global instances (initialized once)
_config = None
_db_adapter = None
_graph_api = None
_external_api = None


def get_config_dependency() -> ConfigAdapter:
    """Get configuration dependency."""
    global _config
    if _config is None:
        _config = ConfigAdapter(get_config())
        logger.info("Configuration initialized")
    return _config


def get_db_adapter_dependency(config: ConfigAdapter = Depends(get_config_dependency)):
    """Get database adapter dependency."""
    global _db_adapter
    if _db_adapter is None:
        _db_adapter = initialize_database(config)
        logger.info("Database adapter initialized")
    return _db_adapter


async def get_db_session(
    db_adapter = Depends(get_db_adapter_dependency)
) -> AsyncGenerator[AsyncSession, None]:
    """Get database session dependency."""
    async with db_adapter.async_session_scope() as session:
        yield session


def get_graph_api_dependency(config: ConfigAdapter = Depends(get_config_dependency)) -> GraphAPIAdapter:
    """Get Graph API adapter dependency."""
    global _graph_api
    if _graph_api is None:
        _graph_api = GraphAPIAdapter(config)
        logger.info("Graph API adapter initialized")
    return _graph_api


def get_external_api_dependency(config: ConfigAdapter = Depends(get_config_dependency)) -> ExternalAPIAdapter:
    """Get External API adapter dependency."""
    global _external_api
    if _external_api is None:
        _external_api = ExternalAPIAdapter(config)
        logger.info("External API adapter initialized")
    return _external_api


# Repository dependencies
def get_user_repository(session: AsyncSession = Depends(get_db_session)) -> SQLUserRepository:
    """Get user repository dependency."""
    return SQLUserRepository(session)


def get_account_repository(session: AsyncSession = Depends(get_db_session)) -> SQLAccountRepository:
    """Get account repository dependency."""
    return SQLAccountRepository(session)


def get_email_repository(session: AsyncSession = Depends(get_db_session)) -> SQLEmailRepository:
    """Get email repository dependency."""
    return SQLEmailRepository(session)


def get_transmission_repository(session: AsyncSession = Depends(get_db_session)) -> SQLTransmissionRecordRepository:
    """Get transmission record repository dependency."""
    return SQLTransmissionRecordRepository(session)


# Use case dependencies
def get_account_usecase(
    user_repo: SQLUserRepository = Depends(get_user_repository),
    account_repo: SQLAccountRepository = Depends(get_account_repository),
    graph_api: GraphAPIAdapter = Depends(get_graph_api_dependency),
    config: ConfigAdapter = Depends(get_config_dependency)
) -> AccountManagementUseCase:
    """Get account management use case dependency."""
    return AccountManagementUseCase(
        user_repository=user_repo,
        account_repository=account_repo,
        graph_api=graph_api,
        config=config
    )


def get_email_usecase(
    account_repo: SQLAccountRepository = Depends(get_account_repository),
    email_repo: SQLEmailRepository = Depends(get_email_repository),
    graph_api: GraphAPIAdapter = Depends(get_graph_api_dependency),
    config: ConfigAdapter = Depends(get_config_dependency)
) -> EmailDetectionUseCase:
    """Get email detection use case dependency."""
    return EmailDetectionUseCase(
        account_repository=account_repo,
        email_repository=email_repo,
        graph_api=graph_api,
        config=config
    )


def get_transmission_usecase(
    email_repo: SQLEmailRepository = Depends(get_email_repository),
    transmission_repo: SQLTransmissionRecordRepository = Depends(get_transmission_repository),
    external_api: ExternalAPIAdapter = Depends(get_external_api_dependency),
    config: ConfigAdapter = Depends(get_config_dependency)
) -> ExternalTransmissionUseCase:
    """Get external transmission use case dependency."""
    return ExternalTransmissionUseCase(
        email_repository=email_repo,
        transmission_repository=transmission_repo,
        external_api=external_api,
        config=config
    )


# Convenience function for getting all dependencies
def get_dependencies():
    """Get all dependencies for manual initialization."""
    return {
        'config': get_config_dependency(),
        'db_adapter': get_db_adapter_dependency(),
        'graph_api': get_graph_api_dependency(),
        'external_api': get_external_api_dependency()
    }


# Cleanup function for application shutdown
async def cleanup_dependencies():
    """Cleanup global dependencies on application shutdown."""
    global _graph_api, _external_api, _db_adapter
    
    try:
        if _graph_api:
            await _graph_api.close()
            logger.info("Graph API adapter closed")
        
        if _external_api:
            await _external_api.close()
            logger.info("External API adapter closed")
        
        if _db_adapter:
            await _db_adapter.close()
            logger.info("Database adapter closed")
            
    except Exception as e:
        logger.error(f"Error during cleanup: {e}")
