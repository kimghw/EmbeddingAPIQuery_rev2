"""Repository implementations using SQLAlchemy."""

import logging
from datetime import datetime, timedelta
from typing import List, Optional, Dict, Any
from uuid import UUID

from sqlalchemy import and_, or_, desc, asc, func, text
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.orm import Session, selectinload
from sqlalchemy.future import select

from core.domain.user import User
from core.domain.account import Account
from core.domain.email import Email
from core.domain.transmission_record import TransmissionRecord
from core.ports.repository import (
    UserRepository,
    AccountRepository,
    EmailRepository,
    TransmissionRecordRepository,
    RepositoryError,
    EntityNotFoundError,
    DuplicateEntityError
)

from .models import (
    UserModel,
    AccountModel,
    EmailModel,
    TransmissionRecordModel,
    user_model_to_domain,
    domain_user_to_model,
    account_model_to_domain,
    domain_account_to_model,
    email_model_to_domain,
    domain_email_to_model,
    transmission_record_model_to_domain,
    domain_transmission_record_to_model
)


logger = logging.getLogger(__name__)


class SQLUserRepository(UserRepository):
    """SQLAlchemy implementation of UserRepository."""
    
    def __init__(self, session: AsyncSession):
        """
        Initialize repository with database session.
        
        Args:
            session: SQLAlchemy async session
        """
        self.session = session
    
    async def save(self, user: User) -> User:
        """Save user to database."""
        try:
            # Check if user already exists
            existing = await self.session.get(UserModel, user.id)
            
            if existing:
                # Update existing user
                existing.username = user.username
                existing.email = user.email
                existing.full_name = user.full_name
                existing.is_active = user.is_active
                existing.last_login = user.last_login
                existing.settings = user.settings
                existing.updated_at = datetime.utcnow()
                
                await self.session.flush()
                return user_model_to_domain(existing)
            else:
                # Create new user
                user_model = domain_user_to_model(user)
                self.session.add(user_model)
                await self.session.flush()
                return user_model_to_domain(user_model)
                
        except Exception as e:
            logger.error(f"Error saving user {user.id}: {e}")
            raise RepositoryError(f"Failed to save user: {e}")
    
    async def find_by_id(self, user_id: UUID) -> Optional[User]:
        """Find user by ID."""
        try:
            user_model = await self.session.get(UserModel, user_id)
            return user_model_to_domain(user_model) if user_model else None
        except Exception as e:
            logger.error(f"Error finding user by ID {user_id}: {e}")
            raise RepositoryError(f"Failed to find user: {e}")
    
    async def find_by_username(self, username: str) -> Optional[User]:
        """Find user by username."""
        try:
            stmt = select(UserModel).where(UserModel.username == username)
            result = await self.session.execute(stmt)
            user_model = result.scalar_one_or_none()
            return user_model_to_domain(user_model) if user_model else None
        except Exception as e:
            logger.error(f"Error finding user by username {username}: {e}")
            raise RepositoryError(f"Failed to find user: {e}")
    
    async def find_by_email(self, email: str) -> Optional[User]:
        """Find user by email."""
        try:
            stmt = select(UserModel).where(UserModel.email == email)
            result = await self.session.execute(stmt)
            user_model = result.scalar_one_or_none()
            return user_model_to_domain(user_model) if user_model else None
        except Exception as e:
            logger.error(f"Error finding user by email {email}: {e}")
            raise RepositoryError(f"Failed to find user: {e}")
    
    async def find_all(self, limit: int = 100, offset: int = 0) -> List[User]:
        """Find all users with pagination."""
        try:
            stmt = select(UserModel).offset(offset).limit(limit).order_by(UserModel.created_at.desc())
            result = await self.session.execute(stmt)
            user_models = result.scalars().all()
            return [user_model_to_domain(model) for model in user_models]
        except Exception as e:
            logger.error(f"Error finding all users: {e}")
            raise RepositoryError(f"Failed to find users: {e}")
    
    async def delete(self, user_id: UUID) -> bool:
        """Delete user by ID."""
        try:
            user_model = await self.session.get(UserModel, user_id)
            if user_model:
                await self.session.delete(user_model)
                await self.session.flush()
                return True
            return False
        except Exception as e:
            logger.error(f"Error deleting user {user_id}: {e}")
            raise RepositoryError(f"Failed to delete user: {e}")


