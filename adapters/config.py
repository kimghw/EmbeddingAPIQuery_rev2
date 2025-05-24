"""Configuration adapter implementation."""

import os
import logging
from typing import Any, Dict, List, Optional
from pydantic import Field, field_validator
from pydantic_settings import BaseSettings

from core.ports.config import (
    ConfigPort, 
    Environment, 
    ConfigurationError, 
    MissingConfigurationError,
    InvalidConfigurationError
)
from core.utils.security import SecurityUtils


class Settings(BaseSettings):
    """Pydantic settings for configuration management."""
    
    # Environment
    environment: Environment = Field(Environment.DEVELOPMENT, env="ENVIRONMENT")
    
    # Database Configuration
    database_url: str = Field(default="sqlite:///./graphapi.db", env="DATABASE_URL")
    database_echo: bool = Field(False, env="DATABASE_ECHO")
    
    # Microsoft Graph API Configuration
    client_id: str = Field(default="", env="MICROSOFT_CLIENT_ID")
    client_secret: str = Field(default="", env="MICROSOFT_CLIENT_SECRET")
    tenant_id: str = Field(default="", env="MICROSOFT_TENANT_ID")
    authority: str = Field(
        "https://login.microsoftonline.com/{tenant_id}",
        env="MICROSOFT_AUTHORITY"
    )
    scopes: List[str] = Field(
        default=[
            "https://graph.microsoft.com/Mail.Read",
            "https://graph.microsoft.com/Mail.ReadWrite",
            "https://graph.microsoft.com/User.Read"
        ],
        env="MICROSOFT_SCOPES"
    )
    redirect_uri: str = Field(
        "http://localhost:5000/auth/callback",
        env="MICROSOFT_REDIRECT_URI"
    )
    graph_api_endpoint: str = Field(
        "https://graph.microsoft.com/v1.0",
        env="GRAPH_API_ENDPOINT"
    )
    token_cache_file: str = Field(
        ".token_cache.json",
        env="TOKEN_CACHE_FILE"
    )
    
    # External API Configuration
    external_api_url: str = Field(default="", env="EXTERNAL_API_URL")
    external_api_key: str = Field(default="", env="EXTERNAL_API_KEY")
    
    # FastAPI Configuration
    api_host: str = Field("0.0.0.0", env="API_HOST")
    api_port: int = Field(5000, env="API_PORT")
    api_reload: bool = Field(True, env="API_RELOAD")
    
    # JWT Configuration
    secret_key: str = Field(default="your-secret-key-change-this-in-production", env="SECRET_KEY")
    algorithm: str = Field("HS256", env="JWT_ALGORITHM")
    access_token_expire_minutes: int = Field(30, env="ACCESS_TOKEN_EXPIRE_MINUTES")
    
    # Logging Configuration
    log_level: str = Field("INFO", env="LOG_LEVEL")
    log_format: str = Field(
        "%(asctime)s - %(name)s - %(levelname)s - %(message)s",
        env="LOG_FORMAT"
    )
    
    # Email Detection Configuration
    email_check_interval: int = Field(300, env="EMAIL_CHECK_INTERVAL")  # 5 minutes
    max_retry_count: int = Field(3, env="MAX_RETRY_COUNT")
    retry_delay: int = Field(60, env="RETRY_DELAY")  # 1 minute
    
    # Optional Configuration
    sentry_dsn: Optional[str] = Field(None, env="SENTRY_DSN")
    user_id: str = Field("default-user", env="DEFAULT_USER_ID")
    
    model_config = {
        "env_file": ".env",
        "env_file_encoding": "utf-8",
        "case_sensitive": False
    }
    
    @field_validator("authority")
    @classmethod
    def format_authority(cls, v, info):
        """Format authority URL with tenant ID."""
        if "{tenant_id}" in v and "tenant_id" in info.data:
            return v.format(tenant_id=info.data["tenant_id"])
        return v
    
    @field_validator("scopes", mode="before")
    @classmethod
    def parse_scopes(cls, v):
        """Parse scopes from string or list."""
        if isinstance(v, str):
            return [scope.strip() for scope in v.split(",")]
        return v
    
    @field_validator("log_level")
    @classmethod
    def validate_log_level(cls, v):
        """Validate log level."""
        valid_levels = ["DEBUG", "INFO", "WARNING", "ERROR", "CRITICAL"]
        if v.upper() not in valid_levels:
            raise ValueError(f"Invalid log level: {v}. Must be one of {valid_levels}")
        return v.upper()
    
    @field_validator("log_format")
    @classmethod
    def validate_log_format(cls, v):
        """Validate and fix log format."""
        # If format is 'json' or invalid, use default format
        if v == "json" or not isinstance(v, str):
            return "%(asctime)s - %(name)s - %(levelname)s - %(message)s"
        return v
    
    @field_validator("api_port")
    @classmethod
    def validate_api_port(cls, v):
        """Validate API port range."""
        if not (1 <= v <= 65535):
            raise ValueError(f"Invalid port: {v}. Must be between 1 and 65535")
        return v


