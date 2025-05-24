"""Configuration port interface for settings management."""

from abc import ABC, abstractmethod
from typing import Any, Dict, List, Optional
from enum import Enum


class Environment(str, Enum):
    """Environment enumeration."""
    DEVELOPMENT = "development"
    STAGING = "staging"
    PRODUCTION = "production"


class ConfigPort(ABC):
    """Configuration port interface."""
    
    @abstractmethod
    def get(self, key: str, default: Any = None) -> Any:
        """
        Get configuration value by key.
        
        Args:
            key: Configuration key
            default: Default value if key not found
            
        Returns:
            Configuration value
        """
        pass
    
    @abstractmethod
    def get_string(self, key: str, default: str = "") -> str:
        """Get string configuration value."""
        pass
    
    @abstractmethod
    def get_int(self, key: str, default: int = 0) -> int:
        """Get integer configuration value."""
        pass
    
    @abstractmethod
    def get_float(self, key: str, default: float = 0.0) -> float:
        """Get float configuration value."""
        pass
    
    @abstractmethod
    def get_bool(self, key: str, default: bool = False) -> bool:
        """Get boolean configuration value."""
        pass
    
    @abstractmethod
    def get_list(self, key: str, default: List[Any] = None) -> List[Any]:
        """Get list configuration value."""
        pass
    
    @abstractmethod
    def get_dict(self, key: str, default: Dict[str, Any] = None) -> Dict[str, Any]:
        """Get dictionary configuration value."""
        pass
    
    # Environment
    @abstractmethod
    def get_environment(self) -> Environment:
        """Get current environment."""
        pass
    
    @abstractmethod
    def is_development(self) -> bool:
        """Check if running in development mode."""
        pass
    
    @abstractmethod
    def is_staging(self) -> bool:
        """Check if running in staging mode."""
        pass
    
    @abstractmethod
    def is_production(self) -> bool:
        """Check if running in production mode."""
        pass
    
    # Database Configuration
    @abstractmethod
    def get_database_url(self) -> str:
        """Get database connection URL."""
        pass
    
    @abstractmethod
    def get_database_echo(self) -> bool:
        """Get database echo setting."""
        pass
    
    # Microsoft Graph API Configuration
    @abstractmethod
    def get_client_id(self) -> str:
        """Get Microsoft Graph client ID."""
        pass
    
    @abstractmethod
    def get_client_secret(self) -> str:
        """Get Microsoft Graph client secret."""
        pass
    
    @abstractmethod
    def get_tenant_id(self) -> str:
        """Get Microsoft Graph tenant ID."""
        pass
    
    @abstractmethod
    def get_authority(self) -> str:
        """Get Microsoft Graph authority URL."""
        pass
    
    @abstractmethod
    def get_scopes(self) -> List[str]:
        """Get Microsoft Graph API scopes."""
        pass
    
    @abstractmethod
    def get_redirect_uri(self) -> str:
        """Get OAuth redirect URI."""
        pass
    
    @abstractmethod
    def get_graph_api_endpoint(self) -> str:
        """Get Graph API endpoint URL."""
        pass
    
    @abstractmethod
    def get_token_cache_file(self) -> str:
        """Get token cache file path."""
        pass
    
    # External API Configuration
    @abstractmethod
    def get_external_api_url(self) -> str:
        """Get external API URL."""
        pass
    
    @abstractmethod
    def get_external_api_key(self) -> str:
        """Get external API key."""
        pass
    
    # FastAPI Configuration
    @abstractmethod
    def get_api_host(self) -> str:
        """Get API host."""
        pass
    
    @abstractmethod
    def get_api_port(self) -> int:
        """Get API port."""
        pass
    
    @abstractmethod
    def get_api_reload(self) -> bool:
        """Get API reload setting."""
        pass
    
    # JWT Configuration
    @abstractmethod
    def get_secret_key(self) -> str:
        """Get JWT secret key."""
        pass
    
    @abstractmethod
    def get_algorithm(self) -> str:
        """Get JWT algorithm."""
        pass
    
    @abstractmethod
    def get_access_token_expire_minutes(self) -> int:
        """Get access token expiration minutes."""
        pass
    
    # Logging Configuration
    @abstractmethod
    def get_log_level(self) -> str:
        """Get logging level."""
        pass
    
    @abstractmethod
    def get_log_format(self) -> str:
        """Get logging format."""
        pass
    
    # Email Detection Configuration
    @abstractmethod
    def get_email_check_interval(self) -> int:
        """Get email check interval in seconds."""
        pass
    
    @abstractmethod
    def get_max_retry_count(self) -> int:
        """Get maximum retry count."""
        pass
    
    @abstractmethod
    def get_retry_delay(self) -> int:
        """Get retry delay in seconds."""
        pass
    
    # Optional Configuration
    @abstractmethod
    def get_sentry_dsn(self) -> Optional[str]:
        """Get Sentry DSN for error monitoring."""
        pass
    
    @abstractmethod
    def get_user_id(self) -> str:
        """Get default user ID."""
        pass
    
    # Validation
    @abstractmethod
    def validate_required_settings(self) -> bool:
        """
        Validate that all required settings are present.
        
        Returns:
            True if all required settings are valid
            
        Raises:
            ConfigurationError: If required settings are missing or invalid
        """
        pass
    
    @abstractmethod
    def get_all_settings(self) -> Dict[str, Any]:
        """
        Get all configuration settings.
        
        Returns:
            Dictionary of all settings (sensitive values masked)
        """
        pass
    
    @abstractmethod
    def reload_settings(self) -> None:
        """Reload configuration from source."""
        pass


class ConfigurationError(Exception):
    """Configuration related error."""
    
    def __init__(self, message: str, setting_key: str = None):
        super().__init__(message)
        self.setting_key = setting_key


class MissingConfigurationError(ConfigurationError):
    """Missing required configuration error."""
    pass


class InvalidConfigurationError(ConfigurationError):
    """Invalid configuration value error."""
    pass
