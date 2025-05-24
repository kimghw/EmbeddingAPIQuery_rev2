"""SQLAlchemy models for database entities."""

from datetime import datetime
from typing import List, Optional, Dict, Any
from uuid import UUID, uuid4
import json

from sqlalchemy import (
    Column, String, DateTime, Boolean, Integer, Text, 
    ForeignKey, JSON, Index, UniqueConstraint, TypeDecorator
)
from sqlalchemy.orm import declarative_base, relationship
from sqlalchemy.sql import func

# Create base class
Base = declarative_base()


class GUID(TypeDecorator):
    """Platform-independent GUID type.
    
    Uses PostgreSQL's UUID type, otherwise uses CHAR(36), storing as stringified hex values.
    """
    impl = String
    cache_ok = True

    def load_dialect_impl(self, dialect):
        if dialect.name == 'postgresql':
            return dialect.type_descriptor(dialect.UUID())
        else:
            return dialect.type_descriptor(String(36))

    def process_bind_param(self, value, dialect):
        if value is None:
            return value
        elif dialect.name == 'postgresql':
            return str(value)
        else:
            if not isinstance(value, UUID):
                return str(UUID(value))
            else:
                return str(value)

    def process_result_value(self, value, dialect):
        if value is None:
            return value
        else:
            if not isinstance(value, UUID):
                return UUID(value)
            return value


class UserModel(Base):
    """SQLAlchemy model for User entity."""
    
    __tablename__ = "users"
    
    # Primary key
    id = Column(GUID(), primary_key=True, default=uuid4)
    
    # Basic fields
    username = Column(String(255), unique=True, nullable=False, index=True)
    email = Column(String(255), unique=True, nullable=False, index=True)
    full_name = Column(String(255), nullable=True)
    
    # Status and metadata
    is_active = Column(Boolean, default=True, nullable=False)
    created_at = Column(DateTime(timezone=True), server_default=func.now(), nullable=False)
    updated_at = Column(DateTime(timezone=True), server_default=func.now(), onupdate=func.now(), nullable=False)
    last_login = Column(DateTime(timezone=True), nullable=True)
    
    # Settings (JSON field)
    settings = Column(JSON, nullable=True)
    
    # Relationships
    accounts = relationship("AccountModel", back_populates="user", cascade="all, delete-orphan")
    
    # Indexes
    __table_args__ = (
        Index('idx_users_username', 'username'),
        Index('idx_users_email', 'email'),
        Index('idx_users_active', 'is_active'),
        Index('idx_users_created_at', 'created_at'),
    )
    
    def __repr__(self):
        return f"<UserModel(id={self.id}, username='{self.username}', email='{self.email}')>"


class AccountModel(Base):
    """SQLAlchemy model for Account entity."""
    
    __tablename__ = "accounts"
    
    # Primary key
    id = Column(GUID(), primary_key=True, default=uuid4)
    
    # Foreign key
    user_id = Column(GUID(), ForeignKey("users.id"), nullable=False)
    
    # Account identification
    email = Column(String(255), nullable=False, index=True)
    display_name = Column(String(255), nullable=True)
    tenant_id = Column(String(255), nullable=True)
    
    # OAuth tokens
    access_token = Column(Text, nullable=True)
    refresh_token = Column(Text, nullable=True)
    token_expires_at = Column(DateTime(timezone=True), nullable=True)
    
    # Account status
    is_active = Column(Boolean, default=True, nullable=False)
    is_authorized = Column(Boolean, default=False, nullable=False)
    
    # Sync settings
    last_sync_at = Column(DateTime(timezone=True), nullable=True)
    delta_link = Column(Text, nullable=True)
    sync_enabled = Column(Boolean, default=True, nullable=False)
    
    # Metadata
    created_at = Column(DateTime(timezone=True), server_default=func.now(), nullable=False)
    updated_at = Column(DateTime(timezone=True), server_default=func.now(), onupdate=func.now(), nullable=False)
    
    # Additional settings (JSON field)
    settings = Column(JSON, nullable=True)
    
    # Relationships
    user = relationship("UserModel", back_populates="accounts")
    emails = relationship("EmailModel", back_populates="account", cascade="all, delete-orphan")
    
    # Constraints and indexes
    __table_args__ = (
        UniqueConstraint('user_id', 'email', name='uq_user_account_email'),
        Index('idx_accounts_user_id', 'user_id'),
        Index('idx_accounts_email', 'email'),
        Index('idx_accounts_active', 'is_active'),
        Index('idx_accounts_authorized', 'is_authorized'),
        Index('idx_accounts_sync_enabled', 'sync_enabled'),
        Index('idx_accounts_last_sync', 'last_sync_at'),
    )
    
    def __repr__(self):
        return f"<AccountModel(id={self.id}, email='{self.email}', is_active={self.is_active})>"


