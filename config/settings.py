"""Application settings using Pydantic Settings."""

from functools import lru_cache
from typing import List, Optional
from pydantic import Field, field_validator, ConfigDict
from pydantic_settings import BaseSettings
import os


class Settings(BaseSettings):
    """Application settings."""
    
    # Environment
    ENVIRONMENT: str = Field(default="development", description="Application environment")
    
    # Microsoft Graph API Settings
    CLIENT_ID: str = Field(default="", description="Azure client ID")
    TENANT_ID: str = Field(default="", description="Azure tenant ID")
    CLIENT_SECRET: str = Field(default="", description="Azure client secret")
    USER_ID: str = Field(default="", description="User ID for Graph API")
    SCOPES: List[str] = Field(
        default=["https://graph.microsoft.com/Mail.Read", "https://graph.microsoft.com/Mail.Send"],
        description="Graph API scopes"
    )
    REDIRECT_URI: str = Field(default="http://localhost:5000/auth/callback", description="OAuth redirect URI")
    GRAPH_API_ENDPOINT: str = Field(default="https://graph.microsoft.com/v1.0", description="Graph API endpoint")
    AUTHORITY: str = Field(default="", description="Azure authority URL")
    TOKEN_CACHE_FILE: str = Field(default=".token_cache.json", description="Token cache file path")
    
    # Database Settings
    DATABASE_URL: str = Field(default="sqlite:///./graphapi.db", description="Database connection URL")
    
    # External API Settings
    EXTERNAL_API_URL: str = Field(default="", description="External API base URL")
    EXTERNAL_API_KEY: str = Field(default="", description="External API key")
    
    # Logging Settings
    LOG_LEVEL: str = Field(default="INFO", description="Logging level")
    LOG_FORMAT: str = Field(default="json", description="Log format")
    
    # FastAPI Settings
    API_HOST: str = Field(default="0.0.0.0", description="API host")
    API_PORT: int = Field(default=5000, description="API port")
    API_RELOAD: bool = Field(default=True, description="Enable API auto-reload")
    
    # JWT Settings
    SECRET_KEY: str = Field(default="your-secret-key-change-this-in-production", description="JWT secret key")
    ALGORITHM: str = Field(default="HS256", description="JWT algorithm")
    ACCESS_TOKEN_EXPIRE_MINUTES: int = Field(default=30, description="Access token expiration minutes")
    
    # Email Detection Settings
    EMAIL_CHECK_INTERVAL: int = Field(default=300, description="Email check interval in seconds")
    MAX_RETRY_COUNT: int = Field(default=3, description="Maximum retry count")
    RETRY_DELAY: int = Field(default=60, description="Retry delay in seconds")
    
    # Optional Sentry Settings
    SENTRY_DSN: Optional[str] = Field(default=None, description="Sentry DSN for error tracking")
    
    @field_validator("ENVIRONMENT")
    @classmethod
    def validate_environment(cls, v):
        """Validate environment value."""
        allowed_envs = ["development", "staging", "production", "test"]
        if v not in allowed_envs:
            raise ValueError(f"Environment must be one of {allowed_envs}")
        return v
    
    @field_validator("LOG_LEVEL")
    @classmethod
    def validate_log_level(cls, v):
        """Validate log level."""
        allowed_levels = ["DEBUG", "INFO", "WARNING", "ERROR", "CRITICAL"]
        if v.upper() not in allowed_levels:
            raise ValueError(f"Log level must be one of {allowed_levels}")
        return v.upper()
    
    @field_validator("SECRET_KEY")
    @classmethod
    def validate_secret_key(cls, v, info):
        """Validate secret key in production."""
        if hasattr(info, 'data') and info.data.get("ENVIRONMENT") == "production" and v == "your-secret-key-change-this-in-production":
            raise ValueError("Secret key must be changed in production environment")
        return v
    
    @property
    def is_development(self) -> bool:
        """Check if running in development mode."""
        return self.ENVIRONMENT == "development"
    
    @property
    def is_production(self) -> bool:
        """Check if running in production mode."""
        return self.ENVIRONMENT == "production"
    
    @property
    def is_test(self) -> bool:
        """Check if running in test mode."""
        return self.ENVIRONMENT == "test"
    
    @property
    def database_echo(self) -> bool:
        """Enable database query logging in development."""
        return self.is_development or self.is_test
    
    model_config = ConfigDict(
        env_file=".env",
        env_file_encoding="utf-8",
        case_sensitive=False
    )


@lru_cache()
def get_settings() -> Settings:
    """Get cached settings instance."""
    return Settings()


# Alias for backward compatibility
def get_config() -> Settings:
    """Get configuration settings."""
    return get_settings()


# Development settings
class DevelopmentSettings(Settings):
    """Development-specific settings."""
    
    def __init__(self, **kwargs):
        super().__init__(**kwargs)
        self.ENVIRONMENT = "development"
        self.API_RELOAD = True
        self.LOG_LEVEL = "DEBUG"


# Test settings
class TestSettings(Settings):
    """Test-specific settings."""
    
    def __init__(self, **kwargs):
        super().__init__(**kwargs)
        self.ENVIRONMENT = "test"
        self.API_RELOAD = False
        self.LOG_LEVEL = "DEBUG"
        self.DATABASE_URL = "sqlite:///./test_graphapi.db"


# Production settings
class ProductionSettings(Settings):
    """Production-specific settings."""
    
    def __init__(self, **kwargs):
        super().__init__(**kwargs)
        self.ENVIRONMENT = "production"
        self.API_RELOAD = False
        self.LOG_LEVEL = "INFO"


def get_settings_by_environment(env: str = None) -> Settings:
    """Get settings based on environment."""
    if env is None:
        env = os.getenv("ENVIRONMENT", "development")
    
    if env == "development":
        return DevelopmentSettings()
    elif env == "test":
        return TestSettings()
    elif env == "production":
        return ProductionSettings()
    else:
        return Settings()