class SQLAccountRepository(AccountRepository):
    """SQLAlchemy implementation of AccountRepository."""
    
    def __init__(self, session: AsyncSession):
        """
        Initialize repository with database session.
        
        Args:
            session: SQLAlchemy async session
        """
        self.session = session
    
    async def save(self, account: Account) -> Account:
        """Save account to database."""
        try:
            # Check if account already exists
            existing = await self.session.get(AccountModel, account.id)
            
            if existing:
                # Update existing account
                existing.email = account.email
                existing.display_name = account.display_name
                existing.tenant_id = account.tenant_id
                existing.access_token = account.access_token
                existing.refresh_token = account.refresh_token
                existing.token_expires_at = account.token_expires_at
                existing.is_active = account.is_active
                existing.is_authorized = account.is_authorized
                existing.last_sync_at = account.last_sync_at
                existing.delta_link = account.delta_link
                existing.sync_enabled = account.sync_enabled
                existing.settings = account.settings
                existing.updated_at = datetime.utcnow()
                
                await self.session.flush()
                return account_model_to_domain(existing)
            else:
                # Create new account
                account_model = domain_account_to_model(account)
                self.session.add(account_model)
                await self.session.flush()
                return account_model_to_domain(account_model)
                
        except Exception as e:
            logger.error(f"Error saving account {account.id}: {e}")
            raise RepositoryError(f"Failed to save account: {e}")
    
    async def find_by_id(self, account_id: UUID) -> Optional[Account]:
        """Find account by ID."""
        try:
            account_model = await self.session.get(AccountModel, account_id)
            return account_model_to_domain(account_model) if account_model else None
        except Exception as e:
            logger.error(f"Error finding account by ID {account_id}: {e}")
            raise RepositoryError(f"Failed to find account: {e}")
    
    async def find_by_user_id(self, user_id: UUID) -> List[Account]:
        """Find accounts by user ID."""
        try:
            stmt = select(AccountModel).where(AccountModel.user_id == user_id)
            result = await self.session.execute(stmt)
            account_models = result.scalars().all()
            return [account_model_to_domain(model) for model in account_models]
        except Exception as e:
            logger.error(f"Error finding accounts by user ID {user_id}: {e}")
            raise RepositoryError(f"Failed to find accounts: {e}")
    
    async def find_by_email(self, email: str) -> Optional[Account]:
        """Find account by email."""
        try:
            stmt = select(AccountModel).where(AccountModel.email == email)
            result = await self.session.execute(stmt)
            account_model = result.scalar_one_or_none()
            return account_model_to_domain(account_model) if account_model else None
        except Exception as e:
            logger.error(f"Error finding account by email {email}: {e}")
            raise RepositoryError(f"Failed to find account: {e}")
    
    async def find_active_accounts(self) -> List[Account]:
        """Find all active accounts."""
        try:
            stmt = select(AccountModel).where(
                and_(AccountModel.is_active == True, AccountModel.is_authorized == True)
            )
            result = await self.session.execute(stmt)
            account_models = result.scalars().all()
            return [account_model_to_domain(model) for model in account_models]
        except Exception as e:
            logger.error(f"Error finding active accounts: {e}")
            raise RepositoryError(f"Failed to find active accounts: {e}")
    
    async def update_token_info(self, account_id: UUID, token_info: Dict[str, Any]) -> bool:
        """Update account token information."""
        try:
            account_model = await self.session.get(AccountModel, account_id)
            if not account_model:
                return False
            
            account_model.access_token = token_info.get("access_token")
            account_model.refresh_token = token_info.get("refresh_token")
            account_model.token_expires_at = token_info.get("expires_at")
            account_model.is_authorized = True
            account_model.updated_at = datetime.utcnow()
            
            await self.session.flush()
            return True
        except Exception as e:
            logger.error(f"Error updating token info for account {account_id}: {e}")
            raise RepositoryError(f"Failed to update token info: {e}")
    
    async def update_sync_info(self, account_id: UUID, delta_link: str) -> bool:
        """Update account sync information."""
        try:
            account_model = await self.session.get(AccountModel, account_id)
            if not account_model:
                return False
            
            account_model.delta_link = delta_link
            account_model.last_sync_at = datetime.utcnow()
            account_model.updated_at = datetime.utcnow()
            
            await self.session.flush()
            return True
        except Exception as e:
            logger.error(f"Error updating sync info for account {account_id}: {e}")
            raise RepositoryError(f"Failed to update sync info: {e}")
    
    async def delete(self, account_id: UUID) -> bool:
        """Delete account by ID."""
        try:
            account_model = await self.session.get(AccountModel, account_id)
            if account_model:
                await self.session.delete(account_model)
                await self.session.flush()
                return True
            return False
        except Exception as e:
            logger.error(f"Error deleting account {account_id}: {e}")
            raise RepositoryError(f"Failed to delete account: {e}")