class EmailModel(Base):
    """SQLAlchemy model for Email entity."""
    
    __tablename__ = "emails"
    
    # Primary key
    id = Column(GUID(), primary_key=True, default=uuid4)
    
    # Foreign key
    account_id = Column(GUID(), ForeignKey("accounts.id"), nullable=False)
    
    # Email identification
    message_id = Column(String(255), nullable=False, unique=True, index=True)
    conversation_id = Column(String(255), nullable=True, index=True)
    
    # Email content
    subject = Column(Text, nullable=True)
    body = Column(Text, nullable=True)
    body_preview = Column(Text, nullable=True)
    
    # Email metadata
    sender = Column(String(255), nullable=True, index=True)
    recipients = Column(JSON, nullable=True)  # List of recipient emails
    cc_recipients = Column(JSON, nullable=True)
    bcc_recipients = Column(JSON, nullable=True)
    
    # Timestamps
    received_at = Column(DateTime(timezone=True), nullable=True, index=True)
    sent_at = Column(DateTime(timezone=True), nullable=True)
    
    # Email properties
    folder = Column(String(100), nullable=False, default="inbox", index=True)
    importance = Column(String(20), nullable=True)
    priority = Column(String(20), nullable=True)
    is_read = Column(Boolean, default=False, nullable=False)
    has_attachments = Column(Boolean, default=False, nullable=False)
    
    # Attachments (JSON field)
    attachments = Column(JSON, nullable=True)
    
    # Processing status
    processing_status = Column(String(50), default="pending", nullable=False, index=True)
    processed_at = Column(DateTime(timezone=True), nullable=True)
    
    # Metadata
    created_at = Column(DateTime(timezone=True), server_default=func.now(), nullable=False)
    updated_at = Column(DateTime(timezone=True), server_default=func.now(), onupdate=func.now(), nullable=False)
    
    # Additional metadata (JSON field) - renamed to avoid SQLAlchemy reserved word
    email_metadata = Column(JSON, nullable=True)
    
    # Relationships
    account = relationship("AccountModel", back_populates="emails")
    transmission_records = relationship("TransmissionRecordModel", back_populates="email", cascade="all, delete-orphan")
    
    # Indexes
    __table_args__ = (
        Index('idx_emails_account_id', 'account_id'),
        Index('idx_emails_message_id', 'message_id'),
        Index('idx_emails_conversation_id', 'conversation_id'),
        Index('idx_emails_sender', 'sender'),
        Index('idx_emails_received_at', 'received_at'),
        Index('idx_emails_folder', 'folder'),
        Index('idx_emails_processing_status', 'processing_status'),
        Index('idx_emails_created_at', 'created_at'),
        Index('idx_emails_account_received', 'account_id', 'received_at'),
        Index('idx_emails_account_status', 'account_id', 'processing_status'),
    )
    
    def __repr__(self):
        return f"<EmailModel(id={self.id}, message_id='{self.message_id}', subject='{self.subject[:50] if self.subject else ''}...')>"


