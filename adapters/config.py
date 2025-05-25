"""Configuration adapter implementation."""

from enum import Enum
from typing import List, Optional, Any, Dict
from pydantic import Field, ConfigDict
from pydantic_settings import BaseSettings

from core.ports.config import ConfigPort


class Environment(str, Enum):
    """Environment enumeration."""
    DEVELOPMENT = "development"
    STAGING = "staging"
    PRODUCTION = "production"
    TEST = "test"


class ConfigAdapter(BaseSettings, ConfigPort):
    """Configuration adapter using Pydantic Settings."""
    
    # Environment Configuration
    environment: Environment = Field(Environment.DEVELOPMENT, description="Application environment", validation_alias="ENVIRONMENT")
    
    # Database Configuration
    database_url: str = Field(default="sqlite:///./graphapi.db", description="Database connection URL", validation_alias="DATABASE_URL")
    database_echo: bool = Field(False, description="Enable database query logging", validation_alias="DATABASE_ECHO")
    
    # Microsoft Graph API Configuration
    client_id: str = Field(default="", description="Microsoft client ID", validation_alias="CLIENT_ID")
    client_secret: str = Field(default="", description="Microsoft client secret", validation_alias="CLIENT_SECRET")
    tenant_id: str = Field(default="", description="Microsoft tenant ID", validation_alias="TENANT_ID")
    authority: str = Field(
        "https://login.microsoftonline.com/{tenant_id}",
        description="Microsoft authority URL"
    )
    scopes: List[str] = Field(
        default=[
            "https://graph.microsoft.com/Mail.Read",
            "https://graph.microsoft.com/Mail.Send"
        ],
        description="Microsoft Graph API scopes"
    )
    redirect_uri: str = Field(
        "http://localhost:5000/auth/callback",
        description="OAuth redirect URI"
    )
    graph_api_endpoint: str = Field(
        "https://graph.microsoft.com/v1.0",
        description="Microsoft Graph API endpoint"
    )
    token_cache_file: str = Field(
        ".token_cache.json",
        description="Token cache file path"
    )
    
    # External API Configuration
    external_api_url: str = Field(default="", description="External API base URL", validation_alias="EXTERNAL_API_URL")
    external_api_key: str = Field(default="", description="External API key", validation_alias="EXTERNAL_API_KEY")
    
    # FastAPI Configuration
    api_host: str = Field("0.0.0.0", description="API host", validation_alias="API_HOST")
    api_port: int = Field(5000, description="API port", validation_alias="API_PORT")
    api_reload: bool = Field(True, description="Enable API auto-reload", validation_alias="API_RELOAD")
    
    # JWT Configuration
    secret_key: str = Field(default="your-secret-key-change-this-in-production", description="JWT secret key", validation_alias="SECRET_KEY")
    algorithm: str = Field("HS256", description="JWT algorithm", validation_alias="ALGORITHM")
    access_token_expire_minutes: int = Field(30, description="Access token expiration minutes", validation_alias="ACCESS_TOKEN_EXPIRE_MINUTES")
    
    # Logging Configuration
    log_level: str = Field("INFO", description="Logging level")
    log_format: str = Field(
        "%(asctime)s - %(name)s - %(levelname)s - %(message)s",
        description="Log format string"
    )
    
    # Email Detection Configuration
    email_check_interval: int = Field(300, description="Email check interval in seconds")  # 5 minutes
    max_retry_count: int = Field(3, description="Maximum retry count")
    retry_delay: int = Field(60, description="Retry delay in seconds")  # 1 minute
    
    # Optional Configuration
    sentry_dsn: Optional[str] = Field(None, description="Sentry DSN for error tracking", validation_alias="SENTRY_DSN")
    user_id: str = Field("default-user", description="Default user ID", validation_alias="USER_ID")
    
    model_config = ConfigDict(
        env_file=".env",
        env_file_encoding="utf-8",
        case_sensitive=False,
        # Map field names to environment variable names
        env_prefix="",
        extra="ignore"
    )
    
    # ConfigPort interface implementation
    def get_environment(self) -> str:
        """Get current environment."""
        return self.environment.value
    
    def get_database_url(self) -> str:
        """Get database URL."""
        return self.database_url
    
    def get_database_echo(self) -> bool:
        """Get database echo setting."""
        return self.database_echo
    
    def get_client_id(self) -> str:
        """Get Microsoft client ID."""
        return self.client_id
    
    def get_client_secret(self) -> str:
        """Get Microsoft client secret."""
        return self.client_secret
    
    def get_tenant_id(self) -> str:
        """Get Microsoft tenant ID."""
        return self.tenant_id
    
    def get_authority(self) -> str:
        """Get Microsoft authority URL."""
        return self.authority.format(tenant_id=self.tenant_id)
    
    def get_scopes(self) -> List[str]:
        """Get Microsoft Graph API scopes."""
        return self.scopes
    
    def get_redirect_uri(self) -> str:
        """Get OAuth redirect URI."""
        return self.redirect_uri
    
    def get_graph_api_endpoint(self) -> str:
        """Get Microsoft Graph API endpoint."""
        return self.graph_api_endpoint
    
    def get_token_cache_file(self) -> str:
        """Get token cache file path."""
        return self.token_cache_file
    
    def get_external_api_url(self) -> str:
        """Get external API URL."""
        return self.external_api_url
    
    def get_external_api_key(self) -> str:
        """Get external API key."""
        return self.external_api_key
    
    def get_api_host(self) -> str:
        """Get API host."""
        return self.api_host
    
    def get_api_port(self) -> int:
        """Get API port."""
        return self.api_port
    
    def get_api_reload(self) -> bool:
        """Get API reload setting."""
        return self.api_reload
    
    def get_secret_key(self) -> str:
        """Get JWT secret key."""
        return self.secret_key
    
    def get_algorithm(self) -> str:
        """Get JWT algorithm."""
        return self.algorithm
    
    def get_access_token_expire_minutes(self) -> int:
        """Get access token expiration minutes."""
        return self.access_token_expire_minutes
    
    def get_log_level(self) -> str:
        """Get logging level."""
        return self.log_level
    
    def get_log_format(self) -> str:
        """Get log format."""
        return self.log_format
    
    def get_email_check_interval(self) -> int:
        """Get email check interval."""
        return self.email_check_interval
    
    def get_max_retry_count(self) -> int:
        """Get maximum retry count."""
        return self.max_retry_count
    
    def get_retry_delay(self) -> int:
        """Get retry delay."""
        return self.retry_delay
    
    def get_sentry_dsn(self) -> Optional[str]:
        """Get Sentry DSN."""
        return self.sentry_dsn
    
    def get_user_id(self) -> str:
        """Get default user ID."""
        return self.user_id
    
    def is_development(self) -> bool:
        """Check if running in development mode."""
        return self.environment == Environment.DEVELOPMENT
    
    def is_production(self) -> bool:
        """Check if running in production mode."""
        return self.environment == Environment.PRODUCTION
    
    def is_test(self) -> bool:
        """Check if running in test mode."""
        return self.environment == Environment.TEST
    
    def is_staging(self) -> bool:
        """Check if running in staging mode."""
        return self.environment == Environment.STAGING
    
    # Generic configuration methods
    def get(self, key: str, default: Any = None) -> Any:
        """Get configuration value by key."""
        return getattr(self, key, default)
    
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
            return value.lower() in ('true', '1', 'yes', 'on')
        return bool(value) if value is not None else default
    
    def get_list(self, key: str, default: List[Any] = None) -> List[Any]:
        """Get list configuration value."""
        if default is None:
            default = []
        value = self.get(key, default)
        if isinstance(value, list):
            return value
        if isinstance(value, str):
            # Try to parse comma-separated values
            return [item.strip() for item in value.split(',') if item.strip()]
        return default
    
    def get_dict(self, key: str, default: Dict[str, Any] = None) -> Dict[str, Any]:
        """Get dictionary configuration value."""
        if default is None:
            default = {}
        value = self.get(key, default)
        return value if isinstance(value, dict) else default
    
    def validate_required_settings(self) -> bool:
        """Validate that all required settings are present."""
        # In production, validate that critical settings are not empty
        if self.is_production():
            required_settings = [
                'client_id', 'client_secret', 'tenant_id',
                'external_api_url', 'external_api_key', 'secret_key'
            ]
            for setting in required_settings:
                value = getattr(self, setting, None)
                if not value or value == "":
                    raise ValueError(f"Required setting '{setting}' is missing or empty")
        return True
    
    def get_all_settings(self) -> Dict[str, Any]:
        """Get all configuration settings (sensitive values masked)."""
        settings = {}
        for field_name, field_info in self.model_fields.items():
            value = getattr(self, field_name)
            # Mask sensitive values
            if any(sensitive in field_name.lower() for sensitive in ['secret', 'key', 'password', 'token']):
                if value:
                    settings[field_name] = "***masked***"
                else:
                    settings[field_name] = value
            else:
                settings[field_name] = value
        return settings
    
    def reload_settings(self) -> None:
        """Reload configuration from source."""
        # For Pydantic Settings, we would need to recreate the instance
        # This is a placeholder implementation
        pass


# Factory function for dependency injection
def create_config_adapter() -> ConfigAdapter:
    """Create configuration adapter instance."""
    return ConfigAdapter()