class SQLEmailRepository(EmailRepository):
    """SQLAlchemy implementation of EmailRepository."""
    
    def __init__(self, session: AsyncSession):
        """
        Initialize repository with database session.
        
        Args:
            session: SQLAlchemy async session
        """
        self.session = session
    
    async def save(self, email: Email) -> Email:
        """Save email to database."""
        try:
            # Check if email already exists
            existing = await self.session.get(EmailModel, email.id)
            
            if existing:
                # Update existing email
                existing.subject = email.subject
                existing.body = email.body
                existing.body_preview = email.body_preview
                existing.sender = email.sender
                existing.recipients = email.recipients
                existing.cc_recipients = email.cc_recipients
                existing.bcc_recipients = email.bcc_recipients
                existing.received_at = email.received_at
                existing.sent_at = email.sent_at
                existing.folder = email.folder
                existing.importance = email.importance
                existing.priority = email.priority
                existing.is_read = email.is_read
                existing.has_attachments = email.has_attachments
                existing.attachments = email.attachments
                existing.processing_status = email.processing_status
                existing.processed_at = email.processed_at
                existing.metadata = email.metadata
                existing.updated_at = datetime.utcnow()
                
                await self.session.flush()
                return email_model_to_domain(existing)
            else:
                # Create new email
                email_model = domain_email_to_model(email)
                self.session.add(email_model)
                await self.session.flush()
                return email_model_to_domain(email_model)
                
        except Exception as e:
            logger.error(f"Error saving email {email.id}: {e}")
            raise RepositoryError(f"Failed to save email: {e}")
    
    async def bulk_save(self, emails: List[Email]) -> List[Email]:
        """Bulk save emails to database."""
        try:
            saved_emails = []
            for email in emails:
                saved_email = await self.save(email)
                saved_emails.append(saved_email)
            return saved_emails
        except Exception as e:
            logger.error(f"Error bulk saving emails: {e}")
            raise RepositoryError(f"Failed to bulk save emails: {e}")
    
    async def find_by_id(self, email_id: UUID) -> Optional[Email]:
        """Find email by ID."""
        try:
            email_model = await self.session.get(EmailModel, email_id)
            return email_model_to_domain(email_model) if email_model else None
        except Exception as e:
            logger.error(f"Error finding email by ID {email_id}: {e}")
            raise RepositoryError(f"Failed to find email: {e}")
    
    async def find_by_message_id(self, message_id: str) -> Optional[Email]:
        """Find email by message ID."""
        try:
            stmt = select(EmailModel).where(EmailModel.message_id == message_id)
            result = await self.session.execute(stmt)
            email_model = result.scalar_one_or_none()
            return email_model_to_domain(email_model) if email_model else None
        except Exception as e:
            logger.error(f"Error finding email by message ID {message_id}: {e}")
            raise RepositoryError(f"Failed to find email: {e}")
    
    async def find_by_account_id(self, account_id: UUID, limit: int = 100, offset: int = 0) -> List[Email]:
        """Find emails by account ID."""
        try:
            stmt = (
                select(EmailModel)
                .where(EmailModel.account_id == account_id)
                .order_by(EmailModel.received_at.desc())
                .offset(offset)
                .limit(limit)
            )
            result = await self.session.execute(stmt)
            email_models = result.scalars().all()
            return [email_model_to_domain(model) for model in email_models]
        except Exception as e:
            logger.error(f"Error finding emails by account ID {account_id}: {e}")
            raise RepositoryError(f"Failed to find emails: {e}")
    
    async def find_by_processing_status(self, status: str, limit: int = 100) -> List[Email]:
        """Find emails by processing status."""
        try:
            stmt = (
                select(EmailModel)
                .where(EmailModel.processing_status == status)
                .order_by(EmailModel.created_at.asc())
                .limit(limit)
            )
            result = await self.session.execute(stmt)
            email_models = result.scalars().all()
            return [email_model_to_domain(model) for model in email_models]
        except Exception as e:
            logger.error(f"Error finding emails by status {status}: {e}")
            raise RepositoryError(f"Failed to find emails: {e}")
    
    async def update_processing_status(self, email_id: UUID, status: str) -> bool:
        """Update email processing status."""
        try:
            email_model = await self.session.get(EmailModel, email_id)
            if not email_model:
                return False
            
            email_model.processing_status = status
            if status in ["transmitted", "completed"]:
                email_model.processed_at = datetime.utcnow()
            email_model.updated_at = datetime.utcnow()
            
            await self.session.flush()
            return True
        except Exception as e:
            logger.error(f"Error updating processing status for email {email_id}: {e}")
            raise RepositoryError(f"Failed to update processing status: {e}")
    
    async def delete_old_emails(self, days: int) -> int:
        """Delete emails older than specified days."""
        try:
            cutoff_date = datetime.utcnow() - timedelta(days=days)
            stmt = select(EmailModel).where(EmailModel.created_at < cutoff_date)
            result = await self.session.execute(stmt)
            emails_to_delete = result.scalars().all()
            
            count = len(emails_to_delete)
            for email in emails_to_delete:
                await self.session.delete(email)
            
            await self.session.flush()
            return count
        except Exception as e:
            logger.error(f"Error deleting old emails: {e}")
            raise RepositoryError(f"Failed to delete old emails: {e}")
    
    async def delete(self, email_id: UUID) -> bool:
        """Delete email by ID."""
        try:
            email_model = await self.session.get(EmailModel, email_id)
            if email_model:
                await self.session.delete(email_model)
                await self.session.flush()
                return True
            return False
        except Exception as e:
            logger.error(f"Error deleting email {email_id}: {e}")
            raise RepositoryError(f"Failed to delete email: {e}")