class TransmissionRecordModel(Base):
    """SQLAlchemy model for TransmissionRecord entity."""
    
    __tablename__ = "transmission_records"
    
    # Primary key
    id = Column(GUID(), primary_key=True, default=uuid4)
    
    # Foreign key
    email_id = Column(GUID(), ForeignKey("emails.id"), nullable=False)
    
    # Transmission details
    endpoint = Column(String(500), nullable=True)
    method = Column(String(10), default="POST", nullable=False)
    
    # Status and priority
    status = Column(String(50), default="pending", nullable=False, index=True)
    priority = Column(String(20), default="normal", nullable=False, index=True)
    
    # Retry management
    retry_count = Column(Integer, default=0, nullable=False)
    max_retries = Column(Integer, default=3, nullable=False)
    next_retry_at = Column(DateTime(timezone=True), nullable=True, index=True)
    
    # Response data
    response_status_code = Column(Integer, nullable=True)
    response_data = Column(JSON, nullable=True)
    error_message = Column(Text, nullable=True)
    
    # Timing
    started_at = Column(DateTime(timezone=True), nullable=True)
    completed_at = Column(DateTime(timezone=True), nullable=True)
    processing_time_ms = Column(Integer, nullable=True)
    
    # Metadata
    created_at = Column(DateTime(timezone=True), server_default=func.now(), nullable=False)
    updated_at = Column(DateTime(timezone=True), server_default=func.now(), onupdate=func.now(), nullable=False)
    
    # Additional metadata (JSON field) - renamed to avoid SQLAlchemy reserved word
    record_metadata = Column(JSON, nullable=True)
    
    # Relationships
    email = relationship("EmailModel", back_populates="transmission_records")
    
    # Indexes
    __table_args__ = (
        Index('idx_transmission_email_id', 'email_id'),
        Index('idx_transmission_status', 'status'),
        Index('idx_transmission_priority', 'priority'),
        Index('idx_transmission_retry_at', 'next_retry_at'),
        Index('idx_transmission_created_at', 'created_at'),
        Index('idx_transmission_status_priority', 'status', 'priority'),
        Index('idx_transmission_email_status', 'email_id', 'status'),
    )
    
    def __repr__(self):
        return f"<TransmissionRecordModel(id={self.id}, email_id={self.email_id}, status='{self.status}')>"


# Utility functions for model conversion
def user_model_to_domain(user_model: UserModel):
    """Convert UserModel to domain User entity."""
    from core.domain.user import User, UserStatus
    
    # Convert is_active to status
    status = UserStatus.ACTIVE if user_model.is_active else UserStatus.INACTIVE
    
    return User(
        id=str(user_model.id) if user_model.id else None,
        username=user_model.username,
        email=user_model.email,
        full_name=user_model.full_name,
        status=status,
        created_at=user_model.created_at,
        updated_at=user_model.updated_at,
        last_login_at=user_model.last_login
    )


def domain_user_to_model(user):
    """Convert domain User entity to UserModel."""
    from core.domain.user import UserStatus
    
    # Convert status to is_active
    is_active = user.status == UserStatus.ACTIVE if hasattr(user, 'status') else user.is_active()
    
    return UserModel(
        id=UUID(user.id) if user.id else uuid4(),
        username=user.username,
        email=user.email,
        full_name=user.full_name,
        is_active=is_active,
        created_at=user.created_at or datetime.utcnow(),
        updated_at=user.updated_at or datetime.utcnow(),
        last_login=user.last_login_at,
        settings=getattr(user, 'settings', {}) or {}
    )


def account_model_to_domain(account_model: AccountModel):
    """Convert AccountModel to domain Account entity."""
    from core.domain.account import Account, AccountStatus
    
    # Convert is_active to status
    if account_model.is_active:
        status = AccountStatus.ACTIVE
    else:
        status = AccountStatus.INACTIVE
    
    return Account(
        id=str(account_model.id) if account_model.id else None,
        user_id=str(account_model.user_id),
        email_address=account_model.email,  # DB uses 'email', domain uses 'email_address'
        display_name=account_model.display_name,
        tenant_id=account_model.tenant_id,
        access_token=account_model.access_token,
        refresh_token=account_model.refresh_token,
        token_expires_at=account_model.token_expires_at,
        status=status,
        last_sync_at=account_model.last_sync_at,
        delta_link=account_model.delta_link,
        sync_enabled=account_model.sync_enabled,
        created_at=account_model.created_at,
        updated_at=account_model.updated_at
    )


