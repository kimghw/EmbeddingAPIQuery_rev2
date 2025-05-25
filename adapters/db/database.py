"""Database connection and session management."""

import logging
from contextlib import asynccontextmanager
from typing import AsyncGenerator, Optional

from sqlalchemy import create_engine, event, text
from sqlalchemy.ext.asyncio import AsyncSession, create_async_engine, async_sessionmaker
from sqlalchemy.orm import sessionmaker, Session
from sqlalchemy.pool import StaticPool

from core.ports.config import ConfigPort
from core.utils.security import SecurityUtils
from .models import Base


logger = logging.getLogger(__name__)


class DatabaseAdapter:
    """Database adapter for managing connections and sessions."""
    
    def __init__(self, config: ConfigPort):
        """
        Initialize database adapter.
        
        Args:
            config: Configuration port instance
        """
        self.config = config
        self._engine = None
        self._async_engine = None
        self._session_factory = None
        self._async_session_factory = None
        
        # Initialize engines and session factories
        self._setup_engines()
        self._setup_session_factories()
    
    def _setup_engines(self) -> None:
        """Setup synchronous and asynchronous database engines."""
        database_url = self.config.get_database_url()
        echo = self.config.get_database_echo()
        
        # Synchronous engine
        if database_url.startswith("sqlite"):
            # SQLite specific configuration
            self._engine = create_engine(
                database_url,
                echo=echo,
                poolclass=StaticPool,
                connect_args={
                    "check_same_thread": False,
                    "timeout": 20
                }
            )
        else:
            # PostgreSQL/MySQL configuration
            self._engine = create_engine(
                database_url,
                echo=echo,
                pool_size=10,
                max_overflow=20,
                pool_pre_ping=True,
                pool_recycle=3600
            )
        
        # Asynchronous engine
        async_database_url = self._convert_to_async_url(database_url)
        
        if async_database_url.startswith("sqlite+aiosqlite"):
            # Async SQLite configuration
            self._async_engine = create_async_engine(
                async_database_url,
                echo=echo,
                poolclass=StaticPool,
                connect_args={
                    "check_same_thread": False,
                    "timeout": 20
                }
            )
        else:
            # Async PostgreSQL configuration
            self._async_engine = create_async_engine(
                async_database_url,
                echo=echo,
                pool_size=10,
                max_overflow=20,
                pool_pre_ping=True,
                pool_recycle=3600
            )
        
        # Add event listeners
        self._setup_event_listeners()
        
        logger.info(f"Database engines initialized with URL: {self._mask_url(database_url)}")
    
    def _convert_to_async_url(self, sync_url: str) -> str:
        """Convert synchronous database URL to asynchronous."""
        if sync_url.startswith("sqlite:///"):
            return sync_url.replace("sqlite:///", "sqlite+aiosqlite:///")
        elif sync_url.startswith("postgresql://"):
            return sync_url.replace("postgresql://", "postgresql+asyncpg://")
        elif sync_url.startswith("mysql://"):
            return sync_url.replace("mysql://", "mysql+aiomysql://")
        else:
            return sync_url
    
    def _mask_url(self, url: str) -> str:
        """Mask sensitive information in database URL for logging."""
        return SecurityUtils.mask_url(url)
    
    def _setup_session_factories(self) -> None:
        """Setup session factories for sync and async operations."""
        # Synchronous session factory
        self._session_factory = sessionmaker(
            bind=self._engine,
            class_=Session,
            expire_on_commit=False
        )
        
        # Asynchronous session factory
        self._async_session_factory = async_sessionmaker(
            bind=self._async_engine,
            class_=AsyncSession,
            expire_on_commit=False
        )
        
        logger.info("Database session factories initialized")
    
    def _setup_event_listeners(self) -> None:
        """Setup database event listeners."""
        
        @event.listens_for(self._engine, "connect")
        def set_sqlite_pragma(dbapi_connection, connection_record):
            """Set SQLite pragmas for better performance and reliability."""
            if "sqlite" in str(self._engine.url):
                cursor = dbapi_connection.cursor()
                cursor.execute("PRAGMA foreign_keys=ON")
                cursor.execute("PRAGMA journal_mode=WAL")
                cursor.execute("PRAGMA synchronous=NORMAL")
                cursor.execute("PRAGMA temp_store=MEMORY")
                cursor.execute("PRAGMA mmap_size=268435456")  # 256MB
                cursor.close()
        
        @event.listens_for(self._engine, "checkout")
        def receive_checkout(dbapi_connection, connection_record, connection_proxy):
            """Log database connection checkout."""
            logger.debug("Database connection checked out")
        
        @event.listens_for(self._engine, "checkin")
        def receive_checkin(dbapi_connection, connection_record):
            """Log database connection checkin."""
            logger.debug("Database connection checked in")
    
    # Synchronous methods
    def get_session(self) -> Session:
        """Get synchronous database session."""
        if not self._session_factory:
            raise RuntimeError("Database not initialized")
        return self._session_factory()
    
    def create_tables(self) -> None:
        """Create all database tables."""
        if not self._engine:
            raise RuntimeError("Database engine not initialized")
        
        logger.info("Creating database tables...")
        Base.metadata.create_all(bind=self._engine)
        logger.info("Database tables created successfully")
    
    def drop_tables(self) -> None:
        """Drop all database tables."""
        if not self._engine:
            raise RuntimeError("Database engine not initialized")
        
        logger.warning("Dropping all database tables...")
        Base.metadata.drop_all(bind=self._engine)
        logger.warning("All database tables dropped")
    
    # Asynchronous methods
    async def get_async_session(self) -> AsyncSession:
        """Get asynchronous database session."""
        if not self._async_session_factory:
            raise RuntimeError("Async database not initialized")
        return self._async_session_factory()
    
    async def create_tables_async(self) -> None:
        """Create all database tables asynchronously."""
        if not self._async_engine:
            raise RuntimeError("Async database engine not initialized")
        
        logger.info("Creating database tables asynchronously...")
        async with self._async_engine.begin() as conn:
            await conn.run_sync(Base.metadata.create_all)
        logger.info("Database tables created successfully")
    
    async def drop_tables_async(self) -> None:
        """Drop all database tables asynchronously."""
        if not self._async_engine:
            raise RuntimeError("Async database engine not initialized")
        
        logger.warning("Dropping all database tables asynchronously...")
        async with self._async_engine.begin() as conn:
            await conn.run_sync(Base.metadata.drop_all)
        logger.warning("All database tables dropped")
    
    # Context managers
    @asynccontextmanager
    async def async_session_scope(self) -> AsyncGenerator[AsyncSession, None]:
        """
        Async context manager for database sessions with automatic commit/rollback.
        
        Usage:
            async with db_adapter.async_session_scope() as session:
                # Use session here
                pass
        """
        session = await self.get_async_session()
        try:
            yield session
            await session.commit()
        except Exception as e:
            await session.rollback()
            logger.error(f"Database session rolled back due to error: {e}")
            raise
        finally:
            await session.close()
    
    def session_scope(self):
        """
        Context manager for synchronous database sessions with automatic commit/rollback.
        
        Usage:
            with db_adapter.session_scope() as session:
                # Use session here
                pass
        """
        from contextlib import contextmanager
        
        @contextmanager
        def _session_scope():
            session = self.get_session()
            try:
                yield session
                session.commit()
            except Exception as e:
                session.rollback()
                logger.error(f"Database session rolled back due to error: {e}")
                raise
            finally:
                session.close()
        
        return _session_scope()
    
    # Health check and maintenance
    async def health_check(self) -> bool:
        """
        Check database connectivity and health.
        
        Returns:
            True if database is healthy, False otherwise
        """
        try:
            async with self.async_session_scope() as session:
                result = await session.execute(text("SELECT 1"))
                return result.scalar() == 1
        except Exception as e:
            logger.error(f"Database health check failed: {e}")
            return False
    
    def sync_health_check(self) -> bool:
        """
        Synchronous database health check.
        
        Returns:
            True if database is healthy, False otherwise
        """
        try:
            with self.session_scope() as session:
                result = session.execute(text("SELECT 1"))
                return result.scalar() == 1
        except Exception as e:
            logger.error(f"Database health check failed: {e}")
            return False
    
    async def get_connection_info(self) -> dict:
        """Get database connection information."""
        return {
            "url": self._mask_url(str(self._async_engine.url)),
            "pool_size": getattr(self._async_engine.pool, 'size', None),
            "checked_out_connections": getattr(self._async_engine.pool, 'checkedout', None),
            "overflow_connections": getattr(self._async_engine.pool, 'overflow', None),
            "is_healthy": await self.health_check()
        }
    
    # Cleanup
    async def close(self) -> None:
        """Close database connections and cleanup resources."""
        if self._async_engine:
            await self._async_engine.dispose()
            logger.info("Async database engine disposed")
        
        if self._engine:
            self._engine.dispose()
            logger.info("Sync database engine disposed")


