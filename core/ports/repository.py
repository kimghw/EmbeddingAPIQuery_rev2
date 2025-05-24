"""Repository interfaces for data persistence."""

from abc import ABC, abstractmethod
from typing import List, Optional, Dict, Any
from uuid import UUID

from ..domain.user import User
from ..domain.account import Account
from ..domain.email import Email
from ..domain.transmission_record import TransmissionRecord


class RepositoryError(Exception):
    """Base exception for repository operations."""
    pass


class EntityNotFoundError(RepositoryError):
    """Exception raised when entity is not found."""
    pass


class DuplicateEntityError(RepositoryError):
    """Exception raised when trying to create duplicate entity."""
    pass


class DatabaseConnectionError(RepositoryError):
    """Exception raised when database connection fails."""
    pass


class BaseRepository(ABC):
    """Base repository interface."""
    
    @abstractmethod
    async def save(self, entity: Any) -> Any:
        """Save an entity."""
        pass
    
    @abstractmethod
    async def find_by_id(self, entity_id: UUID) -> Optional[Any]:
        """Find entity by ID."""
        pass
    
    @abstractmethod
    async def find_all(self, skip: int = 0, limit: int = 100) -> List[Any]:
        """Find all entities with pagination."""
        pass
    
    @abstractmethod
    async def update(self, entity: Any) -> Any:
        """Update an entity."""
        pass
    
    @abstractmethod
    async def delete(self, entity_id: UUID) -> bool:
        """Delete an entity by ID."""
        pass


class UserRepository(BaseRepository):
    """User repository interface."""
    
    @abstractmethod
    async def save(self, user: User) -> User:
        """Save a user."""
        pass
    
    @abstractmethod
    async def find_by_id(self, user_id: UUID) -> Optional[User]:
        """Find user by ID."""
        pass
    
    @abstractmethod
    async def find_by_username(self, username: str) -> Optional[User]:
        """Find user by username."""
        pass
    
    @abstractmethod
    async def find_by_email(self, email: str) -> Optional[User]:
        """Find user by email."""
        pass
    
    @abstractmethod
    async def find_all(self, skip: int = 0, limit: int = 100) -> List[User]:
        """Find all users with pagination."""
        pass
    
    @abstractmethod
    async def update(self, user: User) -> User:
        """Update a user."""
        pass
    
    @abstractmethod
    async def delete(self, user_id: UUID) -> bool:
        """Delete a user by ID."""
        pass
    
    @abstractmethod
    async def exists_by_username(self, username: str) -> bool:
        """Check if user exists by username."""
        pass
    
    @abstractmethod
    async def exists_by_email(self, email: str) -> bool:
        """Check if user exists by email."""
        pass


class AccountRepository(BaseRepository):
    """Account repository interface."""
    
    @abstractmethod
    async def save(self, account: Account) -> Account:
        """Save an account."""
        pass
    
    @abstractmethod
    async def find_by_id(self, account_id: UUID) -> Optional[Account]:
        """Find account by ID."""
        pass
    
    @abstractmethod
    async def find_by_user_id(self, user_id: UUID) -> List[Account]:
        """Find accounts by user ID."""
        pass
    
    @abstractmethod
    async def find_by_email(self, email: str) -> Optional[Account]:
        """Find account by email address."""
        pass
    
    @abstractmethod
    async def find_active_accounts(self) -> List[Account]:
        """Find all active accounts."""
        pass
    
    @abstractmethod
    async def find_all(self, skip: int = 0, limit: int = 100) -> List[Account]:
        """Find all accounts with pagination."""
        pass
    
    @abstractmethod
    async def update(self, account: Account) -> Account:
        """Update an account."""
        pass
    
    @abstractmethod
    async def delete(self, account_id: UUID) -> bool:
        """Delete an account by ID."""
        pass
    
    @abstractmethod
    async def update_token_info(self, account_id: UUID, token_info: Dict[str, Any]) -> bool:
        """Update account token information."""
        pass


class EmailRepository(BaseRepository):
    """Email repository interface."""
    
    @abstractmethod
    async def save(self, email: Email) -> Email:
        """Save an email."""
        pass
    
    @abstractmethod
    async def find_by_id(self, email_id: UUID) -> Optional[Email]:
        """Find email by ID."""
        pass
    
    @abstractmethod
    async def find_by_message_id(self, message_id: str) -> Optional[Email]:
        """Find email by message ID."""
        pass
    
    @abstractmethod
    async def find_by_account_id(self, account_id: UUID, skip: int = 0, limit: int = 100) -> List[Email]:
        """Find emails by account ID with pagination."""
        pass
    
    @abstractmethod
    async def find_recent_emails(self, account_id: UUID, hours: int = 24) -> List[Email]:
        """Find recent emails within specified hours."""
        pass
    
    @abstractmethod
    async def find_by_status(self, status: str, skip: int = 0, limit: int = 100) -> List[Email]:
        """Find emails by processing status."""
        pass
    
    @abstractmethod
    async def find_all(self, skip: int = 0, limit: int = 100) -> List[Email]:
        """Find all emails with pagination."""
        pass
    
    @abstractmethod
    async def update(self, email: Email) -> Email:
        """Update an email."""
        pass
    
    @abstractmethod
    async def delete(self, email_id: UUID) -> bool:
        """Delete an email by ID."""
        pass
    
    @abstractmethod
    async def bulk_save(self, emails: List[Email]) -> List[Email]:
        """Save multiple emails in bulk."""
        pass
    
    @abstractmethod
    async def update_processing_status(self, email_id: UUID, status: str) -> bool:
        """Update email processing status."""
        pass


class TransmissionRecordRepository(BaseRepository):
    """Transmission record repository interface."""
    
    @abstractmethod
    async def save(self, record: TransmissionRecord) -> TransmissionRecord:
        """Save a transmission record."""
        pass
    
    @abstractmethod
    async def find_by_id(self, record_id: UUID) -> Optional[TransmissionRecord]:
        """Find transmission record by ID."""
        pass
    
    @abstractmethod
    async def find_by_email_id(self, email_id: UUID) -> List[TransmissionRecord]:
        """Find transmission records by email ID."""
        pass
    
    @abstractmethod
    async def find_by_status(self, status: str, skip: int = 0, limit: int = 100) -> List[TransmissionRecord]:
        """Find transmission records by status."""
        pass
    
    @abstractmethod
    async def find_failed_records(self, max_retry_count: int = 3) -> List[TransmissionRecord]:
        """Find failed transmission records that need retry."""
        pass
    
    @abstractmethod
    async def find_pending_records(self, limit: int = 100) -> List[TransmissionRecord]:
        """Find pending transmission records."""
        pass
    
    @abstractmethod
    async def find_all(self, skip: int = 0, limit: int = 100) -> List[TransmissionRecord]:
        """Find all transmission records with pagination."""
        pass
    
    @abstractmethod
    async def update(self, record: TransmissionRecord) -> TransmissionRecord:
        """Update a transmission record."""
        pass
    
    @abstractmethod
    async def delete(self, record_id: UUID) -> bool:
        """Delete a transmission record by ID."""
        pass
    
    @abstractmethod
    async def update_status(self, record_id: UUID, status: str, error_message: Optional[str] = None) -> bool:
        """Update transmission record status."""
        pass
    
    @abstractmethod
    async def increment_retry_count(self, record_id: UUID) -> bool:
        """Increment retry count for a transmission record."""
        pass
    
    @abstractmethod
    async def cleanup_old_records(self, days: int = 30) -> int:
        """Clean up old transmission records."""
        pass
