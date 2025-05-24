"""Application settings using Pydantic Settings."""

from functools import lru_cache
from typing import List, Optional
from pydantic import Field, validator
from pydantic_settings import BaseSettings
import os


class Settings(BaseSettings):
    """Application settings."""
    
    # Environment
    ENVIRONMENT: str = Field(default="development", env="ENVIRONMENT")
    
    # Microsoft Graph API Settings
    CLIENT_ID: str = Field(default="", env="CLIENT_ID")
    TENANT_ID: str = Field(default="", env="TENANT_ID")
    CLIENT_SECRET: str = Field(default="", env="CLIENT_SECRET")
    USER_ID: str = Field(default="", env="USER_ID")
    SCOPES: List[str] = Field(
        default=["https://graph.microsoft.com/Mail.Read", "https://graph.microsoft.com/Mail.Send"],
        env="SCOPES"
    )
    REDIRECT_URI: str = Field(default="http://localhost:5000/auth/callback", env="REDIRECT_URI")
    GRAPH_API_ENDPOINT: str = Field(default="https://graph.microsoft.com/v1.0", env="GRAPH_API_ENDPOINT")
    AUTHORITY: str = Field(default="", env="AUTHORITY")
    TOKEN_CACHE_FILE: str = Field(default=".token_cache.json", env="TOKEN_CACHE_FILE")
    
    # Database Settings
    DATABASE_URL: str = Field(default="sqlite:///./graphapi.db", env="DATABASE_URL")
    
    # External API Settings
    EXTERNAL_API_URL: str = Field(default="", env="EXTERNAL_API_URL")
    EXTERNAL_API_KEY: str = Field(default="", env="EXTERNAL_API_KEY")
    
    # Logging Settings
    LOG_LEVEL: str = Field(default="INFO", env="LOG_LEVEL")
    LOG_FORMAT: str = Field(default="json", env="LOG_FORMAT")
    
    # FastAPI Settings
    API_HOST: str = Field(default="0.0.0.0", env="API_HOST")
    API_PORT: int = Field(default=8000, env="API_PORT")
    API_RELOAD: bool = Field(default=True, env="API_RELOAD")
    
    # JWT Settings
    SECRET_KEY: str = Field(default="your-secret-key-change-this-in-production", env="SECRET_KEY")
    ALGORITHM: str = Field(default="HS256", env="ALGORITHM")
    ACCESS_TOKEN_EXPIRE_MINUTES: int = Field(default=30, env="ACCESS_TOKEN_EXPIRE_MINUTES")
    
    # Email Detection Settings
    EMAIL_CHECK_INTERVAL: int = Field(default=300, env="EMAIL_CHECK_INTERVAL")
    MAX_RETRY_COUNT: int = Field(default=3, env="MAX_RETRY_COUNT")
    RETRY_DELAY: int = Field(default=60, env="RETRY_DELAY")
    
    # Optional Sentry Settings
    SENTRY_DSN: Optional[str] = Field(default=None, env="SENTRY_DSN")
    
    @validator("ENVIRONMENT")
    def validate_environment(cls, v):
        """Validate environment value."""
        allowed_envs = ["development", "staging", "production"]
        if v not in allowed_envs:
            raise ValueError(f"Environment must be one of {allowed_envs}")
        return v
    
    @validator("LOG_LEVEL")
    def validate_log_level(cls, v):
        """Validate log level."""
        allowed_levels = ["DEBUG", "INFO", "WARNING", "ERROR", "CRITICAL"]
        if v.upper() not in allowed_levels:
            raise ValueError(f"Log level must be one of {allowed_levels}")
        return v.upper()
    
    @validator("SECRET_KEY")
    def validate_secret_key(cls, v, values):
        """Validate secret key in production."""
        if values.get("ENVIRONMENT") == "production" and v == "your-secret-key-change-this-in-production":
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
    def database_echo(self) -> bool:
        """Enable database query logging in development."""
        return self.is_development
    
    class Config:
        """Pydantic config."""
        env_file = ".env"
        env_file_encoding = "utf-8"
        case_sensitive = False


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
    elif env == "production":
        return ProductionSettings()
    else:
        return Settings()