# Global database adapter instance
_database_adapter: Optional[DatabaseAdapter] = None


def initialize_database(config: ConfigPort) -> DatabaseAdapter:
    """
    Initialize global database adapter.
    
    Args:
        config: Configuration port instance
        
    Returns:
        DatabaseAdapter instance
    """
    global _database_adapter
    _database_adapter = DatabaseAdapter(config)
    return _database_adapter


def get_database_adapter() -> DatabaseAdapter:
    """
    Get global database adapter instance.
    
    Returns:
        DatabaseAdapter instance
        
    Raises:
        RuntimeError: If database not initialized
    """
    if _database_adapter is None:
        raise RuntimeError("Database not initialized. Call initialize_database() first.")
    return _database_adapter


# Dependency injection functions for FastAPI
async def get_database_session() -> AsyncGenerator[AsyncSession, None]:
    """
    FastAPI dependency for getting async database session.
    
    Yields:
        AsyncSession instance
    """
    db_adapter = get_database_adapter()
    async with db_adapter.async_session_scope() as session:
        yield session


def get_sync_database_session() -> Session:
    """
    Get synchronous database session for CLI usage.
    
    Returns:
        Session instance
    """
    db_adapter = get_database_adapter()
    return db_adapter.get_session()


# Database migration utilities
async def migrate_database(config: ConfigPort, drop_existing: bool = False) -> None:
    """
    Migrate database schema.
    
    Args:
        config: Configuration port instance
        drop_existing: Whether to drop existing tables first
    """
    db_adapter = DatabaseAdapter(config)
    
    try:
        if drop_existing:
            await db_adapter.drop_tables_async()
        
        await db_adapter.create_tables_async()
        logger.info("Database migration completed successfully")
        
    except Exception as e:
        logger.error(f"Database migration failed: {e}")
        raise
    finally:
        await db_adapter.close()


def migrate_database_sync(config: ConfigPort, drop_existing: bool = False) -> None:
    """
    Synchronous database migration.
    
    Args:
        config: Configuration port instance
        drop_existing: Whether to drop existing tables first
    """
    db_adapter = DatabaseAdapter(config)
    
    try:
        if drop_existing:
            db_adapter.drop_tables()
        
        db_adapter.create_tables()
        logger.info("Database migration completed successfully")
        
    except Exception as e:
        logger.error(f"Database migration failed: {e}")
        raise
    finally:
        if db_adapter._engine:
            db_adapter._engine.dispose()