class SQLTransmissionRecordRepository(TransmissionRecordRepository):
    """SQLAlchemy implementation of TransmissionRecordRepository."""
    
    def __init__(self, session: AsyncSession):
        """
        Initialize repository with database session.
        
        Args:
            session: SQLAlchemy async session
        """
        self.session = session
    
    async def save(self, record: TransmissionRecord) -> TransmissionRecord:
        """Save transmission record to database."""
        try:
            # Check if record already exists
            existing = await self.session.get(TransmissionRecordModel, record.id)
            
            if existing:
                # Update existing record
                existing.endpoint = record.endpoint
                existing.method = record.method
                existing.status = record.status
                existing.priority = record.priority
                existing.retry_count = record.retry_count
                existing.max_retries = record.max_retries
                existing.next_retry_at = record.next_retry_at
                existing.response_status_code = record.response_status_code
                existing.response_data = record.response_data
                existing.error_message = record.error_message
                existing.started_at = record.started_at
                existing.completed_at = record.completed_at
                existing.processing_time_ms = record.processing_time_ms
                existing.metadata = record.metadata
                existing.updated_at = datetime.utcnow()
                
                await self.session.flush()
                return transmission_record_model_to_domain(existing)
            else:
                # Create new record
                record_model = domain_transmission_record_to_model(record)
                self.session.add(record_model)
                await self.session.flush()
                return transmission_record_model_to_domain(record_model)
                
        except Exception as e:
            logger.error(f"Error saving transmission record {record.id}: {e}")
            raise RepositoryError(f"Failed to save transmission record: {e}")
    
    async def find_by_id(self, record_id: UUID) -> Optional[TransmissionRecord]:
        """Find transmission record by ID."""
        try:
            record_model = await self.session.get(TransmissionRecordModel, record_id)
            return transmission_record_model_to_domain(record_model) if record_model else None
        except Exception as e:
            logger.error(f"Error finding transmission record by ID {record_id}: {e}")
            raise RepositoryError(f"Failed to find transmission record: {e}")
    
    async def find_by_email_id(self, email_id: UUID) -> List[TransmissionRecord]:
        """Find transmission records by email ID."""
        try:
            stmt = (
                select(TransmissionRecordModel)
                .where(TransmissionRecordModel.email_id == email_id)
                .order_by(TransmissionRecordModel.created_at.desc())
            )
            result = await self.session.execute(stmt)
            record_models = result.scalars().all()
            return [transmission_record_model_to_domain(model) for model in record_models]
        except Exception as e:
            logger.error(f"Error finding transmission records by email ID {email_id}: {e}")
            raise RepositoryError(f"Failed to find transmission records: {e}")
    
    async def find_by_status(self, status: str, limit: int = 100) -> List[TransmissionRecord]:
        """Find transmission records by status."""
        try:
            stmt = (
                select(TransmissionRecordModel)
                .where(TransmissionRecordModel.status == status)
                .order_by(TransmissionRecordModel.created_at.asc())
                .limit(limit)
            )
            result = await self.session.execute(stmt)
            record_models = result.scalars().all()
            return [transmission_record_model_to_domain(model) for model in record_models]
        except Exception as e:
            logger.error(f"Error finding transmission records by status {status}: {e}")
            raise RepositoryError(f"Failed to find transmission records: {e}")
    
    async def find_pending_records(self, limit: int = 100) -> List[TransmissionRecord]:
        """Find pending transmission records."""
        try:
            stmt = (
                select(TransmissionRecordModel)
                .where(TransmissionRecordModel.status == "pending")
                .order_by(TransmissionRecordModel.priority.asc(), TransmissionRecordModel.created_at.asc())
                .limit(limit)
            )
            result = await self.session.execute(stmt)
            record_models = result.scalars().all()
            return [transmission_record_model_to_domain(model) for model in record_models]
        except Exception as e:
            logger.error(f"Error finding pending transmission records: {e}")
            raise RepositoryError(f"Failed to find pending transmission records: {e}")
    
    async def find_retry_ready_records(self, limit: int = 100) -> List[TransmissionRecord]:
        """Find records ready for retry."""
        try:
            now = datetime.utcnow()
            stmt = (
                select(TransmissionRecordModel)
                .where(
                    and_(
                        TransmissionRecordModel.status == "retry",
                        TransmissionRecordModel.next_retry_at <= now
                    )
                )
                .order_by(TransmissionRecordModel.priority.asc(), TransmissionRecordModel.next_retry_at.asc())
                .limit(limit)
            )
            result = await self.session.execute(stmt)
            record_models = result.scalars().all()
            return [transmission_record_model_to_domain(model) for model in record_models]
        except Exception as e:
            logger.error(f"Error finding retry ready transmission records: {e}")
            raise RepositoryError(f"Failed to find retry ready transmission records: {e}")
    
    async def update_status(self, record_id: UUID, status: str, error_message: Optional[str] = None) -> bool:
        """Update transmission record status."""
        try:
            record_model = await self.session.get(TransmissionRecordModel, record_id)
            if not record_model:
                return False
            
            record_model.status = status
            if error_message:
                record_model.error_message = error_message
            
            if status in ["success", "failed"]:
                record_model.completed_at = datetime.utcnow()
            elif status == "processing":
                record_model.started_at = datetime.utcnow()
            
            record_model.updated_at = datetime.utcnow()
            
            await self.session.flush()
            return True
        except Exception as e:
            logger.error(f"Error updating status for transmission record {record_id}: {e}")
            raise RepositoryError(f"Failed to update transmission record status: {e}")
    
    async def increment_retry_count(self, record_id: UUID) -> bool:
        """Increment retry count for transmission record."""
        try:
            record_model = await self.session.get(TransmissionRecordModel, record_id)
            if not record_model:
                return False
            
            record_model.retry_count += 1
            record_model.updated_at = datetime.utcnow()
            
            await self.session.flush()
            return True
        except Exception as e:
            logger.error(f"Error incrementing retry count for transmission record {record_id}: {e}")
            raise RepositoryError(f"Failed to increment retry count: {e}")
    
    async def cleanup_old_records(self, days: int) -> int:
        """Delete transmission records older than specified days."""
        try:
            cutoff_date = datetime.utcnow() - timedelta(days=days)
            stmt = select(TransmissionRecordModel).where(TransmissionRecordModel.created_at < cutoff_date)
            result = await self.session.execute(stmt)
            records_to_delete = result.scalars().all()
            
            count = len(records_to_delete)
            for record in records_to_delete:
                await self.session.delete(record)
            
            await self.session.flush()
            return count
        except Exception as e:
            logger.error(f"Error cleaning up old transmission records: {e}")
            raise RepositoryError(f"Failed to cleanup old transmission records: {e}")
    
    async def find_all(self, limit: int = 100, offset: int = 0) -> List[TransmissionRecord]:
        """Find all transmission records with pagination."""
        try:
            stmt = (
                select(TransmissionRecordModel)
                .order_by(TransmissionRecordModel.created_at.desc())
                .offset(offset)
                .limit(limit)
            )
            result = await self.session.execute(stmt)
            record_models = result.scalars().all()
            return [transmission_record_model_to_domain(model) for model in record_models]
        except Exception as e:
            logger.error(f"Error finding all transmission records: {e}")
            raise RepositoryError(f"Failed to find transmission records: {e}")
    
    async def delete(self, record_id: UUID) -> bool:
        """Delete transmission record by ID."""
        try:
            record_model = await self.session.get(TransmissionRecordModel, record_id)
            if record_model:
                await self.session.delete(record_model)
                await self.session.flush()
                return True
            return False
        except Exception as e:
            logger.error(f"Error deleting transmission record {record_id}: {e}")
            raise RepositoryError(f"Failed to delete transmission record: {e}")