class DevelopmentSettings(Settings):
    """Development environment settings."""
    
    environment: Environment = Environment.DEVELOPMENT
    database_echo: bool = True
    api_reload: bool = True
    log_level: str = "DEBUG"


class StagingSettings(Settings):
    """Staging environment settings."""
    
    environment: Environment = Environment.STAGING
    database_echo: bool = False
    api_reload: bool = False
    log_level: str = "INFO"


class ProductionSettings(Settings):
    """Production environment settings."""
    
    environment: Environment = Environment.PRODUCTION
    database_echo: bool = False
    api_reload: bool = False
    log_level: str = "WARNING"
    
    @field_validator("secret_key")
    @classmethod
    def validate_secret_key_production(cls, v):
        """Ensure secret key is secure in production."""
        if len(v) < 32:
            raise ValueError("Secret key must be at least 32 characters in production")
        return v
    
    @field_validator("sentry_dsn")
    @classmethod
    def require_sentry_in_production(cls, v):
        """Require Sentry DSN in production."""
        if not v:
            raise ValueError("Sentry DSN is required in production environment")
        return v


class ConfigAdapter(ConfigPort):
    """Configuration adapter implementation using Pydantic Settings."""
    
    def __init__(self, settings: Optional[Settings] = None):
        """
        Initialize configuration adapter.
        
        Args:
            settings: Optional settings instance. If None, will be created based on environment.
        """
        if settings:
            self._settings = settings
        else:
            self._settings = self._create_settings()
        
        # Setup logging
        self._setup_logging()
        
        # Log configuration status
        self._log_configuration_status()
    
    def _create_settings(self) -> Settings:
        """Create settings instance based on environment."""
        env = os.getenv("ENVIRONMENT", "development").lower()
        
        if env == "production":
            return ProductionSettings()
        elif env == "staging":
            return StagingSettings()
        else:
            return DevelopmentSettings()
    
    def _setup_logging(self) -> None:
        """Setup logging configuration."""
        # Safely get log format with fallback
        log_format = getattr(self._settings, 'log_format', None)
        if not log_format or log_format == "json":
            log_format = "%(asctime)s - %(name)s - %(levelname)s - %(message)s"
        
        # Safely get log level with fallback
        log_level = getattr(self._settings, 'log_level', 'INFO')
        
        logging.basicConfig(
            level=getattr(logging, log_level),
            format=log_format
        )
        
        # Create logger for this adapter
        self._logger = logging.getLogger(__name__)
    
    def _log_configuration_status(self) -> None:
        """Log configuration status."""
        environment = getattr(self._settings, 'environment', 'unknown')
        database_url = getattr(self._settings, 'database_url', '')
        client_id = getattr(self._settings, 'client_id', '')
        external_api_url = getattr(self._settings, 'external_api_url', '')
        
        self._logger.info(f"Configuration loaded for environment: {environment}")
        self._logger.info(f"Database URL configured: {bool(database_url)}")
        self._logger.info(f"Microsoft Graph API configured: {bool(client_id)}")
        self._logger.info(f"External API configured: {bool(external_api_url)}")
    
    # ConfigPort implementation
    def get(self, key: str, default: Any = None) -> Any:
        """Get configuration value by key."""
        return getattr(self._settings, key, default)
    
    def get_string(self, key: str, default: str = "") -> str:
        """Get string configuration value."""
        value = self.get(key, default)
        return str(value) if value is not None else default
    
    def get_int(self, key: str, default: int = 0) -> int:
        """Get integer configuration value."""
        value = self.get(key, default)
        try:
            return int(value) if value is not None else default
        except (ValueError, TypeError):
            return default
    
    def get_float(self, key: str, default: float = 0.0) -> float:
        """Get float configuration value."""
        value = self.get(key, default)
        try:
            return float(value) if value is not None else default
        except (ValueError, TypeError):
            return default
    
    def get_bool(self, key: str, default: bool = False) -> bool:
        """Get boolean configuration value."""
        value = self.get(key, default)
        if isinstance(value, bool):
            return value
        if isinstance(value, str):
            return value.lower() in ("true", "1", "yes", "on")
        return bool(value) if value is not None else default
    
    def get_list(self, key: str, default: List[Any] = None) -> List[Any]:
        """Get list configuration value."""
        if default is None:
            default = []
        value = self.get(key, default)
        if isinstance(value, list):
            return value
        if isinstance(value, str):
            return [item.strip() for item in value.split(",") if item.strip()]
        return default
    
    def get_dict(self, key: str, default: Dict[str, Any] = None) -> Dict[str, Any]:
        """Get dictionary configuration value."""
        if default is None:
            default = {}
        value = self.get(key, default)
        return value if isinstance(value, dict) else default
    
    # Environment methods
    def get_environment(self) -> Environment:
        """Get current environment."""
        return self._settings.environment
    
    def is_development(self) -> bool:
        """Check if running in development mode."""
        return self._settings.environment == Environment.DEVELOPMENT
    
    def is_staging(self) -> bool:
        """Check if running in staging mode."""
        return self._settings.environment == Environment.STAGING
    
    def is_production(self) -> bool:
        """Check if running in production mode."""
        return self._settings.environment == Environment.PRODUCTION
    
    # Database Configuration
    def get_database_url(self) -> str:
        """Get database connection URL."""
        return getattr(self._settings, 'database_url', 'sqlite:///./graphapi.db')
    
    def get_database_echo(self) -> bool:
        """Get database echo setting."""
        return getattr(self._settings, 'database_echo', False)
    
    # Microsoft Graph API Configuration
    def get_client_id(self) -> str:
        """Get Microsoft Graph client ID."""
        return getattr(self._settings, 'client_id', '')
    
    def get_client_secret(self) -> str:
        """Get Microsoft Graph client secret."""
        return getattr(self._settings, 'client_secret', '')
    
    def get_tenant_id(self) -> str:
        """Get Microsoft Graph tenant ID."""
        return getattr(self._settings, 'tenant_id', '')
    
    def get_authority(self) -> str:
        """Get Microsoft Graph authority URL."""
        return getattr(self._settings, 'authority', 'https://login.microsoftonline.com/common')
    
    def get_scopes(self) -> List[str]:
        """Get Microsoft Graph API scopes."""
        return getattr(self._settings, 'scopes', [
            "https://graph.microsoft.com/Mail.Read",
            "https://graph.microsoft.com/Mail.ReadWrite",
            "https://graph.microsoft.com/User.Read"
        ])
    
    def get_redirect_uri(self) -> str:
        """Get OAuth redirect URI."""
        return getattr(self._settings, 'redirect_uri', 'http://localhost:5000/auth/callback')
    
    def get_graph_api_endpoint(self) -> str:
        """Get Graph API endpoint URL."""
        return getattr(self._settings, 'graph_api_endpoint', 'https://graph.microsoft.com/v1.0')
    
    def get_token_cache_file(self) -> str:
        """Get token cache file path."""
        return getattr(self._settings, 'token_cache_file', '.token_cache.json')
    
    # External API Configuration
    def get_external_api_url(self) -> str:
        """Get external API URL."""
        return getattr(self._settings, 'external_api_url', 'https://api.example.com/webhook')
    
    def get_external_api_key(self) -> str:
        """Get external API key."""
        return getattr(self._settings, 'external_api_key', '')
    
    # FastAPI Configuration
    def get_api_host(self) -> str:
        """Get API host."""
        return getattr(self._settings, 'api_host', '0.0.0.0')
    
    def get_api_port(self) -> int:
        """Get API port."""
        return getattr(self._settings, 'api_port', 5000)
    
    def get_api_reload(self) -> bool:
        """Get API reload setting."""
        return getattr(self._settings, 'api_reload', True)
    
    # JWT Configuration
    def get_secret_key(self) -> str:
        """Get JWT secret key."""
        return getattr(self._settings, 'secret_key', 'your-secret-key-change-this-in-production')
    
    def get_algorithm(self) -> str:
        """Get JWT algorithm."""
        return getattr(self._settings, 'algorithm', 'HS256')
    
    def get_access_token_expire_minutes(self) -> int:
        """Get access token expiration minutes."""
        return getattr(self._settings, 'access_token_expire_minutes', 30)
    
    # Logging Configuration
    def get_log_level(self) -> str:
        """Get logging level."""
        return getattr(self._settings, 'log_level', 'INFO')
    
    def get_log_format(self) -> str:
        """Get logging format."""
        return getattr(self._settings, 'log_format', '%(asctime)s - %(name)s - %(levelname)s - %(message)s')
    
    # Email Detection Configuration
    def get_email_check_interval(self) -> int:
        """Get email check interval in seconds."""
        return getattr(self._settings, 'email_check_interval', 300)
    
    def get_max_retry_count(self) -> int:
        """Get maximum retry count."""
        return getattr(self._settings, 'max_retry_count', 3)
    
    def get_retry_delay(self) -> int:
        """Get retry delay in seconds."""
        return getattr(self._settings, 'retry_delay', 60)
    
    # Optional Configuration
    def get_sentry_dsn(self) -> Optional[str]:
        """Get Sentry DSN for error monitoring."""
        return getattr(self._settings, 'sentry_dsn', None)
    
    def get_user_id(self) -> str:
        """Get default user ID."""
        return getattr(self._settings, 'user_id', 'default-user')
    
    # Validation and Management
    def validate_required_settings(self) -> bool:
        """Validate that all required settings are present."""
        # For development, we don't require all settings
        if self.is_development():
            return True
            
        required_fields = [
            "database_url",
            "client_id", 
            "client_secret",
            "tenant_id",
            "external_api_url",
            "external_api_key",
            "secret_key"
        ]
        
        missing_fields = []
        for field in required_fields:
            value = getattr(self._settings, field, None)
            if not value:
                missing_fields.append(field)
        
        if missing_fields:
            raise MissingConfigurationError(
                f"Missing required configuration fields: {', '.join(missing_fields)}"
            )
        
        # Additional validation for production
        if self.is_production():
            if len(self._settings.secret_key) < 32:
                raise InvalidConfigurationError(
                    "Secret key must be at least 32 characters in production",
                    "secret_key"
                )
        
        return True
    
    def get_all_settings(self) -> Dict[str, Any]:
        """Get all configuration settings (sensitive values masked)."""
        settings_dict = self._settings.model_dump()
        
        # Mask sensitive values using SecurityUtils
        sensitive_keys = [
            "client_secret",
            "external_api_key", 
            "secret_key",
            "sentry_dsn",
            "database_url"
        ]
        
        return SecurityUtils.mask_sensitive_dict(settings_dict, sensitive_keys)
    
    def reload_settings(self) -> None:
        """Reload configuration from source."""
        self._settings = self._create_settings()
        self._setup_logging()
        self._log_configuration_status()
        self._logger.info("Configuration reloaded successfully")


# Factory function for creating config adapter
def create_config_adapter(environment: Optional[str] = None) -> ConfigAdapter:
    """
    Factory function to create configuration adapter.
    
    Args:
        environment: Optional environment override
        
    Returns:
        ConfigAdapter instance
    """
    if environment:
        os.environ["ENVIRONMENT"] = environment
    
    return ConfigAdapter()