def domain_account_to_model(account):
    """Convert domain Account entity to AccountModel."""
    from core.domain.account import AccountStatus
    
    # Convert status to is_active
    is_active = account.status == AccountStatus.ACTIVE if hasattr(account, 'status') else account.is_active()
    
    return AccountModel(
        id=UUID(account.id) if account.id else uuid4(),
        user_id=UUID(account.user_id) if isinstance(account.user_id, str) else account.user_id,
        email=account.email_address,  # Domain uses 'email_address', DB uses 'email'
        display_name=account.display_name,
        tenant_id=account.tenant_id,
        access_token=account.access_token,
        refresh_token=account.refresh_token,
        token_expires_at=account.token_expires_at,
        is_active=is_active,
        is_authorized=getattr(account, 'is_authorized', False),
        last_sync_at=account.last_sync_at,
        delta_link=account.delta_link,
        sync_enabled=account.sync_enabled,
        created_at=account.created_at or datetime.utcnow(),
        updated_at=account.updated_at or datetime.utcnow(),
        settings=getattr(account, 'settings', {}) or {}
    )


def email_model_to_domain(email_model: EmailModel):
    """Convert EmailModel to domain Email entity."""
    from core.domain.email import Email
    
    return Email(
        id=email_model.id,
        account_id=email_model.account_id,
        message_id=email_model.message_id,
        conversation_id=email_model.conversation_id,
        subject=email_model.subject,
        body=email_model.body,
        body_preview=email_model.body_preview,
        sender=email_model.sender,
        recipients=email_model.recipients or [],
        cc_recipients=email_model.cc_recipients or [],
        bcc_recipients=email_model.bcc_recipients or [],
        received_at=email_model.received_at,
        sent_at=email_model.sent_at,
        folder=email_model.folder,
        importance=email_model.importance,
        priority=email_model.priority,
        is_read=email_model.is_read,
        has_attachments=email_model.has_attachments,
        attachments=email_model.attachments or [],
        processing_status=email_model.processing_status,
        processed_at=email_model.processed_at,
        created_at=email_model.created_at,
        updated_at=email_model.updated_at,
        metadata=email_model.email_metadata or {}
    )


def domain_email_to_model(email):
    """Convert domain Email entity to EmailModel."""
    return EmailModel(
        id=email.id,
        account_id=email.account_id,
        message_id=email.message_id,
        conversation_id=email.conversation_id,
        subject=email.subject,
        body=email.body,
        body_preview=email.body_preview,
        sender=email.sender,
        recipients=email.recipients,
        cc_recipients=email.cc_recipients,
        bcc_recipients=email.bcc_recipients,
        received_at=email.received_at,
        sent_at=email.sent_at,
        folder=email.folder,
        importance=email.importance,
        priority=email.priority,
        is_read=email.is_read,
        has_attachments=email.has_attachments,
        attachments=email.attachments,
        processing_status=email.processing_status,
        processed_at=email.processed_at,
        created_at=email.created_at,
        updated_at=email.updated_at,
        email_metadata=email.metadata
    )


def transmission_record_model_to_domain(record_model: TransmissionRecordModel):
    """Convert TransmissionRecordModel to domain TransmissionRecord entity."""
    from core.domain.transmission_record import TransmissionRecord
    
    return TransmissionRecord(
        id=record_model.id,
        email_id=record_model.email_id,
        endpoint=record_model.endpoint,
        method=record_model.method,
        status=record_model.status,
        priority=record_model.priority,
        retry_count=record_model.retry_count,
        max_retries=record_model.max_retries,
        next_retry_at=record_model.next_retry_at,
        response_status_code=record_model.response_status_code,
        response_data=record_model.response_data,
        error_message=record_model.error_message,
        started_at=record_model.started_at,
        completed_at=record_model.completed_at,
        processing_time_ms=record_model.processing_time_ms,
        created_at=record_model.created_at,
        updated_at=record_model.updated_at,
        metadata=record_model.record_metadata or {}
    )


def domain_transmission_record_to_model(record):
    """Convert domain TransmissionRecord entity to TransmissionRecordModel."""
    return TransmissionRecordModel(
        id=record.id,
        email_id=record.email_id,
        endpoint=record.endpoint,
        method=record.method,
        status=record.status,
        priority=record.priority,
        retry_count=record.retry_count,
        max_retries=record.max_retries,
        next_retry_at=record.next_retry_at,
        response_status_code=record.response_status_code,
        response_data=record.response_data,
        error_message=record.error_message,
        started_at=record.started_at,
        completed_at=record.completed_at,
        processing_time_ms=record.processing_time_ms,
        created_at=record.created_at,
        updated_at=record.updated_at,
        record_metadata=record.metadata
    )
